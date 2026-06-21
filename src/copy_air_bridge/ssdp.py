from __future__ import annotations

import socket
import threading
import time
import logging
from dataclasses import dataclass


LOGGER = logging.getLogger("copy_air_bridge")
SSDP_ADDRESS = "239.255.255.250"
SSDP_PORT = 1900


@dataclass(frozen=True)
class SsdpAdvertisement:
    service_type: str
    location: str
    server: str
    unique_service_name: str
    notify_interval_seconds: int


def advertised_host(host: str) -> str:
    if host not in {"0.0.0.0", "::"}:
        return host
    try:
        return socket.gethostbyname(socket.gethostname())
    except OSError:
        return "127.0.0.1"


def build_location(host: str, port: int) -> str:
    return f"http://{advertised_host(host)}:{port}/rootDesc.xml"


def build_search_response(advertisement: SsdpAdvertisement) -> bytes:
    return _encode_headers(
        "HTTP/1.1 200 OK",
        {
            "CACHE-CONTROL": f"max-age={advertisement.notify_interval_seconds * 3}",
            "EXT": "",
            "LOCATION": advertisement.location,
            "SERVER": advertisement.server,
            "ST": advertisement.service_type,
            "USN": advertisement.unique_service_name,
        },
    )


def build_notify_message(advertisement: SsdpAdvertisement, notification_sub_type: str) -> bytes:
    return _encode_headers(
        "NOTIFY * HTTP/1.1",
        {
            "HOST": f"{SSDP_ADDRESS}:{SSDP_PORT}",
            "CACHE-CONTROL": f"max-age={advertisement.notify_interval_seconds * 3}",
            "LOCATION": advertisement.location,
            "NT": advertisement.service_type,
            "NTS": notification_sub_type,
            "SERVER": advertisement.server,
            "USN": advertisement.unique_service_name,
        },
    )


def _encode_headers(start_line: str, headers: dict[str, str]) -> bytes:
    header_lines = [start_line]
    header_lines.extend(f"{name}: {value}" if value else f"{name}:" for name, value in headers.items())
    return ("\r\n".join(header_lines) + "\r\n\r\n").encode("utf-8")


class SsdpAdvertiser:
    def __init__(self, advertisement: SsdpAdvertisement, interface: str | None = None) -> None:
        self.advertisement = advertisement
        self.interface = interface
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket: socket.socket | None = None

    def start(self) -> None:
        if self._thread is not None:
            return
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError as error:
                LOGGER.info("SSDP SO_REUSEPORT unavailable: %s", error)
        self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
        self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1)
        self._socket.bind(("", SSDP_PORT))
        interface = self.interface or "0.0.0.0"
        membership = socket.inet_aton(SSDP_ADDRESS) + socket.inet_aton(interface)
        self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, membership)
        if self.interface is not None:
            self._socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_IF, socket.inet_aton(self.interface))
        self._socket.settimeout(1.0)

        self._thread = threading.Thread(target=self._run, name="copy-air-bridge-ssdp", daemon=True)
        self._thread.start()
        LOGGER.info("SSDP advertiser started: location=%s interface=%s", self.advertisement.location, interface)

    def stop(self) -> None:
        self._stop_event.set()
        if self._socket is not None:
            self._send_notify("ssdp:byebye")
            self._socket.close()
            self._socket = None
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None

    def _run(self) -> None:
        LOGGER.info("SSDP THREAD STARTED")
        self._send_notify("ssdp:alive")
        next_notify_at = time.monotonic() + self.advertisement.notify_interval_seconds
        while not self._stop_event.is_set():
            if time.monotonic() >= next_notify_at:
                self._send_notify("ssdp:alive")
                next_notify_at = time.monotonic() + self.advertisement.notify_interval_seconds
            try:
                message, address = self._socket.recvfrom(1024) if self._socket is not None else (b"", ("", 0))
            except socket.timeout:
                continue
            except OSError:
                return
            if self._is_matching_search(message):
                LOGGER.info("SSDP M-SEARCH matched from %s", address)
                self._send_response(address)
            elif self._is_search(message):
                LOGGER.info("SSDP M-SEARCH ignored from %s: %s", address, self._compact_message(message))

    def _is_search(self, message: bytes) -> bool:
        text = message.decode("utf-8", errors="ignore").lower()
        return "m-search" in text and "ssdp:discover" in text

    def _is_matching_search(self, message: bytes) -> bool:
        text = message.decode("utf-8", errors="ignore").lower()
        if "m-search" not in text or "ssdp:discover" not in text:
            return False
        return f"st: {self.advertisement.service_type.lower()}" in text or "st: ssdp:all" in text

    def _compact_message(self, message: bytes) -> str:
        return " | ".join(message.decode("utf-8", errors="ignore").splitlines())

    def _send_notify(self, notification_sub_type: str) -> None:
        if self._socket is not None:
            try:
                self._socket.sendto(build_notify_message(self.advertisement, notification_sub_type), (SSDP_ADDRESS, SSDP_PORT))
            except OSError as error:
                LOGGER.info("Failed to send SSDP %s notification: %s", notification_sub_type, error)

    def _send_response(self, address: tuple[str, int]) -> None:
        if self._socket is not None:
            LOGGER.info("Sending SSDP response to %s", address)
            try:
                self._socket.sendto(build_search_response(self.advertisement), address)
            except OSError as error:
                LOGGER.info("Failed to send SSDP response to %s: %s", address, error)