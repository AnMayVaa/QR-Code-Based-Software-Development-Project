import os
from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QFont, QFontDatabase, QKeySequence, QIcon
from PyQt5.QtWidgets import (
    QWidget,
    QLabel,
    QGridLayout,
    QVBoxLayout,
    QHBoxLayout,
    QToolBar,
    QAction,
    QLineEdit,
    QShortcut,
)

from gui_section.app_config import (
    DEFAULT_LOCATION,
    SCAN_COOLDOWN,
    STAY_DURATION,
    booth_list,
)
from gui_section.scanner_controller import ScannerController
from gui_section.toolbar import build_toolbar
from gui_section.location_panel import LocationPanel
from gui_section.mode_panel import ModePanel
from gui_section.output_panel import OutputPanel
from gui_section.scanner_input import HiddenScannerInput


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ระบบ Checkin/Checkout งาน Open House")
        self.setWindowIcon(QIcon("src/cropped-cropped-ECET-Shirt.png"))

        # Fonts / theme (Thai)
        self._apply_thai_font_theme()

        # Core controller
        self.ctrl = ScannerController(
            DEFAULT_LOCATION, SCAN_COOLDOWN, STAY_DURATION, self
        )
        self.ctrl.status_text.connect(self._set_status)

        # UI parts
        self.toolbar = build_toolbar(self)
        self.lblTitle = QLabel("พร้อมใช้งาน — กรุณาสแกนโค้ดด้วยเครื่องสแกนเนอร์ของคุณ")
        self.lblStatus = QLabel("กำลังรอการสแกน…")
        self.lblTitle.setProperty("class", "title")
        self.lblStatus.setProperty("class", "status")

        # panels
        self.locationPanel = LocationPanel(
            booth_list(), DEFAULT_LOCATION, self.on_set_location
        )
        self.modePanel = ModePanel(self.on_mode_changed)
        self.outputPanel = OutputPanel(
            self.on_toggle_file_output, self.on_toggle_clipboard
        )

        # hidden scanner input
        self.scEdit = HiddenScannerInput(self.on_text_edited)

        # layout
        right = QVBoxLayout()
        right.addWidget(self.locationPanel)
        right.addWidget(self.modePanel)
        right.addWidget(self.outputPanel)
        right.addStretch(1)

        root = QGridLayout(self)
        root.setContentsMargins(14, 10, 14, 10)
        root.setHorizontalSpacing(16)
        root.setVerticalSpacing(10)
        root.addWidget(self.toolbar, 0, 0, 1, 2)
        root.addWidget(self.lblTitle, 1, 0, 1, 2)
        root.addWidget(self.lblStatus, 2, 0, 1, 2)
        root.addLayout(right, 3, 1)
        root.addWidget(self.scEdit, 4, 0, 1, 2)

        # focus & shortcuts
        self.setFocusPolicy(Qt.StrongFocus)
        self.activateWindow()
        self.raise_()
        self.scEdit.setFocus(Qt.OtherFocusReason)
        QShortcut(QKeySequence("Ctrl+C"), self, activated=self.close)
        QShortcut(QKeySequence("Ctrl+Q"), self, activated=self.close)

        # timer to poll scanner timeout
        self.timer = QTimer(self)
        self.timer.setInterval(15)
        self.timer.timeout.connect(self.on_timer)
        self.timer.start()

        self._prev_len = 0

        self._fullscreen = False

    # ---------- styling ----------
    def _apply_thai_font_theme(self):
        preferred = ["Noto Sans Thai", "Sarabun", "Tahoma", "Th Sarabun New"]
        for fname in os.listdir("."):
            if fname.lower().endswith(".ttf") and "thai" in fname.lower():
                try:
                    QFontDatabase.addApplicationFont(os.path.join(".", fname))
                except:
                    pass
        screen = self.screen().geometry() if self.screen() else self.geometry()
        w = screen.width() if hasattr(screen, "width") else 0
        h = screen.height() if hasattr(screen, "height") else 0
        base_pt = 16 if not w else max(13, min(22, int(min(w, h) / 60)))
        font = QFont(preferred[0], base_pt)
        self.setFont(font)
        self.setStyleSheet(
            f"""
            QWidget {{ background:#f5f7fb; color:#1c1e23; font-size:{base_pt}px; }}
            QGroupBox {{ font-weight:600; border:1px solid #dde3f0; border-radius:8px; margin-top:10px; padding:8px; }}
            QGroupBox::title {{ subcontrol-origin: margin; left:10px; padding:0 5px; }}
            QLabel[class="title"] {{ font-weight:700; font-size:{base_pt+4}px; }}
            QLabel[class="status"] {{ font-size:{base_pt+2}px; color:#0f6b3c; }}
            QPushButton {{ background:#2563eb; color:white; border:none; border-radius:8px; padding:6px 14px; }}
            QPushButton:hover {{ background:#1d4ed8; }}
            QLineEdit {{ background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; padding:4px; }}
            QComboBox {{ background:#ffffff; border:1px solid #cbd5e1; border-radius:6px; padding:3px; }}
            QCheckBox, QRadioButton {{ padding:2px; }}
            QToolBar {{ background:#eef2ff; border:0; padding:4px; }}
        """
        )

    # ---------- event wiring ----------
    def on_text_edited(self, text: str):
        self.ctrl.on_text_delta(text, self._prev_len)
        self._prev_len = len(text)

    def on_timer(self):
        self.ctrl.poll_timeout_finalize(self.isActiveWindow())

    def on_set_location(self, new_loc: str):
        self.ctrl.set_location(new_loc)
        self.scEdit.setFocus(Qt.OtherFocusReason)

    def on_mode_changed(self, mode):
        self.ctrl.set_forced_mode(mode)

    def on_toggle_file_output(self, path_or_none: str):
        self.ctrl.output_path = path_or_none

    def on_toggle_clipboard(self, enabled: bool):
        self.ctrl.clipboard_enabled = enabled

    def toggle_fullscreen(self, on: bool):
        self._fullscreen = bool(on)
        self.showFullScreen() if self._fullscreen else self.showMaximized()
        self.scEdit.setFocus(Qt.OtherFocusReason)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_Q:
            self.close()
            return
        if e.key() == Qt.Key_F11 or (
            e.key() == Qt.Key_Return and e.modifiers() & Qt.ControlModifier
        ):
            self.toggle_fullscreen(not self._fullscreen)
            return
        super().keyPressEvent(e)

    def _set_status(self, text: str, ok: bool, error: bool):
        if error:
            self.lblStatus.setStyleSheet(self.lblStatus.styleSheet() + "color:#b91c1c;")
        elif ok:
            self.lblStatus.setStyleSheet(self.lblStatus.styleSheet() + "color:#0f6b3c;")
        else:
            self.lblStatus.setStyleSheet(self.lblStatus.styleSheet() + "color:#1c1e23;")
        self.lblStatus.setText(text)
