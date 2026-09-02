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

from SysAdminToolbox import SysAdminToolbox as sat  # noqa: E402


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

    def test_vlan_helpers(self):
        cisco = sat.vlan_helper("cisco", 10, "Guest", ["Gi0/1", "Gi0/2"])
        self.assertIn("interface range Gi0/1,Gi0/2", cisco)
        juniper = sat.vlan_helper(
            "juniper", 10, "Guest", ["ge-0/0/1", "ge-0/0/2"]
        )
        self.assertEqual(juniper.count("set interfaces "), 2)
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
            def getpeercert(self):
                return certificate

        fake_context = SimpleNamespace(
            wrap_socket=lambda _sock, server_hostname: ContextManager(FakeTlsSocket())
        )
        with patch.object(sat.ssl, "create_default_context", return_value=fake_context), \
                patch.object(sat.socket, "create_connection", return_value=ContextManager(object())):
            result = sat.cert_check("example.com")
        self.assertEqual(result["subject"], "example.com")
        self.assertEqual(result["issuer"], "Example CA")
        self.assertFalse(result["expired"])

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
        for command in ("convert", "subnet", "ipv6", "mac", "net", "vendor", "cheat"):
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
            ("subnet", "calc", "192.168.1.0/24", "--json"),
            ("subnet", "adv", "192.168.1.0/24", "26", "--json"),
            ("subnet", "vlsm", "192.168.1.0/24", "50", "30", "10", "--json"),
            ("subnet", "overlap", "10.0.0.0/24", "10.0.0.128/25", "--json"),
            ("subnet", "supernet", "10.0.0.0/25", "10.0.0.128/25", "--json"),
            ("subnet", "range", "192.168.1.10", "192.168.1.35", "--json"),
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
