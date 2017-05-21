# author: Hendrik Werner s4549775
# author: Constantin Blach s4329872
import socket


class State(object):
    def run(self, sock):
        raise NotImplementedError


class StateMachine(object):
    def __init__(
            self,
            initial_state: State,
            sock: socket.socket,
    ):
        self.state = initial_state
        self.sock = sock

    def run(self, sock: socket.socket):
        self.state = self.state.run(self.sock)
