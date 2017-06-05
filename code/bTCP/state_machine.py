# author: Hendrik Werner s4549775
# author: Constantin Blach s4329872
import sys


class State(object):
    def __init__(
        self,
        state_machine,
    ):
        self.state_machine = state_machine

    def run(self):
        raise NotImplementedError

    def log_error(
        self,
        message: str,
    ):
        print(
            self.state_machine.__class__.__name__,
            self.__class__.__name__ + ":",
            message,
            file=sys.stderr,
        )


class StateMachine(object):
    def run(self):
        self.state = self.state.run()
