import unittest
import os
import json
import time
import secrets
import base64
from read_qrcode_module.qr_reader import QRData
from read_qrcode_module.reader_logic import ReaderLogic


class QRLogTest(unittest.TestCase):
    def setUp(self):
        self.test_log = "test1_qr_log.json"
        self.test_location = "Test"

    def tearDown(self):
        if os.path.exists(self.test_log):
            os.remove(self.test_log)

    def test_qr_log(self):
        for i in range(1000):
            token = base64.urlsafe_b64encode(secrets.token_bytes(22)).decode("utf-8")[
                :22
            ]
            qr_data = QRData(token, self.test_location, 1, int(time.time()))
            qr_data.qr_log = self.test_log
            qr_data.write_data()

        with open(self.test_log, "r", encoding="UTF-8") as log_file:
            all_logs = json.load(log_file)
            self.assertEqual(len(all_logs), 800)

        reader = ReaderLogic(self.test_location, 10, 300)
        self.assertEqual(len(reader.scan_history), 800)


if __name__ == "__main__":
    unittest.main(verbosity=2)
