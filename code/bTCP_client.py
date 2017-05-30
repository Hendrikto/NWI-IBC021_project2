#!/usr/local/bin/python3
import argparse
from datetime import datetime
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
expected_syn = 0
syn_number = 0
stream_id = 0
highest_ack = 0
timeouts = set()
messages = {}


def accept_ack(ack: int):
    global highest_ack
    highest_ack = ack if ack > highest_ack else highest_ack


class Closed(State):
    def run(self, sock: socket.socket):
        global stream_id
        global syn_number
        syn_number = 0
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
        return Client.syn_sent


class SynSent(State):
    def run(self, sock: socket.socket):
        global expected_syn
        global syn_number
        try:
            synack_message = BTCPMessage.from_bytes(sock.recv(1016))
        except socket.timeout:
            print("SynSent: timed out", file=sys.stderr)
            self.send_syn(sock)
            return Client.syn_sent
        except ChecksumMismatch:
            print("SynSent: checksum mismatch", file=sys.stderr)
            self.send_syn(sock)
            return Client.syn_sent
        if not (
            synack_message.header.id == stream_id and
            synack_message.header.syn and
            synack_message.header.ack
        ):
            print("SynSent: wrong message received", file=sys.stderr)
            self.send_syn(sock)
            return Client.syn_sent
        accept_ack(synack_message.header.ack_number)
        expected_syn = synack_message.header.syn_number + 1
        syn_number += 1
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
        return Client.established

    def send_syn(self, sock):
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


class Established(State):
    def run(self, sock: socket.socket):
        print("Connection established")
        global input_bytes
        global syn_number
        global timeouts
        while input_bytes:
            data = input_bytes[:BTCPMessage.payload_size]
            input_bytes = input_bytes[BTCPMessage.payload_size:]
            message = BTCPMessage(
                BTCPHeader(
                    id=stream_id,
                    syn=syn_number,
                    ack=expected_syn,
                    raw_flags=0,
                    window_size=0,
                ),
                data
            )
            sock.sendto(message.to_bytes(), destination_addr)
            timeouts.add(syn_number)
            messages[syn_number] = (message, datetime.now().timestamp())
            syn_number += 1
        while highest_ack < syn_number:
            try:
                message = BTCPMessage.from_bytes(sock.recv(1016))
            except socket.timeout:
                print("Established: timed out", file=sys.stderr)
                break
            except ChecksumMismatch:
                print("Established: checksum mismatch", file=sys.stderr)
                continue
            timeouts -= {*range(highest_ack, message.header.ack_number)}
            accept_ack(message.header.ack_number)
        for syn_nr in timeouts:
            message, timestamp = messages[syn_nr]
            now = datetime.now().timestamp()
            if now - timestamp > args.timeout / 1000:
                message.header.ack_number = expected_syn
                sock.sendto(message.to_bytes(), destination_addr)
                messages[syn_nr] = (message, now)
        if highest_ack != syn_number:
            return Client.established
        return Client.fin_sent


class FinSent(State):
    def run(self, sock: socket.socket):
        global syn_number
        fin_message = BTCPMessage(
            BTCPHeader(
                id=stream_id,
                syn=syn_number,
                ack=expected_syn,
                raw_flags=0,
                window_size=0,
            ),
            b""
        )
        fin_message.header.fin = True
        sock.sendto(fin_message.to_bytes(), destination_addr)
        try:
            finack_message = BTCPMessage.from_bytes(sock.recv(1016))
        except socket.timeout:
            print("FinSent: timed out", file=sys.stderr)
            return Client.fin_sent
        except ChecksumMismatch:
            print("FinSent: checksum mismatch", file=sys.stderr)
            return Client.fin_sent
        if not (
            finack_message.header.id == stream_id and
            finack_message.header.fin and
            finack_message.header.ack and
            finack_message.header.syn_number == expected_syn
        ):
            print("FinSent: wrong message received", file=sys.stderr)
            return Client.fin_sent
        accept_ack(finack_message.header.ack_number)
        syn_number += 1
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
        return Client.closed


class FinReceived(State):
    def run(self, sock: socket.socket):
        try:
            ack_message = BTCPMessage.from_bytes(sock.recv(1016))
        except socket.timeout:
            print("FinReceived: timed out", file=sys.stderr)
            self.send_finack(sock)
            return Client.fin_received
        except ChecksumMismatch:
            print("FinReceived: checksum mismatch", file=sys.stderr)
            self.send_finack(sock)
            return Client.fin_received
        if not (
            ack_message.header.ack and
            ack_message.header.id == stream_id and
            ack_message.header.syn_number == expected_syn
        ):
            print("FinReceived: wrong message received", file=sys.stderr)
            self.send_finack(sock)
            return Client.fin_received
        return Client.closed

    def send_finack(self, sock):
        finack_message = BTCPMessage(
            BTCPHeader(
                id=stream_id,
                syn=syn_number,
                ack=expected_syn,
                raw_flags=0,
                window_size=0,
            ),
            b""
        )
        finack_message.header.ack = True
        finack_message.header.fin = True
        sock.sendto(finack_message.to_bytes(), destination_addr)


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
while input_bytes or client.state is not Client.closed:
    client.run()

sock.close()
