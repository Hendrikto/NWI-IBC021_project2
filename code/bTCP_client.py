#!/usr/local/bin/python3
import argparse
import socket
from random import randint
from struct import pack

# Handle arguments
parser = argparse.ArgumentParser()
parser.add_argument(
    "-w", "--window", help="Define bTCP window size", type=int, default=100
)
parser.add_argument(
    "-t", "--timeout", help="Define bTCP timeout in milliseconds", type=int,
    default=100
)
parser.add_argument("-i", "--input", help="File to send", default="tmp.file")
parser.add_argument(
    "-d", "--destination", help="Define destination IP", type=str,
    default="127.0.0.1"
)
parser.add_argument(
    "-p", "--port", help="Define destination port", type=int,
    default=9001
)
args = parser.parse_args()


# bTCP header
header_format = "I"
bTCP_header = pack(header_format, randint(0, 100))
bTCP_payload = ""
udp_payload = bTCP_header

# UDP socket which will transport your bTCP packets
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

# send payload
sock.sendto(udp_payload, (destination_ip, destination_port))
