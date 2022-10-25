#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#----------------------------------------------------------------------------
# Author: FERMAN Franck (https://franckferman.fr, https://github.com/franckferman)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# imports
# ---------------------------------------------------------------------------
import sys
import argparse
from functions import *

# ---------------------------------------------------------------------------
# colors
# ---------------------------------------------------------------------------
class color:
   GREEN='\033[92m'
   RED='\033[91m'
   BOLD='\033[1m'
   DEFAULT='\033[0m'


# ---------------------------------------------------------------------------
# argparse
# ---------------------------------------------------------------------------
parser=argparse.ArgumentParser(description=' The Network Calculator Toolbox is a tool allowing the realization of numerous calculations dedicated essentially to the network administration.')
parser.add_argument("--dectobin","--dec2bin","--d2b",help="Convert a decimal number to binary.",
	type=int,default=None)
parser.add_argument("--bintodec","--bin2dec","--b2d",help="Convert a binary number to decimal.",
	type=int,default=None)
parser.add_argument("--dectohex","--dec2hex","--d2h",help="Convert a decimal number to hexadecimal.",
	type=int,default=None)
parser.add_argument("--hextodec","--hex2dec","--h2d",help="Convert a hexadecimal number to decimal.",
	type=str,default=None)
parser.add_argument("--bintohex","--bin2hex","--b2h",help="Convert a binary number to hexadecimal.",
	type=int,default=None)
parser.add_argument("--hextobin","--hex2bin","--h2b",help="Convert a hexadecimal number to binary.",
	type=str,default=None)
parser.add_argument("--iptobin","--ip2bin","--i2b",help="Convert an IP in decimal format to binary format.",
	type=str,default=None)
parser.add_argument("--bintoip","--bin2ip","--b2i",help="Convert an IP in binary format to decimal format.",
	type=str,default=None)
parser.add_argument("--masktobin","--mask2bin","--m2b",help="Convert a mask in decimal format to binary format.",
	type=str,default=None)
parser.add_argument("--bintomask","--bin2mask","--b2m",help="Convert a mask in binary format to decimal format.",
	type=str,default=None)
parser.add_argument("--masktocidr","--mask2cidr","--m2c",help="Convert a mask to CIDR.",
	type=str,default=None)
parser.add_argument("--cidrtomask","--cidr2mask","--c2m",help="Convert a CIDR to mask.",
	type=str,default=None)
parser.add_argument("--masktowildcard","--mask2wildcard","--m2w",help="Convert a mask to wildcard mask.",
	type=str,default=None)
parser.add_argument("--wildcardtomask","--wildcard2mask","--w2m",help="Convert a wildcard mask to mask.",
	type=str,default=None)
parser.add_argument("--cidrtowildcard","--cidr2wildcard","--c2w",help="Convert a CIDR to mask.",
	type=str,default=None)
parser.add_argument("--wildcardtocidr","--wildcard2cidr","--w2c",help="Convert a wildcard mask to CIDR.",
	type=str,default=None)
parser.add_argument("--addrtobin","--addr2bin","--a2b",help="Convert an IP address (IP/CIDR or IP MASK) in binary format to decimal format.",
	type=str,default=None,nargs='+')
parser.add_argument("--bintoaddr","--bin2addr","--b2a",help="Convert an IP address in binary format to decimal format.",
	type=str,default=None,nargs='+')
parser.add_argument("--subnetcalc","--subnet","--sc",help="simple subnet calculator.",
	type=str,default=None,nargs='+')
parser.add_argument("--advancedsubnetcalc","--asubnet","--asc",help="advanced subnet calculator.",
	type=str,default=None,nargs='+')
