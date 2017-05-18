# author: Hendrik Werner s4549775
# author: Constantin Blach s4329872
import struct

import zlib


class BTCPHeader(object):
    def __init__(
            self,
            id: int,
            syn: int,
            ack: int,
            window_size: int,
            data_length: int,
            raw_flags: int = 0,
    ):
        self.id = id
        self.syn_number = syn
        self.ack_number = ack
        self.window_size = window_size
        self.data_length = data_length
        self._flags = raw_flags

    def to_bytes(self):
        data = struct.pack(
            "!LHHBBH",
            self.id,
            self.syn_number,
            self.ack_number,
            self._flags,
            self.window_size,
            self.data_length,
        )
        return data + struct.pack("L", zlib.crc32(data))
