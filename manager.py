import ipaddress
import logging
import socket

from PyQt6.QtCore import QObject, pyqtSignal, QTimer, QByteArray
from PyQt6.QtNetwork import QUdpSocket, QHostAddress

from device import IEMDevice
from protocol import build_command, parse_response

log = logging.getLogger(__name__)

PORT = 53212
PUSH_INTERVAL_MS = 55000       # Re-subscribe every 55s (subscription lasts 60s)
PUSH_UPDATE_RATE = 500         # Device sends updates every 500ms
SCAN_TIMEOUT_MS = 2000
OFFLINE_THRESHOLD = 3


class DeviceManager(QObject):
    device_discovered = pyqtSignal(str)         # ip
    device_updated = pyqtSignal(str)            # ip
    device_went_offline = pyqtSignal(str)       # ip
    device_came_online = pyqtSignal(str)        # ip
    scan_finished = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.devices: dict[str, IEMDevice] = {}

        self._socket = QUdpSocket(self)
        bound = self._socket.bind(QHostAddress.SpecialAddress.AnyIPv4, PORT)
        self._bind_ok = bound
        if not bound:
            log.warning("Could not bind to UDP port %d: %s", PORT, self._socket.errorString())
        else:
            log.info("Bound to UDP port %d", PORT)
        self._socket.readyRead.connect(self._on_data_ready)

        self._push_timer = QTimer(self)
        self._push_timer.timeout.connect(self._renew_subscriptions)

        self._health_timer = QTimer(self)
        self._health_timer.timeout.connect(self._check_all_health)

        self._scanning = False

    # --- Scanning ---

    def clear_devices(self):
        self._push_timer.stop()
        self._health_timer.stop()
        self.devices.clear()

    @staticmethod
    def get_interfaces() -> list[dict]:
        """Return list of available network interfaces with IP info."""
        import netifaces
        result = []
        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_INET in addrs:
                for addr in addrs[netifaces.AF_INET]:
                    ip = addr.get("addr", "")
                    mask = addr.get("netmask", "255.255.255.0")
                    if ip and not ip.startswith("127."):
                        result.append({"name": iface, "ip": ip, "mask": mask})
        return result

    def start_scan(self, interface: dict | None = None):
        self._push_timer.stop()
        self._scanning = True

        if interface:
            local_ip, netmask = interface["ip"], interface["mask"]
        else:
            ifaces = self.get_interfaces()
            if not ifaces:
                self._scanning = False
                self.scan_finished.emit()
                return
            local_ip, netmask = ifaces[0]["ip"], ifaces[0]["mask"]

        log.info("Scanning %s/%s, socket bound: %s, local port: %s", local_ip, netmask, self._bind_ok, self._socket.localPort())
        network = ipaddress.IPv4Network(f"{local_ip}/{netmask}", strict=False)
        cmd = build_command("Push", 5, 1000, 3).encode("ascii")
        sent = 0
        for host in network.hosts():
            host_str = str(host)
            if host_str == local_ip:
                continue
            self._socket.writeDatagram(
                QByteArray(cmd),
                QHostAddress(host_str),
                PORT,
            )
            sent += 1

        log.info("Sent Push to %d hosts, waiting %dms...", sent, SCAN_TIMEOUT_MS)
        QTimer.singleShot(SCAN_TIMEOUT_MS, self._finish_scan)

    def _finish_scan(self):
        self._scanning = False
        self._renew_subscriptions()
        self._push_timer.start(PUSH_INTERVAL_MS)
        self._health_timer.start(2000)
        self.scan_finished.emit()

    # --- Data handling ---

    def _on_data_ready(self):
        while self._socket.hasPendingDatagrams():
            data, host, port = self._socket.readDatagram(
                self._socket.pendingDatagramSize()
            )
            ip = host.toString()
            # Strip IPv6 prefix if present (e.g. "::ffff:192.168.1.143")
            if ip.startswith("::ffff:"):
                ip = ip[7:]
            message = bytes(data).decode("ascii", errors="ignore")
            log.debug("UDP recv from %s:%d: %s", ip, port, message[:80])

            if ip not in self.devices:
                self._add_device(ip)
                self.device_discovered.emit(ip)

            parsed = parse_response(message)
            config_changed = False
            for update in parsed:
                if update["type"] == "Config":
                    config_changed = True
                self._apply_update(ip, update)

            if config_changed:
                self._query_all_params(ip)

            self.device_updated.emit(ip)

    def _add_device(self, ip: str):
        if ip not in self.devices:
            self.devices[ip] = IEMDevice(ip=ip, online=True)

    def _apply_update(self, ip: str, update: dict):
        dev = self.devices.get(ip)
        if not dev:
            return

        was_offline = not dev.online
        dev.online = True
        dev._missed_pushes = 0
        if was_offline:
            self.device_came_online.emit(ip)

        t = update["type"]
        if t == "Name":
            dev.name = update["value"]
        elif t == "Frequency":
            dev.frequency = update["value"]
        elif t == "Sensitivity":
            dev.sensitivity = update["value"]
        elif t == "States":
            dev.mute = update["mute"]
        elif t == "Mode":
            dev.mode = update["value"]
        elif t == "Equalizer":
            dev.eq = update["bands"]
        elif t == "AF":
            dev.audio_level_l = update["peak_l"]
            dev.audio_level_r = update["peak_r"]
            dev.audio_hold_l = update["hold_l"]
            dev.audio_hold_r = update["hold_r"]
        elif t == "RF":
            dev.rf_power = update["value"]
        elif t == "LockMode":
            dev.panel_locked = update["value"]
        elif t == "Identify":
            pass  # no state to apply

    def _query_all_params(self, ip: str):
        for cmd_name in ["Frequency", "Name", "Sensitivity", "Equalizer", "Mode", "RF", "LockMode"]:
            self._send_to(ip, build_command(cmd_name))

    # --- Subscriptions ---

    def _renew_subscriptions(self):
        cmd = build_command("Push", 60, PUSH_UPDATE_RATE, 3)
        for ip in self.devices:
            self._send_to(ip, cmd)

    # --- Health checks ---

    def _check_all_health(self):
        for ip in list(self.devices.keys()):
            self._check_missed_push(ip)

    def _check_missed_push(self, ip: str):
        dev = self.devices.get(ip)
        if not dev:
            return
        dev._missed_pushes += 1
        if dev._missed_pushes >= OFFLINE_THRESHOLD and dev.online:
            dev.online = False
            self.device_went_offline.emit(ip)

    # --- Commands ---

    def send_command(self, ip: str, command: str):
        self._send_to(ip, command)

    def set_sensitivity(self, ip: str, value: int):
        self._send_to(ip, build_command("Sensitivity", value))

    def set_mute(self, ip: str, mute: bool):
        self._send_to(ip, build_command("Mute", 1 if mute else 0))

    def set_frequency(self, ip: str, freq: int):
        self._send_to(ip, build_command("Frequency", freq))

    def set_name(self, ip: str, name: str):
        self._send_to(ip, build_command("Name", name))

    def set_mode(self, ip: str, mode: str):
        val = 1 if mode == "stereo" else 0
        self._send_to(ip, build_command("Mode", val))

    def set_equalizer(self, ip: str, enabled: bool, bands: list[int]):
        en = "#1" if enabled else "#0"
        self._send_to(ip, build_command("Equalizer", en, *bands))

    def set_rf_power(self, ip: str, level: str):
        self._send_to(ip, build_command("RF", level))

    def set_panel_lock(self, ip: str, locked: bool):
        self._send_to(ip, build_command("LockMode", 1 if locked else 0))

    def identify(self, ip: str):
        self._send_to(ip, build_command("Identify", 1))

    # --- Mass operations ---

    def mass_set_sensitivity(self, ips: list[str], value: int):
        for ip in ips:
            self.set_sensitivity(ip, value)

    def mass_set_mute(self, ips: list[str], mute: bool):
        for ip in ips:
            self.set_mute(ip, mute)

    def mass_set_mode(self, ips: list[str], mode: str):
        for ip in ips:
            self.set_mode(ip, mode)

    def mass_set_eq(self, ips: list[str], enabled: bool, bands: list[int]):
        for ip in ips:
            self.set_equalizer(ip, enabled, bands)

    def mass_set_rf_power(self, ips: list[str], level: str):
        for ip in ips:
            self.set_rf_power(ip, level)

    def mass_set_panel_lock(self, ips: list[str], locked: bool):
        for ip in ips:
            self.set_panel_lock(ip, locked)

    def mass_identify(self, ips: list[str]):
        for ip in ips:
            self.identify(ip)

    def mass_reset(self, ips: list[str]):
        for ip in ips:
            self.set_sensitivity(ip, -18)
            self.set_mode(ip, "stereo")
            self.set_equalizer(ip, False, [0, 0, 0, 0, 0])
            self.set_rf_power(ip, "Std")
            self.set_panel_lock(ip, False)
            self.set_mute(ip, False)

    def mute_all(self):
        for ip in self.devices:
            self.set_mute(ip, True)

    def unmute_all(self):
        for ip in self.devices:
            self.set_mute(ip, False)

    def identify_all(self):
        for ip in self.devices:
            self.identify(ip)

    # --- Internal ---

    def _send_to(self, ip: str, command: str):
        self._socket.writeDatagram(
            QByteArray(command.encode("ascii")),
            QHostAddress(ip),
            PORT,
        )
