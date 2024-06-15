#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Author: FERMAN Franck (https://franckferman.fr, https://github.com/franckferman)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# imports
# ---------------------------------------------------------------------------
import ipaddress


# ---------------------------------------------------------------------------
# functions
# ---------------------------------------------------------------------------
def decimal_to_binary(number):
	"""
	>>> decimal_to_binary(192)
	('11000000', '11000000')
	>>> decimal_to_binary(168)
	('10101000', '10101000')
	>>> decimal_to_binary(0)
	('0', '00000000')
	"""
	decimal=int(number)
	binary=bin(decimal)[2:]
	signed_binary=format(decimal,'#010b')[2:]
	return binary,signed_binary


def binary_to_decimal(user_input):
	"""
	>>> binary_to_decimal(11000000)
	192
	>>> binary_to_decimal(10101000)
	168
	>>> binary_to_decimal(00000000)
	0
	"""
	binary="0b"+str(user_input)
	decimal=int(binary,2)
	return decimal


def decimal_to_hexadecimal(number):
	"""
	>>> decimal_to_hexadecimal(10)
	'a'
	>>> decimal_to_hexadecimal(11)
	'b'
	>>> decimal_to_hexadecimal(161)
	'a1'
	"""
	decimal=int(number)
	hexadecimal=hex(decimal)[2:]
	return hexadecimal


def hexadecimal_to_decimal(hexa):
	"""
	>>> hexadecimal_to_decimal('a')
	10
	>>> hexadecimal_to_decimal('b')
	11
	>>> hexadecimal_to_decimal('a1')
	161
	"""
	hexadecimal=str("0x")+hexa
	decimal=int(hexadecimal,16)
	return decimal


def binary_to_hexadecimal(user_input):
	"""
	>>> binary_to_hexadecimal('00001010')
	'a'
	>>> binary_to_hexadecimal('00001011')
	'b'
	>>> binary_to_hexadecimal('10100001')
	'a1'
	"""
	decimal=binary_to_decimal(user_input)
	hexadecimal=decimal_to_hexadecimal(decimal)
	return hexadecimal


def hexadecimal_to_binary(user_input):
	"""
	>>> hexadecimal_to_binary('a')
	('1010', '00001010')
	>>> hexadecimal_to_binary('b')
	('1011', '00001011')
	>>> hexadecimal_to_binary('a1')
	('10100001', '10100001')
	"""
	decimal=hexadecimal_to_decimal(user_input)
	binary=decimal_to_binary(decimal)
	return binary


def ip_to_binary(ip):
	"""
	>>> ip_to_binary('192.168.0.1')
	('11000000.10101000.0.1', '11000000.10101000.00000000.00000001')
	>>> ip_to_binary('127.0.0.1')
	('1111111.0.0.1', '01111111.00000000.00000000.00000001')
	>>> ip_to_binary('10.0.0.1')
	('1010.0.0.1', '00001010.00000000.00000000.00000001')
	"""
	addr=[int(byte) for byte in ip.split('.')]
	binary=bin(addr[0])[2:]+'.'+bin(addr[1])[2:]+'.'+bin(addr[2])[2:]+'.'+bin(addr[3])[2:]
	signed_binary=format(addr[0],'#010b')[2:]+'.'+format(addr[1],'#010b')[2:]+'.'+format(addr[2],'#010b')[2:]+'.'+format(addr[3],'#010b')[2:]
	return binary,signed_binary


def binary_to_ip(ip):
	"""
	>>> binary_to_ip('11000000.10101000.00000000.00000001')
	'192.168.0.1'
	>>> binary_to_ip('01111111.00000000.00000000.00000001')
	'127.0.0.1'
	>>> binary_to_ip('00001010.00000000.00000000.00000001')
	'10.0.0.1'
	"""
	addr=[int(byte) for byte in ip.split('.')]

	first_byte="0b"+str(addr[0])
	second_byte="0b"+str(addr[1])
	third_byte="0b"+str(addr[2])
	fourth_byte="0b"+str(addr[3])

	first_binary_byte=int(first_byte,2)
	second_binary_byte=int(second_byte,2)
	third_binary_byte=int(third_byte,2)
	fourth_binary_byte=int(fourth_byte,2)

	decimal=str(first_binary_byte)+'.'+str(second_binary_byte)+'.'+str(third_binary_byte)+'.'+str(fourth_binary_byte)
	return decimal


def mask_to_binary(mask):
	"""
	>>> mask_to_binary('255.255.255.0')
	('11111111.11111111.11111111.0', '11111111.11111111.11111111.00000000')
	>>> mask_to_binary('255.0.0.0')
	('11111111.0.0.0', '11111111.00000000.00000000.00000000')
	>>> mask_to_binary('255.255.255.192')
	('11111111.11111111.11111111.11000000', '11111111.11111111.11111111.11000000')
	"""
	binary=ip_to_binary(mask)
	return binary


def binary_to_mask(binary):
	"""
	>>> binary_to_mask('11111111.11111111.11111111.00000000')
	('255.255.255.0')
	>>> binary_to_mask('11111111.00000000.00000000.00000000')
	'255.0.0.0'
	>>> binary_to_mask('11111111.11111111.11111111.11000000')
	'255.255.255.192'
	"""
	decimal=binary_to_mask(binary)
	return decimal


