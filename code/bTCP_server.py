#!/usr/local/bin/python3
import argparse
import socket

import sys
import shutil

from bTCP.exceptions import ChecksumMismatch
from bTCP.message import BTCPMessage, MessageFactory
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

expected_syn = 0
syn_number = 0
client_address = None
stream_id = 0
factory = None


class Listen(State):
    def run(self):
        sock.setblocking(True)
        global client_address
        global expected_syn
        global factory
        global stream_id
        global syn_number
        syn_number = 100
        try:
            data, client_address = sock.recvfrom(1016)
            syn_message = BTCPMessage.from_bytes(data)
        except ChecksumMismatch:
            print("S Listen: checksum mismatch", file=sys.stderr)
            return Server.listen
        if not (
            syn_message.header.syn and
            syn_message.header.ack_number == 0
        ):
            print("S Listen: wrong message received", file=sys.stderr)
            return Server.listen
        expected_syn = syn_message.header.syn_number + 1
        stream_id = syn_message.header.id
        factory = MessageFactory(stream_id, args.window)
        return Server.syn_received


class SynReceived(State):
    def run(self):
        global syn_number
        sock.sendto(
            factory.synack_message(syn_number, expected_syn).to_bytes(),
            client_address,
        )
        sock.settimeout(args.timeout / 1000)
        try:
            packet = BTCPMessage.from_bytes(sock.recv(1016))
        except socket.timeout:
            print("S SynReceived: timed out", file=sys.stderr)
            return Server.syn_received
        except ChecksumMismatch:
            print("S SynReceived: checksum mismatch", file=sys.stderr)
            return Server.syn_received
        if not (
            packet.header.id == stream_id and
            packet.header.syn_number >= expected_syn
        ):
            print("S SynReceived: wrong message received", file=sys.stderr)
            return Server.syn_received
        syn_number += 1
        return Server.established


class Established(State):
    def run(self):
        print("S Connection established")
        global expected_syn
        self.output = bytes()
        self.window = {}
        while True:
            try:
                packet = BTCPMessage.from_bytes(sock.recv(1016))
            except socket.timeout:
                print("S Established: timed out", file=sys.stderr)
                continue
            except ChecksumMismatch:
                print("S Established: checksum mismatch", file=sys.stderr)
                continue
            if packet.header.id != stream_id:
                continue
            if packet.header.no_flags:
                self.handle_data_packet(packet)
                if shutil.disk_usage(".").free < len(self.output):
                    Server.fin_sent.retries = 10
                    return Server.fin_sent
                sock.sendto(
                    factory.ack_message(syn_number, expected_syn).to_bytes(),
                    client_address,
                )
            elif (
                packet.header.fin and
                packet.header.syn_number == expected_syn
            ):
                expected_syn += 1
                with open(args.output, "wb") as f:
                    f.write(self.output)
                Server.fin_received.retries = 10
                return Server.fin_received

    def handle_data_packet(self, packet):
        global expected_syn
        if packet.header.syn_number == expected_syn:
            self.output += packet.payload
            expected_syn += 1
            while expected_syn in self.window:
                self.output += self.window[expected_syn]
                del self.window[expected_syn]
                expected_syn += 1
        elif packet.header.syn_number < expected_syn + args.window:
            self.window[packet.header.syn_number] = packet.payload


class FinSent(State):
    def run(self):
        if self.retries <= 0:
            print("S FinSent: retry limit reached", file=sys.stderr)
            return Server.closed
        self.retries -= 1
        global expected_syn
        global syn_number
        sock.sendto(
            factory.fin_message(syn_number, expected_syn).to_bytes(),
            client_address,
        )
        try:
            finack_message = BTCPMessage.from_bytes(sock.recv(1016))
        except socket.timeout:
            print("S FinSent: timed out", file=sys.stderr)
            return Server.fin_sent
        except ChecksumMismatch:
            print("S FinSent: checksum mismatch", file=sys.stderr)
            return Server.fin_sent
        if not (
            finack_message.header.fin and
            finack_message.header.ack and
            finack_message.header.id == stream_id
        ):
            print("S FinSent: wrong message received", file=sys.stderr)
            return Server.fin_sent
        syn_number += 1
        expected_syn += 1
        sock.sendto(
            factory.ack_message(syn_number, expected_syn).to_bytes(),
            client_address
        )
        return Server.closed


class FinReceived(State):
    def run(self):
        if self.retries <= 0:
            print("S FinReceived: timeout limit reached.", file=sys.stderr)
            return Server.closed
        self.retries -= 1
        sock.sendto(
            factory.finack_message(syn_number, expected_syn).to_bytes(),
            client_address,
        )
        try:
            ack_message = BTCPMessage.from_bytes(sock.recv(1016))
        except socket.timeout:
            print("S FinReceived: timed out", file=sys.stderr)
            return Server.fin_received
        except ChecksumMismatch:
            print("S FinReceived: checksum mismatch", file=sys.stderr)
            return Server.fin_received
        if not (
            ack_message.header.ack and
            ack_message.header.id == stream_id and
            ack_message.header.syn_number == expected_syn
        ):
            print("S FinReceived: wrong message received", file=sys.stderr)
            return Server.fin_received
        return Server.closed


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
sock.bind((args.serverip, args.serverport))
server = Server(Server.listen)

try:
    while server.state is not Server.closed:
        server.run()
finally:
    sock.close()
