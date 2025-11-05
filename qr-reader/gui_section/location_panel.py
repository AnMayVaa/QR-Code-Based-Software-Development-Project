from PyQt5.QtWidgets import QGroupBox, QHBoxLayout, QComboBox, QPushButton


class LocationPanel(QGroupBox):
    def __init__(self, booths, current_loc, on_set):
        super().__init__("จุดบริการ / สถานที่")
        self.on_set = on_set
        self.cmb = QComboBox()
        self.cmb.setEditable(True)
        self.cmb.addItems(booths)
        self.cmb.setCurrentText(current_loc)
        btn = QPushButton("ตั้งค่าสถานที่")
        btn.clicked.connect(self._set)
        lay = QHBoxLayout(self)
        lay.addWidget(self.cmb)
        lay.addWidget(btn)

    def _set(self):
        self.on_set(self.cmb.currentText().strip())
