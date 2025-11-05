# gui_section/location_panel.py
from PyQt5.QtWidgets import QGroupBox, QHBoxLayout, QComboBox, QPushButton, QLineEdit
from PyQt5.QtCore import Qt, QTimer


class LocationPanel(QGroupBox):
    def __init__(self, booths, current_loc, on_set):
        super().__init__("จุดบริการ / สถานที่")
        self.on_set = on_set

        self.cmb = QComboBox()
        self.cmb.setEditable(True)
        self.cmb.setFocusPolicy(Qt.NoFocus)

        le = self.cmb.lineEdit() or QLineEdit()
        if self.cmb.lineEdit() is None:
            self.cmb.setLineEdit(le)

        # keep model in sync
        def _sync():
            t = self.cmb.lineEdit().text().strip()
            if t and t != self.cmb.currentText():
                self.cmb.setCurrentText(t)

        le.editingFinished.connect(_sync)
        self.cmb.activated[str].connect(lambda _: _sync())

        self.cmb.addItems(booths)
        self.cmb.setCurrentText(current_loc)

        btn = QPushButton("ตั้งค่าสถานที่")
        btn.setFocusPolicy(Qt.NoFocus)

        # 👇 ensure commit happens BEFORE we read it
        def _set():
            le.clearFocus()  # fires editingFinished
            _sync()  # commit the visible text
            # queue one tick so activated/finished run first in the event loop
            QTimer.singleShot(0, lambda: self.on_set(self.cmb.currentText().strip()))

        btn.clicked.connect(_set)

        lay = QHBoxLayout(self)
        lay.addWidget(self.cmb, 1)
        lay.addWidget(btn)
