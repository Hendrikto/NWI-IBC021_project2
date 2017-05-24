#!/usr/local/bin/python3
import argparse
import socket
from random import randint
import sys

from bTCP.message import BTCPMessage
from bTCP.header import BTCPHeader
from bTCP.state_machine import State, StateMachine

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
    "-p", "--port", help="Define destination port", type=int, default=9001
)
args = parser.parse_args()

with open(args.input, "rb") as input:
    input_bytes = input.read()

destination_addr = (args.destination, args.port)


class Closed(State):
    def run(self, sock):
        syn_message = BTCPMessage(
            BTCPHeader(
                id=randint(1, 2 ** 32),
                syn=1, ack=0,
                raw_flags=0,
                window_size=0,
                data_length=0
            ),
            b""
        )
        syn_message.header.syn = True
        sock.sendto(syn_message.to_bytes(), destination_addr)
        return Client.syn_sent


class SynSent(State):
    def run(self, sock):
        try:
            synack_message = BTCPMessage.from_bytes(sock.recv(1016))
        except socket.timeout:
            print("SynSent: timed out", file=sys.stderr)
            return Client.closed
        if (
                    synack_message.header.syn and
                    synack_message.header.ack
        ):
            ack_message = BTCPMessage(
                BTCPHeader(
                    id=synack_message.header.id,
                    syn=synack_message.header.syn,
                    ack=synack_message.header.syn + 1,
                    raw_flags=0,
                    window_size=0,
                    data_length=0
                ),
                b""
            )
            ack_message.header.ack = True
            sock.sendto(ack_message.to_bytes(), destination_addr)
            return Client.established
        else:
            print("SynSent: wrong message received", file=sys.stderr)


class Established(State):
    pass


class FinSent(State):
    # TODO: Think about timeout and/or resending the packet
    def run(self, sock):
        try:
            finack_message = BTCPMessage.from_bytes(sock.recv(1016))
        except socket.timeout:
            print("SynSent: timed out", file=sys.stderr)
            return Client.closed
        if (
            finack_message.header.fin and
            finack_message.header.ack
        ):
            ack_message = BTCPMessage(
                BTCPHeader(
                    id=finack_message.header.id,
                    syn=finack_message.header.syn,
                    ack=finack_message.header.syn + 1,
                    raw_flags=0,
                    window_size=0,
                    data_length=0
                ),
                b""
            )
            ack_message.header.ack = True
            sock.sendto(ack_message.to_bytes(), destination_addr)
        return Client.closed


class FinReceived(State):
    pass


class Client(StateMachine):
    closed = Closed()
    syn_sent = SynSent()
    established = Established()
    fin_sent = FinSent()
    fin_received = FinReceived()


# UDP socket which will transport your bTCP packets
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(args.timeout / 1000)
