import sys
from sys import exit
from sys import argv
import os
from os import system
import ctypes
from ast import If
from ipaddress import IPv4Address

def Check_UserInput():

    if len(sys.argv)==1:
        usage()
    elif str(sys.argv[1])=="--help":
        usage()
    elif str(sys.argv[1])=="-help":
        usage()
    elif str(sys.argv[1])=="--h":
        usage()
    elif str(sys.argv[1])=="-h":
        usage()
    elif str(sys.argv[1])=="/help":
        usage()
    elif str(sys.argv[1])=="/h":
        usage()

    elif str(sys.argv[1])=="--usage":
        usage()
    elif str(sys.argv[1])=="-usage":
        usage()
    elif str(sys.argv[1])=="--u":
        usage()
    elif str(sys.argv[1])=="-u":
        usage()
    elif str(sys.argv[1])=="/usage":
        usage()
    elif str(sys.argv[1])=="/u":
        usage()

    elif str(sys.argv[1])=="--interactive":
        main()
    elif str(sys.argv[1])=="-interactive":
        main()
    elif str(sys.argv[1])=="--i":
        main()
    elif str(sys.argv[1])=="-i":
        main()
    elif str(sys.argv[1])=="/interactive":
        usage()
    elif str(sys.argv[1])=="/i":
        usage()

    elif str(sys.argv[1])=="--ipmasktobin":
        ipAddrAndMasktobin()
    elif str(sys.argv[1])=="--ipmask2bin":
        ipAddrAndMasktobin()
    elif str(sys.argv[1])=="--ipm2b":
        ipAddrAndMasktobin()
    elif str(sys.argv[1])=="-ipmasktobin":
        ipAddrAndMasktobin()
    elif str(sys.argv[1])=="-ipmask2bin":
        ipAddrAndMasktobin()
    elif str(sys.argv[1])=="-ipm2b":
        ipAddrAndMasktobin()
    elif str(sys.argv[1])=="/ipmasktobin":
        ipAddrAndMasktobin()
    elif str(sys.argv[1])=="/ipmask2bin":
        ipAddrAndMasktobin()
    elif str(sys.argv[1])=="/ipm2b":
        ipAddrAndMasktobin()

    elif str(sys.argv[1])=="--iptobin":
        iptobin()
    elif str(sys.argv[1])=="--ip2bin":
        iptobin()
    elif str(sys.argv[1])=="--i2b":
        iptobin()
    elif str(sys.argv[1])=="-iptobin":
        iptobin()
    elif str(sys.argv[1])=="-ip2bin":
        iptobin()
    elif str(sys.argv[1])=="-i2b":
        iptobin()
    elif str(sys.argv[1])=="/iptobin":
        iptobin()
    elif str(sys.argv[1])=="/ip2bin":
        iptobin()
    elif str(sys.argv[1])=="/i2b":
        iptobin()

    elif str(sys.argv[1])=="--bintoip":
        bintoip()
    elif str(sys.argv[1])=="--bin2ip":
        bintoip()
    elif str(sys.argv[1])=="--b2i":
        bintoip()
    elif str(sys.argv[1])=="-bintoip":
        bintoip()
    elif str(sys.argv[1])=="-bin2ip":
        bintoip()
    elif str(sys.argv[1])=="-b2i":
        bintoip()
    elif str(sys.argv[1])=="/bintoip":
        bintoip()
    elif str(sys.argv[1])=="/bin2ip":
        bintoip()
    elif str(sys.argv[1])=="/b2i":
        bintoip()

    elif str(sys.argv[1])=="--dectobin":
        dectobin()
    elif str(sys.argv[1])=="--dec2bin":
        dectobin()
    elif str(sys.argv[1])=="--d2b":
        dectobin()
    elif str(sys.argv[1])=="-dectobin":
        dectobin()
    elif str(sys.argv[1])=="-dec2bin":
        dectobin()
    elif str(sys.argv[1])=="-d2b":
        dectobin()
    elif str(sys.argv[1])=="/dectobin":
        dectobin()
    elif str(sys.argv[1])=="/dec2bin":
        dectobin()
    elif str(sys.argv[1])=="/d2b":
        dectobin()

    elif str(sys.argv[1])=="--bintodec":
        bintodec()
    elif str(sys.argv[1])=="--bin2dec":
        bintodec()
    elif str(sys.argv[1])=="--b2d":
        bintodec()
    elif str(sys.argv[1])=="-bintodec":
        bintodec()
    elif str(sys.argv[1])=="-bin2dec":
        bintodec()
    elif str(sys.argv[1])=="-b2d":
        bintodec()
    elif str(sys.argv[1])=="/bintodec":
        bintodec()
    elif str(sys.argv[1])=="/bin2dec":
        bintodec()
    elif str(sys.argv[1])=="/b2d":
        bintodec()

    elif str(sys.argv[1])=="--dectohex":
        dectohex()
    elif str(sys.argv[1])=="--dec2hex":
        dectohex()
    elif str(sys.argv[1])=="--d2h":
        dectohex()
    elif str(sys.argv[1])=="-dectohex":
        dectohex()
    elif str(sys.argv[1])=="-dec2hex":
        dectohex()
    elif str(sys.argv[1])=="-d2h":
        dectohex()
    elif str(sys.argv[1])=="/dectohex":
        dectohex()
    elif str(sys.argv[1])=="/dec2hex":
        dectohex()
    elif str(sys.argv[1])=="/d2h":
        dectohex()

    elif str(sys.argv[1])=="--hextodec":
        hextodec()
    elif str(sys.argv[1])=="--hex2dec":
        hextodec()
    elif str(sys.argv[1])=="--h2d":
        hextodec()
    elif str(sys.argv[1])=="-hextodec":
        hextodec()
    elif str(sys.argv[1])=="-hex2dec":
        hextodec()
    elif str(sys.argv[1])=="-h2d":
        hextodec()
    elif str(sys.argv[1])=="/hextodec":
        hextodec()
    elif str(sys.argv[1])=="/hex2dec":
        hextodec()
    elif str(sys.argv[1])=="/h2d":
        hextodec()

    elif str(sys.argv[1])=="--masktocidr":
        masktocidr()
    elif str(sys.argv[1])=="--mask2cidr":
        masktocidr()
    elif str(sys.argv[1])=="--m2c":
        masktocidr()
    elif str(sys.argv[1])=="-masktocidr":
        masktocidr()
    elif str(sys.argv[1])=="-mask2cidr":
        masktocidr()
    elif str(sys.argv[1])=="-m2c":
        masktocidr()
    elif str(sys.argv[1])=="/masktocidr":
        masktocidr()
    elif str(sys.argv[1])=="/mask2cidr":
        masktocidr()
    elif str(sys.argv[1])=="/m2c":
        masktocidr()

    elif str(sys.argv[1])=="--cidrtomask":
        cidrtomask()
    elif str(sys.argv[1])=="--cidr2mask":
        cidrtomask()
    elif str(sys.argv[1])=="--c2m":
        cidrtomask()
    elif str(sys.argv[1])=="-cidrtomask":
        cidrtomask()
    elif str(sys.argv[1])=="-cidr2mask":
        cidrtomask()
    elif str(sys.argv[1])=="-c2m":
        cidrtomask()
    elif str(sys.argv[1])=="/cidrtomask":
        cidrtomask()
    elif str(sys.argv[1])=="/cidr2mask":
        cidrtomask()
    elif str(sys.argv[1])=="/c2m":
        cidrtomask()

    elif str(sys.argv[1])=="--masktowildcard":
        masktowildcard()
    elif str(sys.argv[1])=="--mask2wildcard":
        masktowildcard()
    elif str(sys.argv[1])=="--m2w":
        masktowildcard()
    elif str(sys.argv[1])=="-masktowildcard":
        masktowildcard()
    elif str(sys.argv[1])=="-mask2wildcard":
        masktowildcard()
    elif str(sys.argv[1])=="-m2w":
        masktowildcard()
    elif str(sys.argv[1])=="/masktowildcard":
        masktowildcard()
    elif str(sys.argv[1])=="/mask2wildcard":
        masktowildcard()
    elif str(sys.argv[1])=="/m2w":
        masktowildcard()

    elif str(sys.argv[1])=="--wildcardtomask":
        wildcardtomask()
    elif str(sys.argv[1])=="--wildcard2mask":
        wildcardtomask()
    elif str(sys.argv[1])=="--w2m":
        wildcardtomask()
    elif str(sys.argv[1])=="-wildcardtomask":
        wildcardtomask()
    elif str(sys.argv[1])=="-wildcard2mask":
        wildcardtomask()
    elif str(sys.argv[1])=="-w2m":
        wildcardtomask()
    elif str(sys.argv[1])=="/wildcardtomask":
        wildcardtomask()
    elif str(sys.argv[1])=="/wildcard2mask":
        wildcardtomask()
    elif str(sys.argv[1])=="/w2m":
        wildcardtomask()

    elif str(sys.argv[1])=="--cidrtowildcard":
        cidrtowildcard()
    elif str(sys.argv[1])=="--cidr2wildcard":
        cidrtowildcard()
    elif str(sys.argv[1])=="--c2w":
        cidrtowildcard()
    elif str(sys.argv[1])=="-cidrtowildcard":
        cidrtowildcard()
    elif str(sys.argv[1])=="-cidr2wildcard":
        cidrtowildcard()
    elif str(sys.argv[1])=="-c2w":
        cidrtowildcard()
    elif str(sys.argv[1])=="/cidrtowildcard":
        cidrtowildcard()
    elif str(sys.argv[1])=="/cidr2wildcard":
        cidrtowildcard()
    elif str(sys.argv[1])=="/c2w":
        cidrtowildcard()

    elif str(sys.argv[1])=="--wildcardtocidr":
        wildcardtocidr()
    elif str(sys.argv[1])=="--wildcard2cidr":
        wildcardtocidr()
    elif str(sys.argv[1])=="--w2c":
        wildcardtocidr()
    elif str(sys.argv[1])=="-wildcardtocidr":
        wildcardtocidr()
    elif str(sys.argv[1])=="-wildcard2cidr":
        wildcardtocidr()
    elif str(sys.argv[1])=="-w2c":
        wildcardtocidr()
    elif str(sys.argv[1])=="/wildcardtocidr":
        wildcardtocidr()
    elif str(sys.argv[1])=="/wildcard2cidr":
        wildcardtocidr()
    elif str(sys.argv[1])=="/w2c":
        wildcardtocidr()
    
    else:
        print("\033[0;31mAn unexpected error was caused.\033[00m")
        exit(1)

