# calculations.py

import ipaddress
from typing import List, Dict, Any


def decimal_to_binary(decimal: int) -> str:
    """
    Convert a decimal number to its binary representation, both unsigned and 2's complement.

    Args:
        decimal (int): The decimal number to convert.

    Returns:
        str: A string showing the original value, unsigned binary, and 2's complement binary (8 digits).
    """
    unsigned_binary = bin(decimal)[2:]  # No padding zeros
    signed_binary = format(decimal & 0xff, '08b')  # Complement of 2 on 8 bits
    return f"Original value: {decimal}\nUnsigned Binary: {unsigned_binary}\nBinary signed 2's complement (8 digits): {signed_binary}"


def binary_to_decimal(binary: str, signed_bits: int = 8) -> int:
    """
    Convert a binary string to its decimal equivalent.

    Args:
        binary (str): The binary string to convert.
        signed_bits (int): The number of bits for signed conversion (default is 8).

    Returns:
        int: The decimal equivalent of the binary string.
    """
    if len(binary) <= signed_bits and binary[0] == '0':  # unsigned or positive number
        return int(binary, 2)
    elif len(binary) == signed_bits:  # signed 2's complement
        return int(binary, 2) - (1 << signed_bits)
    else:  # Handling binary input shorter than signed_bits and considered as unsigned
        return int(binary, 2)


def decimal_to_hexadecimal(decimal: int) -> str:
    """
    Convert a decimal number to its hexadecimal equivalent.

    Args:
        decimal (int): The decimal number to convert.

    Returns:
        str: The hexadecimal representation of the decimal number.
    """
    return hex(decimal)[2:]


def hexadecimal_to_decimal(hexadecimal: str) -> int:
    """
    Convert a hexadecimal string to its decimal equivalent.

    Args:
        hexadecimal (str): The hexadecimal string to convert.

    Returns:
        int: The decimal equivalent of the hexadecimal string.
    """
    return int(hexadecimal, 16)


def binary_to_hexadecimal(binary: str) -> str:
    """
    Convert a binary string to its hexadecimal equivalent.

    Args:
        binary (str): The binary string to convert.

    Returns:
        str: The hexadecimal equivalent of the binary string.
    """
    decimal = binary_to_decimal(binary)
    return decimal_to_hexadecimal(decimal)


def hexadecimal_to_binary(hexadecimal: str) -> str:
    """
    Convert a hexadecimal string to its binary representation, both unsigned and 2's complement.

    Args:
        hexadecimal (str): The hexadecimal string to convert.

    Returns:
        str: The binary representation of the hexadecimal string.
    """
    decimal = hexadecimal_to_decimal(hexadecimal)
    return decimal_to_binary(decimal)


def ip_to_binary(ip: str) -> str:
    """
    Convert an IP address to its binary representation, both unsigned and 2's complement.

    Args:
        ip (str): The IP address to convert.

    Returns:
        str: A string showing the original IP address, unsigned binary, and 2's complement binary (8 digits).
    """
    octets = ip.split('.')
    unsigned_binary = '.'.join([bin(int(octet))[2:] for octet in octets])
    signed_binary = '.'.join([format(int(octet), '08b') for octet in octets])
    return f"Original value: {ip}\nUnsigned Binary: {unsigned_binary}\nBinary signed 2's complement (8 digits): {signed_binary}"


def binary_to_ip(binary: str) -> str:
    """
    Convert a binary string to its IP address equivalent.

    Args:
        binary (str): The binary string to convert, with or without '.' as separators.

    Returns:
        str: The IP address equivalent of the binary string.
    """
    if '.' in binary:
        # If the binary contains dots, it is separated into bytes.
        binary_groups = binary.split('.')
    else:
        # Otherwise, the string is split into 8-bit bytes.
        binary_groups = [binary[i:i+8] for i in range(0, len(binary), 8)]
    
    # Convert each binary group into its decimal equivalent.
    return '.'.join([str(int(b, 2)) for b in binary_groups])


def mask_to_binary(mask: str) -> str:
    """
    Convert a subnet mask to its binary representation.

    Args:
        mask (str): The subnet mask in dotted-decimal format (e.g., '255.255.255.0').

    Returns:
        str: The binary representation of the subnet mask.
    """
    return ip_to_binary(mask)


def binary_to_mask(binary: str) -> str:
    """
    Convert a binary string to its equivalent subnet mask.

    Args:
        binary (str): The binary string representing a subnet mask, either unsigned or 2's complement.

    Returns:
        str: The subnet mask in dotted-decimal format.
    """
    return binary_to_ip(binary)


