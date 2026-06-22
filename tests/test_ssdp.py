from __future__ import annotations

import unittest
import socket
from unittest.mock import Mock, patch

from copy_air_bridge.ssdp import SsdpAdvertisement, SsdpAdvertiser, advertised_host, build_location, build_notify_message, build_search_response


class SsdpTest(unittest.TestCase):
    def create_advertisement(self) -> SsdpAdvertisement:
        return SsdpAdvertisement(
            service_type="urn:schemas-upnp-org:device:CopyAirBridge:1",
            location="http://192.0.2.20:8080",
            server="CopyAirBridge/0.1 UPnP/1.1",
            unique_service_name="uuid:copy-air-bridge::urn:schemas-upnp-org:device:CopyAirBridge:1",
            notify_interval_seconds=30,
        )

    def test_search_response_contains_discovery_headers(self) -> None:
        response = build_search_response(self.create_advertisement()).decode("utf-8")

        self.assertTrue(response.startswith("HTTP/1.1 200 OK\r\n"))
        self.assertIn("CACHE-CONTROL: max-age=90\r\n", response)
        self.assertIn("EXT:\r\n", response)
        self.assertIn("LOCATION: http://192.0.2.20:8080\r\n", response)
        self.assertIn("ST: urn:schemas-upnp-org:device:CopyAirBridge:1\r\n", response)
        self.assertIn("USN: uuid:copy-air-bridge::urn:schemas-upnp-org:device:CopyAirBridge:1\r\n", response)
        self.assertTrue(response.endswith("\r\n\r\n"))

    def test_notify_message_contains_alive_headers(self) -> None:
        response = build_notify_message(self.create_advertisement(), "ssdp:alive").decode("utf-8")

        self.assertTrue(response.startswith("NOTIFY * HTTP/1.1\r\n"))
        self.assertIn("HOST: 239.255.255.250:1900\r\n", response)
        self.assertIn("NTS: ssdp:alive\r\n", response)
        self.assertIn("NT: urn:schemas-upnp-org:device:CopyAirBridge:1\r\n", response)

    def test_build_location_uses_configured_host_when_specific(self) -> None:
        self.assertEqual(build_location("192.0.2.30", 8080), "http://192.0.2.30:8080/rootDesc.xml")

    def test_advertised_host_resolves_wildcard_binding(self) -> None:
        with patch("copy_air_bridge.ssdp.socket.gethostname", return_value="bridge.local"):
            with patch("copy_air_bridge.ssdp.socket.gethostbyname", return_value="192.0.2.40"):
                self.assertEqual(advertised_host("0.0.0.0"), "192.0.2.40")

    def test_start_uses_configured_multicast_interface(self) -> None:
        socket_instance = Mock()
        with patch("copy_air_bridge.ssdp.socket.socket", return_value=socket_instance):
            with patch("copy_air_bridge.ssdp.threading.Thread") as thread_class:
                advertiser = SsdpAdvertiser(self.create_advertisement(), interface="192.0.2.20")

                advertiser.start()

        socket_instance.bind.assert_called_once_with(("", 1900))
        self.assertTrue(socket_instance.settimeout.called)
        self.assertTrue(thread_class.return_value.start.called)
        socket_options = [call.args for call in socket_instance.setsockopt.call_args_list]
        self.assertIn((socket.IPPROTO_IP, socket.IP_MULTICAST_IF, b"\xc0\x00\x02\x14"), socket_options)
        self.assertIn((socket.IPPROTO_IP, socket.IP_MULTICAST_LOOP, 1), socket_options)

    def test_run_keeps_listening_after_socket_timeout(self) -> None:
        socket_instance = Mock()
        socket_instance.recvfrom.side_effect = [socket.timeout(), KeyboardInterrupt()]
        advertiser = SsdpAdvertiser(self.create_advertisement())
        advertiser._socket = socket_instance
        advertiser._stop_event.set = Mock()

        with self.assertRaises(KeyboardInterrupt):
            advertiser._run()

        self.assertEqual(socket_instance.recvfrom.call_count, 2)

    def test_matching_search_accepts_header_without_space_after_colon(self) -> None:
        advertiser = SsdpAdvertiser(self.create_advertisement())
        message = b"M-SEARCH * HTTP/1.1\r\nHOST:239.255.255.250:1900\r\nMAN:\"ssdp:discover\"\r\nST:urn:schemas-upnp-org:device:CopyAirBridge:1\r\n\r\n"

        self.assertTrue(advertiser._is_matching_search(message))

    def test_matching_search_accepts_ssdp_all(self) -> None:
        advertiser = SsdpAdvertiser(self.create_advertisement())
        message = b"M-SEARCH * HTTP/1.1\r\nMAN: \"ssdp:discover\"\r\nST: ssdp:all\r\n\r\n"

        self.assertTrue(advertiser._is_matching_search(message))

    def test_search_ignores_non_matching_search_target(self) -> None:
        advertiser = SsdpAdvertiser(self.create_advertisement())
        message = b"M-SEARCH * HTTP/1.1\r\nMAN: \"ssdp:discover\"\r\nST: urn:schemas-upnp-org:device:Other:1\r\n\r\n"

        self.assertTrue(advertiser._is_search(message))
        self.assertFalse(advertiser._is_matching_search(message))


if __name__ == "__main__":
    unittest.main()