def usage():
    print("Usage: python3 main.py OPTION")
    print("")
    print("OPTIONS:")
    print("     --help, --usage, -h: display this help message.")
    print("     -i, --i: interactive mode.")
    print("")
    print("ARGS:")
    print("     --ipmasktobin IP/CIDR: convert an IP address and its mask (or CIDR) into a binary number.")
    print("")    
    print("     --iptobin IP: convert an IP address to a binary number.")
    print("     --bintoip binary-number: convert an IP address in binary format to decimal format.")
    print("")
    print("     --dectobin decimal-number: convert a decimal number into a binary number.")
    print("     --bintodec binary-number: convert a binary number into a decimal number.")
    print("")
    print("     --dectohex decimal-number: convert a decimal number into a hexadecimal number.")
    print("     --hextodec hexa_number: convert a hexadecimal number into a decimal number.")
    print("")
    print("     --masktocidr mask: calculate the CIDR of a mask.")
    print("     --cidrtomask CIDR: calculate the mask from a CIDR.")
    print("")
    print("     --masktowildcard mask: convert a mask to wildcard mask.")
    print("     --wildcardtomask wildcard_mask: convert a wildcard mask to a mask.")
    print("")
    print("     --cidrtowildcard mask: convert a mask to wildcard mask.")
    print("     --wildcardtocidr wildcard_mask: convert a wildcard mask to a mask.")
    print("")
    print("EXAMPLES:")
    print("     python3 ./main.py --ipmasktobin 192.168.1.42/16")
    print("     python3 ./main.py --dectobin 42")
    exit(0)

