#!/usr/bin/env python3

""" Versatile tool designed for network administration, providing a wide range of useful calculations.

Created By  : Franck FERMAN @franckferman
Created Date: 24/08/24
Version     : 1.0.0 (24/08/24)
"""

import argparse, sys
from calculations import (
    decimal_to_binary, binary_to_decimal, decimal_to_hexadecimal,
    hexadecimal_to_decimal, binary_to_hexadecimal, hexadecimal_to_binary,
    ip_to_binary, binary_to_ip, mask_to_binary, binary_to_mask,
    mask_to_cidr, cidr_to_mask, mask_to_wildcard, wildcard_to_mask,
    address_to_binary, binary_to_address, subnet_calculator,
    advanced_subnet_calculator, vlsm_calculator
)
from network_tools import dns_lookup, vlan_helper, acl_helper, vlan_cheatsheet, acl_cheatsheet


def main():
    parser = argparse.ArgumentParser(
        description=(
            "A versatile tool designed for network administrators, offering a comprehensive suite of network calculations, "
            "conversions, and configuration helpers. This tool supports operations like IP subnetting, binary and hexadecimal "
            "conversions, DNS lookups, VLAN and ACL management, and much more."
        ),
        epilog=(
            "Example commands:\n\n"
            "# Convert decimal to binary:\n"
            "python3 network_calculator.py --dectobin 42\n\n"
            "# Convert IP address to binary:\n"
            "python3 network_calculator.py --iptobin 192.168.1.1\n\n"
            "# Perform a DNS lookup:\n"
            "python3 network_calculator.py --dnslookup example.com\n\n"
            "# Calculate subnet details:\n"
            "python3 network_calculator.py --subnetcalc 192.168.0.1 255.255.255.0\n\n"
            "# Generate VLAN creation commands:\n"
            "python3 network_calculator.py --vlanhelper cisco 10 Engineering Gi0/1-15\n\n"
            "# Display VLAN cheat sheet:\n"
            "python3 network_calculator.py --vlancheatsheet trunk\n"
        ),
        formatter_class=argparse.RawTextHelpFormatter
    )
    
    parser.add_argument("--dectobin", "--dec2bin", "--d2b", type=int, help="Convert decimal to binary")
    parser.add_argument("--bintodec", "--bin2dec", "--b2d", type=str, help="Convert binary to decimal")
    parser.add_argument("--dectohex", "--dec2hex", "--d2h", type=int, help="Convert decimal to hexadecimal")
    parser.add_argument("--hextodec", "--hex2dec", "--h2d", type=str, help="Convert hexadecimal to decimal")
    parser.add_argument("--bintohex", "--bin2hex", "--b2h", type=str, help="Convert binary to hexadecimal")
    parser.add_argument("--hextobin", "--hex2bin", "--h2b", type=str, help="Convert hexadecimal to binary")
    parser.add_argument("--iptobin", "--ip2bin", "--i2b", type=str, help="Convert IP address to binary")
    parser.add_argument("--bintoip", "--bin2ip", "--b2i", type=str, help="Convert binary to IP address")
    parser.add_argument("--masktobin", "--mask2bin", "--m2b", type=str, help="Convert subnet mask to binary")
    parser.add_argument("--bintomask", "--bin2mask", "--b2m", type=str, help="Convert binary to subnet mask")
    parser.add_argument("--masktocidr", "--mask2cidr", "--m2c", type=str, help="Convert subnet mask to CIDR")
    parser.add_argument("--cidrtomask", "--cidr2mask", "--c2m", type=int, help="Convert CIDR to subnet mask")
    parser.add_argument("--masktowildcard", "--mask2wildcard", "--m2w", type=str, help="Convert subnet mask to wildcard")
    parser.add_argument("--wildcardtomask", "--wildcard2mask", "--w2m", type=str, help="Convert wildcard to subnet mask")
    parser.add_argument("--cidrtowildcard", "--cidr2wildcard", "--c2w", type=int, help="Convert CIDR to wildcard")
    parser.add_argument("--wildcardtocidr", "--wildcard2cidr", "--w2c", type=str, help="Convert wildcard to CIDR")
    parser.add_argument("--addrtobin", "--addr2bin", "--a2b", type=str, nargs='+', help="Convert address (and optional mask) to binary")
    parser.add_argument("--bintoaddr", "--bin2addr", "--b2a", type=str, nargs='+', help="Convert binary to address or mask")
    parser.add_argument("--subnetcalc", "--subnet", "--sc", type=str, nargs='+', help="Calculate subnet details")
    parser.add_argument("--advancedsubnetcalc", "--asc", type=str, nargs=2, metavar=('IP_MASK', 'NEW_MASK'), help="Calculate advanced subnet details")
    parser.add_argument("--vlsmcalc", "--vlsm", type=str, nargs='+', metavar=('NETWORK', 'HOSTS'), help="Calculate VLSM details for a network with required hosts")
    parser.add_argument("--dnslookup", type=str, metavar='DOMAIN', help="Perform a DNS lookup on a domain name")
    parser.add_argument("--vlanhelper", type=str, nargs='+', metavar='ARGS', help="Provide VLAN creation command help")
    parser.add_argument("--aclhelper", type=str, nargs='+', metavar='ARGS', help="Provide ACL creation command help")
    parser.add_argument("--vlancheatsheet", type=str, nargs='?', const='all', metavar='SECTION', help=(
        "Display VLAN cheat sheet. Options: "
        "'creation', 'access', 'trunk', 'svi', 'vtp', 'troubleshooting', "
        "'terminology', 'trunktypes', 'vlannumbers', or no argument to display all."
    ))
    parser.add_argument("--aclcheatsheet", type=str, nargs='?', const='all', metavar='SECTION', help=(
        "Display ACL cheat sheet. Options: "
        "'creation', 'permit', 'deny', 'apply', 'verify', 'ipv6', or no argument to display all."
    ))

    args = parser.parse_args()

    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)

    if args.dectobin:
        print(decimal_to_binary(args.dectobin))
    if args.bintodec:
        print(binary_to_decimal(args.bintodec))
    if args.dectohex:
        print(decimal_to_hexadecimal(args.dectohex))
    if args.hextodec:
        print(hexadecimal_to_decimal(args.hextodec))
    if args.bintohex:
        print(binary_to_hexadecimal(args.bintohex))
    if args.hextobin:
        print(hexadecimal_to_binary(args.hextobin))
    if args.iptobin:
        print(ip_to_binary(args.iptobin))
    if args.bintoip:
        print(binary_to_ip(args.bintoip))
    if args.masktobin:
        print(mask_to_binary(args.masktobin))
    if args.bintomask:
        print(binary_to_mask(args.bintomask))
    if args.masktocidr:
        print(mask_to_cidr(args.masktocidr))
    if args.cidrtomask:
        print(cidr_to_mask(args.cidrtomask))
    if args.masktowildcard:
        print(mask_to_wildcard(args.masktowildcard))
    if args.wildcardtomask:
        print(wildcard_to_mask(args.wildcardtomask))
    if args.cidrtowildcard:
        print(mask_to_wildcard(cidr_to_mask(args.cidrtowildcard)))
    if args.wildcardtocidr:
        print(mask_to_cidr(wildcard_to_mask(args.wildcardtocidr)))
    if args.addrtobin:
            print(address_to_binary(args.addrtobin))
    if args.bintoaddr:
        print(binary_to_address(args.bintoaddr))

    if args.subnetcalc:
        if len(args.subnetcalc) == 1:
            network, mask = args.subnetcalc[0].split('/')
            mask = cidr_to_mask(int(mask))
        else:
            network, mask = args.subnetcalc
        details = subnet_calculator(network, mask)
        for key, value in details.items():
            print(f"{key}: {value}")

    if args.advancedsubnetcalc:
        ip_mask, new_mask = args.advancedsubnetcalc
        
        if '/' in ip_mask:
            ip_address = ip_mask
        elif '.' in ip_mask:
            ip_address = ip_mask
        else:
            raise ValueError("Invalid format for IP address or mask.")
        
        details = advanced_subnet_calculator(ip_address, new_mask)
        
        for key, value in details.items():
            print(f"{key}: {value}")

    if args.vlsmcalc:
        network = args.vlsmcalc[0]
        hosts = list(map(int, args.vlsmcalc[1:]))
        
        subnets = vlsm_calculator(network, hosts)
        
        for idx, subnet in enumerate(subnets):
            print(f"Subnet {idx + 1}:")
            for key, value in subnet.items():
                print(f"  {key}: {value}")
            print("\n")

    if args.dnslookup:
        results = dns_lookup(args.dnslookup)
        for domain, ips in results.items():
            print(f"{domain}: {', '.join(ips)}")

    if args.vlanhelper:
        vendor = args.vlanhelper[0]
        vlan_id = int(args.vlanhelper[1])
        vlan_name = args.vlanhelper[2] if len(args.vlanhelper) > 2 else None
        ports = args.vlanhelper[3:] if len(args.vlanhelper) > 3 else None
        commands = vlan_helper(vendor, vlan_id, vlan_name, ports)
        print(commands)

    if args.aclhelper:
        vendor = args.aclhelper[0]
        acl_name = args.aclhelper[1]
        action = args.aclhelper[2]
        protocol = args.aclhelper[3]
        src = args.aclhelper[4]
        dst = args.aclhelper[5]
        src_port = int(args.aclhelper[6]) if len(args.aclhelper) > 6 else None
        dst_port = int(args.aclhelper[7]) if len(args.aclhelper) > 7 else None
        commands = acl_helper(vendor, acl_name, action, protocol, src, dst, src_port, dst_port)
        print(commands)

    if args.vlancheatsheet:
        section = args.vlancheatsheet if args.vlancheatsheet != 'all' else None
        cheatsheet_content = vlan_cheatsheet(section)
        print(cheatsheet_content)

    if args.aclcheatsheet:
        section = args.aclcheatsheet if args.aclcheatsheet != 'all' else None
        cheatsheet_content = acl_cheatsheet(section)
        print(cheatsheet_content)


if __name__ == "__main__":
    main()
