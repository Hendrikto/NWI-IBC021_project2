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

expected_syn = None
syn_number = None
client_address = None
stream_id = 0


class Listen(State):
    def run(self, sock: socket.socket):
        sock.setblocking(True)
        global syn_number
        syn_number = 100
        try:
            global client_address
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
        global expected_syn
        expected_syn = syn_message.header.syn_number + 1
        global stream_id
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
        sock.settimeout(args.timeout / 1000)
        global expected_syn
        global syn_number
        try:
            sock.recv(1016)
        except socket.timeout:
            print("SynRecv: timeout error", file=sys.stderr)
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
        expected_syn += 1
        syn_number += 1
        return Server.established


class Established(State):
    def run(self, sock: socket.socket):
        print("Connection established")
        output = bytes()
        global expected_syn
        while True:
            try:
                data = sock.recv(1016)
                packet = BTCPMessage.from_bytes(data)
                if not packet.header.fin and not packet.header.ack:
                    output += packet.payload
                    expected_syn += 1
                    self.send_ack(sock)
                elif packet.header.fin:
                    expected_syn += 1
                    with open("test", "wb") as f:
                        f.write(output)
                    return Server.fin_received
            except socket.timeout:
                print("Established: timeout error", file=sys.stderr)
                break
            except ChecksumMismatch:
                print("Established: ChecksumMismatch", file=sys.stderr)
        return Server.closed

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


class FinSent(State):
    pass


class FinReceived(State):
    def run(self, sock: socket.socket):
        global syn_number
        fin_ack_message = BTCPMessage(
            BTCPHeader(
                id=stream_id,
                syn=syn_number,
                ack=expected_syn,
                raw_flags=0,
                window_size=args.window,
            ),
            b""
        )
        fin_ack_message.header.ack = True
        fin_ack_message.header.fin = True
        sock.sendto(fin_ack_message.to_bytes(), client_address)
        syn_number += 1
        while True:
            try:
                answer = sock.recv(1016)
                break
            except socket.timeout:
                sock.sendto(fin_ack_message.to_bytes(), client_address)
                continue
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
server = Server(Server.listen, sock)

while server.state is not Server.closed:
    server.run()

sock.close()
