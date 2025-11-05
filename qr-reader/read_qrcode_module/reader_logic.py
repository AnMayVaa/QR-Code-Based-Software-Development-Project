# reader_logic.py
import time
import json
import os
from typing import Dict, Any

QR_LOG = "qr_log.json"


class ReaderLogic:
    """
    Stateless-ish core: given (token, current station, timers) decide outcome.
    Keeps a small in-memory map of open check-ins so we don't scan the whole log each time.
    """

    def __init__(self, location: str, cooldown: int, checkin_checkout_duration: int):
        self.location = location
        self.cooldown = cooldown
        self.checkin_checkout_duration = checkin_checkout_duration
        # token -> {"ts": last_checkin_epoch, "loc": last_location} for OPEN sessions only
        self.scan_history: Dict[str, Dict[str, Any]] = self._load_open_sessions()

    # ---------- persistence helpers ----------

    def _load_open_sessions(self) -> Dict[str, Dict[str, Any]]:
        """
        Walk the tail of qr_log.json (up to 800) newest->oldest.
        For each token, take the *most recent* record:
          - if status==1 => user is currently OPEN at that location
          - if status==0 => user is currently CLOSED (skip)
        """
        if not os.path.exists(QR_LOG) or os.path.getsize(QR_LOG) == 0:
            return {}
        try:
            with open(QR_LOG, "r", encoding="utf-8") as f:
                all_logs = json.load(f)
        except Exception:
            return {}

        history: Dict[str, Dict[str, Any]] = {}
        for row in reversed(all_logs[-800:]):
            token = row.get("token")
            if not token or token in history:
                continue
            if row.get("status") == 1:
                history[token] = {
                    "ts": int(row.get("timestamp", 0)),
                    "loc": row.get("location"),
                }
            # if latest is status==0, they are closed => do not add
        return history

    # ---------- core state machine ----------

    def read_qr(self, token: str) -> Dict[str, Any]:
        """
        One scan decides:
          - New token  -> CHECK-IN (status=1)
          - Same token ->
              * if different station     : error (must checkout there first)
              * if dt > stay_duration    : CHECK-OUT (status=0)
              * if dt <= cooldown        : 'Wait...' error
              * else                     : RE-CHECK-IN (status=1)
                                           and set replace_last=True iff dt <= half_duration
        Returns: dict with keys: status, message, qr_data (when status in {0,1}),
                                 existed (bool), replace_last (optional bool)
        """
        now = int(time.time())
        existed = token in self.scan_history

        if not existed:
            # First check-in at this station
            self.scan_history[token] = {"ts": now, "loc": self.location}
            return {
                "status": 1,
                "message": "Checked in",
                "qr_data": f"{token},{self.location},1,{now}",
                "existed": False,
            }

        prev = self.scan_history[token]
        prev_ts, prev_loc = int(prev["ts"]), prev["loc"]
        if prev_loc != self.location:
            return {
                "status": -1,
                "message": f"Already checked in at {prev_loc}. Please checkout there first.",
                "qr_data": "",
                "existed": True,
            }

        dt = now - prev_ts
        stay = int(self.checkin_checkout_duration)
        half = stay // 2

        # matured -> checkout automatically
        if dt > stay:
            self.scan_history.pop(token, None)
            return {
                "status": 0,
                "message": "Checked out",
                "qr_data": f"{token},{self.location},0,{now}",
                "existed": True,
            }

        # rate-limit noise
        if dt <= int(self.cooldown):
            return {"status": -1, "message": "Wait...", "qr_data": "", "existed": True}

        # still within stay window -> treat as re-check-in
        # refresh epoch and (optionally) request JSON replacement
        self.scan_history[token] = {"ts": now, "loc": self.location}
        result = {
            "status": 1,
            "message": "Rechecked in",
            "qr_data": f"{token},{self.location},1,{now}",
            "existed": True,
        }
        if dt <= half:
            # Tell the caller to replace the *last* check-in row for this token
            result["replace_last"] = True
        return result


# ---------- Forced mode helpers (controller calls the module-level function) ----------


def apply_forced_mode(
    qr_reader: ReaderLogic, token: str, result: Dict[str, Any], forced_mode: int
) -> Dict[str, Any]:
    """
    forced_mode == 0 : FORCE CHECK-OUT (only at same station as open session)
    forced_mode == 1 : FORCE CHECK-IN  (blocked if open elsewhere)
      - if forcing check-in while within first half of stay -> mark replace_last=True
    """
    try:
        now_ts = int(time.time())
        existed = token in qr_reader.scan_history
        prev_loc = qr_reader.scan_history[token]["loc"] if existed else None

        if forced_mode == 0:
            if not existed:
                result.update(
                    status=-1,
                    message=f"You haven't checked in at {qr_reader.location}. Please check in here first.",
                )
                return result
            if prev_loc != qr_reader.location:
                result.update(
                    status=-1,
                    message=f"You're already checked in at {prev_loc}. Please checkout there first.",
                )
                return result
            qr_reader.scan_history.pop(token, None)
            result.update(status=0, message="Checked out")
            return result

        if forced_mode == 1:
            if existed and prev_loc and prev_loc != qr_reader.location:
                result.update(
                    status=-1,
                    message=f"Already checked in at {prev_loc}. Checkout there first.",
                )
                return result

            # decide replace_last on half-window, if there was an earlier check-in here
            replace = False
            if existed and prev_loc == qr_reader.location:
                prev_ts = int(qr_reader.scan_history[token]["ts"])
                if now_ts - prev_ts <= int(qr_reader.checkin_checkout_duration) // 2:
                    replace = True

            qr_reader.scan_history[token] = {"ts": now_ts, "loc": qr_reader.location}
            result.update(
                status=1, message=("Rechecked in" if existed else "Checked in")
            )
            if replace:
                result["replace_last"] = True
            return result

        return result
    except Exception:
        return result