def mask_to_cidr(mask):
	"""
	>>> mask_to_cidr('255.255.255.0')
	24
	>>> mask_to_cidr('255.0.0.0')
	8
	>>> mask_to_cidr('255.255.255.192')
	26
	"""
	addr=[int(byte) for byte in mask.split('.')]
	cidr=sum((bin(mask).count('1') for mask in addr))
	return cidr


def cidr_to_mask(cidr_input):
    cidr=int(cidr_input)
    mask=[]
    y=0
    z=[1]*cidr

    for i in range(len(z)):
        math=i%8
        if math==0:
            if i>=8:
                mask.append(y)
                y=0
        y+=pow(2,7-math)
    mask.append(y)
    [mask.append(0) for i in range(4-len(mask))]
    mask=".".join([str(i) for i in mask])
    return mask


def mask_to_wildcard(mask_input):
	mask=str(mask_input)
	wildcard_mask=str(ipaddress.IPv4Address(int(ipaddress.IPv4Address(mask))^(2**32-1)))
	return wildcard_mask


def wildcard_to_mask(wildcard_input):
	mask=mask_to_wildcard(wildcard_input)
	return mask


def wildcard_to_cidr(wildcard_input):
	cidr=ipaddress.IPv4Address._prefix_from_ip_int(int(ipaddress.IPv4Address(wildcard_input))^(2**32-1))
	return cidr


def address_to_binary(ip_address):
	if '/' in ip_address:
		(ip,cidr)=ip_address.split('/')
        
		ip=[int(ip_address) for ip_address in ip.split('.')]
		cidr=int(cidr)
		mask=[(((1<<32)-1)<<(32-cidr)>>i)&255 for i in reversed(range(0,32,8))]

		ip=str(ip[0])+'.'+str(ip[1])+'.'+str(ip[2])+'.'+str(ip[3])
		mask=str(mask[0])+'.'+str(mask[1])+'.'+str(mask[2])+'.'+str(mask[3])

		binary_ip_address=ip_to_binary(ip)
		binary_mask=mask_to_binary(mask)
		return mask,binary_ip_address[0],binary_ip_address[1],binary_mask[0],binary_mask[1]

	elif " " in ip_address:
		(ip,mask)=ip_address.split(" ")
		cidr=mask_to_cidr(mask)
		ip_address=ip_to_binary(ip)
		mask_address=mask_to_binary(mask)
		return cidr,ip_address[0],ip_address[1],mask_address[0],mask_address[1]


def binary_to_address(binary_address):
		binary_ip_address=binary_address[0]
		binary_mask=binary_address[1]
		ip_address=binary_to_ip(binary_ip_address)
		mask=binary_to_mask(binary_mask)
		cidr=mask_to_cidr(mask)
		return ip_address,mask,cidr


def subnet_calculator(value):
	if '/' in value:
		ip_address=ipaddress.ip_network(value,strict=False)

		mask=ip_address.netmask
		hosts=ip_address.num_addresses-2
		first_host=ip_address[1]
		last_host=ip_address[hosts]
		broadcast=ip_address.broadcast_address
		is_private=ip_address.is_private
		is_global=ip_address.is_global
		
		subnets=[]
		for subnet in ip_address.subnets(prefixlen_diff=0):
			subnets.append(subnet)
		count_subnet=len(subnets)

		return ip_address,mask,hosts,first_host,last_host,broadcast,is_private,is_global
	elif ' ' in value:
		(ip,mask)=value.split(" ")
		cidr=mask_to_cidr(mask)
		ip_address=str(ip)+'/'+str(cidr)
		ip_address=ipaddress.ip_network(ip_address,strict=False)

		mask=ip_address.netmask
		hosts=ip_address.num_addresses-2
		first_host=ip_address[1]
		last_host=ip_address[hosts]
		broadcast=ip_address.broadcast_address
		is_private=ip_address.is_private
		is_global=ip_address.is_global
		
		subnets=[]
		for subnet in ip_address.subnets(prefixlen_diff=0):
			subnets.append(subnet)
		count_subnet=len(subnets)

		return ip_address,cidr,hosts,first_host,last_host,broadcast,is_private,is_global


def advanced_subnet_calculator(ip_address):
	if '/' in ip_address[0]:
		original_ip_address=ip_address[0]
		(ip,cidr)=ip_address[0].split('/')
		new_netmask=ip_address[1]
		netmask=cidr_to_mask(cidr)
		new_netmask_b=cidr_to_mask(new_netmask)

		ip_address=ipaddress.ip_network(original_ip_address,strict=False)

		hosts=ip_address.num_addresses-2
		first_host=ip_address[1]
		last_host=ip_address[hosts]
		broadcast=ip_address.broadcast_address
		is_private=ip_address.is_private
		is_global=ip_address.is_global
		
		subnets=[]
		for subnet in ip_address.subnets(new_prefix=int(new_netmask)):
			subnets.append(subnet)
		count_subnet=len(subnets)

		return netmask,new_netmask_b,hosts,first_host,last_host,broadcast,is_private,is_global,count_subnet,subnets
	
print (" it has been a pleasure working on this app")
	 