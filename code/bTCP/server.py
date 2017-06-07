# author: Hendrik Werner s4549775
# author: Constantin Blach s4329872
import socket

import shutil

from bTCP.exceptions import ChecksumMismatch
from bTCP.message import BTCPMessage, MessageFactory
from bTCP.state_machine import State, StateMachine


class Server(StateMachine):
    def __init__(
        self,
        sock: socket.socket,
        timeout: float,
        window_size: int,
        output_file: str,
    ):
        self.listen = Server.Listen(self)
        self.syn_received = Server.SynReceived(self)
        self.established = Server.Established(self)
        self.fin_sent = Server.FinSent(self)
        self.fin_received = Server.FinReceived(self)
        self.closed = Server.Closed(self)
        self.state = self.listen

        self.client_address = None
        self.expected_syn = 0
        self.factory = MessageFactory(0, window_size)
        self.output_file = output_file
        self.sock = sock
        self.stream_id = 0
        self.syn_number = 0
        self.timeout = timeout
        self.window_size = window_size

    class Listen(State):
        def run(self):
            sm = self.state_machine
            sm.sock.setblocking(True)
            sm.syn_number = 100
            try:
                data, sm.client_address = sm.sock.recvfrom(1016)
                syn_message = BTCPMessage.from_bytes(data)
            except ChecksumMismatch:
                self.log_error("checksum mismatch")
                return sm.listen
            if not (
                syn_message.header.syn and
                syn_message.header.ack_number == 0
            ):
                self.log_error("wrong message received")
                return sm.listen
            sm.expected_syn = syn_message.header.syn_number + 1
            sm.stream_id = syn_message.header.id
            sm.factory.stream_id = syn_message.header.id
            if (syn_message.header.name and
                len(syn_message.payload) < 30 and
                len(syn_message.payload) != 0
            ):
                sm.output_file = str(syn_message.payload, "utf-8")
            return sm.syn_received

    class SynReceived(State):
        def run(self):
            sm = self.state_machine
            sm.sock.sendto(
                sm.factory.synack_message(
                    sm.syn_number, sm.expected_syn
                ).to_bytes(),
                sm.client_address,
            )
            sm.sock.settimeout(sm.timeout)
            try:
                packet = BTCPMessage.from_bytes(sm.sock.recv(1016))
            except socket.timeout:
                self.log_error("timed out")
                return sm.syn_received
            except ChecksumMismatch:
                self.log_error("checksum mismatch")
                return sm.syn_received
            if not (
                packet.header.id == sm.stream_id and
                packet.header.syn_number >= sm.expected_syn
            ):
                self.log_error("wrong message received")
                return sm.syn_received
            sm.syn_number += 1
            print("S Connection established")
            return sm.established

    class Established(State):
        def __init__(self, state_machine: StateMachine):
            super().__init__(state_machine)
            self.output = bytes()
            self.window = {}

        def run(self):
            sm = self.state_machine
            try:
                packet = BTCPMessage.from_bytes(sm.sock.recv(1016))
            except socket.timeout:
                self.log_error("timed out")
                return sm.established
            except ChecksumMismatch:
                self.log_error("checksum mismatch")
                return sm.established
            if packet.header.id != sm.stream_id:
                return sm.established
            if packet.header.no_flags:
                self.handle_data_packet(packet)
                if shutil.disk_usage(".").free < len(self.output):
                    return sm.fin_sent
                sm.sock.sendto(
                    sm.factory.ack_message(
                        sm.syn_number, sm.expected_syn
                    ).to_bytes(),
                    sm.client_address,
                )
            elif (
                packet.header.fin and
                packet.header.syn_number == sm.expected_syn
            ):
                sm.expected_syn += 1
                with open(sm.output_file, "wb") as f:
                    f.write(self.output)
                return sm.fin_received
            return sm.established

        def handle_data_packet(self, packet):
            sm = self.state_machine
            if packet.header.syn_number == sm.expected_syn:
                self.output += packet.payload
                sm.expected_syn += 1
                while sm.expected_syn in self.window:
                    self.output += self.window[sm.expected_syn]
                    del self.window[sm.expected_syn]
                    sm.expected_syn += 1
            elif (
                sm.expected_syn <
                packet.header.syn_number <
                sm.expected_syn + sm.window_size
            ):
                self.window[packet.header.syn_number] = packet.payload

    class FinSent(State):
        def __init__(self, state_machine: StateMachine):
            super().__init__(state_machine)
            self.retries = 10

        def run(self):
            sm = self.state_machine
            if self.retries <= 0:
                self.log_error("retry limit reached")
                return sm.closed
            self.retries -= 1
            sm.sock.sendto(
                sm.factory.fin_message(
                    sm.syn_number, sm.expected_syn
                ).to_bytes(),
                sm.client_address,
            )
            try:
                finack_message = BTCPMessage.from_bytes(sm.sock.recv(1016))
            except socket.timeout:
                self.log_error("timed out")
                return sm.fin_sent
            except ChecksumMismatch:
                self.log_error("checksum mismatch")
                return sm.fin_sent
            if not (
                finack_message.header.fin and
                finack_message.header.ack and
                finack_message.header.id == sm.stream_id
            ):
                self.log_error("wrong message received")
                return sm.fin_sent
            sm.syn_number += 1
            sm.expected_syn += 1
            sm.sock.sendto(
                sm.factory.ack_message(
                    sm.syn_number, sm.expected_syn
                ).to_bytes(),
                sm.client_address
            )
            return sm.closed

    class FinReceived(State):
        def __init__(self, state_machine: StateMachine):
            super().__init__(state_machine)
            self.retries = 10

        def run(self):
            sm = self.state_machine
            if self.retries <= 0:
                self.log_error("timeout limit reached.")
                return sm.closed
            self.retries -= 1
            sm.sock.sendto(
                sm.factory.finack_message(
                    sm.syn_number, sm.expected_syn
                ).to_bytes(),
                sm.client_address,
            )
            try:
                ack_message = BTCPMessage.from_bytes(sm.sock.recv(1016))
            except socket.timeout:
                self.log_error("timed out")
                return sm.fin_received
            except ChecksumMismatch:
                self.log_error("checksum mismatch")
                return sm.fin_received
            if not (
                ack_message.header.ack and
                ack_message.header.id == sm.stream_id and
                ack_message.header.syn_number == sm.expected_syn
            ):
                self.log_error("wrong message received")
                return sm.fin_received
            return sm.closed

    class Closed(State):
        pass
