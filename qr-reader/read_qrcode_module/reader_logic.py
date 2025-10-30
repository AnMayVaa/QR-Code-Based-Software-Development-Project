import time
import json
import os
import pytz
from datetime import datetime

timezone = pytz.timezone("Asia/Bangkok")
time_format = "%H:%M"

class ReaderLogic:
    def __init__(self, location, cooldown, checkin_checkout_duration):
        self.location = location
        self.cooldown = cooldown
        self.checkin_checkout_duration = checkin_checkout_duration
        self.qr_log = "qr_log.json"
        self.scan_history = self.load_data()

    def load_data(self):
        if not os.path.exists("qr_log.json") or os.path.getsize("qr_log.json") == 0:
            print("QR Log created")
            return {}
        try:
            with open("qr_log.json", "r", encoding="UTF-8") as log_file:
                history = {}
                all_logs = json.load(log_file)
                all_logs = all_logs[-800:]
                for log in reversed(all_logs):
                    token = log.get("token")
                    timestamp = log.get("epoch")
                    if token and timestamp and token not in history:
                        if log.get("check") == 1:
                            history[token] = timestamp
        except Exception as e:
            print(f"Log file error: {e}")
            return {}
        return history

    def read_qr(self, token):
        timestamp = int(time.time())
        existed_before = token in self.scan_history
        if not existed_before: # check in
            status = 1
            self.scan_history[token] = timestamp
            message = "Checked in"
            qr_data = f"{token},{self.location},{status},{timestamp}"
            return {
                "status": status,
                "message": message,
                "qr_data": qr_data,
                "existed": existed_before
            }
        
        last_scan_time = self.scan_history[token]
        time_diff = timestamp - last_scan_time

        if time_diff > self.checkin_checkout_duration: # check out
            status = 0
            self.scan_history.pop(token, None)
            message = "Checked out"
            qr_data = f"{token},{self.location},{status},{timestamp}"
            return {
                "status": status,
                "message": message,
                "qr_data": qr_data,
                "existed": existed_before,
            }

        remain_sec = self.checkin_checkout_duration - time_diff
        if 0 < remain_sec <= self.checkin_checkout_duration / 2: # after check in, before check out
            status = -1
            message = "Too soon to checkout"
            next_checkout_epoch = last_scan_time + self.checkin_checkout_duration
            next_checkout_str = datetime.fromtimestamp(next_checkout_epoch, tz=timezone).strftime(time_format)

            return {
                "status": status,
                "message": message,
                "qr_data": "",
                "existed": existed_before,
                "next_checkout_str": next_checkout_str,  
            }

        if time_diff <= self.cooldown:
            status = -1
            message = "Wait..."
            return {
                "status": status,
                "message": message,
                "qr_data": "",
                "existed": existed_before,
            }

        status = 1 # re-check in
        self.scan_history[token] = timestamp
        message = "Rechecked in"
        qr_data = f"{token},{self.location},{status},{timestamp}"
        return {
            "status": status,
            "message": message,
            "qr_data": qr_data,
            "existed": existed_before,
        }
    
    @staticmethod
    def poll_mode_from_serial(ser, current_mode):
        try:
            updated_mode = current_mode
            # อ่านทุกอย่างที่รออยู่ในบัฟเฟอร์ตอนนี้
            while getattr(ser, "in_waiting", 0):
                raw = ser.readline()
                try:
                    line = raw.decode("utf-8", errors="ignore").strip()
                except Exception:
                    continue
                if line.startswith("MODE:"):
                    val = line[5:].strip()
                    if val in ("0", "1"):
                        updated_mode = int(val)
                        print(f"[MODE] Received mode from ESP32 => {updated_mode}")
            return updated_mode
        except Exception:
            return current_mode
    
    @staticmethod
    def apply_forced_mode(qr_reader, token, result, forced_mode):
        try:
            status = result.get("status", -1)
            message = result.get("message", "No message")
            now_ts = int(time.time())
            existed_before = bool(result.get("existed"))
            if forced_mode == 0:
                qr_reader.scan_history.pop(token, None)
                status = 0
                message = "Checked out"
            elif forced_mode == 1:
                qr_reader.scan_history[token] = now_ts
                status = 1
                message = "Rechecked in" if existed_before == 1 else "Checked in"

            result["status"] = status
            result["message"] = message
            return result
        except Exception:
            return result


def poll_mode_from_serial(ser, current_mode):
    return ReaderLogic.poll_mode_from_serial(ser, current_mode)

def apply_forced_mode(qr_reader, token, result, forced_mode):
    return ReaderLogic.apply_forced_mode(qr_reader, token, result, forced_mode)
