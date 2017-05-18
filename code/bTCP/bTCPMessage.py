# author: Hendrik Werner s4549775
# author: Constantin Blach s4329872
import struct

import zlib

from bTCP.bTCPHeader import BTCPHeader


class BTCPMessage(object):
    payload_size = 1000

    def __init__(
            self,
            header: BTCPHeader,
            payload: bytes,
    ):
        self.header = header
        self.payload = payload

    def to_bytes(self):
        header_bytes = self.header.to_bytes()
        return header_bytes + struct.pack("L", zlib.crc32(
            header_bytes + self.payload
        )) + self.payload.ljust(BTCPMessage.payload_size, b"\0")
