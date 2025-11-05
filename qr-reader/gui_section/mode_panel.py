from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QRadioButton
from PyQt5.QtCore import Qt

class ModePanel(QGroupBox):
    def __init__(self, on_mode_change):
        super().__init__("โหมด")
        self.on_mode_change = on_mode_change
        self.rbAuto = QRadioButton("อัตโนมัติ")
        self.rbIn = QRadioButton("บังคับเช็คอิน")
        self.rbOut = QRadioButton("บังคับเช็คเอาท์")
        self.rbAuto.setChecked(True)
        for rb in (self.rbAuto, self.rbIn, self.rbOut):
            rb.toggled.connect(self._changed)
            rb.setFocusPolicy(Qt.NoFocus)
        lay = QVBoxLayout(self)
        for w in (self.rbAuto, self.rbIn, self.rbOut):
            lay.addWidget(w)

    def _changed(self):
        mode = None
        if self.rbIn.isChecked():
            mode = 1
        elif self.rbOut.isChecked():
            mode = 0
        self.on_mode_change(mode)
