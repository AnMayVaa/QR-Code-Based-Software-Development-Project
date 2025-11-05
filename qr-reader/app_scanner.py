# main.py
import os, sys, time, signal
from PyQt5.QtCore import Qt, QCoreApplication, QLocale
from PyQt5.QtWidgets import QApplication

# ---- Force Bangkok time for this process (ignore system tz) ----
os.environ["TZ"] = "Asia/Bangkok"
if hasattr(time, "tzset"):
    time.tzset()

# ---- Qt HiDPI (set before QApplication) ----
QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

# ---- Optional: Thai locale defaults in Qt ----
QLocale.setDefault(QLocale(QLocale.Thai, QLocale.Thailand))


# ---- Graceful Ctrl+C ----
def _handle_sigint(*_):
    QCoreApplication.quit()


signal.signal(signal.SIGINT, _handle_sigint)

# ---- Platform plugin (Windows/RPi) ----
if sys.platform.startswith("win"):
    os.environ["QT_QPA_PLATFORM"] = "windows"
elif sys.platform.startswith("linux"):
    os.environ.setdefault("QT_QPA_PLATFORM", "xcb")
else:
    os.environ.pop("QT_QPA_PLATFORM", None)

from gui_section.window import MainWindow  # your refactored window


def main():
    app = QApplication(sys.argv)
    w = MainWindow()
    w.showMaximized()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
