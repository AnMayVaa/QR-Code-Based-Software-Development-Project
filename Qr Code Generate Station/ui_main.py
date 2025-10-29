from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QTimer
import cv2, sys

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KIOS Camera + QR System")
        self.setGeometry(100, 100, 1200, 700)

        layout = QHBoxLayout(self)

        # -------------------------------
        # ฝั่งซ้าย (QR Info Panel 9:16)
        # -------------------------------
        self.left_frame = QFrame()
        self.left_frame.setStyleSheet("border: 2px solid black; background: white;")
        self.left_frame.setFixedSize(360, 640)  # อัตราส่วน 9:16

        left_layout = QVBoxLayout()
        self.lbl_uuid = QLabel("uuid : 00000000")
        self.lbl_qr = QLabel("[ QR CODE ]")
        self.lbl_qr.setAlignment(Qt.AlignCenter)
        self.lbl_info = QLabel(
            "- QR code ใช้สำหรับ check in แต่ละบูธ\n"
            "- เข้าร่วมครบ 4 บูธ รับของรางวัล\n"
            "- หาก QR Code ไม่สามารถสแกนได้ ให้แจ้ง staff\n"
        )
        self.lbl_info.setWordWrap(True)

        left_layout.addWidget(self.lbl_uuid, alignment=Qt.AlignTop)
        left_layout.addWidget(self.lbl_qr, alignment=Qt.AlignCenter)
        left_layout.addWidget(self.lbl_info, alignment=Qt.AlignBottom)
        self.left_frame.setLayout(left_layout)

        # -------------------------------
        # ฝั่งขวา (Camera)
        # -------------------------------
        self.right_frame = QFrame()
        right_layout = QVBoxLayout()
        self.lbl_camera = QLabel()
        self.lbl_camera.setFixedSize(640, 480)

        # จัดให้อยู่กึ่งกลางทั้งแนวตั้ง-แนวนอน
        right_layout.addWidget(self.lbl_camera, alignment=Qt.AlignCenter)
        self.right_frame.setLayout(right_layout)

        # -------------------------------
        # ใส่ layout หลัก
        # -------------------------------
        layout.addWidget(self.left_frame, alignment=Qt.AlignCenter)
        layout.addWidget(self.right_frame, alignment=Qt.AlignCenter)

        # -------------------------------
        # กล้อง
        # -------------------------------
        self.cap = cv2.VideoCapture(0)
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    def update_frame(self):
        ret, frame = self.cap.read()
        if not ret:
            return
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch*w, QImage.Format_RGB888)
        self.lbl_camera.setPixmap(QPixmap.fromImage(img))

    def closeEvent(self, event):
        self.cap.release()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
