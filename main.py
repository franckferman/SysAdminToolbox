import sys
from sys import argv
import os
from os import system
import ipaddress
from ipaddress import IPv4Address
from ipaddress import IPv4Network

def Check_UserInput():

	WordListUsage=["--help","-help","--h","-h","/help","/h","--usage","-usage","--u","-u","/usage","/u"]
	WordListDecToBin=["--dectobin","--dec2bin","--d2b","-dectobin","-dec2bin","-d2b","/dectobin","/dec2bin","/d2b"]
	WordListBinToDec=["--bintodec","--bin2dec","--b2d","-bintodec","-bin2dec","-b2d","/bintodec","/bin2dec","/b2d"]
	WordListDecToHex=["--dectohex","--dec2hex","--d2h","-dectohex","-dec2hex","-d2h","/dectohex","/dec2hex","/d2h"]
	WordListHexToDec=["--hextodec","--hex2dec","--h2d","-hextodec","-hex2dec","-h2d","/hextodec","/hex2dec","/h2d"]
	WordListIPToBin=["--iptobin","--ip2bin","--i2b","-iptobin","-ip2bin","-i2b","/iptobin","/ip2bin","/i2b"]
	WordListBinToIP=["--bintoip","--bin2ip","--b2i","-bintoip","-bin2ip","-b2i","/bintoip","/bin2ip","/b2i"]
	WordListMaskToBin=["--masktobin","--mask2bin","--m2b","-masktobin","-mask2bin","-m2b","/masktobin","/mask2bin","/m2b"]
	WordListBinToMask=["--bintomask","--bin2mask","--b2m","-bintomask","-bin2mask","-b2m","/bintomask","/bin2mask","/b2m"]
	WordListMaskToCIDR=["--masktocidr","--mask2cidr","--m2c","-masktocidr","-mask2cidr","-m2c","/masktocidr","/mask2cidr","/m2c"]
	WordListCIDRToMask=["--cidrtomask","--cidr2mask","--c2m","-cidrtomask","-cidr2mask","-c2m","/cidrtomask","/cidr2mask","/c2m"]
	WordListMaskToWildcard=["--masktowildcard","--mask2wildcard","--m2w","-masktowildcard","-mask2wildcard","-m2w","/masktowildcard","/mask2wildcard","/m2w"]
	WordListWildcardToMask=["--wildcardtomask","--wildcard2mask","--w2m","-wildcardtomask","-wildcard2mask","-w2m","/wildcardtomask","/wildcard2mask","/w2m"]
	WordListCIDRToWildcard=["--cidrtowildcard","--cidr2wildcard","--c2w","-cidrtowildcard","-cidr2wildcard","-c2w","/cidrtowildcard","/cidr2wildcard","/c2w"]
	WordListWildcardToCIDR=["--wildcardtocidr","--wildcard2cidr","--w2c","-wildcardtocidr","-wildcard2cidr","-w2c","/wildcardtocidr","/wildcard2cidr","/w2c"]
	WordListAddrToBin=["--addrtobin","--addr2bin","--a2b","-addrtobin","-addr2bin","-a2b","/addrtobin","/addr2bin","/a2b"]
	WordListBinToAddr=["--bintoaddr","--bin2addr","--b2a","-bintoaddr","-bin2addr","-b2a","/bintoaddr","/bin2addr","/b2a"]
	WordListSubnetCalc=["--subnetcalc","--subnet","--sc","-subnetcalc","-subnet","-sc","/subnetcalc","/subnet","/sc"]
	WordListAdvancedSubnetCalc=["--advancedsubnetcalc","--asubnet","--asc","-advancedsubnetcalc","-asubnet","-asc","/advancedsubnetcalc","/asubnet","/asc"]

	if len(sys.argv)==1:
		usage()

	elif str(sys.argv[1]) in WordListUsage:
		usage()

	elif str(sys.argv[1]) in WordListDecToBin:
		decimaltobinary()

	elif str(sys.argv[1]) in WordListBinToDec:
		binarytodecimal()

	elif str(sys.argv[1]) in WordListDecToHex:
		decimaltohexadecimal()

	elif str(sys.argv[1]) in WordListHexToDec:
		hexadecimaltodecimal()

	elif str(sys.argv[1]) in WordListIPToBin:
		ipaddrtobinary()

	elif str(sys.argv[1]) in WordListBinToIP:
		binarytoipaddr()

	elif str(sys.argv[1]) in WordListMaskToBin:
		ipaddrtobinary()

	elif str(sys.argv[1]) in WordListBinToMask:
		binarytoipaddr()

	elif str(sys.argv[1]) in WordListMaskToCIDR:
		masktocidr()

	elif str(sys.argv[1]) in WordListCIDRToMask:
		cidrtomask()

	elif str(sys.argv[1]) in WordListMaskToWildcard:
		masktowildcardmask()

	elif str(sys.argv[1]) in WordListWildcardToMask:
		wildcardtomask()

	elif str(sys.argv[1]) in WordListCIDRToWildcard:
		cidrtowildcard()

	elif str(sys.argv[1]) in WordListWildcardToCIDR:
		wildcardtocidr()

	elif str(sys.argv[1]) in WordListAddrToBin:
		addrtobinary()

	elif str(sys.argv[1]) in WordListBinToAddr:
		binarytoaddr()

	elif str(sys.argv[1]) in WordListSubnetCalc:
		subnetcalculator()
	
	elif str(sys.argv[1]) in WordListAdvancedSubnetCalc:
		advancedsubnetcalculator()

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

