from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QCheckBox, QLabel, QFileDialog
from PyQt5.QtCore import Qt


class OutputPanel(QGroupBox):
    def __init__(self, on_file_toggle, on_clipboard_toggle):
        super().__init__("เอาต์พุต")
        self.on_file_toggle = on_file_toggle
        self.on_clipboard_toggle = on_clipboard_toggle

        self.chkClipboard = QCheckBox("คัดลอกผลล่าสุดไปคลิปบอร์ด")
        self.chkClipboard.toggled.connect(self._clip)
        self.chkFile = QCheckBox("บันทึกลงไฟล์…")
        self.chkFile.toggled.connect(self._file)
        self.lblPath = QLabel("")
        lay = QVBoxLayout(self)
        lay.addWidget(self.chkClipboard)
        lay.addWidget(self.chkFile)
        lay.addWidget(self.lblPath)

    def _clip(self, checked: bool):
        self.on_clipboard_toggle(checked)

    def _file(self, checked: bool):
        if checked:
            path, _ = QFileDialog.getSaveFileName(
                self, "เลือกไฟล์สำหรับบันทึก", "qr_out.txt", "Text files (*.txt)"
            )
            if path:
                self.lblPath.setText(path)
                self.on_file_toggle(path)
                return
            self.chkFile.setChecked(False)
            self.on_file_toggle(None)
        else:
            self.lblPath.setText("")
            self.on_file_toggle(None)