def clear():
    os.system("cls" if os.name=="nt" else "clear")

def dectobin():

    if len(sys.argv)==2:
        dec_value=input("Enter a decimal number: ")
        dec_value=int(dec_value)
        bin_value=bin(dec_value)[2:]
        bin_complement_value=format(dec_value, '#010b')[2:]

        print("")
        print("Initial value (decimal):",dec_value)
        print("Binary value:",bin_value)
        print("Signed binary number value:",bin_complement_value)
        exit(0)
    
    elif len(sys.argv)==3:
        dec_value=int(sys.argv[2])
        dec_value=int(dec_value)
        bin_value=bin(dec_value)[2:]
        bin_complement_value=format(dec_value, '#010b')[2:]

        print("Initial value (decimal):",dec_value)
        print("Binary value:",bin_value)
        print("Signed binary number value:",bin_complement_value)
        exit(0)

    elif len(sys.argv)>=4:
        print("\033[0;31mOnly one argument is expected.\033[00m")
        exit(1)

    else:
        print("\033[0;31mAn unexpected error was caused.\033[00m")
        exit(1)

def bintodec():

    if len(sys.argv)==2:
        bin_value=input("Enter a binary number: ")
        new_bin_value="0b"+bin_value
        dec_value=int(new_bin_value, 2)

        print("")
        print("Initial value (binary):",bin_value)
        print("Decimal value:",dec_value)
        exit(0)
    
    elif len(sys.argv)==3:
        bin_value=(sys.argv[2])
        new_bin_value="0b"+bin_value
        dec_value=int(new_bin_value, 2)

        print("Initial value (binary):",bin_value)
        print("Decimal value:",dec_value)
        exit(0)

    elif len(sys.argv)>=4:
        print("\033[0;31mOnly one argument is expected.\033[00m")
        exit(1)

    else:
        print("\033[0;31mAn unexpected error was caused.\033[00m")
        exit(1)

def dectohex():

    if len(sys.argv)==2:
        dec_value=input("Enter a decimal number: ")
        dec_value=int(dec_value)
        hex_value=hex(dec_value)[2:]

        print("")
        print("Initial value (decimal):",dec_value)
        print("Hexadecimal value:",hex_value)
        exit(0)
    
    elif len(sys.argv)==3:
        dec_value=int(sys.argv[2])
        dec_value=int(dec_value)
        hex_value=hex(dec_value)[2:]

        print("Initial value (decimal):",dec_value)
        print("Hexadecimal value:",hex_value)
        exit(0)

    elif len(sys.argv)>=4:
        print("\033[0;31mOnly one argument is expected.\033[00m")
        exit(1)

    else:
        print("\033[0;31mAn unexpected error was caused.\033[00m")
        exit(1)

def hextodec():

    if len(sys.argv)==2:
        hex_value=input("Enter a hexadecimal number: ")
        new_hex_value="0x"+hex_value
        dec_value=int(new_hex_value, 16)

        print("")
        print("Initial value (hexadecimal):",hex_value)
        print("Decimal value:",dec_value)
        exit(0)
    
    elif len(sys.argv)==3:
        hex_value=(sys.argv[2])
        new_hex_value="0x"+hex_value
        dec_value=int(new_hex_value, 16)

        print("Initial value (hexa):",hex_value)
        print("Decimal value:",dec_value)
        exit(0)

    elif len(sys.argv)>=4:
        print("\033[0;31mOnly one argument is expected.\033[00m")
        exit(1)

    else:
        print("\033[0;31mAn unexpected error was caused.\033[00m")
        exit(1)