def usage():
	clear()
	print("Usage: python3 main.py OPTION")
	print("")
	print("OPTIONS:")
	print("     --help, -help: display this help message.")
	print("")
	print("ARGS:")
	print("     --subnetcalc 192.168.0.1/24: simple subnet calculator.")
	print("     --advancedsubnetcalc 192.168.0.1/24 25 (ip/original_cidr new_cidr): advanced subnet calculator.")
	print("")
	print("     --addrtobin 192.168.0.1/24 or 192.168.0.1 255.255.255.0: convert an IP address and a CIDR or a mask to a binary number.")
	print("     --bintoaddr 11111111.11111111.11111111.00000000 11111111.11111111.11111111.00000000: convert a binary IP address and a mask to a decimal value.")
	print("")
	print("     --iptobin 192.168.0.1: convert an IP address to a binary number.")
	print("     --bintoip 11000000.10101000.00000000.00000001: convert an IP address in binary format to decimal format.")
	print("")
	print("     --masktobin 255.255.255.0: convert a mask to a binary number.")
	print("     --bintomask 11111111.11111111.11111111.00000000: convert a mask in binary format to decimal format.")
	print("")
	print("     --masktocidr 255.255.255.0: convert a mask to a CIDR.")
	print("     --cidrtomask 24: convert a CIDR to a mask.")
	print("")
	print("     --masktowildcard 255.255.255.0: convert a mask to a wildcard mask.")
	print("     --wildcardtomask 0.0.0.255: convert a wildcard mask to mask.")
	print("")
	print("     --cidrtowildcard 24: convert a cidr to a wildcard mask.")
	print("     --wildcardtocidr 0.0.0.255: convert a wildcard mask to cidr.")
	print("")
	print("     --dectobin 42: convert a decimal number into a binary number.")
	print("     --bintodec 00101010: convert a binary number into a decimal number.")
	print("")
	print("     --dectohex 42: convert a decimal number into a hexadecimal number.")
	print("     --hextodec FF: convert a hexadecimal number into a decimal number.")
	print("")
	print("EXAMPLES:")
	print("     python3 ./main.py --addrtobin 192.168.1.42/16")
	print("     python3 ./main.py --dectobin 42")
	print("")
	exit(0)

