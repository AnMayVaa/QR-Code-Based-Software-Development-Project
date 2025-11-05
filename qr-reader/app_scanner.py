# app_scanner_th.py
# สแกนเนอร์เท่านั้น (ไม่มีกล้อง) — UI ภาษาไทย + สเกลตามจอ + สลับเต็มหน้าจอ + ออกด้วย q/ๆ

import os, sys, time, re, configparser
from datetime import datetime

# ---- เลือก Qt platform plugin ตาม OS ----
if sys.platform.startswith("win"):
    os.environ["QT_QPA_PLATFORM"] = "windows"
elif sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
else:
    os.environ.pop("QT_QPA_PLATFORM", None)

from PyQt5.QtCore import Qt, QTimer, QCoreApplication
from PyQt5.QtGui import QFont, QFontDatabase
from PyQt5.QtWidgets import (
    QApplication,
    QWidget,
    QLabel,
    QPushButton,
    QComboBox,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QGroupBox,
    QRadioButton,
    QCheckBox,
    QFileDialog,
    QMessageBox,
    QLineEdit,
    QToolBar,
    QAction,
)
import pytz

# ---- โมดูลโปรเจกต์ของคุณ (ไม่แก้) ----
from read_qrcode_module.reader_logic import ReaderLogic, apply_forced_mode
from read_qrcode_module.qr_reader import QRData

# -------------------- CONFIG --------------------
CONFIG_FILE = "config.ini"
cfg = configparser.ConfigParser()
cfg.read(CONFIG_FILE)

DEFAULT_LOCATION = cfg.get("Device", "Location", fallback="จุดที่ 1")
SCAN_COOLDOWN = cfg.getint("Device", "ScanCooldown", fallback=5)
STAY_DURATION = cfg.getint("Device", "StayDuration", fallback=600)


def _parse_booth_list(cfg, default_loc):
    raw = cfg.get("BoothList", "Names", fallback="").strip()
    if not raw:
        return [default_loc, "จุดที่ 2", "จุดที่ 3", "ประตูเข้า", "ประตูออก", "อื่น ๆ"]
    items = [s.strip() for s in raw.split(",")]
    items = [s for s in items if s]
    if default_loc not in items:
        items = [default_loc] + items
    seen, deduped = set(), []
    for it in items:
        key = it.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(it)
    return deduped


BOOTH_LIST = _parse_booth_list(cfg, DEFAULT_LOCATION)

# -------------------- การตั้งค่าสแกนเนอร์ --------------------
SC_TERM = cfg.get(
    "Scanner", "Terminator", fallback="CRLF"
).upper()  # CR, LF, CRLF, NONE
SC_MINLEN = cfg.getint("Scanner", "MinLength", fallback=6)
SC_TMO_MS = cfg.getint("Scanner", "TimeoutMs", fallback=250)

TERM_MAP = {"CR": "\r", "LF": "\n", "CRLF": "\r\n", "NONE": ""}
TERMINATOR = TERM_MAP.get(SC_TERM, "\r\n")

# -------------------- ค่าคงที่ --------------------
TZ = pytz.timezone("Asia/Bangkok")
TIME_FMT_HMS = "%H:%M:%S"  # ไทยนิยม 24 ชม.
TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-]{22}$")  # โทเคน base64url-ish
RATE_LIMIT_S = 1.0

QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)