def iptobin():

    if len(sys.argv)==2:
        ip=input("Enter an IP address: ")
        addr=[0,0,0,0]
        addr=ip
        addr=[int(x) for x in addr.split(".")]

        if len(addr)>4 or len(addr)<4:
            print("\033[0;31mAn IP address can only be encoded on four bytes.\033[00m")
            exit(1)
    
        First_Byte_dec=addr[0]
        Second_Byte_dec=addr[1]
        Third_Octet_dec=addr[2]
        Fourth_Octet_dec=addr[3]
    
        First_Byte_bin=bin(First_Byte_dec)[2:]
        Second_Byte_bin=bin(Second_Byte_dec)[2:]
        Third_Octet_bin=bin(Third_Octet_dec)[2:]
        Fourth_Octet_bin=bin(Fourth_Octet_dec)[2:]
    
        final_bin_value=First_Byte_bin+"."+Second_Byte_bin+"."+Third_Octet_bin+"."+Fourth_Octet_bin
    
        First_Byte_bin_complement=format(First_Byte_dec,'#010b')[2:]
        Second_Byte_bin_complement=format(Second_Byte_dec,'#010b')[2:]
        Third_Octet_bin_complement=format(Third_Octet_dec,'#010b')[2:]
        Fourth_Octet_bin_complement=format(Fourth_Octet_dec,'#010b')[2:]
    
        final_bin_complement_value=First_Byte_bin_complement+"."+Second_Byte_bin_complement+"."+Third_Octet_bin_complement+"."+Fourth_Octet_bin_complement

        print("")
        print("Initial value (IP address in decimal):",ip)
        print("IP address in binary format:",final_bin_value)
        print("Signed binary number value:",final_bin_complement_value)
        exit(0)

    elif len(sys.argv)==3:
        ip=(sys.argv[2])
        addr=[0,0,0,0]
        addr=ip
        addr=[int(x) for x in addr.split(".")]

        if len(addr)>4 or len(addr)<4:
            print("\033[0;31mAn IP address can only be encoded on four bytes.\033[00m")
            exit(1)
    
        First_Byte_dec=addr[0]
        Second_Byte_dec=addr[1]
        Third_Octet_dec=addr[2]
        Fourth_Octet_dec=addr[3]
    
        First_Byte_bin=bin(First_Byte_dec)[2:]
        Second_Byte_bin=bin(Second_Byte_dec)[2:]
        Third_Octet_bin=bin(Third_Octet_dec)[2:]
        Fourth_Octet_bin=bin(Fourth_Octet_dec)[2:]
    
        final_bin_value=First_Byte_bin+"."+Second_Byte_bin+"."+Third_Octet_bin+"."+Fourth_Octet_bin
    
        First_Byte_bin_complement=format(First_Byte_dec,'#010b')[2:]
        Second_Byte_bin_complement=format(Second_Byte_dec,'#010b')[2:]
        Third_Octet_bin_complement=format(Third_Octet_dec,'#010b')[2:]
        Fourth_Octet_bin_complement=format(Fourth_Octet_dec,'#010b')[2:]
    
        final_bin_complement_value=First_Byte_bin_complement+"."+Second_Byte_bin_complement+"."+Third_Octet_bin_complement+"."+Fourth_Octet_bin_complement

        print("Initial value (IP address in decimal):",ip)
        print("IP address in binary format:",final_bin_value)
        print("Signed binary number value:",final_bin_complement_value)
        exit(0)

    elif len(sys.argv)>=4:
        print("\033[0;31mOnly one argument is expected.\033[00m")
        exit(1)

    else:
        print("\033[0;31mAn unexpected error was caused.\033[00m")
        exit(1)

def bintoip():

    if len(sys.argv)==2:
        ip=input("Enter an IP address in binary format: ")

        Test_Value=ip
        Test_Value=[str(x) for x in Test_Value.split(" ")]
        if len(Test_Value)>=2:
            print("\033[0;31mAn IP address, whether in binary or decimal, cannot contain spaces.\033[00m")
            exit(1)

        addr=[0,0,0,0]
        addr=ip
        addr=[int(x) for x in addr.split(".")]

        if len(addr)>4 or len(addr)<4:
            print("\033[0;31mAn IP address can only be encoded on four bytes.\033[00m")
            exit(1)
    
        First_Byte_bin=addr[0]
        New_First_Byte_bin="0b"+str(First_Byte_bin)
        First_Byte_dec=int(New_First_Byte_bin, 2)

        Second_Byte_bin=addr[1]
        New_Second_Byte_bin="0b"+str(Second_Byte_bin)
        Second_Byte_dec=int(New_Second_Byte_bin, 2)

        Third_Octet_bin=addr[2]
        New_Third_Octet_bin="0b"+str(Third_Octet_bin)
        Third_Octet_dec=int(New_Third_Octet_bin, 2)

        Fourth_Octet_bin=addr[3]
        New_Fourth_Octet_bin="0b"+str(Fourth_Octet_bin)
        Fourth_Octet_dec=int(New_Fourth_Octet_bin, 2)
    
        final_dec_value=str(First_Byte_dec)+"."+str(Second_Byte_dec)+"."+str(Third_Octet_dec)+"."+str(Fourth_Octet_dec)

        print("")
        print("Initial value (IP address in binary format):",ip)
        print("IP address in decimal format:",final_dec_value)

    elif len(sys.argv)==3:
        ip=(sys.argv[2])
        addr=[0,0,0,0]
        addr=ip
        addr=[int(x) for x in addr.split(".")]

        if len(addr)>4 or len(addr)<4:
            print("\033[0;31mAn IP address can only be encoded on four bytes.\033[00m")
            exit(1)
    
        First_Byte_bin=addr[0]
        New_First_Byte_bin="0b"+str(First_Byte_bin)
        First_Byte_dec=int(New_First_Byte_bin, 2)

        Second_Byte_bin=addr[1]
        New_Second_Byte_bin="0b"+str(Second_Byte_bin)
        Second_Byte_dec=int(New_Second_Byte_bin, 2)

        Third_Octet_bin=addr[2]
        New_Third_Octet_bin="0b"+str(Third_Octet_bin)
        Third_Octet_dec=int(New_Third_Octet_bin, 2)

        Fourth_Octet_bin=addr[3]
        New_Fourth_Octet_bin="0b"+str(Fourth_Octet_bin)
        Fourth_Octet_dec=int(New_Fourth_Octet_bin, 2)
    
        final_dec_value=str(First_Byte_dec)+"."+str(Second_Byte_dec)+"."+str(Third_Octet_dec)+"."+str(Fourth_Octet_dec)

        print("Initial value (IP address in binary format):",ip)
        print("IP address in decimal format:",final_dec_value)

    elif len(sys.argv)>=4:
        print("\033[0;31mOnly one argument is expected.\033[00m")
        exit(1)

    else:
        print("\033[0;31mAn unexpected error was caused.\033[00m")
        exit(1)

