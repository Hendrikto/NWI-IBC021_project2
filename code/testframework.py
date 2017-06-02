import os
import sys
import unittest

import subprocess

timeout = 100
winsize = 100
intf = "lo"
netem_add = "sudo tc qdisc add dev {} root netem".format(intf)
netem_change = "sudo tc qdisc change dev {} root netem {}".format(intf, "{}")
netem_del = "sudo tc qdisc del dev {} root netem".format(intf)


def run_command(command, cwd=None, shell=True):
    """Run command with no output piping"""
    try:
        return subprocess.Popen(command, shell=shell, cwd=cwd)
    except Exception as ex:
        print("problem running command:", command, "\n\tproblem:", ex)


def run_command_blocking(command, cwd=None, shell=True):
    process = run_command(command, cwd, shell)
    process.wait()
    if process.returncode:
        print("problem running command:", command)
        print("\treturn code:", process.returncode)


class TestbTCPFramework(unittest.TestCase):
    """Test cases for bTCP"""

    def setUp(self):
        """Prepare for testing"""
        # default netem rule (does nothing)
        run_command_blocking(netem_add)

        # launch localhost server
        self.server_process = run_command("python3 bTCP_server.py -o out.file")

    def tearDown(self):
        """Clean up after testing"""
        # clean the environment
        run_command_blocking(netem_del)
        os.remove("out.file")

        self.server_process.wait()

    def test_ideal_network(self):
        """reliability over an ideal framework"""
        # setup environment (nothing to set)

        # launch localhost client connecting to server

        # client sends content to server

        # server receives content from client

        # content received by server matches the content sent by client

    def test_flipping_network(self):
        """reliability over network with bit flips
        (which sometimes results in lower layer packet loss)"""
        # setup environment
        run_command(netem_change.format("corrupt 1%"))

        # launch localhost client connecting to server

        # client sends content to server

        # server receives content from client

        # content received by server matches the content sent by client

    def test_duplicates_network(self):
        """reliability over network with duplicate packets"""
        # setup environment
        run_command(netem_change.format("duplicate 10%"))

        # launch localhost client connecting to server

        # client sends content to server

        # server receives content from client

        # content received by server matches the content sent by client

    def test_lossy_network(self):
        """reliability over network with packet loss"""
        # setup environment
        run_command(netem_change.format("loss 10% 25%"))

        # launch localhost client connecting to server

        # client sends content to server

        # server receives content from client

        # content received by server matches the content sent by client

    def test_reordering_network(self):
        """reliability over network with packet reordering"""
        # setup environment
        run_command(netem_change.format("delay 20ms reorder 25% 50%"))

        # launch localhost client connecting to server

        # client sends content to server

        # server receives content from client

        # content received by server matches the content sent by client

    def test_delayed_network(self):
        """reliability over network with delay relative to the timeout value"""
        # setup environment
        run_command(netem_change.format("delay " + str(timeout) + "ms 20ms"))

        # launch localhost client connecting to server

        # client sends content to server

        # server receives content from client

        # content received by server matches the content sent by client

    def test_allbad_network(self):
        """reliability over network with all of the above problems"""

        # setup environment
        run_command(netem_change.format(
            "corrupt 1% duplicate 10% loss 10% 25% delay 20ms reorder 25% 50%"
        ))

        # launch localhost client connecting to server

        # client sends content to server

        # server receives content from client

        # content received by server matches the content sent by client


# def test_command(self):
#     # command=['dir','.']
#     out = run_command_with_output("dir .")
#     print(out)


if __name__ == "__main__":
    # Parse command line arguments
    import argparse

    parser = argparse.ArgumentParser(description="bTCP tests")
    parser.add_argument(
        "-w", "--window", help="Define bTCP window size used", type=int,
        default=100
    )
    parser.add_argument(
        "-t", "--timeout", help="Define the timeout value used (ms)", type=int,
        default=timeout
    )
    args, extra = parser.parse_known_args()
    timeout = args.timeout
    winsize = args.window

    # Pass the extra arguments to unittest
    sys.argv[1:] = extra

    # Start test suite
    unittest.main()
