#!/usr/local/bin/python3
import argparse
import socket

from bTCP.server import Server

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
parser.add_argument(
    "-s", "--serverip", help="Define server IP", type=str,
    default="127.0.0.1"
)
parser.add_argument(
    "-p", "--serverport", help="Define server port", type=int,
    default=9001
)
parser.add_argument(
    "-r", "--retry", help="Define the retry limit when closing the connection",
    type=int, default=10
)
args = parser.parse_args()

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.bind((args.serverip, args.serverport))

server = Server(
    sock=sock,
    timeout=args.timeout / 1000,
    retry_limit=args.retry,
    window_size=args.window,
    output_file=args.output,
)

try:
    while server.state is not server.closed:
        server.run()
finally:
    sock.close()
