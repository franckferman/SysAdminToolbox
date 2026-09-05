#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Network administration calculations, diagnostics, and configuration helpers.

Author   : Franck FERMAN (@franckferman)
Created  : 2024-08-24
Version  : 4.4.0
License  : AGPL-3.0-or-later

Repository:
    https://github.com/franckferman/SysAdminToolbox
License details:
    See the LICENSE file.
"""

import argparse
import csv
import hashlib
import http.client
import http.server
import ipaddress
import itertools
import json
import os
import platform
import re
import secrets
import shlex
import shutil
import socket
import ssl
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any, Dict, List, Optional, cast

__version__ = "4.4.0"

MAX_SUBNET_DETAILS = 256
MAX_NETWORK_HOSTS = 4096
MAX_BATCH_TARGETS = 10000
DEFAULT_IEEE_OUI_URL = "https://standards-oui.ieee.org/oui/oui.csv"


# ---------------------------------------------------------------------------
#  Terminal and output helpers
# ---------------------------------------------------------------------------

_json_output = False


def set_json_mode(enabled: bool) -> None:
    global _json_output
    _json_output = enabled


def is_json_mode() -> bool:
    return _json_output


def _stdout_is_tty() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _no_color_requested() -> bool:
    return "--no-color" in sys.argv or os.environ.get("NO_COLOR") is not None


def colors_enabled() -> bool:
    return _stdout_is_tty() and not _no_color_requested()


class Colors:
    RED: str
    GREEN: str
    YELLOW: str
    BLUE: str
    MAGENTA: str
    CYAN: str
    BOLD: str
    DIM: str
    RESET: str

    _CODES = {
        "RED": "\033[31m",
        "GREEN": "\033[32m",
        "YELLOW": "\033[33m",
        "BLUE": "\033[34m",
        "MAGENTA": "\033[35m",
        "CYAN": "\033[36m",
        "BOLD": "\033[1m",
        "DIM": "\033[2m",
        "RESET": "\033[0m",
    }

    def __init__(self, force: Optional[bool] = None):
        enabled = colors_enabled() if force is None else force
        for name, code in self._CODES.items():
            setattr(self, name, code if enabled else "")


_DISPLAY_INITIALISMS = {
    "asn": "ASN",
    "cidr": "CIDR",
    "dns": "DNS",
    "http": "HTTP",
    "id": "ID",
    "ip": "IP",
    "ipv4": "IPv4",
    "ipv6": "IPv6",
    "mac": "MAC",
    "ms": "ms",
    "oui": "OUI",
    "rtt": "RTT",
    "tls": "TLS",
    "url": "URL",
}

_DISPLAY_NAMES = {
    "ipv4_mapped_ipv6": "IPv4-mapped IPv6",
    "num_addresses": "Number of Addresses",
}


def _display_name(name: Any) -> str:
    """Return a readable label while preserving common network initialisms."""
    normalized = str(name).replace("-", "_")
    if normalized.lower() in _DISPLAY_NAMES:
        return _DISPLAY_NAMES[normalized.lower()]
    words = normalized.split("_")
    return " ".join(
        _DISPLAY_INITIALISMS.get(word.lower(), word.capitalize())
        for word in words
    )


def _format_human(data: Any, indent: int = 0) -> str:
    prefix = "  " * indent
    lines = []

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{_display_name(key)}:")
                lines.append(_format_human(value, indent + 1))
            else:
                lines.append(f"{prefix}{_display_name(key)}: {value}")
    elif isinstance(data, (list, tuple)):
        for index, item in enumerate(data):
            if isinstance(item, (dict, list, tuple)):
                lines.append(f"{prefix}[{index}]")
                lines.append(_format_human(item, indent + 1))
            else:
                lines.append(f"{prefix}- {item}")
    else:
        lines.append(f"{prefix}{data}")

    return "\n".join(lines)


def output(data: Any, label: str = "result", file=None) -> None:
    destination = file or sys.stdout

    if _json_output:
        if not isinstance(data, (dict, list)):
            data = {label: data}
        print(json.dumps(data, indent=2, default=str), file=destination)
        return

    if isinstance(data, (dict, list)):
        print(f"{_display_name(label)}:", file=destination)
        print(_format_human(data, indent=1), file=destination)
    else:
        print(data, file=destination)


def _flatten_record(record: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten nested values into JSON strings for stable CSV output."""
    flattened: Dict[str, Any] = {}
    for key, value in record.items():
        if isinstance(value, (dict, list, tuple)):
            flattened[key] = json.dumps(value, sort_keys=True, default=str)
        elif value is None:
            flattened[key] = ""
        else:
            flattened[key] = value
    return flattened


def emit_records(
    records: List[Dict[str, Any]],
    output_format: str = "text",
    label: str = "results",
    file=None,
) -> None:
    """Emit batch records as text, JSON, NDJSON, or CSV."""
    destination = file or sys.stdout
    fmt = output_format.lower()
    if fmt not in {"text", "json", "ndjson", "csv"}:
        raise ValueError("Output format must be text, json, ndjson, or csv")
    if fmt == "json":
        print(json.dumps(records, indent=2, default=str), file=destination)
    elif fmt == "ndjson":
        for record in records:
            print(json.dumps(record, separators=(",", ":"), default=str), file=destination)
    elif fmt == "csv":
        flattened = [_flatten_record(record) for record in records]
        fieldnames = sorted({key for record in flattened for key in record})
        if not fieldnames:
            return
        writer = csv.DictWriter(destination, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(flattened)
    else:
        output(records, label=label, file=destination)


def _read_text_source(source: str) -> str:
    if source == "-":
        return sys.stdin.read()
    path = Path(source).expanduser()
    if not path.is_file():
        raise ValueError(f"Input file not found: {source}")
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(f"Cannot read input file '{source}': {exc}")


def read_targets(source: str) -> List[str]:
    """Read unique targets from a UTF-8 file or stdin, preserving order."""
    targets = []
    seen = set()
    for raw_line in _read_text_source(source).splitlines():
        value = raw_line.strip()
        if not value or value.startswith("#"):
            continue
        if value not in seen:
            seen.add(value)
            targets.append(value)
    if not targets:
        raise ValueError("Input contains no targets")
    if len(targets) > MAX_BATCH_TARGETS:
        raise ValueError(f"Input exceeds {MAX_BATCH_TARGETS} unique targets")
    return targets


def load_subnet_inventory(source: str) -> Dict[str, Any]:
    """Load an IPAM inventory from JSON, CSV, or one-CIDR-per-line text."""
    text = _read_text_source(source)
    suffix = Path(source).suffix.lower() if source != "-" else ""
    if suffix == ".json" or text.lstrip().startswith(("[", "{")):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON inventory: {exc}")
        if isinstance(data, list):
            return {"parent": None, "allocations": data}
        if isinstance(data, dict) and isinstance(data.get("allocations"), list):
            return {"parent": data.get("parent"), "allocations": data["allocations"]}
        raise ValueError("JSON inventory must be a list or contain an allocations list")
    if suffix == ".csv" or (text.splitlines() and "," in text.splitlines()[0]):
        reader = csv.DictReader(text.splitlines())
        if not reader.fieldnames or "network" not in reader.fieldnames:
            raise ValueError("CSV inventory requires a network column")
        return {"parent": None, "allocations": [dict(row) for row in reader]}
    entries = [line.strip() for line in text.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    return {"parent": None, "allocations": entries}


def colored_subnet_output(details: dict) -> str:
    colors = Colors()
    field_colors = {
        "network_address": colors.CYAN,
        "broadcast": colors.RED,
        "first_host": colors.GREEN,
        "last_host": colors.GREEN,
        "cidr": colors.YELLOW,
        "netmask": colors.YELLOW,
        "wildcard": colors.YELLOW,
        "is_private": colors.BOLD,
        "is_global": colors.BOLD,
    }
    lines = []
    for key, value in details.items():
        color = field_colors.get(key, "")
        reset = colors.RESET if color else ""
        label = key.replace("_", " ").title()
        lines.append(f"  {label}: {color}{value}{reset}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
#  Validation helpers
# ---------------------------------------------------------------------------

def _validate_ip(ip: str) -> str:
    octets = ip.split('.')
    if len(octets) != 4:
        raise ValueError(f"Invalid IPv4 address: '{ip}' (expected 4 octets)")
    for i, o in enumerate(octets):
        if not o.isdigit() or not 0 <= int(o) <= 255:
            raise ValueError(f"Invalid IPv4 address: '{ip}' (octet {i+1} = '{o}')")
    return ip


def _validate_mask(mask: str) -> str:
    _validate_ip(mask)
    bits = ''.join(format(int(o), '08b') for o in mask.split('.'))
    if '01' in bits:
        raise ValueError(f"Invalid subnet mask: '{mask}' (non-contiguous bits)")
    return mask


def _validate_cidr(cidr: int) -> int:
    if not 0 <= cidr <= 32:
        raise ValueError(f"Invalid CIDR: {cidr} (must be 0-32)")
    return cidr


def _validate_binary(binary: str) -> str:
    clean = binary.strip().replace(' ', '').replace('.', '')
    if not clean:
        raise ValueError("Empty binary string")
    if not all(c in '01' for c in clean):
        raise ValueError(f"Invalid binary string: '{binary}' (non-binary characters)")
    return clean


def _validate_vlan_id(vlan_id: int) -> int:
    if not 1 <= vlan_id <= 4094:
        raise ValueError(f"Invalid VLAN ID: {vlan_id} (must be 1-4094)")
    return vlan_id


# ---------------------------------------------------------------------------
#  Decimal <-> Binary
# ---------------------------------------------------------------------------

def decimal_to_binary(decimal: int) -> str:
    prefix = '-' if decimal < 0 else ''
    return prefix + bin(abs(decimal))[2:]


def decimal_to_binary_signed(decimal: int, bits: int = 8) -> str:
    if bits < 1:
        raise ValueError("Signed width must be at least 1 bit")
    minimum = -(1 << (bits - 1))
    maximum = (1 << (bits - 1)) - 1
    if not minimum <= decimal <= maximum:
        raise ValueError(
            f"{decimal} does not fit in a signed {bits}-bit integer "
            f"({minimum} to {maximum})"
        )
    return format(decimal & ((1 << bits) - 1), f'0{bits}b')


def decimal_to_binary_values(decimal: int) -> dict:
    return {
        "decimal": decimal,
        "binary": decimal_to_binary(decimal),
        "unsigned": decimal_to_binary(decimal) if decimal >= 0 else None,
        "signed_8bit": (
            decimal_to_binary_signed(decimal)
            if -128 <= decimal <= 127
            else None
        ),
    }


def print_binary_info(info: dict) -> None:
    print(f"Original value                : {info['decimal']}")
    print(f"Binary                        : {info['binary']}")
    unsigned = info['unsigned'] if info['unsigned'] is not None else "not applicable"
    print(f"Unsigned binary               : {unsigned}")
    signed = info['signed_8bit'] if info['signed_8bit'] is not None else "not representable"
    print(f"Signed (2's complement, 8-bit): {signed}")


def binary_to_decimal(binary: str, signed_bits: int = 8) -> int:
    clean = _validate_binary(binary)
    unsigned = int(clean, 2)
    if len(clean) == signed_bits and clean[0] == '1':
        return unsigned - (1 << signed_bits)
    return unsigned


def binary_to_decimal_values(binary: str, signed_bits: int = 8) -> dict:
    clean = _validate_binary(binary)
    unsigned = int(clean, 2)
    if len(clean) == signed_bits and clean[0] == '1':
        signed = unsigned - (1 << signed_bits)
    else:
        signed = unsigned
    return {"binary": clean, "unsigned": unsigned, "signed": signed}


def print_binary_to_decimal_info(binary: str, signed_bits: int = 8) -> None:
    info = binary_to_decimal_values(binary, signed_bits)
    print(f"Binary input    : {info['binary']}")
    print(f"Unsigned decimal: {info['unsigned']}")
    print(f"Signed decimal  : {info['signed']}")


# ---------------------------------------------------------------------------
#  Decimal <-> Hexadecimal
# ---------------------------------------------------------------------------

def decimal_to_hexadecimal(decimal: int) -> str:
    if decimal < 0:
        return '-' + hex(-decimal)[2:]
    return hex(decimal)[2:]


def hexadecimal_to_decimal(hexadecimal: str) -> int:
    try:
        return int(hexadecimal, 16)
    except ValueError:
        raise ValueError(f"Invalid hexadecimal string: '{hexadecimal}'")


# ---------------------------------------------------------------------------
#  Binary <-> Hexadecimal
# ---------------------------------------------------------------------------

def binary_to_hexadecimal(binary: str) -> str:
    return decimal_to_hexadecimal(int(_validate_binary(binary), 2))


def hexadecimal_to_binary(hexadecimal: str) -> str:
    dec = hexadecimal_to_decimal(hexadecimal)
    return decimal_to_binary(dec)


# ---------------------------------------------------------------------------
#  IP <-> Binary
# ---------------------------------------------------------------------------

def ip_to_binary(ip: str) -> str:
    _validate_ip(ip)
    return '.'.join(format(int(o), '08b') for o in ip.split('.'))


def ip_to_binary_full(ip: str) -> str:
    binary = ip_to_binary(ip)
    return (
        f"IPv4 address: {ip}\n"
        f"Binary (32-bit): {binary}"
    )


def binary_to_ip(binary: str) -> str:
    clean = binary.strip().replace(' ', '')
    if '.' in clean:
        groups = clean.split('.')
    else:
        _validate_binary(clean)
        if len(clean) != 32:
            raise ValueError(f"Expected 32-bit binary for IP, got {len(clean)} bits")
        groups = [clean[i:i+8] for i in range(0, 32, 8)]

    octets = []
    for g in groups:
        _validate_binary(g)
        val = int(g, 2)
        if not 0 <= val <= 255:
            raise ValueError(f"Binary group '{g}' exceeds octet range (0-255)")
        octets.append(str(val))

    if len(octets) != 4:
        raise ValueError(f"Expected 4 octets, got {len(octets)}")
    return '.'.join(octets)


# ---------------------------------------------------------------------------
#  Mask conversions
# ---------------------------------------------------------------------------

def mask_to_binary(mask: str) -> str:
    _validate_mask(mask)
    return ip_to_binary(mask)


def binary_to_mask(binary: str) -> str:
    result = binary_to_ip(binary)
    _validate_mask(result)
    return result


def mask_to_cidr(mask: str) -> int:
    _validate_mask(mask)
    return sum(bin(int(o)).count('1') for o in mask.split('.'))


def cidr_to_mask(cidr: int) -> str:
    _validate_cidr(cidr)
    bits = (0xFFFFFFFF >> (32 - cidr)) << (32 - cidr) if cidr > 0 else 0
    return '.'.join(str((bits >> (8 * i)) & 0xFF) for i in range(3, -1, -1))


def mask_to_wildcard(mask: str) -> str:
    _validate_mask(mask)
    return '.'.join(str(255 - int(o)) for o in mask.split('.'))


def wildcard_to_mask(wildcard: str) -> str:
    _validate_ip(wildcard)
    result = '.'.join(str(255 - int(o)) for o in wildcard.split('.'))
    _validate_mask(result)
    return result


# ---------------------------------------------------------------------------
#  Address / mask combined conversions
# ---------------------------------------------------------------------------

def address_to_binary(args: list) -> str:
    address = args[0]
    mask = args[1] if len(args) > 1 else None
    ip_bin = ip_to_binary(address)
    if mask:
        mask_bin = ip_to_binary(mask)
        return (
            f"IP Address : {address}\n"
            f"Mask       : {mask}\n"
            f"IP Binary  : {ip_bin}\n"
            f"Mask Binary: {mask_bin}"
        )
    return f"IP Address: {address}\nIP Binary : {ip_bin}"


def binary_to_address(binaries: List[str]) -> str:
    return '\n'.join(binary_to_ip(b) for b in binaries)


def ipv4_info(value: str) -> Dict[str, Any]:
    """Return common integer, hexadecimal, binary, and network forms."""
    try:
        interface = ipaddress.IPv4Interface(value if '/' in value else f"{value}/32")
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError) as exc:
        raise ValueError(f"Invalid IPv4 address or interface: '{value}' ({exc})")

    address = interface.ip
    network = interface.network
    result = {
        "address": str(address),
        "integer": int(address),
        "hexadecimal": f"0x{int(address):08X}",
        "binary": ip_to_binary(str(address)),
        "ipv4_mapped_ipv6": f"::ffff:{address}",
        "reverse_pointer": address.reverse_pointer,
        "classification": classify_ip(str(address)),
    }
    if '/' in value:
        result.update({
            "network": str(network),
            "prefix_length": interface.network.prefixlen,
            "netmask": str(network.netmask),
            "last_address": str(network.broadcast_address),
            "num_addresses": network.num_addresses,
        })
    return result


_IPV4_SPECIAL_PURPOSE = (
    ("255.255.255.255/32", "limited broadcast", "link", False, "current", "RFC 919"),
    ("0.0.0.0/32", "unspecified", "host", False, "current", "RFC 1122"),
    ("192.0.0.9/32", "Port Control Protocol anycast", "global", True, "current", "RFC 7723"),
    ("192.0.0.10/32", "TURN anycast", "global", True, "current", "RFC 8155"),
    ("0.0.0.0/8", "this network", "host", False, "current", "RFC 1122"),
    ("10.0.0.0/8", "private-use", "private", False, "current", "RFC 1918"),
    ("100.64.0.0/10", "shared address space (CGNAT)", "shared", False, "current", "RFC 6598"),
    ("127.0.0.0/8", "loopback", "host", False, "current", "RFC 1122"),
    ("169.254.0.0/16", "link-local", "link", False, "current", "RFC 3927"),
    ("172.16.0.0/12", "private-use", "private", False, "current", "RFC 1918"),
    ("192.0.0.0/24", "IETF protocol assignments", "special", False, "current", "RFC 6890"),
    ("192.0.0.0/29", "IPv4 service continuity prefix", "special", False, "current", "RFC 7335"),
    ("192.0.0.8/32", "IPv4 dummy address", "host", False, "current", "RFC 7600"),
    ("192.0.2.0/24", "documentation (TEST-NET-1)", "documentation", False, "current", "RFC 5737"),
    ("192.0.0.170/32", "NAT64/DNS64 discovery", "special", False, "current", "RFC 8880 / RFC 7050"),
    ("192.0.0.171/32", "NAT64/DNS64 discovery", "special", False, "current", "RFC 8880 / RFC 7050"),
    ("192.31.196.0/24", "AS112-v4", "global", True, "current", "RFC 7535"),
    ("192.52.193.0/24", "Automatic Multicast Tunneling", "global", True, "current", "RFC 7450"),
    ("192.88.99.0/24", "deprecated 6to4 relay anycast", "special", None, "legacy", "RFC 7526"),
    ("192.88.99.2/32", "6a44 relay anycast", "special", False, "current", "RFC 6751"),
    ("192.168.0.0/16", "private-use", "private", False, "current", "RFC 1918"),
    ("192.175.48.0/24", "direct delegation AS112 service", "global", True, "current", "RFC 7534"),
    ("198.18.0.0/15", "benchmarking", "benchmark", False, "current", "RFC 2544"),
    ("198.51.100.0/24", "documentation (TEST-NET-2)", "documentation", False, "current", "RFC 5737"),
    ("203.0.113.0/24", "documentation (TEST-NET-3)", "documentation", False, "current", "RFC 5737"),
    ("224.0.0.0/4", "multicast", "multicast", False, "current", "RFC 5771"),
    ("240.0.0.0/4", "reserved", "reserved", False, "current", "RFC 1112"),
)

_IPV6_SPECIAL_PURPOSE = (
    ("::/128", "unspecified", "host", False, "current", "RFC 4291"),
    ("::1/128", "loopback", "host", False, "current", "RFC 4291"),
    ("::ffff:0:0/96", "IPv4-mapped", "host", False, "current", "RFC 4291"),
    ("64:ff9b::/96", "IPv4/IPv6 translation", "global", True, "current", "RFC 6052"),
    ("64:ff9b:1::/48", "local-use IPv4/IPv6 translation", "private", False, "current", "RFC 8215"),
    ("100::/64", "discard-only", "special", False, "current", "RFC 6666"),
    ("100:0:0:1::/64", "dummy IPv6 prefix", "special", False, "current", "RFC 9780"),
    ("2001::/23", "IETF protocol assignments", "special", False, "current", "RFC 2928"),
    ("2001::/32", "Teredo", "transition", None, "legacy", "RFC 4380"),
    ("2001:1::1/128", "Port Control Protocol anycast", "global", True, "current", "RFC 7723"),
    ("2001:1::2/128", "TURN anycast", "global", True, "current", "RFC 8155"),
    ("2001:1::3/128", "DNS-SD service registration anycast", "global", True, "current", "RFC 9665"),
    ("2001:2::/48", "benchmarking", "benchmark", False, "current", "RFC 5180"),
    ("2001:3::/32", "Automatic Multicast Tunneling", "global", True, "current", "RFC 7450"),
    ("2001:4:112::/48", "AS112-v6", "global", True, "current", "RFC 7535"),
    ("2001:10::/28", "deprecated ORCHID", "special", False, "legacy", "RFC 4843"),
    ("2001:20::/28", "ORCHIDv2", "special", True, "current", "RFC 7343"),
    ("2001:30::/28", "Drone Remote ID protocol entity tags", "special", True, "current", "RFC 9374"),
    ("2001:db8::/32", "documentation", "documentation", False, "current", "RFC 3849"),
    ("2002::/16", "6to4", "transition", None, "legacy", "RFC 3056"),
    ("2620:4f:8000::/48", "direct delegation AS112 service", "global", True, "current", "RFC 7534"),
    ("3fff::/20", "documentation", "documentation", False, "current", "RFC 9637"),
    ("5f00::/20", "segment routing services", "special", False, "current", "RFC 9602"),
    ("fc00::/7", "unique-local", "private", False, "current", "RFC 4193"),
    ("fe80::/10", "link-local", "link", False, "current", "RFC 4291"),
    ("fec0::/10", "site-local", "private", False, "legacy", "RFC 3879"),
    ("ff00::/8", "multicast", "multicast", False, "current", "RFC 4291"),
)


def classify_ip(value: str) -> Dict[str, Any]:
    """Classify an address consistently across supported Python versions."""
    try:
        address = ipaddress.ip_address(value)
    except ValueError as exc:
        raise ValueError(f"Invalid IP address: '{value}' ({exc})")
    registry = _IPV4_SPECIAL_PURPOSE if address.version == 4 else _IPV6_SPECIAL_PURPOSE
    matches = []
    for prefix, name, scope, globally_reachable, status, reference in registry:
        network = ipaddress.ip_network(prefix)
        if address in network:
            matches.append((network.prefixlen, prefix, name, scope, globally_reachable, status, reference))
    matched_prefix: Optional[str]
    if matches:
        _, matched_prefix, name, scope, globally_reachable, status, reference = max(matches)
    else:
        matched_prefix = None
        name = "global unicast"
        scope = "global"
        globally_reachable = True
        status = "current"
        reference = "IANA special-purpose address registries"
    return {
        "address": str(address),
        "version": address.version,
        "name": name,
        "scope": scope,
        "globally_reachable": globally_reachable,
        "status": status,
        "matched_prefix": matched_prefix,
        "reference": reference,
        "reverse_pointer": address.reverse_pointer,
    }


def ipv4_range_to_cidrs(first: str, last: str) -> List[str]:
    """Return the exact minimal CIDR set covering an inclusive IPv4 range."""
    try:
        start = ipaddress.IPv4Address(first)
        end = ipaddress.IPv4Address(last)
    except ipaddress.AddressValueError as exc:
        raise ValueError(f"Invalid IPv4 range: {exc}")
    if int(start) > int(end):
        raise ValueError("First IPv4 address must not exceed the last address")
    return [str(net) for net in ipaddress.summarize_address_range(start, end)]


def subnet_contains(container: str, candidate: str) -> Dict[str, Any]:
    """Return whether a network contains an address or another network."""
    try:
        parent = ipaddress.ip_network(container, strict=False)
        if "/" in candidate:
            child: Any = ipaddress.ip_network(candidate, strict=False)
            if child.version != parent.version:
                raise ValueError("Cannot compare IPv4 and IPv6 values")
            contains = child.subnet_of(parent)
            normalized = str(child)
            kind = "network"
        else:
            address = ipaddress.ip_address(candidate)
            if address.version != parent.version:
                raise ValueError("Cannot compare IPv4 and IPv6 values")
            contains = address in parent
            normalized = str(address)
            kind = "address"
    except ValueError as exc:
        if str(exc).startswith("Cannot compare"):
            raise
        raise ValueError(f"Invalid subnet containment input: {exc}")
    return {
        "container": str(parent),
        "candidate": normalized,
        "candidate_type": kind,
        "contains": contains,
    }


def subnet_exclude(container: str, excluded: str) -> List[str]:
    """Return the minimal CIDRs left after excluding one contained network."""
    try:
        parent: Any = ipaddress.ip_network(container, strict=False)
        child: Any = ipaddress.ip_network(excluded, strict=False)
    except ValueError as exc:
        raise ValueError(f"Invalid subnet exclusion input: {exc}")
    if child.version != parent.version:
        raise ValueError("Cannot mix IPv4 and IPv6 networks")
    if not child.subnet_of(parent):
        raise ValueError(f"Excluded network {child} is not contained in {parent}")
    if child == parent:
        return []
    return [str(network) for network in parent.address_exclude(child)]


def subnet_nth(network: str, index: int) -> Dict[str, Any]:
    """Return an indexed address without materializing the network."""
    try:
        net = ipaddress.ip_network(network, strict=False)
    except ValueError as exc:
        raise ValueError(f"Invalid network: '{network}' ({exc})")
    if index < 0 or index >= net.num_addresses:
        raise ValueError(
            f"Address index must be between 0 and {net.num_addresses - 1}"
        )
    address = net.network_address + index
    if index == 0:
        role = "network"
    elif net.version == 4 and index == net.num_addresses - 1 and net.prefixlen < 31:
        role = "broadcast"
    elif net.version == 4 and net.prefixlen == 31:
        role = "point-to-point endpoint"
    elif net.version == 4 and net.prefixlen == 32:
        role = "host"
    elif net.version == 4:
        role = "host"
    else:
        role = "address"
    return {
        "network": str(net),
        "index": index,
        "address": str(address),
        "role": role,
        "reverse_pointer": address.reverse_pointer,
    }


def subnet_audit(entries: List[Any], parent: Optional[str] = None) -> Dict[str, Any]:
    """Audit named or unnamed network allocations for common IPAM mistakes."""
    if len(entries) > MAX_BATCH_TARGETS:
        raise ValueError(f"Subnet inventory exceeds {MAX_BATCH_TARGETS} entries")
    allocations: List[Dict[str, Any]] = []
    invalid: List[Dict[str, Any]] = []
    for index, entry in enumerate(entries):
        if isinstance(entry, str):
            value, name, requested = entry, f"entry-{index + 1}", None
        elif isinstance(entry, dict):
            value = str(entry.get("network", ""))
            name = str(entry.get("name") or f"entry-{index + 1}")
            requested = entry.get("requested_hosts") or None
        else:
            invalid.append({"index": index, "value": repr(entry), "error": "expected string or object"})
            continue
        try:
            network = ipaddress.ip_network(value, strict=False)
            if requested is not None:
                requested = int(requested)
                if requested < 0:
                    raise ValueError("requested_hosts must be zero or greater")
            usable = network.num_addresses
            if network.version == 4 and network.prefixlen < 31:
                usable -= 2
            allocations.append({
                "name": name,
                "input": value,
                "network": str(network),
                "version": network.version,
                "addresses": network.num_addresses,
                "usable_hosts": usable,
                "requested_hosts": requested,
                "unused_hosts": usable - requested if requested is not None else None,
                "utilization_pct": round((requested / usable) * 100, 2) if requested is not None and usable else None,
                "_object": network,
            })
        except ValueError as exc:
            invalid.append({"index": index, "name": name, "value": value, "error": str(exc)})

    duplicates: List[Dict[str, Any]] = []
    seen: Dict[str, str] = {}
    for allocation in allocations:
        normalized = allocation["network"]
        if normalized in seen:
            duplicates.append({
                "network": normalized,
                "first": seen[normalized],
                "duplicate": allocation["name"],
            })
        else:
            seen[normalized] = allocation["name"]

    overlaps: List[Dict[str, Any]] = []
    for left_index, left in enumerate(allocations):
        for right in allocations[left_index + 1:]:
            left_net = left["_object"]
            right_net = right["_object"]
            if left_net.version == right_net.version and left_net != right_net and left_net.overlaps(right_net):
                overlaps.append({
                    "left": left["name"],
                    "left_network": left["network"],
                    "right": right["name"],
                    "right_network": right["network"],
                })

    capacity_issues = [
        {
            "name": allocation["name"],
            "network": allocation["network"],
            "requested_hosts": allocation["requested_hosts"],
            "usable_hosts": allocation["usable_hosts"],
        }
        for allocation in allocations
        if allocation["requested_hosts"] is not None
        and allocation["requested_hosts"] > allocation["usable_hosts"]
    ]

    parent_net: Any = None
    outside_parent: List[Dict[str, str]] = []
    free_networks: List[str] = []
    if parent:
        try:
            parent_net = ipaddress.ip_network(parent, strict=False)
        except ValueError as exc:
            raise ValueError(f"Invalid parent network: '{parent}' ({exc})")
        contained_nets: List[Any] = []
        for allocation in allocations:
            network = allocation["_object"]
            if network.version != parent_net.version or not network.subnet_of(parent_net):
                outside_parent.append({"name": allocation["name"], "network": allocation["network"]})
            else:
                contained_nets.append(network)
        remaining: List[Any] = [parent_net]
        for used in ipaddress.collapse_addresses(contained_nets):
            updated: List[Any] = []
            for available in remaining:
                if used.subnet_of(available):
                    updated.extend(available.address_exclude(used))
                elif not available.overlaps(used):
                    updated.append(available)
            remaining = updated
        free_networks = [str(network) for network in remaining]

    public_allocations = []
    for allocation in allocations:
        cleaned = dict(allocation)
        cleaned.pop("_object")
        public_allocations.append(cleaned)
    status = "ok" if not (invalid or duplicates or overlaps or outside_parent or capacity_issues) else "issues"
    return {
        "status": status,
        "parent": str(parent_net) if parent_net else None,
        "allocation_count": len(public_allocations),
        "allocations": public_allocations,
        "invalid": invalid,
        "duplicates": duplicates,
        "overlaps": overlaps,
        "capacity_issues": capacity_issues,
        "outside_parent": outside_parent,
        "free_networks": free_networks,
    }


# ---------------------------------------------------------------------------
#  Subnet calculators
# ---------------------------------------------------------------------------

def subnet_calculator(network: str, mask: str) -> Dict[str, Any]:
    _validate_ip(network)
    _validate_mask(mask)
    cidr = mask_to_cidr(mask)
    net = ipaddress.ip_network(f"{network}/{cidr}", strict=False)

    num = net.num_addresses
    if net.prefixlen == 32:
        usable = 1
        first_host = last_host = str(net.network_address)
        broadcast = "N/A"
    elif net.prefixlen == 31:
        usable = 2
        first_host = str(net.network_address)
        last_host = str(net.broadcast_address)
        broadcast = "N/A"
    else:
        usable = num - 2
        first_host = str(net[1])
        last_host = str(net[-2])
        broadcast = str(net.broadcast_address)

    return {
        "network_address": str(net.network_address),
        "netmask": str(net.netmask),
        "wildcard": mask_to_wildcard(str(net.netmask)),
        "cidr": f"/{cidr}",
        "num_addresses": num,
        "hosts": usable,
        "first_host": first_host,
        "last_host": last_host,
        "broadcast": broadcast,
        "is_private": net.is_private,
        "is_global": net.is_global,
    }


def advanced_subnet_calculator(
    ip_address: str,
    new_mask: str,
    max_details: int = MAX_SUBNET_DETAILS,
) -> Dict[str, Any]:
    if '/' not in ip_address:
        raise ValueError("IP address must include CIDR notation (e.g., '192.168.1.0/24' or '2001:db8::/32')")

    # Detect IPv4 vs IPv6
    ip, original_cidr_str = ip_address.rsplit('/', 1)
    original_cidr = int(original_cidr_str)
    is_v6 = ':' in ip

    if is_v6:
        if not 0 <= original_cidr <= 128:
            raise ValueError(f"Invalid IPv6 prefix: /{original_cidr} (must be 0-128)")
        new_cidr = int(new_mask)
        if not 0 <= new_cidr <= 128:
            raise ValueError(f"Invalid IPv6 prefix: /{new_cidr} (must be 0-128)")
        max_bits = 128
    else:
        _validate_cidr(original_cidr)
        if '.' in new_mask:
            new_cidr = mask_to_cidr(new_mask)
        else:
            new_cidr = int(new_mask)
        _validate_cidr(new_cidr)
        max_bits = 32

    if new_cidr < original_cidr:
        raise ValueError(f"New prefix /{new_cidr} is larger than original /{original_cidr}")

    network = ipaddress.ip_network(f"{ip}/{original_cidr}", strict=False)
    num = network.num_addresses
    if max_details < 0:
        raise ValueError("max_details must be zero or greater")
    count_subnets = 1 << (new_cidr - original_cidr)
    sub_objects: List[Any] = list(itertools.islice(
        network.subnets(new_prefix=new_cidr),
        min(count_subnets, max_details),
    ))
    addresses_per = 1 << (max_bits - new_cidr)
    if is_v6:
        hosts_per = addresses_per
    elif new_cidr == 32:
        hosts_per = 1
    elif new_cidr == 31:
        hosts_per = 2
    else:
        hosts_per = addresses_per - 2

    subnets_detail: List[Dict[str, Any]] = []
    for s in sub_objects:
        if is_v6:
            subnets_detail.append({
                "network": str(s.network_address),
                "cidr": f"/{new_cidr}",
                "first_address": str(s.network_address),
                "last_address": str(s.broadcast_address),
                "num_addresses": s.num_addresses,
            })
        else:
            detail = subnet_calculator(str(s.network_address), str(s.netmask))
            subnets_detail.append({
                "network": str(s.network_address),
                "cidr": f"/{new_cidr}",
                "first_host": detail["first_host"],
                "last_host": detail["last_host"],
                "broadcast": detail["broadcast"],
                "usable_hosts": detail["hosts"],
            })

    result: Dict[str, Any] = {
        "original_cidr": f"/{original_cidr}",
        "new_cidr": f"/{new_cidr}",
        "original_hosts": num if is_v6 else subnet_calculator(
            str(network.network_address), str(network.netmask)
        )["hosts"],
        "hosts_per_subnet": hosts_per,
        "is_private": network.is_private,
        "count_subnets": count_subnets,
        "shown_subnets": len(subnets_detail),
        "truncated": len(subnets_detail) < count_subnets,
        "subnets": subnets_detail,
    }
    if not is_v6:
        result["original_netmask"] = cidr_to_mask(original_cidr)
        result["new_netmask"] = cidr_to_mask(new_cidr)
        result["is_global"] = network.is_global
    else:
        result["is_link_local"] = network.network_address.is_link_local

    return result


def vlsm_calculator(network: str, hosts: List[int]) -> List[Dict[str, Any]]:
    sorted_hosts = sorted(hosts, reverse=True)
    subnets = []
    try:
        ip_network_obj = ipaddress.IPv4Network(network, strict=False)
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError) as exc:
        raise ValueError(f"Invalid IPv4 network: '{network}' ({exc})")
    cursor = int(ip_network_obj.network_address)
    pool_end = int(ip_network_obj.broadcast_address) + 1

    for host_count in sorted_hosts:
        if host_count < 1:
            raise ValueError(f"Host count must be >= 1, got {host_count}")
        needed = host_count + 2
        prefix = 32 - (needed - 1).bit_length()
        _validate_cidr(prefix)

        if prefix < ip_network_obj.prefixlen:
            raise ValueError(
                f"Cannot fit {host_count} hosts (/{prefix}) in {ip_network_obj}"
            )
        block_size = 1 << (32 - prefix)
        cursor = ((cursor + block_size - 1) // block_size) * block_size
        if cursor + block_size > pool_end:
            raise ValueError(f"No space left for {host_count} hosts (/{prefix})")
        new_sub = ipaddress.IPv4Network((cursor, prefix))
        subnets.append({
            "requested_hosts": host_count,
            "subnet": str(new_sub.network_address),
            "prefix_length": prefix,
            "netmask": str(new_sub.netmask),
            "num_addresses": new_sub.num_addresses,
            "usable_hosts": new_sub.num_addresses - 2,
            "first_host": str(new_sub[1]),
            "last_host": str(new_sub[-2]),
            "broadcast": str(new_sub.broadcast_address),
            "is_private": new_sub.is_private,
            "is_global": new_sub.is_global,
        })

        cursor += block_size

    return subnets


# ---------------------------------------------------------------------------
#  IPv6 utilities
# ---------------------------------------------------------------------------

def _validate_ipv6(addr: str) -> ipaddress.IPv6Address:
    try:
        return ipaddress.IPv6Address(addr)
    except (ipaddress.AddressValueError, ValueError) as exc:
        raise ValueError(f"Invalid IPv6 address: '{addr}' ({exc})")


def _validate_ipv6_network(network: str) -> ipaddress.IPv6Network:
    if '/' not in network:
        raise ValueError(
            f"Invalid IPv6 network: '{network}' (expected CIDR notation, e.g. '2001:db8::/32')"
        )
    try:
        return ipaddress.IPv6Network(network, strict=False)
    except (ipaddress.AddressValueError, ValueError) as exc:
        raise ValueError(f"Invalid IPv6 network: '{network}' ({exc})")


def ipv6_expand(addr: str) -> str:
    obj = _validate_ipv6(addr)
    return obj.exploded


def ipv6_compress(addr: str) -> str:
    obj = _validate_ipv6(addr)
    return obj.compressed


def ipv6_to_binary(addr: str) -> str:
    obj = _validate_ipv6(addr)
    full = obj.exploded.replace(':', '')
    int_val = int(full, 16)
    bits = format(int_val, '0128b')
    return ':'.join(bits[i:i+16] for i in range(0, 128, 16))


def ipv6_subnet_calculator(network: str) -> Dict[str, Any]:
    net = _validate_ipv6_network(network)
    prefix = net.prefixlen
    num_addresses = net.num_addresses

    return {
        "network_address": str(net.network_address),
        "prefix_length": prefix,
        "num_addresses": str(num_addresses),
        "first_address": str(net.network_address),
        "last_address": str(net.broadcast_address),
        "is_private": net.is_private,
        "is_link_local": net.network_address.is_link_local,
        "is_multicast": net.network_address.is_multicast,
    }


def ipv6_type(addr: str) -> str:
    obj = _validate_ipv6(addr)

    if obj == ipaddress.IPv6Address('::1'):
        return "loopback"
    if obj == ipaddress.IPv6Address('::'):
        return "unspecified"
    if obj.is_multicast:
        return "multicast"
    if obj.is_link_local:
        return "link-local"
    if obj.is_site_local:
        return "site-local (deprecated)"
    if obj.is_private and obj.packed[0] in (0xfc, 0xfd):
        return "unique local"
    # 2001:db8::/32 - documentation range (RFC 3849)
    doc_prefix = ipaddress.IPv6Network('2001:db8::/32')
    if obj in doc_prefix:
        return "documentation"
    if obj.ipv4_mapped is not None:
        return "ipv4-mapped"
    if int(obj) >> 96 == 0x0064_ff9b:
        return "ipv4-translated (NAT64)"
    if obj.is_global:
        return "global unicast"
    if obj.is_reserved:
        return "reserved"
    # Catch-all for remaining global-scope addresses that Python
    # marks private (e.g. 6to4, Teredo) but are routable
    if obj.packed[0] & 0xe0 == 0x20:
        return "global unicast"

    return "unknown"


def generate_ipv6_ula() -> Dict[str, str]:
    """Generate a locally assigned RFC 4193 ULA /48 from 40 random bits."""
    global_id = secrets.token_bytes(5).hex()
    prefix = f"fd{global_id[:2]}:{global_id[2:6]}:{global_id[6:10]}"
    return {
        "global_id": global_id.upper(),
        "prefix": f"{prefix}::/48",
        "first_subnet": f"{prefix}:0::/64",
        "example_subnet": f"{prefix}:1::/64",
    }


# ---------------------------------------------------------------------------
#  DNS lookup
# ---------------------------------------------------------------------------

def dns_lookup(domain: str, timeout: int = 5) -> Dict[str, Any]:
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        hostname, aliases, addresses = socket.gethostbyname_ex(domain)
        return {
            "domain": domain,
            "hostname": hostname,
            "aliases": aliases,
            "addresses": addresses,
        }
    except socket.gaierror as e:
        return {"domain": domain, "error": str(e), "addresses": []}
    except socket.timeout:
        return {"domain": domain, "error": "DNS lookup timed out", "addresses": []}
    finally:
        socket.setdefaulttimeout(old_timeout)


def reverse_dns_lookup(ip: str, timeout: int = 5) -> Dict[str, Any]:
    _validate_ip(ip)
    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        hostname, aliases, addresses = socket.gethostbyaddr(ip)
        return {
            "ip": ip,
            "hostname": hostname,
            "aliases": aliases,
        }
    except (socket.herror, socket.gaierror) as e:
        return {"ip": ip, "error": str(e)}
    except socket.timeout:
        return {"ip": ip, "error": "Reverse DNS lookup timed out"}
    finally:
        socket.setdefaulttimeout(old_timeout)


# ---------------------------------------------------------------------------
#  VLAN helper
# ---------------------------------------------------------------------------

def _validate_config_name(value: str, label: str, max_length: int = 64) -> str:
    if not re.fullmatch(rf'[A-Za-z0-9_.-]{{1,{max_length}}}', value):
        raise ValueError(
            f"Invalid {label}: '{value}' (use letters, numbers, '.', '_', or '-')"
        )
    return value


def _validate_interface(value: str) -> str:
    if not re.fullmatch(r'[A-Za-z0-9./:_-]+', value):
        raise ValueError(f"Invalid interface name: '{value}'")
    return value


def _cisco_acl_address(value: str) -> str:
    value = value.strip()
    if value.lower() == 'any':
        return 'any'
    try:
        if '/' in value:
            network = ipaddress.IPv4Network(value, strict=False)
            return f"{network.network_address} {network.hostmask}"
        address = ipaddress.IPv4Address(value)
        return f"host {address}"
    except ipaddress.AddressValueError as exc:
        raise ValueError(f"Invalid Cisco ACL address: '{value}' ({exc})")


def _junos_acl_address(value: str) -> str:
    value = value.strip()
    if value.lower() == 'any':
        return '0.0.0.0/0'
    try:
        return str(ipaddress.IPv4Network(
            value if '/' in value else f"{value}/32", strict=False
        ))
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as exc:
        raise ValueError(f"Invalid Juniper ACL address: '{value}' ({exc})")


PLATFORM_PROFILES: Dict[str, Dict[str, Any]] = {
    "cisco-iosxe": {
        "vendor": "cisco",
        "software": "Cisco IOS XE",
        "status": "current",
        "version_pattern": r"^(?:1[6-9]|[2-9][0-9])(?:\.|$)",
        "reference": "https://www.cisco.com/c/en/us/td/docs/switches/lan/c9000/lyr2-fwd/vlan/vlan-configuration-guide/configure-vlan-trunks.html",
    },
    "cisco-ios": {
        "vendor": "cisco",
        "software": "Cisco IOS on legacy Catalyst hardware",
        "status": "legacy",
        "version_pattern": r"^(?:12|15)(?:\.|$)",
        "reference": "https://www.cisco.com/c/en/us/support/docs/lan-switching/8021q/8758-43.html",
    },
    "juniper-junos-els": {
        "vendor": "juniper",
        "software": "Juniper Junos ELS",
        "status": "current",
        "version_pattern": r"^[0-9]+(?:\.|R|$)",
        "reference": "https://www.juniper.net/documentation/us/en/software/junos/multicast-l2/topics/topic-map/vlans.html",
    },
    "juniper-junos-legacy": {
        "vendor": "juniper",
        "software": "Juniper Junos non-ELS",
        "status": "legacy",
        "version_pattern": r"^[0-9]+(?:\.|R|$)",
        "reference": "https://www.juniper.net/documentation/us/en/software/junos/multicast-l2/topics/topic-map/vlans.html",
    },
    "huawei-vrp": {
        "vendor": "huawei",
        "software": "Huawei VRP",
        "status": "current",
        "version_pattern": r"^V?[0-9]+(?:R|\.|$)",
        "reference": "https://support.huawei.com/enterprise/en/doc/EDOC1100334321",
    },
}

DEFAULT_PLATFORM = {
    "cisco": "cisco-iosxe",
    "juniper": "juniper-junos-els",
    "huawei": "huawei-vrp",
}


def platform_profiles(include_legacy: bool = False) -> List[Dict[str, Any]]:
    profiles = []
    for name, profile in PLATFORM_PROFILES.items():
        if profile["status"] == "legacy" and not include_legacy:
            continue
        profiles.append({"name": name, **{key: value for key, value in profile.items() if key != "version_pattern"}})
    return profiles


def _resolve_platform_profile(
    vendor: str,
    platform_name: Optional[str] = None,
    software_version: Optional[str] = None,
    allow_legacy: bool = False,
) -> tuple:
    normalized_vendor = vendor.lower()
    selected = platform_name or DEFAULT_PLATFORM.get(normalized_vendor)
    if not selected or selected not in PLATFORM_PROFILES:
        available = ", ".join(sorted(PLATFORM_PROFILES))
        raise ValueError(f"Unknown platform profile '{selected}'. Available: {available}")
    profile = PLATFORM_PROFILES[selected]
    if profile["vendor"] != normalized_vendor:
        raise ValueError(
            f"Platform profile '{selected}' belongs to {profile['vendor']}, not {vendor}"
        )
    if profile["status"] == "legacy" and not allow_legacy:
        raise ValueError(f"Platform profile '{selected}' requires --legacy")
    if software_version:
        if not re.fullmatch(r"[A-Za-z0-9_.()/-]{1,40}", software_version):
            raise ValueError("Invalid software version")
        pattern = profile.get("version_pattern")
        if pattern and not re.match(pattern, software_version, re.IGNORECASE):
            raise ValueError(
                f"Software version '{software_version}' does not match profile '{selected}'"
            )
    return selected, profile


def _parse_vlan_list(value: Optional[str]) -> List[int]:
    if not value:
        return []
    vlans = []
    for item in value.split(","):
        item = item.strip()
        if "-" in item:
            start_text, end_text = item.split("-", 1)
            start, end = int(start_text), int(end_text)
            if start > end:
                raise ValueError(f"Invalid VLAN range: {item}")
            candidates: Any = range(start, end + 1)
        else:
            candidates = [int(item)]
        for candidate in candidates:
            _validate_vlan_id(candidate)
            if candidate not in vlans:
                vlans.append(candidate)
    return vlans


def vlan_helper(
    vendor: str,
    vlan_id: int,
    vlan_name: Optional[str] = None,
    ports: Optional[List[str]] = None,
    *,
    platform_name: Optional[str] = None,
    software_version: Optional[str] = None,
    mode: str = "access",
    allowed_vlans: Optional[str] = None,
    native_vlan: Optional[int] = None,
    allow_legacy: bool = False,
) -> str:
    _validate_vlan_id(vlan_id)
    v = vendor.lower()
    selected, _profile = _resolve_platform_profile(
        v, platform_name, software_version, allow_legacy
    )
    mode = mode.lower()
    if mode not in {"access", "trunk"}:
        raise ValueError("VLAN mode must be access or trunk")
    allowed = _parse_vlan_list(allowed_vlans)
    if native_vlan is not None:
        _validate_vlan_id(native_vlan)
    if vlan_name:
        _validate_config_name(vlan_name, "VLAN name", max_length=32)
    if ports:
        for port in ports:
            _validate_interface(port)

    if v == 'cisco':
        lines = [
            "configure terminal",
            f"vlan {vlan_id}",
        ]
        if vlan_name:
            lines.append(f" name {vlan_name}")
        port_range = ','.join(ports) if ports else 'Gi0/1-24'
        lines.append(f"interface range {port_range}")
        if mode == "access":
            lines.extend([" switchport mode access", " switchport nonegotiate", f" switchport access vlan {vlan_id}"])
        else:
            if selected == "cisco-ios":
                lines.append(" switchport trunk encapsulation dot1q")
            lines.extend([" switchport mode trunk", " switchport nonegotiate"])
            if allowed:
                lines.append(f" switchport trunk allowed vlan {allowed_vlans}")
            if native_vlan is not None:
                lines.append(f" switchport trunk native vlan {native_vlan}")
        lines.extend(["end", "write memory"])
    elif v == 'juniper':
        name = vlan_name or f'vlan-{vlan_id}'
        interfaces = ports or ['ge-0/0/0']
        lines = [
            "configure",
            f"set vlans {name} vlan-id {vlan_id}",
        ]
        for iface in interfaces:
            mode_keyword = "interface-mode" if selected == "juniper-junos-els" else "port-mode"
            lines.append(f"set interfaces {iface} unit 0 family ethernet-switching {mode_keyword} {mode}")
            if mode == "access":
                lines.append(f"set interfaces {iface} unit 0 family ethernet-switching vlan members {name}")
            else:
                members = allowed_vlans or str(vlan_id)
                lines.append(f"set interfaces {iface} unit 0 family ethernet-switching vlan members [ {members.replace(',', ' ')} ]")
                if native_vlan is not None:
                    lines.append(f"set interfaces {iface} native-vlan-id {native_vlan}")
        lines.append("commit and-quit")
    elif v == 'huawei':
        lines = [
            "system-view",
            f"vlan {vlan_id}",
        ]
        if vlan_name:
            lines.append(f" name {vlan_name}")
        lines.append("quit")
        if ports:
            for port in ports:
                lines.extend([f"interface {port}", f" port link-type {mode}"])
                if mode == "access":
                    lines.append(f" port default vlan {vlan_id}")
                else:
                    members = allowed_vlans or str(vlan_id)
                    lines.append(f" port trunk allow-pass vlan {members.replace(',', ' ')}")
                    if native_vlan is not None:
                        lines.append(f" port trunk pvid vlan {native_vlan}")
                lines.append("quit")
        lines.append("return")
    else:
        raise ValueError(
            f"Unsupported vendor: '{vendor}'. Supported: cisco, juniper, huawei."
        )

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
#  ACL helper
# ---------------------------------------------------------------------------

def acl_helper(
    vendor: str,
    acl_name: str,
    action: str,
    protocol: str,
    src: str,
    dst: str,
    src_port: Optional[int] = None,
    dst_port: Optional[int] = None,
    *,
    platform_name: Optional[str] = None,
    software_version: Optional[str] = None,
    allow_legacy: bool = False,
) -> str:
    if action.lower() not in ('permit', 'deny'):
        raise ValueError(f"Invalid action: '{action}' (must be 'permit' or 'deny')")
    _validate_config_name(acl_name, "ACL name")
    v = vendor.lower()
    _resolve_platform_profile(v, platform_name, software_version, allow_legacy)
    action = action.lower()
    protocol = protocol.lower()
    _validate_config_name(protocol, "protocol", max_length=32)
    for port in (src_port, dst_port):
        if port is not None:
            _validate_port(port)
    if (src_port is not None or dst_port is not None) and protocol not in ('tcp', 'udp'):
        raise ValueError("Source and destination ports require TCP or UDP")

    if v == 'cisco':
        src_value = _cisco_acl_address(src)
        dst_value = _cisco_acl_address(dst)
        entry = f"{action} {protocol} {src_value}"
        if src_port is not None:
            entry += f" eq {src_port}"
        entry += f" {dst_value}"
        if dst_port is not None:
            entry += f" eq {dst_port}"
        lines = [
            "configure terminal",
            f"ip access-list extended {acl_name}",
            f" {entry}",
            "exit",
            "end",
            "write memory",
        ]
    elif v == 'juniper':
        base = f"set firewall family inet filter {acl_name} term RULE"
        src_value = _junos_acl_address(src)
        dst_value = _junos_acl_address(dst)
        lines = [
            "configure",
        ]
        if protocol != 'ip':
            lines.append(f"{base} from protocol {protocol}")
        lines.extend([
            f"{base} from source-address {src_value}",
            f"{base} from destination-address {dst_value}",
        ])
        if src_port is not None:
            lines.append(f"{base} from source-port {src_port}")
        if dst_port is not None:
            lines.append(f"{base} from destination-port {dst_port}")
        junos_action = "accept" if action == "permit" else "discard"
        lines.extend([f"{base} then {junos_action}", "commit and-quit"])
    else:
        raise ValueError(
            f"Unsupported vendor: '{vendor}'. Supported: cisco, juniper."
        )

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
#  Cheatsheets
# ---------------------------------------------------------------------------

VLAN_CHEATSHEET = {
    "creation": (
        "VLAN Creation:\n"
        "  Switch(config)# vlan 100\n"
        "  Switch(config-vlan)# name Engineering"
    ),
    "access": (
        "Access Port Configuration:\n"
        "  Switch(config-if)# switchport mode access\n"
        "  Switch(config-if)# switchport nonegotiate\n"
        "  Switch(config-if)# switchport access vlan 100\n"
        "  Switch(config-if)# switchport voice vlan 150"
    ),
    "trunk": (
        "Trunk Port Configuration:\n"
        "  Switch(config-if)# switchport mode trunk\n"
        "  Switch(config-if)# switchport nonegotiate\n"
        "  Switch(config-if)# switchport trunk allowed vlan 10,100-200,999\n"
        "  Switch(config-if)# switchport trunk native vlan 999"
    ),
    "svi": (
        "SVI Configuration:\n"
        "  Switch(config)# interface vlan 100\n"
        "  Switch(config-if)# ip address 192.168.100.1 255.255.255.0\n"
        "  Switch(config-if)# no shutdown"
    ),
    "vtp": (
        "VLAN Trunking Protocol (VTP, when intentionally deployed):\n"
        "  Switch(config)# vtp version 3\n"
        "  Switch(config)# vtp domain EXAMPLE\n"
        "  Switch(config)# vtp mode transparent\n"
        "  Verify the configuration revision before joining an existing domain."
    ),
    "troubleshooting": (
        "Troubleshooting:\n"
        "  show vlan\n"
        "  show interfaces status\n"
        "  show interfaces switchport\n"
        "  show interfaces trunk\n"
        "  show vtp status\n"
        "  show vtp counters"
    ),
    "terminology": (
        "Terminology:\n"
        "  Trunking:  Extending multiple VLANs over the same physical connection\n"
        "  Native VLAN:  Frames in this VLAN are untagged on a trunk\n"
        "  Access VLAN:  The VLAN to which an access port is assigned\n"
        "  Voice VLAN:  Enables minimal trunking for voice traffic on an access port\n"
        "  DTP:  Dynamic Trunking Protocol (security risk)\n"
        "  SVI:  Switched Virtual Interface, routed gateway into/out of a VLAN\n\n"
        "Switch Port Modes:\n"
        "  trunk:             Forms an unconditional trunk\n"
        "  dynamic desirable: Actively attempts to negotiate a trunk\n"
        "  dynamic auto:      Will form a trunk only if requested\n"
        "  access:            Will never form a trunk"
    ),
    "trunktypes": (
        "Trunk Types:\n"
        "  802.1Q: 4-byte tag | IEEE standard | VLAN IDs 1-4094"
    ),
    "vlannumbers": (
        "VLAN Numbers:\n"
        "  0:         Reserved\n"
        "  1:         Default\n"
        "  1002-1005: Legacy (FDDI/Token Ring)\n"
        "  1006-4094: Extended\n"
        "  4095:      Reserved"
    ),
}

VLAN_LEGACY_CHEATSHEET = {
    "legacy_trunking": (
        "Legacy Cisco Trunking (maintenance and migration only):\n"
        "  These commands apply only to hardware supporting both ISL and 802.1Q.\n"
        "  Switch(config-if)# switchport trunk encapsulation dot1q\n"
        "  Switch(config-if)# switchport trunk encapsulation isl\n"
        "  ISL is Cisco-proprietary; use IEEE 802.1Q for new deployments."
    ),
    "legacy_vtp": (
        "VTP Versions 1 and 2 (maintenance and migration only):\n"
        "  Switch(config)# vtp version 2\n"
        "  Switch(config)# vtp domain EXAMPLE\n"
        "  Switch(config)# vtp mode server\n"
        "  Before joining an existing domain, verify and reset the configuration\n"
        "  revision with the procedure documented for the target platform. A device\n"
        "  with a higher revision can replace the domain VLAN database."
    ),
}

ACL_CHEATSHEET = {
    "creation": (
        "ACL Creation:\n"
        "  Standard ACL (1-99):\n"
        "    Router(config)# access-list 10 permit 192.168.1.0 0.0.0.255\n\n"
        "  Extended ACL (100-199):\n"
        "    Router(config)# access-list 101 permit tcp 192.168.1.0 0.0.0.255 any eq 80\n"
        "    Router(config)# access-list 101 deny ip any any log"
    ),
    "permit": (
        "Permit Statements:\n"
        "  Specific IP:  access-list 10 permit 192.168.1.10\n"
        "  Subnet:       access-list 10 permit 192.168.1.0 0.0.0.255\n"
        "  TCP traffic:  access-list 101 permit tcp any any eq 80"
    ),
    "deny": (
        "Deny Statements:\n"
        "  Specific IP:  access-list 10 deny 192.168.1.10\n"
        "  Subnet:       access-list 10 deny 192.168.1.0 0.0.0.255\n"
        "  All:          access-list 101 deny ip any any"
    ),
    "apply": (
        "Applying ACLs to Interfaces:\n"
        "  Inbound:  Router(config-if)# ip access-group 101 in\n"
        "  Outbound: Router(config-if)# ip access-group 101 out"
    ),
    "verify": (
        "Verifying ACLs:\n"
        "  Router# show access-lists\n"
        "  Router# show ip interface [interface_name]\n"
        "  Router# show access-list 101"
    ),
    "ipv6": (
        "IPv6 ACLs:\n"
        "  Create:  Router(config)# ipv6 access-list MYV6ACL\n"
        "           Router(config-ipv6-acl)# permit tcp any any eq 80\n"
        "  Apply:   Router(config-if)# ipv6 traffic-filter MYV6ACL in"
    ),
}

HUAWEI_VLAN_CHEATSHEET = {
    "creation": (
        "Huawei VRP - VLAN Creation:\n"
        "  [Switch] vlan 100\n"
        "  [Switch-vlan100] description Engineering\n"
        "  [Switch] vlan batch 10 20 30\n"
        "  [Switch] vlan batch 100 to 200"
    ),
    "access": (
        "Huawei VRP - Access Port Configuration:\n"
        "  [Switch] interface GigabitEthernet 0/0/1\n"
        "  [Switch-GigabitEthernet0/0/1] port link-type access\n"
        "  [Switch-GigabitEthernet0/0/1] port default vlan 100"
    ),
    "trunk": (
        "Huawei VRP - Trunk Port Configuration:\n"
        "  [Switch] interface GigabitEthernet 0/0/24\n"
        "  [Switch-GigabitEthernet0/0/24] port link-type trunk\n"
        "  [Switch-GigabitEthernet0/0/24] port trunk allow-pass vlan 10 20 100\n"
        "  [Switch-GigabitEthernet0/0/24] port trunk pvid vlan 1"
    ),
    "hybrid": (
        "Huawei VRP - Hybrid Port Configuration:\n"
        "  [Switch-GigabitEthernet0/0/1] port link-type hybrid\n"
        "  [Switch-GigabitEthernet0/0/1] port hybrid pvid vlan 100\n"
        "  [Switch-GigabitEthernet0/0/1] port hybrid untagged vlan 100\n"
        "  [Switch-GigabitEthernet0/0/1] port hybrid tagged vlan 10 20"
    ),
    "troubleshooting": (
        "Huawei VRP - Troubleshooting:\n"
        "  display vlan\n"
        "  display vlan 100\n"
        "  display port vlan\n"
        "  display interface GigabitEthernet 0/0/1\n"
        "  display vlan summary\n"
        "  display current-configuration interface GigabitEthernet 0/0/1"
    ),
}

MIKROTIK_VLAN_CHEATSHEET = {
    "creation": (
        "MikroTik RouterOS - VLAN Creation (Bridge VLAN Filtering):\n"
        "  /interface bridge add name=bridge1 vlan-filtering=no\n"
        "  /interface bridge vlan add bridge=bridge1 vlan-ids=100 tagged=bridge1\n"
        "  /interface vlan add interface=bridge1 vlan-id=100 name=vlan100\n"
        "  # Enable filtering after config is complete:\n"
        "  /interface bridge set bridge1 vlan-filtering=yes"
    ),
    "access": (
        "MikroTik RouterOS - Access Port (Untagged):\n"
        "  /interface bridge port add bridge=bridge1 interface=ether2 pvid=100\n"
        "  /interface bridge vlan add bridge=bridge1 vlan-ids=100 untagged=ether2\n"
        "  # Or append to existing entry:\n"
        "  /interface bridge vlan set [find vlan-ids=100] untagged=ether2,ether3"
    ),
    "trunk": (
        "MikroTik RouterOS - Trunk Port (Tagged):\n"
        "  /interface bridge port add bridge=bridge1 interface=ether1\n"
        "  /interface bridge vlan set [find vlan-ids=100] tagged=ether1,bridge1\n"
        "  # Multiple VLANs on same trunk:\n"
        "  /interface bridge vlan add bridge=bridge1 vlan-ids=200 tagged=ether1,bridge1"
    ),
    "ip_assignment": (
        "MikroTik RouterOS - IP on VLAN Interface:\n"
        "  /ip address add address=192.168.100.1/24 interface=vlan100"
    ),
    "troubleshooting": (
        "MikroTik RouterOS - Troubleshooting:\n"
        "  /interface bridge vlan print\n"
        "  /interface bridge port print\n"
        "  /interface vlan print\n"
        "  /interface bridge host print\n"
        "  /interface print detail where type=vlan"
    ),
}

FIREWALL_CHEATSHEET = {
    "paloalto": (
        "Palo Alto PAN-OS - Firewall Rules:\n"
        "  set rulebase security rules ALLOW-WEB from untrust to trust\n"
        "  set rulebase security rules ALLOW-WEB source any\n"
        "  set rulebase security rules ALLOW-WEB destination 10.0.1.100\n"
        "  set rulebase security rules ALLOW-WEB application web-browsing\n"
        "  set rulebase security rules ALLOW-WEB service application-default\n"
        "  set rulebase security rules ALLOW-WEB action allow\n"
        "  set rulebase security rules ALLOW-WEB log-start yes\n"
        "  set rulebase security rules ALLOW-WEB log-end yes\n\n"
        "  Commit:  commit\n"
        "  Verify:  show running security-policy"
    ),
    "fortinet": (
        "Fortinet FortiGate - Firewall Policy:\n"
        "  config firewall policy\n"
        "    edit 0\n"
        "      set name \"Allow-Web\"\n"
        "      set srcintf \"wan1\"\n"
        "      set dstintf \"lan\"\n"
        "      set srcaddr \"all\"\n"
        "      set dstaddr \"WebServer\"\n"
        "      set action accept\n"
        "      set schedule \"always\"\n"
        "      set service \"HTTP\" \"HTTPS\"\n"
        "      set logtraffic all\n"
        "    next\n"
        "  end\n\n"
        "  Verify:  get firewall policy\n"
        "  Debug:   diagnose debug flow filter addr 10.0.1.100"
    ),
    "iptables": (
        "iptables - Firewall Rules:\n"
        "  # Allow inbound HTTP\n"
        "  iptables -A INPUT -p tcp --dport 80 -j ACCEPT\n"
        "  # Allow established/related\n"
        "  iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT\n"
        "  # Drop all other inbound\n"
        "  iptables -A INPUT -j DROP\n"
        "  # Allow specific source\n"
        "  iptables -A INPUT -s 192.168.1.0/24 -p tcp --dport 22 -j ACCEPT\n"
        "  # Delete rule by number\n"
        "  iptables -D INPUT 3\n\n"
        "  List:    iptables -L -n -v --line-numbers\n"
        "  Save:    iptables-save > /etc/iptables/rules.v4\n"
        "  Restore: iptables-restore < /etc/iptables/rules.v4"
    ),
    "nftables": (
        "nftables - Firewall Rules:\n"
        "  # Create table and chain\n"
        "  nft add table inet filter\n"
        "  nft add chain inet filter input { type filter hook input priority 0 \\; policy drop \\; }\n\n"
        "  # Allow loopback\n"
        "  nft add rule inet filter input iif lo accept\n"
        "  # Allow established/related\n"
        "  nft add rule inet filter input ct state established,related accept\n"
        "  # Allow SSH from subnet\n"
        "  nft add rule inet filter input ip saddr 192.168.1.0/24 tcp dport 22 accept\n"
        "  # Allow HTTP/HTTPS\n"
        "  nft add rule inet filter input tcp dport { 80, 443 } accept\n\n"
        "  List:    nft list ruleset\n"
        "  Save:    nft list ruleset > /etc/nftables.conf\n"
        "  Flush:   nft flush ruleset"
    ),
}

ROUTING_CHEATSHEET = {
    "static": (
        "Static Routing:\n"
        "  Cisco IOS:\n"
        "    Router(config)# ip route 10.10.0.0 255.255.0.0 192.168.1.1\n"
        "    Router(config)# ip route 0.0.0.0 0.0.0.0 192.168.1.1        ! default route\n"
        "    Router(config)# ipv6 route 2001:db8::/32 2001:db8::1\n\n"
        "  Juniper JunOS:\n"
        "    set routing-options static route 10.10.0.0/16 next-hop 192.168.1.1\n"
        "    set routing-options static route 0.0.0.0/0 next-hop 192.168.1.1\n\n"
        "  Huawei VRP:\n"
        "    [Router] ip route-static 10.10.0.0 255.255.0.0 192.168.1.1\n"
        "    [Router] ip route-static 0.0.0.0 0.0.0.0 192.168.1.1"
    ),
    "ospf": (
        "OSPF (Cisco IOS):\n"
        "  Router(config)# router ospf 1\n"
        "  Router(config-router)# router-id 1.1.1.1\n"
        "  Router(config-router)# network 10.0.0.0 0.0.0.255 area 0\n"
        "  Router(config-router)# network 192.168.1.0 0.0.0.255 area 1\n"
        "  Router(config-router)# passive-interface GigabitEthernet0/0\n"
        "  Router(config-router)# default-information originate\n\n"
        "  Interface cost:\n"
        "    Router(config-if)# ip ospf cost 10\n"
        "    Router(config-if)# ip ospf priority 100"
    ),
    "bgp": (
        "BGP (Cisco IOS):\n"
        "  Router(config)# router bgp 65001\n"
        "  Router(config-router)# bgp router-id 1.1.1.1\n"
        "  Router(config-router)# neighbor 203.0.113.1 remote-as 65002\n"
        "  Router(config-router)# neighbor 203.0.113.1 description UPSTREAM-ISP\n"
        "  Router(config-router)# network 10.0.0.0 mask 255.255.255.0\n\n"
        "  iBGP peer:\n"
        "    Router(config-router)# neighbor 10.0.0.2 remote-as 65001\n"
        "    Router(config-router)# neighbor 10.0.0.2 update-source Loopback0\n"
        "    Router(config-router)# neighbor 10.0.0.2 next-hop-self"
    ),
    "troubleshooting": (
        "Routing Troubleshooting:\n"
        "  show ip route\n"
        "  show ip route ospf\n"
        "  show ip route bgp\n"
        "  show ip protocols\n"
        "  show ip ospf neighbor\n"
        "  show ip ospf interface brief\n"
        "  show ip ospf database\n"
        "  show ip bgp summary\n"
        "  show ip bgp neighbors 203.0.113.1\n"
        "  show ip bgp\n"
        "  debug ip routing\n"
        "  traceroute 10.10.0.1"
    ),
}

NAT_CHEATSHEET = {
    "cisco_static": (
        "Cisco Static NAT (1:1):\n"
        "  Router(config)# ip nat inside source static 10.0.1.100 203.0.113.10\n"
        "  Router(config)# interface GigabitEthernet0/0\n"
        "  Router(config-if)# ip nat inside\n"
        "  Router(config)# interface GigabitEthernet0/1\n"
        "  Router(config-if)# ip nat outside"
    ),
    "cisco_dynamic": (
        "Cisco Dynamic NAT (Pool):\n"
        "  Router(config)# ip nat pool NATPOOL 203.0.113.10 203.0.113.20 netmask 255.255.255.0\n"
        "  Router(config)# access-list 1 permit 10.0.1.0 0.0.0.255\n"
        "  Router(config)# ip nat inside source list 1 pool NATPOOL\n"
        "  Router(config-if)# ip nat inside\n"
        "  Router(config-if)# ip nat outside"
    ),
    "cisco_pat": (
        "Cisco PAT (Overload / Many-to-One):\n"
        "  Router(config)# access-list 1 permit 10.0.0.0 0.0.255.255\n"
        "  Router(config)# ip nat inside source list 1 interface GigabitEthernet0/1 overload\n"
        "  Router(config)# interface GigabitEthernet0/0\n"
        "  Router(config-if)# ip nat inside\n"
        "  Router(config)# interface GigabitEthernet0/1\n"
        "  Router(config-if)# ip nat outside"
    ),
    "iptables_nat": (
        "iptables NAT:\n"
        "  # Enable IP forwarding\n"
        "  sysctl -w net.ipv4.ip_forward=1\n\n"
        "  # Source NAT (masquerade outbound)\n"
        "  iptables -t nat -A POSTROUTING -s 10.0.0.0/16 -o eth0 -j MASQUERADE\n\n"
        "  # Static SNAT\n"
        "  iptables -t nat -A POSTROUTING -s 10.0.1.100 -o eth0 -j SNAT --to-source 203.0.113.10\n\n"
        "  # Destination NAT (port forward)\n"
        "  iptables -t nat -A PREROUTING -i eth0 -p tcp --dport 8080 -j DNAT --to-destination 10.0.1.100:80\n\n"
        "  List NAT rules:\n"
        "  iptables -t nat -L -n -v --line-numbers"
    ),
    "troubleshooting": (
        "NAT Troubleshooting:\n"
        "  Cisco:\n"
        "    show ip nat translations\n"
        "    show ip nat statistics\n"
        "    clear ip nat translation *\n"
        "    debug ip nat\n\n"
        "  Linux:\n"
        "    conntrack -L\n"
        "    conntrack -E\n"
        "    cat /proc/net/nf_conntrack\n"
        "    iptables -t nat -L -n -v"
    ),
}


CHEATSHEET_COLLECTIONS = {
    "vlan": VLAN_CHEATSHEET,
    "acl": ACL_CHEATSHEET,
    "huawei": HUAWEI_VLAN_CHEATSHEET,
    "mikrotik": MIKROTIK_VLAN_CHEATSHEET,
    "firewall": FIREWALL_CHEATSHEET,
    "routing": ROUTING_CHEATSHEET,
    "nat": NAT_CHEATSHEET,
}

CHEATSHEET_DEFAULT_METADATA = {
    "vlan": {
        "status": "current",
        "platforms": ["cisco-iosxe"],
        "software": "Cisco IOS XE",
        "source": PLATFORM_PROFILES["cisco-iosxe"]["reference"],
    },
    "acl": {
        "status": "current",
        "platforms": ["cisco-iosxe"],
        "software": "Cisco IOS XE",
        "source": "https://www.cisco.com/c/en/us/support/docs/security/ios-firewall/23602-confaccesslists.html",
    },
    "huawei": {
        "status": "current",
        "platforms": ["huawei-vrp"],
        "software": "Huawei VRP",
        "source": PLATFORM_PROFILES["huawei-vrp"]["reference"],
    },
    "mikrotik": {
        "status": "current",
        "platforms": ["mikrotik-routeros"],
        "software": "MikroTik RouterOS",
        "source": "https://help.mikrotik.com/docs/spaces/ROS/pages/28606465/Bridge+VLAN+Table",
    },
    "firewall": {
        "status": "current",
        "platforms": ["linux", "paloalto-panos", "fortinet-fortios"],
        "software": "Platform-specific",
        "source": "https://netfilter.org/projects/nftables/manpage.html",
    },
    "routing": {
        "status": "current",
        "platforms": ["cisco-iosxe", "juniper-junos-els", "huawei-vrp"],
        "software": "Platform-specific",
        "source": "https://www.cisco.com/c/en/us/td/docs/ios-xml/ios/iproute_pi/configuration/xe-17/iri-xe-17-book.html",
    },
    "nat": {
        "status": "current",
        "platforms": ["cisco-iosxe", "linux"],
        "software": "Platform-specific",
        "source": "https://www.cisco.com/c/en/us/support/docs/ip/network-address-translation-nat/13772-12.html",
    },
}

CHEATSHEET_SECTION_METADATA = {
    ("vlan", "legacy_trunking"): {
        "status": "legacy",
        "platforms": ["cisco-ios"],
        "software": "Cisco IOS on ISL-capable Catalyst hardware",
        "replacement": "IEEE 802.1Q on a current platform",
        "source": PLATFORM_PROFILES["cisco-ios"]["reference"],
    },
    ("vlan", "legacy_vtp"): {
        "status": "legacy",
        "platforms": ["cisco-ios", "cisco-iosxe"],
        "software": "Cisco VTP versions 1 and 2",
        "replacement": "VTP version 3 or transparent/off mode",
        "source": "https://www.cisco.com/c/en/us/support/docs/lan-switching/vtp/98154-conf-vlan.html",
    },
}


def render_cheatsheet(
    sheet: str,
    section: Optional[str] = None,
    include_legacy: bool = False,
    platform_name: Optional[str] = None,
    show_sources: bool = False,
) -> str:
    """Render filtered reference entries with optional provenance metadata."""
    if sheet not in CHEATSHEET_COLLECTIONS:
        raise ValueError(f"Unknown cheatsheet: {sheet}")
    entries = dict(CHEATSHEET_COLLECTIONS[sheet])
    if sheet == "vlan" and include_legacy:
        entries.update(VLAN_LEGACY_CHEATSHEET)
    if section:
        if section not in entries:
            available = ", ".join(entries)
            raise ValueError(f"Unknown section '{section}'. Available: {available}")
        entries = {section: entries[section]}
    rendered = []
    for name, content in entries.items():
        metadata = dict(CHEATSHEET_DEFAULT_METADATA[sheet])
        metadata.update(CHEATSHEET_SECTION_METADATA.get((sheet, name), {}))
        if platform_name and platform_name not in metadata.get("platforms", []):
            continue
        block = content
        if show_sources:
            block += (
                "\n  Reference metadata:"
                f"\n    status: {metadata['status']}"
                f"\n    platforms: {', '.join(metadata.get('platforms', []))}"
                f"\n    software: {metadata.get('software', 'unspecified')}"
            )
            if metadata.get("replacement"):
                block += f"\n    replacement: {metadata['replacement']}"
            if metadata.get("source"):
                block += f"\n    source: {metadata['source']}"
        rendered.append(block)
    if not rendered:
        raise ValueError(
            f"No {sheet} reference entries match platform '{platform_name}'"
        )
    return "\n\n".join(rendered)


def _cheatsheet_lookup(sheets: dict, section: Optional[str] = None) -> str:
    if section and section in sheets:
        return sheets[section]
    if section and section not in sheets:
        avail = ', '.join(sheets.keys())
        raise ValueError(f"Unknown section '{section}'. Available: {avail}")
    return '\n\n'.join(sheets.values())


def vlan_cheatsheet(
    section: Optional[str] = None,
    include_legacy: bool = False,
) -> str:
    sheets = dict(VLAN_CHEATSHEET)
    if include_legacy:
        sheets.update(VLAN_LEGACY_CHEATSHEET)
    return _cheatsheet_lookup(sheets, section)

def acl_cheatsheet(section: Optional[str] = None) -> str:
    return _cheatsheet_lookup(ACL_CHEATSHEET, section)

def huawei_vlan_cheatsheet(section: Optional[str] = None) -> str:
    return _cheatsheet_lookup(HUAWEI_VLAN_CHEATSHEET, section)

def mikrotik_vlan_cheatsheet(section: Optional[str] = None) -> str:
    return _cheatsheet_lookup(MIKROTIK_VLAN_CHEATSHEET, section)

def firewall_cheatsheet(section: Optional[str] = None) -> str:
    return _cheatsheet_lookup(FIREWALL_CHEATSHEET, section)

def routing_cheatsheet(section: Optional[str] = None) -> str:
    return _cheatsheet_lookup(ROUTING_CHEATSHEET, section)

def nat_cheatsheet(section: Optional[str] = None) -> str:
    return _cheatsheet_lookup(NAT_CHEATSHEET, section)


# ---------------------------------------------------------------------------
#  MAC address utilities
# ---------------------------------------------------------------------------

_MAC_RE = re.compile(
    r'^(?:'
    r'(?:[0-9a-fA-F]{2}[:\-]){5}[0-9a-fA-F]{2}'
    r'|'
    r'(?:[0-9a-fA-F]{4}\.){2}[0-9a-fA-F]{4}'
    r'|'
    r'[0-9a-fA-F]{12}'
    r')$'
)


def _strip_mac(mac: str) -> str:
    """Return 12 lowercase hex characters from any accepted MAC format."""
    raw = mac.strip()
    if not _MAC_RE.match(raw):
        raise ValueError(f"Invalid MAC address: '{mac}'")
    bare = raw.replace(':', '').replace('-', '').replace('.', '').lower()
    if len(bare) != 12:
        raise ValueError(f"Invalid MAC address: '{mac}'")
    return bare


def mac_normalize(mac: str) -> str:
    """Accept any MAC format and return lowercase colon-separated
    (aa:bb:cc:dd:ee:ff)."""
    bare = _strip_mac(mac)
    return ':'.join(bare[i:i + 2] for i in range(0, 12, 2))


def mac_format(mac: str, style: str = "colon") -> str:
    """Convert MAC to the requested style.

    Styles:
        colon - aa:bb:cc:dd:ee:ff
        dash  - AA-BB-CC-DD-EE-FF
        cisco - aabb.ccdd.eeff
        bare  - aabbccddeeff
    """
    bare = _strip_mac(mac)
    if style == "colon":
        return ':'.join(bare[i:i + 2] for i in range(0, 12, 2))
    if style == "dash":
        return '-'.join(bare[i:i + 2] for i in range(0, 12, 2)).upper()
    if style == "cisco":
        return '.'.join(bare[i:i + 4] for i in range(0, 12, 4))
    if style == "bare":
        return bare
    raise ValueError(
        f"Unknown style '{style}'. Choose from: colon, dash, cisco, bare"
    )


def mac_vendor(mac: str) -> str:
    """Return the OUI prefix (first 3 octets) formatted as XX:XX:XX.

    Full vendor name resolution requires an external OUI database (e.g. the
    IEEE MA-L file at https://standards-oui.ieee.org/oui/oui.csv). This
    function only extracts and formats the OUI portion of the address.
    """
    bare = _strip_mac(mac)
    oui = ':'.join(bare[i:i + 2] for i in range(0, 6, 2))
    return (
        f"OUI: {oui.upper()} "
        f"(vendor lookup requires an external IEEE OUI database)"
    )


def default_oui_database_path() -> Path:
    cache_root = os.environ.get("XDG_CACHE_HOME")
    base = Path(cache_root).expanduser() if cache_root else Path.home() / ".cache"
    return base / "sysadmintoolbox" / "oui.csv"


def update_oui_database(
    destination: Optional[str] = None,
    url: str = DEFAULT_IEEE_OUI_URL,
    timeout: int = 30,
) -> Dict[str, Any]:
    """Download the IEEE MA-L registry to an explicit local cache."""
    if timeout <= 0:
        raise ValueError("Timeout must be greater than zero")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("OUI database URL must use HTTPS")
    target = Path(destination).expanduser() if destination else default_oui_database_path()
    request = urllib.request.Request(url, headers={"User-Agent": f"SysAdminToolbox/{__version__}"})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content = response.read(50 * 1024 * 1024 + 1)
    except (urllib.error.URLError, socket.timeout, OSError) as exc:
        raise RuntimeError(f"Cannot download IEEE OUI database: {exc}")
    if len(content) > 50 * 1024 * 1024:
        raise RuntimeError("IEEE OUI database exceeds the 50 MiB safety limit")
    try:
        decoded = content.decode("utf-8-sig")
        reader = csv.DictReader(decoded.splitlines())
        fields = set(reader.fieldnames or [])
        required = {"Assignment", "Organization Name"}
        if not required.issubset(fields):
            raise ValueError("downloaded file does not contain IEEE OUI columns")
        count = sum(1 for row in reader if row.get("Assignment"))
    except (UnicodeDecodeError, csv.Error, ValueError) as exc:
        raise RuntimeError(f"Invalid IEEE OUI database: {exc}")
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    try:
        temporary.write_bytes(content)
        os.replace(temporary, target)
    except OSError as exc:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise RuntimeError(f"Cannot write OUI database '{target}': {exc}")
    return {
        "path": str(target),
        "source": url,
        "entries": count,
        "bytes": len(content),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def load_oui_database(source: Optional[str] = None) -> Dict[str, Dict[str, str]]:
    path = Path(source).expanduser() if source else default_oui_database_path()
    if not path.is_file():
        raise ValueError(
            f"OUI database not found: {path}. Run 'mac oui-update' or provide --db."
        )
    database: Dict[str, Dict[str, str]] = {}
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            fields = set(reader.fieldnames or [])
            if not {"Assignment", "Organization Name"}.issubset(fields):
                raise ValueError("OUI database is missing Assignment or Organization Name")
            for row in reader:
                assignment = re.sub(r"[^0-9A-Fa-f]", "", row.get("Assignment", "")).upper()
                if len(assignment) == 6:
                    database[assignment] = {
                        "organization": row.get("Organization Name", "").strip(),
                        "address": row.get("Organization Address", "").strip(),
                        "registry": row.get("Registry", "MA-L").strip() or "MA-L",
                    }
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise ValueError(f"Cannot read OUI database '{path}': {exc}")
    if not database:
        raise ValueError(f"OUI database contains no valid MA-L assignments: {path}")
    return database


def mac_vendor_lookup(mac: str, database_path: Optional[str] = None) -> Dict[str, Any]:
    bare = _strip_mac(mac)
    oui = bare[:6].upper()
    result: Dict[str, Any] = {
        "mac": mac_normalize(mac),
        "oui": ":".join(oui[index:index + 2] for index in range(0, 6, 2)),
        "is_local": bool(int(bare[:2], 16) & 0x02),
        "database": str(Path(database_path).expanduser() if database_path else default_oui_database_path()),
    }
    if result["is_local"]:
        result.update({"found": False, "organization": None, "reason": "locally administered address"})
        return result
    database = load_oui_database(database_path)
    match = database.get(oui)
    if match:
        result.update({"found": True, **match})
    else:
        result.update({"found": False, "organization": None, "reason": "OUI not present in database"})
    return result


def mac_info(mac: str) -> Dict[str, Any]:
    """Return a dict with detailed information about the given MAC address.

    Keys:
        normalized   - lowercase colon-separated form
        oui          - first 3 octets (uppercase, colon-separated)
        is_multicast - True when bit 0 of the first octet is set
        is_unicast   - opposite of is_multicast
        is_local     - True when bit 1 of the first octet is set (LAA)
        all_formats  - dict with colon / dash / cisco / bare representations
    """
    bare = _strip_mac(mac)
    first_octet = int(bare[0:2], 16)
    multicast = bool(first_octet & 0x01)
    local = bool(first_octet & 0x02)
    normalized = ':'.join(bare[i:i + 2] for i in range(0, 12, 2))
    oui = ':'.join(bare[i:i + 2] for i in range(0, 6, 2)).upper()

    return {
        "normalized": normalized,
        "oui": oui,
        "is_multicast": multicast,
        "is_unicast": not multicast,
        "is_local": local,
        "all_formats": {
            "colon": mac_format(mac, "colon"),
            "dash": mac_format(mac, "dash"),
            "cisco": mac_format(mac, "cisco"),
            "bare": mac_format(mac, "bare"),
        },
    }


def generate_local_macs(count: int = 1, style: str = "colon") -> List[str]:
    """Generate cryptographically random locally administered unicast MACs."""
    if not 1 <= count <= 100:
        raise ValueError("MAC quantity must be between 1 and 100")
    results = []
    for _ in range(count):
        raw = bytearray(secrets.token_bytes(6))
        raw[0] = (raw[0] | 0x02) & 0xFE
        results.append(mac_format(raw.hex(), style))
    return results


# ---------------------------------------------------------------------------
#  Supernet / overlap utilities
# ---------------------------------------------------------------------------

def supernet(networks: List[str]) -> str:
    """Find the smallest supernet that contains all given CIDR networks.

    Uses ipaddress.collapse_addresses() to merge contiguous blocks, then
    widens until a single prefix covers every input network.
    """
    if not networks:
        raise ValueError("Network list must not be empty")
    nets: List[Any] = [ipaddress.ip_network(n, strict=False) for n in networks]

    versions = {n.version for n in nets}
    if len(versions) > 1:
        raise ValueError("Cannot mix IPv4 and IPv6 networks")

    collapsed: List[Any] = list(ipaddress.collapse_addresses(nets))
    if len(collapsed) == 1:
        return str(collapsed[0])

    first = collapsed[0]
    last = collapsed[-1]
    for prefix_len in range(min(n.prefixlen for n in collapsed), -1, -1):
        candidate = ipaddress.ip_network(
            f"{first.network_address}/{prefix_len}", strict=False
        )
        if (
            int(last.broadcast_address)
            <= int(candidate.broadcast_address)
            and int(first.network_address)
            >= int(candidate.network_address)
        ):
            return str(candidate)

    return str(ipaddress.ip_network(
        f"{first.network_address}/0", strict=False
    ))


def check_overlap(net1: str, net2: str) -> Dict[str, Any]:
    """Check whether two CIDR networks overlap and return details.

    Keys:
        network1        - first network (normalized CIDR)
        network2        - second network (normalized CIDR)
        overlaps        - True if any addresses are shared
        overlap_network - the overlapping portion as CIDR, or None
    """
    n1 = ipaddress.ip_network(net1, strict=False)
    n2 = ipaddress.ip_network(net2, strict=False)

    if n1.version != n2.version:
        raise ValueError("Cannot compare IPv4 and IPv6 networks")

    overlaps = n1.overlaps(n2)
    overlap_network: Optional[str] = None
    if overlaps:
        overlap_network = str(n1 if n1.prefixlen >= n2.prefixlen else n2)

    return {
        "network1": str(n1),
        "network2": str(n2),
        "overlaps": overlaps,
        "overlap_network": overlap_network,
    }


# ---------------------------------------------------------------------------
#  Network diagnostics - validation helpers
# ---------------------------------------------------------------------------

def _validate_host(host: str) -> str:
    """Validate that *host* is a valid IP address or hostname."""
    try:
        ipaddress.ip_address(host)
        return host
    except ValueError:
        pass
    pattern = re.compile(
        r'^(?!-)[A-Za-z0-9-]{1,63}(?<!-)(\.[A-Za-z0-9-]{1,63})*$'
    )
    if not pattern.match(host):
        raise ValueError(
            f"Invalid host: '{host}' (not a valid IPv4 address or hostname)"
        )
    return host


def _validate_port(port: int) -> int:
    if not (1 <= port <= 65535):
        raise ValueError(f"Invalid port: {port} (must be 1-65535)")
    return port


# ---------------------------------------------------------------------------
#  Network diagnostics - ping_host
# ---------------------------------------------------------------------------

def ping_host(host: str, count: int = 4, timeout: int = 2) -> Dict[str, Any]:
    """Ping *host* using the system ``ping`` command.

    Returns a dict with keys:
        host, alive, packets_sent, packets_received,
        packet_loss_pct, min_ms, avg_ms, max_ms
    """
    _validate_host(host)

    system = platform.system().lower()

    if system == "windows":
        cmd = ["ping", "-n", str(count), "-w", str(timeout * 1000), host]
    else:
        # Linux and macOS both accept -c / -W.
        cmd = ["ping", "-c", str(count), "-W", str(timeout), host]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=count * (timeout + 1) + 5,
        )
        output = proc.stdout + proc.stderr
    except FileNotFoundError:
        raise RuntimeError("ping command not found on this system")
    except subprocess.TimeoutExpired:
        return {
            "host": host,
            "alive": False,
            "packets_sent": count,
            "packets_received": 0,
            "packet_loss_pct": 100.0,
            "min_ms": None,
            "avg_ms": None,
            "max_ms": None,
        }

    # -- parse packet stats ------------------------------------------------
    # Linux : "4 packets transmitted, 4 received, 0% packet loss, ..."
    # macOS : "4 packets transmitted, 4 packets received, 0.0% packet loss"
    pkt_match = re.search(
        r'(\d+)\s+packets?\s+transmitted.*?'
        r'(\d+)\s+(?:packets?\s+)?received.*?'
        r'([\d.]+)%\s+packet\s+loss',
        output,
        re.DOTALL,
    )
    if not pkt_match and system == "windows":
        pkt_match = re.search(
            r'Sent\s*=\s*(\d+).*?Received\s*=\s*(\d+).*?'
            r'\(([\d.]+)%\s*loss\)',
            output,
            re.IGNORECASE | re.DOTALL,
        )
    packets_sent = int(pkt_match.group(1)) if pkt_match else count
    packets_received = (
        int(pkt_match.group(2)) if pkt_match else (count if proc.returncode == 0 else 0)
    )
    packet_loss_pct = (
        float(pkt_match.group(3)) if pkt_match else (0.0 if proc.returncode == 0 else 100.0)
    )

    # -- parse RTT stats ---------------------------------------------------
    # Linux : "rtt min/avg/max/mdev = 0.028/0.042/0.068/0.015 ms"
    # macOS : "round-trip min/avg/max/stddev = 12.063/13.511/14.959/1.448 ms"
    rtt_match = re.search(
        r'(?:rtt|round-trip)\s+min/avg/max/(?:mdev|stddev)\s*=\s*'
        r'([\d.]+)/([\d.]+)/([\d.]+)',
        output,
    )
    min_ms: Optional[float]
    avg_ms: Optional[float]
    max_ms: Optional[float]
    if rtt_match:
        min_ms = float(rtt_match.group(1))
        avg_ms = float(rtt_match.group(2))
        max_ms = float(rtt_match.group(3))
    else:
        windows_rtt = re.search(
            r'Minimum\s*=\s*([\d.]+)ms.*?Maximum\s*=\s*([\d.]+)ms.*?'
            r'Average\s*=\s*([\d.]+)ms',
            output,
            re.IGNORECASE | re.DOTALL,
        )
        min_ms = float(windows_rtt.group(1)) if windows_rtt else None
        max_ms = float(windows_rtt.group(2)) if windows_rtt else None
        avg_ms = float(windows_rtt.group(3)) if windows_rtt else None

    return {
        "host": host,
        "alive": packets_received > 0,
        "packets_sent": packets_sent,
        "packets_received": packets_received,
        "packet_loss_pct": packet_loss_pct,
        "min_ms": min_ms,
        "avg_ms": avg_ms,
        "max_ms": max_ms,
    }


# ---------------------------------------------------------------------------
#  Network diagnostics - tcp_port_check
# ---------------------------------------------------------------------------

def tcp_port_check(
    host: str,
    ports: List[int],
    timeout: float = 1.0,
) -> List[Dict[str, Any]]:
    """Perform a TCP connect check against each port in *ports*.

    Returns a list of dicts (one per port) with keys:
        port, state ("open" / "closed" / "filtered"), service
    """
    _validate_host(host)
    for p in ports:
        _validate_port(p)

    results: List[Dict[str, Any]] = []

    for port in ports:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        try:
            sock.connect((host, port))
            state = "open"
        except socket.timeout:
            state = "filtered"
        except ConnectionRefusedError:
            state = "closed"
        except OSError:
            state = "filtered"
        finally:
            sock.close()

        try:
            service = socket.getservbyport(port, "tcp")
        except OSError:
            service = "unknown"

        results.append({"port": port, "state": state, "service": service})

    return results


# ---------------------------------------------------------------------------
#  Network diagnostics - traceroute
# ---------------------------------------------------------------------------

def traceroute(
    host: str,
    max_hops: int = 30,
    timeout: int = 2,
) -> List[Dict[str, Any]]:
    """Run a traceroute to *host* using the system command.

    Returns a list of dicts with keys: hop, ip, hostname, rtt_ms.
    Hops that time out are returned with ip/hostname/rtt_ms set to None.
    """
    _validate_host(host)

    system = platform.system().lower()

    if system == "windows":
        cmd = [
            "tracert", "-h", str(max_hops),
            "-w", str(timeout * 1000), host,
        ]
    else:
        cmd = [
            "traceroute", "-m", str(max_hops),
            "-w", str(timeout), host,
        ]

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=max_hops * (timeout + 1) + 10,
        )
        output = proc.stdout
    except FileNotFoundError:
        raise RuntimeError(
            "traceroute command not found. Install it with: "
            "apt install traceroute (Debian/Ubuntu) "
            "or brew install traceroute (macOS)"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError("traceroute timed out")

    hops: List[Dict[str, Any]] = []

    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue

        # Skip header/footer lines.
        if line.lower().startswith(("traceroute to", "tracing route")):
            continue
        if line.lower().startswith("trace complete"):
            continue

        tokens = line.split()
        if not tokens or not tokens[0].isdigit():
            continue

        hop_num = int(tokens[0])

        # Timeout line: "3  * * *"
        if re.fullmatch(r'\d+\s+(\*\s*)+', line):
            hops.append({
                "hop": hop_num,
                "ip": None,
                "hostname": None,
                "rtt_ms": None,
            })
            continue

        # Extract first IP in parentheses, e.g. "(192.168.1.1)".
        ip_match = re.search(r'\((\d{1,3}(?:\.\d{1,3}){3})\)', line)
        if not ip_match:
            ip_match = re.search(r'(\d{1,3}(?:\.\d{1,3}){3})', line)

        ip_addr = ip_match.group(1) if ip_match else None

        # Hostname: second token on Unix, or the name before [IP] on Windows.
        hostname = None
        if ip_addr:
            named_match = re.search(
                rf'([A-Za-z0-9_.-]+)\s+[\[(]{re.escape(ip_addr)}[\])]', line
            )
            if named_match:
                hostname = named_match.group(1)
        if len(tokens) > 1:
            candidate = tokens[1]
            if (
                hostname is None
                and not re.match(r'^\d{1,3}(\.\d{1,3}){3}$', candidate)
                and not re.match(r'^[\d.]+$', candidate)
                and not candidate.startswith('(')
                and not candidate.startswith('<')
                and candidate.lower() != 'ms'
            ):
                hostname = candidate
            elif hostname is None and ip_addr:
                hostname = ip_addr

        if hostname is None and ip_addr:
            hostname = ip_addr

        # First RTT value.
        rtt_match = re.search(r'([\d.]+)\s*ms', line)
        rtt_ms = float(rtt_match.group(1)) if rtt_match else None

        hops.append({
            "hop": hop_num,
            "ip": ip_addr,
            "hostname": hostname,
            "rtt_ms": rtt_ms,
        })

    return hops


# ---------------------------------------------------------------------------
#  Network diagnostics - whois_lookup
# ---------------------------------------------------------------------------

def whois_lookup(target: str) -> str:
    """Run a WHOIS query for *target* (IP address or domain name).

    Returns the raw WHOIS output as a string.
    Raises RuntimeError if the ``whois`` command is not installed.
    """
    _validate_host(target)

    try:
        proc = subprocess.run(
            ["whois", target],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        raise RuntimeError(
            "whois command not found. Install it with: "
            "apt install whois (Debian/Ubuntu) "
            "or brew install whois (macOS)"
        )
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"whois lookup for '{target}' timed out")

    output = proc.stdout.strip()
    if proc.returncode != 0 and not output:
        raise RuntimeError(f"whois failed: {proc.stderr.strip()}")

    return output


# ---------------------------------------------------------------------------
#  Advanced ping / ARP / reverse DNS sweep
# ---------------------------------------------------------------------------

def ping_sweep(network: str, timeout: int = 1, max_threads: int = 50) -> List[Dict[str, Any]]:
    net = ipaddress.ip_network(network, strict=False)
    if net.num_addresses > MAX_NETWORK_HOSTS + 2:
        raise ValueError(
            f"Network contains too many addresses ({net.num_addresses}); "
            f"maximum is {MAX_NETWORK_HOSTS + 2}"
        )
    hosts = [str(ip) for ip in net.hosts()]

    def _ping_one(ip):
        system = platform.system().lower()
        if system == "windows":
            cmd = ["ping", "-n", "1", "-w", str(timeout * 1000), ip]
        else:
            cmd = ["ping", "-c", "1", "-W", str(timeout), ip]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 2)
            alive = result.returncode == 0
            rtt_ms = None
            if alive:
                match = re.search(r"time[=<]\s*([\d.]+)\s*ms", result.stdout)
                if match:
                    rtt_ms = float(match.group(1))
            return {"ip": ip, "alive": alive, "rtt_ms": rtt_ms}
        except (subprocess.TimeoutExpired, OSError):
            return {"ip": ip, "alive": False, "rtt_ms": None}

    with ThreadPoolExecutor(max_workers=max_threads) as pool:
        results = list(pool.map(_ping_one, hosts))
    results.sort(key=lambda r: (not r["alive"], ipaddress.ip_address(r["ip"])))
    return results


def arp_scan() -> List[Dict[str, Any]]:
    system = platform.system().lower()
    entries: List[Dict[str, Any]] = []
    if system == "linux":
        try:
            with open("/proc/net/arp", "r") as f:
                lines = f.readlines()
        except OSError:
            return entries
        for line in lines[1:]:
            parts = line.split()
            if len(parts) < 6:
                continue
            mac = parts[3]
            state = "reachable" if parts[2] != "0x0" and mac != "00:00:00:00:00:00" else "incomplete"
            entries.append({"ip": parts[0], "mac": mac, "interface": parts[5], "state": state})
    elif system == "darwin":
        try:
            result = subprocess.run(["arp", "-a"], capture_output=True, text=True, timeout=10)
        except (subprocess.TimeoutExpired, OSError):
            return entries
        pattern = re.compile(r"\S+\s+\(([\d.]+)\)\s+at\s+([\da-fA-F:]+|\(incomplete\))\s+on\s+(\S+)")
        for line in result.stdout.splitlines():
            match = pattern.search(line)
            if not match:
                continue
            mac_raw = match.group(2).strip()
            if mac_raw == "(incomplete)":
                entries.append({"ip": match.group(1), "mac": "00:00:00:00:00:00", "interface": match.group(3), "state": "incomplete"})
            else:
                entries.append({"ip": match.group(1), "mac": mac_raw, "interface": match.group(3), "state": "reachable"})
    elif system == "windows":
        try:
            result = subprocess.run(
                ["arp", "-a"], capture_output=True, text=True, timeout=10
            )
        except (subprocess.TimeoutExpired, OSError):
            return entries
        interface = "unknown"
        header_pattern = re.compile(r"Interface:\s+([\d.]+)", re.IGNORECASE)
        entry_pattern = re.compile(
            r"^\s*(\d{1,3}(?:\.\d{1,3}){3})\s+"
            r"([0-9a-fA-F]{2}(?:-[0-9a-fA-F]{2}){5})\s+(\S+)"
        )
        for line in result.stdout.splitlines():
            header = header_pattern.search(line)
            if header:
                interface = header.group(1)
                continue
            match = entry_pattern.match(line)
            if match:
                entries.append({
                    "ip": match.group(1),
                    "mac": match.group(2).replace("-", ":").lower(),
                    "interface": interface,
                    "state": match.group(3).lower(),
                })
    return entries


def _optional_command(command: List[str], timeout: int = 10) -> Dict[str, Any]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return {"ok": False, "error": f"command not found: {command[0]}", "stdout": ""}
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"command timed out: {command[0]}", "stdout": ""}
    return {
        "ok": result.returncode == 0,
        "error": result.stderr.strip() if result.returncode else None,
        "stdout": result.stdout,
    }


def _resolver_addresses() -> List[str]:
    path = Path("/etc/resolv.conf")
    if not path.is_file():
        return []
    try:
        values = []
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            match = re.match(r"\s*nameserver\s+(\S+)", line)
            if match and match.group(1) not in values:
                values.append(match.group(1))
        return values
    except OSError:
        return []


def local_network_inventory() -> Dict[str, Any]:
    """Return a best-effort, cross-platform snapshot of local network state."""
    system = platform.system().lower()
    hostname = socket.gethostname()
    result: Dict[str, Any] = {
        "hostname": hostname,
        "fqdn": socket.getfqdn(),
        "platform": platform.platform(),
        "interfaces": [],
        "routes": [],
        "dns_servers": _resolver_addresses() if system != "windows" else [],
        "errors": [],
    }
    if system == "linux":
        addresses = _optional_command(["ip", "-j", "address", "show"])
        if addresses["ok"]:
            try:
                for interface in json.loads(addresses["stdout"]):
                    result["interfaces"].append({
                        "name": interface.get("ifname"),
                        "state": interface.get("operstate"),
                        "mtu": interface.get("mtu"),
                        "mac": interface.get("address"),
                        "addresses": [
                            {
                                "family": item.get("family"),
                                "address": item.get("local"),
                                "prefix_length": item.get("prefixlen"),
                                "scope": item.get("scope"),
                            }
                            for item in interface.get("addr_info", [])
                        ],
                    })
            except (json.JSONDecodeError, TypeError) as exc:
                result["errors"].append(f"cannot parse ip address output: {exc}")
        else:
            result["errors"].append(addresses["error"])
        routes = _optional_command(["ip", "-j", "route", "show"])
        if routes["ok"]:
            try:
                result["routes"] = [
                    {
                        "destination": route.get("dst", "default"),
                        "gateway": route.get("gateway"),
                        "interface": route.get("dev"),
                        "source": route.get("prefsrc"),
                        "metric": route.get("metric"),
                    }
                    for route in json.loads(routes["stdout"])
                ]
            except (json.JSONDecodeError, TypeError) as exc:
                result["errors"].append(f"cannot parse ip route output: {exc}")
        else:
            result["errors"].append(routes["error"])
    elif system == "darwin":
        interfaces = _optional_command(["ifconfig"])
        current: Optional[Dict[str, Any]] = None
        if interfaces["ok"]:
            for line in interfaces["stdout"].splitlines():
                header = re.match(r"^(\S+):\s+flags=.*mtu\s+(\d+)", line)
                if header:
                    current = {"name": header.group(1), "mtu": int(header.group(2)), "addresses": []}
                    result["interfaces"].append(current)
                    continue
                if current is None:
                    continue
                mac = re.match(r"\s*ether\s+(\S+)", line)
                address = re.match(r"\s*inet6?\s+(\S+)", line)
                if mac:
                    current["mac"] = mac.group(1)
                elif address:
                    value = address.group(1).split("%", 1)[0]
                    current["addresses"].append({
                        "family": "inet6" if ":" in value else "inet",
                        "address": value,
                    })
        else:
            result["errors"].append(interfaces["error"])
        route = _optional_command(["route", "-n", "get", "default"])
        if route["ok"]:
            gateway = re.search(r"^\s*gateway:\s+(\S+)", route["stdout"], re.MULTILINE)
            interface = re.search(r"^\s*interface:\s+(\S+)", route["stdout"], re.MULTILINE)
            result["routes"].append({
                "destination": "default",
                "gateway": gateway.group(1) if gateway else None,
                "interface": interface.group(1) if interface else None,
            })
    elif system == "windows":
        configuration = _optional_command(["ipconfig", "/all"])
        current = None
        if configuration["ok"]:
            for line in configuration["stdout"].splitlines():
                header = re.match(r"^([^\s].*adapter\s+.+):\s*$", line, re.IGNORECASE)
                if header:
                    current = {"name": header.group(1).strip(), "addresses": []}
                    result["interfaces"].append(current)
                    continue
                if current is None:
                    continue
                mac = re.search(r"Physical Address[^:]*:\s*([0-9A-Fa-f-]{17})", line)
                address = re.search(r"IPv[46] Address[^:]*:\s*([^\s(]+)", line)
                gateway = re.search(r"Default Gateway[^:]*:\s*(\S+)", line)
                dns = re.search(r"DNS Servers[^:]*:\s*(\S+)", line)
                if mac:
                    current["mac"] = mac.group(1).replace("-", ":").lower()
                elif address:
                    value = address.group(1).split("%", 1)[0]
                    current["addresses"].append({"family": "inet6" if ":" in value else "inet", "address": value})
                if gateway:
                    result["routes"].append({"destination": "default", "gateway": gateway.group(1), "interface": current["name"]})
                if dns and dns.group(1) not in result["dns_servers"]:
                    result["dns_servers"].append(dns.group(1))
        else:
            result["errors"].append(configuration["error"])
    else:
        result["errors"].append(f"unsupported platform: {system}")

    result["interface_count"] = len(result["interfaces"])
    result["default_routes"] = [route for route in result["routes"] if route.get("destination") == "default"]
    return result


# ---------------------------------------------------------------------------
#  Read-only system and service diagnostics
# ---------------------------------------------------------------------------

DIAGNOSTIC_MAX_OUTPUT = 2 * 1024 * 1024
DIAGNOSTIC_MAX_LOG_LINES = 500


def _diagnostic_command(
    command: List[str],
    timeout: float = 10.0,
    max_output: int = DIAGNOSTIC_MAX_OUTPUT,
) -> Dict[str, Any]:
    """Run a read-only diagnostic command with bounded captured output."""
    if timeout <= 0:
        raise ValueError("Timeout must be greater than zero")
    started = time.monotonic()
    environment = dict(os.environ)
    environment.setdefault("LC_ALL", "C")
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            env=environment,
        )
    except FileNotFoundError:
        return {
            "available": False,
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "error": f"command not found: {command[0]}",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        }
    except OSError as exc:
        return {
            "available": True,
            "ok": False,
            "returncode": None,
            "stdout": "",
            "stderr": "",
            "error": str(exc),
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "available": True,
            "ok": False,
            "returncode": None,
            "stdout": (exc.stdout or "")[-max_output:] if isinstance(exc.stdout, str) else "",
            "stderr": (exc.stderr or "")[-max_output:] if isinstance(exc.stderr, str) else "",
            "error": f"command timed out after {timeout:g} seconds",
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        }
    stdout = process.stdout
    stderr = process.stderr
    truncated = len(stdout) > max_output or len(stderr) > max_output
    if len(stdout) > max_output:
        stdout = stdout[-max_output:]
    if len(stderr) > max_output:
        stderr = stderr[-max_output:]
    return {
        "available": True,
        "ok": process.returncode == 0,
        "returncode": process.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "error": stderr.strip() if process.returncode else None,
        "truncated": truncated,
        "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
    }


def _finding(
    code: str,
    severity: str,
    summary: str,
    evidence: Optional[str] = None,
    recommendation: Optional[str] = None,
    phase: Optional[str] = None,
) -> Dict[str, Any]:
    item: Dict[str, Any] = {
        "code": code,
        "severity": severity,
        "summary": summary,
    }
    if evidence:
        item["evidence"] = evidence
    if recommendation:
        item["recommendation"] = recommendation
    if phase:
        item["phase"] = phase
    return item


def _diagnostic_step(
    step_id: str,
    title: str,
    status: str,
    summary: str,
    layer: Optional[str] = None,
    depends_on: Optional[List[str]] = None,
    evidence: Optional[Any] = None,
) -> Dict[str, Any]:
    """Build one explicit, machine-readable troubleshooting step."""
    if status not in {"passed", "warning", "failed", "skipped", "not_applicable"}:
        raise ValueError(f"Invalid diagnostic step status: {status}")
    step: Dict[str, Any] = {
        "id": step_id,
        "title": title,
        "status": status,
        "summary": summary,
    }
    if layer:
        step["layer"] = layer
    if depends_on:
        step["depends_on"] = depends_on
    if evidence is not None and evidence != "" and evidence != []:
        step["evidence"] = evidence
    return step


def _methodology(name: str, strategy: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Describe the ordered diagnostic method separately from raw observations."""
    return {
        "name": name,
        "version": 1,
        "strategy": strategy,
        "steps": steps,
    }


def _rank_cause_candidates(findings: List[Dict[str, Any]], limit: int = 10) -> List[Dict[str, Any]]:
    """Rank observations as hypotheses without claiming unproven root cause."""
    severity_rank = {"critical": 0, "warning": 1, "info": 2}
    ordered = sorted(
        enumerate(_deduplicate_findings(findings)),
        key=lambda item: (severity_rank.get(str(item[1].get("severity")), 3), item[0]),
    )
    result = []
    for _index, finding in ordered[:limit]:
        severity = finding.get("severity")
        confidence = (
            "high" if severity == "critical" and finding.get("evidence") else
            "medium" if severity in {"critical", "warning"} else "low"
        )
        candidate = {
            "code": finding.get("code"),
            "priority": severity,
            "hypothesis": finding.get("summary"),
            "confidence": confidence,
        }
        for key in ("phase", "evidence", "recommendation"):
            if finding.get(key):
                candidate[key] = finding[key]
        result.append(candidate)
    return result


def _validate_diagnostic_context(value: Optional[str], label: str) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    if len(cleaned) > 500 or any(ord(char) < 32 and char not in "\t" for char in cleaned):
        raise ValueError(f"Invalid {label}; use at most 500 printable characters")
    return cleaned


def _diagnostic_context(
    target: str,
    symptom: Optional[str] = None,
    expected: Optional[str] = None,
    recent_change: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "target": target,
        "symptom": _validate_diagnostic_context(symptom, "symptom"),
        "expected": _validate_diagnostic_context(expected, "expected behavior"),
        "recent_change": _validate_diagnostic_context(recent_change, "recent change"),
    }


def _has_operator_context(context: Dict[str, Any]) -> bool:
    """Return whether the operator supplied useful diagnostic context."""
    return any(context.get(key) for key in ("symptom", "expected", "recent_change"))


def _deduplicate_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result = []
    seen = set()
    for finding in findings:
        key = (finding.get("code"), finding.get("summary"), finding.get("evidence"))
        if key not in seen:
            seen.add(key)
            result.append(finding)
    return result


def _diagnostic_status(findings: List[Dict[str, Any]]) -> str:
    severities = {finding.get("severity") for finding in findings}
    if "critical" in severities:
        return "failed"
    if "warning" in severities:
        return "warning"
    return "ok"


def _redact_log_line(line: str) -> str:
    redacted = re.sub(
        r"(?i)\b(authorization|proxy-authorization|cookie|set-cookie)\s*:\s*[^\r\n]+",
        r"\1: [REDACTED]",
        line,
    )
    redacted = re.sub(
        r"(?i)([?&](?:access_?token|api_?key|auth|code|credential|jwt|password|secret|session|signature|token)=)[^&\s\"']+",
        r"\1[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)(\b(?:access_?token|api_?key|auth|credential|jwt|password|secret|session|signature|token)\s*=\s*)[^&\s\"']+",
        r"\1[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"(?i)(--(?:access-?token|api-?key|auth|credential|jwt|password|secret|session|signature|token)\s+)[^\s\"']+",
        r"\1[REDACTED]",
        redacted,
    )
    redacted = re.sub(
        r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b",
        "[REDACTED_JWT]",
        redacted,
    )
    return redacted


def _redact_url(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
        hostname = parsed.hostname or ""
        if ":" in hostname and not hostname.startswith("["):
            hostname = f"[{hostname}]"
        if parsed.port:
            hostname = f"{hostname}:{parsed.port}"
        if parsed.username is not None or parsed.password is not None:
            hostname = f"[REDACTED]@{hostname}"
        query = _redact_log_line(f"?{parsed.query}")[1:] if parsed.query else ""
        return urllib.parse.urlunsplit((parsed.scheme, hostname, parsed.path, query, parsed.fragment))
    except ValueError:
        return _redact_log_line(value)


def _validate_log_options(lines: int, since: str) -> None:
    if not 1 <= lines <= DIAGNOSTIC_MAX_LOG_LINES:
        raise ValueError(
            f"Log line count must be between 1 and {DIAGNOSTIC_MAX_LOG_LINES}"
        )
    if not since or len(since) > 80 or any(ord(char) < 32 for char in since):
        raise ValueError("Invalid journal time range")


def _tail_log_file(
    path: str,
    lines: int = 50,
    include_content: bool = False,
    raw: bool = False,
) -> Dict[str, Any]:
    candidate = Path(path).expanduser()
    result: Dict[str, Any] = {"path": str(candidate), "exists": candidate.is_file()}
    if not candidate.is_file():
        return result
    try:
        details = candidate.stat()
        result.update({
            "size_bytes": details.st_size,
            "modified_at": datetime.fromtimestamp(
                details.st_mtime, timezone.utc
            ).isoformat(),
            "readable": os.access(candidate, os.R_OK),
        })
        if not include_content:
            return result
        read_size = min(details.st_size, max(65536, lines * 4096), DIAGNOSTIC_MAX_OUTPUT)
        with candidate.open("rb") as handle:
            if details.st_size > read_size:
                handle.seek(-read_size, os.SEEK_END)
            data = handle.read(read_size)
        decoded = data.decode("utf-8", errors="replace")
        selected = decoded.splitlines()[-lines:]
        result["lines"] = selected if raw else [_redact_log_line(line) for line in selected]
        result["truncated"] = details.st_size > read_size
    except OSError as exc:
        result.update({"readable": False, "error": str(exc)})
    return result


def _mount_details(path: Path) -> Optional[Dict[str, Any]]:
    mounts = Path("/proc/self/mounts")
    if not mounts.is_file():
        return None
    try:
        resolved = str(path.resolve())
        matches = []
        for line in mounts.read_text(encoding="utf-8", errors="replace").splitlines():
            fields = line.split()
            if len(fields) < 4:
                continue
            mountpoint = fields[1].replace("\\040", " ")
            if resolved == mountpoint or resolved.startswith(mountpoint.rstrip("/") + "/"):
                matches.append((len(mountpoint), fields[0], mountpoint, fields[2], fields[3]))
        if not matches:
            return None
        _, device, mountpoint, filesystem, options = max(matches)
        return {
            "device": device,
            "mountpoint": mountpoint,
            "filesystem": filesystem,
            "options": options.split(","),
            "read_only": "ro" in options.split(","),
        }
    except OSError:
        return None


def disk_diagnostic(
    path: str = "/",
    include_du: bool = False,
    timeout: float = 30.0,
    warning_percent: float = 85.0,
    critical_percent: float = 95.0,
    symptom: Optional[str] = None,
    expected: Optional[str] = None,
    recent_change: Optional[str] = None,
) -> Dict[str, Any]:
    """Inspect capacity, inodes, mount state, and optional top-level usage."""
    if not 0 < warning_percent < critical_percent <= 100:
        raise ValueError("Disk thresholds must satisfy 0 < warning < critical <= 100")
    candidate = Path(path).expanduser()
    context = _diagnostic_context(str(candidate), symptom, expected, recent_change)
    if not candidate.exists():
        finding = _finding(
            "path_missing", "critical", f"Path does not exist: {candidate}",
            recommendation="Check the mount point or path supplied to the diagnostic.",
            phase="target",
        )
        steps = [
            _diagnostic_step(
                "context", "Define the capacity symptom", "passed" if _has_operator_context(context) else "warning",
                "Operator context was recorded." if _has_operator_context(context) else "No symptom, expectation, or recent change was supplied.",
            ),
            _diagnostic_step(
                "target", "Resolve target path", "failed", "The requested path does not exist.",
                depends_on=["context"], evidence=str(candidate),
            ),
        ]
        return {
            "path": str(candidate), "status": "failed", "read_only": True,
            "context": context,
            "methodology": _methodology(
                "filesystem-capacity", "Resolve the target, then check capacity, inodes, mount state, and bounded growth.", steps,
            ),
            "cause_candidates": _rank_cause_candidates([finding]),
            "findings": [finding],
        }
    measured = candidate if candidate.is_dir() else candidate.parent
    usage = shutil.disk_usage(measured)
    used_percent = round((usage.used / usage.total) * 100, 2) if usage.total else 0.0
    inode_total = None
    inode_free = None
    inode_used_percent = None
    try:
        filesystem = os.statvfs(measured)
        if filesystem.f_files:
            inode_total = filesystem.f_files
            inode_free = filesystem.f_ffree
            inode_used_percent = round(
                ((inode_total - inode_free) / inode_total) * 100, 2
            )
    except (AttributeError, OSError):
        pass
    findings = []
    for metric, percent in (("disk", used_percent), ("inode", inode_used_percent)):
        if percent is None:
            continue
        if percent >= critical_percent:
            findings.append(_finding(
                f"{metric}_critical", "critical",
                f"{metric.capitalize()} usage is critically high ({percent}%).",
                recommendation="Free space or inodes, rotate logs, and identify growth before restarting services.",
                phase="capacity" if metric == "disk" else "inodes",
            ))
        elif percent >= warning_percent:
            findings.append(_finding(
                f"{metric}_warning", "warning",
                f"{metric.capitalize()} usage is high ({percent}%).",
                recommendation="Review growth and available capacity before the filesystem becomes full.",
                phase="capacity" if metric == "disk" else "inodes",
            ))
    mount = _mount_details(measured)
    if mount and mount.get("read_only"):
        findings.append(_finding(
            "filesystem_read_only", "critical",
            f"Filesystem mounted at {mount['mountpoint']} is read-only.",
            recommendation="Inspect kernel and storage errors before attempting a remount.",
            phase="mount",
        ))
    largest = []
    du_error = None
    if include_du:
        command = ["du", "-x", "-k", "-d", "1", str(measured.resolve())]
        du = _diagnostic_command(command, timeout=timeout)
        if du["ok"]:
            rows = []
            for line in du["stdout"].splitlines():
                match = re.match(r"^(\d+)\s+(.+)$", line)
                if match and Path(match.group(2)) != measured:
                    rows.append({"path": match.group(2), "size_bytes": int(match.group(1)) * 1024})
            largest = sorted(rows, key=lambda row: row["size_bytes"], reverse=True)[:20]
        else:
            du_error = du.get("error") or "du failed"
            findings.append(_finding(
                "du_unavailable", "warning", "Top-level usage could not be collected.",
                evidence=du_error,
                recommendation="Run the same diagnostic with sufficient read permissions or inspect the path manually.",
                phase="growth",
            ))
    findings = _deduplicate_findings(findings)
    capacity_findings = [item for item in findings if item.get("phase") == "capacity"]
    inode_findings = [item for item in findings if item.get("phase") == "inodes"]
    mount_findings = [item for item in findings if item.get("phase") == "mount"]
    growth_findings = [item for item in findings if item.get("phase") == "growth"]
    steps = [
        _diagnostic_step(
            "context", "Define the capacity symptom", "passed" if _has_operator_context(context) else "warning",
            "Operator context was recorded." if _has_operator_context(context) else "No symptom, expectation, or recent change was supplied.",
        ),
        _diagnostic_step(
            "target", "Resolve target path", "passed", f"Resolved target path: {measured}", depends_on=["context"],
        ),
        _diagnostic_step(
            "capacity", "Check filesystem capacity",
            "failed" if any(item["severity"] == "critical" for item in capacity_findings) else "warning" if capacity_findings else "passed",
            f"Filesystem usage is {used_percent}%.", depends_on=["target"],
        ),
        _diagnostic_step(
            "inodes", "Check inode capacity",
            "failed" if any(item["severity"] == "critical" for item in inode_findings) else "warning" if inode_findings else "passed",
            "Inode accounting is unavailable on this platform." if inode_used_percent is None else f"Inode usage is {inode_used_percent}%.",
            depends_on=["target"],
        ),
        _diagnostic_step(
            "mount", "Check mount state",
            "failed" if mount_findings else "passed" if mount else "not_applicable",
            "The filesystem is mounted read-only." if mount_findings else "The mount is writable." if mount else "Mount metadata is unavailable.",
            depends_on=["target"],
        ),
        _diagnostic_step(
            "growth", "Inspect top-level growth",
            "warning" if growth_findings else "passed" if include_du else "skipped",
            "A bounded top-level usage scan was collected." if include_du and not growth_findings else
            "The usage scan failed." if growth_findings else "Enable --du when a capacity problem needs attribution.",
            depends_on=["capacity"],
        ),
    ]
    return {
        "path": str(candidate),
        "measured_path": str(measured),
        "status": _diagnostic_status(findings),
        "read_only": True,
        "context": context,
        "methodology": _methodology(
            "filesystem-capacity", "Resolve the target, then check capacity, inodes, mount state, and bounded growth.", steps,
        ),
        "capacity": {
            "total_bytes": usage.total,
            "used_bytes": usage.used,
            "free_bytes": usage.free,
            "used_percent": used_percent,
        },
        "inodes": {
            "total": inode_total,
            "free": inode_free,
            "used_percent": inode_used_percent,
        },
        "mount": mount,
        "writable_by_current_user": os.access(measured, os.W_OK),
        "largest_entries": largest,
        "du_error": du_error,
        "cause_candidates": _rank_cause_candidates(findings),
        "findings": findings,
    }


def _process_matches(name: str, timeout: float = 5.0) -> List[Dict[str, Any]]:
    process_name = name.removesuffix(".service")
    _validate_config_name(process_name, "process name", max_length=128)
    command = _diagnostic_command(["pgrep", "-a", "-x", process_name], timeout=timeout)
    matches = []
    if command["ok"]:
        for line in command["stdout"].splitlines():
            pid, _, arguments = line.strip().partition(" ")
            if pid.isdigit():
                matches.append({"pid": int(pid), "command": _redact_log_line(arguments)})
    return matches


def _service_manager() -> str:
    system = platform.system().lower()
    if system == "linux":
        if shutil.which("systemctl"):
            return "systemd"
        if shutil.which("rc-service"):
            return "openrc"
        if shutil.which("service"):
            return "sysv"
    elif system == "darwin":
        return "launchd"
    elif system == "windows":
        return "windows-scm"
    return "unknown"


def service_diagnostic(
    name: str,
    include_logs: bool = False,
    lines: int = 50,
    since: str = "1 hour ago",
    raw_logs: bool = False,
    timeout: float = 10.0,
    symptom: Optional[str] = None,
    expected: Optional[str] = None,
    recent_change: Optional[str] = None,
    port: Optional[int] = None,
) -> Dict[str, Any]:
    """Inspect a service without starting, stopping, or reloading it."""
    _validate_config_name(name.removesuffix(".service"), "service name", max_length=128)
    _validate_log_options(lines, since)
    context = _diagnostic_context(name, symptom, expected, recent_change)
    manager = _service_manager()
    details: Dict[str, Any] = {}
    manager_findings = []
    journal: List[str] = []
    log_source = None
    manager_status = "not_applicable"
    manager_summary = f"No supported service manager was detected for {name}."
    if manager == "systemd":
        properties = (
            "LoadState,ActiveState,SubState,UnitFileState,Result,ExecMainStatus,"
            "FragmentPath,User,Group,MainPID,NRestarts,MemoryCurrent,TasksCurrent"
        )
        command = _diagnostic_command(
            ["systemctl", "show", name, "--no-pager", f"--property={properties}"],
            timeout=timeout,
        )
        for line in command["stdout"].splitlines():
            key, separator, value = line.partition("=")
            if separator:
                details[key] = value or None
        load_state = details.get("LoadState")
        active_state = details.get("ActiveState")
        if not command["ok"] and not details:
            manager_status = "failed"
            manager_summary = f"systemd could not query {name}."
            manager_findings.append(_finding(
                "service_query_failed", "critical", f"Service state for '{name}' could not be queried.",
                evidence=command.get("error"),
                recommendation="Check service-manager availability, permissions, and whether the host booted with systemd.",
                phase="service_manager",
            ))
        elif load_state == "not-found":
            manager_status = "failed"
            manager_summary = f"systemd does not define {name}."
            manager_findings.append(_finding(
                "service_not_found", "critical", f"Service unit '{name}' was not found.",
                recommendation="Confirm the package, unit name, and installation path.",
                phase="service_manager",
            ))
        elif active_state != "active":
            manager_status = "failed"
            manager_summary = f"systemd reports {name} as {active_state or 'inactive'}."
            manager_findings.append(_finding(
                "service_inactive", "critical", f"Service '{name}' is not active.",
                evidence=f"ActiveState={active_state}, SubState={details.get('SubState')}, Result={details.get('Result')}",
                recommendation="Review configuration and service logs before attempting a restart.",
                phase="service_manager",
            ))
        else:
            manager_status = "passed"
            manager_summary = f"systemd reports {name} as active ({details.get('SubState') or 'running'})."
        if details.get("ExecMainStatus") not in {None, "", "0"}:
            manager_findings.append(_finding(
                "service_exit_status", "warning",
                f"The last main process exit status was {details['ExecMainStatus']}.",
                recommendation="Correlate the exit code with the unit journal and application logs.",
                phase="service_manager",
            ))
        if include_logs:
            log_source = "journalctl"
            log_command = _diagnostic_command(
                [
                    "journalctl", "--no-pager", "-u", name,
                    "--since", since, "-n", str(lines), "-o", "short-iso",
                ],
                timeout=timeout,
            )
            selected = log_command["stdout"].splitlines()[-lines:]
            journal = selected if raw_logs else [_redact_log_line(line) for line in selected]
            if not log_command["ok"] and log_command.get("error"):
                manager_findings.append(_finding(
                    "service_logs_unavailable", "warning", "Service journal could not be read.",
                    evidence=log_command["error"],
                    recommendation="Check journal access for the current user.",
                    phase="logs",
                ))
    elif manager == "openrc":
        command = _diagnostic_command(["rc-service", name, "status"], timeout=timeout)
        details = {"output": _redact_log_line((command["stdout"] + command["stderr"]).strip())}
        if not command["ok"]:
            manager_status = "failed"
            manager_summary = f"OpenRC does not report {name} as running."
            manager_findings.append(_finding(
                "service_inactive", "critical", f"OpenRC reports '{name}' as unavailable or stopped.",
                evidence=details["output"],
                recommendation="Review the application configuration and OpenRC log destination.",
                phase="service_manager",
            ))
        else:
            manager_status = "passed"
            manager_summary = f"OpenRC reports {name} as running."
    elif manager == "sysv":
        command = _diagnostic_command(["service", name, "status"], timeout=timeout)
        details = {"output": _redact_log_line((command["stdout"] + command["stderr"]).strip())}
        if not command["ok"]:
            manager_status = "failed"
            manager_summary = f"SysV init does not report {name} as running."
            manager_findings.append(_finding(
                "service_inactive", "critical", f"Service '{name}' is unavailable or stopped.",
                evidence=details["output"],
                recommendation="Review the application configuration and service log destination.",
                phase="service_manager",
            ))
        else:
            manager_status = "passed"
            manager_summary = f"SysV init reports {name} as running."
    elif manager == "launchd":
        command = _diagnostic_command(["launchctl", "print", f"system/{name}"], timeout=timeout)
        details = {"output": _redact_log_line(command["stdout"][-8192:])}
        if not command["ok"]:
            manager_status = "failed"
            manager_summary = f"launchd does not report {name} as active."
            manager_findings.append(_finding(
                "service_inactive", "critical", f"launchd could not find an active '{name}' service.",
                recommendation="Confirm the launchd label and inspect its configured log paths.",
                phase="service_manager",
            ))
        else:
            manager_status = "passed"
            manager_summary = f"launchd reports {name} as active."
    elif manager == "windows-scm":
        command = _diagnostic_command(["sc", "query", name], timeout=timeout)
        details = {"output": _redact_log_line(command["stdout"][-8192:])}
        if not command["ok"] or "RUNNING" not in command["stdout"].upper():
            manager_status = "failed"
            manager_summary = f"Windows SCM does not report {name} as running."
            manager_findings.append(_finding(
                "service_inactive", "critical", f"Windows Service Control Manager does not report '{name}' as running.",
                evidence=_redact_log_line((command["stdout"] + command["stderr"]).strip()),
                recommendation="Confirm the service name and review the Windows Event Log.",
                phase="service_manager",
            ))
        else:
            manager_status = "passed"
            manager_summary = f"Windows SCM reports {name} as running."
    else:
        manager_status = "warning"
        manager_findings.append(_finding(
            "service_manager_unavailable", "warning", "No supported service manager was detected.",
            recommendation="Use the process list and application-specific diagnostics.",
            phase="service_manager",
        ))
    if include_logs and manager != "systemd":
        manager_findings.append(_finding(
            "service_log_source_unspecified", "info",
            f"Automatic service-log collection is not defined for {manager}.",
            recommendation="Use the log path configured by the application or the platform event-log viewer.",
            phase="logs",
        ))
    processes = _process_matches(name, timeout) if platform.system().lower() != "windows" else []
    findings = list(manager_findings)
    mismatch_codes = {"service_query_failed", "service_not_found", "service_inactive", "service_manager_unavailable"}
    if processes and any(item.get("code") in mismatch_codes for item in findings):
        findings = [item for item in findings if item.get("code") not in mismatch_codes]
        findings.append(_finding(
            "service_manager_process_mismatch", "warning",
            f"The service manager does not report '{name}' as active, but matching process(es) are running.",
            evidence=f"matching_processes={len(processes)}",
            recommendation="Determine whether the application is managed by another unit, container, supervisor, or standalone launcher before changing state.",
            phase="service_manager",
        ))
        manager_status = "warning"
        manager_summary = f"The manager state conflicts with {len(processes)} running process(es)."
    firewall = firewall_diagnostic([port], timeout=timeout) if port is not None else None
    if firewall:
        findings.extend(firewall["findings"])
    findings = _deduplicate_findings(findings)
    manager_phase_findings = [item for item in findings if item.get("phase") == "service_manager"]
    log_findings = [item for item in findings if item.get("phase") == "logs"]
    if any(item.get("severity") == "critical" for item in manager_phase_findings):
        manager_status = "failed"
    elif any(item.get("severity") == "warning" for item in manager_phase_findings):
        manager_status = "warning"
    steps = [
        _diagnostic_step(
            "context", "Define the problem", "passed" if _has_operator_context(context) else "warning",
            "Operator context was recorded." if _has_operator_context(context) else
            "No symptom, expectation, or recent change was supplied; conclusions are limited to the current snapshot.",
        ),
        _diagnostic_step(
            "service_manager", "Query the service manager", manager_status, manager_summary,
            depends_on=["context"], evidence={"manager": manager, "state": details.get("ActiveState") or details.get("output")},
        ),
        _diagnostic_step(
            "process", "Correlate running processes",
            "passed" if processes or details.get("MainPID") not in {None, "", "0"} else
            "not_applicable" if platform.system().lower() == "windows" or manager_status == "passed" else "warning",
            f"Found {len(processes)} exact-name process(es)." if processes else
            f"The service manager reports main PID {details.get('MainPID')}." if details.get("MainPID") not in {None, "", "0"} else
            "Process correlation is unavailable on Windows." if platform.system().lower() == "windows" else
            "The manager already reports the service active; exact executable-name correlation is not required." if manager_status == "passed" else
            "No exact-name process was found; the executable name may differ from the service name.",
            depends_on=["service_manager"],
        ),
        _diagnostic_step(
            "firewall", "Correlate the service port with host firewall policy",
            "failed" if firewall and firewall.get("status") == "failed" else
            "warning" if firewall and firewall.get("status") == "warning" else
            "passed" if firewall else "skipped",
            f"Inspected inbound TCP port {port}." if firewall else
            "Supply --port to correlate this service with the host firewall.",
            layer="OSI 3-4", depends_on=["process"],
        ),
        _diagnostic_step(
            "logs", "Inspect time-bounded service logs",
            "warning" if any(item.get("severity") in {"critical", "warning"} for item in log_findings) else
            "passed" if include_logs and manager == "systemd" else "skipped" if not include_logs else "not_applicable",
            f"Collected {len(journal)} redacted journal line(s) since {since}." if journal else
            "Log content was not requested." if not include_logs else
            f"No service journal entries were returned since {since}." if manager == "systemd" else
            f"Automatic journal collection is not available for {manager}.",
            depends_on=["service_manager"],
        ),
    ]
    return {
        "service": name,
        "manager": manager,
        "status": _diagnostic_status(findings),
        "read_only": True,
        "context": context,
        "methodology": _methodology(
            "service-state", "Define the symptom, query the manager, correlate processes and any explicit service port, then inspect bounded logs before changing state.", steps,
        ),
        "details": details,
        "processes": processes,
        "firewall": firewall,
        "journal": journal,
        "logs_requested": include_logs,
        "logs_collected": bool(journal),
        "log_source": log_source,
        "logs_included": include_logs,
        "logs_redacted": include_logs and not raw_logs,
        "cause_candidates": _rank_cause_candidates(findings),
        "findings": findings,
    }


def _proc_memory() -> Dict[str, Any]:
    path = Path("/proc/meminfo")
    if not path.is_file():
        if platform.system().lower() == "windows":
            try:
                import ctypes

                class MemoryStatus(ctypes.Structure):
                    _fields_ = [
                        ("length", ctypes.c_ulong), ("memory_load", ctypes.c_ulong),
                        ("total_physical", ctypes.c_ulonglong), ("available_physical", ctypes.c_ulonglong),
                        ("total_page_file", ctypes.c_ulonglong), ("available_page_file", ctypes.c_ulonglong),
                        ("total_virtual", ctypes.c_ulonglong), ("available_virtual", ctypes.c_ulonglong),
                        ("available_extended_virtual", ctypes.c_ulonglong),
                    ]

                status = MemoryStatus()
                status.length = ctypes.sizeof(MemoryStatus)
                windll = getattr(ctypes, "windll", None)
                if windll and windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                    return {
                        "total_bytes": status.total_physical,
                        "available_bytes": status.available_physical,
                        "available_percent": round(status.available_physical / status.total_physical * 100, 2),
                        "swap_total_bytes": None, "swap_used_bytes": None, "swap_used_percent": None,
                    }
            except (AttributeError, OSError, ZeroDivisionError):
                return {}
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            total = os.sysconf("SC_PHYS_PAGES") * page_size
            available = os.sysconf("SC_AVPHYS_PAGES") * page_size
            return {
                "total_bytes": total, "available_bytes": available,
                "available_percent": round(available / total * 100, 2) if total else None,
                "swap_total_bytes": None, "swap_used_bytes": None, "swap_used_percent": None,
            }
        except (AttributeError, OSError, ValueError):
            return {}
    values: Dict[str, int] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            key, separator, value = line.partition(":")
            if not separator:
                continue
            match = re.match(r"\s*(\d+)", value)
            if match:
                values[key] = int(match.group(1)) * 1024
    except OSError:
        return {}
    total = values.get("MemTotal", 0)
    available = values.get("MemAvailable", values.get("MemFree", 0))
    swap_total = values.get("SwapTotal", 0)
    swap_free = values.get("SwapFree", 0)
    return {
        "total_bytes": total,
        "available_bytes": available,
        "available_percent": round(available / total * 100, 2) if total else None,
        "swap_total_bytes": swap_total,
        "swap_used_bytes": max(0, swap_total - swap_free),
        "swap_used_percent": round((swap_total - swap_free) / swap_total * 100, 2) if swap_total else 0.0,
    }


def _linux_pressure() -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for resource in ("cpu", "memory", "io"):
        path = Path("/proc/pressure") / resource
        if not path.is_file():
            continue
        rows: Dict[str, Any] = {}
        try:
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                fields = line.split()
                if not fields:
                    continue
                metrics: Dict[str, Any] = {}
                for field in fields[1:]:
                    key, separator, value = field.partition("=")
                    if separator:
                        metrics[key] = float(value) if key.startswith("avg") else int(value)
                rows[fields[0]] = metrics
        except (OSError, ValueError):
            continue
        result[resource] = rows
    return result


def _process_summary() -> Dict[str, Any]:
    proc = Path("/proc")
    if not proc.is_dir():
        return {}
    total = 0
    zombies = 0
    unreadable = 0
    try:
        entries = proc.iterdir()
    except OSError:
        return {}
    for entry in entries:
        if not entry.name.isdigit():
            continue
        total += 1
        try:
            value = (entry / "stat").read_text(encoding="utf-8", errors="replace")
            closing = value.rfind(")")
            state = value[closing + 2:closing + 3] if closing >= 0 else ""
            if state == "Z":
                zombies += 1
        except OSError:
            unreadable += 1
    return {"total": total, "zombies": zombies, "unreadable": unreadable}


def _time_sync_status(timeout: float) -> Dict[str, Any]:
    if shutil.which("timedatectl"):
        command = _diagnostic_command(
            ["timedatectl", "show", "--property=NTPSynchronized", "--property=NTP", "--property=Timezone"],
            timeout=timeout,
        )
        values: Dict[str, Any] = {}
        for line in command["stdout"].splitlines():
            key, separator, value = line.partition("=")
            if separator:
                values[key] = value
        return {
            "available": command["available"], "source": "timedatectl", "ok": command["ok"],
            "synchronized": values.get("NTPSynchronized") == "yes" if command["ok"] else None,
            "properties": values, "error": command.get("error") if not command["ok"] else None,
        }
    if shutil.which("chronyc"):
        command = _diagnostic_command(["chronyc", "tracking"], timeout=timeout)
        leap = re.search(r"^Leap status\s*:\s*(.+)$", command["stdout"], re.MULTILINE | re.IGNORECASE)
        return {
            "available": True, "source": "chronyc", "ok": command["ok"],
            "synchronized": bool(leap and leap.group(1).strip().lower() == "normal") if command["ok"] else None,
            "summary": _redact_log_line(command["stdout"][-8192:]),
            "error": command.get("error") if not command["ok"] else None,
        }
    if shutil.which("ntpq"):
        command = _diagnostic_command(["ntpq", "-pn"], timeout=timeout)
        synchronized = any(line.startswith("*") for line in command["stdout"].splitlines())
        return {
            "available": True, "source": "ntpq", "ok": command["ok"],
            "synchronized": synchronized if command["ok"] else None,
            "summary": command["stdout"][-8192:],
            "error": command.get("error") if not command["ok"] else None,
        }
    if platform.system().lower() == "windows" and shutil.which("w32tm"):
        command = _diagnostic_command(["w32tm", "/query", "/status"], timeout=timeout)
        return {
            "available": True, "source": "w32tm", "ok": command["ok"],
            "synchronized": command["ok"], "summary": command["stdout"][-8192:],
            "error": command.get("error") if not command["ok"] else None,
        }
    return {"available": False, "source": None, "synchronized": None}


def _listening_sockets(timeout: float = 5.0) -> Dict[str, Any]:
    if shutil.which("ss"):
        command = _diagnostic_command(["ss", "-H", "-lntux"], timeout=timeout)
        source = "ss"
    elif shutil.which("netstat"):
        command = _diagnostic_command(["netstat", "-an"], timeout=timeout)
        source = "netstat"
    else:
        return {"available": False, "source": None, "listeners": []}
    listeners = []
    for line in command["stdout"].splitlines():
        fields = line.split()
        if not fields:
            continue
        protocol = fields[0].lower()
        if source == "netstat" and "listen" not in line.lower() and not protocol.startswith("udp"):
            continue
        local = ""
        if source == "ss" and len(fields) >= 5:
            local = fields[4]
        elif source == "netstat" and len(fields) >= 4:
            local = fields[3]
        if protocol.startswith("u_") or protocol == "unix":
            listeners.append({
                "family": "unix", "protocol": protocol,
                "local_address": local, "path": local, "port": None,
            })
        else:
            match = re.search(r"(?:\]|:|\.)(\d+)$", local)
            listeners.append({
                "family": "ip", "protocol": protocol,
                "local_address": local,
                "port": int(match.group(1)) if match else None,
            })
        if len(listeners) >= 1000:
            break
    return {
        "available": command["available"],
        "source": source,
        "listeners": listeners,
        "truncated": len(listeners) >= 1000,
        "error": command.get("error") if not command["ok"] else None,
    }


def _firewall_permission_limited(command: Dict[str, Any]) -> bool:
    text = "\n".join(
        str(command.get(key) or "") for key in ("stdout", "stderr", "error")
    ).lower()
    return any(marker in text for marker in (
        "permission denied", "operation not permitted", "must be root",
        "need to be root", "you need to be root", "access is denied",
        "requires elevation", "insufficient privileges",
    ))


def _port_in_numeric_spec(port: int, value: str) -> bool:
    """Match a port against numeric single, range, or comma-separated syntax."""
    for start_text, end_text in re.findall(r"(?<![\d.])(\d{1,5})(?:\s*[-:]\s*(\d{1,5}))?", value):
        start = int(start_text)
        end = int(end_text) if end_text else start
        if 1 <= start <= port <= end <= 65535:
            return True
    return False


def _firewall_rule_mentions_port(line: str, port: int) -> bool:
    lowered = line.lower()
    has_port_selector = "dport" in lowered or bool(re.search(r"\bport\b", lowered))
    if not has_port_selector:
        # A terminal inbound deny without a port selector can affect every new
        # connection. Do not treat stateful ESTABLISHED/RELATED accepts or
        # outbound PF rules as evidence about a new inbound connection.
        if re.search(r"\b(?:established|related)\b", lowered):
            return False
        if re.search(r"\bout\b", lowered) and not re.search(r"\bin\b", lowered):
            return False
        return bool(re.search(r"\b(?:block|drop|deny|reject)\b", lowered))
    if re.search(r"(?:--dports?|\bdport|\bport\s*(?:=)?)\s+[\"']?(?:any\b|\*)", lowered):
        return True
    if "--dport" in lowered:
        match = re.search(r"--dports?\s+([^\s]+)", lowered)
        return bool(match and _port_in_numeric_spec(port, match.group(1)))
    match = re.search(
        r"\bdport\s+(.*?)(?:\s+(?:accept|allow|drop|deny|reject|counter|jump|goto|comment)\b|$)",
        lowered,
    )
    if match:
        return _port_in_numeric_spec(port, match.group(1))
    match = re.search(
        r"\bport\s*(?:=)?\s*(.*?)(?:\s+(?:accept|allow|drop|deny|reject|in|on|from|to|$)\b|$)",
        lowered,
    )
    return bool(match and _port_in_numeric_spec(port, match.group(1)))


def _rule_assessment(
    backend: str,
    port: int,
    rules: List[str],
    default_policy: Optional[str] = None,
) -> Dict[str, Any]:
    raw_matches = [
        line.strip()
        for line in rules
        if _firewall_rule_mentions_port(line, port)
    ][:20]
    matches = [_redact_log_line(line)[:1000] for line in raw_matches]
    actions = set()
    for line in raw_matches:
        lowered = re.sub(r'"[^"\n]*"|\'[^\'\n]*\'', "", line.lower())
        if re.search(r"\b(?:accept|allow|pass)\b", lowered) or "-j accept" in lowered:
            actions.add("allow")
        if re.search(r"\b(?:block|drop|deny|reject)\b", lowered) or re.search(r"-j\s+(?:drop|reject)\b", lowered):
            actions.add("deny")
    normalized_policy = (default_policy or "").lower()
    if actions == {"allow"}:
        verdict = "explicit_allow_observed"
    elif actions == {"deny"}:
        verdict = "explicit_deny_observed"
    elif len(actions) > 1:
        verdict = "conflicting_rules_observed"
    elif normalized_policy in {"drop", "deny", "reject", "block"}:
        verdict = "default_deny_without_direct_match"
    elif normalized_policy in {"accept", "allow", "pass"}:
        verdict = "default_allow_without_direct_match"
    else:
        verdict = "indeterminate"
    return {
        "backend": backend,
        "port": port,
        "protocol": "tcp",
        "verdict": verdict,
        "default_policy": default_policy,
        "matching_rules": matches,
    }


def _inspect_ufw(ports: List[int], timeout: float) -> Optional[Dict[str, Any]]:
    executable = shutil.which("ufw")
    if not executable:
        return None
    command = _diagnostic_command([executable, "status", "verbose"], timeout=timeout)
    text = command.get("stdout", "") + command.get("stderr", "")
    permission_limited = _firewall_permission_limited(command)
    active = bool(re.search(r"(?im)^status:\s*active\s*$", text)) if command["ok"] else None
    if re.search(r"(?im)^status:\s*inactive\s*$", text):
        active = False
    policy_match = re.search(r"(?im)^default:\s*(allow|deny|reject)\s*\(incoming\)", text)
    default_policy = policy_match.group(1).lower() if policy_match else None
    rule_lines = []
    application_rules = []
    for line in text.splitlines():
        match = re.match(
            r"^\s*(?:\[\s*\d+\]\s*)?(.+?)\s{2,}(ALLOW|DENY|REJECT|LIMIT)\s+IN\b",
            line,
        )
        if not match:
            continue
        destination = match.group(1).strip()
        action = "accept" if match.group(2) in {"ALLOW", "LIMIT"} else "drop"
        if re.match(r"^\d", destination):
            if "/udp" not in destination.lower():
                rule_lines.append(f"tcp dport {destination.split('/', 1)[0]} {action} comment {line.strip()}")
        elif destination.lower() in {"anywhere", "anywhere (v6)"}:
            rule_lines.append(f"tcp dport any {action} comment {line.strip()}")
        else:
            profile = re.sub(r"\s+\(v6\)$", "", destination).strip()
            if profile:
                application_rules.append((profile, action, line.strip()))
    for profile, action, original in list(dict.fromkeys(application_rules))[:20]:
        profile_info = _diagnostic_command([executable, "app", "info", profile], timeout=timeout)
        permission_limited = permission_limited or _firewall_permission_limited(profile_info)
        if not profile_info["ok"]:
            continue
        for profile_line in profile_info.get("stdout", "").splitlines():
            tcp_specs = re.findall(
                r"(\d{1,5}(?:\s*[-:]\s*\d{1,5})?(?:\s*,\s*\d{1,5}(?:\s*[-:]\s*\d{1,5})?)*)/tcp\b",
                profile_line,
                re.IGNORECASE,
            )
            for port_spec in tcp_specs:
                rule_lines.append(
                    f"tcp dport {port_spec} {action} comment profile={profile} rule={original}"
                )
    assessments = []
    for port in ports:
        assessment = _rule_assessment("ufw", port, rule_lines, default_policy)
        assessments.append(assessment)
    return {
        "name": "ufw", "role": "frontend", "available": True, "active": active,
        "inspection": "permission_limited" if permission_limited else "ok" if command["ok"] else "failed",
        "default_inbound_policy": default_policy,
        "port_assessments": assessments,
        "error": command.get("error") if not command["ok"] else None,
    }


def _parse_firewalld_zones(text: str) -> List[str]:
    zones = []
    for line in text.splitlines():
        if line and not line[0].isspace():
            zone = line.split()[0]
            if re.fullmatch(r"[A-Za-z0-9_.-]+", zone):
                zones.append(zone)
    return list(dict.fromkeys(zones))[:32]


def _firewalld_service_ports(
    executable: str,
    services: List[str],
    timeout: float,
) -> tuple[Dict[str, List[str]], bool]:
    """Resolve active firewalld service names to declared TCP port specs."""
    result: Dict[str, List[str]] = {}
    permission_limited = False
    for service in list(dict.fromkeys(services))[:64]:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", service):
            continue
        command = _diagnostic_command(
            [executable, f"--info-service={service}"], timeout=timeout,
        )
        permission_limited = permission_limited or _firewall_permission_limited(command)
        if not command["ok"]:
            continue
        specs: List[str] = []
        for line in command.get("stdout", "").splitlines():
            key, separator, value = line.strip().partition(":")
            if separator and key.lower() == "ports":
                specs.extend(
                    item.rsplit("/", 1)[0]
                    for item in value.split()
                    if item.lower().endswith("/tcp")
                )
        result[service] = specs
    return result, permission_limited


def _inspect_firewalld(ports: List[int], timeout: float) -> Optional[Dict[str, Any]]:
    executable = shutil.which("firewall-cmd")
    if not executable:
        return None
    state = _diagnostic_command([executable, "--state"], timeout=timeout)
    permission_limited = _firewall_permission_limited(state)
    state_text = (state.get("stdout", "") + state.get("stderr", "")).strip().lower()
    active = state["ok"] and state_text == "running"
    state_known = active or "not running" in state_text
    zones: List[Dict[str, Any]] = []
    if active:
        active_zones = _diagnostic_command([executable, "--get-active-zones"], timeout=timeout)
        permission_limited = permission_limited or _firewall_permission_limited(active_zones)
        for zone_name in _parse_firewalld_zones(active_zones.get("stdout", "")):
            details = _diagnostic_command([executable, f"--zone={zone_name}", "--list-all"], timeout=timeout)
            permission_limited = permission_limited or _firewall_permission_limited(details)
            values: Dict[str, str] = {}
            for line in details.get("stdout", "").splitlines():
                key, separator, value = line.strip().partition(":")
                if separator:
                    values[key] = value.strip()
            rich_rules = [
                line.strip()
                for line in details.get("stdout", "").splitlines()
                if line.strip().startswith("rule ")
            ]
            zones.append({
                "name": zone_name,
                "interfaces": values.get("interfaces", "").split(),
                "sources": values.get("sources", "").split(),
                "services": values.get("services", "").split(),
                "ports": values.get("ports", "").split(),
                "target": values.get("target"),
                "rich_rules": rich_rules[:128],
            })
    service_names = [
        service
        for zone_details in zones
        for service in zone_details["services"]
    ]
    service_ports, service_limited = _firewalld_service_ports(
        executable, service_names, timeout,
    ) if active else ({}, False)
    permission_limited = permission_limited or service_limited
    assessments = []
    for port in ports:
        rules = []
        policies = []
        for zone_details in zones:
            zone_name = zone_details["name"]
            for spec in zone_details["ports"]:
                if spec.lower().endswith("/tcp"):
                    rules.append(
                        f"tcp dport {spec.rsplit('/', 1)[0]} accept comment zone={zone_name}"
                    )
            for service in zone_details["services"]:
                for spec in service_ports.get(service, []):
                    rules.append(
                        f"tcp dport {spec} accept comment zone={zone_name} service={service}"
                    )
            rules.extend(
                f"{rich_rule} comment zone={zone_name}"
                for rich_rule in zone_details.get("rich_rules", [])
            )
            target = str(zone_details.get("target") or "").strip("%").lower()
            if target in {"accept", "drop", "reject"}:
                policies.append(target)
        policy = (
            policies[0]
            if zones and len(policies) == len(zones) and len(set(policies)) == 1
            else None
        )
        assessments.append(_rule_assessment("firewalld", port, rules, policy))
    return {
        "name": "firewalld", "role": "frontend", "available": True, "active": active,
        "inspection": "permission_limited" if permission_limited else "ok" if state["ok"] or state_known else "failed",
        "zones": zones, "port_assessments": assessments,
        "error": state.get("error") if not state["ok"] and not state_known else None,
    }


def _nft_input_rules(text: str) -> tuple[List[str], List[str]]:
    rules: List[str] = []
    policies: List[str] = []
    chain_lines: List[str] = []
    in_chain = False
    depth = 0
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("chain ") and stripped.endswith("{"):
            in_chain = True
            depth = 1
            chain_lines = []
            continue
        if not in_chain:
            continue
        depth += stripped.count("{") - stripped.count("}")
        if depth <= 0:
            block = "\n".join(chain_lines)
            if re.search(r"\bhook\s+input\b", block):
                policies.extend(re.findall(r"\bpolicy\s+(accept|drop|reject)\b", block, re.IGNORECASE))
                rules.extend(
                    chain_line
                    for chain_line in chain_lines
                    if not re.search(r"\bhook\s+input\b", chain_line)
                    and not re.match(r"^policy\s+", chain_line)
                )
            in_chain = False
            chain_lines = []
        else:
            chain_lines.append(stripped)
    return rules, policies


def _inspect_nftables(ports: List[int], timeout: float) -> Optional[Dict[str, Any]]:
    executable = shutil.which("nft")
    if not executable:
        return None
    command = _diagnostic_command([executable, "-n", "list", "ruleset"], timeout=timeout)
    permission_limited = _firewall_permission_limited(command)
    rules, policies = _nft_input_rules(command.get("stdout", "")) if command["ok"] else ([], [])
    policy = policies[0].lower() if len(set(value.lower() for value in policies)) == 1 and policies else None
    return {
        "name": "nftables", "role": "backend", "available": True,
        "active": bool(rules or policies) if command["ok"] else None,
        "inspection": "permission_limited" if permission_limited else "ok" if command["ok"] else "failed",
        "default_inbound_policy": policy,
        "input_chain_count": len(policies),
        "port_assessments": [_rule_assessment("nftables", port, rules, policy) for port in ports],
        "error": command.get("error") if not command["ok"] else None,
    }


def _inspect_iptables_command(name: str, ports: List[int], timeout: float) -> Optional[Dict[str, Any]]:
    executable = shutil.which(name)
    if not executable:
        return None
    command = _diagnostic_command([executable, "-S", "INPUT"], timeout=timeout)
    permission_limited = _firewall_permission_limited(command)
    lines = command.get("stdout", "").splitlines() if command["ok"] else []
    policy_match = re.search(r"(?m)^-P\s+INPUT\s+(ACCEPT|DROP|REJECT)\b", command.get("stdout", ""))
    policy = policy_match.group(1).lower() if policy_match else None
    return {
        "name": name, "role": "backend", "available": True,
        "active": bool(lines) if command["ok"] else None,
        "inspection": "permission_limited" if permission_limited else "ok" if command["ok"] else "failed",
        "default_inbound_policy": policy,
        "port_assessments": [_rule_assessment(name, port, lines, policy) for port in ports],
        "error": command.get("error") if not command["ok"] else None,
    }


def _inspect_windows_firewall(ports: List[int], timeout: float) -> Optional[Dict[str, Any]]:
    executable = shutil.which("powershell") or shutil.which("pwsh")
    if not executable:
        return None
    script = (
        "$profiles=@(Get-NetFirewallProfile | ForEach-Object { "
        "[pscustomobject]@{Name=$_.Name.ToString();Enabled=$_.Enabled;"
        "DefaultInboundAction=$_.DefaultInboundAction.ToString()} });"
        "$rules=@();"
        + (
            "$rules=@(Get-NetFirewallRule -Enabled True -Direction Inbound | ForEach-Object { "
            "$rule=$_; @($rule | Get-NetFirewallPortFilter) | Where-Object { "
            "$_.Protocol -eq 'TCP' -or $_.Protocol -eq 6 } | ForEach-Object { "
            "[pscustomobject]@{Name=$rule.DisplayName;Action=$rule.Action.ToString();"
            "LocalPort=$_.LocalPort;Profile=$rule.Profile.ToString()} } } | Select-Object -First 512);"
            if ports else ""
        )
        + "[pscustomobject]@{Profiles=$profiles;Rules=$rules} | ConvertTo-Json -Depth 4 -Compress"
    )
    command = _diagnostic_command(
        [executable, "-NoProfile", "-NonInteractive", "-Command", script], timeout=timeout,
    )
    profiles: List[Dict[str, Any]] = []
    firewall_rules: List[Dict[str, Any]] = []
    parsed_ok = False
    if command["ok"]:
        try:
            parsed = json.loads(command["stdout"])
            if isinstance(parsed, dict):
                raw_profiles = parsed.get("Profiles", [])
                raw_rules = parsed.get("Rules", [])
                profiles = raw_profiles if isinstance(raw_profiles, list) else [raw_profiles]
                firewall_rules = raw_rules if isinstance(raw_rules, list) else [raw_rules]
                parsed_ok = True
        except (json.JSONDecodeError, TypeError):
            pass
    active = any(bool(item.get("Enabled")) for item in profiles) if parsed_ok else None
    default_values = {
        str(item.get("DefaultInboundAction", "")).lower()
        for item in profiles if item.get("Enabled")
    }
    policy = next(iter(default_values)) if len(default_values) == 1 else None
    normalized_rules = [
        f"tcp dport {item.get('LocalPort', '')} {item.get('Action', '')} "
        f"comment profile={item.get('Profile', '')}"
        for item in firewall_rules
        if item.get("LocalPort") not in {None, ""}
    ]
    return {
        "name": "windows-firewall", "role": "backend", "available": True,
        "active": active if command["ok"] else None,
        "inspection": "permission_limited" if _firewall_permission_limited(command) else "ok" if command["ok"] and parsed_ok else "failed",
        "profiles": profiles, "default_inbound_policy": policy,
        "inspected_rule_count": len(firewall_rules),
        "port_assessments": [
            _rule_assessment("windows-firewall", port, normalized_rules, policy)
            for port in ports
        ],
        "error": command.get("error") if not command["ok"] else None if parsed_ok else "PowerShell returned an unreadable firewall result",
    }


def _inspect_pf(ports: List[int], timeout: float) -> Optional[Dict[str, Any]]:
    executable = shutil.which("pfctl")
    if not executable:
        return None
    info = _diagnostic_command([executable, "-s", "info"], timeout=timeout)
    rules_command = _diagnostic_command([executable, "-sr"], timeout=timeout)
    permission_limited = _firewall_permission_limited(info) or _firewall_permission_limited(rules_command)
    active_match = re.search(r"(?im)^status:\s*(enabled|disabled)", info.get("stdout", ""))
    active = active_match.group(1).lower() == "enabled" if active_match else None
    rules = rules_command.get("stdout", "").splitlines() if rules_command["ok"] else []
    return {
        "name": "pf", "role": "backend", "available": True, "active": active,
        "inspection": "permission_limited" if permission_limited else "ok" if info["ok"] else "failed",
        "port_assessments": [_rule_assessment("pf", port, rules) for port in ports],
        "error": info.get("error") if not info["ok"] else None,
    }


def firewall_diagnostic(
    ports: Optional[List[int]] = None,
    timeout: float = 5.0,
    symptom: Optional[str] = None,
    expected: Optional[str] = None,
    recent_change: Optional[str] = None,
) -> Dict[str, Any]:
    """Inspect host firewall state and cautiously correlate inbound TCP ports."""
    if timeout <= 0:
        raise ValueError("Timeout must be greater than zero")
    selected_ports = list(dict.fromkeys(ports or []))
    if len(selected_ports) > 32:
        raise ValueError("A firewall diagnostic accepts at most 32 ports")
    for port in selected_ports:
        _validate_port(port)
    target = ",".join(str(port) for port in selected_ports) or "host firewall"
    context = _diagnostic_context(target, symptom, expected, recent_change)
    system = platform.system().lower()
    backends: List[Dict[str, Any]] = []
    inspectors: List[Any]
    if system == "linux":
        inspectors = [
            _inspect_ufw, _inspect_firewalld, _inspect_nftables,
            lambda values, limit: _inspect_iptables_command("iptables", values, limit),
            lambda values, limit: _inspect_iptables_command("ip6tables", values, limit),
        ]
    elif system == "windows":
        inspectors = [_inspect_windows_firewall]
    elif system in {"darwin", "freebsd", "openbsd"}:
        inspectors = [_inspect_pf]
    else:
        inspectors = []
    for inspector in inspectors:
        result = inspector(selected_ports, timeout)
        if result:
            backends.append(result)
    active = [item for item in backends if item.get("active") is True]
    limited = [item["name"] for item in backends if item.get("inspection") in {"permission_limited", "failed"}]
    assessments = []
    findings = []
    for port in selected_ports:
        observations = [
            assessment
            for backend in active
            for assessment in backend.get("port_assessments", [])
            if assessment.get("port") == port
        ]
        verdicts = {item.get("verdict") for item in observations}
        if "explicit_deny_observed" in verdicts or "conflicting_rules_observed" in verdicts:
            verdict = "potentially_blocked"
        elif "default_deny_without_direct_match" in verdicts and "explicit_allow_observed" not in verdicts:
            verdict = "no_allow_observed_with_default_deny"
        elif "explicit_allow_observed" in verdicts:
            verdict = "allow_rule_observed"
        elif active and verdicts == {"default_allow_without_direct_match"}:
            verdict = "no_local_block_observed"
        elif not active and backends and not limited:
            verdict = "no_active_host_firewall_detected"
        else:
            verdict = "indeterminate"
        assessment = {
            "port": port, "protocol": "tcp", "verdict": verdict,
            "backend_observations": observations,
        }
        assessments.append(assessment)
        if verdict == "potentially_blocked":
            findings.append(_finding(
                "firewall_port_potentially_blocked", "warning",
                f"An observed host-firewall rule may block inbound TCP port {port}.",
                evidence=", ".join(sorted(
                    {item["backend"] for item in observations if item.get("verdict") in {"explicit_deny_observed", "conflicting_rules_observed"}}
                )),
                recommendation="Confirm source address, interface, address family, rule order, counters, and network namespace before changing policy.",
                phase="firewall",
            ))
        elif verdict == "no_allow_observed_with_default_deny":
            findings.append(_finding(
                "firewall_port_not_explicitly_allowed", "warning",
                f"No direct allow for TCP port {port} was observed under a default-deny inbound policy.",
                recommendation="Inspect referenced chains, sets, zones, source restrictions, address family, and counters before concluding that the port is blocked.",
                phase="firewall",
            ))
    if limited:
        findings.append(_finding(
            "firewall_inspection_limited", "warning" if selected_ports else "info",
            "Some installed firewall controls could not be fully inspected by the current account.",
            evidence=", ".join(limited),
            recommendation="Repeat with an account that can list the ruleset; SysAdminToolbox never invokes sudo itself.",
            phase="firewall",
        ))
    if not backends:
        findings.append(_finding(
            "firewall_tooling_unavailable", "info",
            "No supported host-firewall inspection command was found.",
            recommendation="Check the host platform and any external firewall, security group, load balancer, or container policy.",
            phase="firewall",
        ))
    findings = _deduplicate_findings(findings)
    correlation_warning = any(item["severity"] == "warning" for item in findings)
    steps = [
        _diagnostic_step(
            "context", "Define the affected inbound service ports",
            "passed" if selected_ports or _has_operator_context(context) else "warning",
            f"Assessing inbound TCP port(s): {', '.join(map(str, selected_ports))}." if selected_ports else
            "No ports were supplied; only firewall discovery is performed.",
        ),
        _diagnostic_step(
            "discovery", "Discover host firewall managers and backends",
            "passed" if backends else "not_applicable",
            f"Found {len(backends)} supported firewall control(s)." if backends else
            "No supported firewall command was found on this platform.",
            depends_on=["context"],
        ),
        _diagnostic_step(
            "rules", "Read active inbound policy without changing it",
            "warning" if limited else "passed" if active else "not_applicable",
            f"Inspected {len(active)} active control(s)." if active else
            "Inspection was limited by permissions." if limited else "No active supported host firewall was detected.",
            depends_on=["discovery"],
        ),
        _diagnostic_step(
            "ports", "Correlate policy with service ports",
            "warning" if correlation_warning else "passed" if selected_ports and assessments else "skipped",
            f"Produced {len(assessments)} cautious port assessment(s)." if assessments else
            "Supply one or more ports to correlate firewall policy with a service.",
            layer="OSI 3-4", depends_on=["rules"],
        ),
        _diagnostic_step(
            "external_boundary", "Separate host policy from upstream controls", "not_applicable",
            "Host inspection cannot observe cloud security groups, routers, load balancers, provider ACLs, or another network namespace.",
            layer="Network path", depends_on=["ports"],
        ),
    ]
    return {
        "status": _diagnostic_status(findings), "read_only": True,
        "context": context,
        "methodology": _methodology(
            "host-firewall", "Discover active host controls, inspect inbound policy, correlate only the requested service ports, and keep upstream controls outside the proof boundary.", steps,
        ),
        "platform": platform.system(), "ports": selected_ports,
        "backends": backends, "active_backends": [item["name"] for item in active],
        "port_assessments": assessments,
        "scope_limit": "Local host rules only; external and namespace-specific controls require separate evidence.",
        "cause_candidates": _rank_cause_candidates(findings), "findings": findings,
    }


def _route_to_address(address: str, timeout: float) -> Dict[str, Any]:
    """Resolve the selected egress route without sending traffic."""
    system = platform.system().lower()
    if system == "linux" and shutil.which("ip"):
        command = _diagnostic_command(["ip", "-j", "route", "get", address], timeout=timeout)
        route = None
        if command["ok"]:
            try:
                rows = json.loads(command["stdout"])
                route = rows[0] if rows else None
            except (json.JSONDecodeError, TypeError, IndexError):
                route = None
        return {
            "available": command["available"], "status": "ok" if route else "failed",
            "destination": address, "route": route,
            "error": None if route else command.get("error") or "route lookup returned no result",
        }
    if system == "darwin" and shutil.which("route"):
        command = _diagnostic_command(["route", "-n", "get", address], timeout=timeout)
        values = {}
        for line in command["stdout"].splitlines():
            key, separator, value = line.strip().partition(":")
            if separator:
                values[key.strip()] = value.strip()
        return {
            "available": command["available"], "status": "ok" if command["ok"] else "failed",
            "destination": address, "route": values or None,
            "error": command.get("error") if not command["ok"] else None,
        }
    return {
        "available": False, "status": "not_applicable", "destination": address,
        "route": None, "error": "target-specific route lookup is unavailable on this platform",
    }


def network_diagnostic(
    probe: Optional[str] = None,
    port: int = 443,
    timeout: float = 5.0,
    symptom: Optional[str] = None,
    expected: Optional[str] = None,
    recent_change: Optional[str] = None,
) -> Dict[str, Any]:
    """Follow a bottom-up network path and optionally test one endpoint."""
    if timeout <= 0:
        raise ValueError("Timeout must be greater than zero")
    _validate_port(port)
    context = _diagnostic_context(probe or "local network", symptom, expected, recent_change)
    inventory = local_network_inventory()
    listeners = _listening_sockets(timeout)
    findings = []
    interfaces = inventory.get("interfaces", [])
    non_loopback = [item for item in interfaces if item.get("name") not in {"lo", "lo0"}]
    active_interfaces = [
        item for item in non_loopback
        if str(item.get("state") or "").upper() in {"UP", "UNKNOWN", "CONNECTED"}
        or any(address.get("scope") == "global" for address in item.get("addresses", []))
        or (not item.get("state") and bool(item.get("addresses")))
    ]
    if not interfaces:
        findings.append(_finding(
            "network_interfaces_unavailable", "warning", "No network-interface inventory was collected.",
            evidence="; ".join(inventory.get("errors", [])) or None,
            recommendation="Check platform tooling and inspect interface/link state manually.", phase="link",
        ))
    elif probe and not active_interfaces:
        findings.append(_finding(
            "network_link_unavailable", "critical", "No active non-loopback network interface was detected.",
            recommendation="Check interface administrative state, carrier, VLAN attachment, and the platform network manager.",
            phase="link",
        ))
    endpoint = parse_endpoint(probe, default_port=port) if probe else None
    host_is_ip = False
    if endpoint:
        try:
            ipaddress.ip_address(endpoint["host"])
            host_is_ip = True
        except ValueError:
            pass
    if not inventory.get("default_routes") and (not endpoint or not host_is_ip):
        findings.append(_finding(
            "default_route_missing", "warning", "No default route was detected.",
            recommendation="Check interface state, addressing, and the expected routing table.",
            phase="routing",
        ))
    if not inventory.get("dns_servers") and (not endpoint or not host_is_ip):
        findings.append(_finding(
            "dns_servers_missing", "warning", "No DNS resolver was detected.",
            recommendation="Inspect the resolver configuration and network manager state.",
            phase="dns",
        ))
    checks: Dict[str, Any] = {}
    selected_address = None
    route = None
    if endpoint:
        if host_is_ip:
            selected_address = endpoint["host"]
            checks["dns"] = {
                "status": "not_applicable", "addresses": [],
                "reason": "The target is already an IP address.",
            }
        else:
            checks["dns"] = resolve_all(endpoint["host"], timeout)
            if checks["dns"]["status"] == "ok" and checks["dns"].get("addresses"):
                selected_address = checks["dns"]["addresses"][0]["address"]
        if checks["dns"]["status"] == "failed":
            findings.append(_finding(
                "probe_dns_failed", "critical", f"DNS resolution failed for {endpoint['host']}.",
                evidence=checks["dns"].get("error"),
                recommendation="Check the resolver, search domains, and authoritative DNS records.",
                phase="dns",
            ))
            checks["tcp"] = {
                "status": "skipped", "host": endpoint["host"], "port": endpoint["port"],
                "reason": "Transport probing depends on successful name resolution.",
            }
        else:
            route_candidates = []
            addresses_to_check = (
                [str(selected_address)] if host_is_ip else
                [str(item["address"]) for item in checks.get("dns", {}).get("addresses", [])]
            )
            for address in addresses_to_check:
                candidate_route = _route_to_address(address, timeout)
                route_candidates.append(candidate_route)
                if candidate_route.get("status") == "ok":
                    route = candidate_route
                    selected_address = address
                    break
            if route is None and route_candidates:
                route = route_candidates[0]
            checks["route"] = route
            checks["route_candidates"] = route_candidates
            if route and route["status"] == "failed":
                findings.append(_finding(
                    "probe_route_failed", "critical", f"No usable route was found for {selected_address}.",
                    evidence=route.get("error"),
                    recommendation="Check the selected routing table, source address, gateway, and network namespace.",
                    phase="routing",
                ))
            checks["tcp"] = tcp_probe(endpoint["host"], endpoint["port"], timeout)
            checks["tcp"]["requested_host"] = endpoint["host"]
        if checks["tcp"]["status"] == "failed":
            findings.append(_finding(
                "probe_tcp_failed", "critical",
                f"TCP connection to {endpoint['host']}:{endpoint['port']} failed.",
                evidence=checks["tcp"].get("error"),
                recommendation="Check routing, firewall policy, listener state, and the target service.",
                phase="transport",
            ))
        if endpoint.get("scheme") and checks["tcp"]["status"] == "ok":
            url_host = f"[{endpoint['host']}]" if ":" in endpoint["host"] else endpoint["host"]
            default = 443 if endpoint["scheme"] == "https" else 80
            authority = url_host if endpoint["port"] == default else f"{url_host}:{endpoint['port']}"
            request_path = endpoint.get("path") or "/"
            if endpoint.get("query"):
                request_path += "?" + endpoint["query"]
            url = f"{endpoint['scheme']}://{authority}{request_path}"
            checks["application"] = _http_status_probe(url, None, timeout)
            if checks["application"]["status"] == "failed":
                findings.append(_finding(
                    "probe_application_failed", "critical", "The application-layer probe failed.",
                    evidence=str(checks["application"].get("error") or checks["application"].get("status_code")),
                    recommendation="Keep the working lower layers and inspect TLS or application configuration next.",
                    phase="application",
                ))
            elif checks["application"]["status"] == "warning":
                findings.append(_finding(
                    "probe_application_warning", "warning",
                    f"The application returned HTTP {checks['application'].get('status_code')}.",
                    recommendation="Keep the working lower layers and inspect the application response and selected virtual host.",
                    phase="application",
                ))
    findings = _deduplicate_findings(findings)
    phase_findings = {
        phase: [item for item in findings if item.get("phase") == phase]
        for phase in ("link", "routing", "dns", "transport", "application")
    }
    steps = [
        _diagnostic_step(
            "context", "Define endpoint and symptom", "passed" if probe or _has_operator_context(context) else "warning",
            "A target or operator context was supplied." if probe or _has_operator_context(context) else
            "No endpoint or operator context was supplied; only local state is assessed.",
        ),
        _diagnostic_step(
            "link", "Check interfaces and link state",
            "failed" if any(item["severity"] == "critical" for item in phase_findings["link"]) else
            "warning" if phase_findings["link"] else "passed",
            f"Collected {len(interfaces)} interface(s); {len(active_interfaces)} non-loopback interface(s) appear active.",
            layer="OSI 1-2", depends_on=["context"],
        ),
        _diagnostic_step(
            "addressing", "Check local addressing", "passed" if interfaces else "warning",
            "Local interface addresses were inventoried." if interfaces else "Address inventory is unavailable.",
            layer="OSI 3", depends_on=["link"],
        ),
        _diagnostic_step(
            "local_routing", "Check the local routing prerequisite",
            "warning" if any(item.get("code") == "default_route_missing" for item in phase_findings["routing"]) else "passed",
            "A default route is present." if inventory.get("default_routes") else
            "No default route was found; directly connected targets may still be reachable.",
            layer="OSI 3", depends_on=["addressing"],
        ),
        _diagnostic_step(
            "dns", "Resolve the endpoint name",
            "failed" if phase_findings["dns"] else "not_applicable" if host_is_ip else "passed" if endpoint else "skipped",
            "The target is an IP address." if host_is_ip else
            "Name resolution succeeded." if endpoint and checks.get("dns", {}).get("status") == "ok" else
            "No endpoint was supplied." if not endpoint else "Name resolution failed.",
            layer="Application infrastructure", depends_on=["local_routing"],
        ),
        _diagnostic_step(
            "target_route", "Select the route to the resolved target",
            "failed" if any(
                item.get("code") == "probe_route_failed" and item.get("severity") == "critical"
                for item in phase_findings["routing"]
            ) else
            "passed" if route and route.get("status") == "ok" else
            "skipped" if not endpoint or checks.get("dns", {}).get("status") == "failed" else "not_applicable",
            "A target-specific route was selected." if route and route.get("status") == "ok" else
            "No target was supplied." if not endpoint else
            "Target route selection depends on successful name resolution." if checks.get("dns", {}).get("status") == "failed" else
            "Target-specific route lookup is unavailable on this platform.",
            layer="OSI 3", depends_on=["dns"],
        ),
        _diagnostic_step(
            "transport", "Open the target transport",
            "failed" if phase_findings["transport"] else "passed" if checks.get("tcp", {}).get("status") == "ok" else "skipped",
            "TCP connectivity succeeded." if checks.get("tcp", {}).get("status") == "ok" else
            checks.get("tcp", {}).get("reason", "No transport probe was run."),
            layer="OSI 4", depends_on=["target_route"],
        ),
        _diagnostic_step(
            "application", "Test TLS and application response",
            "failed" if phase_findings["application"] else "passed" if checks.get("application", {}).get("status") == "ok" else
            "warning" if checks.get("application", {}).get("status") == "warning" else "skipped",
            "The application responded." if checks.get("application") else "Supply an HTTP or HTTPS URL to test the application layer.",
            layer="OSI 6-7", depends_on=["transport"],
        ),
    ]
    return {
        "status": _diagnostic_status(findings),
        "read_only": True,
        "context": context,
        "methodology": _methodology(
            "network-bottom-up", "Define the path, then move from local link and addressing through routing, name resolution, transport, and application.", steps,
        ),
        "platform": platform.system(),
        "inventory": inventory,
        "listening_sockets": listeners,
        "probe": probe,
        "checks": checks,
        "cause_candidates": _rank_cause_candidates(findings),
        "findings": findings,
    }


def system_diagnostic(
    path: str = "/",
    include_du: bool = False,
    include_logs: bool = False,
    lines: int = 50,
    since: str = "1 hour ago",
    raw_logs: bool = False,
    timeout: float = 10.0,
    symptom: Optional[str] = None,
    expected: Optional[str] = None,
    recent_change: Optional[str] = None,
) -> Dict[str, Any]:
    """Collect a read-only host health overview with actionable findings."""
    _validate_log_options(lines, since)
    if timeout <= 0:
        raise ValueError("Timeout must be greater than zero")
    context = _diagnostic_context(socket.gethostname(), symptom, expected, recent_change)
    cpu_count = os.cpu_count() or 1
    load = None
    try:
        one, five, fifteen = os.getloadavg()
        load = {
            "one_minute": round(one, 2), "five_minutes": round(five, 2),
            "fifteen_minutes": round(fifteen, 2),
            "one_minute_per_cpu": round(one / cpu_count, 2),
        }
    except (AttributeError, OSError):
        pass
    uptime_seconds = None
    try:
        uptime_seconds = float(Path("/proc/uptime").read_text().split()[0])
    except (OSError, ValueError, IndexError):
        pass
    memory = _proc_memory()
    pressure = _linux_pressure()
    processes = _process_summary()
    time_sync = _time_sync_status(timeout)
    disk = disk_diagnostic(path, include_du=include_du, timeout=max(timeout, 30.0))
    findings = list(disk["findings"])
    if load and load["one_minute_per_cpu"] >= 2:
        findings.append(_finding(
            "load_critical", "critical", "One-minute load is at least twice the CPU count.",
            evidence=f"normalized load={load['one_minute_per_cpu']}",
            recommendation="Inspect runnable and uninterruptible processes, I/O pressure, and recent workload changes.",
            phase="resources",
        ))
    elif load and load["one_minute_per_cpu"] >= 1.2:
        findings.append(_finding(
            "load_high", "warning", "One-minute load is above the CPU count.",
            evidence=f"normalized load={load['one_minute_per_cpu']}",
            recommendation="Correlate CPU, I/O wait, and process activity before capacity is exhausted.",
            phase="resources",
        ))
    available_percent = memory.get("available_percent")
    if available_percent is not None and available_percent < 5:
        findings.append(_finding(
            "memory_critical", "critical", f"Available memory is critically low ({available_percent}%).",
            recommendation="Identify memory growth and OOM events before restarting or terminating a process.",
            phase="resources",
        ))
    elif available_percent is not None and available_percent < 10:
        findings.append(_finding(
            "memory_low", "warning", f"Available memory is low ({available_percent}%).",
            recommendation="Inspect working sets, cache pressure, swap activity, and recent growth.",
            phase="resources",
        ))
    swap_used_percent = memory.get("swap_used_percent")
    if isinstance(swap_used_percent, (int, float)) and swap_used_percent >= 90:
        findings.append(_finding(
            "swap_high", "warning", f"Swap usage is high ({memory['swap_used_percent']}%).",
            recommendation="Check whether swap-in activity is current before treating allocated swap as active pressure.",
            phase="resources",
        ))
    if processes.get("zombies", 0):
        zombie_count = processes["zombies"]
        findings.append(_finding(
            "zombie_processes", "warning" if zombie_count >= 5 else "info",
            f"{zombie_count} zombie process(es) detected.",
            recommendation="Identify and diagnose the parent process responsible for reaping child exit status.",
            phase="processes",
        ))
    if time_sync.get("ok") and time_sync.get("synchronized") is False:
        findings.append(_finding(
            "time_not_synchronized", "warning", "The service manager reports that system time is not synchronized.",
            recommendation="Check the configured NTP client, source reachability, offset, and recent clock changes.",
            phase="time",
        ))
    for resource, rows in pressure.items():
        full_avg10 = rows.get("full", {}).get("avg10", 0)
        if full_avg10 >= 10:
            findings.append(_finding(
                f"{resource}_pressure", "warning",
                f"Sustained {resource} pressure is elevated (full avg10={full_avg10}).",
                recommendation="Correlate pressure stalls with processes and resource saturation.",
                phase="resources",
            ))
    failed_services: List[str] = []
    service_manager = _service_manager()
    if service_manager == "systemd":
        command = _diagnostic_command(
            ["systemctl", "--failed", "--no-legend", "--plain", "--no-pager"],
            timeout=timeout,
        )
        if command["ok"]:
            failed_services = [line.strip() for line in command["stdout"].splitlines() if line.strip()][:100]
            if failed_services:
                findings.append(_finding(
                    "failed_services", "warning", f"{len(failed_services)} failed systemd unit(s) detected.",
                    recommendation="Run a targeted service diagnostic and inspect its journal before changing state.",
                    phase="services",
                ))
    journal: List[str] = []
    if include_logs:
        if shutil.which("journalctl"):
            command = _diagnostic_command(
                ["journalctl", "--no-pager", "-b", "-p", "emerg..err", "--since", since,
                 "-n", str(lines), "-o", "short-iso"],
                timeout=timeout,
            )
            selected = command["stdout"].splitlines()[-lines:]
            journal = selected if raw_logs else [_redact_log_line(line) for line in selected]
            if not command["ok"]:
                findings.append(_finding(
                    "system_logs_unavailable", "warning", "System journal could not be read.",
                    evidence=command.get("error"), recommendation="Check journal permissions for the current user.",
                    phase="logs",
                ))
        else:
            findings.append(_finding(
                "system_log_source_unavailable", "info", "journalctl is not available on this host.",
                recommendation="Inspect the platform's configured system log destination.",
                phase="logs",
            ))
    network = network_diagnostic(timeout=timeout)
    firewall = firewall_diagnostic(timeout=timeout)
    findings.extend(network["findings"])
    findings.extend(firewall["findings"])
    findings = _deduplicate_findings(findings)
    critical_resource = any(
        item.get("severity") == "critical" and item.get("phase") in {"resources", "capacity", "inodes", "mount"}
        for item in findings
    )
    warning_resource = any(
        item.get("severity") == "warning" and item.get("phase") in {"resources", "capacity", "inodes", "mount"}
        for item in findings
    )
    network_status = network.get("status", "ok")
    steps = [
        _diagnostic_step(
            "context", "Define symptom and time window", "passed" if _has_operator_context(context) else "warning",
            "Operator context was recorded." if _has_operator_context(context) else
            "No symptom, expectation, or recent change was supplied; this is a point-in-time health snapshot.",
        ),
        _diagnostic_step(
            "identity", "Identify host and uptime", "passed",
            f"Collected identity for {socket.gethostname()} with {cpu_count} CPU(s).", depends_on=["context"],
        ),
        _diagnostic_step(
            "resources", "Check saturation and hard capacity blockers",
            "failed" if critical_resource else "warning" if warning_resource else "passed",
            "Checked load, memory, pressure stalls, filesystem capacity, inodes, and mount state.",
            depends_on=["identity"],
        ),
        _diagnostic_step(
            "processes", "Check process health", "warning" if processes.get("zombies", 0) else "passed",
            f"Inspected {processes.get('total', 0)} process(es)." if processes else "Process accounting is unavailable.",
            depends_on=["resources"],
        ),
        _diagnostic_step(
            "services", "Check failed services",
            "warning" if failed_services else "passed" if service_manager == "systemd" else "not_applicable",
            f"Found {len(failed_services)} failed systemd unit(s)." if failed_services else
            "No failed systemd units were reported." if service_manager == "systemd" else
            "Global failed-unit enumeration is not available for this service manager.",
            depends_on=["resources"],
        ),
        _diagnostic_step(
            "logs", "Inspect severe events in the selected time window",
            "warning" if any(item.get("phase") == "logs" and item.get("severity") == "warning" for item in findings) else
            "passed" if include_logs else "skipped",
            f"Collected {len(journal)} redacted severe journal line(s) since {since}." if journal else
            "Log content was not requested." if not include_logs else "No severe journal entries were returned.",
            depends_on=["services"],
        ),
        _diagnostic_step(
            "network", "Check local network prerequisites",
            "failed" if network_status == "failed" else "warning" if network_status == "warning" else "passed",
            "Ran the bottom-up local network diagnostic.", depends_on=["identity"],
        ),
        _diagnostic_step(
            "firewall", "Discover local host firewall controls",
            "failed" if firewall.get("status") == "failed" else
            "warning" if firewall.get("status") == "warning" or any(
                item.get("inspection") in {"permission_limited", "failed"}
                for item in firewall.get("backends", [])
            ) else "passed",
            f"Observed {len(firewall.get('active_backends', []))} active supported firewall control(s).",
            layer="OSI 3-4", depends_on=["network"],
        ),
    ]
    return {
        "status": _diagnostic_status(findings),
        "read_only": True,
        "context": context,
        "methodology": _methodology(
            "host-health", "Define the symptom, rule out hard resource blockers, inspect processes and services, correlate logs, then verify network and host-firewall prerequisites.", steps,
        ),
        "host": {
            "hostname": socket.gethostname(), "platform": platform.system(),
            "release": platform.release(), "architecture": platform.machine(),
            "python": platform.python_version(), "cpu_count": cpu_count,
            "uptime_seconds": uptime_seconds,
        },
        "load": load,
        "memory": memory,
        "pressure": pressure,
        "processes": processes,
        "time_sync": time_sync,
        "disk": disk,
        "network": network,
        "firewall": firewall,
        "failed_services": failed_services,
        "journal": journal,
        "logs_requested": include_logs,
        "logs_collected": bool(journal),
        "log_source": "journalctl" if include_logs and shutil.which("journalctl") else None,
        "logs_included": include_logs,
        "logs_redacted": include_logs and not raw_logs,
        "cause_candidates": _rank_cause_candidates(findings),
        "findings": findings,
    }


def _nginx_build_details(text: str) -> Dict[str, Any]:
    details: Dict[str, Any] = {"raw_version": None, "configure_arguments": {}}
    version = re.search(r"nginx version:\s*nginx/([^\s]+)", text)
    if version:
        details["version"] = version.group(1)
        details["raw_version"] = version.group(0)
    arguments = re.search(r"configure arguments:\s*(.+)", text)
    if arguments:
        try:
            tokens = shlex.split(arguments.group(1))
        except ValueError:
            tokens = arguments.group(1).split()
        for token in tokens:
            if token.startswith("--"):
                key, separator, value = token[2:].partition("=")
                details["configure_arguments"][key] = value if separator else True
    return details


def _nginx_resolve_path(value: str, prefix: str) -> Optional[str]:
    value = value.strip().strip('"\'')
    if not value or value in {"off", "stderr"} or value.startswith("syslog:") or "$" in value:
        return None
    if re.match(r"^[A-Za-z]:[\\/]", value):
        return str(PureWindowsPath(value))
    if value.startswith("/"):
        return str(PurePosixPath(value))
    if re.match(r"^[A-Za-z]:[\\/]", prefix):
        return str(PureWindowsPath(prefix) / PureWindowsPath(value))
    if prefix.startswith("/"):
        return str(PurePosixPath(prefix) / PurePosixPath(value))
    return str(Path(prefix) / Path(value))


def _strip_nginx_comments(text: str) -> str:
    cleaned = []
    for line in text.splitlines():
        quote = None
        escaped = False
        output_line = []
        for char in line:
            if escaped:
                output_line.append(char)
                escaped = False
                continue
            if char == "\\":
                output_line.append(char)
                escaped = True
                continue
            if char in {'"', "'"}:
                quote = None if quote == char else char if quote is None else quote
            if char == "#" and quote is None:
                break
            output_line.append(char)
        cleaned.append("".join(output_line))
    return "\n".join(cleaned)


def _redact_nginx_endpoint(value: str) -> str:
    value = re.sub(r"(://)[^/@\s]+@", r"\1[REDACTED]@", value)
    return _redact_log_line(value)


def _parse_nginx_configuration(text: str, build: Dict[str, Any]) -> Dict[str, Any]:
    arguments = build.get("configure_arguments", {})
    prefix = str(arguments.get("prefix") or "/usr/local/nginx")
    config_files = re.findall(r"^# configuration file (.+):$", text, re.MULTILINE)
    directives: Dict[str, List[str]] = {
        name: [] for name in (
            "user", "pid", "error_log", "access_log", "root", "alias", "index", "listen",
            "server_name", "ssl_certificate", "ssl_certificate_key", "proxy_pass", "fastcgi_pass",
            "try_files",
        )
    }
    names = "|".join(re.escape(name) for name in directives)
    cleaned = _strip_nginx_comments(text)
    for match in re.finditer(rf"(?m)^\s*({names})\s+([^;]+);", cleaned):
        directives[match.group(1)].append(" ".join(match.group(2).split()))
    worker_user = None
    worker_group = None
    if directives["user"]:
        fields = directives["user"][0].split()
        worker_user = fields[0] if fields else None
        worker_group = fields[1] if len(fields) > 1 else None
    paths: Dict[str, List[str]] = {
        "roots": [], "aliases": [], "error_logs": [], "access_logs": [], "certificates": [],
    }
    for key, destination in (("root", "roots"), ("alias", "aliases")):
        for root in directives[key]:
            resolved = _nginx_resolve_path(root, prefix)
            if resolved:
                paths[destination].append(resolved)
    for key, destination in (("error_log", "error_logs"), ("access_log", "access_logs")):
        for value in directives[key]:
            try:
                first = shlex.split(value)[0]
            except (ValueError, IndexError):
                first = value.split()[0] if value.split() else ""
            resolved = _nginx_resolve_path(first, prefix)
            if resolved:
                paths[destination].append(resolved)
    for key in ("ssl_certificate", "ssl_certificate_key"):
        for value in directives[key]:
            resolved = _nginx_resolve_path(value.split()[0], prefix)
            if resolved:
                paths["certificates"].append(resolved)
    listeners = []
    ports = []
    unix_sockets = []
    for value in directives["listen"]:
        try:
            tokens = shlex.split(value)
        except ValueError:
            tokens = value.split()
        if not tokens:
            continue
        endpoint = tokens[0]
        options = tokens[1:]
        if endpoint.startswith("unix:"):
            socket_path = _nginx_resolve_path(endpoint[5:], prefix)
            if socket_path:
                unix_sockets.append(socket_path)
                listeners.append({
                    "family": "unix", "path": socket_path, "raw": value,
                    "ssl": "ssl" in options,
                })
            continue
        port = None
        address = "*"
        if endpoint.isdigit():
            port = int(endpoint)
        elif endpoint.startswith("["):
            listen_address = re.fullmatch(r"(\[[^]]+])(?::(\d+))?", endpoint)
            if listen_address:
                address = listen_address.group(1)
                port = int(listen_address.group(2)) if listen_address.group(2) else 80
        elif ":" in endpoint:
            address, separator, port_text = endpoint.rpartition(":")
            if separator and port_text.isdigit():
                port = int(port_text)
        else:
            address = endpoint
            port = 80
        listeners.append({
            "family": "ip", "address": address, "port": port, "raw": value,
            "ssl": "ssl" in options, "default_server": "default_server" in options,
        })
        if port is not None and port not in ports:
            ports.append(port)
    return {
        "prefix": prefix,
        "config_files": list(dict.fromkeys(config_files)),
        "worker_user": worker_user,
        "worker_group": worker_group,
        "paths": {key: list(dict.fromkeys(values)) for key, values in paths.items()},
        "listeners": listeners,
        "listen_ports": ports,
        "unix_sockets": list(dict.fromkeys(unix_sockets)),
        "implicit_listen": not bool(directives["listen"]),
        "implicit_port_candidates": [80, 8000] if not directives["listen"] else [],
        "explicit_error_log": bool(directives["error_log"]),
        "explicit_access_log": bool(directives["access_log"]),
        "server_names": list(dict.fromkeys(directives["server_name"])),
        "indexes": list(dict.fromkeys(directives["index"])),
        "try_files": list(dict.fromkeys(directives["try_files"])),
        "upstreams": list(dict.fromkeys(
            _redact_nginx_endpoint(value)
            for value in directives["proxy_pass"] + directives["fastcgi_pass"]
        )),
    }


def _path_access_for_user(
    path: str,
    username: Optional[str],
    groupname: Optional[str] = None,
) -> Dict[str, Any]:
    result: Dict[str, Any] = {
        "path": path, "user": username, "group": groupname, "exists": Path(path).exists(),
    }
    if not username or platform.system().lower() == "windows":
        return result
    try:
        import grp
        import pwd
        account = pwd.getpwnam(username)
        group_ids = {account.pw_gid}
        group_ids.update(entry.gr_gid for entry in grp.getgrall() if username in entry.gr_mem)
        if groupname:
            group_ids.add(grp.getgrnam(groupname).gr_gid)
    except (ImportError, KeyError, OSError):
        result["error"] = f"user not found or account database unavailable: {username}"
        return result
    candidate = Path(path)
    chain = list(candidate.parents)
    if candidate.exists() and candidate.is_dir():
        chain.insert(0, candidate)
    blocker: Optional[Dict[str, Any]] = None
    for directory in reversed(chain):
        if not directory.exists():
            continue
        try:
            details = directory.stat()
        except OSError as exc:
            blocker = {"path": str(directory), "error": str(exc)}
            break
        if account.pw_uid == 0:
            allowed = True
        elif details.st_uid == account.pw_uid:
            allowed = bool(details.st_mode & stat.S_IXUSR)
        elif details.st_gid in group_ids:
            allowed = bool(details.st_mode & stat.S_IXGRP)
        else:
            allowed = bool(details.st_mode & stat.S_IXOTH)
        if not allowed:
            blocker = {
                "path": str(directory), "mode": oct(stat.S_IMODE(details.st_mode)),
                "uid": details.st_uid, "gid": details.st_gid,
            }
            break
    result["traversable"] = blocker is None
    result["blocker"] = blocker
    result["caveat"] = "POSIX mode-bit check; ACL and security-module policy are evaluated separately."
    return result


def _security_frameworks(paths: List[str], timeout: float) -> Dict[str, Any]:
    result: Dict[str, Any] = {"selinux": None, "apparmor": None, "path_contexts": []}
    if shutil.which("getenforce"):
        command = _diagnostic_command(["getenforce"], timeout=timeout)
        result["selinux"] = command["stdout"].strip() or command.get("error")
    apparmor = Path("/sys/module/apparmor/parameters/enabled")
    if apparmor.is_file():
        try:
            result["apparmor"] = apparmor.read_text().strip()
        except OSError:
            result["apparmor"] = "unknown"
    if paths and shutil.which("ls"):
        for path in paths[:50]:
            command = _diagnostic_command(["ls", "-Zd", path], timeout=timeout, max_output=8192)
            if command["ok"]:
                result["path_contexts"].append(command["stdout"].strip())
    return result


def _nginx_log_findings(error_lines: List[str], access_lines: List[str]) -> List[Dict[str, Any]]:
    findings = []
    error_text = "\n".join(error_lines).lower()
    signatures = [
        ("permission denied", "nginx_permission_denied", "critical", "Nginx logged a permission denial.", "Check every parent-directory execute bit, file read access, ACLs, SELinux, and AppArmor policy."),
        ("directory index of", "nginx_directory_index", "warning", "A directory index request was forbidden.", "Confirm the intended index file or explicitly configure directory listing only where appropriate."),
        ("access forbidden by rule", "nginx_access_rule", "warning", "An Nginx access rule rejected a request.", "Review allow/deny, auth, and location precedence for the affected URI."),
        ("no such file or directory", "nginx_path_missing", "warning", "Nginx referenced a missing path.", "Confirm root/alias resolution, deployment output, includes, certificates, and socket paths."),
        ("connect() failed", "nginx_upstream_connect", "critical", "Nginx could not connect to an upstream.", "Check the upstream service, socket permissions, address family, port, and security policy."),
        ("upstream timed out", "nginx_upstream_timeout", "warning", "An upstream timed out.", "Measure upstream latency and capacity before changing proxy timeout values."),
        ("no space left on device", "nginx_no_space", "critical", "Nginx encountered a full filesystem or exhausted inodes.", "Inspect both capacity and inode usage on log, cache, temporary, and content filesystems."),
        ("too many open files", "nginx_file_descriptors", "critical", "Nginx exhausted file descriptors.", "Compare worker_connections, process limits, active connections, and upstream usage."),
        ("address already in use", "nginx_bind_collision", "critical", "Nginx could not bind a configured address.", "Identify the process already listening and check duplicate listen directives."),
        ("cannot load certificate", "nginx_certificate_load", "critical", "Nginx could not load a TLS certificate or key.", "Check paths, syntax, file readability, key format, and certificate/key pairing."),
    ]
    for needle, code, severity, summary, recommendation in signatures:
        if needle in error_text:
            findings.append(_finding(code, severity, summary, evidence=needle, recommendation=recommendation))
    statuses: Counter = Counter()
    for line in access_lines:
        match = re.search(r'"\s(\d{3})\s', line)
        if match:
            statuses[match.group(1)] += 1
    total = sum(statuses.values())
    if total:
        errors_5xx = sum(count for status, count in statuses.items() if status.startswith("5"))
        forbidden = statuses.get("403", 0)
        missing = statuses.get("404", 0)
        if errors_5xx:
            findings.append(_finding(
                "nginx_access_5xx", "warning", f"Recent access-log sample contains {errors_5xx}/{total} server errors.",
                recommendation="Correlate timestamps and request IDs with the error log and upstream health.",
            ))
        if forbidden:
            findings.append(_finding(
                "nginx_access_403", "warning", f"Recent access-log sample contains {forbidden}/{total} HTTP 403 responses.",
                recommendation="Check location policy, authentication, filesystem traversal, ACLs, SELinux, and AppArmor.",
            ))
        if missing:
            findings.append(_finding(
                "nginx_access_404", "info", f"Recent access-log sample contains {missing}/{total} HTTP 404 responses.",
                recommendation="Confirm whether the paths are expected traffic, stale links, probes, or deployment omissions.",
            ))
    return findings


def _host_from_authority(value: str) -> str:
    """Extract and validate the host portion of an HTTP authority value."""
    authority = value.strip()
    if not authority or len(authority) > 255 or any(ord(char) < 33 for char in authority):
        raise ValueError("Invalid Host header or TLS server name")
    if authority.startswith("["):
        closing = authority.find("]")
        if closing < 0:
            raise ValueError("Invalid bracketed Host header")
        host = authority[1:closing]
        remainder = authority[closing + 1:]
        if remainder and (not remainder.startswith(":") or not remainder[1:].isdigit()):
            raise ValueError("Invalid Host header port")
        if remainder:
            _validate_port(int(remainder[1:]))
    elif authority.count(":") == 1 and authority.rsplit(":", 1)[1].isdigit():
        host, port_text = authority.rsplit(":", 1)
        _validate_port(int(port_text))
    else:
        host = authority
    return _validate_host(host)


def _http_probe_once(
    url: str,
    host_header: Optional[str],
    timeout: float,
    sni: Optional[str],
    verify_tls: bool,
) -> Dict[str, Any]:
    """Make one direct HEAD request without environment proxies or redirects."""
    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Probe URL must use http:// or https://")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("Credentials are not accepted in diagnostic probe URLs")
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError as exc:
        raise ValueError(f"Invalid probe URL port: {exc}")
    connect_host = _validate_host(parsed.hostname)
    default_port = 443 if parsed.scheme == "https" else 80
    formatted_host = f"[{connect_host}]" if ":" in connect_host else connect_host
    authority = formatted_host if port == default_port else f"{formatted_host}:{port}"
    request_host = host_header or authority
    request_name = _host_from_authority(request_host)
    tls_name = _host_from_authority(sni) if sni else request_name if parsed.scheme == "https" else None
    path = urllib.parse.quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
    if parsed.query:
        path += "?" + urllib.parse.quote(parsed.query, safe="=&;%:@!$'()*+,-._~/?")
    request = (
        f"HEAD {path} HTTP/1.1\r\n"
        f"Host: {request_host}\r\n"
        f"User-Agent: SysAdminToolbox/{__version__}\r\n"
        "Accept: */*\r\n"
        "Connection: close\r\n\r\n"
    ).encode("ascii", errors="strict")
    started = time.monotonic()
    connection = None
    try:
        connection = socket.create_connection((connect_host, port), timeout=timeout)
        connection.settimeout(timeout)
        tls_details = None
        if parsed.scheme == "https":
            context = ssl.create_default_context()
            if not verify_tls:
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE
            connection = context.wrap_socket(connection, server_hostname=tls_name)
            cipher = connection.cipher()
            certificate = connection.getpeercert()
            tls_details = {
                "verified": verify_tls,
                "server_name": tls_name,
                "version": connection.version(),
                "cipher": cipher[0] if cipher else None,
                "certificate_subject": certificate.get("subject") if certificate else None,
                "subject_alt_names": certificate.get("subjectAltName") if certificate else None,
            }
        connection.sendall(request)
        response = http.client.HTTPResponse(connection)
        response.begin()
        headers = {key.lower(): value for key, value in response.getheaders()}
        status = "failed" if response.status >= 500 else "warning" if response.status >= 400 else "ok"
        return {
            "status": status,
            "status_code": response.status,
            "reason": response.reason,
            "url": _redact_url(url),
            "connect_host": connect_host,
            "host_header": request_host,
            "tls": tls_details,
            "server": headers.get("server"),
            "location": headers.get("location"),
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        }
    except (ssl.SSLError, socket.timeout, OSError, ValueError, http.client.HTTPException) as exc:
        return {
            "status": "failed", "url": _redact_url(url), "connect_host": connect_host,
            "host_header": request_host, "tls_server_name": tls_name,
            "error": str(exc), "error_type": type(exc).__name__,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        }
    finally:
        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass


def _http_status_probe(
    url: str,
    host_header: Optional[str],
    timeout: float,
    sni: Optional[str] = None,
    follow_redirects: bool = False,
    verify_tls: bool = True,
    max_redirects: int = 5,
) -> Dict[str, Any]:
    """Probe an HTTP endpoint directly, with explicit Host/SNI and redirect policy."""
    if timeout <= 0:
        raise ValueError("Timeout must be greater than zero")
    if not 0 <= max_redirects <= 10:
        raise ValueError("Maximum redirects must be between 0 and 10")
    started = time.monotonic()
    current = url
    chain = []
    for redirect_index in range(max_redirects + 1):
        result = _http_probe_once(
            current,
            host_header if redirect_index == 0 else None,
            timeout,
            sni if redirect_index == 0 else None,
            verify_tls,
        )
        chain.append({
            key: result.get(key) for key in ("url", "status_code", "location", "connect_host", "host_header")
            if result.get(key) is not None
        })
        code = result.get("status_code")
        location = result.get("location")
        if not (follow_redirects and code in {301, 302, 303, 307, 308} and location):
            result["initial_url"] = _redact_url(url)
            result["final_url"] = result.get("url", _redact_url(current))
            result["redirected"] = len(chain) > 1
            result["redirect_chain"] = chain
            result["redirect_policy"] = "follow" if follow_redirects else "stop"
            result["proxy_policy"] = "direct"
            result["elapsed_ms_total"] = round((time.monotonic() - started) * 1000, 2)
            return result
        if redirect_index == max_redirects:
            return {
                "status": "failed", "error": f"redirect limit exceeded ({max_redirects})",
                "initial_url": _redact_url(url), "final_url": _redact_url(current),
                "redirected": True, "redirect_chain": chain, "redirect_policy": "follow",
                "proxy_policy": "direct",
                "elapsed_ms_total": round((time.monotonic() - started) * 1000, 2),
            }
        next_url = urllib.parse.urljoin(current, location)
        next_target = urllib.parse.urlsplit(next_url)
        if (
            next_target.scheme not in {"http", "https"}
            or not next_target.hostname
            or next_target.username is not None
            or next_target.password is not None
        ):
            return {
                "status": "failed", "error": "redirect target is not a credential-free HTTP/HTTPS URL",
                "initial_url": _redact_url(url), "final_url": _redact_url(current),
                "redirected": True, "redirect_chain": chain, "redirect_policy": "follow",
                "proxy_policy": "direct",
                "elapsed_ms_total": round((time.monotonic() - started) * 1000, 2),
            }
        current = next_url
    raise RuntimeError("unreachable redirect state")


def _discover_nginx_runtime(processes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Extract a running master process binary and safe path arguments."""
    for process in processes:
        command = str(process.get("command") or "")
        marker = re.search(r"\bmaster process\s+(.+)$", command)
        if not marker:
            continue
        try:
            tokens = shlex.split(marker.group(1))
        except ValueError:
            tokens = marker.group(1).split()
        if not tokens:
            continue
        candidate = Path(tokens[0]).expanduser()
        result: Dict[str, Any] = {
            "pid": process.get("pid"),
            "binary": str(candidate.resolve()) if candidate.is_file() else str(candidate),
            "binary_exists": candidate.is_file(),
            "config": None,
            "prefix": None,
        }
        index = 1
        while index < len(tokens):
            token = tokens[index]
            if token in {"-c", "-p"} and index + 1 < len(tokens):
                key = "config" if token == "-c" else "prefix"
                result[key] = tokens[index + 1]
                index += 2
                continue
            index += 1
        return result
    return {"pid": None, "binary": None, "binary_exists": False, "config": None, "prefix": None}


def nginx_diagnostic(
    service_name: str = "nginx",
    binary: str = "nginx",
    config: Optional[str] = None,
    url: Optional[str] = None,
    host_header: Optional[str] = None,
    log_mode: str = "none",
    lines: int = 50,
    since: str = "1 hour ago",
    raw_logs: bool = False,
    timeout: float = 10.0,
    sni: Optional[str] = None,
    follow_redirects: bool = False,
    verify_tls: bool = True,
    symptom: Optional[str] = None,
    expected: Optional[str] = None,
    recent_change: Optional[str] = None,
) -> Dict[str, Any]:
    """Diagnose Nginx through an ordered, read-only dependency path."""
    if log_mode not in {"none", "service", "error", "access", "all"}:
        raise ValueError("Invalid log mode")
    _validate_log_options(lines, since)
    _validate_config_name(service_name.removesuffix(".service"), "service name", max_length=128)
    context = _diagnostic_context(url or service_name, symptom, expected, recent_change)
    if host_header:
        _host_from_authority(host_header)
    if sni:
        _host_from_authority(sni)
    findings = []
    root_disk = disk_diagnostic("/")
    findings.extend(root_disk["findings"])
    include_service_logs = log_mode in {"service", "all"}
    service = service_diagnostic(
        service_name, include_logs=include_service_logs, lines=lines, since=since,
        raw_logs=raw_logs, timeout=timeout, symptom=symptom, expected=expected,
        recent_change=recent_change,
    )
    findings.extend(service["findings"])
    runtime = _discover_nginx_runtime(service.get("processes", []))
    executable = binary if os.path.sep in binary else shutil.which(binary)
    if (not executable or not Path(executable).is_file()) and binary == "nginx" and runtime.get("binary_exists"):
        executable = runtime["binary"]
    effective_config = config or (runtime.get("config") if binary == "nginx" else None)
    build: Dict[str, Any] = {}
    syntax: Dict[str, Any] = {"tested": False}
    parsed: Dict[str, Any] = {
        "prefix": None, "config_files": [], "worker_user": None, "worker_group": None,
        "paths": {"roots": [], "aliases": [], "error_logs": [], "access_logs": [], "certificates": []},
        "listeners": [], "listen_ports": [], "unix_sockets": [], "implicit_listen": False,
        "implicit_port_candidates": [], "server_names": [], "upstreams": [], "indexes": [], "try_files": [],
        "explicit_error_log": False, "explicit_access_log": False,
    }
    if not executable or not Path(executable).is_file():
        findings.append(_finding(
            "nginx_binary_missing", "critical", f"Nginx binary was not found: {binary}",
            recommendation="Confirm the package installation or pass the binary path with --binary.",
            phase="runtime",
        ))
    else:
        version_command = _diagnostic_command([str(executable), "-V"], timeout=timeout)
        build = _nginx_build_details(version_command["stdout"] + version_command["stderr"])
        config_args = []
        if runtime.get("prefix") and not config:
            config_args.extend(["-p", str(runtime["prefix"])])
        if effective_config:
            config_args.extend(["-c", str(effective_config)])
        test_command = _diagnostic_command([str(executable), "-t"] + config_args, timeout=timeout)
        test_text = "\n".join(
            _redact_log_line(line) for line in (test_command["stdout"] + test_command["stderr"]).splitlines()
        )
        syntax = {
            "tested": True, "ok": test_command["ok"], "returncode": test_command["returncode"],
            "diagnostic": test_text[-16384:], "elapsed_ms": test_command["elapsed_ms"],
        }
        if not test_command["ok"]:
            findings.append(_finding(
                "nginx_config_invalid", "critical", "Nginx configuration validation failed.",
                evidence=test_text[-4096:], recommendation="Resolve the reported syntax, include, path, or permission error before reloading Nginx.",
                phase="configuration",
            ))
        dump_command = _diagnostic_command([str(executable), "-T"] + config_args, timeout=timeout)
        if dump_command["stdout"]:
            parsed = _parse_nginx_configuration(dump_command["stdout"], build)
        elif not dump_command["ok"]:
            findings.append(_finding(
                "nginx_config_dump_unavailable", "warning", "Expanded Nginx configuration could not be inspected.",
                evidence=_redact_log_line(dump_command.get("error") or "nginx -T failed"),
                recommendation="Run the diagnostic with an account allowed to read every included configuration file.",
                phase="configuration",
            ))
    build_args = build.get("configure_arguments", {})
    if not parsed["paths"]["error_logs"] and not parsed.get("explicit_error_log"):
        default_error = build_args.get("error-log-path") or "/var/log/nginx/error.log"
        resolved = _nginx_resolve_path(str(default_error), str(parsed.get("prefix") or "/"))
        if resolved:
            parsed["paths"]["error_logs"].append(resolved)
    if not parsed["paths"]["access_logs"] and not parsed.get("explicit_access_log"):
        default_access = build_args.get("http-log-path") or "/var/log/nginx/access.log"
        resolved = _nginx_resolve_path(str(default_access), str(parsed.get("prefix") or "/"))
        if resolved:
            parsed["paths"]["access_logs"].append(resolved)
    log_files: Dict[str, List[Dict[str, Any]]] = {"error": [], "access": []}
    error_lines: List[str] = []
    access_lines: List[str] = []
    for kind, paths in (("error", parsed["paths"]["error_logs"]), ("access", parsed["paths"]["access_logs"])):
        include = log_mode in {kind, "all"}
        for path in paths[:50]:
            record = _tail_log_file(path, lines=lines, include_content=include, raw=raw_logs)
            log_files[kind].append(record)
            if include:
                if kind == "error":
                    error_lines.extend(record.get("lines", []))
                else:
                    access_lines.extend(record.get("lines", []))
    for item in _nginx_log_findings(error_lines, access_lines):
        item["phase"] = "application_logs"
        findings.append(item)
    path_checks = []
    relevant_paths = (
        parsed["paths"]["roots"] + parsed["paths"]["aliases"] + parsed["paths"]["certificates"] +
        parsed["paths"]["error_logs"] + parsed["paths"]["access_logs"]
    )
    worker_user = parsed.get("worker_user")
    sockets = _listening_sockets(timeout)
    listening_ports = {item.get("port") for item in sockets["listeners"]}
    listening_unix = {item.get("path") for item in sockets["listeners"] if item.get("family") == "unix"}
    runtime_active = bool(service.get("processes")) or service.get("details", {}).get("ActiveState") == "active"
    for port in parsed.get("listen_ports", []):
        if sockets.get("available") and runtime_active and port not in listening_ports:
            findings.append(_finding(
                "nginx_listener_missing", "critical", f"Configured port {port} was not found in the listening-socket table.",
                recommendation="Check bind addresses, namespace/container boundaries, socket activation, and startup logs.",
                phase="listeners",
            ))
    for path in parsed.get("unix_sockets", []):
        if sockets.get("available") and runtime_active and path not in listening_unix:
            findings.append(_finding(
                "nginx_unix_listener_missing", "critical", f"Configured Unix listener was not found: {path}",
                recommendation="Check the effective listen directive, socket directory permissions, process namespace, and startup logs.",
                phase="listeners",
            ))
    if parsed.get("implicit_listen") and sockets.get("available") and runtime_active:
        candidates = set(parsed.get("implicit_port_candidates", []))
        if not candidates.intersection(listening_ports):
            findings.append(_finding(
                "nginx_implicit_listener_unconfirmed", "warning",
                "No listener was found on either implicit Nginx default port.",
                evidence="expected one of 80 or 8000",
                recommendation="Confirm the master-process privileges, network namespace, and effective server configuration.",
                phase="listeners",
            ))
    firewall = firewall_diagnostic(parsed.get("listen_ports", []), timeout=timeout)
    findings.extend(firewall["findings"])
    http_probe = None
    branch_summary = "No HTTP symptom was supplied."
    if url:
        http_probe = _http_status_probe(
            url, host_header, timeout, sni=sni, follow_redirects=follow_redirects,
            verify_tls=verify_tls,
        )
        code = http_probe.get("status_code")
        if http_probe["status"] == "failed":
            if str(http_probe.get("error_type", "")).startswith("SSL"):
                branch_summary = "The TLS handshake or certificate verification failed."
                findings.append(_finding(
                    "nginx_tls_probe_failed", "critical", branch_summary,
                    evidence=str(http_probe.get("error")),
                    recommendation="Check SNI, certificate names, trust chain, validity, protocols, and certificate/key loading.",
                    phase="application",
                ))
            elif code in {502, 503, 504}:
                branch_summary = f"HTTP {code} points to upstream availability or latency."
                findings.append(_finding(
                    "nginx_upstream_http_failure", "critical", branch_summary,
                    evidence=str(code),
                    recommendation="Check the selected upstream, its process/socket, DNS, route, capacity, and timeout evidence.",
                    phase="application",
                ))
            else:
                branch_summary = "The HTTP connection failed or returned a server error."
                findings.append(_finding(
                    "nginx_http_failed", "critical", branch_summary,
                    evidence=str(http_probe.get("error") or code),
                    recommendation="Keep successful lower-layer checks and correlate listener state, logs, virtual-host selection, and upstream health.",
                    phase="application",
                ))
        elif code == 403:
            branch_summary = "HTTP 403 selects the access-policy and filesystem-permission branch."
            findings.append(_finding(
                "nginx_http_403", "warning", "HTTP probe returned 403 Forbidden.",
                recommendation="Check access rules, authentication, root/alias traversal, ACLs, SELinux, and AppArmor.",
                phase="application",
            ))
        elif code == 404:
            branch_summary = "HTTP 404 selects the virtual-host, location, and deployment-path branch."
            findings.append(_finding(
                "nginx_http_404", "warning", "HTTP probe returned 404 Not Found.",
                recommendation="Check virtual-host selection, location precedence, root/alias mapping, and deployed files.",
                phase="application",
            ))
        elif code in {401}:
            branch_summary = "HTTP 401 selects the authentication-policy branch."
            findings.append(_finding(
                "nginx_http_401", "warning", "HTTP probe returned 401 Unauthorized.",
                recommendation="Confirm that the selected virtual host and location require the intended authentication scheme.",
                phase="application",
            ))
        elif code in {301, 302, 303, 307, 308} and not follow_redirects:
            branch_summary = "A redirect was observed and intentionally not followed."
            findings.append(_finding(
                "nginx_http_redirect", "info", f"HTTP probe returned redirect {code}.",
                evidence=str(http_probe.get("location") or "location not provided"),
                recommendation="Inspect the Location target or repeat with --follow-redirects when leaving the original endpoint is intended.",
                phase="application",
            ))
        else:
            branch_summary = f"HTTP {code} confirms an application response."
        if not verify_tls and urllib.parse.urlsplit(url).scheme == "https":
            findings.append(_finding(
                "nginx_tls_verification_disabled", "warning", "TLS certificate verification was explicitly disabled.",
                recommendation="Repeat with verification enabled before treating the HTTPS path as healthy.",
                phase="application",
            ))
    for path in (parsed["paths"]["roots"] + parsed["paths"]["aliases"])[:100]:
        if not Path(path).exists():
            findings.append(_finding(
                "nginx_document_root_missing", "warning", f"Configured document root does not exist: {path}",
                recommendation="Confirm the active virtual host, deployment path, and root/alias mapping.",
                phase="path_access",
            ))
        check_path = path if Path(path).exists() else str(Path(path).parent)
        check = _path_access_for_user(check_path, worker_user, parsed.get("worker_group"))
        path_checks.append(check)
        if check.get("traversable") is False:
            findings.append(_finding(
                "nginx_path_permission", "critical", f"Worker user '{worker_user}' cannot traverse a required path.",
                evidence=str(check.get("blocker")),
                recommendation="Review ownership, POSIX mode bits, ACLs, and security-module policy; do not recursively chmod content.",
                phase="path_access",
            ))
    for path in parsed["paths"]["certificates"]:
        if not Path(path).is_file():
            findings.append(_finding(
                "nginx_certificate_missing", "critical", f"Configured TLS file does not exist: {path}",
                recommendation="Confirm the certificate/key deployment path and configuration include selected by nginx -T.",
                phase="configuration",
            ))
    security = _security_frameworks(list(dict.fromkeys(relevant_paths)), timeout)
    disk_paths = {"/"}
    for path in relevant_paths:
        candidate = Path(path)
        if candidate.exists():
            measured = candidate if candidate.is_dir() else candidate.parent
            mount = _mount_details(measured)
            disk_paths.add(str(mount["mountpoint"]) if mount else str(measured))
    disks = [root_disk if path == "/" else disk_diagnostic(path) for path in sorted(disk_paths)]
    for disk in disks:
        if disk is not root_disk:
            findings.extend(disk["findings"])
    findings = _deduplicate_findings(findings)
    phase_findings = {
        phase: [item for item in findings if item.get("phase") == phase]
        for phase in (
            "runtime", "configuration", "application_logs", "listeners",
            "firewall", "application", "path_access",
        )
    }
    config_status = (
        "failed" if any(item.get("severity") == "critical" for item in phase_findings["configuration"]) else
        "warning" if phase_findings["configuration"] else
        "passed" if syntax.get("ok") and parsed.get("config_files") else
        "warning" if syntax.get("ok") else "skipped"
    )
    listener_status = (
        "failed" if any(item.get("severity") == "critical" for item in phase_findings["listeners"]) else
        "warning" if phase_findings["listeners"] else "passed" if sockets.get("available") else "not_applicable"
    )
    application_status = (
        "failed" if http_probe and http_probe.get("status") == "failed" else
        "warning" if http_probe and http_probe.get("status") == "warning" else
        "passed" if http_probe else "skipped"
    )
    steps = [
        _diagnostic_step(
            "context", "Define symptom, endpoint, and recent change",
            "passed" if url or _has_operator_context(context) else "warning",
            "Diagnostic context was supplied." if url or _has_operator_context(context) else
            "No URL or operator context was supplied; the result is a readiness snapshot.",
        ),
        _diagnostic_step(
            "host_prerequisites", "Rule out hard host blockers",
            "failed" if root_disk.get("status") == "failed" else "warning" if root_disk.get("status") == "warning" else "passed",
            "Checked root filesystem capacity, inodes, and mount state.", depends_on=["context"],
        ),
        _diagnostic_step(
            "runtime", "Correlate service manager, processes, and binary",
            "failed" if not executable else "warning" if service.get("status") == "warning" else
            "failed" if service.get("status") == "failed" and not service.get("processes") else "passed",
            f"Using {executable}." if executable else "No executable could be resolved.",
            depends_on=["host_prerequisites"],
            evidence={"service_manager": service.get("manager"), "process_count": len(service.get("processes", [])), "runtime": runtime},
        ),
        _diagnostic_step(
            "service_logs", "Inspect bounded service-manager logs",
            "warning" if any(
                item.get("phase") == "logs" and item.get("severity") in {"critical", "warning"}
                for item in service.get("findings", [])
            ) else
            "passed" if service.get("logs_collected") else "skipped" if not include_service_logs else "not_applicable",
            f"Collected {len(service.get('journal', []))} service journal line(s)." if service.get("logs_collected") else
            "Service logs were not requested." if not include_service_logs else "No automatic service journal was available.",
            depends_on=["runtime"],
        ),
        _diagnostic_step(
            "configuration", "Validate and expand the active configuration", config_status,
            f"Validated {len(parsed.get('config_files', []))} active configuration file(s) through nginx -t/-T." if parsed.get("config_files") else
            "Configuration expansion was not available.",
            depends_on=["runtime"],
        ),
        _diagnostic_step(
            "application_logs", "Inspect configured Nginx logs",
            "failed" if any(item.get("severity") == "critical" for item in phase_findings["application_logs"]) else
            "warning" if phase_findings["application_logs"] else
            "passed" if error_lines or access_lines else "skipped" if log_mode not in {"error", "access", "all"} else "not_applicable",
            f"Inspected {len(error_lines)} error and {len(access_lines)} access-log line(s)." if error_lines or access_lines else
            "Application log content was not requested." if log_mode not in {"error", "access", "all"} else "No readable log content was returned.",
            depends_on=["configuration"],
        ),
        _diagnostic_step(
            "listeners", "Verify configured listeners", listener_status,
            f"Compared {len(parsed.get('listeners', []))} configured listener(s) with the local socket table.",
            layer="OSI 4", depends_on=["runtime", "configuration"],
        ),
        _diagnostic_step(
            "firewall", "Correlate listening ports with host firewall policy",
            "failed" if firewall.get("status") == "failed" else
            "warning" if firewall.get("status") == "warning" else
            "passed" if parsed.get("listen_ports") else "skipped",
            f"Assessed {len(firewall.get('port_assessments', []))} configured TCP port(s)." if parsed.get("listen_ports") else
            "No numeric TCP listener was recovered from the effective configuration.",
            layer="OSI 3-4", depends_on=["listeners"],
        ),
        _diagnostic_step(
            "application", "Probe the selected virtual host", application_status,
            branch_summary, layer="OSI 6-7", depends_on=["firewall"],
            evidence={
                "host_header": http_probe.get("host_header") if http_probe else None,
                "tls_server_name": (http_probe.get("tls") or {}).get("server_name") if http_probe else None,
                "status_code": http_probe.get("status_code") if http_probe else None,
            },
        ),
        _diagnostic_step(
            "path_access", "Check the selected content and security policy path",
            "failed" if any(item.get("severity") == "critical" for item in phase_findings["path_access"]) else
            "warning" if phase_findings["path_access"] else "passed" if path_checks else "not_applicable",
            f"Checked {len(path_checks)} root/alias path(s), POSIX traversal, ACL caveats, SELinux, and AppArmor signals.",
            depends_on=["configuration", "application"],
        ),
    ]
    return {
        "status": _diagnostic_status(findings),
        "read_only": True,
        "context": context,
        "methodology": _methodology(
            "nginx-layered", "Define the symptom, rule out host blockers, correlate runtime and logs, validate the effective configuration, verify transport, then branch on the observed HTTP/TLS result.", steps,
        ),
        "binary": str(executable) if executable else binary,
        "runtime_discovery": runtime,
        "effective_config": effective_config,
        "build": build,
        "syntax": syntax,
        "configuration": parsed,
        "service": service,
        "listening_sockets": sockets,
        "firewall": firewall,
        "path_access": path_checks,
        "security_frameworks": security,
        "filesystems": disks,
        "logs": log_files,
        "logs_included": log_mode != "none",
        "logs_redacted": log_mode != "none" and not raw_logs,
        "http_probe": http_probe,
        "cause_candidates": _rank_cause_candidates(findings),
        "findings": findings,
    }


def reverse_dns_sweep(network: str, timeout: int = 2, max_threads: int = 50) -> List[Dict[str, Any]]:
    net = ipaddress.ip_network(network, strict=False)
    if net.num_addresses > MAX_NETWORK_HOSTS + 2:
        raise ValueError(
            f"Network contains too many addresses ({net.num_addresses}); "
            f"maximum is {MAX_NETWORK_HOSTS + 2}"
        )
    hosts = [str(ip) for ip in net.hosts()]

    def _resolve_one(ip):
        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except (socket.herror, socket.gaierror, socket.timeout, OSError):
            hostname = None
        return {"ip": ip, "hostname": hostname}

    old_timeout = socket.getdefaulttimeout()
    socket.setdefaulttimeout(timeout)
    try:
        with ThreadPoolExecutor(max_workers=max_threads) as pool:
            results = list(pool.map(_resolve_one, hosts))
    finally:
        socket.setdefaulttimeout(old_timeout)
    return results


# ---------------------------------------------------------------------------
#  Advanced port scanning
# ---------------------------------------------------------------------------

TOP_PORTS = {
    21: "ftp", 22: "ssh", 23: "telnet", 25: "smtp", 53: "dns",
    80: "http", 110: "pop3", 111: "rpcbind", 135: "msrpc", 139: "netbios",
    143: "imap", 443: "https", 445: "smb", 993: "imaps", 995: "pop3s",
    1723: "pptp", 3306: "mysql", 3389: "rdp", 5900: "vnc", 8080: "http-proxy",
}
HTTP_PORTS = {80, 443, 8080}


def banner_grab(host: str, port: int, timeout: float = 2.0) -> Optional[str]:
    _validate_host(host)
    _validate_port(port)
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            s.connect((host, port))
            s.sendall(b"HEAD / HTTP/1.0\r\n\r\n" if port in HTTP_PORTS else b"\r\n")
            data = s.recv(1024)
        if not data:
            return None
        text = data.decode("utf-8", errors="replace")
        cleaned = "".join(ch for ch in text if ch in "\n\r\t" or (0x20 <= ord(ch) < 0x7f))
        return cleaned.strip() or None
    except Exception:
        return None


def _scan_single_port(host, port, timeout, grab):
    result = {"port": port, "state": "closed", "service": TOP_PORTS.get(port, "unknown"), "banner": None}
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            if s.connect_ex((host, port)) == 0:
                result["state"] = "open"
    except Exception:
        pass
    if grab and result["state"] == "open":
        result["banner"] = banner_grab(host, port, timeout=max(timeout, 2.0))
    return result


def tcp_port_scan_advanced(
    host: str,
    ports: List[int],
    timeout: float = 1.0,
    grab_banner: bool = False,
    max_threads: int = 100,
) -> List[Dict[str, Any]]:
    _validate_host(host)
    for p in ports:
        _validate_port(p)
    if not 1 <= max_threads <= 256:
        raise ValueError("Workers must be between 1 and 256")
    workers = min(max_threads, len(ports)) if ports else 1
    results = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_scan_single_port, host, p, timeout, grab_banner): p for p in ports}
        for fut in as_completed(futures):
            try:
                results.append(fut.result())
            except Exception:
                p = futures[fut]
                results.append({"port": p, "state": "closed", "service": TOP_PORTS.get(p, "unknown"), "banner": None})
    results.sort(key=lambda r: r["port"])
    return results


def udp_port_check(host: str, ports: List[int], timeout: float = 2.0) -> List[Dict[str, Any]]:
    _validate_host(host)
    for p in ports:
        _validate_port(p)
    results = []
    for port in ports:
        state = "open|filtered"
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(timeout)
                s.sendto(b"", (host, port))
                try:
                    s.recvfrom(1024)
                    state = "open"
                except socket.timeout:
                    state = "open|filtered"
                except (ConnectionRefusedError, OSError) as e:
                    state = "closed" if getattr(e, 'errno', 0) in (111, None) or isinstance(e, ConnectionRefusedError) else "open|filtered"
        except Exception:
            pass
        results.append({"port": port, "state": state, "service": TOP_PORTS.get(port, "unknown")})
    return results


def scan_network_port(
    network: str,
    port: int,
    timeout: float = 1.0,
    max_threads: int = 100,
) -> List[Dict[str, Any]]:
    _validate_port(port)
    try:
        net = ipaddress.IPv4Network(network, strict=False)
    except (ipaddress.AddressValueError, ipaddress.NetmaskValueError, ValueError) as exc:
        raise ValueError(f"Invalid IPv4 network: '{network}' ({exc})")
    if net.num_addresses > MAX_NETWORK_HOSTS + 2:
        raise ValueError(
            f"Network contains too many addresses ({net.num_addresses}); "
            f"maximum is {MAX_NETWORK_HOSTS + 2}"
        )
    hosts = [str(addr) for addr in net.hosts()]
    results = []
    if not 1 <= max_threads <= 256:
        raise ValueError("Workers must be between 1 and 256")
    workers = min(max_threads, len(hosts)) if hosts else 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_scan_single_port, ip, port, timeout, False): ip for ip in hosts}
        for fut in as_completed(futures):
            try:
                res = fut.result()
                res["ip"] = futures[fut]
                results.append(res)
            except Exception:
                results.append({"ip": futures[fut], "port": port, "state": "closed", "service": TOP_PORTS.get(port, "unknown")})
    results.sort(key=lambda r: ipaddress.ip_address(r["ip"]))
    return results


def generate_random_ports(minimum: int = 49152, maximum: int = 65535,
                          count: int = 10) -> List[int]:
    """Return unique, sorted random candidate ports without probing them."""
    _validate_port(minimum)
    _validate_port(maximum)
    if minimum > maximum:
        raise ValueError("Minimum port must not exceed maximum port")
    available = maximum - minimum + 1
    if not 1 <= count <= min(100, available):
        raise ValueError(
            f"Port quantity must be between 1 and {min(100, available)}"
        )
    return sorted(secrets.SystemRandom().sample(range(minimum, maximum + 1), count))


# ---------------------------------------------------------------------------
#  Advanced DNS
# ---------------------------------------------------------------------------

def dns_lookup_type(domain: str, record_type: str = "A", server: Optional[str] = None,
                    timeout: int = 5) -> Dict[str, Any]:
    record_type = record_type.upper()
    valid_types = {
        "A", "AAAA", "CAA", "CNAME", "DNSKEY", "DS", "MX", "NS",
        "PTR", "RRSIG", "SOA", "SRV", "TXT",
    }
    if record_type not in valid_types:
        return {"domain": domain, "type": record_type, "server": server or "default",
                "records": [], "error": f"Unsupported type: {record_type}"}
    dig_cmd = ["dig", "+noall", "+answer"]
    if server:
        dig_cmd.append(f"@{server}")
    dig_cmd.extend([domain, record_type])
    try:
        result = subprocess.run(dig_cmd, capture_output=True, text=True, timeout=timeout)
        records = [l.strip() for l in result.stdout.splitlines() if l.strip() and not l.startswith(";")]
        full = subprocess.run(["dig"] + ([f"@{server}"] if server else []) + [domain, record_type],
                              capture_output=True, text=True, timeout=timeout)
        return {"domain": domain, "type": record_type, "server": server or "default",
                "records": records, "raw": full.stdout}
    except FileNotFoundError:
        pass
    except subprocess.TimeoutExpired:
        return {"domain": domain, "type": record_type, "server": server or "default",
                "records": [], "error": "dig timed out"}
    # Fallback to nslookup
    cmd = ["nslookup"] + ([f"-type={record_type}"] if record_type != "A" else []) + [domain] + ([server] if server else [])
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        raw = result.stdout + result.stderr
        records = [l.strip() for l in raw.splitlines() if l.strip() and not l.strip().startswith(("Server:", "Address:", "#", "Non-authoritative"))]
        return {"domain": domain, "type": record_type, "server": server or "default", "records": records, "raw": raw}
    except FileNotFoundError:
        if not server and record_type in {"A", "AAAA"}:
            family = socket.AF_INET if record_type == "A" else socket.AF_INET6
            try:
                addresses = sorted({
                    item[4][0]
                    for item in socket.getaddrinfo(domain, None, family, socket.SOCK_STREAM)
                })
                return {
                    "domain": domain,
                    "type": record_type,
                    "server": "system resolver",
                    "records": [f"{domain}. 0 IN {record_type} {address}" for address in addresses],
                    "fallback": "socket.getaddrinfo",
                }
            except (socket.gaierror, OSError) as exc:
                return {
                    "domain": domain, "type": record_type,
                    "server": "system resolver", "records": [], "error": str(exc),
                }
        return {"domain": domain, "type": record_type, "server": server or "default",
                "records": [], "error": "Neither dig nor nslookup found"}
    except subprocess.TimeoutExpired:
        return {"domain": domain, "type": record_type, "server": server or "default",
                "records": [], "error": "nslookup timed out"}


def dns_compare(
    domain: str,
    servers: List[str],
    record_type: str = "A",
    timeout: int = 5,
) -> Dict[str, Any]:
    results = {}
    for srv in servers:
        lookup = dns_lookup_type(domain, record_type, server=srv, timeout=timeout)
        parsed = []
        for rec in lookup.get("records", []):
            parts = rec.split()
            parsed.append(" ".join(parts[4:]) if len(parts) >= 5 else rec)
        results[srv] = parsed
    return {"domain": domain, "type": record_type, "results": results}


def dns_zone_transfer(
    domain: str,
    nameserver: Optional[str] = None,
    timeout: int = 30,
) -> Dict[str, Any]:
    if not nameserver:
        ns_lookup = dns_lookup_type(domain, "NS")
        ns_records = ns_lookup.get("records", [])
        if not ns_records:
            return {"domain": domain, "nameserver": None, "success": False, "records": [], "error": "No NS found"}
        nameserver = ns_records[0].split()[-1].rstrip(".")
    try:
        result = subprocess.run(["dig", "axfr", domain, f"@{nameserver}"],
                                capture_output=True, text=True, timeout=timeout)
        records = [l.strip() for l in result.stdout.splitlines() if l.strip() and not l.startswith((";", "<<>>"))]
        success = len(records) > 0 and "Transfer failed" not in result.stdout and "refused" not in result.stdout.lower()
        return {"domain": domain, "nameserver": nameserver, "success": success, "records": records}
    except FileNotFoundError:
        return {"domain": domain, "nameserver": nameserver, "success": False, "records": [], "error": "dig not found"}
    except subprocess.TimeoutExpired:
        return {"domain": domain, "nameserver": nameserver, "success": False, "records": [], "error": "Timed out"}


def _dns_record_payloads(records: List[str]) -> List[str]:
    payloads = []
    for record in records:
        parts = record.split()
        payloads.append(" ".join(parts[4:]) if len(parts) >= 5 else record)
    return payloads


def dnssec_status(domain: str, timeout: int = 5) -> Dict[str, Any]:
    """Report whether a validating resolver returned authenticated DNSSEC data."""
    try:
        result = subprocess.run(
            ["dig", "+dnssec", "+comments", "+answer", domain, "SOA"],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except FileNotFoundError:
        return {"status": "unavailable", "error": "dig not found"}
    except subprocess.TimeoutExpired:
        return {"status": "failed", "error": "dig timed out"}
    raw = result.stdout
    flags_match = re.search(r"flags:\s*([^;]+);", raw)
    flags = flags_match.group(1).split() if flags_match else []
    has_rrsig = bool(re.search(r"\sRRSIG\s", raw))
    authenticated = "ad" in flags
    return {
        "status": "validated" if authenticated else ("signed" if has_rrsig else "unsigned"),
        "authenticated_data": authenticated,
        "rrsig_present": has_rrsig,
        "resolver_flags": flags,
    }


def dns_health(
    domain: str,
    timeout: int = 5,
    dkim_selector: Optional[str] = None,
) -> Dict[str, Any]:
    """Collect resolution, delegation, DNSSEC, and mail DNS health signals."""
    _validate_host(domain.rstrip("."))
    normalized = domain.rstrip(".").lower()
    record_types = ("A", "AAAA", "CNAME", "NS", "SOA", "MX", "CAA", "TXT")
    records: Dict[str, Any] = {}
    for record_type in record_types:
        lookup = dns_lookup_type(normalized, record_type, timeout=timeout)
        records[record_type] = {
            "records": _dns_record_payloads(lookup.get("records", [])),
            **({"error": lookup["error"]} if "error" in lookup else {}),
        }

    ns_values = [value.rstrip(".") for value in records["NS"]["records"]]
    authoritative: Dict[str, Any] = {"nameserver": ns_values[0] if ns_values else None}
    if ns_values:
        authoritative_lookup = dns_lookup_type(
            normalized, "NS", server=ns_values[0], timeout=timeout
        )
        authoritative_values = {
            value.rstrip(".")
            for value in _dns_record_payloads(authoritative_lookup.get("records", []))
        }
        recursive_values = set(ns_values)
        authoritative.update({
            "reachable": "error" not in authoritative_lookup,
            "records": sorted(authoritative_values),
            "consistent": bool(authoritative_values) and authoritative_values == recursive_values,
        })
        if "error" in authoritative_lookup:
            authoritative["error"] = authoritative_lookup["error"]
    else:
        authoritative.update({"reachable": False, "records": [], "consistent": False})

    cname_values = [value.rstrip(".").lower() for value in records["CNAME"]["records"]]
    cname_loop = normalized in cname_values or len(cname_values) != len(set(cname_values))
    txt_values = records["TXT"]["records"]
    spf = [value for value in txt_values if "v=spf1" in value.lower()]
    dmarc_lookup = dns_lookup_type(f"_dmarc.{normalized}", "TXT", timeout=timeout)
    dmarc = [
        value for value in _dns_record_payloads(dmarc_lookup.get("records", []))
        if "v=dmarc1" in value.lower()
    ]
    mail: Dict[str, Any] = {
        "mx": records["MX"]["records"],
        "spf": spf,
        "dmarc": dmarc,
    }
    if dkim_selector:
        _validate_config_name(dkim_selector, "DKIM selector")
        dkim_lookup = dns_lookup_type(
            f"{dkim_selector}._domainkey.{normalized}", "TXT", timeout=timeout
        )
        mail["dkim_selector"] = dkim_selector
        mail["dkim"] = _dns_record_payloads(dkim_lookup.get("records", []))

    core_resolution = bool(records["A"]["records"] or records["AAAA"]["records"] or cname_values)
    problems = []
    if not core_resolution:
        problems.append("no A, AAAA, or CNAME record")
    if not records["NS"]["records"]:
        if records["NS"].get("error"):
            problems.append(f"NS check unavailable: {records['NS']['error']}")
        else:
            problems.append("no NS record")
    if not records["SOA"]["records"]:
        if records["SOA"].get("error"):
            problems.append(f"SOA check unavailable: {records['SOA']['error']}")
        else:
            problems.append("no SOA record")
    if cname_loop:
        problems.append("possible CNAME loop")
    if ns_values and not authoritative.get("reachable"):
        problems.append("authoritative nameserver did not answer")
    if authoritative.get("reachable") and not authoritative.get("consistent"):
        problems.append("recursive and authoritative NS sets differ")
    dnssec = dnssec_status(normalized, timeout)
    if dnssec.get("status") in {"unavailable", "failed"}:
        problems.append(f"DNSSEC check unavailable: {dnssec.get('error', 'unknown error')}")
    status = "failed" if not core_resolution else ("warning" if problems else "ok")
    return {
        "domain": normalized,
        "status": status,
        "problems": problems,
        "records": records,
        "delegation": authoritative,
        "dnssec": dnssec,
        "mail": mail,
        "cname_loop": cname_loop,
    }


# ---------------------------------------------------------------------------
#  TLS cert check + HTTP headers
# ---------------------------------------------------------------------------

def cert_check(host: str, port: int = 443, timeout: int = 5) -> Dict[str, Any]:
    _validate_host(host)
    _validate_port(port)
    if timeout <= 0:
        raise ValueError("Timeout must be greater than zero")
    result: Dict[str, Any] = {"host": host, "port": port}
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = cast(Dict[str, Any], ssock.getpeercert() or {})
                try:
                    binary_certificate = ssock.getpeercert(binary_form=True)
                except TypeError:
                    binary_certificate = None
                tls_version = getattr(ssock, "version", lambda: None)()
                cipher_details = getattr(ssock, "cipher", lambda: None)()
                alpn_protocol = getattr(ssock, "selected_alpn_protocol", lambda: None)()
        subject_cn = ""
        for rdn in cert.get("subject", ()):
            for attr_type, attr_value in rdn:
                if attr_type == "commonName":
                    subject_cn = attr_value
        issuer_org = ""
        for rdn in cert.get("issuer", ()):
            for attr_type, attr_value in rdn:
                if attr_type == "organizationName":
                    issuer_org = attr_value
        not_before_str = cert.get("notBefore", "")
        not_after_str = cert.get("notAfter", "")
        now_utc = datetime.now(timezone.utc)
        try:
            not_before_dt = datetime.fromtimestamp(
                ssl.cert_time_to_seconds(not_before_str), timezone.utc
            )
            not_after_dt = datetime.fromtimestamp(
                ssl.cert_time_to_seconds(not_after_str), timezone.utc
            )
            days_remaining = (not_after_dt - now_utc).days
            expired = now_utc > not_after_dt
            not_yet_valid = now_utc < not_before_dt
        except (TypeError, ValueError):
            days_remaining = None
            expired = None
            not_yet_valid = None
        san_list = [f"{t}:{v}" for t, v in cert.get("subjectAltName", ())]
        result.update({
            "subject": subject_cn, "issuer": issuer_org,
            "serial_number": cert.get("serialNumber", ""),
            "not_before": not_before_str, "not_after": not_after_str,
            "days_remaining": days_remaining, "san": san_list,
            "certificate_version": cert.get("version"),
            "expired": expired, "not_yet_valid": not_yet_valid,
            "hostname_verified": True,
            "tls_version": tls_version,
            "cipher": cipher_details[0] if cipher_details else None,
            "cipher_bits": cipher_details[2] if cipher_details else None,
            "alpn_protocol": alpn_protocol,
            "sha256_fingerprint": hashlib.sha256(binary_certificate).hexdigest().upper()
            if binary_certificate else None,
        })
    except ssl.SSLCertVerificationError as e:
        result["error"] = f"SSL verification failed: {e}"
        result["hostname_verified"] = False
    except ssl.SSLError as e:
        result["error"] = f"SSL error: {e}"
    except (socket.timeout, ConnectionRefusedError, socket.gaierror, OSError) as e:
        result["error"] = str(e)
    return result


def http_headers(url: str, timeout: int = 5) -> Dict[str, Any]:
    sec_names = ["Strict-Transport-Security", "Content-Security-Policy", "X-Frame-Options",
                 "X-Content-Type-Options", "X-XSS-Protection", "Referrer-Policy", "Permissions-Policy"]
    result: Dict[str, Any] = {"url": url}
    if not re.match(r'^https?://', url, re.IGNORECASE):
        return {"url": url, "error": "URL must use http:// or https://"}
    try:
        started = time.monotonic()
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", f"SysAdminToolbox/{__version__}")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result["status_code"] = resp.getcode()
            result["final_url"] = resp.geturl()
            result["headers"] = dict(resp.headers)
            resp.read(1)
        result["elapsed_ms"] = round((time.monotonic() - started) * 1000, 2)
    except urllib.error.HTTPError as e:
        result["status_code"] = e.code
        result["final_url"] = e.geturl()
        result["headers"] = dict(e.headers) if e.headers else {}
        result["elapsed_ms"] = round((time.monotonic() - started) * 1000, 2)
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        result["error"] = str(e)
        return result
    hdr_lower = {k.lower(): v for k, v in result.get("headers", {}).items()}
    result["redirected"] = result.get("final_url") != url
    sec: Dict[str, Dict[str, Any]] = {}
    for sh in sec_names:
        val = hdr_lower.get(sh.lower())
        sec[sh] = {"present": val is not None, "value": val.strip() if val else None}
    result["security_headers"] = sec
    return result


def parse_endpoint(target: str, default_port: int = 443) -> Dict[str, Any]:
    """Parse a hostname, host:port, bracketed IPv6 endpoint, or URL."""
    raw = target.strip()
    if not raw:
        raise ValueError("Target must not be empty")
    scheme = None
    path = ""
    query = ""
    if "://" in raw:
        parsed = urllib.parse.urlparse(raw)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Target URL must use http:// or https:// and include a host")
        host = parsed.hostname
        scheme = parsed.scheme
        try:
            port = parsed.port or (443 if scheme == "https" else 80)
        except ValueError as exc:
            raise ValueError(f"Invalid target port: {exc}")
        path = parsed.path or "/"
        query = parsed.query
    elif raw.startswith("["):
        match = re.fullmatch(r"\[([^]]+)](?::(\d+))?", raw)
        if not match:
            raise ValueError(f"Invalid bracketed endpoint: '{target}'")
        host = match.group(1)
        port = int(match.group(2)) if match.group(2) else default_port
    elif raw.count(":") == 1 and raw.rsplit(":", 1)[1].isdigit():
        host, port_text = raw.rsplit(":", 1)
        port = int(port_text)
    else:
        host = raw
        port = default_port
    _validate_host(host)
    _validate_port(port)
    return {
        "target": raw, "host": host, "port": port, "scheme": scheme,
        "path": path, "query": query,
    }


def resolve_all(host: str, timeout: float = 5.0) -> Dict[str, Any]:
    _validate_host(host)
    if timeout <= 0:
        raise ValueError("Timeout must be greater than zero")
    started = time.monotonic()
    try:
        records = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        addresses = []
        for family, _socktype, _proto, canonical, sockaddr in records:
            value = sockaddr[0]
            item = {
                "address": value,
                "family": "IPv6" if family == socket.AF_INET6 else "IPv4",
            }
            if canonical:
                item["canonical_name"] = canonical
            if item not in addresses:
                addresses.append(item)
        return {
            "status": "ok" if addresses else "failed",
            "addresses": addresses,
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        }
    except (socket.gaierror, socket.timeout, OSError) as exc:
        return {
            "status": "failed",
            "addresses": [],
            "error": str(exc),
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        }


def tcp_probe(host: str, port: int, timeout: float = 5.0) -> Dict[str, Any]:
    _validate_host(host)
    _validate_port(port)
    started = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {
                "status": "ok",
                "host": host,
                "port": port,
                "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
            }
    except (socket.timeout, ConnectionRefusedError, socket.gaierror, OSError) as exc:
        return {
            "status": "failed",
            "host": host,
            "port": port,
            "error": str(exc),
            "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        }


def wait_for_service(
    host: str,
    port: int,
    timeout: float = 60.0,
    interval: float = 2.0,
) -> Dict[str, Any]:
    """Wait until a TCP endpoint accepts a connection or the deadline passes."""
    _validate_host(host)
    _validate_port(port)
    if timeout <= 0 or interval <= 0:
        raise ValueError("Timeout and interval must be greater than zero")
    started = time.monotonic()
    deadline = started + timeout
    attempts = 0
    last_error = None
    while True:
        attempts += 1
        remaining = max(0.01, deadline - time.monotonic())
        probe = tcp_probe(host, port, timeout=min(interval, remaining))
        if probe["status"] == "ok":
            return {
                "status": "ready",
                "host": host,
                "port": port,
                "attempts": attempts,
                "elapsed_seconds": round(time.monotonic() - started, 3),
            }
        last_error = probe.get("error")
        now = time.monotonic()
        if now >= deadline:
            break
        time.sleep(min(interval, deadline - now))
    return {
        "status": "timed_out",
        "host": host,
        "port": port,
        "attempts": attempts,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "error": last_error,
    }


def doctor_target(
    target: str,
    timeout: float = 5.0,
    warn_days: int = 30,
) -> Dict[str, Any]:
    """Run DNS, TCP, TLS, and HTTP checks as one diagnostic pipeline."""
    if timeout <= 0:
        raise ValueError("Timeout must be greater than zero")
    if warn_days < 0:
        raise ValueError("warn_days must be zero or greater")
    endpoint = parse_endpoint(target)
    host = endpoint["host"]
    port = endpoint["port"]
    scheme = endpoint["scheme"] or ("https" if port == 443 else "http")
    url_host = f"[{host}]" if ":" in host else host
    url = target if endpoint["scheme"] else f"{scheme}://{url_host}:{port}/"
    started = time.monotonic()
    checks: Dict[str, Any] = {}
    checks["dns"] = resolve_all(host, timeout)
    checks["tcp"] = tcp_probe(host, port, timeout)
    if checks["tcp"]["status"] == "ok" and scheme == "https":
        certificate = cert_check(host, port, int(max(1, timeout)))
        if "error" in certificate:
            certificate["status"] = "failed"
        elif certificate.get("expired") or certificate.get("not_yet_valid"):
            certificate["status"] = "failed"
        elif certificate.get("days_remaining") is not None and certificate["days_remaining"] <= warn_days:
            certificate["status"] = "warning"
        else:
            certificate["status"] = "ok"
        checks["tls"] = certificate
    if checks["tcp"]["status"] == "ok" and scheme in {"http", "https"}:
        web = http_headers(url, int(max(1, timeout)))
        if "error" in web or int(web.get("status_code", 599)) >= 500:
            web["status"] = "failed"
        elif int(web.get("status_code", 599)) >= 400:
            web["status"] = "warning"
        else:
            web["status"] = "ok"
        checks["http"] = web
    statuses = [check.get("status", "failed") for check in checks.values()]
    if "failed" in statuses:
        status = "failed"
    elif "warning" in statuses:
        status = "warning"
    else:
        status = "ok"
    return {
        "target": target,
        "host": host,
        "port": port,
        "scheme": scheme,
        "status": status,
        "elapsed_ms": round((time.monotonic() - started) * 1000, 2),
        "checks": checks,
    }


def run_batch(targets: List[str], function, workers: int = 10) -> List[Dict[str, Any]]:
    """Apply a diagnostic function concurrently while preserving input order."""
    if not 1 <= workers <= 256:
        raise ValueError("Workers must be between 1 and 256")
    if len(targets) > MAX_BATCH_TARGETS:
        raise ValueError(f"Batch exceeds {MAX_BATCH_TARGETS} targets")
    results: List[Optional[Dict[str, Any]]] = [None] * len(targets)
    with ThreadPoolExecutor(max_workers=min(workers, max(1, len(targets)))) as pool:
        futures = {pool.submit(function, target): (index, target) for index, target in enumerate(targets)}
        for future in as_completed(futures):
            index, target = futures[future]
            try:
                results[index] = future.result()
            except Exception as exc:
                results[index] = {"target": target, "status": "failed", "error": str(exc)}
    return [cast(Dict[str, Any], result) for result in results]


def audit_certificates(
    targets: List[str],
    warn_days: int = 30,
    timeout: int = 5,
    workers: int = 10,
) -> List[Dict[str, Any]]:
    if warn_days < 0:
        raise ValueError("warn_days must be zero or greater")

    def check(target: str) -> Dict[str, Any]:
        endpoint = parse_endpoint(target)
        result = cert_check(endpoint["host"], endpoint["port"], timeout)
        result["target"] = target
        if "error" in result:
            result["status"] = "failed"
        elif result.get("expired"):
            result["status"] = "expired"
        elif result.get("not_yet_valid"):
            result["status"] = "not_yet_valid"
        elif result.get("days_remaining") is not None and result["days_remaining"] <= warn_days:
            result["status"] = "warning"
        else:
            result["status"] = "ok"
        return result

    return run_batch(targets, check, workers)


# ---------------------------------------------------------------------------
#  Traceroute with ASN
# ---------------------------------------------------------------------------

def asn_lookup(ip: str) -> Dict[str, Any]:
    try:
        reversed_ip = ".".join(ip.split(".")[::-1])
        query = f"{reversed_ip}.origin.asn.cymru.com"
        result = subprocess.run(["dig", "+short", query, "TXT"],
                                capture_output=True, text=True, timeout=5)
        out = result.stdout.strip().strip('"')
        if not out or result.returncode != 0:
            return {"ip": ip, "error": "no result"}
        parts = [p.strip() for p in out.split("|")]
        if len(parts) < 4:
            return {"ip": ip, "error": f"unexpected format: {out}"}
        return {"ip": ip, "asn": f"AS{parts[0]}" if not parts[0].startswith("AS") else parts[0],
                "prefix": parts[1], "country": parts[2], "registry": parts[3]}
    except (subprocess.TimeoutExpired, Exception) as e:
        return {"ip": ip, "error": str(e)}


def traceroute_asn(host: str, max_hops: int = 30, timeout: int = 2) -> List[Dict[str, Any]]:
    hops = traceroute(host, max_hops=max_hops, timeout=timeout)
    hops_with_ip = [(i, h) for i, h in enumerate(hops) if h.get("ip")]
    asn_results: Dict[int, Optional[Dict[str, Any]]] = {}
    if hops_with_ip:
        with ThreadPoolExecutor(max_workers=min(len(hops_with_ip), 20)) as pool:
            futures = {pool.submit(asn_lookup, h["ip"]): i for i, h in hops_with_ip}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    asn_results[idx] = future.result()
                except Exception:
                    asn_results[idx] = None
    enriched: List[Dict[str, Any]] = []
    for i, hop in enumerate(hops):
        entry: Dict[str, Any] = {
            "hop": hop.get("hop"), "ip": hop.get("ip"),
            "hostname": hop.get("hostname"), "rtt_ms": hop.get("rtt_ms"),
            "asn": None, "prefix": None, "country": None,
        }
        asn_result = asn_results.get(i)
        if asn_result and "error" not in asn_result:
            entry["asn"] = asn_result["asn"]
            entry["prefix"] = asn_result["prefix"]
            entry["country"] = asn_result["country"]
        enriched.append(entry)
    return enriched


# ---------------------------------------------------------------------------
#  CLI
# ---------------------------------------------------------------------------

BANNER = """
 ┌──────────────────────────────────────┐
 │  SysAdminToolbox  v""" + __version__.ljust(18) + """│
 │  Network Administration Suite        │
 └──────────────────────────────────────┘"""



def _setup_parser():
    parser = argparse.ArgumentParser(
        prog='SysAdminToolbox',
        description="Network administration calculations, conversions, diagnostics, and configuration helpers.",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument("--json", action="store_true", default=False, help="Output in JSON")
    parser.add_argument("--no-color", action="store_true", default=False, dest="no_color", help="Disable colors")
    parser.add_argument("--version", action="version", version=f"SysAdminToolbox v{__version__}")
    parser.add_argument("-i", "--interactive", action="store_true", default=False, help="Interactive REPL mode")

    sub = parser.add_subparsers(dest="command", title="commands")

    # Shared flags available in every subcommand
    shared = argparse.ArgumentParser(add_help=False)
    shared.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS,
        help="Output in JSON",
    )
    shared.add_argument(
        "--no-color", action="store_true", default=argparse.SUPPRESS,
        dest="no_color", help="Disable colors",
    )

    # -- convert --
    p = sub.add_parser("convert", aliases=["conv", "c"], parents=[shared], help="Number/base conversions",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  convert d2b 42\n  convert iptobin 192.168.1.1\n  convert ipinfo 192.168.1.42/24\n  convert ipclass 100.64.0.1")
    p.add_argument("op", choices=["d2b","b2d","d2h","h2d","b2h","h2b","iptobin","bintoip",
                                   "masktobin","bintomask","m2c","c2m","m2w","w2m","c2w","w2c",
                                   "a2b","b2a","ipinfo","ipclass"], help="Conversion operation")
    p.add_argument("value", nargs='+', help="Value(s) to convert")

    # -- subnet --
    p = sub.add_parser("subnet", aliases=["sub", "s"], parents=[shared], help="Subnet calculations",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  subnet calc 192.168.0.0/24\n  subnet adv 192.168.1.0/24 26\n  subnet vlsm 192.168.1.0/24 50 30 10\n  subnet contains 10.0.0.0/8 10.1.2.3\n  subnet exclude 10.0.0.0/24 10.0.0.64/26\n  subnet nth 2001:db8::/64 1000\n  subnet audit inventory.json")
    p.add_argument("op", choices=["calc","adv","vlsm","overlap","supernet","range",
                                   "contains","exclude","nth","audit"], help="Subnet operation")
    p.add_argument("args", nargs='+', help="Arguments")
    p.add_argument(
        "--limit", type=int, default=MAX_SUBNET_DETAILS,
        help=f"Maximum subnet detail rows for 'adv' (default: {MAX_SUBNET_DETAILS})",
    )

    # -- ipv6 --
    p = sub.add_parser("ipv6", aliases=["v6"], parents=[shared], help="IPv6 utilities",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  ipv6 expand ::1\n  ipv6 compress 2001:0db8::1\n  ipv6 type fe80::1\n  ipv6 subnet 2001:db8::/32\n  ipv6 ula")
    p.add_argument("op", choices=["expand","compress","tobin","type","subnet","ula"], help="IPv6 operation")
    p.add_argument("value", nargs='?', default="", help="IPv6 address or network")

    # -- mac --
    p = sub.add_parser("mac", aliases=["m"], parents=[shared], help="MAC address utilities",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  mac info AA:BB:CC:DD:EE:FF\n  mac format aa:bb:cc:dd:ee:ff cisco\n  mac generate 5 colon\n  mac oui-update\n  mac vendor 00:11:22:33:44:55")
    p.add_argument("op", choices=["info","format","normalize","vendor","generate","oui-update"], help="MAC operation")
    p.add_argument("value", nargs='?', default="", help="MAC address, or quantity for 'generate'")
    p.add_argument("style", nargs='?', default="colon", help="Format style (colon/dash/cisco/bare)")
    p.add_argument("--db", help="IEEE OUI CSV path (default: user cache)")
    p.add_argument("--url", default=DEFAULT_IEEE_OUI_URL, help="HTTPS URL used by oui-update")
    p.add_argument("--timeout", type=int, default=30, help="Network timeout in seconds")

    # -- net --
    p = sub.add_parser("net", aliases=["n"], parents=[shared], help="Network diagnostics",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  net doctor https://example.com\n  net doctor --input targets.txt --format ndjson\n  net wait database.internal 5432 --timeout 60\n  net cert-audit --input tls-targets.txt --format csv\n  net dns-health example.com --dkim-selector mail\n  net local --json\n  net portscan 192.168.1.1 22 80 443\n  net traceroute-asn example.com")
    p.add_argument("op", choices=["ping","pingsweep","portscan","portscan-adv","portscan-udp","portscan-net",
                                   "traceroute","tracert","traceroute-asn","whois","dns","dns-type","dns-compare",
                                   "dns-axfr","rdns","rdns-sweep","arp","certcheck","headers","banner",
                                   "random-ports","doctor","wait","cert-audit","dns-health","local"], help="Network operation")
    p.add_argument("target", nargs='?', default="", help="Target host/IP/domain (not needed for arp)")
    p.add_argument("extra", nargs='*', help="Extra args (ports for portscan)")
    p.add_argument("--input", dest="input_file", help="Read batch targets from a file, or '-' for stdin")
    p.add_argument("--format", choices=["text", "json", "ndjson", "csv"], default="text", dest="output_format")
    p.add_argument("--timeout", type=float, help="Operation timeout in seconds")
    p.add_argument("--workers", type=int, default=10, help="Batch worker count (1-256)")
    p.add_argument("--warn-days", type=int, default=30, help="Certificate warning threshold")
    p.add_argument("--interval", type=float, default=2.0, help="Polling interval for net wait")
    p.add_argument("--dkim-selector", help="Optional DKIM selector for dns-health")

    # -- doctor --
    p = sub.add_parser(
        "doctor", aliases=["diag", "diagnose"], parents=[shared],
        help="Read-only system, service, disk, network, firewall, and Nginx diagnostics",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  doctor system\n"
            "  doctor system --logs system --since '30 minutes ago'\n"
            "  doctor disk /var --du\n"
            "  doctor service postgresql --port 5432 --logs service\n"
            "  doctor network database.internal --port 5432\n"
            "  doctor firewall 80,443\n"
            "  doctor nginx --url http://127.0.0.1 --host-header example.com\n"
            "  doctor nginx --url https://127.0.0.1 --host-header example.com --sni example.com\n"
            "  doctor nginx --logs all --lines 100\n\n"
            "Diagnostics never change service state, ownership, permissions, or configuration.\n"
            "Log content is opt-in, bounded, and redacted unless --raw-logs is explicit.\n"
            "HTTP probes connect directly; redirects and disabled TLS verification are opt-in."
        ),
    )
    p.add_argument(
        "op", nargs="?", default="system",
        choices=["system", "general", "nginx", "service", "disk", "network", "firewall"],
        help="Diagnostic to run (default: system)",
    )
    p.add_argument(
        "target", nargs="?", default="",
        help="Service name, path, endpoint, or comma-separated firewall ports",
    )
    p.add_argument("--url", help="HTTP/HTTPS URL to probe during an Nginx diagnostic")
    p.add_argument("--host-header", help="Explicit Host header for the Nginx URL probe")
    p.add_argument("--sni", help="Explicit TLS server name when connecting to another address")
    p.add_argument(
        "--follow-redirects", action="store_true",
        help="Follow up to five HTTP redirects (disabled by default)",
    )
    p.add_argument(
        "--insecure", action="store_true",
        help="Disable TLS certificate verification for the explicit probe only",
    )
    p.add_argument("--config", help="Explicit Nginx configuration file passed to nginx -t/-T")
    p.add_argument("--binary", default="nginx", help="Nginx executable name or path")
    p.add_argument(
        "--logs", choices=["none", "system", "service", "error", "access", "all"],
        default="none", help="Include selected logs (default: none)",
    )
    p.add_argument("--lines", type=int, default=50, help="Maximum log lines per source (1-500)")
    p.add_argument("--since", default="1 hour ago", help="Journal time range understood by journalctl")
    p.add_argument(
        "--raw-logs", action="store_true",
        help="Disable log redaction (may expose credentials or personal data)",
    )
    p.add_argument("--du", action="store_true", help="Collect top-level disk usage (may be slow)")
    p.add_argument(
        "--port", type=int,
        help="TCP port for network, service, or firewall correlation",
    )
    p.add_argument("--timeout", type=float, default=10.0, help="Per-check timeout in seconds")
    p.add_argument("--symptom", help="Observed behavior or error (maximum 500 characters)")
    p.add_argument("--expected", help="Expected behavior (maximum 500 characters)")
    p.add_argument("--recent-change", help="Relevant recent change (maximum 500 characters)")

    # -- vendor --
    p = sub.add_parser("vendor", aliases=["v"], parents=[shared], help="Vendor config helpers",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  vendor profiles\n  vendor profiles --legacy\n  vendor vlan cisco 10 Engineering Gi1/0/1\n  vendor vlan cisco 10 Engineering Gi1/0/48 --mode trunk --allowed-vlans 10,20-30\n  vendor acl cisco BLOCK deny tcp 10.0.0.0/8 any")
    p.add_argument("op", choices=["vlan","acl","profiles"], help="Vendor operation")
    p.add_argument("args", nargs='*', help="Arguments")
    p.add_argument("--platform", dest="platform_name", help="Explicit platform profile")
    p.add_argument("--software-version", help="Validate a release against the selected profile")
    p.add_argument("--mode", choices=["access", "trunk"], default="access", help="VLAN port mode")
    p.add_argument("--allowed-vlans", help="Comma-separated VLAN IDs and ranges for trunks")
    p.add_argument("--native-vlan", type=int, help="Native/PVID VLAN for trunks")
    p.add_argument("--legacy", action="store_true", help="Allow an explicitly selected legacy profile")

    # -- cheat --
    p = sub.add_parser("cheat", aliases=["cs"], parents=[shared], help="Cheatsheets",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  cheat vlan trunk\n  cheat vlan --legacy\n  cheat vlan legacy_trunking --legacy\n  cheat acl\n  cheat firewall iptables\n  cheat routing ospf\n  cheat nat cisco_pat\n  cheat huawei\n  cheat mikrotik")
    p.add_argument("sheet", choices=["vlan","acl","huawei","mikrotik","firewall","routing","nat"], help="Cheatsheet topic")
    p.add_argument("section", nargs='?', default=None, help="Specific section (optional)")
    p.add_argument(
        "--legacy",
        action="store_true",
        help="Include explicitly marked compatibility references for older systems",
    )
    p.add_argument("--platform", dest="platform_name", help="Filter references by platform profile")
    p.add_argument("--show-sources", action="store_true", help="Show status, platform, replacement, and source metadata")

    # -- ai --
    p = sub.add_parser("ai", parents=[shared], help="AI assistant (optional, opt-in)",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  ai ask \"what is a /29 useful for\"\n  ai suggest \"split 10.0.0.0/24 into 4 subnets\"\n  SysAdminToolbox net certcheck example.com --json | SysAdminToolbox ai explain\n  ai run \"check the TLS cert of example.com\"\n  ai diagnose example.com --symptom \"site is slow\"\n  ai agent \"why can I not reach example.com on 443\"\n\nProviders (--provider): auto (default) | ollama | anthropic | openai | deepseek | kimi, optionally provider:model.\nKeys via env: ANTHROPIC_API_KEY / OPENAI_API_KEY / DEEPSEEK_API_KEY / MOONSHOT_API_KEY. Local Ollama: OLLAMA_HOST.\nPrivacy: local ollama is preferred when reachable; cloud sends require a confirmation or --yes.")
    p.add_argument("op", choices=["ask", "explain", "suggest", "run", "diagnose", "agent"], help="AI operation")
    p.add_argument("text", nargs="*", help="Question or request (explain also reads piped stdin)")
    p.add_argument("--provider", default="auto", help="auto|ollama|anthropic|openai|deepseek|kimi (or provider:model)")
    p.add_argument("--yes", "-y", action="store_true", help="Skip the cloud-send confirmation")
    p.add_argument("--symptom", default=None, help="Symptom hint for 'ai diagnose'")
    p.add_argument("--max-steps", type=int, default=8, dest="max_steps", help="Max steps for 'ai agent' (default 8)")
    p.add_argument("--dry-run", action="store_true", dest="dry_run", help="For 'ai agent': print the plan without running commands")

    # -- web --
    p = sub.add_parser("web", parents=[shared], help="Serve a local web UI (optional)",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  web\n  web --host 127.0.0.1 --port 8787\n\nServes the safe command groups (convert, subnet, ipv6, mac, vendor, cheat) and\ncheatsheets in your browser. Binds 127.0.0.1 by default; net and ai are not exposed.")
    p.add_argument("--host", default="127.0.0.1", help="Bind address (default: 127.0.0.1)")
    p.add_argument("--port", type=int, default=8787, help="Port (default: 8787)")


    return parser


# ---------------------------------------------------------------------------
#  Dispatch handlers
# ---------------------------------------------------------------------------

def _dispatch_convert(args):
    op = args.op
    val = args.value
    if op == "d2b":
        info = decimal_to_binary_values(int(val[0]))
        if is_json_mode():
            output(info, label="binary")
        else:
            print_binary_info(info)
    elif op == "b2d":
        info = binary_to_decimal_values(val[0])
        if is_json_mode():
            output(info, label="decimal")
        else:
            print_binary_to_decimal_info(val[0])
    elif op == "d2h":
        output(decimal_to_hexadecimal(int(val[0])), label="hexadecimal")
    elif op == "h2d":
        output(hexadecimal_to_decimal(val[0]), label="decimal")
    elif op == "b2h":
        output(binary_to_hexadecimal(val[0]), label="hexadecimal")
    elif op == "h2b":
        output(hexadecimal_to_binary(val[0]), label="binary")
    elif op == "iptobin":
        if is_json_mode():
            output({"address": val[0], "binary": ip_to_binary(val[0])}, label="ipv4")
        else:
            print(ip_to_binary_full(val[0]))
    elif op == "bintoip":
        output(binary_to_ip(val[0]), label="address")
    elif op == "masktobin":
        output(mask_to_binary(val[0]), label="binary_mask")
    elif op == "bintomask":
        output(binary_to_mask(val[0]), label="netmask")
    elif op == "m2c":
        output(mask_to_cidr(val[0]), label="cidr")
    elif op == "c2m":
        output(cidr_to_mask(int(val[0])), label="netmask")
    elif op == "m2w":
        output(mask_to_wildcard(val[0]), label="wildcard")
    elif op == "w2m":
        output(wildcard_to_mask(val[0]), label="netmask")
    elif op == "c2w":
        output(mask_to_wildcard(cidr_to_mask(int(val[0]))), label="wildcard")
    elif op == "w2c":
        output(mask_to_cidr(wildcard_to_mask(val[0])), label="cidr")
    elif op == "a2b":
        output(address_to_binary(val), label="binary_address")
    elif op == "b2a":
        addresses = [binary_to_ip(item) for item in val]
        output(addresses if len(addresses) > 1 else addresses[0], label="address")
    elif op == "ipinfo":
        output(ipv4_info(val[0]), label="ipv4")
    elif op == "ipclass":
        output(classify_ip(val[0]), label="classification")


def _dispatch_subnet(args):
    op = args.op
    a = args.args
    if op == "calc":
        if len(a) == 1 and '/' in a[0]:
            network, cidr_str = a[0].split('/')
            mask = cidr_to_mask(int(cidr_str))
        elif len(a) == 2:
            network, mask = a
            if mask.isdigit():
                mask = cidr_to_mask(int(mask))
        else:
            raise ValueError("Usage: subnet calc IP/CIDR  or  subnet calc IP MASK")
        details = subnet_calculator(network, mask)
        if is_json_mode():
            output(details, label="subnet")
        elif colors_enabled():
            print(colored_subnet_output(details))
        else:
            for k, v in details.items():
                print(f"  {k}: {v}")
    elif op == "adv":
        if len(a) < 2:
            raise ValueError("Usage: subnet adv IP/CIDR NEW_PREFIX")
        details = advanced_subnet_calculator(a[0], a[1], max_details=args.limit)
        if is_json_mode():
            output(details, label="advanced_subnet")
        else:
            for k, v in details.items():
                if k == 'subnets':
                    print(f"\n  subnets ({details['count_subnets']}):")
                    for i, s in enumerate(v, 1):
                        if 'first_host' in s:
                            detail = (
                                f"hosts: {s['first_host']} - {s['last_host']}  "
                                f"broadcast: {s['broadcast']}  "
                                f"({s['usable_hosts']} usable)"
                            )
                        else:
                            detail = (
                                f"addresses: {s['first_address']} - {s['last_address']}  "
                                f"({s['num_addresses']} total)"
                            )
                        print(f"    [{i}] {s['network']}{s['cidr']}  {detail}")
                    if details['truncated']:
                        print(
                            f"    ... {details['count_subnets'] - details['shown_subnets']} "
                            "additional subnets omitted; change --limit to show more"
                        )
                elif k in ('count_subnets', 'shown_subnets', 'truncated'):
                    continue
                else:
                    print(f"  {k}: {v}")
    elif op == "vlsm":
        network = a[0]
        host_list = [int(h) for h in a[1:]]
        if not host_list:
            raise ValueError("Usage: subnet vlsm NETWORK HOST1 HOST2 ...")
        subnets = vlsm_calculator(network, host_list)
        if is_json_mode():
            output(subnets, label="vlsm")
        else:
            for idx, sub in enumerate(subnets, 1):
                print(f"  Subnet {idx} (requested: {sub['requested_hosts']} hosts):")
                for k, v in sub.items():
                    if k == 'requested_hosts':
                        continue
                    print(f"    {k}: {v}")
                print()
    elif op == "overlap":
        if len(a) < 2:
            raise ValueError("Usage: subnet overlap NET1 NET2")
        result = check_overlap(a[0], a[1])
        if is_json_mode():
            output(result, label="overlap")
        else:
            print(f"  Network 1: {result['network1']}")
            print(f"  Network 2: {result['network2']}")
            print(f"  Overlaps : {result['overlaps']}")
            if result['overlap_network']:
                print(f"  Overlap  : {result['overlap_network']}")
    elif op == "supernet":
        result = supernet(a)
        if is_json_mode():
            output(result, label="supernet")
        else:
            print(f"  Supernet: {result}")
    elif op == "range":
        if len(a) != 2:
            raise ValueError("Usage: subnet range FIRST_IP LAST_IP")
        cidrs = ipv4_range_to_cidrs(a[0], a[1])
        output(cidrs, label="cidrs")
    elif op == "contains":
        if len(a) != 2:
            raise ValueError("Usage: subnet contains CONTAINER ADDRESS_OR_NETWORK")
        output(subnet_contains(a[0], a[1]), label="containment")
    elif op == "exclude":
        if len(a) != 2:
            raise ValueError("Usage: subnet exclude CONTAINER EXCLUDED_NETWORK")
        output(subnet_exclude(a[0], a[1]), label="remaining_networks")
    elif op == "nth":
        if len(a) != 2:
            raise ValueError("Usage: subnet nth NETWORK INDEX")
        output(subnet_nth(a[0], int(a[1])), label="address")
    elif op == "audit":
        if not a:
            raise ValueError("Usage: subnet audit INVENTORY_FILE [PARENT_NETWORK]")
        inventory = load_subnet_inventory(a[0])
        parent = a[1] if len(a) > 1 else inventory.get("parent")
        result = subnet_audit(inventory["allocations"], parent)
        output(result, label="subnet_audit")
        return 0 if result["status"] == "ok" else 1


def _dispatch_ipv6(args):
    op = args.op
    val = args.value
    if op == "expand":
        output(ipv6_expand(val), label="expanded")
    elif op == "compress":
        output(ipv6_compress(val), label="compressed")
    elif op == "tobin":
        output(ipv6_to_binary(val), label="binary")
    elif op == "type":
        if is_json_mode():
            output({"address": val, "type": ipv6_type(val)}, label="ipv6")
        else:
            print(f"  {val}: {ipv6_type(val)}")
    elif op == "subnet":
        details = ipv6_subnet_calculator(val)
        if is_json_mode():
            output(details, label="ipv6_subnet")
        else:
            for k, v in details.items():
                print(f"  {k}: {v}")
    elif op == "ula":
        output(generate_ipv6_ula(), label="ula")


def _dispatch_mac(args):
    op = args.op
    val = args.value
    if op == "info":
        info = mac_info(val)
        if is_json_mode():
            output(info, label="mac")
        else:
            print(f"  Normalized : {info['normalized']}")
            print(f"  OUI        : {info['oui']}")
            print(f"  Unicast    : {info['is_unicast']}")
            print(f"  Multicast  : {info['is_multicast']}")
            print(f"  Local (LAA): {info['is_local']}")
            print("  Formats:")
            for style, v in info['all_formats'].items():
                print(f"    {style:5s}: {v}")
    elif op == "format":
        output(mac_format(val, args.style), label="mac")
    elif op == "normalize":
        output(mac_normalize(val), label="mac")
    elif op == "vendor":
        database = args.db
        if database or default_oui_database_path().is_file():
            output(mac_vendor_lookup(val, database), label="vendor")
        else:
            output(mac_vendor(val), label="oui")
    elif op == "generate":
        count = int(val) if val else 1
        output(generate_local_macs(count, args.style), label="mac_addresses")
    elif op == "oui-update":
        output(update_oui_database(args.db, args.url, args.timeout), label="oui_database")


def _dispatch_net(args):
    op = args.op
    target = args.target
    output_format = "json" if getattr(args, "json", False) else args.output_format
    if args.timeout is not None and args.timeout <= 0:
        raise ValueError("Timeout must be greater than zero")
    if not 1 <= args.workers <= 256:
        raise ValueError("Workers must be between 1 and 256")
    if op == "doctor":
        targets = read_targets(args.input_file) if args.input_file else ([target] if target else [])
        if not targets:
            raise ValueError("Usage: net doctor TARGET or net doctor --input FILE")
        timeout = args.timeout if args.timeout is not None else 5.0
        results = run_batch(
            targets,
            lambda item: doctor_target(item, timeout, args.warn_days),
            args.workers,
        )
        emit_records(results, output_format, label="doctor")
        return 1 if any(result.get("status") in {"warning", "failed"} for result in results) else 0
    elif op == "wait":
        if not target or not args.extra:
            raise ValueError("Usage: net wait HOST PORT [--timeout SECONDS] [--interval SECONDS]")
        timeout = args.timeout if args.timeout is not None else 60.0
        result = wait_for_service(target, int(args.extra[0]), timeout, args.interval)
        if output_format in {"csv", "ndjson"}:
            emit_records([result], output_format, label="wait")
        else:
            output(result, label="wait")
        return 0 if result["status"] == "ready" else 1
    elif op == "cert-audit":
        if args.input_file:
            targets = read_targets(args.input_file)
        elif target and Path(target).expanduser().is_file():
            targets = read_targets(target)
        elif target:
            targets = [target]
        else:
            raise ValueError("Usage: net cert-audit HOST_OR_FILE or net cert-audit --input FILE")
        timeout = int(args.timeout if args.timeout is not None else 5)
        results = audit_certificates(targets, args.warn_days, timeout, args.workers)
        emit_records(results, output_format, label="certificates")
        return 1 if any(result.get("status") != "ok" for result in results) else 0
    elif op == "dns-health":
        targets = read_targets(args.input_file) if args.input_file else ([target] if target else [])
        if not targets:
            raise ValueError("Usage: net dns-health DOMAIN or net dns-health --input FILE")
        timeout = int(args.timeout if args.timeout is not None else 5)
        results = run_batch(
            targets,
            lambda item: dns_health(item, timeout, args.dkim_selector),
            args.workers,
        )
        emit_records(results, output_format, label="dns_health")
        return 1 if any(result.get("status") != "ok" for result in results) else 0
    elif op == "local":
        result = local_network_inventory()
        if output_format in {"csv", "ndjson"}:
            emit_records([result], output_format, label="local_network")
        else:
            output(result, label="local_network")
        return 0
    elif op == "ping":
        result = ping_host(target, timeout=max(1, int(args.timeout or 2)))
        if is_json_mode():
            output(result, label="ping")
        else:
            status = "alive" if result['alive'] else "unreachable"
            print(f"  {result['host']}: {status}")
            print(f"  Packets: {result['packets_sent']} sent, {result['packets_received']} received, {result['packet_loss_pct']}% loss")
            if result['avg_ms'] is not None:
                print(f"  RTT: min={result['min_ms']}ms avg={result['avg_ms']}ms max={result['max_ms']}ms")
    elif op == "portscan":
        ports = []
        for pa in args.extra:
            if '-' in pa:
                start, end = pa.split('-', 1)
                ports.extend(range(int(start), int(end) + 1))
            else:
                ports.append(int(pa))
        if not ports:
            raise ValueError("Usage: net portscan HOST PORT1 [PORT2 ...] or HOST 20-25")
        results = tcp_port_check(target, ports, timeout=args.timeout or 1.0)
        if is_json_mode():
            output(results, label="portscan")
        else:
            for r in results:
                print(f"  {r['port']:5d}/tcp  {r['state']:8s}  {r['service']}")
    elif op in ("traceroute", "tracert"):
        hops = traceroute(target, timeout=max(1, int(args.timeout or 2)))
        if is_json_mode():
            output(hops, label="traceroute")
        else:
            for h in hops:
                if h['ip'] is None:
                    print(f"  {h['hop']:2d}  * * *")
                else:
                    rtt = f"{h['rtt_ms']:.1f}ms" if h['rtt_ms'] else "?"
                    hn = h['hostname'] if h['hostname'] != h['ip'] else ""
                    if hn:
                        print(f"  {h['hop']:2d}  {hn} ({h['ip']})  {rtt}")
                    else:
                        print(f"  {h['hop']:2d}  {h['ip']}  {rtt}")
    elif op == "pingsweep":
        results = ping_sweep(
            target, timeout=max(1, int(args.timeout or 1)), max_threads=args.workers
        )
        if is_json_mode():
            output(results, label="pingsweep")
        else:
            alive = [r for r in results if r['alive']]
            dead = [r for r in results if not r['alive']]
            print(f"  {len(alive)} hosts up, {len(dead)} hosts down")
            for r in alive:
                rtt = f"{r['rtt_ms']:.1f}ms" if r['rtt_ms'] else "?"
                print(f"    {r['ip']:15s}  up  {rtt}")

    elif op == "portscan-adv":
        ports = []
        do_banner = False
        for pa in args.extra:
            if pa in ("banner", "grab"):
                do_banner = True
            elif pa == "top20":
                ports = list(TOP_PORTS.keys())
            elif '-' in pa:
                start, end = pa.split('-', 1)
                ports.extend(range(int(start), int(end) + 1))
            else:
                ports.append(int(pa))
        if not ports:
            ports = list(TOP_PORTS.keys())
        results = tcp_port_scan_advanced(
            target, ports, timeout=args.timeout or 1.0,
            grab_banner=do_banner, max_threads=args.workers,
        )
        if is_json_mode():
            output(results, label="portscan")
        else:
            for r in results:
                line = f"  {r['port']:5d}/tcp  {r['state']:8s}  {r['service']}"
                if r.get('banner'):
                    banner_preview = r['banner'][:60].replace('\n', ' ')
                    line += f"  | {banner_preview}"
                print(line)

    elif op == "portscan-udp":
        ports = []
        for pa in args.extra:
            if '-' in pa:
                start, end = pa.split('-', 1)
                ports.extend(range(int(start), int(end) + 1))
            else:
                ports.append(int(pa))
        if not ports:
            raise ValueError("Usage: net portscan-udp HOST PORT1 [PORT2 ...]")
        results = udp_port_check(target, ports, timeout=args.timeout or 2.0)
        if is_json_mode():
            output(results, label="udpscan")
        else:
            for r in results:
                print(f"  {r['port']:5d}/udp  {r['state']:15s}  {r['service']}")

    elif op == "portscan-net":
        if not args.extra:
            raise ValueError("Usage: net portscan-net NETWORK PORT")
        port = int(args.extra[0])
        results = scan_network_port(
            target, port, timeout=args.timeout or 1.0, max_threads=args.workers
        )
        if is_json_mode():
            output(results, label="netscan")
        else:
            open_hosts = [r for r in results if r['state'] == 'open']
            print(f"  Port {port}/tcp open on {len(open_hosts)}/{len(results)} hosts:")
            for r in open_hosts:
                print(f"    {r['ip']}")

    elif op == "banner":
        if not args.extra:
            raise ValueError("Usage: net banner HOST PORT")
        port = int(args.extra[0])
        result = banner_grab(target, port, timeout=args.timeout or 2.0)
        if is_json_mode():
            output({"host": target, "port": port, "banner": result}, label="banner")
        elif result:
            print(result)
        else:
            print("  No banner received")

    elif op == "whois":
        output(whois_lookup(target), label="whois")

    elif op in ("traceroute-asn",):
        hops = traceroute_asn(target, timeout=max(1, int(args.timeout or 2)))
        if is_json_mode():
            output(hops, label="traceroute_asn")
        else:
            for h in hops:
                if h['ip'] is None:
                    print(f"  {h['hop']:2d}  * * *")
                else:
                    rtt = f"{h['rtt_ms']:.1f}ms" if h['rtt_ms'] else "?"
                    asn = h['asn'] or "?"
                    country = h['country'] or ""
                    hn = h['hostname'] if h['hostname'] and h['hostname'] != h['ip'] else ""
                    if hn:
                        print(f"  {h['hop']:2d}  {hn} ({h['ip']})  {rtt}  [{asn} {country}]")
                    else:
                        print(f"  {h['hop']:2d}  {h['ip']}  {rtt}  [{asn} {country}]")

    elif op == "dns-type":
        if not args.extra:
            raise ValueError("Usage: net dns-type DOMAIN TYPE [SERVER]")
        rtype = args.extra[0] if args.extra else "A"
        server = args.extra[1] if len(args.extra) > 1 else None
        result = dns_lookup_type(
            target, rtype, server=server, timeout=max(1, int(args.timeout or 5))
        )
        if is_json_mode():
            output(result, label="dns")
        else:
            print(f"  {result['domain']} {result['type']} (server: {result['server']}):")
            for rec in result.get('records', []):
                print(f"    {rec}")
            if 'error' in result:
                print(f"    Error: {result['error']}")

    elif op == "dns-compare":
        if not args.extra:
            raise ValueError("Usage: net dns-compare DOMAIN SERVER1 SERVER2 [TYPE]")
        servers = args.extra
        rtype = "A"
        # Last arg could be a record type
        if args.extra[-1].upper() in ("A","AAAA","MX","TXT","NS","CNAME","SOA"):
            rtype = args.extra[-1].upper()
            servers = args.extra[:-1]
        result = dns_compare(
            target, servers, rtype, timeout=max(1, int(args.timeout or 5))
        )
        if is_json_mode():
            output(result, label="dns_compare")
        else:
            print(f"  {result['domain']} ({result['type']}):")
            for srv, recs in result['results'].items():
                print(f"    {srv}: {', '.join(recs) if recs else 'no records'}")

    elif op == "dns-axfr":
        ns = args.extra[0] if args.extra else None
        result = dns_zone_transfer(
            target, nameserver=ns, timeout=max(1, int(args.timeout or 30))
        )
        if is_json_mode():
            output(result, label="zone_transfer")
        else:
            status = "SUCCESS" if result['success'] else "FAILED"
            print(f"  Zone transfer {target} @{result['nameserver']}: {status}")
            if result['success']:
                for rec in result['records'][:50]:
                    print(f"    {rec}")
                if len(result['records']) > 50:
                    print(f"    ... {len(result['records']) - 50} more records")
            if 'error' in result:
                print(f"    Error: {result['error']}")

    elif op == "rdns-sweep":
        results = reverse_dns_sweep(
            target, timeout=max(1, int(args.timeout or 2)), max_threads=args.workers
        )
        if is_json_mode():
            output(results, label="rdns_sweep")
        else:
            found = [r for r in results if r['hostname']]
            print(f"  {len(found)} PTR records found:")
            for r in found:
                print(f"    {r['ip']:15s}  {r['hostname']}")

    elif op == "arp":
        results = arp_scan()
        if is_json_mode():
            output(results, label="arp")
        else:
            print(f"  {len(results)} ARP entries:")
            for r in results:
                print(f"    {r['ip']:15s}  {r['mac']:17s}  {r['interface']}  {r['state']}")

    elif op == "certcheck":
        port = int(args.extra[0]) if args.extra else 443
        result = cert_check(target, port, timeout=max(1, int(args.timeout or 5)))
        if is_json_mode():
            output(result, label="cert")
        else:
            if 'error' in result:
                print(f"  {target}:{port} - {result['error']}")
            else:
                if result.get('expired'):
                    status = "EXPIRED"
                elif result.get('not_yet_valid'):
                    status = "NOT YET VALID"
                else:
                    status = f"{result['days_remaining']}d remaining"
                print(f"  {target}:{port}")
                print(f"    Subject : {result['subject']}")
                print(f"    Issuer  : {result['issuer']}")
                print(f"    Valid   : {result['not_before']} - {result['not_after']}")
                print(f"    Status  : {status}")
                print(f"    SANs    : {', '.join(result['san'][:5])}")
                if len(result['san']) > 5:
                    print(f"              ... +{len(result['san'])-5} more")

    elif op == "headers":
        result = http_headers(target, timeout=max(1, int(args.timeout or 5)))
        if is_json_mode():
            output(result, label="headers")
        else:
            if 'error' in result:
                print(f"  {target}: {result['error']}")
            else:
                print(f"  {target} [{result.get('status_code', '?')}]")
                print("  Security headers:")
                for name, info in result.get('security_headers', {}).items():
                    mark = "+" if info['present'] else "-"
                    val = f" ({info['value'][:50]})" if info['value'] else ""
                    print(f"    [{mark}] {name}{val}")

    elif op == "dns":
        result = dns_lookup(target)
        if is_json_mode():
            output(result, label="dns")
        elif 'error' in result:
            print(f"  {result['domain']}: {result['error']}")
        else:
            print(f"  Domain   : {result['domain']}")
            print(f"  Hostname : {result['hostname']}")
            if result['aliases']:
                print(f"  Aliases  : {', '.join(result['aliases'])}")
            print(f"  Addresses: {', '.join(result['addresses'])}")
    elif op == "rdns":
        result = reverse_dns_lookup(target)
        if is_json_mode():
            output(result, label="rdns")
        elif 'error' in result:
            print(f"  {result['ip']}: {result['error']}")
        else:
            print(f"  IP       : {result['ip']}")
            print(f"  Hostname : {result['hostname']}")
            if result.get('aliases'):
                print(f"  Aliases  : {', '.join(result['aliases'])}")

    elif op == "random-ports":
        minimum = int(target) if target else 49152
        maximum = int(args.extra[0]) if args.extra else 65535
        count = int(args.extra[1]) if len(args.extra) > 1 else 10
        ports = generate_random_ports(minimum, maximum, count)
        output(ports, label="ports")


def _parse_firewall_ports(value: str, extra_port: Optional[int] = None) -> List[int]:
    ports = []
    for token in re.split(r"[,\s]+", value.strip()) if value.strip() else []:
        if not token.isdigit():
            raise ValueError(f"Invalid firewall port: {token}")
        ports.append(_validate_port(int(token)))
    if extra_port is not None:
        ports.append(_validate_port(extra_port))
    result = list(dict.fromkeys(ports))
    if len(result) > 32:
        raise ValueError("A firewall diagnostic accepts at most 32 ports")
    return result


def _dispatch_doctor(args):
    if args.timeout <= 0:
        raise ValueError("Timeout must be greater than zero")
    _validate_log_options(args.lines, args.since)
    if args.raw_logs and args.logs == "none":
        raise ValueError("--raw-logs requires an explicit --logs selection")
    operation = "system" if args.op == "general" else args.op
    nginx_probe_flags = bool(args.url or args.host_header or args.sni or args.follow_redirects or args.insecure or args.config)
    if operation != "nginx" and nginx_probe_flags:
        raise ValueError("--url, --host-header, --sni, --follow-redirects, --insecure, and --config apply only to doctor nginx")
    if operation not in {"system", "disk"} and args.du:
        raise ValueError("--du applies only to doctor system or doctor disk")
    if operation not in {"network", "service", "firewall"} and args.port is not None:
        raise ValueError("--port applies only to doctor network, doctor service, or doctor firewall")
    if operation == "system":
        if args.logs not in {"none", "system", "all"}:
            raise ValueError("doctor system supports --logs none, system, or all")
        result = system_diagnostic(
            path=args.target or "/", include_du=args.du,
            include_logs=args.logs != "none", lines=args.lines, since=args.since,
            raw_logs=args.raw_logs, timeout=args.timeout, symptom=args.symptom,
            expected=args.expected, recent_change=args.recent_change,
        )
    elif operation == "disk":
        if args.logs != "none" or args.raw_logs:
            raise ValueError("doctor disk does not read logs")
        result = disk_diagnostic(
            args.target or "/", include_du=args.du, timeout=args.timeout,
            symptom=args.symptom, expected=args.expected, recent_change=args.recent_change,
        )
    elif operation == "service":
        if not args.target:
            raise ValueError("Usage: doctor service NAME [--port PORT] [--logs service]")
        if args.logs not in {"none", "service", "all"}:
            raise ValueError("doctor service supports --logs none, service, or all")
        result = service_diagnostic(
            args.target, include_logs=args.logs != "none", lines=args.lines,
            since=args.since, raw_logs=args.raw_logs, timeout=args.timeout,
            symptom=args.symptom, expected=args.expected, recent_change=args.recent_change,
            port=args.port,
        )
    elif operation == "network":
        if args.logs != "none" or args.raw_logs:
            raise ValueError("doctor network does not read logs")
        result = network_diagnostic(
            args.target or None, port=args.port or 443, timeout=args.timeout,
            symptom=args.symptom, expected=args.expected, recent_change=args.recent_change,
        )
    elif operation == "firewall":
        if args.logs != "none" or args.raw_logs:
            raise ValueError("doctor firewall does not read logs")
        result = firewall_diagnostic(
            _parse_firewall_ports(args.target, args.port), timeout=args.timeout,
            symptom=args.symptom, expected=args.expected, recent_change=args.recent_change,
        )
    elif operation == "nginx":
        if args.logs == "system":
            raise ValueError("doctor nginx supports --logs none, service, error, access, or all")
        if (args.host_header or args.sni or args.follow_redirects or args.insecure) and not args.url:
            raise ValueError("--host-header, --sni, --follow-redirects, and --insecure require --url")
        if args.sni and urllib.parse.urlsplit(args.url).scheme != "https":
            raise ValueError("--sni requires an HTTPS --url")
        if args.insecure and urllib.parse.urlsplit(args.url).scheme != "https":
            raise ValueError("--insecure requires an HTTPS --url")
        result = nginx_diagnostic(
            service_name=args.target or "nginx", binary=args.binary,
            config=args.config, url=args.url, host_header=args.host_header,
            log_mode=args.logs, lines=args.lines, since=args.since,
            raw_logs=args.raw_logs, timeout=args.timeout, sni=args.sni,
            follow_redirects=args.follow_redirects, verify_tls=not args.insecure,
            symptom=args.symptom, expected=args.expected, recent_change=args.recent_change,
        )
    else:
        raise ValueError(f"Unsupported diagnostic: {operation}")
    output(result, label=f"{operation}_diagnostic")
    return 1 if result.get("status") in {"warning", "failed"} else 0


def _dispatch_vendor(args):
    op = args.op
    a = args.args
    if op == "profiles":
        output(platform_profiles(include_legacy=args.legacy), label="platform_profiles")
    elif op == "vlan":
        if len(a) < 2:
            raise ValueError("Usage: vendor vlan VENDOR VLAN_ID [NAME] [PORTS...]")
        vendor = a[0]
        vlan_id = int(a[1])
        vlan_name = a[2] if len(a) > 2 else None
        ports = a[3:] if len(a) > 3 else None
        output(
            vlan_helper(
                vendor,
                vlan_id,
                vlan_name,
                ports,
                platform_name=args.platform_name,
                software_version=args.software_version,
                mode=args.mode,
                allowed_vlans=args.allowed_vlans,
                native_vlan=args.native_vlan,
                allow_legacy=args.legacy,
            ),
            label="configuration",
        )
    elif op == "acl":
        if len(a) < 6:
            raise ValueError("Usage: vendor acl VENDOR NAME ACTION PROTO SRC DST [SPORT] [DPORT]")
        src_port = int(a[6]) if len(a) > 6 and a[6] != "0" else None
        dst_port = int(a[7]) if len(a) > 7 and a[7] != "0" else None
        output(
            acl_helper(
                a[0], a[1], a[2], a[3], a[4], a[5], src_port, dst_port,
                platform_name=args.platform_name,
                software_version=args.software_version,
                allow_legacy=args.legacy,
            ),
            label="configuration",
        )


def _dispatch_cheat(args):
    if args.legacy and args.sheet != "vlan":
        raise ValueError(
            "--legacy is currently available only for the VLAN cheatsheet"
        )
    content = render_cheatsheet(
        args.sheet,
        args.section,
        include_legacy=args.legacy,
        platform_name=args.platform_name,
        show_sources=args.show_sources,
    )
    output(content, label="cheatsheet")


# ---------------------------------------------------------------------------
#  AI assistant (optional, opt-in) - standard library only (urllib).
#  No network call happens unless the `ai` command is used, so the tool stays
#  dependency-free and fully offline by default.
# ---------------------------------------------------------------------------

_AI_SYSTEM = (
    "You are a concise network engineering assistant inside a CLI named "
    "SysAdminToolbox. Answer accurately and briefly for a professional sysadmin. "
    "When a SysAdminToolbox command would help, name it (groups: convert, subnet, "
    "ipv6, mac, net, vendor, cheat)."
)

# provider -> (env var with the API key, default model, base url; None base url = anthropic)
_AI_CLOUD = {
    "anthropic": ("ANTHROPIC_API_KEY", "claude-haiku-4-5-20251001", None),
    "openai":    ("OPENAI_API_KEY",    "gpt-4o-mini",              "https://api.openai.com/v1"),
    "deepseek":  ("DEEPSEEK_API_KEY",  "deepseek-chat",            "https://api.deepseek.com/v1"),
    "kimi":      ("MOONSHOT_API_KEY",  "moonshot-v1-8k",           "https://api.moonshot.cn/v1"),
}
_AI_OLLAMA_DEFAULT = "llama3.2"


def _ai_timeout() -> int:
    try:
        return int(os.environ.get("LLM_TIMEOUT", "60"))
    except ValueError:
        return 60


def _ai_prompt_digest(prompt: str) -> str:
    """Short hash of the prompt for transparency/logging - never the prompt itself."""
    return "sha256:" + hashlib.sha256((prompt or "").encode("utf-8", "ignore")).hexdigest()[:12]


def _ai_ollama_host() -> str:
    return os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")


def _ai_ollama_reachable() -> bool:
    try:
        req = urllib.request.Request(_ai_ollama_host() + "/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=2):
            return True
    except (urllib.error.URLError, OSError):
        return False


def _ai_resolve_provider(spec: str):
    """Resolve a provider spec to (provider, model).

    'auto' (default) picks a reachable local Ollama, else the first cloud provider
    whose API key is set. Otherwise 'provider' or 'provider:model'.
    """
    spec = (spec or "auto").strip().lower()
    if spec in ("", "auto"):
        if _ai_ollama_reachable():
            return ("ollama", _AI_OLLAMA_DEFAULT)
        for name, (env, default, _url) in _AI_CLOUD.items():
            if os.environ.get(env):
                return (name, default)
        return ("ollama", _AI_OLLAMA_DEFAULT)
    provider, _, model = spec.partition(":")
    if provider == "ollama":
        return ("ollama", model or _AI_OLLAMA_DEFAULT)
    if provider in _AI_CLOUD:
        return (provider, model or _AI_CLOUD[provider][1])
    raise ValueError(
        "Unknown AI provider '%s' (use auto|ollama|anthropic|openai|deepseek|kimi)" % provider)


def _ai_call_ollama(prompt: str, model: str, system: str = _AI_SYSTEM) -> str:
    payload = json.dumps({
        "model": model, "system": system, "prompt": prompt,
        "stream": False, "options": {"temperature": 0.3},
    }).encode()
    req = urllib.request.Request(
        _ai_ollama_host() + "/api/generate", data=payload,
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=_ai_timeout()) as resp:
        return json.loads(resp.read()).get("response", "")


def _ai_call_openai_compat(prompt: str, model: str, api_key: str, base_url: str, system: str = _AI_SYSTEM) -> str:
    if not api_key:
        raise RuntimeError("Missing API key for this provider (set the matching *_API_KEY env var).")
    payload = json.dumps({
        "model": model, "temperature": 0.3,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    }).encode()
    req = urllib.request.Request(
        base_url.rstrip("/") + "/chat/completions", data=payload,
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + api_key},
        method="POST")
    with urllib.request.urlopen(req, timeout=_ai_timeout()) as resp:
        return json.loads(resp.read())["choices"][0]["message"]["content"]


def _ai_call_anthropic(prompt: str, model: str, api_key: str, system: str = _AI_SYSTEM) -> str:
    if not api_key:
        raise RuntimeError("Missing ANTHROPIC_API_KEY.")
    payload = json.dumps({
        "model": model, "max_tokens": 1024, "system": system,
        "messages": [{"role": "user", "content": prompt}],
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages", data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST")
    with urllib.request.urlopen(req, timeout=_ai_timeout()) as resp:
        return json.loads(resp.read())["content"][0]["text"]


def ai_complete(prompt: str, spec: str = "auto", system: str = None) -> str:
    """Run one completion and return the model's text. Raises RuntimeError on failure."""
    if system is None:
        system = _AI_SYSTEM
    provider, model = _ai_resolve_provider(spec)
    try:
        if provider == "ollama":
            return _ai_call_ollama(prompt, model, system)
        if provider == "anthropic":
            return _ai_call_anthropic(prompt, model, os.environ.get("ANTHROPIC_API_KEY", ""), system)
        env, _default, base_url = _AI_CLOUD[provider]
        return _ai_call_openai_compat(prompt, model, os.environ.get(env, ""), base_url, system)
    except (urllib.error.URLError, OSError) as exc:
        raise RuntimeError("AI request failed (%s): %s" % (provider, exc))
    except (KeyError, IndexError, json.JSONDecodeError) as exc:
        raise RuntimeError("Unexpected AI response (%s): %s" % (provider, exc))


def _ai_build_prompt(op: str, text: str) -> str:
    if op == "explain":
        return ("Explain the following network diagnostic or CLI output for a sysadmin, "
                "concisely and in plain language:\n\n" + text)
    if op == "suggest":
        return ("Given this SysAdminToolbox command reference:\n" + _AI_CMD_REFERENCE +
                "\nGive the single best command line for the request. Output ONLY the command, "
                "without the 'SysAdminToolbox' prefix and without prose.\nRequest: " + text)
    return text  # ask



# -- agent / run / diagnose: the AI drives SysAdminToolbox's own read-only commands --

# Command groups the AI may run as tools (read-only; ai/web are never exposed).
_AI_AGENT_TOOLS = {"convert", "subnet", "ipv6", "mac", "net", "doctor", "vendor", "cheat"}

_AI_CMD_REFERENCE = (
    "convert <op> <value>   ops: d2b b2d d2h h2d iptobin bintoip m2c c2m m2w w2m a2b b2a ipinfo ipclass\n"
    "subnet calc <IP/CIDR> | subnet adv <IP/CIDR> <new-prefix> | subnet vlsm <IP/CIDR> <hosts...>\n"
    "subnet range <ip1> <ip2> | subnet contains <net> <ip> | subnet exclude <net> <subnet>\n"
    "subnet overlap <a> <b> | subnet supernet <a> <b> | subnet audit <net...>\n"
    "ipv6 <op> <value>   ops: expand compress tobin type subnet ula\n"
    "mac info|normalize|vendor <mac> | mac format <mac> <colon|dash|cisco|bare> | mac generate <count> <style>\n"
    "net <op> <target>   ops: ping dns dns-type certcheck cert-audit dns-health headers traceroute-asn rdns whois portscan\n"
    "net dns-compare <domain> <resolver1> <resolver2>\n"
    "doctor <check> [target]   checks: system service disk network firewall nginx\n"
    "vendor vlan <cisco|juniper|huawei> <id> <name> [ports...] | vendor acl <platform> <name> <permit|deny> <proto> <src> <dst>\n"
    "cheat <topic>   topics: vlan acl firewall routing nat huawei mikrotik\n"
)


def _ai_extract_json(text: str):
    """Best-effort extraction of a single JSON object from model text."""
    text = re.sub(r"```(?:json)?", "", text or "").strip()
    candidates = [text]
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        try:
            obj = json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(obj, dict):
            return obj
    return {}


def _ai_tool_run(group, args):
    """Run one whitelisted read-only SysAdminToolbox command as a tool. Returns (ok, text)."""
    group = str(group).strip().lower()
    if group not in _AI_AGENT_TOOLS:
        return (False, "tool '%s' is not available" % group)
    cmd = [sys.executable, os.path.abspath(__file__), group] + [str(a) for a in (args or [])]
    cmd += ["--json", "--no-color"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=25)
    except subprocess.TimeoutExpired:
        return (False, "command timed out")
    out = (proc.stdout or proc.stderr or "").strip()
    return (proc.returncode == 0, out[:2000])


def _ai_confirm_cloud(provider, model, digest, yes, extra=""):
    """Return True to proceed. Cloud providers warn + confirm (or refuse non-interactively)."""
    if provider == "ollama" or yes:
        return True
    print("[ai] This uses cloud provider '%s' (model %s).%s Prompt digest %s"
          % (provider, model, extra, digest), file=sys.stderr)
    if sys.stdin.isatty():
        try:
            return input("[ai] Continue? [y/N] ").strip().lower() in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False
    raise RuntimeError(
        "Refusing to use cloud provider '%s' non-interactively; pass --yes, or use a local ollama." % provider)


_AI_AGENT_SYSTEM = (
    "You are a read-only network troubleshooting agent driving a CLI called SysAdminToolbox. "
    "Solve the user's goal by calling its commands as tools and reading their JSON output.\n"
    "Available commands (use one op per step):\n" + _AI_CMD_REFERENCE +
    "\nProtocol: reply with ONE JSON object and nothing else.\n"
    '  to run a command:  {"tool": "<group>", "args": ["<op>", "<arg>", ...], "why": "<short reason>"}\n'
    '  when finished:     {"final": "<diagnosis and concrete next steps>"}\n'
    "Prefer single-target diagnostics, avoid network-wide sweeps, and finish in a few steps."
)


def _ai_maybe_json(text):
    """Return parsed JSON when text is a JSON document, else the raw string.

    Lets `ai agent --json` embed each command's structured output instead of an
    opaque escaped blob.
    """
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return text


def _ai_agent(goal, spec, max_steps, as_json=False):
    """Autonomous tool-use loop: the model runs read-only commands until it can conclude.

    With as_json, collect the goal, every step (command, reason, ok, output) and
    the conclusion into one JSON object printed at the end, instead of streaming
    progress to stderr.
    """
    max_steps = max(1, min(int(max_steps or 8), 15))
    transcript = "GOAL: " + goal + "\n"
    steps = []

    def _report(conclusion, completed, note=None):
        report = {"goal": goal, "steps": steps,
                  "conclusion": conclusion, "completed": completed}
        if note:
            report["note"] = note
        print(json.dumps(report, indent=2))

    for step in range(1, max_steps + 1):
        raw = ai_complete(transcript + "\nWhat is your next JSON action?", spec, system=_AI_AGENT_SYSTEM)
        action = _ai_extract_json(raw)
        if action.get("final"):
            final = action["final"]
            if as_json:
                _report(final, True)
            else:
                print(final if isinstance(final, str) else json.dumps(final))
            return
        group = action.get("tool", "")
        args = action.get("args", []) or []
        if not group:
            if as_json:
                _report(raw.strip(), False, note="no actionable step returned")
            else:
                print("[agent] no actionable step returned; stopping.", file=sys.stderr)
                print(raw.strip())
            return
        line = (str(group) + " " + " ".join(str(a) for a in args)).strip()
        if not as_json:
            print("[agent] step %d: SysAdminToolbox %s  (%s)"
                  % (step, line, action.get("why", "")), file=sys.stderr)
        ok, out = _ai_tool_run(group, args)
        steps.append({"step": step, "command": line, "why": action.get("why", ""),
                      "ok": ok, "output": _ai_maybe_json(out)})
        transcript += "\nSTEP %d: `%s` -> %s\n%s\n" % (step, line, "ok" if ok else "ERROR", out)
    raw = ai_complete(transcript + "\nStep budget reached. Reply now with {\"final\": ...}.",
                      spec, system=_AI_AGENT_SYSTEM)
    action = _ai_extract_json(raw)
    final = action.get("final") or raw.strip()
    if as_json:
        _report(final, False, note="step budget reached")
    else:
        print(final)


def _ai_agent_plan(goal, spec):
    """--dry-run: print the ordered plan the agent would run, without executing anything."""
    system = ("You are a network troubleshooting planner for SysAdminToolbox (read-only). "
              "Available commands:\n" + _AI_CMD_REFERENCE +
              "\nGiven the goal, output an ordered, numbered plan of SysAdminToolbox commands you "
              "would run, each with a one-line reason. Do not execute anything.")
    print(ai_complete("GOAL: " + goal, spec, system=system).strip())


def _ai_run(nl, spec, yes):
    """Translate a natural-language request into one SysAdminToolbox command and run it."""
    system = ("Translate the request into ONE SysAdminToolbox command, using this reference:\n"
              + _AI_CMD_REFERENCE +
              "\nOutput ONLY the command, without the 'SysAdminToolbox' prefix and without prose.")
    raw = ai_complete("Request: " + nl, spec, system=system).strip()
    line = re.sub(r"```", "", raw).strip().splitlines()[0].strip() if raw else ""
    line = re.sub(r"^\$?\s*SysAdminToolbox\s+", "", line).strip()
    if not line:
        raise RuntimeError("The model did not return a command.")
    try:
        parts = shlex.split(line)
    except ValueError:
        parts = line.split()
    print("[ai] proposed: SysAdminToolbox " + line, file=sys.stderr)
    if not yes and sys.stdin.isatty():
        try:
            if input("[ai] Run it? [y/N] ").strip().lower() not in ("y", "yes"):
                print("[ai] Not run.", file=sys.stderr)
                return
        except (EOFError, KeyboardInterrupt):
            return
    ok, out = _ai_tool_run(parts[0], parts[1:]) if parts else (False, "empty command")
    print(out)


def _ai_diagnose(target, symptom, spec):
    """Run a fixed battery of read-only checks on a target, then narrate the result."""
    checks = [
        ("net", ["dns", target]),
        ("net", ["ping", target]),
        ("net", ["certcheck", target]),
        ("net", ["headers", "https://" + target]),
        ("net", ["traceroute-asn", target]),
    ]
    collected = []
    for group, args in checks:
        line = group + " " + " ".join(args)
        print("[diagnose] SysAdminToolbox " + line, file=sys.stderr)
        ok, out = _ai_tool_run(group, args)
        collected.append("### %s (%s)\n%s" % (line, "ok" if ok else "error", out))
    prompt = ("You are a network diagnostician. Below are read-only SysAdminToolbox results for '"
              + target + "'"
              + ((" (reported symptom: " + symptom + ")") if symptom else "")
              + ". Give a concise root-cause assessment and concrete next steps.\n\n"
              + "\n\n".join(collected))
    print(ai_complete(prompt, spec).strip())


def _dispatch_ai(args):
    op = args.op
    yes = getattr(args, "yes", False)
    if op == "explain" and not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    else:
        text = " ".join(args.text).strip()
    if not text:
        if op == "diagnose":
            raise ValueError("Usage: ai diagnose <target> [--symptom ...]")
        extra = " (or pipe output into 'ai explain')" if op == "explain" else ""
        raise ValueError("Nothing to send. Usage: ai %s \"<text>\"%s" % (op, extra))

    provider, model = _ai_resolve_provider(args.provider)
    extra = " Command outputs will be sent to it." if op in ("agent", "diagnose") else ""
    if not _ai_confirm_cloud(provider, model, _ai_prompt_digest(text), yes, extra):
        print("[ai] Aborted.", file=sys.stderr)
        return

    if op == "agent":
        if getattr(args, "dry_run", False):
            _ai_agent_plan(text, args.provider)
        else:
            _ai_agent(text, args.provider, getattr(args, "max_steps", 8), as_json=is_json_mode())
    elif op == "run":
        _ai_run(text, args.provider, yes)
    elif op == "diagnose":
        _ai_diagnose(text.split()[0], getattr(args, "symptom", None), args.provider)
    else:  # ask / explain / suggest
        answer = ai_complete(_ai_build_prompt(op, text), args.provider)
        if is_json_mode():
            output({"provider": provider, "model": model,
                    "prompt_digest": _ai_prompt_digest(text), "answer": answer}, label="ai")
        else:
            print(answer.strip())



# ---------------------------------------------------------------------------
#  Web mode (optional) - standard library http.server only.
#  Serves a local UI that runs the SAFE command groups and browses cheatsheets.
#  Network diagnostics (net) and the ai command are intentionally NOT exposed,
#  and the server binds 127.0.0.1 by default.
# ---------------------------------------------------------------------------

_WEB_SAFE = {
    "convert", "conv", "c", "subnet", "sub", "s", "ipv6", "v6",
    "mac", "m", "vendor", "v", "cheat", "cs",
}

_WEB_HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>SysAdminToolbox</title>
<style>
:root{color-scheme:light;--bg:#f9f9f7;--card:#fcfcfb;--ink:#0b0b0b;--sub:#52514e;--mut:#898781;--bd:rgba(11,11,11,.12);--ac:#2a78d6;--code:#f4f3f0;--codeink:#1f2933;--bad:#b3261e;}
@media(prefers-color-scheme:dark){:root{color-scheme:dark;--bg:#0d0d0d;--card:#1a1a19;--ink:#fff;--sub:#c3c2b7;--mut:#898781;--bd:rgba(255,255,255,.12);--ac:#3987e5;--code:#111110;--codeink:#d7d7cf;--bad:#f0857c;}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif;line-height:1.5}
.wrap{max-width:900px;margin:0 auto;padding:24px 18px 60px}
h1{font-size:1.25rem;margin:0 0 2px;display:flex;align-items:center;gap:9px}
.logo{width:28px;height:28px;border-radius:7px;background:var(--ac);color:#fff;display:grid;place-items:center;font-family:ui-monospace,monospace;font-weight:700}
.sub{color:var(--mut);font-size:.85rem;margin:0 0 18px}
.runbar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:12px}
#line{flex:1 1 320px;min-width:0;font:inherit;font-family:ui-monospace,monospace;color:var(--ink);background:var(--card);border:1px solid var(--bd);border-radius:9px;padding:10px 12px}
.chk{color:var(--sub);font-size:.85rem;display:flex;align-items:center;gap:5px}
button{cursor:pointer;font:inherit;border:1px solid var(--ac);background:var(--ac);color:#fff;border-radius:9px;padding:10px 16px}
button.ghost{background:var(--card);color:var(--sub);border-color:var(--bd);padding:5px 11px;font-size:.82rem;border-radius:999px}
button.ghost:hover{color:var(--ink)}
.out{background:var(--code);color:var(--codeink);border:1px solid var(--bd);border-radius:10px;padding:13px 15px;overflow-x:auto;max-width:100%;min-height:80px;white-space:pre;font-family:ui-monospace,monospace;font-size:.85rem;margin:0 0 20px}
.out.err{color:var(--bad)}
.grp{margin:16px 0 6px;font-size:.8rem;color:var(--mut);text-transform:uppercase;letter-spacing:.04em}
.chips{display:flex;flex-wrap:wrap;gap:7px}
a{color:var(--ac)}
footer{margin-top:26px;color:var(--mut);font-size:.8rem}
</style>
</head>
<body>
<div class="wrap">
  <h1><span class="logo">&gt;_</span> SysAdminToolbox</h1>
  <p class="sub">Local web UI - safe command groups only (convert, subnet, ipv6, mac, vendor, cheat).</p>
  <div class="runbar">
    <input id="line" placeholder="e.g. subnet calc 192.168.0.0/24" autocomplete="off" spellcheck="false">
    <label class="chk"><input type="checkbox" id="json"> JSON</label>
    <button id="run" type="button">Run</button>
  </div>
  <pre class="out" id="out">Ready. Pick an example or type a command.</pre>
  <div class="grp">Examples</div>
  <div class="chips" id="examples"></div>
  <div class="grp">Cheatsheets</div>
  <div class="chips" id="cheats"></div>
  <footer>SysAdminToolbox web mode - <a href="https://github.com/franckferman/SysAdminToolbox" target="_blank" rel="noopener">source</a></footer>
</div>
<script>
var EX=["convert ipinfo 192.168.1.42/24","subnet calc 192.168.0.0/24","subnet vlsm 192.168.1.0/24 50 30 10","ipv6 expand ::1","mac info AA:BB:CC:DD:EE:FF","vendor vlan cisco 10 Engineering"];
var CS=["vlan","acl","firewall","routing","nat","huawei","mikrotik"];
var line=document.getElementById("line"),out=document.getElementById("out"),jsonBox=document.getElementById("json");
function chip(text){var b=document.createElement("button");b.className="ghost";b.type="button";b.textContent=text;return b;}
EX.forEach(function(e){var b=chip(e);b.addEventListener("click",function(){line.value=e;run();});document.getElementById("examples").appendChild(b);});
CS.forEach(function(t){var b=chip("cheat "+t);b.addEventListener("click",function(){line.value="cheat "+t;jsonBox.checked=false;run();});document.getElementById("cheats").appendChild(b);});
function run(){
  var v=line.value.trim();if(!v){return;}
  out.className="out";out.textContent="Running...";
  fetch("/api/run?json="+(jsonBox.checked?1:0)+"&line="+encodeURIComponent(v))
    .then(function(r){return r.json();})
    .then(function(d){out.className="out"+(d.ok?"":" err");out.textContent=(d.output||"").replace(/\s+$/,"")||"(no output)";})
    .catch(function(e){out.className="out err";out.textContent="Request failed: "+e;});
}
document.getElementById("run").addEventListener("click",run);
line.addEventListener("keydown",function(e){if(e.key==="Enter"){run();}});
</script>
</body>
</html>
"""


def _web_run(line: str, as_json: bool):
    """Run one whitelisted command line in an isolated subprocess. Returns (ok, text)."""
    try:
        parts = shlex.split(line)
    except ValueError as exc:
        return (False, "Parse error: " + str(exc))
    if not parts:
        return (False, "Empty command.")
    if parts[0].lower() not in _WEB_SAFE:
        return (False, "Command '%s' is not available in web mode. "
                       "Allowed: convert, subnet, ipv6, mac, vendor, cheat." % parts[0])
    cmd = [sys.executable, os.path.abspath(__file__)] + parts + ["--no-color"]
    if as_json:
        cmd.append("--json")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except subprocess.TimeoutExpired:
        return (False, "Command timed out.")
    if proc.returncode != 0:
        return (False, (proc.stderr or proc.stdout or "Error").strip())
    return (True, proc.stdout)


def _make_web_handler():
    class _WebHandler(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep the console quiet
            return

        def _send(self, code, body, ctype="application/json; charset=utf-8"):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if parsed.path in ("/", "/index.html"):
                self._send(200, _WEB_HTML, "text/html; charset=utf-8")
                return
            if parsed.path == "/api/run":
                qs = urllib.parse.parse_qs(parsed.query)
                line = (qs.get("line", [""])[0]).strip()
                as_json = (qs.get("json", ["0"])[0]) not in ("0", "false", "")
                ok, out = _web_run(line, as_json)
                self._send(200 if ok else 400, json.dumps({"ok": ok, "output": out}))
                return
            self._send(404, json.dumps({"ok": False, "output": "Not found"}))

    return _WebHandler


def _dispatch_web(args):
    try:
        httpd = http.server.HTTPServer((args.host, args.port), _make_web_handler())
    except OSError as exc:
        raise RuntimeError("Cannot bind %s:%d (%s)" % (args.host, args.port, exc))
    print("SysAdminToolbox web UI on http://%s:%d/" % (args.host, args.port), file=sys.stderr)
    print("Safe commands only (convert, subnet, ipv6, mac, vendor, cheat). Ctrl+C to stop.",
          file=sys.stderr)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", file=sys.stderr)
    finally:
        httpd.server_close()


DISPATCH = {
    "convert": _dispatch_convert, "conv": _dispatch_convert, "c": _dispatch_convert,
    "subnet": _dispatch_subnet, "sub": _dispatch_subnet, "s": _dispatch_subnet,
    "ipv6": _dispatch_ipv6, "v6": _dispatch_ipv6,
    "mac": _dispatch_mac, "m": _dispatch_mac,
    "net": _dispatch_net, "n": _dispatch_net,
    "doctor": _dispatch_doctor, "diag": _dispatch_doctor, "diagnose": _dispatch_doctor,
    "vendor": _dispatch_vendor, "v": _dispatch_vendor,
    "cheat": _dispatch_cheat, "cs": _dispatch_cheat,
    "ai": _dispatch_ai,
    "web": _dispatch_web,
}


# ---------------------------------------------------------------------------
#  Interactive REPL
# ---------------------------------------------------------------------------

def _repl():
    c = Colors()
    print(f"{c.CYAN}{BANNER}{c.RESET}\n")
    print(f"  {c.DIM}Interactive mode. Type a command or 'help'. Ctrl+C to exit.{c.RESET}\n")

    parser = _setup_parser()

    while True:
        try:
            line = input(f"{c.GREEN}sat{c.RESET} > ").strip()
        except (EOFError, KeyboardInterrupt):
            print(f"\n{c.DIM}Bye.{c.RESET}")
            break

        if not line:
            continue
        if line.lower() in ('exit', 'quit', 'q'):
            print(f"{c.DIM}Bye.{c.RESET}")
            break
        if line.lower() in ('help', 'h', '?'):
            print(f"\n{c.BOLD}Available commands:{c.RESET}")
            print(f"  {c.YELLOW}convert{c.RESET} (c)   d2b, b2d, d2h, h2d, b2h, h2b, iptobin, bintoip, m2c, c2m ...")
            print(f"  {c.YELLOW}subnet{c.RESET}  (s)   calc, adv, vlsm, overlap, supernet")
            print(f"  {c.YELLOW}ipv6{c.RESET}    (v6)  expand, compress, tobin, type, subnet")
            print(f"  {c.YELLOW}mac{c.RESET}     (m)   info, format, normalize, vendor")
            print(f"  {c.YELLOW}net{c.RESET}     (n)   ping, portscan, traceroute, whois, dns, rdns")
            print(f"  {c.YELLOW}doctor{c.RESET}  (diag) system, nginx, service, disk, network, firewall")
            print(f"  {c.YELLOW}vendor{c.RESET}  (v)   vlan, acl")
            print(f"  {c.YELLOW}cheat{c.RESET}   (cs)  vlan, acl, huawei, mikrotik, firewall, routing, nat")
            print(f"\n  {c.DIM}Flags: --json, --no-color{c.RESET}")
            print(f"  {c.DIM}Type 'exit' or Ctrl+C to quit.{c.RESET}\n")
            continue
        if line.lower() == 'banner':
            print(f"{c.CYAN}{BANNER}{c.RESET}")
            continue

        try:
            tokens = shlex.split(line)
        except ValueError as e:
            print(f"  {c.RED}Error: {e}{c.RESET}")
            continue
        try:
            args = parser.parse_args(tokens)
            if args.json:
                set_json_mode(True)
            if args.command and args.command in DISPATCH:
                DISPATCH[args.command](args)
            else:
                print(f"  {c.RED}Unknown command. Type 'help'.{c.RESET}")
        except SystemExit:
            pass
        except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError) as e:
            print(f"  {c.RED}Error: {e}{c.RESET}")
        except RuntimeError as e:
            print(f"  {c.RED}Error: {e}{c.RESET}")
        finally:
            set_json_mode(False)


# ---------------------------------------------------------------------------
#  Main entry point
# ---------------------------------------------------------------------------

def main():
    parser = _setup_parser()
    args = parser.parse_args()

    if args.json:
        set_json_mode(True)

    if args.interactive:
        _repl()
        return

    if len(sys.argv) == 1:
        c = Colors()
        print(f"{c.CYAN}{BANNER}{c.RESET}\n")
        parser.print_help()
        sys.exit(0)

    if not args.command:
        parser.print_help()
        sys.exit(0)

    try:
        if args.command in DISPATCH:
            exit_code = DISPATCH[args.command](args)
            if isinstance(exit_code, int) and exit_code:
                sys.exit(exit_code)
        else:
            parser.print_help()
    except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except BrokenPipeError:
        try:
            sys.stdout.close()
        finally:
            sys.exit(0)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