def clear():
    os.system("cls" if os.name=="nt" else "clear")

def func_decimaltobinary(x):
	decimal_value=int(x)
	binary_value=bin(x)[2:]
	return binary_value

def func_decimaltobinaryfull(x):
	decimal_value=int(x)
	binary_full_value=format(x,'#010b')[2:]
	return binary_full_value

def decimaltobinary():
	if len(sys.argv)==2:
		decimal_value=input("Enter a decimal number: ")
		decimal_value=int(decimal_value)
		print("Initial value (decimal):",decimal_value)
		print("")
		print("Binary number value:",func_decimaltobinary(decimal_value))
		print("Signed binary number value:",func_decimaltobinaryfull(decimal_value))
		exit(0)

	elif len(sys.argv)==3:
		decimal_value=int(sys.argv[2])
		print("Initial value (decimal):",decimal_value)
		print("")
		print("Binary number value:",func_decimaltobinary(decimal_value))
		print("Signed binary number value:",func_decimaltobinaryfull(decimal_value))
		exit(0)

	elif len(sys.argv)==4:
		print("\033[0;31mOnly one argument is expected.\033[00m")
		exit(1)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

def func_binarytodecimal(x):
	binary_value="0b"+x
	decimal_value=int(x,2)
	return decimal_value

def binarytodecimal():
	if len(sys.argv)==2:
		binary_value=input("Enter a binary value: ")
		print("Initial value (binary):",binary_value)
		print("")
		print("Decimal number value:",func_binarytodecimal(binary_value))
		exit(0)

	elif len(sys.argv)==3:
		binary_value=(sys.argv[2])
		print("Initial value (binary):",binary_value)
		print("")
		print("Decimal number value:",func_binarytodecimal(binary_value))
		exit(0)

	elif len(sys.argv)==4:
		print("\033[0;31mOnly one argument is expected.\033[00m")
		exit(1)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

def func_decimaltohexadecimal(x):
	decimal_value=int(x)
	hexadecimal_value=hex(x)[2:]
	return hexadecimal_value

def decimaltohexadecimal():
	if len(sys.argv)==2:
		decimal_value=input("Enter a decimal value: ")
		decimal_value=int(decimal_value)
		print("Initial value (decimal):",decimal_value)
		print("")
		print("Hexadecimal number value:",func_decimaltohexadecimal(decimal_value))
		exit(0)

	elif len(sys.argv)==3:
		decimal_value=(sys.argv[2])
		decimal_value=int(decimal_value)
		print("Initial value (decimal):",decimal_value)
		print("")
		print("Hexadecimal number value:",func_decimaltohexadecimal(decimal_value))
		exit(0)

	elif len(sys.argv)==4:
		print("\033[0;31mOnly one argument is expected.\033[00m")
		exit(1)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

def func_hexadecimaltodecimal(x):
	hexadecimal_value="0x"+x
	decimal_value=int(x,16)
	return decimal_value

def hexadecimaltodecimal():
	if len(sys.argv)==2:
		hexadecimal_value=input("Enter a hexadecimal value: ")
		print("Initial value (hexadecimal):",hexadecimal_value)
		print("")
		print("Decimal number value:",func_hexadecimaltodecimal(hexadecimal_value))
		exit(0)

	elif len(sys.argv)==3:
		hexadecimal_value=(sys.argv[2])
		print("Initial value (hexadecimal):",hexadecimal_value)
		print("")
		print("Decimal number value:",func_hexadecimaltodecimal(hexadecimal_value))
		exit(0)

	elif len(sys.argv)==4:
		print("\033[0;31mOnly one argument is expected.\033[00m")
		exit(1)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

def func_ipaddrtobinary(x):

	addr=[int(i) for i in x.split(".")]
	Final_Byte_Binary=bin(addr[0])[2:]+"."+bin(addr[1])[2:]+"."+bin(addr[2])[2:]+"."+bin(addr[3])[2:]
	return Final_Byte_Binary

