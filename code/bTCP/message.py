# author: Hendrik Werner s4549775
# author: Constantin Blach s4329872
import struct

import zlib

from bTCP.exceptions import ChecksumMismatch
from bTCP.header import BTCPHeader


class BTCPMessage(object):
    payload_size = 1000

    @classmethod
    def from_bytes(cls, data: bytes):
        header = BTCPHeader.from_bytes(data[:12])
        checksum = struct.unpack("!L", data[12:16])[0]
        payload = data[16:16 + header.data_length]
        if checksum == zlib.crc32(data[:12] + payload):
            return cls(header, payload)
        else:
            raise ChecksumMismatch()

    def __init__(
        self,
        header: BTCPHeader,
        payload: bytes,
    ):
        if len(payload) > BTCPMessage.payload_size:
            raise AttributeError("Payload is too big.")
        self.header = header
        self.payload = payload
        self.header.data_length = len(payload)

    def __str__(self):
        header = str(self.header).replace("\t", "\t\t")
        return (
            "bTCP Message:\n\t" +
            header +
            "\n\tpayload: " +
            str(self.payload)
        )

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__) and
            self.__dict__ == other.__dict__
        )

    def to_bytes(self) -> bytes:
        header_bytes = self.header.to_bytes()
        return header_bytes + struct.pack("!L", zlib.crc32(
            header_bytes + self.payload
        )) + self.payload.ljust(BTCPMessage.payload_size, b"\0")


class MessageFactory(object):
    def __init__(
        self,
        stream_id: int,
        window_size: int,
    ):
        self.stream_id = stream_id
        self.window_size = window_size

    def message(
        self,
        syn_number: int,
        ack_number: int,
        payload: bytes=b"",
    ) -> BTCPMessage:
        return BTCPMessage(
            BTCPHeader(
                id=self.stream_id,
                syn=syn_number,
                ack=ack_number,
                raw_flags=0,
                window_size=self.window_size,
            ),
            payload
        )

    def syn_message(
        self,
        syn_number: int,
        ack_number: int,
    ) -> BTCPMessage:
        message = self.message(syn_number, ack_number)
        message.header.syn = True
        return message

    def ack_message(
        self,
        syn_number: int,
        ack_number: int,
    ) -> BTCPMessage:
        message = self.message(syn_number, ack_number)
        message.header.ack = True
        return message

    def fin_message(
        self,
        syn_number: int,
        ack_number: int,
    ) -> BTCPMessage:
        message = self.message(syn_number, ack_number)
        message.header.fin = True
        return message
