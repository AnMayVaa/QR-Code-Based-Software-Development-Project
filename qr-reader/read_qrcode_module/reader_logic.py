# --- replace the whole ReaderLogic class with this version ---

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
        # token -> {"ts": last_checkin_epoch, "loc": last_location}
        self.scan_history = self.load_data()

    def load_data(self):
        """Load last known OPEN check-ins (check==1), keeping their location."""
        if not os.path.exists(self.qr_log) or os.path.getsize(self.qr_log) == 0:
            print("QR Log created")
            return {}
        try:
            with open(self.qr_log, "r", encoding="UTF-8") as log_file:
                history = {}
                all_logs = json.load(log_file)[-800:]
                # take the newest OPEN entry per token
                for log in reversed(all_logs):
                    token = log.get("token")
                    ts = log.get("epoch")
                    loc = log.get("location")
                    if token and ts and token not in history:
                        if log.get("check") == 1:
                            history[token] = {"ts": ts, "loc": loc}
        except Exception as e:
            print(f"Log file error: {e}")
            return {}
        return history

    def read_qr(self, token):
        """Enforce: must checkout at previous location before checking in elsewhere."""
        now = int(time.time())
        existed = token in self.scan_history

        # brand-new check-in
        if not existed:
            self.scan_history[token] = {"ts": now, "loc": self.location}
            return {
                "status": 1,
                "message": "Checked in",
                "qr_data": f"{token},{self.location},1,{now}",
                "existed": False,
            }

        # someone already checked in
        prev = self.scan_history[token]
        prev_ts, prev_loc = prev["ts"], prev["loc"]

        # (NEW RULE) different booth -> block until checkout at previous booth
        if prev_loc != self.location:
            return {
                "status": -1,
                "message": f"Already checked in at {prev_loc}. Please checkout there first.",
                "qr_data": "",
                "existed": True,
                "prev_location": prev_loc,
            }

        # same booth logic as before
        dt = now - prev_ts

        # eligible to checkout (duration elapsed)
        if dt > self.checkin_checkout_duration:
            self.scan_history.pop(token, None)
            return {
                "status": 0,
                "message": "Checked out",
                "qr_data": f"{token},{self.location},0,{now}",
                "existed": True,
            }

        # too soon to checkout (first half of window)
        remain = self.checkin_checkout_duration - dt
        if 0 < remain <= self.checkin_checkout_duration / 2:
            next_checkout_epoch = prev_ts + self.checkin_checkout_duration
            next_checkout_str = datetime.fromtimestamp(
                next_checkout_epoch, tz=timezone
            ).strftime(time_format)
            return {
                "status": -1,
                "message": "Too soon to checkout",
                "qr_data": "",
                "existed": True,
                "next_checkout_str": next_checkout_str,
            }

        # cooldown guard
        if dt <= self.cooldown:
            return {
                "status": -1,
                "message": "Wait...",
                "qr_data": "",
                "existed": True,
            }

        # re-check in (same booth) refresh timestamp
        self.scan_history[token] = {"ts": now, "loc": self.location}
        return {
            "status": 1,
            "message": "Rechecked in",
            "qr_data": f"{token},{self.location},1,{now}",
            "existed": True,
        }

    @staticmethod
    def poll_mode_from_serial(ser, current_mode):
        try:
            updated_mode = current_mode
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
        """Respect the cross-location rule in forced operations, too."""
        try:
            now_ts = int(time.time())
            existed = token in qr_reader.scan_history
            if existed:
                prev = qr_reader.scan_history[token]
                prev_loc = prev["loc"]
            else:
                prev_loc = None

            # Force CHECK-OUT only at the same booth as the open session
            if forced_mode == 0:
                if existed and prev_loc == qr_reader.location:
                    qr_reader.scan_history.pop(token, None)
                    result.update(status=0, message="Checked out")
                else:
                    # enforce “checkout at previous location”
                    where = prev_loc or "unknown"
                    result.update(status=-1, message=f"Checkout at {where} booth.")
                return result

            # Force CHECK-IN blocked if user is open at a different booth
            if forced_mode == 1:
                if existed and prev_loc and prev_loc != qr_reader.location:
                    result.update(
                        status=-1,
                        message=f"Already checked in at {prev_loc}. Checkout there first.",
                    )
                else:
                    qr_reader.scan_history[token] = {
                        "ts": now_ts,
                        "loc": qr_reader.location,
                    }
                    result.update(
                        status=1, message=("Rechecked in" if existed else "Checked in")
                    )
                return result

            return result
        except Exception:
            return result


def poll_mode_from_serial(ser, current_mode):
    return ReaderLogic.poll_mode_from_serial(ser, current_mode)


def apply_forced_mode(qr_reader, token, result, forced_mode):
    try:
        now_ts = int(time.time())
        existed = token in qr_reader.scan_history
        prev_loc = qr_reader.scan_history[token]["loc"] if existed else None

        if forced_mode == 0:  # FORCE CHECK-OUT
            if not existed:
                # never checked in anywhere
                result.update(
                    status=-1,
                    message=f"You haven't checked in at {qr_reader.location}. Please check in here first.",
                )
                return result

            if prev_loc != qr_reader.location:
                # checked in elsewhere
                result.update(
                    status=-1,
                    message=f"You're already checked in at {prev_loc}. Please checkout there first.",
                )
                return result

            # OK to checkout here
            qr_reader.scan_history.pop(token, None)
            result.update(status=0, message="Checked out")
            return result

        if forced_mode == 1:  # FORCE CHECK-IN
            # still block if open somewhere else
            if existed and prev_loc and prev_loc != qr_reader.location:
                result.update(
                    status=-1,
                    message=f"Already checked in at {prev_loc}. Checkout there first.",
                )
                return result

            qr_reader.scan_history[token] = {"ts": now_ts, "loc": qr_reader.location}
            result.update(
                status=1, message=("Rechecked in" if existed else "Checked in")
            )
            return result

        return result
    except Exception:
        return result
