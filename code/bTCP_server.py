#!/usr/local/bin/python3
import argparse
import socket

import sys

from bTCP.exceptions import ChecksumMismatch
from bTCP.message import BTCPMessage
from bTCP.header import BTCPHeader
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


class Listen(State):
    def run(self, sock: socket.socket):
        sock.setblocking(True)
        global client_address
        global expected_syn
        global stream_id
        global syn_number
        syn_number = 100
        try:
            data, client_address = sock.recvfrom(1016)
            syn_message = BTCPMessage.from_bytes(data)
        except ChecksumMismatch:
            print("Listen: checksum mismatch", file=sys.stderr)
            return Server.listen
        if not (
            syn_message.header.syn and
            syn_message.header.ack_number == 0
        ):
            print("Listen: wrong message received", file=sys.stderr)
            return Server.listen
        expected_syn = syn_message.header.syn_number + 1
        stream_id = syn_message.header.id
        synack_message = BTCPMessage(
            BTCPHeader(
                id=stream_id,
                syn=syn_number,
                ack=expected_syn,
                raw_flags=0,
                window_size=args.window,
            ),
            b""
        )
        synack_message.header.syn = True
        synack_message.header.ack = True
        sock.sendto(synack_message.to_bytes(), client_address)
        return Server.syn_received


class SynReceived(State):
    def run(self, sock: socket.socket):
        global expected_syn
        global syn_number
        sock.settimeout(args.timeout / 1000)
        try:
            packet = BTCPMessage.from_bytes(sock.recv(1016))
        except socket.timeout:
            print("SynRecv: timeout error", file=sys.stderr)
            self.send_synack_message(sock)
            return Server.syn_received
        except ChecksumMismatch:
            self.send_synack_message(sock)
            print("SynRecv: Checksum error", file=sys.stderr)
            return Server.syn_received
        if not (
            packet.header.id == stream_id and
            packet.header.syn_number >= expected_syn
        ):
            print("SynRecv: Wrong Message received", file=sys.stderr)
            return Server.syn_received
        syn_number += 1
        return Server.established

    def send_synack_message(self, sock):
        global expected_syn
        global syn_number
        synack_message = BTCPMessage(
            BTCPHeader(
                id=stream_id,
                syn=syn_number,
                ack=expected_syn,
                raw_flags=0,
                window_size=args.window,
            ),
            b""
        )
        synack_message.header.syn = True
        synack_message.header.ack = True
        sock.sendto(synack_message.to_bytes(), client_address)


class Established(State):
    def run(self, sock: socket.socket):
        print("Connection established")
        global expected_syn
        self.output = bytes()
        self.window = {}
        while True:
            try:
                data = sock.recv(1016)
                packet = BTCPMessage.from_bytes(data)
            except socket.timeout:
                print("Established: timeout error", file=sys.stderr)
                continue
            except ChecksumMismatch:
                print("Established: ChecksumMismatch", file=sys.stderr)
                continue
            if packet.header._flags == 0:
                self.handle_data_packet(sock, packet)
                self.send_ack(sock)
            elif (
                packet.header.fin and
                packet.header.syn_number == expected_syn
            ):
                expected_syn += 1
                self.send_finack(sock)
                with open(args.output, "wb") as f:
                    f.write(self.output)
                return Server.fin_received
        return Server.closed

    def handle_data_packet(self, sock, packet):
        global expected_syn
        if packet.header.syn_number == expected_syn:
            self.output += packet.payload
            expected_syn += 1
            while expected_syn in self.window:
                print("Re-assemble packet")
                self.output += self.window[expected_syn]
                del self.window[expected_syn]
                expected_syn += 1
        elif packet.header.syn_number < expected_syn + window_size:
            print("Packet out of Order, saving in dict.")
            self.window[packet.header.syn_number] = packet.payload

    def send_ack(self, sock):
        global syn_number
        ack_message = BTCPMessage(
            BTCPHeader(
                id=stream_id,
                syn=syn_number,
                ack=expected_syn,
                raw_flags=0,
                window_size=args.window,
            ),
            b""
        )
        ack_message.header.ack = True
        sock.sendto(ack_message.to_bytes(), client_address)

    def send_finack(self, sock):
        finack_message = BTCPMessage(
            BTCPHeader(
                id=stream_id,
                syn=syn_number,
                ack=expected_syn,
                raw_flags=0,
                window_size=args.window,
            ),
            b""
        )
        finack_message.header.ack = True
        finack_message.header.fin = True
        sock.sendto(finack_message.to_bytes(), client_address)


class FinSent(State):
    def run(self, sock: socket.socket):
        global expected_syn
        global syn_number
        try:
            finack_message = BTCPMessage.from_bytes(sock.recv(1016))
        except socket.timeout:
            print("FinSent: timed out")
            self.send_fin(sock)
            return Server.fin_sent
        except ChecksumMismatch:
            print("FinSent: checksum mismatch")
            self.send_fin(sock)
            return Server.fin_sent
        if not (
            finack_message.header.fin and
            finack_message.header.ack and
            finack_message.header.id == stream_id
        ):
            print("FinSent: Wrong message received")
            self.send_fin(sock)
            return Server.fin_sent
        syn_number += 1
        expected_syn += 1
        ack_message = BTCPMessage(
            BTCPHeader(
                id=stream_id,
                syn=syn_number,
                ack=expected_syn,
                raw_flags=0,
                window_size=args.window,
            ),
            b""
        )
        ack_message.header.ack = True
        sock.sendto(ack_message.to_bytes(), client_address)
        return Server.closed

    def send_fin(self, sock):
        fin_message = BTCPMessage(
            BTCPHeader(
                id=stream_id,
                syn=syn_number,
                ack=expected_syn,
                raw_flags=0,
                window_size=args.window,
            ),
            b""
        )
        fin_message.header.fin = True
        sock.sendto(fin_message.to_bytes(), client_address)


class FinReceived(State):
    def run(self, sock: socket.socket):
        try:
            ack_message = BTCPMessage.from_bytes(sock.recv(1016))
        except socket.timeout:
            print("FinReceived: timed out", file=sys.stderr)
            self.send_finack(sock)
            return Server.fin_received
        except ChecksumMismatch:
            print("FinReceived: checksum mismatch", file=sys.stderr)
            self.send_finack(sock)
            return Server.fin_received
        if not (
            ack_message.header.ack and
            ack_message.header.id == stream_id and
            ack_message.header.syn_number == expected_syn
        ):
            print("FinReceived: wrong message received", file=sys.stderr)
            self.send_finack(sock)
            return Server.fin_received
        return Server.closed

    def send_finack(self, sock):
        finack_message = BTCPMessage(
            BTCPHeader(
                id=stream_id,
                syn=syn_number,
                ack=expected_syn,
                raw_flags=0,
                window_size=args.window,
            ),
            b""
        )
        finack_message.header.ack = True
        finack_message.header.fin = True
        sock.sendto(finack_message.to_bytes(), client_address)


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
server = Server(Server.listen, sock)

while server.state is not Server.closed:
    server.run()

sock.close()