def ipAddrAndMasktobin():

        if len(sys.argv)==2:
            ipAddrAndMask=input("Enter an IP address followed by a mask or a /CIDR (IP MASK or IP/CIDR): ")
        
            addr=[0,0,0,0]
            addr=ipAddrAndMask
            cidr=0

            if "/" in ipAddrAndMask:
                (addr,cidr)=ipAddrAndMask.split('/')

                addr=[int(x) for x in addr.split(".")]
                cidr=int(cidr)
                mask=[(((1<<32)-1)<<(32-cidr)>>i)&255 for i in reversed(range(0,32,8))]
            
            elif " " in ipAddrAndMask:
                (addr, mask)=ipAddrAndMask.split(' ')

                addr=[int(x) for x in addr.split(".")]
                mask=[int(x) for x in mask.split(".")]
                cidr=sum((bin(x).count('1') for x in mask))
   
            else:
                print("\033[0;31mInvalid arguments have been detected.\033[00m")
                print("")
                print("Example of a valid argument expected: <ip/cidr>")
                print("Example of a valid argument expected: <ip> <mask>")
                exit(1)

            First_Addr_Byte_dec=addr[0]
            Second_Addr_Byte_dec=addr[1]
            Third_Addr_Byte_dec=addr[2]
            Fourth_Addr_Byte_dec=addr[3]
            
            First_Addr_Byte_bin=bin(First_Addr_Byte_dec)[2:]
            Second_Addr_Byte_bin=bin(Second_Addr_Byte_dec)[2:]
            Third_Addr_Byte_bin=bin(Third_Addr_Byte_dec)[2:]
            Fourth_Addr_Byte_bin=bin(Fourth_Addr_Byte_dec)[2:]
            
            final_addr_bin_value=First_Addr_Byte_bin+"."+Second_Addr_Byte_bin+"."+Third_Addr_Byte_bin+"."+Fourth_Addr_Byte_bin
            
            First_Addr_Byte_bin_complement=format(First_Addr_Byte_dec, '#010b')[2:]
            Second_Addr_Byte_bin_complement=format(Second_Addr_Byte_dec, '#010b')[2:]
            Third_Addr_Byte_bin_complement=format(Third_Addr_Byte_dec, '#010b')[2:]
            Fourth_Addr_Byte_bin_complement=format(Fourth_Addr_Byte_dec, '#010b')[2:]
            
            final_addr_bin_complement_value=First_Addr_Byte_bin_complement+"."+Second_Addr_Byte_bin_complement+"."+Third_Addr_Byte_bin_complement+"."+Fourth_Addr_Byte_bin_complement
        
            First_Mask_Byte_dec=mask[0]
            Second_Mask_Byte_dec=mask[1]
            Third_Mask_Byte_dec=mask[2]
            Fourth_Mask_Byte_dec=mask[3]
            
            First_Mask_Byte_bin=bin(First_Mask_Byte_dec)[2:]
            Second_Mask_Byte_bin=bin(Second_Mask_Byte_dec)[2:]
            Third_Mask_Byte_bin=bin(Third_Mask_Byte_dec)[2:]
            Fourth_Mask_Byte_bin=bin(Fourth_Mask_Byte_dec)[2:]
            
            final_mask_bin_value=First_Mask_Byte_bin+"."+Second_Mask_Byte_bin+"."+Third_Mask_Byte_bin+"."+Fourth_Mask_Byte_bin
            
            First_Mask_Byte_bin_complement=format(First_Mask_Byte_dec, '#010b')[2:]
            Second_Mask_Byte_bin_complement=format(Second_Mask_Byte_dec, '#010b')[2:]
            Third_Mask_Byte_bin_complement=format(Third_Mask_Byte_dec, '#010b')[2:]
            Fourth_Mask_Byte_bin_complement=format(Fourth_Mask_Byte_dec, '#010b')[2:]
            
            final_mask_bin_complement_value=First_Mask_Byte_bin_complement+"."+Second_Mask_Byte_bin_complement+"."+Third_Mask_Byte_bin_complement+"."+Fourth_Mask_Byte_bin_complement
        
            print("")
            print("Initial value (IP address and mask in decimal format):",ipAddrAndMask)
            print("IP address in binary format:",final_addr_bin_value)
            print("Mask in binary format:",final_mask_bin_value)
            print("")
            print("Signed binary IP address number value:",final_addr_bin_complement_value)
            print("Signed binary mask number value:",final_mask_bin_complement_value)
            exit(0)

        elif len(sys.argv)==3:

            ipAddrAndCIDR=(sys.argv[2])
        
            addr=[0,0,0,0]
            addr=ipAddrAndCIDR
            cidr=0

            if "/" in addr:
                (addr,cidr)=addr.split('/')
                addr=[int(x) for x in addr.split(".")]
                cidr=int(cidr)
                mask=[(((1<<32)-1)<<(32-cidr)>>i)&255 for i in reversed(range(0,32,8))]

            elif not "/" in addr:
                print("\033[0;31mInvalid arguments have been detected.\033[00m")
                print("")
                print("Example of a valid argument expected: <ip/cidr>")
                print("Example of a valid argument expected: <ip> <mask>")
                exit(1)

            else:
                print("\033[0;31mAn unexpected error was caused.\033[00m")
                exit(1)

            First_Addr_Byte_dec=addr[0]
            Second_Addr_Byte_dec=addr[1]
            Third_Addr_Byte_dec=addr[2]
            Fourth_Addr_Byte_dec=addr[3]
            
            First_Addr_Byte_bin=bin(First_Addr_Byte_dec)[2:]
            Second_Addr_Byte_bin=bin(Second_Addr_Byte_dec)[2:]
            Third_Addr_Byte_bin=bin(Third_Addr_Byte_dec)[2:]
            Fourth_Addr_Byte_bin=bin(Fourth_Addr_Byte_dec)[2:]
            
            final_addr_bin_value=First_Addr_Byte_bin+"."+Second_Addr_Byte_bin+"."+Third_Addr_Byte_bin+"."+Fourth_Addr_Byte_bin
            
            First_Addr_Byte_bin_complement=format(First_Addr_Byte_dec, '#010b')[2:]
            Second_Addr_Byte_bin_complement=format(Second_Addr_Byte_dec, '#010b')[2:]
            Third_Addr_Byte_bin_complement=format(Third_Addr_Byte_dec, '#010b')[2:]
            Fourth_Addr_Byte_bin_complement=format(Fourth_Addr_Byte_dec, '#010b')[2:]
            
            final_addr_bin_complement_value=First_Addr_Byte_bin_complement+"."+Second_Addr_Byte_bin_complement+"."+Third_Addr_Byte_bin_complement+"."+Fourth_Addr_Byte_bin_complement
        
            First_Mask_Byte_dec=mask[0]
            Second_Mask_Byte_dec=mask[1]
            Third_Mask_Byte_dec=mask[2]
            Fourth_Mask_Byte_dec=mask[3]
            
            First_Mask_Byte_bin=bin(First_Mask_Byte_dec)[2:]
            Second_Mask_Byte_bin=bin(Second_Mask_Byte_dec)[2:]
            Third_Mask_Byte_bin=bin(Third_Mask_Byte_dec)[2:]
            Fourth_Mask_Byte_bin=bin(Fourth_Mask_Byte_dec)[2:]
            
            final_mask_bin_value=First_Mask_Byte_bin+"."+Second_Mask_Byte_bin+"."+Third_Mask_Byte_bin+"."+Fourth_Mask_Byte_bin
            
            First_Mask_Byte_bin_complement=format(First_Mask_Byte_dec, '#010b')[2:]
            Second_Mask_Byte_bin_complement=format(Second_Mask_Byte_dec, '#010b')[2:]
            Third_Mask_Byte_bin_complement=format(Third_Mask_Byte_dec, '#010b')[2:]
            Fourth_Mask_Byte_bin_complement=format(Fourth_Mask_Byte_dec, '#010b')[2:]
            
            final_mask_bin_complement_value=First_Mask_Byte_bin_complement+"."+Second_Mask_Byte_bin_complement+"."+Third_Mask_Byte_bin_complement+"."+Fourth_Mask_Byte_bin_complement
        
            print("")
            print("Initial value (IP address and mask in decimal format):",ipAddrAndCIDR)
            print("IP address in binary format:",final_addr_bin_value)
            print("Mask in binary format:",final_mask_bin_value)
            print("")
            print("Signed binary IP address number value:",final_addr_bin_complement_value)
            print("Signed binary mask number value:",final_mask_bin_complement_value)
            exit(0)

        elif len(sys.argv)==4:

            addr=(sys.argv[2])
            mask=(sys.argv[3])
        
            IpAddr=[0,0,0,0]
            IpAddr=addr

            MaskAddr=[0,0,0,0]
            MaskAddr=mask

            cidr=0

            IpAddr=[int(x) for x in IpAddr.split(".")]
            MaskAddr= [int(x) for x in MaskAddr.split(".")]
            cidr=sum((bin(x).count('1') for x in MaskAddr))

            if len(IpAddr)>4 or len(IpAddr)<4:
                print("\033[0;31mAn IP address can only be encoded on four bytes.\033[00m")
                exit(1)

            elif len(MaskAddr)>4 or len(MaskAddr)<4:
                print("\033[0;31mA mask can only be coded on four bytes.\033[00m")
                exit(1)

            First_Addr_Byte_dec=IpAddr[0]
            Second_Addr_Byte_dec=IpAddr[1]
            Third_Addr_Byte_dec=IpAddr[2]
            Fourth_Addr_Byte_dec=IpAddr[3]
            
            First_Addr_Byte_bin=bin(First_Addr_Byte_dec)[2:]
            Second_Addr_Byte_bin=bin(Second_Addr_Byte_dec)[2:]
            Third_Addr_Byte_bin=bin(Third_Addr_Byte_dec)[2:]
            Fourth_Addr_Byte_bin=bin(Fourth_Addr_Byte_dec)[2:]
            
            final_addr_bin_value=First_Addr_Byte_bin+"."+Second_Addr_Byte_bin+"."+Third_Addr_Byte_bin+"."+Fourth_Addr_Byte_bin
            
            First_Addr_Byte_bin_complement=format(First_Addr_Byte_dec, '#010b')[2:]
            Second_Addr_Byte_bin_complement=format(Second_Addr_Byte_dec, '#010b')[2:]
            Third_Addr_Byte_bin_complement=format(Third_Addr_Byte_dec, '#010b')[2:]
            Fourth_Addr_Byte_bin_complement=format(Fourth_Addr_Byte_dec, '#010b')[2:]
            
            final_addr_bin_complement_value=First_Addr_Byte_bin_complement+"."+Second_Addr_Byte_bin_complement+"."+Third_Addr_Byte_bin_complement+"."+Fourth_Addr_Byte_bin_complement
        
            First_Mask_Byte_dec=MaskAddr[0]
            Second_Mask_Byte_dec=MaskAddr[1]
            Third_Mask_Byte_dec=MaskAddr[2]
            Fourth_Mask_Byte_dec=MaskAddr[3]
            
            First_Mask_Byte_bin=bin(First_Mask_Byte_dec)[2:]
            Second_Mask_Byte_bin=bin(Second_Mask_Byte_dec)[2:]
            Third_Mask_Byte_bin=bin(Third_Mask_Byte_dec)[2:]
            Fourth_Mask_Byte_bin=bin(Fourth_Mask_Byte_dec)[2:]
            
            final_mask_bin_value=First_Mask_Byte_bin+"."+Second_Mask_Byte_bin+"."+Third_Mask_Byte_bin+"."+Fourth_Mask_Byte_bin
            
            First_Mask_Byte_bin_complement=format(First_Mask_Byte_dec, '#010b')[2:]
            Second_Mask_Byte_bin_complement=format(Second_Mask_Byte_dec, '#010b')[2:]
            Third_Mask_Byte_bin_complement=format(Third_Mask_Byte_dec, '#010b')[2:]
            Fourth_Mask_Byte_bin_complement=format(Fourth_Mask_Byte_dec, '#010b')[2:]
            
            final_mask_bin_complement_value=First_Mask_Byte_bin_complement+"."+Second_Mask_Byte_bin_complement+"."+Third_Mask_Byte_bin_complement+"."+Fourth_Mask_Byte_bin_complement
        
            print("Initial value (IP address in decimal format):",addr)
            print("Initial value (Mask in decimal format):",mask)
            SlideCidr="/"+str(cidr)
            print("CIDR:",SlideCidr)
            print("")
            print("IP address in binary format:",final_addr_bin_value)
            print("Mask in binary format:",final_mask_bin_value)
            print("")
            print("Signed binary IP address number value:",final_addr_bin_complement_value)
            print("Signed binary mask number value:",final_mask_bin_complement_value)
            exit(0)

        elif len(sys.argv)>=5:
            print("\033[0;31mInvalid arguments have been detected.\033[00m")
            print("")
            print("Example of a valid argument expected: <ip/cidr>")
            print("Example of a valid argument expected: <ip> <mask>")
            exit(1)

        else:
            print("\033[0;31mAn unexpected error was caused.\033[00m")
            exit(1)

