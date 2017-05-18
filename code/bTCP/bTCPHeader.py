# author: Hendrik Werner s4549775
# author: Constantin Blach s4329872

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
        self.syn = syn
        self.ack = ack
        self.window_size = window_size
        self.data_length = data_length
        self._flags = raw_flags
