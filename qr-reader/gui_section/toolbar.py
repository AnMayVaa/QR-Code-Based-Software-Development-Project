# toolbar.py
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPixmap
from PyQt5.QtWidgets import QToolBar, QAction, QLabel, QWidget, QSizePolicy

LOGO_PATH = "src/cropped-cropped-ECET-Shirt.png"  # change if you keep it elsewhere


def _logo_label(path: str, h: int = 22) -> QLabel:
    lb = QLabel()
    pm = QPixmap(path)
    if not pm.isNull():
        lb.setPixmap(pm.scaledToHeight(h, Qt.SmoothTransformation))
    lb.setFixedHeight(h + 4)
    lb.setContentsMargins(6, 0, 6, 0)
    return lb


def _spacer() -> QWidget:
    w = QWidget()
    w.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
    return w


def build_toolbar(window):
    tb = QToolBar()
    tb.setMovable(False)

    # --- left: logo + app summary (what it does) ---
    tb.addWidget(_logo_label(LOGO_PATH))
    summary = QLabel("ระบบ QR Check-in/Check-out")
    summary.setStyleSheet("color:#334155; padding-right:8px;")
    tb.addWidget(summary)

    # push actions to the right
    tb.addWidget(_spacer())

    # --- actions (right side) ---
    act_full = QAction("เต็มหน้าจอ (F11)", window)
    act_full.triggered.connect(
        lambda: window.toggle_fullscreen(not getattr(window, "_fullscreen", False))
    )
    tb.addAction(act_full)

    act_font = QAction("ปรับฟอนต์/สเกลใหม่", window)
    act_font.triggered.connect(window._apply_thai_font_theme)
    tb.addAction(act_font)

    tb.addSeparator()

    act_exit = QAction("ออก (Q/Ctrl+Q/Ctrl+C)", window)
    act_exit.triggered.connect(window.close)
    tb.addAction(act_exit)

    act_manual_input = QAction("พิมพ์โทเคน/คำสั่ง (F2)", window)
    act_manual_input.triggered.connect(window.prompt_manual_input)
    tb.addAction(act_manual_input)

    return tb