def func_ipaddrtobinaryfull(x):

	addr=[int(i) for i in x.split(".")]
	Final_Byte_Binary=format(addr[0],'#010b')[2:]+"."+format(addr[1],'#010b')[2:]+"."+format(addr[2],'#010b')[2:]+"."+format(addr[3],'#010b')[2:]
	return Final_Byte_Binary

def ipaddrtobinary():
	if len(sys.argv)==2:
		decimal_value=input("Enter a decimal number containing four bytes: ")
		decimal_value=str(decimal_value)
		print("Initial value (decimal):",decimal_value)
		print("")
		print("Binary number value:",func_ipaddrtobinary(decimal_value))
		print("Signed binary number value:",func_ipaddrtobinaryfull(decimal_value))
		exit(0)

	elif len(sys.argv)==3:
		decimal_value=str(sys.argv[2])
		print("Initial value (decimal):",decimal_value)
		print("")
		print("Binary number value:",func_ipaddrtobinary(decimal_value))
		print("Signed binary number value:",func_ipaddrtobinaryfull(decimal_value))
		exit(0)

	elif len(sys.argv)==4:
		print("\033[0;31mOnly one argument is expected.\033[00m")
		exit(1)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

def func_binarytoipaddr(x):

	addr=[int(i) for i in x.split(".")]

	First_Byte_Binary="0b"+str(addr[0])
	Second_Byte_Binary="0b"+str(addr[1])
	Third_Byte_Binary="0b"+str(addr[2])
	Fourth_Byte_Binary="0b"+str(addr[3])

	Final_First_Byte_Binary=int(First_Byte_Binary,2)
	Final_Second_Byte_Binary=int(Second_Byte_Binary,2)
	Final_Third_Byte_Binary=int(Third_Byte_Binary,2)
	Final_Fourth_Byte_Binary=int(Fourth_Byte_Binary,2)

	decimal_value=str(Final_First_Byte_Binary)+"."+str(Final_Second_Byte_Binary)+"."+str(Final_Third_Byte_Binary)+"."+str(Final_Fourth_Byte_Binary)
	return decimal_value

def binarytoipaddr():
	if len(sys.argv)==2:
		binary_value=input("Enter an IP address in binary format: ")
		binary_value=str(binary_value)
		print("Initial value (binary):",binary_value)
		print("")
		print("Decimal number value:",func_binarytoipaddr(binary_value))
		exit(0)

	elif len(sys.argv)==3:
		binary_value=str(sys.argv[2])
		print("Initial value (binary):",binary_value)
		print("")
		print("Decimal number value:",func_binarytoipaddr(binary_value))
		exit(0)

	elif len(sys.argv)==4:
		print("\033[0;31mOnly one argument is expected.\033[00m")
		exit(1)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

def func_masktocidr(x):

	addr=[int(i) for i in x.split(".")]
	cidr=sum((bin(x).count('1') for x in addr))
	return cidr

def masktocidr():
	if len(sys.argv)==2:
		mask=input("Enter a mask: ")
		mask=str(mask)
		print("Initial value (decimal):",mask)
		print("")
		print("CIDR:",func_masktocidr(mask))
		exit(0)

	elif len(sys.argv)==3:
		mask=str(sys.argv[2])
		print("Initial value (decimal):",mask)
		print("")
		print("CIDR:",func_masktocidr(mask))
		exit(0)

	elif len(sys.argv)==4:
		print("\033[0;31mOnly one argument is expected.\033[00m")
		exit(1)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

def func_cidrtomask(x):

        cidr=int(x)

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
        mask_result=".".join([str(i) for i in mask])

        return mask_result

