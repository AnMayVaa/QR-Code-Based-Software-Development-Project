import unittest
import os
import json
import time
import secrets
import base64
from read_qrcode_module.qr_reader import QRData


class QRReaderTest(unittest.TestCase):
    def setUp(self):
        self.test_token = base64.urlsafe_b64encode(secrets.token_bytes(22)).decode(
            "utf-8"
        )[:22]
        self.test_location = "Test"
        self.test_status = 1
        self.test_timestamp = int(time.time())
        self.test_log_file = "test2_qr_log.json"
        if os.path.exists(self.test_log_file):
            os.remove(self.test_log_file)
        self.test_qr_code = QRData(
            self.test_token, self.test_location, self.test_status, self.test_timestamp
        )
        self.test_qr_code.qr_log = self.test_log_file

    def tearDown(self):
        if os.path.exists(self.test_log_file):
            os.remove(self.test_log_file)

    # ทดสอบ QR_Data
    def test1_init(self):
        print("Testing initialization")
        self.assertEqual(self.test_qr_code.token, self.test_token)
        self.assertEqual(self.test_qr_code.location, self.test_location)
        self.assertEqual(self.test_qr_code.status, self.test_status)
        self.assertEqual(self.test_qr_code.timestamp, self.test_timestamp)

    # ทดสอบการรับค่าจาก get_data()
    def test2_get_data(self):
        print("Testing get_data()")
        expected_result = f"{self.test_token},{self.test_location},{self.test_status},{self.test_timestamp}"
        self.assertEqual(self.test_qr_code.get_data(), expected_result)

    # ทดสอบการอัดเป็น json
    def test3_compress_data(self):
        print("Testing compress_data()")
        expected_result = {
            "token": self.test_token,
            "location": self.test_location,
            "check": self.test_status,
            "epoch": self.test_timestamp,
        }
        self.assertEqual(self.test_qr_code.compress_data(), expected_result)

    # ทดสอบการสร้างไฟล์ log และการเก็บข้อมูลครั้งแรก
    def test4_create_log(self):
        print("Testing write_data()")
        self.test_qr_code.write_data()
        self.assertTrue(os.path.exists(self.test_log_file))

        with open(self.test_log_file, "r", encoding="utf-8") as log_file:
            logs = json.load(log_file)
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0]["token"], self.test_token)
            self.assertEqual(logs[0]["check"], self.test_status)

    # ทดสอบการเก็บข้อมูลครั้งที่สอง (ครั้งที่ n)
    def test5_append_log(self):
        print("Another testing write_data()")
        self.test_qr_code.write_data()

        another_token = base64.urlsafe_b64encode(secrets.token_bytes(22)).decode(
            "utf-8"
        )[:22]
        another_location = "Test"
        another_status = 1
        another_timestamp = int(time.time() + 10)
        another_qr_data = QRData(
            another_token, another_location, another_status, another_timestamp
        )
        another_qr_data.qr_log = self.test_log_file
        another_qr_data.write_data()

        with open(self.test_log_file, "r", encoding="utf-8") as log_file:
            logs = json.load(log_file)
            self.assertEqual(len(logs), 2)
            self.assertEqual(logs[1]["token"], another_token)
            self.assertEqual(logs[1]["check"], another_status)

    # ทดสอบการเก็บข้อมูลที่ไม่ตรงตามเงื่อนไข
    def test6_handle_bad_log(self):
        print("Handling bad log")
        with open(self.test_log_file, "w", encoding="utf-8") as log_file:
            log_file.write("this is not valid json")

        self.test_qr_code.write_data()
        with open(self.test_log_file, "r", encoding="utf-8") as log_file:
            logs = json.load(log_file)
            self.assertEqual(len(logs), 1)
            self.assertEqual(logs[0]["token"], self.test_token)
            self.assertEqual(logs[0]["check"], self.test_status)


if __name__ == "__main__":
    unittest.main(verbosity=2)
