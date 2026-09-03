import io
import ipaddress
import json
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import mock_open, patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from SysAdminToolbox import SysAdminToolbox as sat  # type: ignore[attr-defined]  # noqa: E402


class ConversionTests(unittest.TestCase):
    def test_ipv4_validation(self):
        self.assertEqual(sat._validate_ip("192.0.2.1"), "192.0.2.1")
        for value in ("192.0.2", "192.0.2.256", "192.0.x.1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                sat._validate_ip(value)

    def test_every_cidr_round_trips(self):
        for cidr in range(33):
            with self.subTest(cidr=cidr):
                mask = sat.cidr_to_mask(cidr)
                self.assertEqual(sat.mask_to_cidr(mask), cidr)
                self.assertEqual(
                    sat.wildcard_to_mask(sat.mask_to_wildcard(mask)), mask
                )
        for cidr in (-1, 33):
            with self.subTest(cidr=cidr), self.assertRaises(ValueError):
                sat.cidr_to_mask(cidr)

    def test_non_contiguous_masks_are_rejected(self):
        for mask in ("255.0.255.0", "255.255.127.0", "128.255.0.0"):
            with self.subTest(mask=mask), self.assertRaises(ValueError):
                sat._validate_mask(mask)

    def test_decimal_binary(self):
        self.assertEqual(sat.decimal_to_binary(42), "101010")
        self.assertEqual(sat.decimal_to_binary(-300), "-100101100")
        self.assertEqual(sat.decimal_to_binary_signed(-1), "11111111")
        self.assertIsNone(sat.decimal_to_binary_values(255)["signed_8bit"])
        self.assertIsNone(sat.decimal_to_binary_values(-300)["unsigned"])
        with self.assertRaises(ValueError):
            sat.decimal_to_binary_signed(128)

    def test_binary_decimal(self):
        self.assertEqual(sat.binary_to_decimal_values("11111111"), {
            "binary": "11111111", "unsigned": 255, "signed": -1,
        })
        self.assertEqual(sat.binary_to_decimal("101010"), 42)
        with self.assertRaises(ValueError):
            sat.binary_to_decimal("10201")
        with self.assertRaises(ValueError):
            sat.binary_to_decimal("")

    def test_hexadecimal(self):
        self.assertEqual(sat.decimal_to_hexadecimal(-255), "-ff")
        self.assertEqual(sat.hexadecimal_to_decimal("0xff"), 255)
        self.assertEqual(sat.binary_to_hexadecimal("11111111"), "ff")
        self.assertEqual(sat.hexadecimal_to_binary("2a"), "101010")
        with self.assertRaises(ValueError):
            sat.hexadecimal_to_decimal("not-hexadecimal")

    def test_ipv4_binary(self):
        binary = "11000000.10101000.00000001.00000001"
        self.assertEqual(sat.ip_to_binary("192.168.1.1"), binary)
        self.assertEqual(
            sat.ip_to_binary_full("192.168.1.1"),
            "IPv4 address: 192.168.1.1\n"
            f"Binary (32-bit): {binary}",
        )
        self.assertEqual(sat.binary_to_ip(binary), "192.168.1.1")
        self.assertEqual(sat.binary_to_ip(binary.replace(".", "")), "192.168.1.1")
        with self.assertRaises(ValueError):
            sat.binary_to_ip("1010")

    def test_ipv4_info(self):
        result = sat.ipv4_info("192.168.1.42/24")
        self.assertEqual(result["integer"], 3232235818)
        self.assertEqual(result["hexadecimal"], "0xC0A8012A")
        self.assertEqual(result["network"], "192.168.1.0/24")
        self.assertEqual(result["reverse_pointer"], "42.1.168.192.in-addr.arpa")

    def test_ipv4_range_to_minimal_cidrs(self):
        self.assertEqual(
            sat.ipv4_range_to_cidrs("192.168.1.10", "192.168.1.35"),
            ["192.168.1.10/31", "192.168.1.12/30", "192.168.1.16/28", "192.168.1.32/30"],
        )
        with self.assertRaises(ValueError):
            sat.ipv4_range_to_cidrs("192.168.1.35", "192.168.1.10")

    def test_iana_special_purpose_classification(self):
        cases = {
            "100.64.0.1": ("shared", False, "current"),
            "192.0.0.9": ("global", True, "current"),
            "192.88.99.1": ("special", None, "legacy"),
            "203.0.113.8": ("documentation", False, "current"),
            "2001:1::3": ("global", True, "current"),
            "2001:10::1": ("special", False, "legacy"),
            "2001:db8::1": ("documentation", False, "current"),
            "2001:4860:4860::8888": ("global", True, "current"),
        }
        for address, expected in cases.items():
            with self.subTest(address=address):
                result = sat.classify_ip(address)
                self.assertEqual(
                    (result["scope"], result["globally_reachable"], result["status"]),
                    expected,
                )
        with self.assertRaises(ValueError):
            sat.classify_ip("not-an-address")


class SubnetTests(unittest.TestCase):
    def test_subnet_calculator_common_prefix(self):
        result = sat.subnet_calculator("192.168.1.42", "255.255.255.0")
        self.assertEqual(result["network_address"], "192.168.1.0")
        self.assertEqual(result["broadcast"], "192.168.1.255")
        self.assertEqual(result["hosts"], 254)

    def test_point_to_point_and_host_routes(self):
        p2p = sat.subnet_calculator("192.0.2.0", "255.255.255.254")
        host = sat.subnet_calculator("192.0.2.1", "255.255.255.255")
        self.assertEqual((p2p["hosts"], p2p["broadcast"]), (2, "N/A"))
        self.assertEqual((host["hosts"], host["first_host"]), (1, "192.0.2.1"))

    def test_advanced_ipv4(self):
        result = sat.advanced_subnet_calculator("192.168.1.0/24", "26")
        self.assertEqual(result["count_subnets"], 4)
        self.assertFalse(result["truncated"])
        self.assertEqual(result["subnets"][-1]["network"], "192.168.1.192")

    def test_advanced_ipv6_is_bounded(self):
        result = sat.advanced_subnet_calculator(
            "2001:db8::/32", "64", max_details=3
        )
        self.assertEqual(result["count_subnets"], 2 ** 32)
        self.assertEqual(result["shown_subnets"], 3)
        self.assertTrue(result["truncated"])
        self.assertIn("first_address", result["subnets"][0])
        self.assertNotIn("broadcast", result["subnets"][0])

    def test_advanced_rejects_supernet_request(self):
        with self.assertRaises(ValueError):
            sat.advanced_subnet_calculator("192.168.1.0/24", "16")

    def test_vlsm_keeps_the_whole_remaining_pool(self):
        result = sat.vlsm_calculator("192.168.1.0/24", [50, 30, 10, 10, 10])
        self.assertEqual(
            [f"{row['subnet']}/{row['prefix_length']}" for row in result],
            ["192.168.1.0/26", "192.168.1.64/27", "192.168.1.96/28", "192.168.1.112/28", "192.168.1.128/28"],
        )

    def test_vlsm_detects_exhaustion(self):
        with self.assertRaises(ValueError):
            sat.vlsm_calculator("192.168.1.0/30", [2, 2])

    def test_supernet_ipv4_and_ipv6(self):
        self.assertEqual(
            sat.supernet(["10.0.0.0/25", "10.0.0.128/25"]), "10.0.0.0/24"
        )
        self.assertEqual(
            sat.supernet(["2001:db8::/33", "2001:db8:8000::/33"]), "2001:db8::/32"
        )
        with self.assertRaises(ValueError):
            sat.supernet(["10.0.0.0/24", "2001:db8::/32"])

    def test_overlap(self):
        self.assertEqual(
            sat.check_overlap("10.0.0.0/23", "10.0.1.0/24")["overlap_network"],
            "10.0.1.0/24",
        )
        self.assertFalse(sat.check_overlap("10.0.0.0/24", "10.0.1.0/24")["overlaps"])
        with self.assertRaises(ValueError):
            sat.check_overlap("10.0.0.0/24", "2001:db8::/32")

    def test_contains_exclude_and_nth_address(self):
        self.assertTrue(sat.subnet_contains("10.0.0.0/8", "10.1.2.3")["contains"])
        self.assertFalse(sat.subnet_contains("10.0.0.0/24", "10.0.1.0/24")["contains"])
        self.assertEqual(
            sat.subnet_exclude("192.0.2.0/29", "192.0.2.0/30"),
            ["192.0.2.4/30"],
        )
        self.assertEqual(sat.subnet_nth("192.0.2.0/24", 255)["role"], "broadcast")
        huge = sat.subnet_nth("2001:db8::/32", 2 ** 64)
        self.assertEqual(huge["address"], "2001:db8:0:1::")
        with self.assertRaises(ValueError):
            sat.subnet_nth("192.0.2.0/30", 4)

    def test_subnet_inventory_loading_and_audit(self):
        inventory = {
            "parent": "10.0.0.0/24",
            "allocations": [
                {"name": "users", "network": "10.0.0.0/26", "requested_hosts": 62},
                {"name": "duplicate", "network": "10.0.0.0/26"},
                {"name": "overlap", "network": "10.0.0.32/27"},
                {"name": "too-small", "network": "10.0.0.64/30", "requested_hosts": 3},
                {"name": "outside", "network": "10.0.1.0/24"},
                {"name": "bad", "network": "nope"},
            ],
        }
        result = sat.subnet_audit(inventory["allocations"], inventory["parent"])
        self.assertEqual(result["status"], "issues")
        self.assertEqual(len(result["duplicates"]), 1)
        self.assertTrue(result["overlaps"])
        self.assertEqual(result["capacity_issues"][0]["name"], "too-small")
        self.assertEqual(result["outside_parent"][0]["name"], "outside")
        self.assertEqual(result["invalid"][0]["name"], "bad")
        self.assertTrue(result["free_networks"])

        with tempfile.TemporaryDirectory() as directory:
            json_path = Path(directory) / "inventory.json"
            csv_path = Path(directory) / "inventory.csv"
            text_path = Path(directory) / "inventory.txt"
            json_path.write_text(json.dumps(inventory), encoding="utf-8")
            csv_path.write_text("name,network,requested_hosts\nweb,192.0.2.0/28,10\n", encoding="utf-8")
            text_path.write_text("# allocations\n192.0.2.0/28\n192.0.2.16/28\n", encoding="utf-8")
            self.assertEqual(sat.load_subnet_inventory(str(json_path))["parent"], "10.0.0.0/24")
            self.assertEqual(sat.load_subnet_inventory(str(csv_path))["allocations"][0]["name"], "web")
            self.assertEqual(len(sat.load_subnet_inventory(str(text_path))["allocations"]), 2)


class IPv6Tests(unittest.TestCase):
    def test_expand_compress_and_binary(self):
        self.assertEqual(sat.ipv6_compress(sat.ipv6_expand("2001:db8::1")), "2001:db8::1")
        self.assertEqual(len(sat.ipv6_to_binary("::1").replace(":", "")), 128)

    def test_address_types(self):
        cases = {
            "::1": "loopback",
            "::": "unspecified",
            "fe80::1": "link-local",
            "fd12::1": "unique local",
            "2001:db8::1": "documentation",
            "::ffff:192.0.2.1": "ipv4-mapped",
            "64:ff9b::192.0.2.1": "ipv4-translated (NAT64)",
            "ff02::1": "multicast",
            "2001:4860:4860::8888": "global unicast",
        }
        for address, expected in cases.items():
            with self.subTest(address=address):
                self.assertEqual(sat.ipv6_type(address), expected)

    def test_ipv6_subnet_has_no_broadcast_semantics(self):
        result = sat.ipv6_subnet_calculator("2001:db8::/126")
        self.assertEqual(result["first_address"], "2001:db8::")
        self.assertEqual(result["last_address"], "2001:db8::3")
        self.assertNotIn("broadcast", result)

    @patch.object(sat.secrets, "token_bytes", return_value=bytes.fromhex("123456789a"))
    def test_secure_ula_generation(self, _token_bytes):
        result = sat.generate_ipv6_ula()
        self.assertEqual(result["global_id"], "123456789A")
        self.assertEqual(result["prefix"], "fd12:3456:789a::/48")
        self.assertTrue(ipaddress.ip_network(result["prefix"]).is_private)


class MacAndVendorTests(unittest.TestCase):
    def test_mac_formats_and_bits(self):
        self.assertEqual(sat.mac_normalize("aabb.ccdd.eeff"), "aa:bb:cc:dd:ee:ff")
        self.assertEqual(sat.mac_format("aa:bb:cc:dd:ee:ff", "dash"), "AA-BB-CC-DD-EE-FF")
        info = sat.mac_info("03:00:00:00:00:00")
        self.assertTrue(info["is_multicast"])
        self.assertTrue(info["is_local"])

    @patch.object(sat.secrets, "token_bytes", return_value=b"\xff\x01\x02\x03\x04\x05")
    def test_generated_mac_is_local_unicast(self, _token_bytes):
        generated = sat.generate_local_macs(1)[0]
        self.assertEqual(generated, "fe:01:02:03:04:05")
        info = sat.mac_info(generated)
        self.assertTrue(info["is_local"])
        self.assertTrue(info["is_unicast"])

    def test_mac_generation_limits(self):
        with self.assertRaises(ValueError):
            sat.generate_local_macs(101)
        with self.assertRaises(ValueError):
            sat.mac_format("aa:bb:cc:dd:ee:ff", "unknown")

    def test_local_ieee_oui_database(self):
        registry = (
            "Registry,Assignment,Organization Name,Organization Address\n"
            "MA-L,001122,Example Networks,Paris FR\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "oui.csv"
            database.write_text(registry, encoding="utf-8")
            result = sat.mac_vendor_lookup("00:11:22:33:44:55", str(database))
            self.assertTrue(result["found"])
            self.assertEqual(result["organization"], "Example Networks")
            local = sat.mac_vendor_lookup("02:11:22:33:44:55", str(database))
            self.assertEqual(local["reason"], "locally administered address")

    def test_oui_database_update_validates_and_writes_atomically(self):
        payload = (
            b"Registry,Assignment,Organization Name,Organization Address\n"
            b"MA-L,AABBCC,Example Vendor,Example Address\n"
        )

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self, _limit):
                return payload

        with tempfile.TemporaryDirectory() as directory, \
                patch.object(sat.urllib.request, "urlopen", return_value=Response()):
            destination = Path(directory) / "oui.csv"
            result = sat.update_oui_database(str(destination))
            self.assertEqual(result["entries"], 1)
            self.assertEqual(destination.read_bytes(), payload)
        with self.assertRaises(ValueError):
            sat.update_oui_database(url="http://example.com/oui.csv")
        with self.assertRaises(ValueError):
            sat.update_oui_database(timeout=0)

    def test_vlan_helpers(self):
        cisco = sat.vlan_helper("cisco", 10, "Guest", ["Gi0/1", "Gi0/2"])
        self.assertIn("interface range Gi0/1,Gi0/2", cisco)
        juniper = sat.vlan_helper(
            "juniper", 10, "Guest", ["ge-0/0/1", "ge-0/0/2"]
        )
        self.assertEqual(juniper.count("interface-mode access"), 2)
        self.assertEqual(juniper.count("vlan members Guest"), 2)
        huawei = sat.vlan_helper(
            "huawei", 10, "Guest", ["GigabitEthernet0/0/1"]
        )
        self.assertIn("port default vlan 10", huawei)
        with self.assertRaises(ValueError):
            sat.vlan_helper("cisco", 10, "Guest WiFi")
        with self.assertRaises(ValueError):
            sat.vlan_helper("unknown", 10)
        with self.assertRaises(ValueError):
            sat.vlan_helper("cisco", 4095)
        with self.assertRaises(ValueError):
            sat.vlan_helper("cisco", 10, "Guest", ["Gi0/1\nshutdown"])

    def test_platform_aware_vlan_generation(self):
        current = sat.vlan_helper(
            "cisco", 10, "Guest", ["Gi0/1"], mode="trunk",
            allowed_vlans="10,20-22", native_vlan=99,
        )
        self.assertNotIn("trunk encapsulation", current)
        self.assertIn("switchport trunk allowed vlan 10,20-22", current)
        self.assertIn("switchport trunk native vlan 99", current)
        with self.assertRaises(ValueError):
            sat.vlan_helper("cisco", 10, platform_name="cisco-ios", mode="trunk")
        legacy = sat.vlan_helper(
            "cisco", 10, platform_name="cisco-ios", software_version="15.2",
            mode="trunk", allow_legacy=True,
        )
        self.assertIn("switchport trunk encapsulation dot1q", legacy)
        profiles = sat.platform_profiles(include_legacy=False)
        self.assertTrue(all(profile["status"] == "current" for profile in profiles))

    def test_acl_helpers(self):
        juniper = sat.acl_helper(
            "juniper", "BLOCK", "deny", "tcp", "10.0.0.0/8", "0.0.0.0/0", dst_port=443
        )
        self.assertIn("then discard", juniper)
        self.assertNotIn("then deny", juniper)
        self.assertIn("from destination-port 443", juniper)
        cisco = sat.acl_helper(
            "cisco", "ALLOW_WEB", "permit", "tcp",
            "192.168.1.0/24", "192.0.2.10", dst_port=443,
        )
        self.assertIn(
            "permit tcp 192.168.1.0 0.0.0.255 host 192.0.2.10 eq 443",
            cisco,
        )
        with self.assertRaises(ValueError):
            sat.acl_helper("cisco", "X", "allow", "tcp", "any", "any")
        with self.assertRaises(ValueError):
            sat.acl_helper("cisco", "X", "permit", "icmp", "any", "any", dst_port=80)

    def test_every_cheatsheet(self):
        functions = (
            sat.vlan_cheatsheet, sat.acl_cheatsheet, sat.huawei_vlan_cheatsheet,
            sat.mikrotik_vlan_cheatsheet, sat.firewall_cheatsheet,
            sat.routing_cheatsheet, sat.nat_cheatsheet,
        )
        for function in functions:
            with self.subTest(function=function.__name__):
                self.assertTrue(function())
                with self.assertRaises(ValueError):
                    function("not-a-section")

    def test_vlan_cheatsheet_uses_current_safe_defaults(self):
        default = sat.vlan_cheatsheet()
        trunk = sat.vlan_cheatsheet("trunk")
        vtp = sat.vlan_cheatsheet("vtp")
        troubleshooting = sat.vlan_cheatsheet("troubleshooting")

        self.assertNotIn("ISL", default)
        self.assertNotIn("encapsulation dot1q", default)
        self.assertIn("switchport nonegotiate", trunk)
        self.assertNotIn("encapsulation dot1q", trunk)
        self.assertIn("vtp version 3", vtp)
        self.assertIn("vtp mode transparent", vtp)
        self.assertNotIn("vtp password", vtp.lower())
        self.assertIn("show interfaces trunk", troubleshooting)
        self.assertNotIn("show vtp password", troubleshooting)

    def test_vlan_legacy_cheatsheet_is_explicitly_opt_in(self):
        with self.assertRaises(ValueError):
            sat.vlan_cheatsheet("legacy_trunking")

        legacy = sat.vlan_cheatsheet(include_legacy=True)
        self.assertIn("Legacy Cisco Trunking", legacy)
        self.assertIn("switchport trunk encapsulation dot1q", legacy)
        self.assertIn("switchport trunk encapsulation isl", legacy)
        self.assertIn("VTP Versions 1 and 2", legacy)
        self.assertIn("maintenance and migration only", legacy)

    def test_structured_cheatsheet_metadata(self):
        current = sat.render_cheatsheet("vlan", "trunk", show_sources=True)
        self.assertIn("status: current", current)
        self.assertIn("source: https://", current)
        legacy = sat.render_cheatsheet(
            "vlan", "legacy_trunking", include_legacy=True, show_sources=True
        )
        self.assertIn("status: legacy", legacy)
        self.assertIn("replacement:", legacy)


class NetworkTests(unittest.TestCase):
    def test_port_and_host_validation(self):
        self.assertEqual(sat._validate_host("example.com"), "example.com")
        self.assertEqual(sat._validate_port(65535), 65535)
        for value in (0, 65536):
            with self.subTest(value=value), self.assertRaises(ValueError):
                sat._validate_port(value)

    @patch.object(sat.platform, "system", return_value="Linux")
    @patch.object(sat.subprocess, "run")
    def test_ping_parser(self, run, _system):
        run.return_value = SimpleNamespace(
            stdout="4 packets transmitted, 3 received, 25% packet loss\n"
                   "rtt min/avg/max/mdev = 1.0/2.0/3.0/0.1 ms\n",
            stderr="", returncode=0,
        )
        result = sat.ping_host("127.0.0.1")
        self.assertTrue(result["alive"])
        self.assertEqual(result["packet_loss_pct"], 25.0)
        self.assertEqual(result["avg_ms"], 2.0)

    @patch.object(sat.platform, "system", return_value="Windows")
    @patch.object(sat.subprocess, "run")
    def test_windows_ping_parser(self, run, _system):
        run.return_value = SimpleNamespace(
            stdout=(
                "Packets: Sent = 4, Received = 4, Lost = 0 (0% loss),\n"
                "Minimum = 1ms, Maximum = 3ms, Average = 2ms\n"
            ),
            stderr="", returncode=0,
        )
        result = sat.ping_host("127.0.0.1")
        self.assertTrue(result["alive"])
        self.assertEqual(result["packets_received"], 4)
        self.assertEqual((result["min_ms"], result["avg_ms"], result["max_ms"]), (1.0, 2.0, 3.0))

    @patch.object(sat.platform, "system", return_value="Linux")
    @patch.object(sat.subprocess, "run")
    def test_traceroute_parser(self, run, _system):
        run.return_value = SimpleNamespace(
            stdout="traceroute to example.com\n1 router (192.0.2.1) 1.23 ms\n2 * * *\n",
            stderr="", returncode=0,
        )
        result = sat.traceroute("example.com")
        self.assertEqual(result[0]["ip"], "192.0.2.1")
        self.assertIsNone(result[1]["ip"])

    @patch.object(sat.platform, "system", return_value="Windows")
    @patch.object(sat.subprocess, "run")
    def test_windows_traceroute_parser(self, run, _system):
        run.return_value = SimpleNamespace(
            stdout=(
                "Tracing route to example.com [192.0.2.10]\n"
                "  1    <1 ms    <1 ms    <1 ms  router.local [192.0.2.1]\n"
                "  2     5 ms     6 ms     5 ms  192.0.2.10\n"
                "Trace complete.\n"
            ),
            stderr="", returncode=0,
        )
        result = sat.traceroute("example.com")
        self.assertEqual(result[0]["hostname"], "router.local")
        self.assertEqual(result[0]["ip"], "192.0.2.1")
        self.assertEqual(result[1]["hostname"], "192.0.2.10")

    def test_tcp_checks_against_loopback(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(2)
        port = listener.getsockname()[1]

        def accept_connections():
            for _ in range(2):
                connection, _ = listener.accept()
                connection.close()

        thread = threading.Thread(target=accept_connections, daemon=True)
        thread.start()
        try:
            result = sat.tcp_port_check("127.0.0.1", [port])
            self.assertEqual(result[0]["state"], "open")
            advanced = sat.tcp_port_scan_advanced("127.0.0.1", [port])
            self.assertEqual(advanced[0]["state"], "open")
        finally:
            listener.close()
            thread.join(timeout=1)

    def test_network_port_scan_against_loopback(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        try:
            result = sat.scan_network_port("127.0.0.1/32", port)
            self.assertEqual(result[0]["ip"], "127.0.0.1")
            self.assertEqual(result[0]["state"], "open")
        finally:
            listener.close()

    def test_udp_check_against_loopback(self):
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        server.bind(("127.0.0.1", 0))
        port = server.getsockname()[1]

        def serve():
            data, address = server.recvfrom(1024)
            server.sendto(data or b"ok", address)

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            result = sat.udp_port_check("127.0.0.1", [port], timeout=1)
            self.assertEqual(result[0]["state"], "open")
        finally:
            server.close()
            thread.join(timeout=1)

    def test_banner_grab_against_loopback(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        def serve():
            conn, _ = listener.accept()
            with conn:
                conn.recv(1024)
                conn.sendall(b"TEST BANNER\r\n")

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        try:
            self.assertEqual(sat.banner_grab("127.0.0.1", port), "TEST BANNER")
        finally:
            listener.close()
            thread.join(timeout=1)

    @patch.object(sat.subprocess, "run")
    def test_whois(self, run):
        run.return_value = SimpleNamespace(stdout="Domain Name: EXAMPLE.COM\n", stderr="", returncode=0)
        self.assertIn("EXAMPLE.COM", sat.whois_lookup("example.com"))

    @patch.object(sat.subprocess, "run")
    def test_dns_record_lookup(self, run):
        run.side_effect = [
            SimpleNamespace(stdout="example.com. 300 IN A 192.0.2.1\n", stderr="", returncode=0),
            SimpleNamespace(stdout="raw", stderr="", returncode=0),
        ]
        result = sat.dns_lookup_type("example.com", "A")
        self.assertEqual(result["records"], ["example.com. 300 IN A 192.0.2.1"])

    def test_dns_record_rejects_unknown_type(self):
        result = sat.dns_lookup_type("example.com", "BOGUS")
        self.assertIn("error", result)

    @patch.object(
        sat.socket,
        "getaddrinfo",
        return_value=[(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("192.0.2.1", 0))],
    )
    @patch.object(sat.subprocess, "run", side_effect=FileNotFoundError)
    def test_dns_address_lookup_has_stdlib_fallback(self, _run, _getaddrinfo):
        result = sat.dns_lookup_type("example.com", "A")
        self.assertEqual(result["records"], ["example.com. 0 IN A 192.0.2.1"])
        self.assertEqual(result["fallback"], "socket.getaddrinfo")

    @patch.object(sat, "dns_lookup_type")
    def test_dns_compare(self, lookup):
        lookup.side_effect = [
            {"records": ["example.com. 60 IN A 192.0.2.1"]},
            {"records": ["example.com. 60 IN A 192.0.2.2"]},
        ]
        result = sat.dns_compare("example.com", ["1.1.1.1", "8.8.8.8"])
        self.assertEqual(result["results"]["1.1.1.1"], ["192.0.2.1"])

    @patch.object(sat.subprocess, "run")
    def test_dns_zone_transfer(self, run):
        run.return_value = SimpleNamespace(
            stdout="example.com. 3600 IN SOA ns.example.com. hostmaster.example.com. 1 2 3 4 5\n",
            stderr="", returncode=0,
        )
        result = sat.dns_zone_transfer("example.com", "ns.example.com")
        self.assertTrue(result["success"])
        self.assertEqual(result["nameserver"], "ns.example.com")

    @patch("builtins.open", new_callable=mock_open, read_data=(
        "IP address HW type Flags HW address Mask Device\n"
        "192.0.2.1 0x1 0x2 aa:bb:cc:dd:ee:ff * eth0\n"
    ))
    @patch.object(sat.platform, "system", return_value="Linux")
    def test_arp_table(self, _system, _open):
        result = sat.arp_scan()
        self.assertEqual(result[0]["state"], "reachable")

    @patch.object(sat.platform, "system", return_value="Windows")
    @patch.object(sat.subprocess, "run")
    def test_windows_arp_table(self, run, _system):
        run.return_value = SimpleNamespace(
            stdout=(
                "Interface: 192.0.2.10 --- 0x6\n"
                "  Internet Address      Physical Address      Type\n"
                "  192.0.2.1             aa-bb-cc-dd-ee-ff     dynamic\n"
            ),
            stderr="", returncode=0,
        )
        result = sat.arp_scan()
        self.assertEqual(result[0], {
            "ip": "192.0.2.1", "mac": "aa:bb:cc:dd:ee:ff",
            "interface": "192.0.2.10", "state": "dynamic",
        })

    @patch.object(
        sat.socket, "gethostbyaddr",
        return_value=("localhost", [], ["127.0.0.1"]),
    )
    @patch.object(
        sat.socket, "gethostbyname_ex",
        return_value=("localhost", [], ["127.0.0.1"]),
    )
    def test_dns_and_reverse_dns(self, _gethostbyname, _gethostbyaddr):
        self.assertIn("127.0.0.1", sat.dns_lookup("localhost")["addresses"])
        self.assertIn("hostname", sat.reverse_dns_lookup("127.0.0.1"))

    @patch.object(sat.platform, "system", return_value="Linux")
    @patch.object(sat.subprocess, "run")
    def test_ping_sweep_small_network(self, run, _system):
        run.return_value = SimpleNamespace(
            stdout="64 bytes from 192.0.2.1: time=1.2 ms", stderr="", returncode=0,
        )
        result = sat.ping_sweep("192.0.2.0/30", max_threads=2)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(row["alive"] for row in result))

    @patch.object(sat.socket, "gethostbyaddr")
    def test_reverse_dns_sweep_small_network(self, gethostbyaddr):
        gethostbyaddr.side_effect = lambda ip: (f"host-{ip}", [], [ip])
        original_timeout = socket.getdefaulttimeout()
        result = sat.reverse_dns_sweep("192.0.2.0/30", timeout=1, max_threads=2)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(row["hostname"] for row in result))
        self.assertEqual(socket.getdefaulttimeout(), original_timeout)

    def test_network_size_guards(self):
        for function, args in (
            (sat.ping_sweep, ("10.0.0.0/8",)),
            (sat.reverse_dns_sweep, ("10.0.0.0/8",)),
            (sat.scan_network_port, ("10.0.0.0/8", 22)),
        ):
            with self.subTest(function=function.__name__), self.assertRaises(ValueError):
                function(*args)
        with self.assertRaises(ValueError):
            sat.scan_network_port("2001:db8::/126", 22)

    def test_random_ports(self):
        ports = sat.generate_random_ports(50000, 50020, 10)
        self.assertEqual(ports, sorted(set(ports)))
        self.assertTrue(all(50000 <= port <= 50020 for port in ports))
        with self.assertRaises(ValueError):
            sat.generate_random_ports(50020, 50000, 1)
        with self.assertRaises(ValueError):
            sat.generate_random_ports(50000, 50002, 4)

    @patch.object(sat.subprocess, "run")
    def test_asn_lookup(self, run):
        run.return_value = SimpleNamespace(
            stdout='"64496 | 192.0.2.0/24 | ZZ | test | 2020-01-01"\n',
            stderr="", returncode=0,
        )
        result = sat.asn_lookup("192.0.2.1")
        self.assertEqual(result["asn"], "AS64496")
        self.assertEqual(result["prefix"], "192.0.2.0/24")

    @patch.object(sat, "asn_lookup", return_value={
        "ip": "192.0.2.1", "asn": "AS64496", "prefix": "192.0.2.0/24", "country": "ZZ"
    })
    @patch.object(sat, "traceroute", return_value=[{
        "hop": 1, "ip": "192.0.2.1", "hostname": "router", "rtt_ms": 1.0
    }])
    def test_traceroute_asn(self, _traceroute, _asn):
        result = sat.traceroute_asn("example.com")
        self.assertEqual(result[0]["asn"], "AS64496")

    def test_cert_check_parses_certificate(self):
        certificate = {
            "subject": ((('commonName', 'example.com'),),),
            "issuer": ((('organizationName', 'Example CA'),),),
            "serialNumber": "01",
            "notBefore": "Jan 01 00:00:00 2026 GMT",
            "notAfter": "Jan 01 00:00:00 2036 GMT",
            "subjectAltName": (("DNS", "example.com"),),
            "version": 3,
        }

        class ContextManager:
            def __init__(self, value):
                self.value = value

            def __enter__(self):
                return self.value

            def __exit__(self, *_args):
                return False

        class FakeTlsSocket:
            def getpeercert(self, binary_form=False):
                return b"certificate" if binary_form else certificate

            def version(self):
                return "TLSv1.3"

            def cipher(self):
                return ("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256)

            def selected_alpn_protocol(self):
                return "h2"

        fake_context = SimpleNamespace(
            wrap_socket=lambda _sock, server_hostname: ContextManager(FakeTlsSocket())
        )
        with patch.object(sat.ssl, "create_default_context", return_value=fake_context), \
                patch.object(sat.socket, "create_connection", return_value=ContextManager(object())):
            result = sat.cert_check("example.com")
        self.assertEqual(result["subject"], "example.com")
        self.assertEqual(result["issuer"], "Example CA")
        self.assertFalse(result["expired"])
        self.assertFalse(result["not_yet_valid"])
        self.assertTrue(result["hostname_verified"])
        self.assertEqual(result["tls_version"], "TLSv1.3")
        self.assertEqual(result["cipher_bits"], 256)
        self.assertEqual(len(result["sha256_fingerprint"]), 64)

    def test_http_headers_and_scheme_guard(self):
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.send_header("X-Content-Type-Options", "nosniff")
                self.end_headers()
                self.wfile.write(b"ok")

            def log_message(self, _format, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = sat.http_headers(f"http://127.0.0.1:{server.server_port}/")
            self.assertEqual(result["status_code"], 200)
            self.assertTrue(result["security_headers"]["X-Content-Type-Options"]["present"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)
        self.assertIn("error", sat.http_headers("file:///etc/passwd"))

    def test_wait_and_batch_orchestration(self):
        listener = socket.socket()
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        def accept_once():
            connection, _ = listener.accept()
            connection.close()

        thread = threading.Thread(target=accept_once, daemon=True)
        thread.start()
        try:
            ready = sat.wait_for_service("127.0.0.1", port, timeout=1, interval=0.01)
            self.assertEqual(ready["status"], "ready")
        finally:
            listener.close()
            thread.join(timeout=1)

        def worker(value):
            if value == "bad":
                raise ValueError("broken target")
            return {"target": value, "status": "ok"}

        batch = sat.run_batch(["second", "bad", "first"], worker, workers=3)
        self.assertEqual([row["target"] for row in batch], ["second", "bad", "first"])
        self.assertEqual(batch[1]["status"], "failed")

    @patch.object(sat, "http_headers", return_value={"status_code": 200})
    @patch.object(sat, "cert_check", return_value={"expired": False, "days_remaining": 90})
    @patch.object(sat, "tcp_probe", return_value={"status": "ok"})
    @patch.object(sat, "resolve_all", return_value={"status": "ok", "addresses": [{"address": "192.0.2.1"}]})
    def test_doctor_pipeline(self, _resolve, _tcp, _cert, _headers):
        result = sat.doctor_target("https://example.com/health", timeout=1)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(set(result["checks"]), {"dns", "tcp", "tls", "http"})

    @patch.object(sat, "dnssec_status", return_value={"status": "validated"})
    @patch.object(sat, "dns_lookup_type")
    def test_dns_health_includes_delegation_and_mail(self, lookup, _dnssec):
        def answer(domain, record_type="A", server=None, timeout=5):
            values = {
                ("example.com", "A"): ["example.com. 300 IN A 192.0.2.1"],
                ("example.com", "NS"): ["example.com. 300 IN NS ns1.example.com."],
                ("example.com", "SOA"): ["example.com. 300 IN SOA ns1.example.com. hostmaster.example.com. 1 2 3 4 5"],
                ("example.com", "TXT"): ["example.com. 300 IN TXT \"v=spf1 -all\""],
                ("_dmarc.example.com", "TXT"): ["_dmarc.example.com. 300 IN TXT \"v=DMARC1; p=reject\""],
                ("mail._domainkey.example.com", "TXT"): ["mail._domainkey.example.com. 300 IN TXT \"v=DKIM1; p=abc\""],
            }
            return {
                "domain": domain,
                "type": record_type,
                "server": server or "default",
                "records": values.get((domain, record_type), []),
            }

        lookup.side_effect = answer
        result = sat.dns_health("example.com", dkim_selector="mail")
        self.assertEqual(result["status"], "ok")
        self.assertTrue(result["delegation"]["consistent"])
        self.assertTrue(result["mail"]["spf"])
        self.assertTrue(result["mail"]["dmarc"])
        self.assertTrue(result["mail"]["dkim"])
        self.assertEqual(result["dnssec"]["status"], "validated")

    @patch.object(sat, "_resolver_addresses", return_value=["192.0.2.53"])
    @patch.object(sat.platform, "platform", return_value="Test Linux")
    @patch.object(sat.platform, "system", return_value="Linux")
    @patch.object(sat, "_optional_command")
    def test_local_network_inventory_linux(self, command, _system, _platform, _resolvers):
        def response(argv, timeout=10):
            if argv[2] == "address":
                payload = [{
                    "ifname": "eth0", "operstate": "UP", "mtu": 1500,
                    "address": "00:11:22:33:44:55",
                    "addr_info": [{"family": "inet", "local": "192.0.2.10", "prefixlen": 24, "scope": "global"}],
                }]
            else:
                payload = [{"dst": "default", "gateway": "192.0.2.1", "dev": "eth0", "prefsrc": "192.0.2.10"}]
            return {"ok": True, "error": None, "stdout": json.dumps(payload)}

        command.side_effect = response
        result = sat.local_network_inventory()
        self.assertEqual(result["interfaces"][0]["name"], "eth0")
        self.assertEqual(result["routes"][0]["gateway"], "192.0.2.1")
        self.assertEqual(result["dns_servers"], ["192.0.2.53"])

    @patch.object(sat.platform, "platform", return_value="Test Windows")
    @patch.object(sat.platform, "system", return_value="Windows")
    @patch.object(sat, "_optional_command")
    def test_local_network_inventory_windows(self, command, _system, _platform):
        command.return_value = {
            "ok": True,
            "error": None,
            "stdout": (
                "Ethernet adapter Ethernet:\n"
                "   Physical Address. . . . . . . . . : 00-11-22-33-44-55\n"
                "   IPv4 Address. . . . . . . . . . . : 192.0.2.10(Preferred)\n"
                "   Default Gateway . . . . . . . . . : 192.0.2.1\n"
                "   DNS Servers . . . . . . . . . . . : 192.0.2.53\n"
            ),
        }
        result = sat.local_network_inventory()
        self.assertEqual(result["interfaces"][0]["mac"], "00:11:22:33:44:55")
        self.assertEqual(result["interfaces"][0]["addresses"][0]["address"], "192.0.2.10")
        self.assertEqual(result["default_routes"][0]["gateway"], "192.0.2.1")
        self.assertEqual(result["dns_servers"], ["192.0.2.53"])


class DiagnosticTests(unittest.TestCase):
    def test_diagnostic_http_probe_separates_connect_host_host_header_and_sni(self):
        class FakeSocket:
            def __init__(self):
                self.request = b""

            def settimeout(self, _timeout):
                pass

            def sendall(self, value):
                self.request += value

            def cipher(self):
                return ("TLS_AES_256_GCM_SHA384", "TLSv1.3", 256)

            def version(self):
                return "TLSv1.3"

            def getpeercert(self):
                return {"subjectAltName": (("DNS", "app.example.com"),)}

            def close(self):
                pass

        class FakeContext:
            def __init__(self):
                self.server_hostname = None

            def wrap_socket(self, sock, server_hostname=None):
                self.server_hostname = server_hostname
                return sock

        class FakeResponse:
            status = 200
            reason = "OK"

            def __init__(self, _sock):
                pass

            def begin(self):
                pass

            def getheaders(self):
                return [("Server", "nginx")]

        sock = FakeSocket()
        context = FakeContext()
        with patch.object(sat.socket, "create_connection", return_value=sock) as connect, \
                patch.object(sat.ssl, "create_default_context", return_value=context), \
                patch.object(sat.http.client, "HTTPResponse", FakeResponse):
            result = sat._http_status_probe(
                "https://127.0.0.1:8443/health", "app.example.com", 1,
            )
        connect.assert_called_once_with(("127.0.0.1", 8443), timeout=1)
        self.assertEqual(context.server_hostname, "app.example.com")
        self.assertIn(b"Host: app.example.com\r\n", sock.request)
        self.assertEqual(result["tls"]["server_name"], "app.example.com")
        self.assertEqual(result["proxy_policy"], "direct")

    def test_diagnostic_http_redirects_are_opt_in(self):
        seen = []

        class Handler(BaseHTTPRequestHandler):
            def do_HEAD(self):
                seen.append((self.path, self.headers.get("Host")))
                if self.path == "/start":
                    self.send_response(302)
                    self.send_header("Location", "/final")
                else:
                    self.send_response(204)
                self.end_headers()

            def log_message(self, _format, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/start"
        try:
            stopped = sat._http_status_probe(url, "app.example.com", 1)
            followed = sat._http_status_probe(url, "app.example.com", 1, follow_redirects=True)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)
        self.assertEqual(stopped["status_code"], 302)
        self.assertFalse(stopped["redirected"])
        self.assertEqual(followed["status_code"], 204)
        self.assertTrue(followed["redirected"])
        self.assertEqual(len(followed["redirect_chain"]), 2)
        self.assertEqual(seen[0], ("/start", "app.example.com"))
        self.assertEqual(seen[-1][0], "/final")

    def test_diagnostic_http_rejects_invalid_redirect_target_and_authority_port(self):
        class Handler(BaseHTTPRequestHandler):
            def do_HEAD(self):
                self.send_response(302)
                self.send_header("Location", "file:///etc/passwd")
                self.end_headers()

            def log_message(self, _format, *args):
                pass

        server = HTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            result = sat._http_status_probe(
                f"http://127.0.0.1:{server.server_port}/", None, 1,
                follow_redirects=True,
            )
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=1)
        self.assertEqual(result["status"], "failed")
        self.assertIn("credential-free HTTP/HTTPS", result["error"])
        with self.assertRaises(ValueError):
            sat._host_from_authority("example.com:70000")

    def test_log_redaction_covers_headers_queries_and_jwts(self):
        line = (
            'GET /?token=secret&name=test HTTP/1.1 Authorization: Bearer abc '
            'Cookie: session=secret eyJabcdefghijk.abcdefghijk.abcdefghijk '
            '--password cli-secret'
        )
        redacted = sat._redact_log_line(line)
        self.assertNotIn("secret", redacted)
        self.assertNotIn("Bearer abc", redacted)
        self.assertNotIn("cli-secret", redacted)
        self.assertNotIn("eyJabcdefghijk", redacted)
        self.assertIn("[REDACTED]", redacted)

    def test_log_tail_is_opt_in_bounded_and_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "access.log"
            path.write_text(
                'first\nGET /?api_key=topsecret HTTP/1.1\nlast\n', encoding="utf-8"
            )
            metadata = sat._tail_log_file(str(path), lines=2)
            content = sat._tail_log_file(str(path), lines=2, include_content=True)
        self.assertNotIn("lines", metadata)
        self.assertEqual(len(content["lines"]), 2)
        self.assertNotIn("topsecret", "\n".join(content["lines"]))
        with self.assertRaises(ValueError):
            sat._validate_log_options(501, "1 hour ago")

    @patch.object(sat, "_mount_details", return_value={"mountpoint": "/", "read_only": False})
    @patch.object(sat.os, "statvfs", create=True)
    @patch.object(sat.shutil, "disk_usage")
    def test_disk_diagnostic_detects_capacity_and_inode_pressure(self, disk_usage, statvfs, _mount):
        disk_usage.return_value = SimpleNamespace(total=1000, used=960, free=40)
        statvfs.return_value = SimpleNamespace(f_files=100, f_ffree=2)
        with tempfile.TemporaryDirectory() as directory:
            result = sat.disk_diagnostic(directory)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(
            {item["code"] for item in result["findings"]},
            {"disk_critical", "inode_critical"},
        )

    @patch.object(sat, "_process_matches", return_value=[{"pid": 12, "command": "nginx"}])
    @patch.object(sat, "_diagnostic_command")
    @patch.object(sat, "_service_manager", return_value="systemd")
    def test_service_diagnostic_reads_selected_properties_and_redacts_journal(self, _manager, command, _processes):
        def response(argv, **_kwargs):
            if argv[0] == "systemctl":
                return {
                    "available": True, "ok": True, "returncode": 0,
                    "stdout": "LoadState=loaded\nActiveState=active\nSubState=running\nExecMainStatus=0\n",
                    "stderr": "", "error": None, "elapsed_ms": 1,
                }
            return {
                "available": True, "ok": True, "returncode": 0,
                "stdout": "service token=secret\n", "stderr": "", "error": None,
                "elapsed_ms": 1,
            }
        command.side_effect = response
        result = sat.service_diagnostic("nginx", include_logs=True)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["details"]["ActiveState"], "active")
        self.assertNotIn("secret", result["journal"][0])
        self.assertTrue(result["logs_redacted"])

    @patch.object(sat, "_process_matches", return_value=[{"pid": 12, "command": "nginx: worker process"}])
    @patch.object(sat, "_diagnostic_command")
    @patch.object(sat, "_service_manager", return_value="openrc")
    def test_service_diagnostic_reconciles_unmanaged_running_process(self, _manager, command, _processes):
        command.return_value = {
            "available": True, "ok": False, "returncode": 1, "stdout": "", "stderr": "not found",
            "error": "not found", "elapsed_ms": 1,
        }
        with patch.object(sat.platform, "system", return_value="Linux"):
            result = sat.service_diagnostic("nginx")
        codes = {item["code"] for item in result["findings"]}
        self.assertEqual(result["status"], "warning")
        self.assertIn("service_manager_process_mismatch", codes)
        self.assertNotIn("service_inactive", codes)

    @patch.object(sat, "_process_matches", return_value=[])
    @patch.object(sat, "_diagnostic_command")
    @patch.object(sat, "_service_manager", return_value="systemd")
    def test_service_diagnostic_accepts_manager_pid_without_exact_name_match(self, _manager, command, _processes):
        command.return_value = {
            "available": True, "ok": True, "returncode": 0,
            "stdout": "LoadState=loaded\nActiveState=active\nSubState=running\nMainPID=321\nExecMainStatus=0\n",
            "stderr": "", "error": None, "elapsed_ms": 1,
        }
        result = sat.service_diagnostic("example-wrapper")
        process_step = next(
            step for step in result["methodology"]["steps"] if step["id"] == "process"
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(process_step["status"], "passed")
        self.assertIn("321", process_step["summary"])

    @patch.object(sat, "firewall_diagnostic")
    @patch.object(sat, "_process_matches", return_value=[])
    @patch.object(sat, "_diagnostic_command")
    @patch.object(sat, "_service_manager", return_value="systemd")
    def test_service_diagnostic_correlates_explicit_port(self, _manager, command, _processes, firewall):
        command.return_value = {
            "available": True, "ok": True, "returncode": 0,
            "stdout": "LoadState=loaded\nActiveState=active\nSubState=running\nMainPID=321\nExecMainStatus=0\n",
            "stderr": "", "error": None, "elapsed_ms": 1,
        }
        firewall.return_value = {
            "status": "warning",
            "findings": [{
                "code": "firewall_port_not_explicitly_allowed", "severity": "warning",
                "summary": "No direct allow was observed.", "phase": "firewall",
            }],
        }
        result = sat.service_diagnostic("postgresql", port=5432)
        firewall.assert_called_once_with([5432], timeout=10.0)
        self.assertEqual(result["status"], "warning")
        self.assertIsNotNone(result["firewall"])
        step = next(item for item in result["methodology"]["steps"] if item["id"] == "firewall")
        self.assertEqual(step["status"], "warning")

    @patch.object(sat, "tcp_probe", return_value={"status": "failed", "error": "refused"})
    @patch.object(sat, "resolve_all", return_value={"status": "ok", "addresses": [{"address": "192.0.2.1"}]})
    @patch.object(sat, "_listening_sockets", return_value={"available": True, "listeners": []})
    @patch.object(sat, "local_network_inventory")
    def test_network_diagnostic_correlates_local_state_and_probe(self, inventory, _listeners, _resolve, _tcp):
        inventory.return_value = {
            "interfaces": [], "default_routes": [], "dns_servers": [], "errors": [],
        }
        result = sat.network_diagnostic("example.com", port=443)
        codes = {item["code"] for item in result["findings"]}
        self.assertEqual(result["status"], "failed")
        self.assertIn("default_route_missing", codes)
        self.assertIn("dns_servers_missing", codes)
        self.assertIn("probe_tcp_failed", codes)

    @patch.object(sat, "tcp_probe")
    @patch.object(sat, "_route_to_address")
    @patch.object(sat, "resolve_all", return_value={"status": "failed", "addresses": [], "error": "not found"})
    @patch.object(sat, "_listening_sockets", return_value={"available": True, "listeners": []})
    @patch.object(sat, "local_network_inventory")
    def test_network_diagnostic_stops_after_dns_failure(
        self, inventory, _listeners, _resolve, route, tcp,
    ):
        inventory.return_value = {
            "interfaces": [{
                "name": "eth0", "state": "UP",
                "addresses": [{"family": "inet", "address": "192.0.2.10", "scope": "global"}],
            }],
            "default_routes": [{"destination": "default", "gateway": "192.0.2.1"}],
            "dns_servers": ["192.0.2.53"], "errors": [],
        }
        result = sat.network_diagnostic("missing.example", port=443)
        self.assertEqual(result["checks"]["tcp"]["status"], "skipped")
        route.assert_not_called()
        tcp.assert_not_called()
        self.assertEqual(
            [step["id"] for step in result["methodology"]["steps"]],
            [
                "context", "link", "addressing", "local_routing", "dns",
                "target_route", "transport", "application",
            ],
        )

    @patch.object(sat, "_diagnostic_command")
    @patch.object(sat.shutil, "which")
    @patch.object(sat.platform, "system", return_value="Linux")
    def test_firewall_diagnostic_correlates_nftables_ports(self, _system, which, command):
        which.side_effect = lambda name: "/usr/sbin/nft" if name == "nft" else None
        command.return_value = {
            "available": True, "ok": True, "returncode": 0,
            "stdout": (
                "table inet filter {\n"
                "  chain input {\n"
                "    type filter hook input priority filter; policy drop;\n"
                "    tcp dport 80 accept\n"
                "    tcp dport 443 drop\n"
                "  }\n"
                "}\n"
            ),
            "stderr": "", "error": None, "elapsed_ms": 1,
        }
        result = sat.firewall_diagnostic([80, 443, 8080])
        verdicts = {item["port"]: item["verdict"] for item in result["port_assessments"]}
        self.assertEqual(result["active_backends"], ["nftables"])
        self.assertEqual(verdicts[80], "allow_rule_observed")
        self.assertEqual(verdicts[443], "potentially_blocked")
        self.assertEqual(verdicts[8080], "no_allow_observed_with_default_deny")
        self.assertEqual(result["status"], "warning")

    @patch.object(sat, "_diagnostic_command")
    @patch.object(sat.shutil, "which")
    def test_ufw_inspection_parses_numeric_inbound_rules(self, which, command):
        which.return_value = "/usr/sbin/ufw"
        command.return_value = {
            "available": True, "ok": True, "returncode": 0,
            "stdout": (
                "Status: active\n"
                "Default: deny (incoming), allow (outgoing), disabled (routed)\n\n"
                "To                         Action      From\n"
                "--                         ------      ----\n"
                "80/tcp                     ALLOW IN    Anywhere\n"
                "443/tcp                    DENY IN     Anywhere\n"
                "53/udp                     ALLOW IN    Anywhere\n"
            ),
            "stderr": "", "error": None, "elapsed_ms": 1,
        }
        result = sat._inspect_ufw([80, 443, 8080], 1)
        self.assertIsNotNone(result)
        assessments = {item["port"]: item["verdict"] for item in result["port_assessments"]}
        self.assertEqual(assessments[80], "explicit_allow_observed")
        self.assertEqual(assessments[443], "explicit_deny_observed")
        self.assertEqual(assessments[8080], "default_deny_without_direct_match")
        self.assertEqual(
            sat._inspect_ufw([53], 1)["port_assessments"][0]["verdict"],
            "default_deny_without_direct_match",
        )

    @patch.object(sat, "_diagnostic_command")
    @patch.object(sat.shutil, "which", return_value="/usr/sbin/ufw")
    def test_ufw_inspection_resolves_application_profiles(self, _which, command):
        def response(argv, **_kwargs):
            stdout = (
                "Status: active\nDefault: deny (incoming), allow (outgoing), disabled (routed)\n"
                "Nginx Full                  ALLOW IN    Anywhere\n"
            ) if argv[1:3] == ["status", "verbose"] else (
                "Profile: Nginx Full\nPorts:\n  80,443/tcp\n"
            )
            return {
                "available": True, "ok": True, "returncode": 0,
                "stdout": stdout, "stderr": "", "error": None, "elapsed_ms": 1,
            }
        command.side_effect = response
        result = sat._inspect_ufw([80, 443, 8080], 1)
        self.assertIsNotNone(result)
        assessments = {item["port"]: item["verdict"] for item in result["port_assessments"]}
        self.assertEqual(assessments[80], "explicit_allow_observed")
        self.assertEqual(assessments[443], "explicit_allow_observed")
        self.assertEqual(assessments[8080], "default_deny_without_direct_match")

    @patch.object(sat, "_diagnostic_command")
    @patch.object(sat.shutil, "which", return_value="/usr/bin/firewall-cmd")
    def test_firewalld_resolves_services_ports_and_rich_rules(self, _which, command):
        def response(argv, **_kwargs):
            if "--state" in argv:
                stdout = "running\n"
            elif "--get-active-zones" in argv:
                stdout = "public\n  interfaces: eth0\n"
            elif "--list-all" in argv:
                stdout = (
                    "public (active)\n  target: default\n  interfaces: eth0\n"
                    "  services: customweb\n  ports: 8443/tcp\n  rich rules:\n"
                    "    rule family=\"ipv4\" port port=\"9443\" protocol=\"tcp\" reject\n"
                )
            else:
                stdout = "customweb\n  ports: 8080/tcp\n"
            return {
                "available": True, "ok": True, "returncode": 0,
                "stdout": stdout, "stderr": "", "error": None, "elapsed_ms": 1,
            }
        command.side_effect = response
        result = sat._inspect_firewalld([8080, 8443, 9443, 9999], 1)
        self.assertIsNotNone(result)
        assessments = {item["port"]: item["verdict"] for item in result["port_assessments"]}
        self.assertEqual(assessments[8080], "explicit_allow_observed")
        self.assertEqual(assessments[8443], "explicit_allow_observed")
        self.assertEqual(assessments[9443], "explicit_deny_observed")
        self.assertEqual(assessments[9999], "indeterminate")

    @patch.object(sat, "_diagnostic_command")
    @patch.object(sat.shutil, "which")
    @patch.object(sat.platform, "system", return_value="Linux")
    def test_firewall_permission_limits_are_warnings_only_for_port_correlation(
        self, _system, which, command,
    ):
        which.side_effect = lambda name: "/usr/sbin/nft" if name == "nft" else None
        command.return_value = {
            "available": True, "ok": False, "returncode": 1,
            "stdout": "", "stderr": "Operation not permitted", "error": "exit status 1",
            "elapsed_ms": 1,
        }
        correlated = sat.firewall_diagnostic([443])
        discovery = sat.firewall_diagnostic([])
        self.assertEqual(correlated["status"], "warning")
        self.assertEqual(discovery["status"], "ok")
        self.assertEqual(correlated["port_assessments"][0]["verdict"], "indeterminate")

    def test_pf_rule_actions_are_understood(self):
        allow = sat._rule_assessment(
            "pf", 80, ["pass in proto tcp from any to any port = 80"],
        )
        deny = sat._rule_assessment(
            "pf", 443, ["block in proto tcp from any to any port = 443"],
        )
        self.assertEqual(allow["verdict"], "explicit_allow_observed")
        self.assertEqual(deny["verdict"], "explicit_deny_observed")

        blanket = sat._rule_assessment(
            "iptables", 8443, ["-A INPUT -j DROP"], "accept",
        )
        established = sat._rule_assessment(
            "iptables", 8443,
            ["-A INPUT -m conntrack --ctstate RELATED,ESTABLISHED -j ACCEPT"],
            "drop",
        )
        self.assertEqual(blanket["verdict"], "explicit_deny_observed")
        self.assertEqual(established["verdict"], "default_deny_without_direct_match")
        misleading_comment = sat._rule_assessment(
            "nftables", 443,
            ['tcp dport 443 comment "deny is only a label" accept'],
        )
        self.assertEqual(misleading_comment["verdict"], "explicit_allow_observed")

    @patch.object(sat, "_diagnostic_command")
    @patch.object(sat.shutil, "which", return_value="C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
    def test_windows_firewall_inspection_correlates_rules(self, _which, command):
        command.return_value = {
            "available": True, "ok": True, "returncode": 0,
            "stdout": json.dumps({
                "Profiles": [{"Name": "Public", "Enabled": True, "DefaultInboundAction": "Block"}],
                "Rules": [
                    {"Name": "Web", "Action": "Allow", "LocalPort": "443", "Profile": "Public"},
                    {"Name": "Legacy", "Action": "Block", "LocalPort": "8080-8089", "Profile": "Public"},
                ],
            }),
            "stderr": "", "error": None, "elapsed_ms": 1,
        }
        result = sat._inspect_windows_firewall([443, 8085, 9999], 1)
        self.assertIsNotNone(result)
        assessments = {item["port"]: item["verdict"] for item in result["port_assessments"]}
        self.assertEqual(assessments[443], "explicit_allow_observed")
        self.assertEqual(assessments[8085], "explicit_deny_observed")
        self.assertEqual(assessments[9999], "default_deny_without_direct_match")

    def test_nginx_configuration_parser_extracts_only_diagnostic_metadata(self):
        configuration = """# configuration file /etc/nginx/nginx.conf:
user www-data www-data;
error_log /var/log/nginx/error.log warn;
http {
  access_log /var/log/nginx/access.log main;
  server {
    listen 443 ssl;
    server_name example.com www.example.com;
    root /srv/www/example;
    ssl_certificate /etc/ssl/example.pem;
    ssl_certificate_key /etc/ssl/example.key;
    proxy_pass http://app_backend;
    location /media/ {
      alias
        /srv/media/;
    }
  }
}
"""
        result = sat._parse_nginx_configuration(
            configuration, {"configure_arguments": {"prefix": "/etc/nginx"}}
        )
        self.assertEqual(result["worker_user"], "www-data")
        self.assertEqual(result["listen_ports"], [443])
        self.assertEqual(result["paths"]["roots"], ["/srv/www/example"])
        self.assertIn("/etc/ssl/example.key", result["paths"]["certificates"])
        self.assertEqual(result["paths"]["aliases"], ["/srv/media"])
        self.assertEqual(result["server_names"], ["example.com www.example.com"])
        self.assertNotIn("ssl_certificate_key", result)

    def test_nginx_listener_parser_covers_default_port_and_unix_socket(self):
        configuration = """# configuration file /etc/nginx/nginx.conf:
server {
  listen 127.0.0.1;
  listen unix:/run/nginx/app.sock;
  server_name app.example.com;
}
"""
        result = sat._parse_nginx_configuration(
            configuration, {"configure_arguments": {"prefix": "/etc/nginx"}},
        )
        self.assertEqual(result["listen_ports"], [80])
        self.assertEqual(result["unix_sockets"], ["/run/nginx/app.sock"])
        self.assertFalse(result["implicit_listen"])
        self.assertEqual([item["family"] for item in result["listeners"]], ["ip", "unix"])

        implicit = sat._parse_nginx_configuration(
            "server { server_name default.example; }", {"configure_arguments": {}},
        )
        self.assertTrue(implicit["implicit_listen"])
        self.assertEqual(implicit["implicit_port_candidates"], [80, 8000])

    def test_nginx_endpoint_and_url_redaction_remove_credentials(self):
        self.assertEqual(
            sat._redact_nginx_endpoint("http://admin:secret@backend/?token=value"),
            "http://[REDACTED]@backend/?token=[REDACTED]",
        )
        self.assertEqual(
            sat._redact_url("https://admin:secret@example.com/path?api_key=value"),
            "https://[REDACTED]@example.com/path?api_key=[REDACTED]",
        )

    @patch.object(sat, "_process_matches", return_value=[])
    @patch.object(sat, "_diagnostic_command")
    @patch.object(sat, "_service_manager", return_value="systemd")
    def test_service_diagnostic_reports_service_manager_query_failure(self, _manager, command, _processes):
        command.return_value = {
            "available": True, "ok": False, "returncode": 1, "stdout": "", "stderr": "offline",
            "error": "offline", "elapsed_ms": 1,
        }
        result = sat.service_diagnostic("nginx")
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["findings"][0]["code"], "service_query_failed")

    @patch.object(sat, "_diagnostic_command")
    @patch.object(sat.shutil, "which")
    def test_time_sync_uses_chrony_when_systemd_tool_is_absent(self, which, command):
        which.side_effect = lambda name: "/usr/bin/chronyc" if name == "chronyc" else None
        command.return_value = {
            "available": True, "ok": True, "returncode": 0,
            "stdout": "Reference ID : 192.0.2.1\nLeap status : Normal\n",
            "stderr": "", "error": None, "elapsed_ms": 1,
        }
        result = sat._time_sync_status(1)
        self.assertEqual(result["source"], "chronyc")
        self.assertTrue(result["synchronized"])

    def test_nginx_log_analysis_distinguishes_causes_and_statuses(self):
        findings = sat._nginx_log_findings(
            ["connect() failed (111: Connection refused)", "open() failed (13: Permission denied)"],
            ['"GET /missing HTTP/1.1" 404 1', '"GET /private HTTP/1.1" 403 1'],
        )
        codes = {item["code"] for item in findings}
        self.assertTrue({"nginx_upstream_connect", "nginx_permission_denied", "nginx_access_403", "nginx_access_404"} <= codes)

    @patch.object(sat, "firewall_diagnostic", return_value={"status": "ok", "findings": [], "port_assessments": []})
    @patch.object(sat, "disk_diagnostic", return_value={"status": "ok", "findings": []})
    @patch.object(sat, "_security_frameworks", return_value={"selinux": "Disabled", "apparmor": None, "path_contexts": []})
    @patch.object(sat, "_path_access_for_user", return_value={"traversable": True})
    @patch.object(sat, "_tail_log_file")
    @patch.object(sat, "_listening_sockets")
    @patch.object(sat, "service_diagnostic")
    @patch.object(sat, "_diagnostic_command")
    def test_nginx_diagnostic_correlates_syntax_service_config_and_logs(
        self, command, service, sockets, tail, _path_access, _security, _disk, _firewall,
    ):
        configuration = """# configuration file /etc/nginx/nginx.conf:
user www-data;
error_log /var/log/nginx/error.log;
access_log /var/log/nginx/access.log main;
listen 8080;
root /srv/www;
"""
        def response(argv, **_kwargs):
            if "-V" in argv:
                stdout, stderr = "", "nginx version: nginx/1.26.2\nconfigure arguments: --prefix=/etc/nginx"
            elif "-T" in argv:
                stdout, stderr = configuration, "configuration test is successful"
            else:
                stdout, stderr = "", "configuration test is successful"
            return {
                "available": True, "ok": True, "returncode": 0, "stdout": stdout,
                "stderr": stderr, "error": None, "elapsed_ms": 1,
            }
        command.side_effect = response
        service.return_value = {"status": "ok", "findings": [], "journal": []}
        sockets.return_value = {
            "available": True, "listeners": [{"port": 8080, "protocol": "tcp", "local_address": "*:8080"}],
        }
        tail.side_effect = lambda path, **kwargs: {
            "path": path, "exists": True,
            "lines": ['"GET / HTTP/1.1" 200 12'] if kwargs.get("include_content") else [],
        }
        with tempfile.NamedTemporaryFile() as executable:
            result = sat.nginx_diagnostic(binary=executable.name, log_mode="access")
        self.assertEqual(result["status"], "warning")
        self.assertIn("nginx_document_root_missing", {item["code"] for item in result["findings"]})
        self.assertTrue(result["syntax"]["ok"])
        self.assertEqual(result["configuration"]["listen_ports"], [8080])
        self.assertEqual(result["build"]["version"], "1.26.2")
        self.assertTrue(result["logs_redacted"])
        self.assertEqual(
            [step["id"] for step in result["methodology"]["steps"]],
            [
                "context", "host_prerequisites", "runtime", "service_logs",
                "configuration", "application_logs", "listeners", "firewall",
                "application", "path_access",
            ],
        )

    @patch.object(sat, "firewall_diagnostic", return_value={"status": "ok", "findings": [], "active_backends": [], "backends": []})
    @patch.object(sat, "network_diagnostic", return_value={"status": "ok", "findings": []})
    @patch.object(sat, "disk_diagnostic", return_value={"status": "ok", "findings": []})
    @patch.object(sat, "_linux_pressure", return_value={})
    @patch.object(sat, "_proc_memory", return_value={"available_percent": 4.0, "swap_used_percent": 0})
    @patch.object(sat, "_service_manager", return_value="unknown")
    @patch.object(sat.os, "getloadavg", return_value=(0.1, 0.1, 0.1), create=True)
    def test_system_diagnostic_reports_resource_pressure(self, _load, _manager, _memory, _pressure, _disk, _network, _firewall):
        result = sat.system_diagnostic(path="/", timeout=1)
        self.assertEqual(result["status"], "failed")
        self.assertIn("memory_critical", {item["code"] for item in result["findings"]})
        self.assertFalse(result["logs_included"])


class OutputAndCliTests(unittest.TestCase):
    CLI = [sys.executable, str(SRC / "SysAdminToolbox" / "SysAdminToolbox.py")]

    def run_cli(self, *args):
        return subprocess.run(
            self.CLI + list(args), cwd=ROOT, text=True, capture_output=True,
            timeout=10,
        )

    def assert_json_command(self, *args):
        process = self.run_cli(*args)
        self.assertEqual(process.returncode, 0, process.stderr)
        try:
            return json.loads(process.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"Invalid JSON for {' '.join(args)}: {exc}\n{process.stdout}")

    def test_version_and_help(self):
        self.assertIn(sat.__version__, self.run_cli("--version").stdout)
        self.assertIn("Network administration", self.run_cli("--help").stdout)
        for command in ("convert", "subnet", "ipv6", "mac", "net", "doctor", "vendor", "cheat"):
            with self.subTest(command=command):
                self.assertEqual(self.run_cli(command, "--help").returncode, 0)

    def test_source_file_runs_without_the_package(self):
        with tempfile.TemporaryDirectory() as directory:
            standalone = Path(directory) / "SysAdminToolbox.py"
            shutil.copy2(self.CLI[1], standalone)
            process = subprocess.run(
                [sys.executable, str(standalone), "--version"],
                cwd=directory,
                text=True,
                capture_output=True,
                timeout=10,
            )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertIn(sat.__version__, process.stdout)

    def test_json_flag_before_and_after_subcommand(self):
        before = self.assert_json_command("--json", "subnet", "calc", "10.0.0.0/8")
        after = self.assert_json_command("subnet", "calc", "10.0.0.0/8", "--json")
        self.assertEqual(before, after)

    def test_every_deterministic_command_family_emits_json(self):
        commands = (
            ("convert", "d2b", "42", "--json"),
            ("convert", "b2d", "11111111", "--json"),
            ("convert", "d2h", "255", "--json"),
            ("convert", "h2d", "ff", "--json"),
            ("convert", "b2h", "11111111", "--json"),
            ("convert", "h2b", "ff", "--json"),
            ("convert", "iptobin", "192.168.1.1", "--json"),
            ("convert", "bintoip", "11000000101010000000000100000001", "--json"),
            ("convert", "masktobin", "255.255.255.0", "--json"),
            ("convert", "bintomask", "11111111111111111111111100000000", "--json"),
            ("convert", "m2c", "255.255.255.0", "--json"),
            ("convert", "c2m", "24", "--json"),
            ("convert", "m2w", "255.255.255.0", "--json"),
            ("convert", "w2m", "0.0.0.255", "--json"),
            ("convert", "c2w", "24", "--json"),
            ("convert", "w2c", "0.0.0.255", "--json"),
            ("convert", "a2b", "192.168.1.1", "--json"),
            ("convert", "b2a", "11000000101010000000000100000001", "--json"),
            ("convert", "ipinfo", "192.168.1.42/24", "--json"),
            ("convert", "ipclass", "100.64.0.1", "--json"),
            ("subnet", "calc", "192.168.1.0/24", "--json"),
            ("subnet", "adv", "192.168.1.0/24", "26", "--json"),
            ("subnet", "vlsm", "192.168.1.0/24", "50", "30", "10", "--json"),
            ("subnet", "overlap", "10.0.0.0/24", "10.0.0.128/25", "--json"),
            ("subnet", "supernet", "10.0.0.0/25", "10.0.0.128/25", "--json"),
            ("subnet", "range", "192.168.1.10", "192.168.1.35", "--json"),
            ("subnet", "contains", "10.0.0.0/8", "10.1.2.3", "--json"),
            ("subnet", "exclude", "192.0.2.0/29", "192.0.2.0/30", "--json"),
            ("subnet", "nth", "2001:db8::/32", "4294967296", "--json"),
            ("ipv6", "expand", "::1", "--json"),
            ("ipv6", "compress", "2001:0db8::1", "--json"),
            ("ipv6", "tobin", "::1", "--json"),
            ("ipv6", "type", "fe80::1", "--json"),
            ("ipv6", "subnet", "2001:db8::/126", "--json"),
            ("ipv6", "ula", "--json"),
            ("mac", "info", "aa:bb:cc:dd:ee:ff", "--json"),
            ("mac", "format", "aa:bb:cc:dd:ee:ff", "cisco", "--json"),
            ("mac", "normalize", "aabb.ccdd.eeff", "--json"),
            ("mac", "vendor", "aa:bb:cc:dd:ee:ff", "--json"),
            ("mac", "generate", "2", "colon", "--json"),
            ("vendor", "vlan", "cisco", "10", "Guest", "Gi0/1", "--json"),
            ("vendor", "acl", "juniper", "BLOCK", "deny", "tcp", "10.0.0.0/8", "0.0.0.0/0", "0", "443", "--json"),
            ("vendor", "profiles", "--json"),
            ("cheat", "vlan", "creation", "--json"),
            ("cheat", "vlan", "--legacy", "--json"),
            ("cheat", "acl", "creation", "--json"),
            ("cheat", "huawei", "creation", "--json"),
            ("cheat", "mikrotik", "creation", "--json"),
            ("cheat", "firewall", "nftables", "--json"),
            ("cheat", "routing", "ospf", "--json"),
            ("cheat", "nat", "cisco_pat", "--json"),
            ("net", "headers", "file:///etc/passwd", "--json"),
            ("net", "random-ports", "50000", "50010", "3", "--json"),
        )
        for command in commands:
            with self.subTest(command=" ".join(command)):
                self.assert_json_command(*command)

    def test_cli_reports_errors_without_traceback(self):
        process = self.run_cli("subnet", "calc", "999.1.1.1/24")
        self.assertEqual(process.returncode, 1)
        self.assertIn("Error:", process.stderr)
        self.assertNotIn("Traceback", process.stderr)

    def test_command_aliases(self):
        commands = (
            ("c", "d2b", "42", "--json"),
            ("s", "calc", "192.0.2.0/24", "--json"),
            ("v6", "type", "::1", "--json"),
            ("m", "normalize", "aabb.ccdd.eeff", "--json"),
            ("v", "vlan", "cisco", "10", "Guest", "--json"),
            ("cs", "nat", "cisco_pat", "--json"),
        )
        for command in commands:
            with self.subTest(command=" ".join(command)):
                self.assert_json_command(*command)

    def test_doctor_disk_cli_and_alias_emit_json(self):
        with tempfile.TemporaryDirectory() as directory:
            direct = self.run_cli("doctor", "disk", directory, "--json")
            alias = self.run_cli("diag", "disk", directory, "--json")
        self.assertIn(direct.returncode, {0, 1}, direct.stderr)
        self.assertIn(alias.returncode, {0, 1}, alias.stderr)
        self.assertEqual(json.loads(direct.stdout)["path"], directory)
        self.assertEqual(json.loads(alias.stdout)["path"], directory)

    def test_doctor_rejects_cross_scope_options(self):
        cases = (
            ("doctor", "system", "--logs", "service"),
            ("doctor", "service", "nginx", "--logs", "system"),
            ("doctor", "network", "localhost", "--url", "http://127.0.0.1"),
            ("doctor", "nginx", "--sni", "app.example.com"),
            ("doctor", "nginx", "--url", "http://127.0.0.1", "--insecure"),
        )
        for arguments in cases:
            with self.subTest(arguments=arguments):
                process = self.run_cli(*arguments)
                self.assertEqual(process.returncode, 1)
                self.assertIn("Error:", process.stderr)

    def test_doctor_records_operator_context(self):
        with tempfile.TemporaryDirectory() as directory:
            process = self.run_cli(
                "doctor", "disk", directory, "--symptom", "writes fail",
                "--expected", "writes succeed", "--recent-change", "new mount", "--json",
            )
        self.assertIn(process.returncode, {0, 1}, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result["context"]["symptom"], "writes fail")
        self.assertEqual(result["context"]["expected"], "writes succeed")
        self.assertEqual(result["methodology"]["steps"][0]["status"], "passed")

    def test_doctor_firewall_cli_and_port_validation(self):
        process = self.run_cli(
            "doctor", "firewall", "80,443", "--timeout", "2", "--json",
        )
        self.assertIn(process.returncode, {0, 1}, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result["ports"], [80, 443])
        self.assertTrue(result["read_only"])
        invalid = self.run_cli("doctor", "firewall", "80,bad")
        self.assertEqual(invalid.returncode, 1)
        self.assertIn("Invalid firewall port", invalid.stderr)

    def test_legacy_cheatsheet_flag(self):
        current = self.run_cli("cs", "vlan")
        legacy = self.run_cli("cs", "vlan", "legacy_trunking", "--legacy")
        unsupported = self.run_cli("cs", "firewall", "--legacy")

        self.assertEqual(current.returncode, 0, current.stderr)
        self.assertNotIn("ISL", current.stdout)
        self.assertEqual(legacy.returncode, 0, legacy.stderr)
        self.assertIn("maintenance and migration only", legacy.stdout)
        self.assertEqual(unsupported.returncode, 1)
        self.assertIn("currently available only", unsupported.stderr)

    def test_repl_handles_bad_quotes_and_resets_json_mode(self):
        stream = io.StringIO()
        commands = iter(('convert d2b "42', "c d2b 42 --json", "exit"))
        with patch("builtins.input", side_effect=lambda _prompt: next(commands)), \
                patch("sys.stdout", new=stream):
            sat._repl()
        self.assertIn("No closing quotation", stream.getvalue())
        self.assertIn('"binary": "101010"', stream.getvalue())
        self.assertFalse(sat.is_json_mode())

    def test_json_output_and_colors(self):
        stream = io.StringIO()
        sat.set_json_mode(True)
        try:
            sat.output("ok", label="status", file=stream)
        finally:
            sat.set_json_mode(False)
        self.assertEqual(json.loads(stream.getvalue()), {"status": "ok"})
        self.assertIn("\x1b[31m", sat.Colors(force=True).RED)
        self.assertEqual(sat.Colors(force=False).RED, "")

    def test_batch_output_formats(self):
        records = [
            {"target": "one", "status": "ok", "detail": {"port": 443}},
            {"target": "two", "status": "failed", "detail": None},
        ]
        ndjson = io.StringIO()
        sat.emit_records(records, "ndjson", file=ndjson)
        self.assertEqual(len(ndjson.getvalue().splitlines()), 2)
        self.assertEqual(json.loads(ndjson.getvalue().splitlines()[0])["target"], "one")

        csv_output = io.StringIO()
        sat.emit_records(records, "csv", file=csv_output)
        lines = csv_output.getvalue().splitlines()
        self.assertIn("detail", lines[0])
        self.assertEqual(len(lines), 3)

    def test_subnet_audit_cli_exit_status(self):
        with tempfile.TemporaryDirectory() as directory:
            clean = Path(directory) / "clean.json"
            broken = Path(directory) / "broken.json"
            clean.write_text(
                json.dumps({"parent": "192.0.2.0/24", "allocations": ["192.0.2.0/25"]}),
                encoding="utf-8",
            )
            broken.write_text(
                json.dumps({"parent": "192.0.2.0/24", "allocations": ["198.51.100.0/24"]}),
                encoding="utf-8",
            )
            clean_process = self.run_cli("subnet", "audit", str(clean), "--json")
            broken_process = self.run_cli("subnet", "audit", str(broken), "--json")
        self.assertEqual(clean_process.returncode, 0, clean_process.stderr)
        self.assertEqual(broken_process.returncode, 1, broken_process.stderr)
        self.assertEqual(json.loads(broken_process.stdout)["status"], "issues")

    def test_human_output_preserves_network_initialisms(self):
        stream = io.StringIO()
        sat.output(
            {"ipv4_mapped_ipv6": "::ffff:192.0.2.1", "num_addresses": 256},
            label="ipv4",
            file=stream,
        )
        self.assertEqual(
            stream.getvalue(),
            "IPv4:\n"
            "  IPv4-mapped IPv6: ::ffff:192.0.2.1\n"
            "  Number of Addresses: 256\n",
        )


class MetadataTests(unittest.TestCase):
    def test_version_and_license_are_consistent(self):
        pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
        source_text = (SRC / "SysAdminToolbox" / "SysAdminToolbox.py").read_text(encoding="utf-8")
        self.assertIn(f'version = "{sat.__version__}"', pyproject)
        self.assertIn(f'__version__ = "{sat.__version__}"', source_text)
        self.assertIn("MIT License", license_text)
        self.assertIn("MIT License", readme)
        combined = pyproject + readme + source_text
        self.assertNotIn("AGPL", combined)
        self.assertNotIn("GPLv3", combined)
        source_files = sorted(
            path.name for path in (SRC / "SysAdminToolbox").glob("*.py")
        )
        self.assertEqual(source_files, ["SysAdminToolbox.py"])

if __name__ == "__main__":
    unittest.main()
