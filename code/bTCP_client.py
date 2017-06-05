#!/usr/local/bin/python3
import argparse
from datetime import datetime
import socket
from random import randint
import sys

from bTCP.exceptions import ChecksumMismatch
from bTCP.message import BTCPMessage, MessageFactory
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


class Closed(State):
    def run(self):
        sm = self.state_machine
        stream_id = randint(0, 2 ** 32)
        sm.stream_id = stream_id
        sm.factory.stream_id = stream_id
        return sm.syn_sent


class SynSent(State):
    def run(self):
        sm = self.state_machine
        sock.sendto(
            sm.factory.syn_message(sm.syn_number, sm.expected_syn).to_bytes(),
            sm.destination_address,
        )
        try:
            synack_message = BTCPMessage.from_bytes(sock.recv(1016))
        except socket.timeout:
            print("SynSent: timed out", file=sys.stderr)
            return sm.syn_sent
        except ChecksumMismatch:
            print("SynSent: checksum mismatch", file=sys.stderr)
            return sm.syn_sent
        if not (
            synack_message.header.id == sm.stream_id and
            synack_message.header.syn and
            synack_message.header.ack
        ):
            print("SynSent: wrong message received", file=sys.stderr)
            return sm.syn_sent
        sm.server_window = synack_message.header.window_size
        sm.accept_ack(synack_message.header.ack_number)
        sm.expected_syn = synack_message.header.syn_number + 1
        sm.syn_number += 1
        sock.sendto(
            sm.factory.ack_message(sm.syn_number, sm.expected_syn).to_bytes(),
            sm.destination_address,
        )
        print("Connection established")
        return sm.established


class Established(State):
    def __init__(
        self,
        state_machine: StateMachine,
        input_bytes: bytes,
    ):
        super().__init__(state_machine)
        self.input_bytes = input_bytes
        self.messages = {}

    def run(self):
        sm = self.state_machine
        while (
            self.input_bytes and
            sm.syn_number < sm.highest_ack + sm.server_window
        ):
            data = self.input_bytes[:BTCPMessage.payload_size]
            self.input_bytes = self.input_bytes[BTCPMessage.payload_size:]
            message = sm.factory.message(sm.syn_number, sm.expected_syn, data)
            sock.sendto(message.to_bytes(), sm.destination_address)
            self.messages[sm.syn_number] = (
                message, datetime.now().timestamp(),
            )
            sm.syn_number += 1
        while sm.highest_ack < sm.syn_number:
            try:
                message = BTCPMessage.from_bytes(sock.recv(1016))
            except socket.timeout:
                print("Established: timed out", file=sys.stderr)
                break
            except ChecksumMismatch:
                print("Established: checksum mismatch", file=sys.stderr)
                continue
            if message.header.id != sm.stream_id:
                continue
            for syn_nr in range(sm.highest_ack, message.header.ack_number):
                del self.messages[syn_nr]
            sm.accept_ack(message.header.ack_number)
            if message.header.fin:
                sm.expected_syn += 1
                return sm.fin_received
        for syn_nr in range(sm.highest_ack, sm.syn_number):
            message, timestamp = self.messages[syn_nr]
            now = datetime.now().timestamp()
            if now - timestamp > args.timeout / 1000:
                message.header.ack_number = sm.expected_syn
                sock.sendto(message.to_bytes(), sm.destination_address)
                self.messages[syn_nr] = (message, now)
        if self.input_bytes or sm.highest_ack < sm.syn_number:
            return sm.established
        return sm.fin_sent


class FinSent(State):
    def __init__(self, state_machine: StateMachine):
        super().__init__(state_machine)
        self.retries = 100

    def run(self):
        sm = self.state_machine
        if self.retries <= 0:
            print("FinSent: retry limit reached", file=sys.stderr)
            return sm.finished
        self.retries -= 1
        global syn_number
        global expected_syn
        sock.sendto(
            sm.factory.fin_message(sm.syn_number, sm.expected_syn).to_bytes(),
            sm.destination_address,
        )
        try:
            finack_message = BTCPMessage.from_bytes(sock.recv(1016))
        except socket.timeout:
            print("FinSent: timed out", file=sys.stderr)
            return sm.fin_sent
        except ChecksumMismatch:
            print("FinSent: checksum mismatch", file=sys.stderr)
            return sm.fin_sent
        if not (
            finack_message.header.id == sm.stream_id and
            finack_message.header.fin and
            finack_message.header.ack and
            finack_message.header.syn_number == sm.expected_syn
        ):
            print("FinSent: wrong message received", file=sys.stderr)
            return sm.fin_sent
        sm.accept_ack(finack_message.header.ack_number)
        sm.syn_number += 1
        sm.expected_syn += 1
        sock.sendto(
            sm.factory.ack_message(sm.syn_number, sm.expected_syn).to_bytes(),
            sm.destination_address,
        )
        return sm.finished


class FinReceived(State):
    def __init__(self, state_machine: StateMachine):
        super().__init__(state_machine)
        self.retries = 100

    def run(self):
        sm = self.state_machine
        if self.retries <= 0:
            print("FinSent: retry limit reached", file=sys.stderr)
            return sm.finished
        self.retries -= 1
        sock.sendto(
            sm.factory.finack_message(
                sm.syn_number, sm.expected_syn
            ).to_bytes(),
            sm.destination_address,
        )
        try:
            ack_message = BTCPMessage.from_bytes(sock.recv(1016))
        except socket.timeout:
            print("FinReceived: timed out", file=sys.stderr)
            return sm.fin_received
        except ChecksumMismatch:
            print("FinReceived: checksum mismatch", file=sys.stderr)
            return sm.fin_received
        if not (
            ack_message.header.ack and
            ack_message.header.id == sm.stream_id and
            ack_message.header.syn_number == expected_syn
        ):
            print("FinReceived: wrong message received", file=sys.stderr)
            return sm.fin_received
        return sm.finished


class Finished(State):
    pass


class Client(StateMachine):
    def __init__(
        self,
        input_bytes: bytes,
    ):
        self.closed = Closed(self)
        self.syn_sent = SynSent(self)
        self.established = Established(self, input_bytes)
        self.fin_sent = FinSent(self)
        self.fin_received = FinReceived(self)
        self.finished = Finished(self)
        self.state = self.closed

        self.destination_address = (args.destination, args.port)
        self.expected_syn = 0
        self.factory = MessageFactory(0, args.window)
        self.highest_ack = 0
        self.server_window = 0
        self.stream_id = 0
        self.syn_number = 0

    def accept_ack(self, ack: int):
        self.highest_ack = ack if ack > self.highest_ack else self.highest_ack


# UDP socket which will transport your bTCP packets
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.settimeout(args.timeout / 1000)

client = Client(input_bytes)

try:
    while client.state is not client.finished:
        client.run()
finally:
    sock.close()
