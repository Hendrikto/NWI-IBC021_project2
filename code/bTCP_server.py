#!/usr/local/bin/python3
import argparse
import socket
from struct import unpack

# Handle arguments
parser = argparse.ArgumentParser()
parser.add_argument(
    "-w", "--window", help="Define bTCP window size", type=int, default=100
)
parser.add_argument(
    "-t", "--timeout", help="Define bTCP timeout in milliseconds", type=int,
    default=100
)
parser.add_argument(
    "-o", "--output", help="Where to store file", default="tmp.file"
)
args = parser.parse_args()
parser.add_argument(
    "-s", "--serverip", help="Define server IP", type=str,
    default="127.0.0.1"
)
parser.add_argument(
    "-p", "--serverport", help="Define server port", type=int,
    default=9001
)


# Define a header format
header_format = "I"

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
sock.bind((args.serverip, args.serverport))

while True:
    data, addr = sock.recvfrom(1016)
    print(unpack(header_format, data))
