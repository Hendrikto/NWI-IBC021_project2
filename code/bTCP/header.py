# author: Hendrik Werner s4549775
# author: Constantin Blach s4329872
import bTCP.message
import struct

from pprint import pformat


class BTCPHeader(object):
    format = struct.Struct("!LHHBBH")
    syn_mask = 0b001
    ack_mask = 0b010
    fin_mask = 0b100

    @classmethod
    def from_bytes(cls, data: bytes):
        return cls(*BTCPHeader.format.unpack(data))

    def __init__(
        self,
        id: int,
        syn: int,
        ack: int,
        raw_flags: int,
        window_size: int,
        data_length: int=0,
    ):
        self.id = id
        self.syn_number = syn
        self.ack_number = ack
        self.window_size = window_size
        self.data_length = data_length
        self._flags = raw_flags

    def __str__(self):
        return "bTCP Header:\n\t" + pformat(self.__dict__).replace(
            "\n", "\n\t"
        )

    def __eq__(self, other):
        return (
            isinstance(other, self.__class__) and
            self.__dict__ == other.__dict__
        )

    @property
    def data_length(self):
        return self._data_length

    @data_length.setter
    def data_length(self, length):
        if length > bTCP.message.BTCPMessage.payload_size:
            raise ValueError("The payload cannot be this big.")
        self._data_length = length

    @property
    def syn(self) -> bool:
        return bool(self._flags & BTCPHeader.syn_mask)

    @syn.setter
    def syn(self, on: bool) -> None:
        if on:
            self._flags |= BTCPHeader.syn_mask
        else:
            self._flags &= ~(BTCPHeader.syn_mask)

    @property
    def ack(self) -> bool:
        return bool(self._flags & BTCPHeader.ack_mask)

    @ack.setter
    def ack(self, on: bool) -> None:
        if on:
            self._flags |= BTCPHeader.ack_mask
        else:
            self._flags &= ~(BTCPHeader.ack_mask)

    @property
    def fin(self) -> bool:
        return bool(self._flags & BTCPHeader.fin_mask)

    @fin.setter
    def fin(self, on: bool) -> None:
        if on:
            self._flags |= BTCPHeader.fin_mask
        else:
            self._flags &= ~(BTCPHeader.fin_mask)

    def to_bytes(self) -> bytes:
        return BTCPHeader.format.pack(
            self.id,
            self.syn_number,
            self.ack_number,
            self._flags,
            self.window_size,
            self.data_length,
        )
