from PyQt5.QtWidgets import QToolBar, QAction


def build_toolbar(window):
    tb = QToolBar()

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

    return tb