def masktocidr():

    if len(sys.argv)==2:
        mask=input("Enter a mask: ")

        MaskAddr=[0,0,0,0]
        MaskAddr=mask
        cidr=0
        MaskAddr=[int(x) for x in MaskAddr.split(".")]
        cidr=sum((bin(x).count('1') for x in MaskAddr))

        if len(MaskAddr)>4 or len(MaskAddr)<4:
            print("\033[0;31mA mask can only be coded on four bytes.\033[00m")
            exit(1)

        print("")
        print("Initial value (Mask):",mask)
        SlideCidr="/"+str(cidr)
        print("CIDR:",SlideCidr)

    elif len(sys.argv)==3:
        mask=sys.argv[2]

        MaskAddr=[0,0,0,0]
        MaskAddr=mask
        cidr=0
        MaskAddr=[int(x) for x in MaskAddr.split(".")]
        cidr=sum((bin(x).count('1') for x in MaskAddr))

        if len(MaskAddr)>4 or len(MaskAddr)<4:
            print("\033[0;31mA mask can only be coded on four bytes.\033[00m")
            exit(1)

        print("Initial value (Mask):",mask)
        SlideCidr="/"+str(cidr)
        print("CIDR:",SlideCidr)

    elif len(sys.argv)>=4:
        print("\033[0;31mOnly one argument is expected.\033[00m")
        exit(1)

    else:
        print("\033[0;31mAn unexpected error was caused.\033[00m")
        exit(1)

