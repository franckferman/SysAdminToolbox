from ast import If
import os
from os import system
import ctypes
from sys import exit
from sys import argv
import sys

def run():
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
    elif str(sys.argv[1])=="--i":
        main()
    elif str(sys.argv[1])=="--d2b":
        main()
    elif str(sys.argv[1])=="-interactive":
        main()
    elif str(sys.argv[1])=="-i":
        main()
    elif str(sys.argv[1])=="/interactive":
        main()
    elif str(sys.argv[1])=="/i":
        main()

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
    
    else:
        print("\033[0;31mAn unexpected error has been caused.\033[00m")
        exit(1)

def usage():
    print("Usage: python3 main.py OPTIONS")
    print("")
    print("OPTIONS:")
    print("     --help, --usage, -h: Display this help message.")
    print("     -i, --i: interactive mode.")
    print("")
    print("ARGS:")
    print("     --iptobin ip_addr: ip address to binary conversion.")
    print("     --bintoip binary_number: IP address in binary to decimal conversion.")
    print("")
    print("     --dectobin decimal_number: decimal to binary conversion.")
    print("     --bintodec binary_number: binary to decimal conversion.")
    print("")
    print("     --dectohex decimal_number: decimal to hexa conversion.")
    print("     --hextodec hexa_number: hexa to decimal conversion.")
    print("")
    print("EXAMPLES:")
    print("     python3 ./main.py --iptobin 192.168.0.1")
    print("     python3 ./main.py --dectobin 250")
    exit(0)

def clear():
    os.system('cls' if os.name=='nt' else 'clear')

def dectobin():
    if len(sys.argv)<3:
        dec_value=input("Input a decimal number: ")
        dec_value=int(dec_value)

        bin_value=bin(dec_value)[2:]
        bin_complement_value=format(dec_value, '#010b')[2:]

        print("Initial value (decimal):",dec_value)
        print("")
        print("Binary value:",bin_value)
        print("Binary signed 2s complement:",bin_complement_value)
    
    elif len(sys.argv)==3:
        dec_value=int(sys.argv[2])

        bin_value=bin(dec_value)[2:]
        bin_complement_value=format(dec_value, '#010b')[2:]

        print("Initial value (decimal):",dec_value)
        print("")
        print("Binary value:",bin_value)
        print("Binary signed 2s complement:",bin_complement_value) 

def bintodec(): 
    if len(sys.argv)<3:
        bin_value=input("Input a binary number: ")

        new_bin_value="0b"+bin_value
        dec_value=int(new_bin_value, 2)

        print("Initial value (binary):",bin_value)
        print("Decimal value:",dec_value)
    
    elif len(sys.argv)==3:
        bin_value=(sys.argv[2])

        new_bin_value="0b"+bin_value
        dec_value=int(new_bin_value, 2)

        print("Initial value (binary):",bin_value)
        print("")
        print("Decimal value:",dec_value)

def dectohex():
    if len(sys.argv)<3:
        dec_value=input("Input a decimal number: ")
        dec_value=int(dec_value)

        hex_value=hex(dec_value)[2:]

        print("Initial value (decimal):",dec_value)
        print("")
        print("Hexa value:",hex_value)
    
    elif len(sys.argv)==3:
        dec_value=int(sys.argv[2])
        
        dec_value=int(dec_value)
        hex_value=hex(dec_value)[2:]

        print("Initial value (decimal):",dec_value)
        print("")
        print("Hexa value:",hex_value)

def hextodec():
    if len(sys.argv)<3:
        hex_value=input("Input a hexa number: ")

        new_hex_value="0x"+hex_value
        dec_value=int(new_hex_value, 16)

        print("Initial value (hexa):",hex_value)
        print("")
        print("Decimal value:",dec_value)
    
    elif len(sys.argv)==3:
        hex_value=(sys.argv[2])

        new_hex_value="0x"+hex_value
        dec_value=int(new_hex_value, 16)

        print("Initial value (hexa):",hex_value)
        print("")
        print("Decimal value:",dec_value)