def mask_to_cidr(mask: str) -> int:
    """
    Convert a subnet mask to CIDR notation.

    Args:
        mask (str): The subnet mask in dotted-decimal format (e.g., '255.255.255.0').

    Returns:
        int: The CIDR notation (e.g., 24).
    """
    return sum([bin(int(octet)).count('1') for octet in mask.split('.')])


def cidr_to_mask(cidr: int) -> str:
    """
    Convert CIDR notation to a subnet mask.

    Args:
        cidr (int): The CIDR notation (e.g., 24).

    Returns:
        str: The subnet mask in dotted-decimal format.
    """
    # Create a binary mask with `cidr` number of 1s followed by 0s
    mask = (0xffffffff >> (32 - cidr)) << (32 - cidr)
    # Convert the binary mask to dotted-decimal format
    return binary_to_ip(bin(mask)[2:].zfill(32))


def mask_to_wildcard(mask: str) -> str:
    """
    Convert a subnet mask to a wildcard mask.

    Args:
        mask (str): The subnet mask in dotted-decimal format.

    Returns:
        str: The wildcard mask in dotted-decimal format.
    """
    wildcard = [str(255 - int(octet)) for octet in mask.split('.')]
    return '.'.join(wildcard)


def wildcard_to_mask(wildcard: str) -> str:
    """
    Convert a wildcard mask to a subnet mask.

    Args:
        wildcard (str): The wildcard mask in dotted-decimal format.

    Returns:
        str: The subnet mask in dotted-decimal format.
    """
    mask = [str(255 - int(octet)) for octet in wildcard.split('.')]
    return '.'.join(mask)


def address_to_binary(args: list) -> str:
    """
    Convert an IP address (and optionally a subnet mask) to its binary representation.

    Args:
        args (list): A list containing an IP address and optionally a subnet mask, both in dotted-decimal format.

    Returns:
        str: The binary representation of the IP address and, if provided, the subnet mask.
    """
    address = args[0]
    mask = args[1] if len(args) > 1 else None
    
    ip_binary = ip_to_binary(address)
    
    if mask:
        mask_binary = ip_to_binary(mask)
        return f"Original value: {address} with mask {mask}\nUnsigned Binary IP: {ip_binary}\nUnsigned Binary Mask: {mask_binary}"
    else:
        return f"Original value: {address}\nUnsigned Binary IP: {ip_binary}"


def binary_to_address(binary: List[str]) -> str:
    """
    Convert a list of binary strings to their corresponding IP addresses or subnet masks.

    Args:
        binary (List[str]): A list of binary strings representing IP addresses or subnet masks.

    Returns:
        str: The IP addresses or subnet masks corresponding to the binary strings, separated by newlines.
    """
    return '\n'.join([binary_to_ip(b) for b in binary])


def subnet_calculator(network: str, mask: str) -> Dict[str, Any]:
    """
    Calculate subnet details based on a given IP address and subnet mask.

    Args:
        network (str): The IP address of the network in dotted-decimal format.
        mask (str): The subnet mask in dotted-decimal format.

    Returns:
        Dict[str, Any]: A dictionary containing the subnet details, including network address, netmask, 
                        number of addresses, number of hosts, first and last host addresses, broadcast address, 
                        and whether the network is private or global.
    """
    # Convert the subnet mask to CIDR notation
    cidr = mask_to_cidr(mask)
    # Create an IP network object
    ip_network = ipaddress.ip_network(f"{network}/{cidr}", strict=False)
    
    # Extract subnet details
    network_address = str(ip_network.network_address)
    netmask = str(ip_network.netmask)
    num_addresses = ip_network.num_addresses
    hosts = num_addresses - 2 if num_addresses > 2 else 0
    first_host = str(ip_network[1]) if num_addresses > 1 else None
    last_host = str(ip_network[-2]) if num_addresses > 1 else None
    broadcast = str(ip_network.broadcast_address)
    is_private = ip_network.is_private
    is_global = ip_network.is_global
    
    # Currently only returns the main network
    subnets = [f"{network}/{cidr}"]
    
    return {
        "network_address": network_address,
        "netmask": netmask,
        "num_addresses": num_addresses,
        "hosts": hosts,
        "first_host": first_host,
        "last_host": last_host,
        "broadcast": broadcast,
        "is_private": is_private,
        "is_global": is_global,
        "subnets": subnets
    }


