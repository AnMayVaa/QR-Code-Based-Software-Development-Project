import sys, os, time, cv2, glob
import numpy as np
from PyQt5.QtWidgets import QApplication, QWidget, QLabel, QVBoxLayout, QHBoxLayout, QFrame
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QTimer
from pyzbar import pyzbar

from modules import paint_model, qr_module, utils
from modules import hand_module  # MediaPipe wrapper

SPACING_X = 10

MAIN_STYLE = """
QWidget { background-color: #f7f8fa; font-family: 'Segoe UI', Arial, Helvetica, sans-serif; color: #2c3e50; }
QFrame { background-color: #ffffff; border: 1px solid #e6e8eb; border-radius: 12px; }
QLabel { font-size: 13pt; color: #2c3e50; }
QLabel#UUID { font-size: 15pt; font-weight: bold; color: #e74c3c; }
QLabel#Title { font-size: 13pt; font-weight: 600; color: #34495e; }
QLabel#Manual { font-size: 11pt; line-height: 150%; color: #777777; }
QLabel#State { font-size: 20pt; font-weight: 700;
    color: qlineargradient(spread:pad, x1:0, y1:0, x2:1, y2:0, stop:0 #ff6a00, stop:1 #ee0979); }
"""

class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("KIOS Camera + QR System")

        screen = QApplication.primaryScreen().geometry()
        self.setGeometry(0, 0, screen.width(), screen.height())
        self.setStyleSheet(MAIN_STYLE)

        # --- State ---
        self.state = "take_pic"

        # SPACE countdown
        self.countdown_active = False
        self.countdown_start = None
        self.countdown_time = 3  # seconds

        # Gesture debounce -> then countdown
        self.gesture_hold_active = False
        self.gesture_hold_start = None
        self.gesture_hold_req = 3.0  # seconds to hold thumbs up

        # Toggles
        self.ai_paint_enabled = False          # E: AI Paint (default OFF)
        self.preview_enabled = False           # Q: Camera Preview (default OFF)
        self._last_key_time = 0                # debounce for key spamming

        self.captured_path = None
        self.painted_path = None
        self.current_token = None
        self.qr_path = None
        self.current_style = "paprika"

        # cache thumb for QR preview (path->image)
        self._qr_thumb_cache_path = None
        self._qr_thumb_cache_img = None

        # --- Layout (left-right) ---
        body_layout = QHBoxLayout(self)
        body_layout.setContentsMargins(20, 20, 20, 20)
        body_layout.setSpacing(20)

        # Left
        self.left_frame = QFrame()
        left_layout = QVBoxLayout()
        left_layout.setContentsMargins(20, 20, 20, 20)

        left_layout.addSpacing(2 * SPACING_X)
        self.lbl_uuid = QLabel("uuid : ")
        self.lbl_uuid.setObjectName("UUID")
        self.lbl_uuid.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.lbl_uuid)

        left_layout.addSpacing(SPACING_X)
        self.lbl_title = QLabel("QR code ใช้สำหรับ check in แต่ละบูธ")
        self.lbl_title.setObjectName("Title")
        self.lbl_title.setAlignment(Qt.AlignCenter)
        left_layout.addWidget(self.lbl_title)

        left_layout.addSpacing(int(0.5 * SPACING_X))
        qr_frame = QFrame()
        qr_inner_layout = QVBoxLayout()
        qr_inner_layout.setContentsMargins(12,12,12,12)
        self.lbl_qr = QLabel("[ QR CODE ]")
        self.lbl_qr.setFixedSize(300,300)
        self.lbl_qr.setAlignment(Qt.AlignCenter)
        qr_inner_layout.addWidget(self.lbl_qr, alignment=Qt.AlignCenter)
        qr_frame.setLayout(qr_inner_layout)
        left_layout.addWidget(qr_frame, alignment=Qt.AlignCenter)

        left_layout.addStretch(1)
        manual_text = ("คู่มือใช้งาน\n"
                       "1. หากสแกนเข้าร่วมไม่ติดให้ลองปรับความสว่างของหน้าจอ\n"
                       "2. ต้องเข้าร่วมกิจกรรมครบ n บูธเพื่อรับรางวัล\n"
                       "3. ตรวจสอบความคืบหน้าได้ที่จุดลงทะเบียน\n"
                       "4. หากเกิดปัญหาติดต่อ staff ที่แผนกต้อนรับ\n")
        self.lbl_manual = QLabel(manual_text)
        self.lbl_manual.setObjectName("Manual")
        self.lbl_manual.setAlignment(Qt.AlignTop)
        self.lbl_manual.setWordWrap(True)
        left_layout.addWidget(self.lbl_manual)
        self.left_frame.setLayout(left_layout)

        # Divider
        divider = QFrame()
        divider.setFrameShape(QFrame.VLine)
        divider.setStyleSheet("background:#e6e8eb;")

        # Right
        self.right_frame = QFrame()
        right_layout = QVBoxLayout()
        right_layout.setAlignment(Qt.AlignTop | Qt.AlignHCenter)
        self.lbl_state = QLabel("ยกนิ้วโป้งค้างไว้หน้ากล้องจนครบ 3 วินาที")
        self.lbl_state.setObjectName("State")
        self.lbl_state.setAlignment(Qt.AlignCenter)

        self.lbl_camera = QLabel()
        self.lbl_camera.setFixedSize(640,480)
        self.lbl_camera.setAlignment(Qt.AlignCenter)

        right_layout.addWidget(self.lbl_state, alignment=Qt.AlignTop | Qt.AlignHCenter)
        right_layout.addWidget(self.lbl_camera, alignment=Qt.AlignCenter)
        self.right_frame.setLayout(right_layout)

        body_layout.addWidget(self.left_frame, alignment=Qt.AlignCenter)
        body_layout.addWidget(divider)
        body_layout.addWidget(self.right_frame, alignment=Qt.AlignCenter)
        self.setLayout(body_layout)

        # --- Camera (UVC via V4L2 + MJPG) ---
        self.cap = None
        self._cam_fail_count = 0
        self._open_camera_with_retry()

        # --- MediaPipe ---
        self.hand_tracker = None
        try:
            self.hand_tracker = hand_module.HandTracker(max_hands=1)
            print("[MP] HandTracker initialized OK")
        except Exception as e:
            print(f"[MP] HandTracker disabled: {e}")

        # Timer
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

    # ---------- Camera open helpers ----------
    def _open_uvc(self, index=0):
        cap = cv2.VideoCapture(index, cv2.CAP_V4L2)
        if not cap.isOpened():
            return None
        # ตั้งค่าที่ UVC ส่วนใหญ่รองรับ + ลดโอกาสค้าง
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)
        # warm-up
        for _ in range(8):
            cap.read()
        return cap

    def _open_camera_with_retry(self):
        # ลอง /dev/video0 ก่อน แล้วค่อย /dev/video1
        for idx in (0, 1):
            cap = self._open_uvc(idx)
            if cap is not None:
                self.cap = cap
                print(f"[Cam] opened /dev/video{idx} (MJPG, 640x480@30)")
                return
        print("[Cam] cannot open UVC (/dev/video0/1).")

    # ---------- Helper: draw HUD (toggles/status) ----------
    def _draw_hud(self, frame_bgr):
        text = f"AI Paint: {'ON' if self.ai_paint_enabled else 'OFF'}  |  Preview: {'ON' if self.preview_enabled else 'OFF'}  |  E: AI  Q: Preview  R: Restart"
        (tw, th), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        h, w = frame_bgr.shape[:2]
        x0 = max(12, w - tw - 20)
        y0 = 14
        cv2.rectangle(frame_bgr, (x0-8, y0), (x0 + tw + 8, y0 + th + 16), (0,0,0), -1)
        cv2.putText(frame_bgr, text, (x0, y0 + th + 8),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,255,255), 2, cv2.LINE_AA)

    # ---------- Helper: fast path (AI OFF) -> 512x512 cover+center-crop ----------
    def _fast_make_painted(self, src_path, target_size=512):
        img = cv2.imread(src_path, cv2.IMREAD_COLOR)
        if img is None:
            raise RuntimeError(f"Cannot read image: {src_path}")
        h, w = img.shape[:2]
        scale = max(target_size / float(h), target_size / float(w))
        new_w, new_h = int(round(w * scale)), int(round(h * scale))
        interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
        resized = cv2.resize(img, (new_w, new_h), interpolation=interp)
        x0 = max(0, (new_w - target_size) // 2)
        y0 = max(0, (new_h - target_size) // 2)
        x1, y1 = x0 + target_size, y0 + target_size
        x0 = min(x0, max(0, new_w - target_size))
        y0 = min(y0, max(0, new_h - target_size))
        x1 = min(x1, new_w); y1 = min(y1, new_h)
        square = resized[y0:y1, x0:x1]
        if square.shape[:2] != (target_size, target_size):
            square = cv2.resize(square, (target_size, target_size), interpolation=cv2.INTER_AREA)
        utils.ensure_dir("output/paint")
        out_path = os.path.join("output/paint", utils.timestamp_name("paint_fast", "jpg"))
        cv2.imwrite(out_path, square)
        return out_path

    # ---------- Helper: blank canvas when preview off ----------
    def _blank_canvas(self, width=640, height=480):
        canvas = np.full((height, width, 3), (240, 242, 245), dtype=np.uint8)  # เทาอ่อน
        cv2.rectangle(canvas, (4, 4), (width-5, height-5), (210, 214, 220), 2) # กรอบ
        return canvas

    # ---------- Helper: thumbs-up status on canvas (preview off) ----------
    def _draw_thumbs_status(self, frame_bgr, is_yes: bool, hold_elapsed: float):
        # หมายเหตุ: ใช้อังกฤษ เพื่อเลี่ยงปัญหาภาษาไทยกับ cv2.putText
        h, w = frame_bgr.shape[:2]
        status = f"Thumbs up: {'YES' if is_yes else 'NO'}"
        color = (0, 180, 0) if is_yes else (80, 80, 80)
        (tw, th), _ = cv2.getTextSize(status, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 3)
        cx, cy = w//2, h//2
        cv2.rectangle(frame_bgr, (cx - tw//2 - 16, cy - th - 24), (cx + tw//2 + 16, cy + 16), (0, 0, 0), -1)
        cv2.putText(frame_bgr, status, (cx - tw//2, cy - 4), cv2.FONT_HERSHEY_SIMPLEX, 1.0, color, 3, cv2.LINE_AA)

        bar_w, bar_h = int(w * 0.6), 22
        x0 = (w - bar_w) // 2
        y0 = h - 50
        cv2.rectangle(frame_bgr, (x0, y0), (x0 + bar_w, y0 + bar_h), (70, 70, 70), 2)
        ratio = max(0.0, min(1.0, hold_elapsed / self.gesture_hold_req))
        fill_w = int(bar_w * ratio)
        cv2.rectangle(frame_bgr, (x0+2, y0+2), (x0 + 2 + fill_w, y0 + bar_h - 2),
                      (0, 200, 0) if is_yes else (170, 170, 170), -1)
        cv2.putText(frame_bgr, f"{hold_elapsed:.1f}s / {self.gesture_hold_req:.0f}s",
                    (x0, y0 - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (60, 60, 60), 2, cv2.LINE_AA)

    # ---------- Helper: draw QR logo image preview (center of canvas) ----------
    def _draw_qr_image_preview(self, frame_bgr, box_size=256):
        """
        แสดงภาพที่จะฝังใน QR (painted > captured) กลาง canvas
        """
        src_path = self.painted_path or self.captured_path
        h, w = frame_bgr.shape[:2]

        # วาง "กลางจอ" จริง ๆ
        box_w = box_h = box_size
        x0 = (w - box_w) // 2
        y0 = (h - box_h) // 2
        x1 = x0 + box_w
        y1 = y0 + box_h

        # กรอบ + ชื่อ
        cv2.rectangle(frame_bgr, (x0-6, y0-36), (x1+6, y1+6), (200, 200, 200), 2)
        title = "QR Image Preview"
        (tw, th), _ = cv2.getTextSize(title, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
        title_y = max(24, y0 - 12)
        cv2.putText(frame_bgr, title, (w//2 - tw//2, title_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (90, 90, 90), 2, cv2.LINE_AA)

        if not src_path or not os.path.exists(src_path):
            cv2.putText(frame_bgr, "No image yet", (w//2 - 70, y0 + box_h//2),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120,120,120), 2, cv2.LINE_AA)
            return

        # cache thumb
        if self._qr_thumb_cache_path != src_path or self._qr_thumb_cache_img is None:
            img = cv2.imread(src_path, cv2.IMREAD_COLOR)
            if img is None:
                cv2.putText(frame_bgr, "Failed to load image", (w//2 - 100, y0 + box_h//2),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (120,120,120), 2, cv2.LINE_AA)
                return
            ih, iw = img.shape[:2]
            scale = max(box_w/iw, box_h/ih)
            new_w, new_h = int(iw*scale), int(ih*scale)
            interp = cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC
            img_r = cv2.resize(img, (new_w, new_h), interpolation=interp)
            cx = (new_w - box_w) // 2
            cy = (new_h - box_h) // 2
            thumb = img_r[cy:cy+box_h, cx:cx+box_w]
            self._qr_thumb_cache_path = src_path
            self._qr_thumb_cache_img = thumb
        else:
            thumb = self._qr_thumb_cache_img

        frame_bgr[y0:y1, x0:x1] = thumb

    # ---------- Helper: reset to initial state (used by R) ----------
    def _reset_to_initial(self):
        self.countdown_active = False
        self.countdown_start = None
        self.gesture_hold_active = False
        self.gesture_hold_start = None
        self.cleanup_output()
        self.lbl_uuid.setText("uuid : ")
        self.lbl_qr.setText("[ QR CODE ]")
        self.lbl_state.setText("ยกนิ้วโป้งค้างไว้หน้ากล้องจนครบ 3 วินาที")
        self.state = "take_pic"
        print("[Action] Restart to initial state")

    def update_frame(self):
        # อ่านกล้อง พร้อม auto-reopen เมื่อ fail ต่อเนื่อง
        if self.cap is None:
            show_frame = self._blank_canvas(640, 480)
            cv2.putText(show_frame, "ไม่พบกล้อง / กล้องไม่พร้อม", (40, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,0,255), 2, cv2.LINE_AA)
            # แสดงบน QLabel แล้ว return
            rgb = cv2.cvtColor(show_frame, cv2.COLOR_BGR2RGB)
            img = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.shape[1]*3, QImage.Format_RGB888)
            self.lbl_camera.setPixmap(QPixmap.fromImage(img))
            # พยายามเปิดใหม่เป็นระยะ
            self._open_camera_with_retry()
            return

        ret, frame = self.cap.read()
        if not ret or frame is None or frame.size == 0:
            self._cam_fail_count += 1
            if self._cam_fail_count >= 10:
                print("[Cam] many read fails -> reopen")
                try:
                    self.cap.release()
                except:
                    pass
                self.cap = None
                self._open_camera_with_retry()
                self._cam_fail_count = 0

            show_frame = self._blank_canvas(640, 480)
            cv2.putText(show_frame, "กล้องไม่พร้อม กำลังลองเชื่อมต่อใหม่...",
                        (20, 240), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0,0,255), 2, cv2.LINE_AA)
            rgb = cv2.cvtColor(show_frame, cv2.COLOR_BGR2RGB)
            img = QImage(rgb.data, rgb.shape[1], rgb.shape[0], rgb.shape[1]*3, QImage.Format_RGB888)
            self.lbl_camera.setPixmap(QPixmap.fromImage(img))
            return
        else:
            self._cam_fail_count = 0

        # show_frame depends on preview mode
        if self.preview_enabled:
            show_frame = frame.copy()
        else:
            show_frame = self._blank_canvas(width=640, height=480)

        # ====== MediaPipe + Debounce เฉพาะ state แรก ======
        hold_elapsed = 0.0
        thumbs_up_detected = False

        if self.state == "take_pic" and self.hand_tracker is not None:
            try:
                # process on real camera frame (even if preview is off)
                _proc_frame = frame if frame is not None else np.zeros((480,640,3), dtype=np.uint8)
                proc_vis, hand_info = self.hand_tracker.process(_proc_frame, draw=self.preview_enabled)

                if self.preview_enabled:
                    show_frame = proc_vis

                thumbs_up_detected = (hand_info and hand_info.gesture == "thumbs_up")

                if thumbs_up_detected:
                    if not self.gesture_hold_active:
                        self.gesture_hold_active = True
                        self.gesture_hold_start = time.time()
                        print("[MP] thumbs_up detected -> start hold timer")
                    hold_elapsed = time.time() - self.gesture_hold_start
                else:
                    if self.gesture_hold_active:
                        print("[MP] thumbs_up lost -> reset hold timer")
                    self.gesture_hold_active = False
                    self.gesture_hold_start = None
                    hold_elapsed = 0.0

                # Hints (EN บนเฟรม), label ไทยแยกอยู่ด้านบน
                if self.preview_enabled:
                    cv2.putText(show_frame, "Hold thumbs up 3s -> auto countdown",
                                (16, 36), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 150, 255), 2, cv2.LINE_AA)
                    if self.gesture_hold_active:
                        h, w = show_frame.shape[:2]
                        bar_w, bar_h = int(w * 0.6), 18
                        x0 = (w - bar_w) // 2
                        y0 = h - 30
                        cv2.rectangle(show_frame, (x0, y0), (x0 + bar_w, y0 + bar_h), (50, 50, 50), 2)
                        ratio = max(0.0, min(1.0, hold_elapsed / self.gesture_hold_req))
                        fill_w = int(bar_w * ratio)
                        cv2.rectangle(show_frame, (x0+2, y0+2),
                                      (x0 + 2 + fill_w, y0 + bar_h - 2), (0, 200, 0), -1)
                        cv2.putText(show_frame, f"{hold_elapsed:.1f}s / {self.gesture_hold_req:.0f}s",
                                    (x0, y0 - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (30, 30, 30), 2, cv2.LINE_AA)
                else:
                    self._draw_thumbs_status(show_frame, thumbs_up_detected, hold_elapsed)

                # when hold complete -> start countdown
                if hold_elapsed >= self.gesture_hold_req and not self.countdown_active:
                    self.gesture_hold_active = False
                    self.gesture_hold_start = None
                    self.countdown_active = True
                    self.countdown_start = time.time()
                    self.countdown_time = 3
                    print("[Flow] gesture-hold OK -> start countdown (3..2..1)")
                    cv2.putText(show_frame, "Gesture OK! Starting countdown...",
                                (16, 64), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0,200,0), 3, cv2.LINE_AA)

            except Exception as e:
                print(f"[MP] runtime error: {e}")

        # ====== Countdown / State Flow ======
        if self.state == "take_pic":
            # ไทยบน QLabel
            if self.countdown_active:
                self.lbl_state.setText("ขยับให้ตรงและมองกล้อง")
            else:
                self.lbl_state.setText("ยกนิ้วโป้งค้างไว้หน้ากล้องจนครบ 3 วินาที")

            if self.countdown_active:
                elapsed = int(time.time() - self.countdown_start)
                remaining = self.countdown_time - elapsed

                # draw countdown on current canvas (preview on/off both)
                h, w, _ = show_frame.shape
                center = (w//2, h//2)
                radius = min(h, w) // 4
                cv2.circle(show_frame, center, radius, (0,255,0), 3)
                if remaining > 0:
                    count_text = str(remaining)
                    (tw, th), _ = cv2.getTextSize(count_text, cv2.FONT_HERSHEY_SIMPLEX, 2, 4)
                    cv2.putText(show_frame, count_text, (w//2 - tw//2, h//2 + th//2),
                                cv2.FONT_HERSHEY_SIMPLEX, 2, (0,255,0), 4, cv2.LINE_AA)
                else:
                    utils.ensure_dir("output/raw")
                    self.captured_path = os.path.join("output/raw", utils.timestamp_name("capture", "jpg"))
                    cv2.imwrite(self.captured_path, frame)  # always save real frame
                    print(f"[Flow] saved raw (countdown): {self.captured_path}")
                    self.state = "generate_paint"
                    self.countdown_active = False

        elif self.state == "generate_paint":
            self.lbl_state.setText(f"กำลังสร้างภาพสำหรับฝังใน QR... ({'AI เปิด' if self.ai_paint_enabled else 'โหมดเร็ว'})")
            try:
                if self.ai_paint_enabled:
                    self.painted_path = paint_model.generate_paint(self.captured_path, style=self.current_style, size=512)
                    print(f"[Flow] paint saved: {self.painted_path}")
                else:
                    self.painted_path = self._fast_make_painted(self.captured_path, target_size=512)
                    print(f"[Flow] fast-painted saved: {self.painted_path}")
            except Exception as e:
                print(f"[Flow] paint step error -> fallback to fast: {e}")
                self.painted_path = self._fast_make_painted(self.captured_path, target_size=512)

            self.state = "generate_qr"

        elif self.state == "generate_qr":
            self.lbl_state.setText("ถ่ายรูปแผ่นทางด้านซ้าย และนำ QR code มาตรวจสอบกับกล้อง")
            self.current_token = qr_module.gen_token(22)
            self.qr_path = qr_module.generate_qr_with_logo(
                self.current_token, self.painted_path, logo_scale=0.31, border_ratio=0.032
            )
            print(f"[Flow] token: {self.current_token}")
            self.lbl_uuid.setText(f"uuid : {self.current_token}")
            self.lbl_qr.setPixmap(QPixmap(self.qr_path).scaled(300, 300, Qt.KeepAspectRatio))

            # แสดงภาพโลโก้กลาง canvas ถ้า preview ปิด
            if not self.preview_enabled:
                self._draw_qr_image_preview(show_frame, box_size=256)

            self.state = "capture"

        elif self.state == "capture":
            self.lbl_state.setText("ถ่ายรูปแผ่นทางด้านซ้าย และนำ QR code มาตรวจสอบกับกล้อง \nหากสแกนไม่ติดลองปรับความสว่าง")

            # decode QR from live frame (camera)
            qrcodes = pyzbar.decode(frame)
            for qr in qrcodes:
                (x, y, w, h) = qr.rect
                if self.preview_enabled:
                    cv2.rectangle(show_frame, (x, y), (x+w, y+h), (0,0,255), 2)
                    cv2.putText(show_frame, "Wrong QR!", (x, y-10),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,0,255), 2)
                token_text = qr.data.decode("utf-8")
                if token_text == self.current_token:
                    print("[Flow] QR matched -> reset")
                    self.cleanup_output()
                    self.lbl_uuid.setText("uuid : ")
                    self.lbl_qr.setText("[ QR CODE ]")
                    self.state = "take_pic"

            # keep showing logo preview while waiting scan (preview OFF)
            if not self.preview_enabled:
                self._draw_qr_image_preview(show_frame, box_size=256)

        # HUD
        self._draw_hud(show_frame)

        # Show on QLabel
        rgb = cv2.cvtColor(show_frame, cv2.COLOR_BGR2RGB)
        h, w, ch = rgb.shape
        img = QImage(rgb.data, w, h, ch*w, QImage.Format_RGB888)
        self.lbl_camera.setPixmap(QPixmap.fromImage(img))

    def cleanup_output(self):
        for folder in ["output/raw", "output/paint", "output/qr"]:
            for f in glob.glob(os.path.join(folder, "*")):
                try: os.remove(f)
                except: pass
        self.captured_path = None
        self.painted_path = None
        self.qr_path = None
        self.current_token = None
        # reset preview cache
        self._qr_thumb_cache_path = None
        self._qr_thumb_cache_img = None

    def keyPressEvent(self, event):
        now = time.time()

        # SPACE = start countdown (in take_pic)
        if event.key() == Qt.Key_Space and self.state == "take_pic":
            if not self.countdown_active:
                self.countdown_active = True
                self.countdown_start = time.time()
                self.countdown_time = 3
                print("[Key] SPACE -> start countdown")

        # E = toggle AI Paint
        elif event.key() == Qt.Key_E:
            if now - self._last_key_time > 0.15:
                self.ai_paint_enabled = not self.ai_paint_enabled
                self._last_key_time = now
                print(f"[Key] Toggle AI Paint -> {'ON' if self.ai_paint_enabled else 'OFF'}")

        # Q = toggle Preview
        elif event.key() == Qt.Key_Q:
            if now - self._last_key_time > 0.15:
                self.preview_enabled = not self.preview_enabled
                self._last_key_time = now
                print(f"[Key] Toggle Preview -> {'ON' if self.preview_enabled else 'OFF'}")

        # R = Restart
        elif event.key() == Qt.Key_R:
            if now - self._last_key_time > 0.15:
                self._last_key_time = now
                self._reset_to_initial()

        # ESC = Exit
        elif event.key() == Qt.Key_Escape:
            self.close()

    def closeEvent(self, event):
        try:
            if self.cap:
                self.cap.release()
        except:
            pass


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())
