# author: Hendrik Werner s4549775
# author: Constantin Blach s4329872


class State(object):
    def run(self):
        raise NotImplementedError


class StateMachine(object):
    def __init__(
        self,
        initial_state: State,
    ):
        self.state = initial_state

    def run(self):
        self.state = self.state.run()