def cidrtomask():

    if len(sys.argv)==2:
        cidr=input("Enter a CIDR: ")
        cidr=int(cidr)

        mask=[]
        dat=0
        ii=[1]*cidr
        for i in range(len(ii)):
            math=i%8
            if math==0:
                if i>=8:
                    mask.append(dat)
                    dat = 0
            dat+=pow(2,7-math)
        mask.append(dat)
        [mask.append(0) for i in range(4 - len(mask))]
        final_Mask=".".join([str(i) for i in mask])

        print("")
        print("Initial value (CIDR):",cidr)
        print("Mask:",final_Mask)

    elif len(sys.argv)==3:
        cidr=sys.argv[2]
        cidr=int(cidr)

        mask=[]
        dat=0
        ii=[1]*cidr
        for i in range(len(ii)):
            math=i%8
            if math==0:
                if i>=8:
                    mask.append(dat)
                    dat = 0
            dat+=pow(2,7-math)
        mask.append(dat)
        [mask.append(0) for i in range(4 - len(mask))]
        final_Mask=".".join([str(i) for i in mask])

        print("")
        print("Initial value (CIDR):",cidr)
        print("Mask:",final_Mask)

    elif len(sys.argv)>=4:
        print("\033[0;31mOnly one argument is expected.\033[00m")
        exit(1)

    else:
        print("\033[0;31mAn unexpected error was caused.\033[00m")
        exit(1)

def masktowildcard():

    if len(sys.argv)==2:
        mask=input("Enter a mask: ")

        wildcardmask=str(IPv4Address(int(IPv4Address(mask))^(2**32-1)))

        print("")
        print("Initial value (Mask):",mask)
        print("Wildcard mask:",wildcardmask)

    elif len(sys.argv)==3:
        mask=sys.argv[2]

        wildcardmask=str(IPv4Address(int(IPv4Address(mask))^(2**32-1)))

        print("Initial value (Mask):",mask)
        print("Wildcard mask:",wildcardmask)

    elif len(sys.argv)>=4:
        print("\033[0;31mOnly one argument is expected.\033[00m")
        exit(1)

    else:
        print("\033[0;31mAn unexpected error was caused.\033[00m")
        exit(1)

def wildcardtomask():

    if len(sys.argv)==2:
        wildcard=input("Enter a wildcard mask: ")

        mask=str(IPv4Address(int(IPv4Address(wildcard))^(2**32-1)))

        print("")
        print("Initial value (wildcard mask):",wildcard)
        print("Mask:",mask)

    elif len(sys.argv)==3:
        wildcard=sys.argv[2]

        mask=str(IPv4Address(int(IPv4Address(wildcard))^(2**32-1)))

        print("Initial value (wildcard mask):",wildcard)
        print("Mask:",mask)

    elif len(sys.argv)>=4:
        print("\033[0;31mOnly one argument is expected.\033[00m")
        exit(1)

    else:
        print("\033[0;31mAn unexpected error was caused.\033[00m")
        exit(1)