def cidrtomask():
	if len(sys.argv)==2:
		cidr=input("Enter a cidr: ")
		print("Initial value (CIDR):",cidr)
		print("")
		print("Mask:",func_cidrtomask(cidr))
		exit(0)

	elif len(sys.argv)==3:
		cidr=str(sys.argv[2])
		print("Initial value (CIDR):",cidr)
		print("")
		print("Mask:",func_cidrtomask(cidr))
		exit(0)

	elif len(sys.argv)==4:
		print("\033[0;31mOnly one argument is expected.\033[00m")
		exit(1)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

def func_masktowildcardmask(x):

	mask=str(x)
	wildcardmask=str(IPv4Address(int(IPv4Address(mask))^(2**32-1)))
	return wildcardmask

def masktowildcardmask():
	if len(sys.argv)==2:
		mask=input("Enter a mask: ")
		mask=str(mask)
		print("Initial value (Mask):",mask)
		print("")
		print("Wildcard mask:",func_masktowildcardmask(mask))
		exit(0)

	elif len(sys.argv)==3:
		mask=str(sys.argv[2])
		print("Initial value (Mask):",mask)
		print("")
		print("Wildcard mask:",func_masktowildcardmask(mask))
		exit(0)

	elif len(sys.argv)==4:
		print("\033[0;31mOnly one argument is expected.\033[00m")
		exit(1)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

def func_wildcardtomask(x):

	wildcardmask=str(x)
	mask=str(IPv4Address(int(IPv4Address(wildcardmask))^(2**32-1)))
	return mask

def wildcardtomask():
	if len(sys.argv)==2:
		wildcardmask=input("Enter a wildcard mask: ")
		wildcardmask=str(wildcardmask)
		print("Initial value (wildcard mask):",wildcardmask)
		print("")
		print("Mask:",func_wildcardtomask(wildcardmask))
		exit(0)

	elif len(sys.argv)==3:
		wildcardmask=str(sys.argv[2])
		print("Initial value (wildcard mask):",wildcardmask)
		print("")
		print("Mask:",func_wildcardtomask(wildcardmask))
		exit(0)

	elif len(sys.argv)==4:
		print("\033[0;31mOnly one argument is expected.\033[00m")
		exit(1)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

def func_cidrtowildcard(x):

	cidr=str(x)
	cidr=str(IPv4Address(int(IPv4Address._make_netmask(cidr)[0])^(2**32-1)))
	return cidr

def cidrtowildcard():
	if len(sys.argv)==2:
		cidr=input("Enter a CIDR: ")
		cidr=str(cidr)
		print("Initial value (CIDR):",cidr)
		print("")
		print("Wildcard mask:",func_cidrtowildcard(cidr))
		exit(0)

	elif len(sys.argv)==3:
		cidr=str(sys.argv[2])
		print("Initial value (CIDR):",cidr)
		print("")
		print("Wildcard mask:",func_cidrtowildcard(cidr))
		exit(0)

	elif len(sys.argv)==4:
		print("\033[0;31mOnly one argument is expected.\033[00m")
		exit(1)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

def func_wildcardtocidr(x):

	wildcardmask=str(x)
	cidr=IPv4Address._prefix_from_ip_int(int(IPv4Address(wildcardmask))^(2**32-1))
	return cidr

def wildcardtocidr():
	if len(sys.argv)==2:
		wildcardmask=input("Enter a wildcard mask: ")
		wildcardmask=str(wildcardmask)
		print("Initial value (wildcard mask):",wildcardmask)
		print("")
		print("CIDR:",func_wildcardtocidr(wildcardmask))
		exit(0)

	elif len(sys.argv)==3:
		wildcardmask=str(sys.argv[2])
		print("Initial value (wildcard mask):",wildcardmask)
		print("")
		print("CIDR:",func_wildcardtocidr(wildcardmask))
		exit(0)

	elif len(sys.argv)==4:
		print("\033[0;31mOnly one argument is expected.\033[00m")
		exit(1)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

