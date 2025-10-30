# ข้อมูลที่ได้จากการสแกน OR Code
import json
import os


class QRData:
    def __init__(self, token, location, status, timestamp=int):
        self.token = token
        self.location = location
        self.status = status
        self.timestamp = timestamp
        self.qr_log = "qr_log.json"

    def get_data(self):
        return f"{self.token},{self.location},{self.status},{self.timestamp}"

    def compress_data(self) -> dict:
        if len(self.token) == 22:
            return {
                "token": self.token,
                "location": self.location,
                "check": self.status,
                "epoch": self.timestamp,
            }
        return {}

    def set_status(self, status):
        self.status = status

    def write_data(self):
        qr_obj = self.compress_data()
        all_logs = []
        try:
            if os.path.exists(self.qr_log) and os.path.getsize(self.qr_log) > 0:
                with open(self.qr_log, "r", encoding="UTF-8") as log_file:
                    all_logs = json.load(log_file)
            all_logs.append(qr_obj)

            if len(all_logs) > 800:
                all_logs = all_logs[-800:]
            with open(self.qr_log, "w", encoding="UTF-8") as log_file:
                json.dump(all_logs, log_file, indent=4, ensure_ascii=False)
        except json.JSONDecodeError:
            with open(self.qr_log, "w", encoding="UTF-8") as log_file:
                json.dump([qr_obj], log_file, indent=4, ensure_ascii=False)

        except Exception as e:
            print(f"Log file error: {e}")
