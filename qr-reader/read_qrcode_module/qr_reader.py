# ข้อมูลที่ได้จากการสแกน QR Code
import json
import os
from typing import List, Dict, Any


class QRData:
    def __init__(self, token: str, location: str, status: int, timestamp: int):
        # NOTE: previously you had "timestamp=int" which passed the type <class 'int'>!
        self.token = token
        self.location = location
        self.status = status  # 1 = check-in, 0 = check-out
        self.timestamp = timestamp  # epoch seconds
        self.qr_log = "qr_log.json"
        self._max_keep = 800

    # ---------- helpers ----------

    def _valid(self) -> bool:
        # enforce 22-char token + status {0,1} + sane timestamp
        return (
            isinstance(self.token, str)
            and len(self.token) == 22
            and self.status in (0, 1)
            and isinstance(self.timestamp, int)
            and self.timestamp > 0
        )

    def _read_all(self) -> List[Dict[str, Any]]:
        if not os.path.exists(self.qr_log) or os.path.getsize(self.qr_log) == 0:
            return []
        try:
            with open(self.qr_log, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            # corrupted file -> start fresh
            return []

    def _write_all(self, rows: List[Dict[str, Any]]):
        # keep only the tail
        if len(rows) > self._max_keep:
            rows = rows[-self._max_keep :]

        tmp = self.qr_log + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(rows, f, indent=4, ensure_ascii=False)
        os.replace(tmp, self.qr_log)  # atomic on the same filesystem

    # ---------- API ----------

    def get_data(self) -> str:
        return f"{self.token},{self.location},{self.status},{self.timestamp}"

    def compress_data(self) -> Dict[str, Any]:
        if not self._valid():
            return {}
        return {
            "token": self.token,
            "location": self.location,
            "check": self.status,
            "epoch": self.timestamp,
        }

    def set_status(self, status: int):
        self.status = status

    def write_data(self):
        obj = self.compress_data()
        if not obj:
            return  # do not write invalid/empty rows
        rows = self._read_all()
        rows.append(obj)
        self._write_all(rows)

    def write_replace_last_checkin(self):
        """Replace the last 'check == 1' row for this token with the new one; append if none."""
        obj = self.compress_data()
        if not obj:
            return

        rows = self._read_all()

        # find last matching check-in for this token
        idx = None
        for i in range(len(rows) - 1, -1, -1):
            row = rows[i]
            if row.get("token") == self.token and row.get("check") == 1:
                # If you also want to require same station, add:
                # and row.get("location") == self.location
                idx = i
                break

        if idx is not None:
            rows[idx] = obj
        else:
            rows.append(obj)

        self._write_all(rows)