def func_addrtobin(x):

	addr=x

	if "/" in addr:
		(addr,cidr)=addr.split("/")
		
		ipaddr=[int(x) for x in addr.split(".")]
		cidr=int(cidr)
		mask=[(((1<<32)-1)<<(32-cidr)>>i)&255 for i in reversed(range(0,32,8))]

		ipaddr=str(ipaddr[0])+"."+str(ipaddr[1])+"."+str(ipaddr[2])+"."+str(ipaddr[3])
		mask=str(mask[0])+"."+str(mask[1])+"."+str(mask[2])+"."+str(mask[3])

	elif " " in addr:
		(addr, mask)=addr.split(" ")

		ipaddr=[int(x) for x in addr.split(".")]
		mask=[int(x) for x in mask.split(".")]
		cidr=sum((bin(x).count('1') for x in mask))

		ipaddr=str(ipaddr[0])+"."+str(ipaddr[1])+"."+str(ipaddr[2])+"."+str(ipaddr[3])
		mask=str(mask[0])+"."+str(mask[1])+"."+str(mask[2])+"."+str(mask[3])

	return func_ipaddrtobinary(ipaddr),func_ipaddrtobinary(mask),func_ipaddrtobinaryfull(ipaddr),func_ipaddrtobinaryfull(mask),cidr,mask

def addrtobinary():
	if len(sys.argv)==2:
		decimal_value=input("Enter an IP address and a subnet mask: ")
		print("Initial value (decimal):",decimal_value)
		if "/" in decimal_value:
			print("Initial mask value (decimal):",func_addrtobin(decimal_value)[5])
		elif " " in decimal_value:
			print("Initial CIDR value (decimal):",func_addrtobin(decimal_value)[4])

		print("")
		print("Binary IP number value:",func_addrtobin(decimal_value)[0])
		print("Binary mask number value:",func_addrtobin(decimal_value)[1])
		print("")
		print("Binary IP number value:",func_addrtobin(decimal_value)[2])
		print("Binary mask number value:",func_addrtobin(decimal_value)[3])
		exit(0)

	elif len(sys.argv)==3:
		decimal_value=(sys.argv[2])
		print("Initial value (decimal):",decimal_value)
		print("Initial mask value (decimal):",func_addrtobin(decimal_value)[5])
		print("")
		print("Binary IP number value:",func_addrtobin(decimal_value)[0])
		print("Binary mask number value:",func_addrtobin(decimal_value)[1])
		print("")
		print("Binary IP number value:",func_addrtobin(decimal_value)[2])
		print("Binary mask number value:",func_addrtobin(decimal_value)[3])
		exit(0)

	elif len(sys.argv)==4:
		decimal_value=(sys.argv[2])+" "+(sys.argv[3])
		print("Initial value (decimal):",decimal_value)
		print("Initial CIDR value (decimal):",func_addrtobin(decimal_value)[4])
		print("")
		print("Binary IP number value:",func_addrtobin(decimal_value)[0])
		print("Binary mask number value:",func_addrtobin(decimal_value)[1])
		print("")
		print("Binary IP number value:",func_addrtobin(decimal_value)[2])
		print("Binary mask number value:",func_addrtobin(decimal_value)[3])
		exit(0)

	elif len(sys.argv)==5:
		print("\033[0;31mOnly one or two argument is expected.\033[00m")
		exit(1)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

def func_binarytoaddr(x):

		addr=x
		(addr, mask)=addr.split(" ")

		addr=func_binarytoipaddr(addr)
		mask=func_binarytoipaddr(mask)
		return addr,mask