# -------------------- แอปหลัก --------------------
class ScannerApp(QWidget):
    def __init__(self):
        super().__init__()
        self._load_font_thai()  # เลือกฟอนต์ไทย

        self.setWindowTitle("ระบบเช็คอิน/เช็คเอาท์ — โหมดสแกนเนอร์")
        self._fullscreen = False

        # สถานะหลัก
        self.location = DEFAULT_LOCATION
        self.forced_mode = None  # None=อัตโนมัติ, 1=บังคับเช็คอิน, 0=บังคับเช็คเอาท์
        self.last_scan_ts = 0.0
        self.output_path = None
        self.reader = ReaderLogic(self.location, SCAN_COOLDOWN, STAY_DURATION)

        # UI
        self._build_ui()

        # บัฟเฟอร์รับคีย์จากสแกนเนอร์
        self.buffer = ""
        self._last_len = 0
        self._last_time = time.time()

        # โพลงด้วย Timer (เบาเครื่อง RPi)
        self.timer = QTimer(self)
        self.timer.setInterval(15)  # ~66 Hz
        self.timer.timeout.connect(self.on_timer)
        self.timer.start()

        # โฟกัสไปที่ช่องรับสแกนเนอร์
        self.scEdit.setFocus(Qt.OtherFocusReason)

        # เริ่มแบบขยายเต็มจอหรือไม่ก็ได้ (เลือกเอง)
        # self.toggle_fullscreen(True)

    def _load_font_thai(self):
        # พยายามใช้ฟอนต์ไทยที่มักมีใน Windows/RPi; ถ้ามีไฟล์ .ttf ใส่โฟลเดอร์เดียวกับแอป ก็โหลดได้
        preferred = ["Noto Sans Thai", "Sarabun", "Tahoma", "Th Sarabun New"]
        # ถ้ามีไฟล์ฟอนต์ในโฟลเดอร์ ให้เพิ่มด้วย
        for fname in os.listdir("."):
            if fname.lower().endswith(".ttf") and "thai" in fname.lower():
                try:
                    QFontDatabase.addApplicationFont(os.path.join(".", fname))
                except Exception:
                    pass
        # คำนวณขนาดฟอนต์ตามจอ
        screen = QApplication.primaryScreen().geometry()
        base_pt = max(11, min(18, int(min(screen.width(), screen.height()) / 70)))
        font = QFont()
        for fam in preferred:
            font.setFamily(fam)
            font.setPointSize(base_pt)
            self.setFont(font)
            if self.font().family() == fam:
                break
        else:
            font.setPointSize(base_pt)
            self.setFont(font)

        # ธีม/สไตล์ที่อ่านง่ายบน RPi
        self.setStyleSheet(
            f"""
            QWidget {{ background:#f5f7fb; color:#1c1e23; font-size:{base_pt}px; }}
            QGroupBox {{ font-weight:600; border:1px solid #dde3f0; border-radius:8px; margin-top:10px; padding:8px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left:10px; padding:0 5px; }}
            QLabel.title {{ font-weight:700; font-size:{base_pt+4}px; }}
            QLabel.status {{ font-size:{base_pt+2}px; color:#0f6b3c; }}
            QPushButton {{ background:#2563eb; color:white; border:none; border-radius:8px; padding:6px 14px; }}
            QPushButton:hover {{ background:#1d4ed8; }}
            QLineEdit {{ background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; padding:4px; }}
            QComboBox {{ background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; padding:3px; }}
            QCheckBox, QRadioButton {{ padding:2px; }}
            QToolBar {{ background:#eef2ff; border:0; padding:4px; }}
        """
        )

    # ---------- UI ----------
    def _build_ui(self):
        # Toolbar (ซ้าย: เต็มหน้าจอ / รีเฟรชฟอนต์, ขวา: ออก)
        self.toolbar = QToolBar()
        act_full = QAction("เต็มหน้าจอ (F11)", self)
        act_full.triggered.connect(lambda: self.toggle_fullscreen(not self._fullscreen))
        self.toolbar.addAction(act_full)

        act_font = QAction("ปรับฟอนต์/สเกลใหม่", self)
        act_font.triggered.connect(self._load_font_thai)
        self.toolbar.addAction(act_font)

        self.toolbar.addSeparator()
        act_exit = QAction("ออก (Q/ๆ)", self)
        act_exit.triggered.connect(self.close)
        self.toolbar.addAction(act_exit)

        # หัวข้อ + สถานะ
        self.lblTitle = QLabel("พร้อมใช้งาน — กรุณาสแกนโค้ดด้วยเครื่องสแกนเนอร์ของคุณ")
        self.lblTitle.setObjectName("title")
        self.lblTitle.setProperty("class", "title")

        self.lblStatus = QLabel("กำลังรอการสแกน…")
        self.lblStatus.setObjectName("status")
        self.lblStatus.setProperty("class", "status")

        # ช่องรับคีย์จากสแกนเนอร์ (ซ่อน)
        self.scEdit = QLineEdit()
        self.scEdit.textEdited.connect(self.on_text_edited)
        self.scEdit.setFixedHeight(1)
        self.scEdit.setStyleSheet(
            "color:#f5f7fb; background:#f5f7fb; border:none;"
        )  # กลืนไปกับพื้นหลัง

        # กล่อง “จุด/บูธ”
        boxLoc = QGroupBox("จุดบริการ / สถานที่")
        self.cmbBooth = QComboBox()
        self.cmbBooth.setEditable(True)
        self.cmbBooth.addItems(BOOTH_LIST)
        self.cmbBooth.setCurrentText(DEFAULT_LOCATION)
        btnSetBooth = QPushButton("ตั้งค่าสถานที่")
        btnSetBooth.clicked.connect(self.on_set_booth)
        layLoc = QHBoxLayout()
        layLoc.addWidget(self.cmbBooth)
        layLoc.addWidget(btnSetBooth)
        boxLoc.setLayout(layLoc)

        # โหมดการทำงาน
        boxMode = QGroupBox("โหมด")
        self.rbAuto = QRadioButton("อัตโนมัติ")
        self.rbIn = QRadioButton("บังคับเช็คอิน")
        self.rbOut = QRadioButton("บังคับเช็คเอาท์")
        self.rbAuto.setChecked(True)
        for rb in (self.rbAuto, self.rbIn, self.rbOut):
            rb.toggled.connect(self.on_mode_change)
        layMode = QVBoxLayout()
        [layMode.addWidget(w) for w in (self.rbAuto, self.rbIn, self.rbOut)]
        boxMode.setLayout(layMode)

        # เอาต์พุต
        boxOut = QGroupBox("เอาต์พุต")
        self.chkClipboard = QCheckBox("คัดลอกผลล่าสุดไปคลิปบอร์ด")
        self.chkFile = QCheckBox("บันทึกลงไฟล์…")
        self.chkFile.toggled.connect(self.on_toggle_file_output)
        self.lblOutPath = QLabel("")
        layOut = QVBoxLayout()
        layOut.addWidget(self.chkClipboard)
        layOut.addWidget(self.chkFile)
        layOut.addWidget(self.lblOutPath)
        boxOut.setLayout(layOut)

        # จัดวาง
        top = QHBoxLayout()
        top.addWidget(self.toolbar)
        right = QVBoxLayout()
        right.addWidget(boxLoc)
        right.addWidget(boxMode)
        right.addWidget(boxOut)
        right.addStretch(1)

        root = QGridLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setHorizontalSpacing(16)
        root.setVerticalSpacing(10)
        root.addLayout(top, 0, 0, 1, 2)
        root.addWidget(self.lblTitle, 1, 0, 1, 2)
        root.addWidget(self.lblStatus, 2, 0, 1, 2)
        root.addLayout(right, 3, 1)
        root.addWidget(self.scEdit, 4, 0, 1, 2)

        # เริ่มแบบขยายหน้าต่างให้เต็มหน้าจอ (แต่ยังไม่ fullscreen)
        self.showMaximized()

    # ---------- โหมดเต็มหน้าจอ ----------
    def toggle_fullscreen(self, on: bool):
        self._fullscreen = bool(on)
        if self._fullscreen:
            self.showFullScreen()
        else:
            self.showMaximized()
        # รักษาโฟกัสรับสแกน
        self.scEdit.setFocus(Qt.OtherFocusReason)

    # ---------- รับสแกนเนอร์ ----------
    def on_text_edited(self, _):
        txt = self.scEdit.text()
        if len(txt) > len(self.buffer):
            self.buffer += txt[len(self.buffer) :]
        else:
            self.buffer = txt

        self._last_len = len(self.buffer)
        self._last_time = time.time()

        if TERMINATOR and self.buffer.endswith(TERMINATOR):
            payload = self.buffer.strip()
            self._finalize_payload(payload)

    def on_timer(self):
        if not self.buffer:
            return
        if (time.time() - self._last_time) * 1000.0 > cfg.getint(
            "Scanner", "TimeoutMs", fallback=250
        ):
            payload = self.buffer.strip()
            self._finalize_payload(payload)

    def _finalize_payload(self, payload: str):
        self.buffer = ""
        self.scEdit.clear()
        if not payload or len(payload) < SC_MINLEN:
            return

        now = time.time()
        if now - self.last_scan_ts < RATE_LIMIT_S:
            return
        self.last_scan_ts = now

        token = payload.strip()
        if not TOKEN_RE.match(token):
            self._set_status(f"ข้าม: รูปแบบโทเคนไม่ถูกต้อง → {token!r}", error=True)
            return

        # โหมดอัตโนมัติ
        result = self.reader.read_qr(token)

        # โหมดบังคับ + กฎสถานที่ (เช็คเอาท์ต้องที่เดิม, ถ้าคนละจุดต้องไปเช็คเอาท์ก่อน)
        fm = 1 if self.forced_mode == 1 else 0 if self.forced_mode == 0 else None
        if fm is not None:
            result = apply_forced_mode(self.reader, token, result, fm)

        status = result.get("status", -1)
        msg = result.get("message", "")
        now_str = datetime.now(TZ).strftime(TIME_FMT_HMS)

        # เขียน log (ผ่าน QRData เหมือนเดิม)
        if status != -1 and result.get("qr_data"):
            try:
                QRData(token, self.location, status, int(time.time())).write_data()
            except Exception:
                try:
                    with open("qr_log.json", "w", encoding="utf-8") as f:
                        f.write("[]")
                    QRData(token, self.location, status, int(time.time())).write_data()
                except Exception:
                    pass

        extra = ""
        if result.get("next_checkout_str"):
            extra = f" | เช็คเอาท์ได้เวลา {result['next_checkout_str']}"
        self._set_status(f"{msg}{extra}  เวลา {now_str}", ok=(status in (0, 1)))

        # บันทึกเอาต์พุต / คลิปบอร์ด
        if status in (0, 1):
            line = f"{token},{status},{now_str}"
            if self.chkClipboard.isChecked():
                QApplication.clipboard().setText(line)
            if self.output_path:
                try:
                    with open(self.output_path, "a", encoding="utf-8") as fp:
                        fp.write(line + "\n")
                except Exception as e:
                    QMessageBox.warning(self, "บันทึกไฟล์", f"ไม่สามารถเขียนไฟล์ได้: {e}")

    # ---------- ปุ่ม/อีเวนต์ UI ----------
    def on_mode_change(self):
        if self.rbAuto.isChecked():
            self.forced_mode = None
        elif self.rbIn.isChecked():
            self.forced_mode = 1
        elif self.rbOut.isChecked():
            self.forced_mode = 0

    def on_set_booth(self):
        new_loc = self.cmbBooth.currentText().strip() or DEFAULT_LOCATION
        self.location = new_loc
        old_hist = self.reader.scan_history
        self.reader = ReaderLogic(self.location, SCAN_COOLDOWN, STAY_DURATION)
        self.reader.scan_history = old_hist
        self._set_status(f"ตั้งค่าสถานที่เป็น “{self.location}” แล้ว", ok=True)
        self.scEdit.setFocus(Qt.OtherFocusReason)

    def on_toggle_file_output(self):
        if self.chkFile.isChecked():
            path, _ = QFileDialog.getSaveFileName(
                self, "เลือกไฟล์สำหรับบันทึก", "qr_out.txt", "Text files (*.txt)"
            )
            if path:
                self.output_path = path
                self.lblOutPath.setText(path)
            else:
                self.chkFile.setChecked(False)
        else:
            self.output_path = None
            self.lblOutPath.setText("")

    def _set_status(self, text, ok=False, error=False):
        # ปรับสีข้อความสถานะให้เห็นชัด
        if error:
            self.lblStatus.setStyleSheet(self.lblStatus.styleSheet() + "color:#b91c1c;")
        elif ok:
            self.lblStatus.setStyleSheet(self.lblStatus.styleSheet() + "color:#0f6b3c;")
        else:
            self.lblStatus.setStyleSheet(self.lblStatus.styleSheet() + "color:#1c1e23;")
        self.lblStatus.setText(text)

    # ---------- คีย์ลัด ----------
    def keyPressEvent(self, e):
        # ออกจากโปรแกรมด้วย q หรือ ‘ๆ’
        if e.key() == Qt.Key_Q:
            self.close()
            return
        # Toggle Fullscreen ด้วย F11 หรือ Ctrl+Enter
        if e.key() in (Qt.Key_F11,) or (
            e.key() == Qt.Key_Return and e.modifiers() & Qt.ControlModifier
        ):
            self.toggle_fullscreen(not self._fullscreen)
            return
        super().keyPressEvent(e)


# -------------------- main --------------------
def main():
    # เปิด High DPI เร็ว ๆ (สำรอง)
    app = QApplication(sys.argv)
    w = ScannerApp()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
