# author: Hendrik Werner s4549775
# author: Constantin Blach s4329872


class State(object):
    def __init__(
        self,
        state_machine,
    ):
        self.state_machine = state_machine

    def run(self):
        raise NotImplementedError


class StateMachine(object):
    def run(self):
        self.state = self.state.run()
