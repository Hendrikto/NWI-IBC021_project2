import unittest

from bTCP.message import BTCPMessage
from bTCP.header import BTCPHeader


class BTCPHeaderTest(unittest.TestCase):
    def test_serialization(self):
        self.assertEqual(
            BTCPHeader(1, 2, 3, 4, 5, 6).to_bytes(),
            b"\x00\x00\x00\x01\x00\x02\x00\x03\x04\x05\x00\x06"
        )

    def test_deserialization(self):
        self.assertEqual(
            BTCPHeader.from_bytes(
                b"\x00\x00\x00\x01\x00\x02\x00\x03\x04\x05\x00\x06"
            ),
            BTCPHeader(1, 2, 3, 4, 5, 6)
        )


class BTCPMessageTest(unittest.TestCase):
    def test_padding(self):
        header = BTCPHeader(1, 2, 3, 4, 5, 6)
        self.assertEqual(
            len(BTCPMessage(header, b"short payload").to_bytes()), 1016
        )

    def test_serialization_deserialization(self):
        header = BTCPHeader(1, 2, 3, 4, 5, 6)
        message = BTCPMessage(header, b"payload")
        self.assertEqual(
            message,
            BTCPMessage.from_bytes(message.to_bytes())
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