args=parser.parse_args()


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
if __name__=='__main__':

	if len(sys.argv)<2:
		print(str(sys.argv[0]),"expected one argument.\nFor more information, enter the --help argument.")

	if args.dectobin!=None:
		print("Original value:",args.dectobin)
		print("\nBinary:",decimal_to_binary(args.dectobin)[0])
		print("Signed Binary:",decimal_to_binary(args.dectobin)[1])

	if args.bintodec!=None:
		print("Original value:",args.bintodec)
		print("\nDecimal:",binary_to_decimal(args.bintodec))

	if args.dectohex!=None:
		print("Original value:",args.dectohex)
		print("\nHexadecimal:",decimal_to_hexadecimal(args.dectohex))

	if args.hextodec!=None:
		print("Original value:",args.hextodec)
		print("\nDecimal:",hexadecimal_to_decimal(args.hextodec))

	if args.bintohex!=None:
		print("Original value:",args.bintohex)
		print("\nHexadecimal:",binary_to_hexadecimal(args.bintohex))

	if args.hextobin!=None:
		print("Original value:",args.hextobin)
		print("\nBinary:",hexadecimal_to_binary(args.hextobin)[0])
		print("Signed Binary:",hexadecimal_to_binary(args.hextobin)[1])

	if args.iptobin!=None:
		print("Original value:",args.iptobin)
		print("\nBinary:",ip_to_binary(args.iptobin)[0])
		print("Signed Binary:",ip_to_binary(args.iptobin)[1])

	if args.bintoip!=None:
		print("Original value:",args.bintoip)
		print("\nDecimal:",binary_to_ip(args.bintoip))

	if args.masktobin!=None:
		print("Original value:",args.masktobin)
		print("\nBinary:",mask_to_binary(args.masktobin)[0])
		print("Signed Binary:",mask_to_binary(args.masktobin)[1])

	if args.bintomask!=None:
		print("Original value:",args.bintomask)
		print("\nDecimal:",binary_to_mask(args.bintomask))

	if args.masktocidr!=None:
		print("Original value:",args.masktocidr)
		print("\nCIDR:",mask_to_cidr(args.masktocidr))

	if args.cidrtomask!=None:
		print("Original value:",args.cidrtomask)
		print("\nMask:",cidr_to_mask(args.cidrtomask))

	if args.masktowildcard!=None:
		print("Original value:",args.masktowildcard)
		print("\nWildcard mask:",mask_to_wildcard(args.masktowildcard))

	if args.wildcardtomask!=None:
		print("Original value:",args.wildcardtomask)
		print("\nMask:",wildcard_to_mask(args.wildcardtomask))

	if args.wildcardtocidr!=None:
		print("Original value:",args.wildcardtocidr)
		print("\nCIDR:",wildcard_to_cidr(args.wildcardtocidr))

	if args.addrtobin!=None:
		if len(args.addrtobin)==1:
			print("Original value:",args.addrtobin[0])
			print("Mask:",address_to_binary(args.addrtobin[0])[0])
			print("\nSigned IP Binary:",address_to_binary(args.addrtobin[0])[1])
			print("IP Binary:",address_to_binary(args.addrtobin[0])[2])
			print("\nSigned Mask Binary:",address_to_binary(args.addrtobin[0])[3])
			print("Mask Binary:",address_to_binary(args.addrtobin[0])[4])
		elif len(args.addrtobin)==2:
			ip_address=str(args.addrtobin[0])+str(" ")+str(args.addrtobin[1])
			print("Original value:",ip_address)
			print("CIDR:",address_to_binary(ip_address)[0])
			print("\nSigned IP Binary:",address_to_binary(ip_address)[1])
			print("IP Binary:",address_to_binary(ip_address)[2])
			print("\nSigned Mask Binary:",address_to_binary(ip_address)[3])
			print("Mask Binary:",address_to_binary(ip_address)[4])
		else:
			print(color.BOLD+color.RED+"A maximum of two arguments are expected."+color.DEFAULT)

	if args.bintoaddr!=None:
		binary_address=str(args.bintoaddr[0])+str(" ")+str(args.bintoaddr[1])
		print("Original value:",binary_address)
		print("\nIP address:",binary_to_address(args.bintoaddr)[0])
		print("Mask:",binary_to_address(args.bintoaddr)[1])
		print("CIDR:",binary_to_address(args.bintoaddr)[2])

	if args.subnetcalc!=None:
		if len(args.subnetcalc)==1:
			print("Original value:",args.subnetcalc[0])
			print("Mask:",subnet_calculator(args.subnetcalc[0])[1])
			print("\nHosts:",subnet_calculator(args.subnetcalc[0])[2])
			print("First host:",subnet_calculator(args.subnetcalc[0])[3])
			print("Last host:",subnet_calculator(args.subnetcalc[0])[4])
			print("Broadcast:",subnet_calculator(args.subnetcalc[0])[5])
			
			private_address=subnet_calculator(args.subnetcalc[0])[6]
			public_address=subnet_calculator(args.subnetcalc[0])[7]
			if public_address==True and private_address==False:
				address_type="public address"
			elif private_address==True and public_address==False:
				address_type="private address"
			else:
				print(color.BOLD+color.RED+"the type of address is not identifiable."+color.DEFAULT)

			print("\nType of address:",address_type)
		elif len(args.subnetcalc)==2:
			user_value=str(args.subnetcalc[0])+str(" ")+str(args.subnetcalc[1])
			print("Original value:",user_value)
			print("CIDR:",subnet_calculator(user_value)[1])
			print("\nHosts:",subnet_calculator(user_value)[2])
			print("First host:",subnet_calculator(user_value)[3])
			print("Last host:",subnet_calculator(user_value)[4])
			print("Broadcast:",subnet_calculator(user_value)[5])
			
			private_address=subnet_calculator(user_value)[6]
			public_address=subnet_calculator(user_value)[7]

			if public_address==True and private_address==False:
				address_type="public address"
			elif private_address==True and public_address==False:
				address_type="private address"
			else:
				print(color.BOLD+color.RED+"the type of address is not identifiable."+color.DEFAULT)

			print("\nType of address:",address_type)

	if args.advancedsubnetcalc!=None:
		original_value=args.advancedsubnetcalc[0]+' '+args.advancedsubnetcalc[1]
		print("Original value:",original_value)

		private_address=advanced_subnet_calculator(args.advancedsubnetcalc)[6]
		public_address=advanced_subnet_calculator(args.advancedsubnetcalc)[7]

		if public_address==True and private_address==False:
			address_type="public address"
		elif private_address==True and public_address==False:
			address_type="private address"
		else:
			print(color.BOLD+color.RED+"the type of address is not identifiable."+color.DEFAULT)

		print("Type of address:",address_type)

		print("Original mask:",advanced_subnet_calculator(args.advancedsubnetcalc)[0])
		print("New mask:",advanced_subnet_calculator(args.advancedsubnetcalc)[1])

		print("\nHosts:",advanced_subnet_calculator(args.advancedsubnetcalc)[2])
		print("First host:",advanced_subnet_calculator(args.advancedsubnetcalc)[3])
		print("Last host:",advanced_subnet_calculator(args.advancedsubnetcalc)[4])
		print("Broadcast:",advanced_subnet_calculator(args.advancedsubnetcalc)[5])

		subnets=advanced_subnet_calculator(args.advancedsubnetcalc)[8]

		if subnets==1:
			print("\nSubnet:",advanced_subnet_calculator(args.advancedsubnetcalc)[8])
		elif subnets>=2:
			print("\nSubnets:",advanced_subnet_calculator(args.advancedsubnetcalc)[8])
		else:
			print(color.BOLD+color.RED+"the number of subnets could not be identified."+color.DEFAULT)
		
		subnet_list=advanced_subnet_calculator(args.advancedsubnetcalc)[9]
		subnets_list=len(subnet_list)

		if subnets_list==1:
			print("Subnet list:",*subnet_list)
		elif subnets_list>=2:
			print("Subnets list:",*subnet_list)
		else:
			print(color.BOLD+color.RED+"the list of subnets could not be identified."+color.DEFAULT)