import os, sys, time, re, configparser
from datetime import datetime

# Pick the right Qt platform plugin
if sys.platform.startswith("win"):
    os.environ["QT_QPA_PLATFORM"] = "windows"
elif sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
else:
    os.environ.pop("QT_QPA_PLATFORM", None)

import pytz
from PyQt5.QtCore import Qt, QTimer
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
)

# --- Project modules (unchanged) ---
from read_qrcode_module.reader_logic import ReaderLogic, apply_forced_mode
from read_qrcode_module.qr_reader import QRData

# -------------------- CONFIG --------------------
CONFIG_FILE = "config.ini"
cfg = configparser.ConfigParser()
cfg.read(CONFIG_FILE)

DEFAULT_LOCATION = cfg.get("Device", "Location", fallback="Booth1")
SCAN_COOLDOWN = cfg.getint("Device", "ScanCooldown", fallback=5)
STAY_DURATION = cfg.getint("Device", "StayDuration", fallback=600)


def _parse_booth_list(cfg, default_loc):
    raw = cfg.get("BoothList", "Locations", fallback="").strip()
    if not raw:
        return [default_loc, "Booth2", "Booth3", "Entrance", "Exit", "Custom…"]
    items = [s.strip() for s in raw.split(",")]
    items = [s for s in items if s]  # drop empties
    # ensure default location is present (put it first)
    if default_loc not in items:
        items = [default_loc] + items
    # de-dupe while preserving order
    seen, deduped = set(), []
    for it in items:
        if it.lower() in seen:
            continue
        seen.add(it.lower())
        deduped.append(it)
    return deduped


BOOTH_LIST = _parse_booth_list(cfg, DEFAULT_LOCATION)

SC_TERM = cfg.get("Scanner", "Terminator", fallback="CRLF").upper()
SC_MINLEN = cfg.getint("Scanner", "MinLength", fallback=6)
SC_TMO_MS = cfg.getint("Scanner", "TimeoutMs", fallback=250)

TERM_MAP = {"CR": "\r", "LF": "\n", "CRLF": "\r\n", "NONE": ""}
TERMINATOR = TERM_MAP.get(SC_TERM, "\r\n")

# -------------------- CONSTANTS --------------------
TZ = pytz.timezone("Asia/Bangkok")
TIME_FMT_HMS = "%I:%M:%S %p"
TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-]{22}$")  # your base64url-ish token
RATE_LIMIT_S = 1.0  # scanner is fast; short anti-spam


class ScannerApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QR/Barcode — Booth Control (Scanner)")
        self.resize(760, 420)

        # State
        self.location = DEFAULT_LOCATION
        self.forced_mode = None  # None=Auto, 1=In, 0=Out
        self.last_scan_ts = 0.0
        self.output_path = None

        self.reader = ReaderLogic(self.location, SCAN_COOLDOWN, STAY_DURATION)

        # UI
        self._build_ui()

        # Scanner buffer logic
        self.buffer = ""
        self._last_len = 0
        self._last_time = time.time()
        self.timer = QTimer(self)
        self.timer.setInterval(15)  # poll ~66 Hz
        self.timer.timeout.connect(self.on_timer)
        self.timer.start()

        # Give focus to hidden edit to capture keystrokes from the scanner
        self.scannerEdit.setFocus(Qt.OtherFocusReason)

    def _build_ui(self):
        # Title & status
        self.lblTitle = QLabel("Ready — scan a code with your barcode scanner")
        self.lblTitle.setStyleSheet("font-size:18px; font-weight:600;")
        self.lblStatus = QLabel("Waiting…")
        self.lblStatus.setStyleSheet("font-size:16px;")

        # Hidden input for scanner
        self.scannerEdit = QLineEdit()
        self.scannerEdit.setPlaceholderText("Focus here and scan…")
        self.scannerEdit.textEdited.connect(self.on_text_edited)
        self.scannerEdit.setFixedHeight(1)
        self.scannerEdit.setStyleSheet("color:#111; background:#111; border:none;")

        # Booth / Location
        boxLoc = QGroupBox("Booth / Location")
        self.cmbBooth = QComboBox()
        self.cmbBooth.setEditable(True)
        self.cmbBooth.addItems(BOOTH_LIST)  # <— use config-driven list
        self.cmbBooth.setCurrentText(DEFAULT_LOCATION)
        btnSetBooth = QPushButton("Set Location")
        btnSetBooth.clicked.connect(self.on_set_booth)
        layLoc = QHBoxLayout()
        layLoc.addWidget(self.cmbBooth)
        layLoc.addWidget(btnSetBooth)
        boxLoc.setLayout(layLoc)

        # Mode
        boxMode = QGroupBox("Mode")
        self.rbAuto = QRadioButton("Auto")
        self.rbIn = QRadioButton("Force Check-in")
        self.rbOut = QRadioButton("Force Check-out")
        self.rbAuto.setChecked(True)
        for rb in (self.rbAuto, self.rbIn, self.rbOut):
            rb.toggled.connect(self.on_mode_change)
        layMode = QVBoxLayout()
        [layMode.addWidget(w) for w in (self.rbAuto, self.rbIn, self.rbOut)]
        boxMode.setLayout(layMode)

        # Output
        boxOut = QGroupBox("Output")
        self.chkClipboard = QCheckBox("Copy last result to clipboard")
        self.chkFile = QCheckBox("Append to file…")
        self.chkFile.toggled.connect(self.on_toggle_file_output)
        self.lblOutPath = QLabel("")
        layOut = QVBoxLayout()
        layOut.addWidget(self.chkClipboard)
        layOut.addWidget(self.chkFile)
        layOut.addWidget(self.lblOutPath)
        boxOut.setLayout(layOut)

        # Layout
        side = QVBoxLayout()
        side.addWidget(boxLoc)
        side.addWidget(boxMode)
        side.addWidget(boxOut)
        side.addStretch(1)
        root = QGridLayout(self)
        root.addWidget(self.lblTitle, 0, 0, 1, 2)
        root.addWidget(self.lblStatus, 1, 0, 1, 2)
        root.addLayout(side, 2, 1)
        root.addWidget(self.scannerEdit, 3, 0, 1, 2)

    # -------- Scanner handling --------
    def on_text_edited(self, _):
        txt = self.scannerEdit.text()

        # append only the new delta
        if len(txt) > len(self.buffer):
            self.buffer += txt[len(self.buffer) :]
        else:
            self.buffer = txt

        self._last_len = len(self.buffer)
        self._last_time = time.time()

        # Terminator-based finalize (CR/LF/CRLF)
        if TERMINATOR and self.buffer.endswith(TERMINATOR):
            payload = self.buffer.strip()
            self._finalize_payload(payload)

    def on_timer(self):
        # Burst timeout finalize (for scanners sending NONE or if terminator got lost)
        if not self.buffer:
            return
        if (time.time() - self._last_time) * 1000.0 > SC_TMO_MS:
            payload = self.buffer.strip()
            self._finalize_payload(payload)

    def _finalize_payload(self, payload: str):
        self.buffer = ""
        self.scannerEdit.clear()
        if not payload or len(payload) < SC_MINLEN:
            return

        now = time.time()
        if now - self.last_scan_ts < RATE_LIMIT_S:
            return
        self.last_scan_ts = now

        token = payload.strip()
        if not TOKEN_RE.match(token):
            self.lblStatus.setText(f"Ignored: not a valid token → {token!r}")
            return

        # Base logic: auto mode
        result = self.reader.read_qr(token)

        # Forced mode rules (enforce location rules too)
        fm = 1 if self.forced_mode == 1 else 0 if self.forced_mode == 0 else None
        if fm is not None:
            result = apply_forced_mode(self.reader, token, result, fm)

        # Persist + status
        status = result.get("status", -1)
        msg = result.get("message", "")
        now_str = datetime.now(TZ).strftime(TIME_FMT_HMS)

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

        # Message
        extra = ""
        if result.get("next_checkout_str"):
            extra = f" | Checkout at {result['next_checkout_str']}"
        self.lblStatus.setText(f"{msg}{extra} at: {now_str}")

        # Output
        if status in (0, 1):
            line = f"{token},{status},{now_str}"
            if self.chkClipboard.isChecked():
                QApplication.clipboard().setText(line)
            if self.output_path:
                try:
                    with open(self.output_path, "a", encoding="utf-8") as fp:
                        fp.write(line + "\n")
                except Exception as e:
                    QMessageBox.warning(
                        self, "Output file", f"Cannot write to file: {e}"
                    )

    # -------- UI actions --------
    def on_mode_change(self):
        if self.rbAuto.isChecked():
            self.forced_mode = None
        elif self.rbIn.isChecked():
            self.forced_mode = 1
        elif self.rbOut.isChecked():
            self.forced_mode = 0

    def on_set_booth(self):
        new_loc = self.cmbBooth.currentText().strip() or "Booth1"
        self.location = new_loc
        old_hist = self.reader.scan_history
        self.reader = ReaderLogic(self.location, SCAN_COOLDOWN, STAY_DURATION)
        self.reader.scan_history = old_hist
        self.lblStatus.setText(f"Location set to: {self.location}")
        self.scannerEdit.setFocus(Qt.OtherFocusReason)

    def on_toggle_file_output(self):
        if self.chkFile.isChecked():
            path, _ = QFileDialog.getSaveFileName(
                self, "Select output file", "qr_out.txt", "Text files (*.txt)"
            )
            if path:
                self.output_path = path
                self.lblOutPath.setText(path)
            else:
                self.chkFile.setChecked(False)
        else:
            self.output_path = None
            self.lblOutPath.setText("")


def main():
    app = QApplication(sys.argv)
    w = ScannerApp()
    w.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