def iptobin():
    if len(sys.argv)<3:
        ip=input("Input a IP address: ")
        addr=[0,0,0,0]
        addr=ip
        addr=[int(x) for x in addr.split(".")]

        if len(addr)<4:
            print("\033[0;31mAn IP address must be coded on 4 bytes.\033[00m")
            print("")
            input("Please press the Enter key to proceed.")
            print("")
            iptobin()
    
        First_Byte_dec=addr[0]
        Second_Byte_dec=addr[1]
        Third_Octet_dec=addr[2]
        Fourth_Octet_dec=addr[3]
    
        First_Byte_bin=bin(First_Byte_dec)[2:]
        Second_Byte_bin=bin(Second_Byte_dec)[2:]
        Third_Octet_bin=bin(Third_Octet_dec)[2:]
        Fourth_Octet_bin=bin(Fourth_Octet_dec)[2:]
    
        final_bin_value=First_Byte_bin+"."+Second_Byte_bin+"."+Third_Octet_bin+"."+Fourth_Octet_bin
    
        First_Byte_bin_complement=format(First_Byte_dec, '#010b')[2:]
        Second_Byte_bin_complement=format(Second_Byte_dec, '#010b')[2:]
        Third_Octet_bin_complement=format(Third_Octet_dec, '#010b')[2:]
        Fourth_Octet_bin_complement=format(Fourth_Octet_dec, '#010b')[2:]
    
        final_bin_complement_value=First_Byte_bin_complement+"."+Second_Byte_bin_complement+"."+Third_Octet_bin_complement+"."+Fourth_Octet_bin_complement

        print("Initial value (IP in decimal):",ip)
        print("")
        print("Binary value:",final_bin_value)
        print("Binary signed 2s complement:",final_bin_complement_value)

    elif len(sys.argv)==3:
        ip=(sys.argv[2])
        addr=[0,0,0,0]
        addr=ip
        addr=[int(x) for x in addr.split(".")]

        if len(addr)<4:
            print("\033[0;31mAn IP address must be coded on 4 bytes.\033[00m")
            print("")
            input("Please press the Enter key to proceed.")
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
    
        First_Byte_bin_complement=format(First_Byte_dec, '#010b')[2:]
        Second_Byte_bin_complement=format(Second_Byte_dec, '#010b')[2:]
        Third_Octet_bin_complement=format(Third_Octet_dec, '#010b')[2:]
        Fourth_Octet_bin_complement=format(Fourth_Octet_dec, '#010b')[2:]
    
        final_bin_complement_value=First_Byte_bin_complement+"."+Second_Byte_bin_complement+"."+Third_Octet_bin_complement+"."+Fourth_Octet_bin_complement

        print("Initial value (IP in decimal):",ip)
        print("")
        print("Binary value:",final_bin_value)
        print("Binary signed 2s complement:",final_bin_complement_value)

def bintoip():
    if len(sys.argv)<3:
        ip=input("Enter an IP address in binary format: ")
        addr=[0,0,0,0]
        addr=ip
        addr=[int(x) for x in addr.split(".")]

        if len(addr)<4:
            print("\033[0;31mAn IP address must be coded on 4 bytes.\033[00m")
            print("")
            input("Please press the Enter key to proceed.")
            print("")
            iptobin()
    
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

        print("Initial value (IP in decimal):",ip)
        print("")
        print("Decimal value:",final_dec_value)

    elif len(sys.argv)==3:
        ip=(sys.argv[2])
        addr=[0,0,0,0]
        addr=ip
        addr=[int(x) for x in addr.split(".")]

        if len(addr)<4:
            print("\033[0;31mAn IP address must be coded on 4 bytes.\033[00m")
            print("")
            input("Please press the Enter key to proceed.")
            print("")
            iptobin()
    
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

        print("Initial value (IP in decimal):",ip)
        print("")
        print("Decimal value:",final_dec_value)

def main():
    clear()
    print("")
    print("╔╦╗┬ ┬┌─┐  ╔╗╔┌─┐┌┬┐┬ ┬┌─┐┬─┐┬┌─  ")
    print(" ║ ├─┤├┤   ║║║├┤  │ ││││ │├┬┘├┴┐  ")
    print(" ╩ ┴ ┴└─┘  ╝╚╝└─┘ ┴ └┴┘└─┘┴└─┴ ┴  ")
    print("╔═╗┌─┐┬  ┌─┐┬ ┬┬  ┌─┐┌┬┐┌─┐┬─┐    ")
    print("║  ├─┤│  │  │ ││  ├─┤ │ │ │├┬┘    ")
    print("╚═╝┴ ┴┴─┘└─┘└─┘┴─┘┴ ┴ ┴ └─┘┴└─    ")
    print("    ╔╦╗┌─┐┌─┐┬  ┌┐ ┌─┐─┐ ┬        ")
    print("     ║ │ ││ ││  ├┴┐│ │┌┴┬┘        ")
    print("     ╩ └─┘└─┘┴─┘└─┘└─┘┴ └─        ")
    print("")
    print("1 - IP to binary.")
    print("2 - Binary to IP.")
    print("")
    print("3 - Decimal to binary conversion.")
    print("4 - Binary to decimal conversion.")
    print("")
    print("5 - Decimal to hexa conversion.")
    print("6 - Hexa to decimal conversion.")
    print("")
    print("9 - Quit the program.")
    print("")
    userChoice=input("Your choice: ")

    if userChoice=="1":
        print("")
        iptobin()

    elif userChoice=="2":
        print("")
        bintoip()

    elif userChoice=="3":
        print("")
        dectobin()

    elif userChoice=="4":
        print("")
        bintodec()

    elif userChoice=="5":
        print("")
        dectohex()

    elif userChoice=="6":
        print("")
        hextodec()

    elif userChoice=="9":
        exit(0)
    
    else:
        print("\033[0;31mAn unexpected error has been caused.\033[00m")
        exit(1)

if __name__ == "__main__":
    run()
