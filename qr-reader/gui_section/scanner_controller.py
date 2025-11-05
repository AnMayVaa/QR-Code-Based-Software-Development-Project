import time
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal

from gui_section.app_config import (
    TOKEN_RE,
    TERMINATOR,
    SC_MINLEN,
    SC_TMO_MS,
    RATE_LIMIT_S,
    TZ,
    TIME_FMT_HMS,
)
from gui_section.localization import to_thai_message
from read_qrcode_module.reader_logic import ReaderLogic, apply_forced_mode
from read_qrcode_module.qr_reader import QRData


class ScannerController(QObject):
    status_text = pyqtSignal(str, bool, bool)  # text, ok, error
    clear_input = pyqtSignal()
    token_update = pyqtSignal(str)

    def __init__(
        self, location: str, scan_cooldown: int, stay_duration: int, parent=None
    ):
        super().__init__(parent)
        self.location = location
        # NEW: keep our own copies
        self._scan_cooldown = scan_cooldown
        self._stay_duration = stay_duration

        self.reader = ReaderLogic(
            self.location, self._scan_cooldown, self._stay_duration
        )
        self.forced_mode = None  # None / 1 / 0
        self.last_scan_ts = 0.0

        self.buffer = ""
        self._last_time = time.time()
        self._last_location_change = time.time()

        self.output_path = None  # optional file
        self.clipboard_enabled = False

    def set_location(self, new_loc: str):
        new_loc = (new_loc or "").strip()
        if not new_loc:
            return
        # update in-place (don’t rebuild ReaderLogic)
        self.location = new_loc
        if getattr(self, "reader", None):
            self.reader.location = new_loc

        # emit the message right here (so MainWindow sees it immediately)
        self.status_text.emit(f'ตั้งค่าสถานที่เป็น "{new_loc}" แล้ว', True, False)

    def set_forced_mode(self, mode):  # None, 1, 0
        self.forced_mode = mode

    # ---- buffer handling from GUI ----
    def on_text_delta(self, new_text: str, old_len: int = 0):
        # ต่อท้ายเฉพาะตัวอักษรที่เพิ่มจากความยาวเดิม
        if old_len <= len(new_text):
            self.buffer += new_text[old_len:]
        else:
            # ข้อความถูกล้าง/สั้นลง (เช่นผู้ใช้กดลบ) — เริ่มใหม่จากที่มี
            self.buffer = new_text

        self._last_time = time.time()
        # ถ้ามีตัวจบ (CR/LF/CRLF) ให้ finalize ทันที
        if TERMINATOR and self.buffer.endswith(TERMINATOR):
            payload = self.buffer[: -len(TERMINATOR)] if TERMINATOR else self.buffer
            self._finalize_payload(payload.strip())

    def poll_timeout_finalize(self, is_active_window: bool):
        if not self.buffer:
            return
        if (time.time() - self._last_time) * 1000.0 > SC_TMO_MS:
            if is_active_window:
                self._finalize_payload(self.buffer.strip())

    # ---- core finalize ----
    def _finalize_payload(self, payload: str):
        self.buffer = ""
        self.clear_input.emit()
        if not payload or len(payload) < SC_MINLEN:
            return

        now = time.time()
        if now - self.last_scan_ts < RATE_LIMIT_S:
            return
        self.last_scan_ts = now

        token = payload.strip()
        if not TOKEN_RE.match(token):
            self.status_text.emit(f"ข้าม: รูปแบบโทเคนไม่ถูกต้อง → {token!r}", False, True)
            return

        result = self.reader.read_qr(token)
        fm = 1 if self.forced_mode == 1 else 0 if self.forced_mode == 0 else None
        if fm is not None:
            result = apply_forced_mode(self.reader, token, result, fm)

        status = result.get("status", -1)
        thai = to_thai_message(result, self.location)
        now_str = datetime.now(TZ).strftime(TIME_FMT_HMS)

        # persist log
        if status != -1 and result.get("qr_data"):
            try:
                q = QRData(token, self.location, status, int(time.time()))
                if status == 1 and result.get("replace_last"):
                    q.write_replace_last_checkin()  # <— replace with new epoch
                else:
                    q.write_data()  # <— default append
            except Exception:
                try:
                    with open("qr_log.json", "w", encoding="utf-8") as f:
                        f.write("[]")
                    # retry once
                    q = QRData(token, self.location, status, int(time.time()))
                    if status == 1 and result.get("replace_last"):
                        q.write_replace_last_checkin()
                    else:
                        q.write_data()
                except Exception:
                    pass

        self.status_text.emit(f"{thai}  เวลา {now_str}", status in (0, 1), False)

        if status in (0, 1):
            line = f"{token},{status},{now_str}"
            if self.clipboard_enabled:
                # GUI will set clipboard; here just pass text via signal if you prefer
                pass
            if self.output_path:
                try:
                    with open(self.output_path, "a", encoding="utf-8") as fp:
                        fp.write(line + "\n")
                except Exception:
                    self.status_text.emit("ไม่สามารถเขียนไฟล์เอาต์พุตได้", False, True)
