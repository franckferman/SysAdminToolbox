#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Network administration calculations, diagnostics, and configuration helpers.

Author   : Franck FERMAN (@franckferman)
Created  : 2024-08-24
Version  : 3.3.2
License  : MIT

Repository:
    https://github.com/franckferman/SysAdminToolbox
License details:
    See the LICENSE file.
"""

import argparse
import ipaddress
import itertools
import json
import os
import platform
import re
import secrets
import shlex
import socket
import ssl
import subprocess
import sys
import urllib.error
import urllib.request

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, cast

__version__ = "3.3.2"

MAX_SUBNET_DETAILS = 256
MAX_NETWORK_HOSTS = 4096


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

def vlan_helper(vendor: str, vlan_id: int, vlan_name: Optional[str] = None,
                ports: Optional[List[str]] = None) -> str:
    _validate_vlan_id(vlan_id)
    v = vendor.lower()
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
        lines += [
            f"interface range {port_range}",
            " switchport mode access",
            f" switchport access vlan {vlan_id}",
            "end",
            "write memory",
        ]
    elif v == 'juniper':
        name = vlan_name or f'vlan-{vlan_id}'
        interfaces = ports or ['ge-0/0/0']
        lines = [
            "configure",
            f"set vlans {name} vlan-id {vlan_id}",
        ]
        lines.extend(
            f"set interfaces {iface} unit 0 family ethernet-switching vlan members {name}"
            for iface in interfaces
        )
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
            for p in ports:
                lines += [
                    f"interface {p}",
                    " port link-type access",
                    f" port default vlan {vlan_id}",
                    "quit",
                ]
        lines.append("return")
    else:
        raise ValueError(
            f"Unsupported vendor: '{vendor}'. Supported: cisco, juniper, huawei."
        )

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
#  ACL helper
# ---------------------------------------------------------------------------

def acl_helper(vendor: str, acl_name: str, action: str, protocol: str,
               src: str, dst: str,
               src_port: Optional[int] = None,
               dst_port: Optional[int] = None) -> str:
    if action.lower() not in ('permit', 'deny'):
        raise ValueError(f"Invalid action: '{action}' (must be 'permit' or 'deny')")
    _validate_config_name(acl_name, "ACL name")
    v = vendor.lower()
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
    """Validate that *host* is a valid IPv4 address or hostname."""
    try:
        ipaddress.IPv4Address(host)
        return host
    except ipaddress.AddressValueError:
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


def tcp_port_scan_advanced(host: str, ports: List[int], timeout: float = 1.0,
                           grab_banner: bool = False) -> List[Dict[str, Any]]:
    _validate_host(host)
    for p in ports:
        _validate_port(p)
    workers = min(100, len(ports)) if ports else 1
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


def scan_network_port(network: str, port: int, timeout: float = 1.0) -> List[Dict[str, Any]]:
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
    workers = min(100, len(hosts)) if hosts else 1
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
    valid_types = {"A", "AAAA", "MX", "TXT", "NS", "CNAME", "SOA", "PTR", "SRV"}
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
        return {"domain": domain, "type": record_type, "server": server or "default",
                "records": [], "error": "Neither dig nor nslookup found"}
    except subprocess.TimeoutExpired:
        return {"domain": domain, "type": record_type, "server": server or "default",
                "records": [], "error": "nslookup timed out"}


def dns_compare(domain: str, servers: List[str], record_type: str = "A") -> Dict[str, Any]:
    results = {}
    for srv in servers:
        lookup = dns_lookup_type(domain, record_type, server=srv)
        parsed = []
        for rec in lookup.get("records", []):
            parts = rec.split()
            parsed.append(" ".join(parts[4:]) if len(parts) >= 5 else rec)
        results[srv] = parsed
    return {"domain": domain, "type": record_type, "results": results}


def dns_zone_transfer(domain: str, nameserver: Optional[str] = None) -> Dict[str, Any]:
    if not nameserver:
        ns_lookup = dns_lookup_type(domain, "NS")
        ns_records = ns_lookup.get("records", [])
        if not ns_records:
            return {"domain": domain, "nameserver": None, "success": False, "records": [], "error": "No NS found"}
        nameserver = ns_records[0].split()[-1].rstrip(".")
    try:
        result = subprocess.run(["dig", "axfr", domain, f"@{nameserver}"],
                                capture_output=True, text=True, timeout=30)
        records = [l.strip() for l in result.stdout.splitlines() if l.strip() and not l.startswith((";", "<<>>"))]
        success = len(records) > 0 and "Transfer failed" not in result.stdout and "refused" not in result.stdout.lower()
        return {"domain": domain, "nameserver": nameserver, "success": success, "records": records}
    except FileNotFoundError:
        return {"domain": domain, "nameserver": nameserver, "success": False, "records": [], "error": "dig not found"}
    except subprocess.TimeoutExpired:
        return {"domain": domain, "nameserver": nameserver, "success": False, "records": [], "error": "Timed out"}


# ---------------------------------------------------------------------------
#  TLS cert check + HTTP headers
# ---------------------------------------------------------------------------

def cert_check(host: str, port: int = 443, timeout: int = 5) -> Dict[str, Any]:
    _validate_host(host)
    _validate_port(port)
    result: Dict[str, Any] = {"host": host, "port": port}
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = cast(Dict[str, Any], ssock.getpeercert() or {})
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
        date_fmt = "%b %d %H:%M:%S %Y %Z"
        try:
            not_after_dt = datetime.strptime(not_after_str, date_fmt).replace(
                tzinfo=timezone.utc
            )
            now_utc = datetime.now(timezone.utc)
            days_remaining = (not_after_dt - now_utc).days
            expired = now_utc > not_after_dt
        except ValueError:
            days_remaining = None
            expired = None
        san_list = [f"{t}:{v}" for t, v in cert.get("subjectAltName", ())]
        result.update({
            "subject": subject_cn, "issuer": issuer_org,
            "serial_number": cert.get("serialNumber", ""),
            "not_before": not_before_str, "not_after": not_after_str,
            "days_remaining": days_remaining, "san": san_list,
            "version": cert.get("version"), "expired": expired,
        })
    except ssl.SSLCertVerificationError as e:
        result["error"] = f"SSL verification failed: {e}"
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
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", f"SysAdminToolbox/{__version__}")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result["status_code"] = resp.getcode()
            result["headers"] = dict(resp.headers)
            resp.read(1)
    except urllib.error.HTTPError as e:
        result["status_code"] = e.code
        result["headers"] = dict(e.headers) if e.headers else {}
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        result["error"] = str(e)
        return result
    hdr_lower = {k.lower(): v for k, v in result.get("headers", {}).items()}
    sec: Dict[str, Dict[str, Any]] = {}
    for sh in sec_names:
        val = hdr_lower.get(sh.lower())
        sec[sh] = {"present": val is not None, "value": val.strip() if val else None}
    result["security_headers"] = sec
    return result


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
                        epilog="Examples:\n  convert d2b 42\n  convert b2d 10101010\n  convert d2h 255\n  convert iptobin 192.168.1.1\n  convert ipinfo 192.168.1.42/24")
    p.add_argument("op", choices=["d2b","b2d","d2h","h2d","b2h","h2b","iptobin","bintoip",
                                   "masktobin","bintomask","m2c","c2m","m2w","w2m","c2w","w2c",
                                   "a2b","b2a","ipinfo"], help="Conversion operation")
    p.add_argument("value", nargs='+', help="Value(s) to convert")

    # -- subnet --
    p = sub.add_parser("subnet", aliases=["sub", "s"], parents=[shared], help="Subnet calculations",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  subnet calc 192.168.0.0/24\n  subnet adv 192.168.1.0/24 26\n  subnet vlsm 192.168.1.0/24 50 30 10\n  subnet range 192.168.1.10 192.168.1.35\n  subnet overlap 10.0.0.0/24 10.0.0.128/25\n  subnet supernet 10.0.0.0/26 10.0.0.64/26")
    p.add_argument("op", choices=["calc","adv","vlsm","overlap","supernet","range"], help="Subnet operation")
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
                        epilog="Examples:\n  mac info AA:BB:CC:DD:EE:FF\n  mac format aa:bb:cc:dd:ee:ff cisco\n  mac generate 5 colon")
    p.add_argument("op", choices=["info","format","normalize","vendor","generate"], help="MAC operation")
    p.add_argument("value", nargs='?', default="", help="MAC address, or quantity for 'generate'")
    p.add_argument("style", nargs='?', default="colon", help="Format style (colon/dash/cisco/bare)")

    # -- net --
    p = sub.add_parser("net", aliases=["n"], parents=[shared], help="Network diagnostics",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  net ping 8.8.8.8\n  net pingsweep 192.168.1.0/24\n  net portscan 192.168.1.1 22 80 443\n  net portscan-adv 192.168.1.1 top20 banner\n  net portscan-net 192.168.1.0/24 22\n  net traceroute-asn example.com\n  net dns-type example.com MX\n  net dns-compare example.com 8.8.8.8 1.1.1.1\n  net certcheck example.com\n  net headers https://example.com\n  net random-ports 49152 65535 10\n  net arp\n  net rdns-sweep 192.168.1.0/24")
    p.add_argument("op", choices=["ping","pingsweep","portscan","portscan-adv","portscan-udp","portscan-net",
                                   "traceroute","tracert","traceroute-asn","whois","dns","dns-type","dns-compare",
                                   "dns-axfr","rdns","rdns-sweep","arp","certcheck","headers","banner",
                                   "random-ports"], help="Network operation")
    p.add_argument("target", nargs='?', default="", help="Target host/IP/domain (not needed for arp)")
    p.add_argument("extra", nargs='*', help="Extra args (ports for portscan)")

    # -- vendor --
    p = sub.add_parser("vendor", aliases=["v"], parents=[shared], help="Vendor config helpers",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  vendor vlan cisco 10 Engineering\n  vendor acl cisco BLOCK deny tcp 10.0.0.0/8 any")
    p.add_argument("op", choices=["vlan","acl"], help="Vendor operation")
    p.add_argument("args", nargs='+', help="Arguments")

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
            print(f"  Formats:")
            for style, v in info['all_formats'].items():
                print(f"    {style:5s}: {v}")
    elif op == "format":
        output(mac_format(val, args.style), label="mac")
    elif op == "normalize":
        output(mac_normalize(val), label="mac")
    elif op == "vendor":
        output(mac_vendor(val), label="oui")
    elif op == "generate":
        count = int(val) if val else 1
        output(generate_local_macs(count, args.style), label="mac_addresses")


def _dispatch_net(args):
    op = args.op
    target = args.target
    if op == "ping":
        result = ping_host(target)
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
        results = tcp_port_check(target, ports)
        if is_json_mode():
            output(results, label="portscan")
        else:
            for r in results:
                print(f"  {r['port']:5d}/tcp  {r['state']:8s}  {r['service']}")
    elif op in ("traceroute", "tracert"):
        hops = traceroute(target)
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
        results = ping_sweep(target)
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
        results = tcp_port_scan_advanced(target, ports, grab_banner=do_banner)
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
        results = udp_port_check(target, ports)
        if is_json_mode():
            output(results, label="udpscan")
        else:
            for r in results:
                print(f"  {r['port']:5d}/udp  {r['state']:15s}  {r['service']}")

    elif op == "portscan-net":
        if not args.extra:
            raise ValueError("Usage: net portscan-net NETWORK PORT")
        port = int(args.extra[0])
        results = scan_network_port(target, port)
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
        result = banner_grab(target, port)
        if is_json_mode():
            output({"host": target, "port": port, "banner": result}, label="banner")
        elif result:
            print(result)
        else:
            print("  No banner received")

    elif op == "whois":
        output(whois_lookup(target), label="whois")

    elif op in ("traceroute-asn",):
        hops = traceroute_asn(target)
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
        result = dns_lookup_type(target, rtype, server=server)
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
        result = dns_compare(target, servers, rtype)
        if is_json_mode():
            output(result, label="dns_compare")
        else:
            print(f"  {result['domain']} ({result['type']}):")
            for srv, recs in result['results'].items():
                print(f"    {srv}: {', '.join(recs) if recs else 'no records'}")

    elif op == "dns-axfr":
        ns = args.extra[0] if args.extra else None
        result = dns_zone_transfer(target, nameserver=ns)
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
        results = reverse_dns_sweep(target)
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
        result = cert_check(target, port)
        if is_json_mode():
            output(result, label="cert")
        else:
            if 'error' in result:
                print(f"  {target}:{port} - {result['error']}")
            else:
                status = "EXPIRED" if result['expired'] else f"{result['days_remaining']}d remaining"
                print(f"  {target}:{port}")
                print(f"    Subject : {result['subject']}")
                print(f"    Issuer  : {result['issuer']}")
                print(f"    Valid   : {result['not_before']} - {result['not_after']}")
                print(f"    Status  : {status}")
                print(f"    SANs    : {', '.join(result['san'][:5])}")
                if len(result['san']) > 5:
                    print(f"              ... +{len(result['san'])-5} more")

    elif op == "headers":
        result = http_headers(target)
        if is_json_mode():
            output(result, label="headers")
        else:
            if 'error' in result:
                print(f"  {target}: {result['error']}")
            else:
                print(f"  {target} [{result.get('status_code', '?')}]")
                print(f"  Security headers:")
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


def _dispatch_vendor(args):
    op = args.op
    a = args.args
    if op == "vlan":
        if len(a) < 2:
            raise ValueError("Usage: vendor vlan VENDOR VLAN_ID [NAME] [PORTS...]")
        vendor = a[0]
        vlan_id = int(a[1])
        vlan_name = a[2] if len(a) > 2 else None
        ports = a[3:] if len(a) > 3 else None
        output(vlan_helper(vendor, vlan_id, vlan_name, ports), label="configuration")
    elif op == "acl":
        if len(a) < 6:
            raise ValueError("Usage: vendor acl VENDOR NAME ACTION PROTO SRC DST [SPORT] [DPORT]")
        src_port = int(a[6]) if len(a) > 6 and a[6] != "0" else None
        dst_port = int(a[7]) if len(a) > 7 and a[7] != "0" else None
        output(
            acl_helper(a[0], a[1], a[2], a[3], a[4], a[5], src_port, dst_port),
            label="configuration",
        )


def _dispatch_cheat(args):
    sheet_map = {
        "vlan": vlan_cheatsheet,
        "acl": acl_cheatsheet,
        "huawei": huawei_vlan_cheatsheet,
        "mikrotik": mikrotik_vlan_cheatsheet,
        "firewall": firewall_cheatsheet,
        "routing": routing_cheatsheet,
        "nat": nat_cheatsheet,
    }
    if args.legacy and args.sheet != "vlan":
        raise ValueError(
            "--legacy is currently available only for the VLAN cheatsheet"
        )
    fn = sheet_map[args.sheet]
    if args.sheet == "vlan":
        content = vlan_cheatsheet(args.section, include_legacy=args.legacy)
    else:
        content = fn(args.section)
    output(content, label="cheatsheet")


DISPATCH = {
    "convert": _dispatch_convert, "conv": _dispatch_convert, "c": _dispatch_convert,
    "subnet": _dispatch_subnet, "sub": _dispatch_subnet, "s": _dispatch_subnet,
    "ipv6": _dispatch_ipv6, "v6": _dispatch_ipv6,
    "mac": _dispatch_mac, "m": _dispatch_mac,
    "net": _dispatch_net, "n": _dispatch_net,
    "vendor": _dispatch_vendor, "v": _dispatch_vendor,
    "cheat": _dispatch_cheat, "cs": _dispatch_cheat,
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
            DISPATCH[args.command](args)
        else:
            parser.print_help()
    except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(130)


if __name__ == "__main__":
    main()
