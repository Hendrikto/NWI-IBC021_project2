import unittest

from bTCP.bTCPMessage import BTCPMessage
from bTCP.bTCPHeader import BTCPHeader


class BTCPMessageTest(unittest.TestCase):
    def test_padding(self):
        header = BTCPHeader(1, 2, 3, 4, 5, 6)
        self.assertEqual(
            len(BTCPMessage(header, b"short payload").to_bytes()), 1016
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
