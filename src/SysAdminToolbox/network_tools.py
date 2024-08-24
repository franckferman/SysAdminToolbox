# network_tools.py

import socket
from typing import Dict, List, Optional


def dns_lookup(domain: str) -> Dict[str, List[str]]:
    """
    Perform a DNS lookup to get the IP addresses associated with a domain name.

    Args:
        domain (str): The domain name to look up (e.g., 'example.com').

    Returns:
        Dict[str, List[str]]: A dictionary with the domain as the key and a list of IP addresses as the value.
    """
    try:
        ip_addresses = socket.gethostbyname_ex(domain)[2]
        return {domain: ip_addresses}
    except socket.gaierror:
        return {domain: []}


def vlan_helper(vendor: str, vlan_id: int, vlan_name: Optional[str] = None, ports: Optional[List[str]] = None) -> str:
    """
    Provide a summary of VLAN creation commands for different vendors.

    Args:
        vendor (str): The vendor of the network equipment (e.g., 'cisco', 'juniper').
        vlan_id (int): The VLAN ID to create.
        vlan_name (Optional[str]): The name of the VLAN (optional).
        ports (Optional[List[str]]): List of ports to assign to the VLAN (optional).

    Returns:
        str: A summary of the VLAN creation commands.
    """
    if vendor.lower() == 'cisco':
        commands = [
            "configure terminal",  # Enter global configuration mode
            f"vlan {vlan_id}",
            f" name {vlan_name}" if vlan_name else "",
            f"interface range {', '.join(ports) if ports else 'Gi0/1-24'}",
            " switchport mode access",
            f" switchport access vlan {vlan_id}",
            "end",  # Exit global configuration mode
            "write memory"  # Save configuration
        ]
    elif vendor.lower() == 'juniper':
        commands = [
            "configure",  # Enter global configuration mode for Juniper
            f"set vlans {vlan_name or f'vlan-{vlan_id}'} vlan-id {vlan_id}",
            f"set interfaces {', '.join(ports) if ports else 'ge-0/0/0'} unit 0 family ethernet-switching vlan members {vlan_name or f'vlan-{vlan_id}'}",
            "commit and-quit",  # Save and exit configuration mode
        ]
    else:
        return "Unsupported vendor. Please provide a supported vendor (e.g., 'cisco', 'juniper')."
    
    return "\n".join(commands).strip()


def acl_helper(vendor: str, acl_name: str, action: str, protocol: str, src: str, dst: str, src_port: Optional[int] = None, dst_port: Optional[int] = None) -> str:
    """
    Provide a summary of ACL creation commands for different vendors.

    Args:
        vendor (str): The vendor of the network equipment (e.g., 'cisco', 'juniper').
        acl_name (str): The name or ID of the ACL.
        action (str): The action to take ('permit' or 'deny').
        protocol (str): The protocol to filter ('ip', 'tcp', 'udp', etc.).
        src (str): The source IP address or network (e.g., '192.168.1.0/24').
        dst (str): The destination IP address or network (e.g., '192.168.2.0/24').
        src_port (Optional[int]): The source port (optional).
        dst_port (Optional[int]): The destination port (optional).

    Returns:
        str: A summary of the ACL creation commands.
    """
    if vendor.lower() == 'cisco':
        acl_entry = f"{action} {protocol} {src} {dst}"
        if src_port:
            acl_entry += f" eq {src_port}"
        if dst_port:
            acl_entry += f" eq {dst_port}"

        commands = [
            "configure terminal",  # Enter global configuration mode
            f"ip access-list extended {acl_name}",
            f" {acl_entry}",
            "exit",  # Exit ACL configuration mode
            "end",  # Exit global configuration mode
            "write memory"  # Save configuration
        ]

    elif vendor.lower() == 'juniper':
        acl_entry = f"term {acl_name} from protocol {protocol}"
        acl_entry += f" source-address {src} destination-address {dst}"
        if src_port:
            acl_entry += f" source-port {src_port}"
        if dst_port:
            acl_entry += f" destination-port {dst_port}"

        commands = [
            "configure",  # Enter global configuration mode for Juniper
            f"set firewall family inet filter {acl_name} {acl_entry}",
            f"set firewall family inet filter {acl_name} term {acl_name} then {action}",
            "commit and-quit",  # Save and exit configuration mode
        ]

    else:
        return "Unsupported vendor. Please provide a supported vendor (e.g., 'cisco', 'juniper')."
    
    return "\n".join(commands).strip()


