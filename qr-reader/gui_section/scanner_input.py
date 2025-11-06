from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtWidgets import QLineEdit


class HiddenScannerInput(QLineEdit):
    def __init__(self, on_text_edited, parent=None):
        super().__init__(parent)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setReadOnly(False)
        self.textEdited.connect(on_text_edited)
        # (optional) style to make it discrete if you show it:
        self.setMaximumHeight(1)
        self.setContentsMargins(0, 0, 0, 0)

    def focusOutEvent(self, e):
        # If our window is active, pull focus back so the scanner keeps typing here
        if self.window() and self.window().isActiveWindow():
            QTimer.singleShot(0, lambda: self.setFocus(Qt.OtherFocusReason))
        super().focusOutEvent(e)