def advanced_subnet_calculator(ip_address: str, new_mask: str) -> Dict[str, Any]:
    """
    Calculate advanced subnet information based on a given IP address with an original mask or CIDR notation,
    and a new subnet mask provided in either CIDR or dotted-decimal notation.

    Args:
        ip_address (str): The IP address, optionally with a CIDR notation (e.g., '192.168.1.0/24').
        new_mask (str): The new subnet mask, either in CIDR notation (e.g., '26') or dotted-decimal format (e.g., '255.255.255.192').

    Returns:
        Dict[str, Any]: A dictionary containing the following subnet details:
            - original_netmask (str): The original subnet mask in dotted-decimal format.
            - new_netmask (str): The new subnet mask in dotted-decimal format.
            - hosts (int): The number of usable hosts in the original subnet.
            - first_host (str): The first usable IP address in the subnet.
            - last_host (str): The last usable IP address in the subnet.
            - broadcast (str): The broadcast address of the subnet.
            - is_private (bool): Indicates if the network is private.
            - is_global (bool): Indicates if the network is global (public).
            - count_subnet (int): The number of subnets created by the new mask.
            - subnets (List[str]): A list of the subnets created by the new mask.
    """
    # Parse the IP address and original CIDR notation if present
    if '/' in ip_address:
        ip, original_cidr = ip_address.split('/')
        original_cidr = int(original_cidr)
    else:
        ip = ip_address
        original_cidr = mask_to_cidr(new_mask)  # Interpret the initial mask as CIDR if not specified

    # Determine the new CIDR notation based on the provided new_mask
    if isinstance(new_mask, str) and '.' in new_mask:
        new_netmask_cidr = mask_to_cidr(new_mask)
    else:
        new_netmask_cidr = int(new_mask)

    # Convert CIDR to dotted-decimal masks
    original_netmask = cidr_to_mask(original_cidr)
    new_netmask = cidr_to_mask(new_netmask_cidr)

    # Create the original network object
    network = ipaddress.ip_network(f"{ip}/{original_cidr}", strict=False)

    # # Calculate subnet details
    hosts = network.num_addresses - 2 if network.num_addresses > 2 else 0
    first_host = str(network[1]) if network.num_addresses > 1 else None
    last_host = str(network[-2]) if network.num_addresses > 1 else None
    broadcast = str(network.broadcast_address)
    is_private = network.is_private
    is_global = network.is_global

    # Generate subnets based on the new mask
    subnets = [str(subnet) for subnet in network.subnets(new_prefix=new_netmask_cidr)]
    count_subnet = len(subnets)

    return {
        "original_netmask": original_netmask,
        "new_netmask": new_netmask,
        "hosts": hosts,
        "first_host": first_host,
        "last_host": last_host,
        "broadcast": broadcast,
        "is_private": is_private,
        "is_global": is_global,
        "count_subnet": count_subnet,
        "subnets": subnets
    }


def vlsm_calculator(network: str, hosts: List[int]) -> List[Dict[str, Any]]:
    """
    Calculate VLSM (Variable Length Subnet Masking) based on a given network and a list of required hosts.

    Args:
        network (str): The network address in CIDR notation (e.g., '192.168.1.0/24').
        hosts (List[int]): A list of integers representing the number of hosts needed for each subnet.

    Returns:
        List[Dict[str, Any]]: A list of dictionaries containing the details of each calculated subnet, including:
            - subnet (str): The network address of the subnet.
            - prefix_length (int): The CIDR prefix length of the subnet.
            - netmask (str): The subnet mask in dotted-decimal format.
            - num_addresses (int): The total number of addresses in the subnet.
            - hosts (int): The number of usable hosts in the subnet.
            - first_host (str): The first usable IP address in the subnet.
            - last_host (str): The last usable IP address in the subnet.
            - broadcast (str): The broadcast address of the subnet.
            - is_private (bool): Indicates if the subnet is private.
            - is_global (bool): Indicates if the subnet is global (public).
    """
    # Sort the list of required hosts in descending order
    hosts.sort(reverse=True)

    # Initialize the list to hold the generated subnets
    subnets = []

    # Calculate the initial network
    ip_network = ipaddress.ip_network(network, strict=False)
    current_subnet = ip_network

    for host_count in hosts:
        # Calculate the necessary prefix for the given number of hosts
        needed_size = host_count + 2  # Include network and broadcast addresses
        subnet_prefix = 32 - (needed_size - 1).bit_length()

        # Generate the subnet with the calculated prefix
        new_subnet = list(current_subnet.subnets(new_prefix=subnet_prefix))[0]
        
        # Add the subnet details to the list
        subnets.append({
            "subnet": str(new_subnet.network_address),
            "prefix_length": subnet_prefix,
            "netmask": str(new_subnet.netmask),
            "num_addresses": new_subnet.num_addresses,
            "hosts": new_subnet.num_addresses - 2,
            "first_host": str(new_subnet[1]),
            "last_host": str(new_subnet[-2]),
            "broadcast": str(new_subnet.broadcast_address),
            "is_private": new_subnet.is_private,
            "is_global": new_subnet.is_global,
        })
        
        # Update the current network for the next subnet
        current_subnet = list(current_subnet.subnets(new_prefix=subnet_prefix))[1]

    return subnets
