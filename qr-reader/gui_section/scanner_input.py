from PyQt5.QtWidgets import QLineEdit


class HiddenScannerInput(QLineEdit):
    def __init__(self, on_text_edited):
        super().__init__()
        self.textEdited.connect(on_text_edited)
        self.setFixedHeight(1)
        self.setStyleSheet("color:#f5f7fb; background:#f5f7fb; border:none;")
