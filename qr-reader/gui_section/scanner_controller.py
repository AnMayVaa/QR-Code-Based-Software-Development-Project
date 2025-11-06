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
    booth_list,
)
from gui_section.localization import to_thai_message
from read_qrcode_module.reader_logic import ReaderLogic, apply_forced_mode
from read_qrcode_module.qr_reader import QRData


class ScannerController(QObject):
    status_text = pyqtSignal(str, bool, bool)  # text, ok, error
    clear_input = pyqtSignal()
    token_update = pyqtSignal(str)
    location_changed = pyqtSignal(str)
    mode_changed = pyqtSignal(object)
    scan_event = pyqtSignal(str, str, int, int)

    def __init__(
        self, location: str, scan_cooldown: int, stay_duration: int, parent=None
    ):
        super().__init__(parent)
        self._booths = booth_list()[:] or [location]
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

    def _index_of_loc(self, loc: str) -> int:
        try:
            return self._booths.index(loc)
        except ValueError:
            return -1

    def _set_location_index(self, idx: int):
        if not self._booths:
            return
        idx %= len(self._booths)
        new_loc = self._booths[idx]
        # reuse your normal setter so it emits the green status
        self.set_location(new_loc)

    def _cycle_location(self, step: int = 1):
        if not self._booths:
            return
        i = self._index_of_loc(self.location)
        if i == -1:
            # current location not in list → add and select it
            self._booths.append(self.location)
            i = len(self._booths) - 1
        self._set_location_index(i + step)

    def submit_text(self, text: str):
        self._finalize_payload((text or "").strip())

    def set_location(self, new_loc: str):
        new_loc = (new_loc or "").strip()
        if not new_loc:
            return
        self.location = new_loc
        if getattr(self, "reader", None):
            self.reader.location = new_loc

        self.status_text.emit(f'ตั้งค่าสถานที่เป็น "{new_loc}" แล้ว', True, False)
        self.location_changed.emit(new_loc)  # ← tell UI to update dropdown

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
        # always clear the hidden field / buffer
        self.buffer = ""
        self.clear_input.emit()
        toggle = payload.upper().strip()
        if toggle == "LOC:TOGGLE":
            self._cycle_location(1)
            return
        elif toggle == "MODE:TOGGLE":
            self._cycle_mode()
            return

        payload = (payload or "").strip()
        if not payload:
            return

        # 1) SPECIAL COMMANDS: LOC:/STN:  (bypass minlen/ratelimit/regex)
        up = payload.upper()
        if up.startswith("LOC:") or up.startswith("STN:"):
            new_loc = payload.split(":", 1)[1].strip()
            if new_loc:
                self.set_location(new_loc)  # emits green status immediately
            return

        # 2) Too short? (normal scans only)
        if not payload or len(payload) < SC_MINLEN:
            return

        # 3) Rate limit (normal scans only)
        now = time.time()
        if now - self.last_scan_ts < RATE_LIMIT_S:
            return
        self.last_scan_ts = now

        # 4) Token validation
        token = payload.strip()  # your scanners feed a raw 22-char token
        if not TOKEN_RE.match(token):
            self.token_update.emit("")  # clear token line for bad input
            self.status_text.emit(f"ข้าม: รูปแบบโทเคนไม่ถูกต้อง → {token!r}", False, True)
            return
        else:
            self.token_update.emit(token)

        # 5) Reader logic (same as before)
        result = self.reader.read_qr(token)
        fm = 1 if self.forced_mode == 1 else 0 if self.forced_mode == 0 else None
        if fm is not None:
            result = apply_forced_mode(self.reader, token, result, fm)

        status = result.get("status", -1)
        thai = to_thai_message(result, self.location)
        now_str = datetime.now(TZ).strftime(TIME_FMT_HMS)

        # 6) Persist log
        if status in (0, 1):
            try:
                q = QRData(token, self.location, status, int(time.time()))
                q.write_data()
            except Exception:
                try:
                    with open("qr_log.json", "w", encoding="utf-8") as f:
                        f.write([""])  # clear file
                        q = QRData(token, self.location, status, int(time.time()))
                        q.write_data()
                except Exception:
                    pass  # give up

        # 7) UI status
        self.status_text.emit(f"{thai}  เวลา {now_str}", status in (0, 1), False)

        # 8) Optional external output
        if status in (0, 1):
            line = f"{token},{status},{now_str}"
            if self.clipboard_enabled:
                pass  # GUI handles clipboard, if you decide to emit another signal
            if self.output_path:
                try:
                    with open(self.output_path, "a", encoding="utf-8") as fp:
                        fp.write(line + "\n")
                except Exception:
                    self.status_text.emit("ไม่สามารถเขียนไฟล์เอาต์พุตได้", False, True)

    def set_mode(self, mode):
        self.forced_mode = mode
        text = {None: "โหมดอัตโนมัติ", 1: "โหมดบังคับเช็คอิน", 0: "โหมดบังคับเช็คเอาท์"}[mode]
        self.status_text.emit(f"{text}", True, False)  # green, will auto-reset
        self.mode_changed.emit(mode)  # tell UI to update radios

    def _cycle_mode(self):
        order = [None, 1, 0]  # Auto → Force In → Force Out → Auto …
        try:
            i = order.index(self.forced_mode)
        except ValueError:
            i = 0
        self.set_mode(order[(i + 1) % len(order)])
