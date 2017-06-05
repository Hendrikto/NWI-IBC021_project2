# author: Hendrik Werner s4549775
# author: Constantin Blach s4329872
from datetime import datetime
from random import randint
import socket

from typing import Tuple

from bTCP.exceptions import ChecksumMismatch
from bTCP.message import BTCPMessage, MessageFactory
from bTCP.state_machine import State, StateMachine


class Client(StateMachine):
    def __init__(
        self,
        sock: socket.socket,
        input_bytes: bytes,
        destination_address: Tuple[str, int],
        window: int,
        timeout: float,
    ):
        self.closed = Client.Closed(self)
        self.syn_sent = Client.SynSent(self)
        self.established = Client.Established(self, input_bytes, timeout)
        self.fin_sent = Client.FinSent(self)
        self.fin_received = Client.FinReceived(self)
        self.finished = Client.Finished(self)
        self.state = self.closed

        self.destination_address = destination_address
        self.expected_syn = 0
        self.factory = MessageFactory(0, window)
        self.highest_ack = 0
        self.server_window = 0
        self.sock = sock
        self.sock.settimeout(timeout)
        self.stream_id = 0
        self.syn_number = 0

    def accept_ack(self, ack: int):
        self.highest_ack = ack if ack > self.highest_ack else self.highest_ack

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
            sm.sock.sendto(
                sm.factory.syn_message(
                    sm.syn_number, sm.expected_syn).to_bytes(),
                sm.destination_address,
            )
            try:
                synack_message = BTCPMessage.from_bytes(sm.sock.recv(1016))
            except socket.timeout:
                self.log_error("timed out")
                return sm.syn_sent
            except ChecksumMismatch:
                self.log_error("checksum mismatch")
                return sm.syn_sent
            if not (
                synack_message.header.id == sm.stream_id and
                synack_message.header.syn and
                synack_message.header.ack
            ):
                self.log_error("wrong message received")
                return sm.syn_sent
            sm.server_window = synack_message.header.window_size
            sm.accept_ack(synack_message.header.ack_number)
            sm.expected_syn = synack_message.header.syn_number + 1
            sm.syn_number += 1
            sm.sock.sendto(
                sm.factory.ack_message(
                    sm.syn_number, sm.expected_syn
                ).to_bytes(),
                sm.destination_address,
            )
            print("Connection established")
            return sm.established

    class Established(State):
        def __init__(
            self,
            state_machine: StateMachine,
            input_bytes: bytes,
            timeout: float,
        ):
            super().__init__(state_machine)
            self.input_bytes = input_bytes
            self.messages = {}
            self.timeout = timeout

        def run(self):
            sm = self.state_machine
            while (
                self.input_bytes and
                sm.syn_number < sm.highest_ack + sm.server_window
            ):
                data = self.input_bytes[:BTCPMessage.payload_size]
                self.input_bytes = self.input_bytes[
                    BTCPMessage.payload_size:
                ]
                message = sm.factory.message(
                    sm.syn_number, sm.expected_syn, data
                )
                sm.sock.sendto(message.to_bytes(), sm.destination_address)
                self.messages[sm.syn_number] = (
                    message, datetime.now().timestamp(),
                )
                sm.syn_number += 1
            while sm.highest_ack < sm.syn_number:
                try:
                    message = BTCPMessage.from_bytes(sm.sock.recv(1016))
                except socket.timeout:
                    self.log_error("timed out")
                    break
                except ChecksumMismatch:
                    self.log_error("checksum mismatch")
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
                if now - timestamp > self.timeout:
                    message.header.ack_number = sm.expected_syn
                    sm.sock.sendto(message.to_bytes(), sm.destination_address)
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
                self.log_error("retry limit reached")
                return sm.finished
            self.retries -= 1
            global syn_number
            global expected_syn
            sm.sock.sendto(
                sm.factory.fin_message(
                    sm.syn_number, sm.expected_syn
                ).to_bytes(),
                sm.destination_address,
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
                finack_message.header.id == sm.stream_id and
                finack_message.header.fin and
                finack_message.header.ack and
                finack_message.header.syn_number == sm.expected_syn
            ):
                self.log_error("wrong message received")
                return sm.fin_sent
            sm.accept_ack(finack_message.header.ack_number)
            sm.syn_number += 1
            sm.expected_syn += 1
            sm.sock.sendto(
                sm.factory.ack_message(
                    sm.syn_number, sm.expected_syn
                ).to_bytes(),
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
                self.log_error("retry limit reached")
                return sm.finished
            self.retries -= 1
            sm.sock.sendto(
                sm.factory.finack_message(
                    sm.syn_number, sm.expected_syn
                ).to_bytes(),
                sm.destination_address,
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
                ack_message.header.syn_number == expected_syn
            ):
                self.log_error("wrong message received")
                return sm.fin_received
            return sm.finished

    class Finished(State):
        pass
