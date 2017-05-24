#!/usr/local/bin/python3
import argparse
import socket

from bTCP.state_machine import StateMachine, State

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
args = parser.parse_args()

# Define a header format
header_format = "I"

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)  # UDP
sock.bind((args.serverip, args.serverport))


class Listen(State):
    pass


class SynReceived(State):
    pass


class Established(State):
    pass


class FinSent(State):
    pass


class FinReceived(State):
    pass


class Closed(State):
    pass


class Server(StateMachine):
    listen = Listen()
    syn_received = SynReceived()
    established = Established()
    fin_sent = FinSent()
    fin_received = FinReceived()
    closed = Closed()


sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
server = Server(Server.listen, sock)

while server.state is not Server.closed:
    server.run()

sock.close()
