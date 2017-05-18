# author: Hendrik Werner s4549775
# author: Constantin Blach s4329872
import struct

import zlib
from pprint import pformat


class BTCPHeader(object):
    syn_mask = 0b001
    ack_mask = 0b010
    fin_mask = 0b100

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

    def __str__(self):
        return "bTCP Header:\n" + pformat(self.__dict__)

    @property
    def syn(self) -> bool:
        return bool(self._flags & BTCPHeader.syn_mask)

    @syn.setter
    def syn(self, on):
        if on:
            self._flags |= BTCPHeader.syn_mask
        else:
            self._flags &= ~(BTCPHeader.syn_mask)

    @property
    def ack(self) -> bool:
        return bool(self._flags & BTCPHeader.ack_mask)

    @ack.setter
    def ack(self, on):
        if on:
            self._flags |= BTCPHeader.ack_mask
        else:
            self._flags &= ~(BTCPHeader.ack_mask)

    @property
    def fin(self) -> bool:
        return bool(self._flags & BTCPHeader.fin_mask)

    @fin.setter
    def fin(self, on):
        if on:
            self._flags |= BTCPHeader.fin_mask
        else:
            self._flags &= ~(BTCPHeader.fin_mask)

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
