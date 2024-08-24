#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Versatile tool designed for network administration, providing a wide range of useful calculations.

Author   : Franck FERMAN (@franckferman)
Created  : 2024-08-24
Version  : 3.0.0
License  : GNU Affero General Public License v3.0

Repository:
    https://github.com/franckferman/SysAdminToolbox
License details:
    See the LICENSE file or https://www.gnu.org/licenses/agpl-3.0.html
"""

import argparse
import ipaddress
import platform
import re
import socket
import ssl
import subprocess
import sys
import urllib.request

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Dict, List, Optional

try:
    from SysAdminToolbox.colors import colored_subnet_output, colors_enabled
    from SysAdminToolbox.output import output, set_json_mode, is_json_mode
except ImportError:
    from colors import colored_subnet_output, colors_enabled
    from output import output, set_json_mode, is_json_mode

__version__ = "3.1.0"


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
    if '01' in bits.replace('0', '', 1) or ('1' in bits and bits.index('0') < bits.rindex('1') if '0' in bits and '1' in bits else False):
        clean = bits.rstrip('0')
        if '0' in clean:
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
    return bin(decimal if decimal >= 0 else (decimal + (1 << 8)))[2:]


def decimal_to_binary_signed(decimal: int, bits: int = 8) -> str:
    return format(decimal & ((1 << bits) - 1), f'0{bits}b')


def decimal_to_binary_values(decimal: int) -> dict:
    return {
        "decimal": decimal,
        "unsigned": decimal_to_binary(decimal),
        "signed_8bit": decimal_to_binary_signed(decimal),
    }


def print_binary_info(info: dict) -> None:
    print(f"Original value                : {info['decimal']}")
    print(f"Unsigned binary               : {info['unsigned']}")
    print(f"Signed (2's complement, 8-bit): {info['signed_8bit']}")


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
    _validate_ip(ip)
    octets = ip.split('.')
    unsigned = '.'.join(bin(int(o))[2:] for o in octets)
    signed = '.'.join(format(int(o), '08b') for o in octets)
    return (
        f"Original value: {ip}\n"
        f"Unsigned Binary: {unsigned}\n"
        f"Binary signed 2's complement (8 digits): {signed}"
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


# ---------------------------------------------------------------------------
#  Subnet calculators
# ---------------------------------------------------------------------------

def subnet_calculator(network: str, mask: str) -> Dict[str, Any]:
    _validate_ip(network)
    _validate_mask(mask)
    cidr = mask_to_cidr(mask)
    net = ipaddress.ip_network(f"{network}/{cidr}", strict=False)

    num = net.num_addresses
    return {
        "network_address": str(net.network_address),
        "netmask": str(net.netmask),
        "wildcard": mask_to_wildcard(str(net.netmask)),
        "cidr": f"/{cidr}",
        "num_addresses": num,
        "hosts": num - 2 if num > 2 else 0,
        "first_host": str(net[1]) if num > 1 else "N/A",
        "last_host": str(net[-2]) if num > 2 else "N/A",
        "broadcast": str(net.broadcast_address),
        "is_private": net.is_private,
        "is_global": net.is_global,
    }


def advanced_subnet_calculator(ip_address: str, new_mask: str) -> Dict[str, Any]:
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
    sub_objects = list(network.subnets(new_prefix=new_cidr))
    hosts_per = (2 ** (max_bits - new_cidr)) - 2 if new_cidr < (max_bits - 1) else 0

    subnets_detail = []
    for s in sub_objects:
        sn = s.num_addresses
        subnets_detail.append({
            "network": str(s.network_address),
            "cidr": f"/{new_cidr}",
            "first_host": str(s.network_address + 1) if sn > 1 else "N/A",
            "last_host": str(s.broadcast_address - 1) if sn > 2 else "N/A",
            "broadcast": str(s.broadcast_address),
            "usable_hosts": sn - 2 if sn > 2 else 0,
        })

    result = {
        "original_cidr": f"/{original_cidr}",
        "new_cidr": f"/{new_cidr}",
        "original_hosts": num - 2 if num > 2 else 0,
        "hosts_per_subnet": hosts_per,
        "is_private": network.is_private,
        "count_subnets": len(subnets_detail),
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
    ip_network_obj = ipaddress.ip_network(network, strict=False)
    current = ip_network_obj

    for host_count in sorted_hosts:
        if host_count < 1:
            raise ValueError(f"Host count must be >= 1, got {host_count}")
        needed = host_count + 2
        prefix = 32 - (needed - 1).bit_length()
        _validate_cidr(prefix)

        if prefix < current.prefixlen:
            raise ValueError(
                f"Cannot fit {host_count} hosts (/{prefix}) in remaining space "
                f"(/{current.prefixlen})"
            )

        candidates = list(current.subnets(new_prefix=prefix))
        if not candidates:
            raise ValueError(f"No space left for {host_count} hosts")

        new_sub = candidates[0]
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

        if len(candidates) > 1:
            current = candidates[1]
        else:
            break

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

    first_host = str(net.network_address + 1) if num_addresses > 1 else "N/A"
    last_host = str(net.broadcast_address - 1) if num_addresses > 2 else "N/A"

    return {
        "network_address": str(net.network_address),
        "prefix_length": prefix,
        "num_addresses": str(num_addresses),
        "first_host": first_host,
        "last_host": last_host,
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
    if obj.is_global:
        return "global unicast"
    if obj.ipv4_mapped is not None:
        return "ipv4-mapped"
    if int(obj) >> 96 == 0x0064_ff9b:
        return "ipv4-translated (NAT64)"
    if obj.is_reserved:
        return "reserved"
    # Catch-all for remaining global-scope addresses that Python
    # marks private (e.g. 6to4, Teredo) but are routable
    if obj.packed[0] & 0xe0 == 0x20:
        return "global unicast"

    return "unknown"


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

def vlan_helper(vendor: str, vlan_id: int, vlan_name: Optional[str] = None,
                ports: Optional[List[str]] = None) -> str:
    _validate_vlan_id(vlan_id)
    v = vendor.lower()

    if v == 'cisco':
        lines = [
            "configure terminal",
            f"vlan {vlan_id}",
        ]
        if vlan_name:
            lines.append(f" name {vlan_name}")
        port_range = ', '.join(ports) if ports else 'Gi0/1-24'
        lines += [
            f"interface range {port_range}",
            " switchport mode access",
            f" switchport access vlan {vlan_id}",
            "end",
            "write memory",
        ]
    elif v == 'juniper':
        name = vlan_name or f'vlan-{vlan_id}'
        iface = ', '.join(ports) if ports else 'ge-0/0/0'
        lines = [
            "configure",
            f"set vlans {name} vlan-id {vlan_id}",
            f"set interfaces {iface} unit 0 family ethernet-switching vlan members {name}",
            "commit and-quit",
        ]
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
        return f"Unsupported vendor: '{vendor}'. Supported: cisco, juniper, huawei."

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
    v = vendor.lower()

    if v == 'cisco':
        entry = f"{action} {protocol} {src}"
        if src_port:
            entry += f" eq {src_port}"
        entry += f" {dst}"
        if dst_port:
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
        from_clause = f"from protocol {protocol} source-address {src} destination-address {dst}"
        if src_port:
            from_clause += f" source-port {src_port}"
        if dst_port:
            from_clause += f" destination-port {dst_port}"
        lines = [
            "configure",
            f"set firewall family inet filter {acl_name} term RULE {from_clause}",
            f"set firewall family inet filter {acl_name} term RULE then {action}",
            "commit and-quit",
        ]
    else:
        return f"Unsupported vendor: '{vendor}'. Supported: cisco, juniper."

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
        "  Switch(config-if)# switchport trunk encapsulation dot1q\n"
        "  Switch(config-if)# switchport trunk allowed vlan 10,100-200\n"
        "  Switch(config-if)# switchport trunk native vlan 10"
    ),
    "svi": (
        "SVI Configuration:\n"
        "  Switch(config)# interface vlan100\n"
        "  Switch(config-if)# ip address 192.168.100.1 255.255.255.0"
    ),
    "vtp": (
        "VLAN Trunking Protocol (VTP):\n"
        "  Switch(config)# vtp mode server\n"
        "  Switch(config)# vtp domain LASVEGAS\n"
        "  Switch(config)# vtp password Presl3y\n"
        "  Switch(config)# vtp version 2\n"
        "  Switch(config)# vtp pruning"
    ),
    "troubleshooting": (
        "Troubleshooting:\n"
        "  show vlan\n"
        "  show interface status\n"
        "  show interface switchport\n"
        "  show interface trunk\n"
        "  show vtp status\n"
        "  show vtp password"
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
        "  802.1Q: Header 4B | Standard IEEE | Max 4094 VLANs | cmd: dot1q\n"
        "  ISL:    Header 26B + Trailer 4B | Cisco | Max 1000 VLANs | cmd: isl"
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


def vlan_cheatsheet(section: Optional[str] = None) -> str:
    return _cheatsheet_lookup(VLAN_CHEATSHEET, section)

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
    nets = [ipaddress.ip_network(n, strict=False) for n in networks]

    versions = {n.version for n in nets}
    if len(versions) > 1:
        raise ValueError("Cannot mix IPv4 and IPv6 networks")

    collapsed = list(ipaddress.collapse_addresses(nets))
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

    overlaps = n1.overlaps(n2)
    overlap_network = None
    if overlaps:
        start = max(int(n1.network_address), int(n2.network_address))
        end = min(int(n1.broadcast_address), int(n2.broadcast_address))
        if n1.version == 4:
            addr_cls = ipaddress.IPv4Address
            net_cls = ipaddress.IPv4Network
        else:
            addr_cls = ipaddress.IPv6Address
            net_cls = ipaddress.IPv6Network
        summary = list(ipaddress.summarize_address_range(
            addr_cls(start), addr_cls(end)
        ))
        if len(summary) == 1:
            overlap_network = str(summary[0])
        else:
            overlap_network = str(net_cls(
                f"{addr_cls(start)}/{min(n1.prefixlen, n2.prefixlen)}",
                strict=False,
            ))

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
    """Validate that *host* is a valid IPv4 address or resolvable hostname."""
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
    packets_sent = int(pkt_match.group(1)) if pkt_match else count
    packets_received = int(pkt_match.group(2)) if pkt_match else 0
    packet_loss_pct = float(pkt_match.group(3)) if pkt_match else 100.0

    # -- parse RTT stats ---------------------------------------------------
    # Linux : "rtt min/avg/max/mdev = 0.028/0.042/0.068/0.015 ms"
    # macOS : "round-trip min/avg/max/stddev = 12.063/13.511/14.959/1.448 ms"
    rtt_match = re.search(
        r'(?:rtt|round-trip)\s+min/avg/max/(?:mdev|stddev)\s*=\s*'
        r'([\d.]+)/([\d.]+)/([\d.]+)',
        output,
    )
    min_ms = float(rtt_match.group(1)) if rtt_match else None
    avg_ms = float(rtt_match.group(2)) if rtt_match else None
    max_ms = float(rtt_match.group(3)) if rtt_match else None

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

        # Hostname: second token when it is not a bare IP or paren-wrapped.
        hostname = None
        if len(tokens) > 1:
            candidate = tokens[1]
            if (
                not re.match(r'^\d{1,3}(\.\d{1,3}){3}$', candidate)
                and not candidate.startswith('(')
            ):
                hostname = candidate
            elif ip_addr:
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
    entries = []
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
    return entries


def reverse_dns_sweep(network: str, timeout: int = 2, max_threads: int = 50) -> List[Dict[str, Any]]:
    net = ipaddress.ip_network(network, strict=False)
    hosts = [str(ip) for ip in net.hosts()]

    def _resolve_one(ip):
        old = socket.getdefaulttimeout()
        socket.setdefaulttimeout(timeout)
        try:
            hostname = socket.gethostbyaddr(ip)[0]
        except (socket.herror, socket.gaierror, socket.timeout, OSError):
            hostname = None
        finally:
            socket.setdefaulttimeout(old)
        return {"ip": ip, "hostname": hostname}

    with ThreadPoolExecutor(max_workers=max_threads) as pool:
        results = list(pool.map(_resolve_one, hosts))
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
    net = ipaddress.ip_network(network, strict=False)
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
    result = {"host": host, "port": port}
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, port), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
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
            not_after_dt = datetime.strptime(not_after_str, date_fmt)
            days_remaining = (not_after_dt - datetime.now(tz=None)).days
            expired = datetime.now(tz=None) > not_after_dt
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
    result = {"url": url}
    try:
        req = urllib.request.Request(url, method="GET")
        req.add_header("User-Agent", "SysAdminToolbox/3.0")
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
    sec = {}
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
    asn_results = {}
    if hops_with_ip:
        with ThreadPoolExecutor(max_workers=min(len(hops_with_ip), 20)) as pool:
            futures = {pool.submit(asn_lookup, h["ip"]): i for i, h in hops_with_ip}
            for future in as_completed(futures):
                idx = futures[future]
                try:
                    asn_results[idx] = future.result()
                except Exception:
                    asn_results[idx] = None
    enriched = []
    for i, hop in enumerate(hops):
        entry = {"hop": hop.get("hop"), "ip": hop.get("ip"), "hostname": hop.get("hostname"),
                 "rtt_ms": hop.get("rtt_ms"), "asn": None, "prefix": None, "country": None}
        if i in asn_results and asn_results[i] and "error" not in asn_results[i]:
            entry["asn"] = asn_results[i]["asn"]
            entry["prefix"] = asn_results[i]["prefix"]
            entry["country"] = asn_results[i]["country"]
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
    shared.add_argument("--json", action="store_true", default=False, help="Output in JSON")
    shared.add_argument("--no-color", action="store_true", default=False, dest="no_color", help="Disable colors")

    # -- convert --
    p = sub.add_parser("convert", aliases=["conv", "c"], parents=[shared], help="Number/base conversions",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  convert d2b 42\n  convert b2d 10101010\n  convert d2h 255\n  convert iptobin 192.168.1.1")
    p.add_argument("op", choices=["d2b","b2d","d2h","h2d","b2h","h2b","iptobin","bintoip",
                                   "masktobin","bintomask","m2c","c2m","m2w","w2m","c2w","w2c",
                                   "a2b","b2a"], help="Conversion operation")
    p.add_argument("value", nargs='+', help="Value(s) to convert")

    # -- subnet --
    p = sub.add_parser("subnet", aliases=["sub", "s"], parents=[shared], help="Subnet calculations",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  subnet calc 192.168.0.0/24\n  subnet adv 192.168.1.0/24 26\n  subnet vlsm 192.168.1.0/24 50 30 10\n  subnet overlap 10.0.0.0/24 10.0.0.128/25\n  subnet supernet 10.0.0.0/26 10.0.0.64/26")
    p.add_argument("op", choices=["calc","adv","vlsm","overlap","supernet"], help="Subnet operation")
    p.add_argument("args", nargs='+', help="Arguments")

    # -- ipv6 --
    p = sub.add_parser("ipv6", aliases=["v6"], parents=[shared], help="IPv6 utilities",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  ipv6 expand ::1\n  ipv6 compress 2001:0db8::1\n  ipv6 type fe80::1\n  ipv6 subnet 2001:db8::/32")
    p.add_argument("op", choices=["expand","compress","tobin","type","subnet"], help="IPv6 operation")
    p.add_argument("value", help="IPv6 address or network")

    # -- mac --
    p = sub.add_parser("mac", aliases=["m"], parents=[shared], help="MAC address utilities",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  mac info AA:BB:CC:DD:EE:FF\n  mac format aa:bb:cc:dd:ee:ff cisco")
    p.add_argument("op", choices=["info","format","normalize","vendor"], help="MAC operation")
    p.add_argument("value", help="MAC address")
    p.add_argument("style", nargs='?', default="colon", help="Format style (colon/dash/cisco/bare)")

    # -- net --
    p = sub.add_parser("net", aliases=["n"], parents=[shared], help="Network diagnostics",
                        formatter_class=argparse.RawTextHelpFormatter,
                        epilog="Examples:\n  net ping 8.8.8.8\n  net pingsweep 192.168.1.0/24\n  net portscan 192.168.1.1 22 80 443\n  net portscan-adv 192.168.1.1 --banner\n  net portscan-net 192.168.1.0/24 22\n  net traceroute-asn google.com\n  net dns-type google.com MX\n  net dns-compare google.com 8.8.8.8 1.1.1.1\n  net certcheck google.com\n  net headers https://google.com\n  net arp\n  net rdns-sweep 192.168.1.0/24")
    p.add_argument("op", choices=["ping","pingsweep","portscan","portscan-adv","portscan-udp","portscan-net",
                                   "traceroute","tracert","traceroute-asn","whois","dns","dns-type","dns-compare",
                                   "dns-axfr","rdns","rdns-sweep","arp","certcheck","headers","banner"], help="Network operation")
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
                        epilog="Examples:\n  cheat vlan trunk\n  cheat acl\n  cheat firewall iptables\n  cheat routing ospf\n  cheat nat cisco_pat\n  cheat huawei\n  cheat mikrotik")
    p.add_argument("sheet", choices=["vlan","acl","huawei","mikrotik","firewall","routing","nat"], help="Cheatsheet topic")
    p.add_argument("section", nargs='?', default=None, help="Specific section (optional)")

    return parser


# ---------------------------------------------------------------------------
#  Dispatch handlers
# ---------------------------------------------------------------------------

def _dispatch_convert(args):
    op = args.op
    val = args.value
    if op == "d2b":
        print_binary_info(decimal_to_binary_values(int(val[0])))
    elif op == "b2d":
        print_binary_to_decimal_info(val[0])
    elif op == "d2h":
        print(decimal_to_hexadecimal(int(val[0])))
    elif op == "h2d":
        print(hexadecimal_to_decimal(val[0]))
    elif op == "b2h":
        print(binary_to_hexadecimal(val[0]))
    elif op == "h2b":
        print(hexadecimal_to_binary(val[0]))
    elif op == "iptobin":
        print(ip_to_binary_full(val[0]))
    elif op == "bintoip":
        print(binary_to_ip(val[0]))
    elif op == "masktobin":
        print(mask_to_binary(val[0]))
    elif op == "bintomask":
        print(binary_to_mask(val[0]))
    elif op == "m2c":
        print(mask_to_cidr(val[0]))
    elif op == "c2m":
        print(cidr_to_mask(int(val[0])))
    elif op == "m2w":
        print(mask_to_wildcard(val[0]))
    elif op == "w2m":
        print(wildcard_to_mask(val[0]))
    elif op == "c2w":
        print(mask_to_wildcard(cidr_to_mask(int(val[0]))))
    elif op == "w2c":
        print(mask_to_cidr(wildcard_to_mask(val[0])))
    elif op == "a2b":
        print(address_to_binary(val))
    elif op == "b2a":
        print(binary_to_address(val))


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
        details = advanced_subnet_calculator(a[0], a[1])
        if is_json_mode():
            output(details, label="advanced_subnet")
        else:
            for k, v in details.items():
                if k == 'subnets':
                    print(f"\n  subnets ({details['count_subnets']}):")
                    for i, s in enumerate(v, 1):
                        print(f"    [{i}] {s['network']}{s['cidr']}  "
                              f"hosts: {s['first_host']} - {s['last_host']}  "
                              f"broadcast: {s['broadcast']}  "
                              f"({s['usable_hosts']} usable)")
                elif k == 'count_subnets':
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
        print(f"  Supernet: {result}")


def _dispatch_ipv6(args):
    op = args.op
    val = args.value
    if op == "expand":
        print(ipv6_expand(val))
    elif op == "compress":
        print(ipv6_compress(val))
    elif op == "tobin":
        print(ipv6_to_binary(val))
    elif op == "type":
        print(f"  {val}: {ipv6_type(val)}")
    elif op == "subnet":
        details = ipv6_subnet_calculator(val)
        if is_json_mode():
            output(details, label="ipv6_subnet")
        else:
            for k, v in details.items():
                print(f"  {k}: {v}")


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
        print(mac_format(val, args.style))
    elif op == "normalize":
        print(mac_normalize(val))
    elif op == "vendor":
        print(mac_vendor(val))


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
        if result:
            print(result)
        else:
            print("  No banner received")

    elif op == "whois":
        print(whois_lookup(target))

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
        print(vlan_helper(vendor, vlan_id, vlan_name, ports))
    elif op == "acl":
        if len(a) < 6:
            raise ValueError("Usage: vendor acl VENDOR NAME ACTION PROTO SRC DST [SPORT] [DPORT]")
        src_port = int(a[6]) if len(a) > 6 else None
        dst_port = int(a[7]) if len(a) > 7 else None
        print(acl_helper(a[0], a[1], a[2], a[3], a[4], a[5], src_port, dst_port))


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
    fn = sheet_map[args.sheet]
    print(fn(args.section))


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
    try:
        from SysAdminToolbox.colors import Colors
    except ImportError:
        from colors import Colors
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

        tokens = line.split()
        try:
            args = parser.parse_args(tokens)
            if args.json:
                set_json_mode(True)
            if args.command and args.command in DISPATCH:
                DISPATCH[args.command](args)
            else:
                print(f"  {c.RED}Unknown command. Type 'help'.{c.RESET}")
            set_json_mode(False)
        except SystemExit:
            pass
        except (ValueError, ipaddress.AddressValueError, ipaddress.NetmaskValueError) as e:
            print(f"  {c.RED}Error: {e}{c.RESET}")
        except RuntimeError as e:
            print(f"  {c.RED}Error: {e}{c.RESET}")


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
        try:
            from SysAdminToolbox.colors import Colors
        except ImportError:
            from colors import Colors
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
