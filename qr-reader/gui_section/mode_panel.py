from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGroupBox, QVBoxLayout, QRadioButton


class ModePanel(QGroupBox):
    def __init__(self, on_changed):
        super().__init__("โหมดการทำงาน")
        self.on_changed = on_changed
        lay = QVBoxLayout(self)
        self.rbAuto = QRadioButton("อัตโนมัติ")
        self.rbIn = QRadioButton("บังคับเช็คอิน")
        self.rbOut = QRadioButton("บังคับเช็คเอาท์")
        for rb in (self.rbAuto, self.rbIn, self.rbOut):
            rb.setFocusPolicy(Qt.NoFocus)
            rb.toggled.connect(self._emit_mode)
            lay.addWidget(rb)
        self.rbAuto.setChecked(True)

    def _emit_mode(self):
        if self.rbAuto.isChecked():
            self.on_changed(None)
        elif self.rbIn.isChecked():
            self.on_changed(1)
        elif self.rbOut.isChecked():
            self.on_changed(0)

    # ← NEW: update radios without re-triggering callbacks
    def set_mode(self, mode):
        self.blockSignals(True)
        if mode is None:
            self.rbAuto.setChecked(True)
        elif mode == 1:
            self.rbIn.setChecked(True)
        elif mode == 0:
            self.rbOut.setChecked(True)
        self.blockSignals(False)