def vlan_cheatsheet(section: Optional[str] = None) -> str:
    """
    Provide a VLAN cheat sheet for various configurations.

    Args:
        section (Optional[str]): The specific section to display ('creation', 'access', 'trunk', 'svi', 'vtp', 
                                 'troubleshooting', 'terminology', 'trunktypes', 'vlannumbers', or None for all).

    Returns:
        str: The corresponding cheat sheet section.
    """
    cheat_sheets = {
        "creation": """
        VLAN Creation:
        Switch(config)# vlan 100
        Switch(config-vlan)# name Engineering
        """,
        "access": """
        Access Port Configuration:
        Switch(config-if)# switchport mode access
        Switch(config-if)# switchport nonegotiate
        Switch(config-if)# switchport access vlan 100
        Switch(config-if)# switchport voice vlan 150
        """,
        "trunk": """
        Trunk Port Configuration:
        Switch(config-if)# switchport mode trunk
        Switch(config-if)# switchport trunk encapsulation dot1q
        Switch(config-if)# switchport trunk allowed vlan 10,100-200
        Switch(config-if)# switchport trunk native vlan 10
        """,
        "svi": """
        SVI Configuration:
        Switch(config)# interface vlan100
        Switch(config-if)# ip address 192.168.100.1 255.255.255.0
        """,
        "vtp": """
        VLAN Trunking Protocol (VTP):
        Switch(config)# vtp mode server
        Switch(config)# vtp domain LASVEGAS
        Switch(config)# vtp password Presl3y
        Switch(config)# vtp version 2
        Switch(config)# vtp pruning
        """,
        "troubleshooting": """
        Troubleshooting:
        show vlan
        show interface status
        show interface switchport
        show interface trunk
        show vtp status
        show vtp password
        """,
        "terminology": """
        Terminology:
        Trunking · Extending multiple VLANs over the same physical connection
        Native VLAN · By default, frames in this VLAN are untagged when sent across a trunk
        Access VLAN · The VLAN to which an access port is assigned
        Voice VLAN · If configured, enables minimal trunking to support voice traffic in addition to data traffic on an access port
        Dynamic Trunking Protocol (DTP) · Can be used to automatically establish trunks between capable ports; carries a security risk
        Switched Virtual Interface (SVI) · A virtual interface which provides a routed gateway into and out of a VLAN

        Switch Port Modes:
        trunk · Forms an unconditional trunk
        dynamic desirable · Actively attempts to negotiate a trunk with the distant end
        dynamic auto · Will form a trunk only if requested by the distant end
        access · Will never form a trunk
        """,
        "trunktypes": """
        Trunk Types:
        802.1Q:
        Header Size: 4 bytes
        Trailer Size: N/A
        Standard: IEEE
        Maximum VLANs: 4094
        Command: dot1q

        ISL:
        Header Size: 26 bytes
        Trailer Size: 4 bytes
        Standard: Cisco
        Maximum VLANs: 1000
        Command: isl
        """,
        "vlannumbers": """
        VLAN Numbers:
        0 Reserved
        1 default
        1002 fddi-default
        1003 tr
        1004 fdnet
        1005 trnet
        1006-4094 Extended
        4095 Reserved
        """
    }

    if section and section in cheat_sheets:
        return cheat_sheets[section].strip()
    else:
        return "\n\n".join(cheat_sheets.values()).strip()


def acl_cheatsheet(section: Optional[str] = None) -> str:
    """
    Provide an ACL (Access Control Lists) cheat sheet for various configurations.

    Args:
        section (Optional[str]): The specific section to display ('creation', 'permit', 'deny', 'apply', 'verify', 
                                 'ipv6', or None for all).

    Returns:
        str: The corresponding cheat sheet section.
    """
    cheat_sheets = {
        "creation": """
        ACL Creation:
        Standard ACL (1-99):
        Router(config)# access-list 10 permit 192.168.1.0 0.0.0.255
        
        Extended ACL (100-199):
        Router(config)# access-list 101 permit tcp 192.168.1.0 0.0.0.255 any eq 80
        Router(config)# access-list 101 deny ip any any log
        """,
        "permit": """
        Permit Statements:
        Permit Specific IP:
        Router(config)# access-list 10 permit 192.168.1.10
        
        Permit Subnet:
        Router(config)# access-list 10 permit 192.168.1.0 0.0.0.255
        
        Permit TCP Traffic:
        Router(config)# access-list 101 permit tcp any any eq 80
        """,
        "deny": """
        Deny Statements:
        Deny Specific IP:
        Router(config)# access-list 10 deny 192.168.1.10
        
        Deny Subnet:
        Router(config)# access-list 10 deny 192.168.1.0 0.0.0.255
        
        Deny All:
        Router(config)# access-list 101 deny ip any any
        """,
        "apply": """
        Applying ACLs to Interfaces:
        Apply to Inbound Traffic:
        Router(config-if)# ip access-group 101 in
        
        Apply to Outbound Traffic:
        Router(config-if)# ip access-group 101 out
        """,
        "verify": """
        Verifying ACLs:
        Display ACLs:
        Router# show access-lists
        
        Display Interface Status with ACLs:
        Router# show ip interface [interface_name]
        
        Display Specific ACL:
        Router# show access-list 101
        """,
        "ipv6": """
        IPv6 ACLs:
        Create IPv6 ACL:
        Router(config)# ipv6 access-list MYV6ACL
        Router(config-ipv6-acl)# permit tcp any any eq 80
        
        Apply IPv6 ACL to Interface:
        Router(config-if)# ipv6 traffic-filter MYV6ACL in
        """
    }

    if section and section in cheat_sheets:
        return cheat_sheets[section].strip()
    else:
        # Combine all sections if no specific section is requested
        return "\n\n".join(cheat_sheets.values()).strip()