def binarytoaddr():
	if len(sys.argv)==2:
		binary_value=input("Enter an IP address and a subnet mask in binary format: ")
		print("Initial value (binary):",binary_value)
		print("")
		print("Decimal IP number value:",func_binarytoaddr(binary_value)[0])
		print("Decimal mask number value:",func_binarytoaddr(binary_value)[1])
		cidr=func_binarytoaddr(binary_value)[1]
		print("CIDR:",func_masktocidr(cidr))
		exit(0)

	elif len(sys.argv)==3:
		decimal_value=(sys.argv[2])
		print("\033[0;31mTwo argument is expected.\033[00m")
		exit(1)

	elif len(sys.argv)==4:
		binary_value=(sys.argv[2])+" "+(sys.argv[3])
		print("Initial value (binary):",binary_value)
		print("")
		print("Decimal IP number value:",func_binarytoaddr(binary_value)[0])
		print("Decimal mask number value:",func_binarytoaddr(binary_value)[1])
		cidr=func_binarytoaddr(binary_value)[1]
		print("CIDR:",func_masktocidr(cidr))
		exit(0)

	elif len(sys.argv)==5:
		print("\033[0;31mOnly two argument is expected.\033[00m")
		exit(1)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

def func_subnetcalculator(x):
	
	if " " in x:
		(addr, mask)=x.split(" ")
		mask=[int(x) for x in mask.split(".")]
		cidr=sum((bin(x).count('1') for x in mask))
		ipaddr=str(addr)+"/"+str(cidr)
		ipaddr=ipaddress.ip_network(ipaddr, strict=False)

	elif "/" in x:
		ipaddr=ipaddress.ip_network(x, strict=False)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

	mask=ipaddr.netmask
	size=ipaddr.num_addresses-2
	firstHost=ipaddr[1]
	lastHost=ipaddr[size]
	br=ipaddr.broadcast_address

	subnets=[]
	for subnet in ipaddr.subnets(prefixlen_diff=0):
		subnets.append(subnet)

	sn=len(subnets)

	return ipaddr,mask,size,firstHost,lastHost,br,sn,subnets

def subnetcalculator():
	if len(sys.argv)==2:
		ipaddr=input("Enter an IP address and a CIDR or a subnet mask: ")
		print("Initial value:",ipaddr)

		mask=str(func_subnetcalculator(ipaddr)[1])
		mask=[int(x) for x in mask.split(".")]
		cidr=sum((bin(x).count('1') for x in mask))

		if "/" in ipaddr:
			print("Mask:",func_subnetcalculator(ipaddr)[1])
		elif " " in ipaddr:
			print("CIDR:", cidr)
		else:
			print("\033[0;31mAn unexpected error was caused.\033[00m")
			exit(1)

		print("")
		print("Network address:",func_subnetcalculator(ipaddr)[0])
		print("")
		print("First host:",func_subnetcalculator(ipaddr)[3])
		print("Last host:",func_subnetcalculator(ipaddr)[4])
		print("")
		print("Broadcast:",func_subnetcalculator(ipaddr)[5])
		print("")
		print("Number of hosts:",func_subnetcalculator(ipaddr)[2])
		exit(0)

	elif len(sys.argv)==3:
		ipaddr=(sys.argv[2])
		print("Initial value:",ipaddr)
		print("Mask:",func_subnetcalculator(ipaddr)[1])

		mask=str(func_subnetcalculator(ipaddr)[1])
		mask=[int(x) for x in mask.split(".")]
		cidr=sum((bin(x).count('1') for x in mask))

		print("")
		print("Network address:",func_subnetcalculator(ipaddr)[0])
		print("")
		print("First host:",func_subnetcalculator(ipaddr)[3])
		print("Last host:",func_subnetcalculator(ipaddr)[4])
		print("")
		print("Broadcast:",func_subnetcalculator(ipaddr)[5])
		print("")
		print("Number of hosts:",func_subnetcalculator(ipaddr)[2])
		exit(0)

	elif len(sys.argv)==4:
		ipaddr=(sys.argv[2])+" "+(sys.argv[3])
		print("Initial value:",ipaddr)

		mask=str(func_subnetcalculator(ipaddr)[1])
		mask=[int(x) for x in mask.split(".")]
		cidr=sum((bin(x).count('1') for x in mask))

		print("CIDR:", cidr)

		print("")
		print("Network address:",func_subnetcalculator(ipaddr)[0])
		print("")
		print("First host:",func_subnetcalculator(ipaddr)[3])
		print("Last host:",func_subnetcalculator(ipaddr)[4])
		print("")
		print("Broadcast:",func_subnetcalculator(ipaddr)[5])
		print("")
		print("Number of hosts:",func_subnetcalculator(ipaddr)[2])
		exit(0)

	elif len(sys.argv)==5:
		print("\033[0;31mOnly two argument is expected.\033[00m")
		exit(1)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