def cidrtowildcard():

    if len(sys.argv)==2:
        cidr=input("Enter a CIDR: ")

        wildcardmask=str(IPv4Address(int(IPv4Address._make_netmask(cidr)[0])^(2**32-1)))

        print("")
        print("Initial value (CIDR):",cidr)
        print("Wildcard mask:",wildcardmask)

    elif len(sys.argv)==3:
        cidr=sys.argv[2]

        wildcardmask=str(IPv4Address(int(IPv4Address._make_netmask(cidr)[0])^(2**32-1)))

        print("Initial value (CIDR):",cidr)
        print("Wildcard mask:",wildcardmask)

    elif len(sys.argv)>=4:
        print("\033[0;31mOnly one argument is expected.\033[00m")
        exit(1)

    else:
        print("\033[0;31mAn unexpected error was caused.\033[00m")
        exit(1)

def wildcardtocidr():

    if len(sys.argv)==2:
        wildcardmask=input("Enter a wildcard mask: ")

        cidr=IPv4Address._prefix_from_ip_int(int(IPv4Address(wildcardmask))^(2**32-1))

        print("")
        print("Initial value (wildcard mask):",wildcardmask)
        print("Wildcard mask:",cidr)

    elif len(sys.argv)==3:
        wildcardmask=sys.argv[2]

        cidr=IPv4Address._prefix_from_ip_int(int(IPv4Address(wildcardmask))^(2**32-1))

        print("Initial value (wildcard mask):",wildcardmask)
        print("Wildcard mask:",cidr)

    elif len(sys.argv)>=4:
        print("\033[0;31mOnly one argument is expected.\033[00m")
        exit(1)

    else:
        print("\033[0;31mAn unexpected error was caused.\033[00m")
        exit(1)

def main():
    clear()
    print("")
    print("                      ╔╦╗┬ ┬┌─┐  ╔╗╔┌─┐┌┬┐┬ ┬┌─┐┬─┐┬┌─  ")
    print("                       ║ ├─┤├┤   ║║║├┤  │ ││││ │├┬┘├┴┐  ")
    print("                       ╩ ┴ ┴└─┘  ╝╚╝└─┘ ┴ └┴┘└─┘┴└─┴ ┴  ")
    print("                      ╔═╗┌─┐┬  ┌─┐┬ ┬┬  ┌─┐┌┬┐┌─┐┬─┐    ")
    print("                      ║  ├─┤│  │  │ ││  ├─┤ │ │ │├┬┘    ")
    print("                      ╚═╝┴ ┴┴─┘└─┘└─┘┴─┘┴ ┴ ┴ └─┘┴└─    ")
    print("                          ╔╦╗┌─┐┌─┐┬  ┌┐ ┌─┐─┐ ┬        ")
    print("                           ║ │ ││ ││  ├┴┐│ │┌┴┬┘        ")
    print("                           ╩ └─┘└─┘┴─┘└─┘└─┘┴ └─        ")
    print("")
    print("1 - IP & MASK TO BINARY: Convert an IP address and its mask (or CIDR) into a binary number.")
    print("")
    print("2 - IP TO BINARY: Convert an IP address (in decimal format) to a binary number.")
    print("3 - BINARY TO IP: Convert an IP address (in binary number) to a decimal format.")
    print("")
    print("4 - DECIMAL TO BINARY: Convert a decimal number into a binary number.")
    print("5 - BINARY TO DECIMAL: Convert a binary number into a decimal number.")
    print("")
    print("6 - DECIMAL TO HEXADECIMAL: Convert a decimal number into a hexadecimal number.")
    print("7 - HEXADECIMAL TO DECIMAL: Convert a hexadecimal number into a decimal number.")
    print("")
    print("8 - CIDR Calculator (FROM MASK, TO CIDR): Calculate the CIDR of a mask.")
    print("9 - Convert a CIDR (FROM CIDR, TO MASK): Calculate the mask from a CIDR.")
    print("")
    print("10 - MASK TO WILDCARD MASK CALCULATOR: Convert a mask to wildcard mask.")
    print("11 - WILDCARD MASK TO MASK CALCULATOR: Convert a wildcard mask to a mask.")
    print("")
    print("12 - CIDR TO WILDCARD MASK: CONVERT A CIDR TO WILDCARD MASK.")
    print("13 - WILDCARD TO MASK: Convert a wildcard mask to a mask.")
    print("")
    print("0 - Quit the program.")
    print("")
    strUserChoice=input("Your choice: ")
    userChoice=int(strUserChoice)

    if userChoice==1:
        print("")
        ipAddrAndMasktobin()

    elif userChoice==2:
        print("")
        iptobin()

    elif userChoice==3:
        print("")
        bintoip()

    elif userChoice==4:
        print("")
        dectobin()

    elif userChoice==5:
        print("")
        bintodec()

    elif userChoice==6:
        print("")
        dectohex()

    elif userChoice==7:
        print("")
        hextodec()

    elif userChoice==8:
        print("")
        masktocidr()

    elif userChoice==9:
        print("")
        cidrtomask()

    elif userChoice==10:
        print("")
        masktowildcard()

    elif userChoice==11:
        print("")
        wildcardtomask()

    elif userChoice==12:
        print("")
        cidrtowildcard()

    elif userChoice==13:
        print("")
        wildcardtocidr()

    elif userChoice==0:
        print("")
        print("Exit of the program in progress.")
        exit(0)

    elif userChoice>13 or userChoice<0:
        print("\033[0;31mYour answer is not a valid choice.\033[00m")
        exit(1)
    
    else:
        print("\033[0;31mAn unexpected error was caused.\033[00m")
        exit(1)

if __name__ == "__main__":
    Check_UserInput()
