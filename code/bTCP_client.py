#!/usr/local/bin/python3
import argparse
import socket
from random import randint
import sys

from bTCP.exceptions import ChecksumMismatch
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
expected_syn = None
syn_number = None
stream_id = 0


class Closed(State):
    def run(self, sock: socket.socket):
        global syn_number
        syn_number = 0
        global stream_id
        stream_id = randint(0, 2 ** 32)
        syn_message = BTCPMessage(
            BTCPHeader(
                id=stream_id,
                syn=syn_number,
                ack=0,
                raw_flags=0,
                window_size=0,
            ),
            b""
        )
        syn_message.header.syn = True
        sock.sendto(syn_message.to_bytes(), destination_addr)
        syn_number += 1
        return Client.syn_sent


class SynSent(State):
    def run(self, sock: socket.socket):
        try:
            synack_message = BTCPMessage.from_bytes(sock.recv(1016))
        except socket.timeout:
            print("SynSent: timed out", file=sys.stderr)
            return Client.closed
        except ChecksumMismatch:
            print("SynSent: checksum mismatch", file=sys.stderr)
            return Client.closed
        if not (
            synack_message.header.id == stream_id and
            synack_message.header.syn and
            synack_message.header.ack and
            synack_message.header.ack_number == syn_number
        ):
            print("SynSent: wrong message received", file=sys.stderr)
            return Client.closed
        global expected_syn
        expected_syn = synack_message.header.syn_number + 1
        ack_message = BTCPMessage(
            BTCPHeader(
                id=stream_id,
                syn=syn_number,
                ack=expected_syn,
                raw_flags=0,
                window_size=0,
            ),
            b""
        )
        ack_message.header.ack = True
        sock.sendto(ack_message.to_bytes(), destination_addr)
        global syn_number
        syn_number += 1
        return Client.established


class Established(State):
    pass


class FinSent(State):
    def run(self, sock: socket.socket):
        try:
            finack_message = BTCPMessage.from_bytes(sock.recv(1016))
        except socket.timeout:
            print("FinSent: timed out", file=sys.stderr)
            # TODO: resend FIN
            return Client.fin_sent
        except ChecksumMismatch:
            print("FinSent: checksum mismatch")
            # TODO: resend FIN
            return Client.fin_sent
        if not (
            finack_message.header.id == stream_id and
            finack_message.header.fin and
            finack_message.header.ack
            # TODO: SYN and ACK numbers
        ):
            print("FinSent: wrong message received")
            # TODO: resend FIN
            return Client.fin_sent
        ack_message = BTCPMessage(
            BTCPHeader(
                id=finack_message.header.id,
                syn=finack_message.header.syn,
                ack=finack_message.header.syn + 1,
                raw_flags=0,
                window_size=0,
            ),
            b""
        )
        ack_message.header.ack = True
        sock.sendto(ack_message.to_bytes(), destination_addr)
        return Client.closed


class FinReceived(State):
    def run(self, sock: socket.socket):
        try:
            sock.recv(1016)
            return Client.closed
        except socket.timeout:
            print("FinReceived: timed out", file=sys.stderr)
            return Client.closed


class Client(StateMachine):
    closed = Closed()
    syn_sent = SynSent()
    established = Established()
    fin_sent = FinSent()
    fin_received = FinReceived()


# UDP socket which will transport your bTCP packets
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(args.timeout / 1000)

client = Client(Client.closed, sock)