def func_advancedsubnetcalculator(x,y):
	
	if " " in x:
		(addr, mask)=x.split(" ")
		mask=[int(x) for x in mask.split(".")]
		cidr=sum((bin(x).count('1') for x in mask))
		ipaddr=str(addr)+"/"+str(cidr)
		ipaddr=ipaddress.ip_network(ipaddr, strict=False)

	elif "/" in x:
		ipaddr=ipaddress.ip_network(x, strict=False)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

	mask=ipaddr.netmask
	size=ipaddr.num_addresses-2
	firstHost=ipaddr[1]
	lastHost=ipaddr[size]
	br=ipaddr.broadcast_address

	subnets=[]
	for subnet in ipaddr.subnets(new_prefix=int(y)):
		subnets.append(subnet)

	sn=len(subnets)

	return ipaddr,mask,size,firstHost,lastHost,br,sn,subnets

def advancedsubnetcalculator():
	if len(sys.argv)==2:
		ipaddr=input("Enter an IP address, a CIDR and the new CIDR: ")

		(addr,cidr)=ipaddr.split("/")
		(addr,newcidr)=ipaddr.split(" ")

		print("Initial value:",str(addr))
		print("")
		print("Original network address:",func_advancedsubnetcalculator(addr,newcidr)[0])
		print("New CIDR:",newcidr)
		print("")
		print("First host:",func_advancedsubnetcalculator(addr,newcidr)[3])
		print("Last host:",func_advancedsubnetcalculator(addr,newcidr)[4])
		print("Broadcast:",func_advancedsubnetcalculator(addr,newcidr)[5])
		print("Number of hosts:",func_advancedsubnetcalculator(addr,newcidr)[2])
		print("")
		print("Number of subnets:",func_advancedsubnetcalculator(addr,newcidr)[6])
		sn=func_advancedsubnetcalculator(addr,newcidr)[7]
		print("List of subnets:",*sn)
		exit(0)

	elif len(sys.argv)==3:
		print("\033[0;31mTwo arguments are expected.\033[00m")
		exit(1)

	elif len(sys.argv)==4:
		ipaddr=(sys.argv[2])+" "+(sys.argv[3])

		(addr,cidr)=ipaddr.split("/")
		(addr,newcidr)=ipaddr.split(" ")

		print("Initial value:",str(addr))
		print("")
		print("Original network address:",func_advancedsubnetcalculator(addr,newcidr)[0])
		print("New CIDR:",newcidr)
		print("")
		print("First host:",func_advancedsubnetcalculator(addr,newcidr)[3])
		print("Last host:",func_advancedsubnetcalculator(addr,newcidr)[4])
		print("Broadcast:",func_advancedsubnetcalculator(addr,newcidr)[5])
		print("Number of hosts:",func_advancedsubnetcalculator(addr,newcidr)[2])
		print("")
		print("Number of subnets:",func_advancedsubnetcalculator(addr,newcidr)[6])
		sn=func_advancedsubnetcalculator(addr,newcidr)[7]
		print("List of subnets:",*sn)
		exit(0)

	else:
		print("\033[0;31mAn unexpected error was caused.\033[00m")
		exit(1)

if __name__ == '__main__':
	Check_UserInput()
