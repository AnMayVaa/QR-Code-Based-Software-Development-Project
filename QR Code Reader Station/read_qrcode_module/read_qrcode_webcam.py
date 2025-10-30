import os
os.environ.setdefault("QT_QPA_PLATFORM", "xcb")

import cv2
import time
import configparser
import pytz
import re
import serial
import serial.tools.list_ports
import numpy as np
from pyzbar.pyzbar import decode, ZBarSymbol
from datetime import datetime
from qr_reader import QRData
from camera import Camera
from reader_logic import ReaderLogic, poll_mode_from_serial, apply_forced_mode


CONFIG_FILE = "config.ini"
CV2_FRAME   = "QR Code Scanner"

RED_COLOR    = (0, 0, 255)
GREEN_COLOR  = (0, 255, 0)
BLUE_COLOR   = (255, 0, 0)
YELLOW_COLOR = (255, 255, 0)
WHITE_COLOR  = (255, 255, 255)

SEND_INTERVAL_SEC = 5          # กันยิงซ้ำไปที่ ESP32 / เขียน log
DISPLAY_HOLD_SEC  = 3        # <<< เวลาหน่วงโชว์ข้อความหลังสแกนสำเร็จ (วินาที)
message_expiry_time = 0

# -------------------- LOAD CONFIG --------------------
config = configparser.ConfigParser()
try:
    config.read(CONFIG_FILE)
    LOCATION                  = config.get("Device", "Location")
    SCAN_COOLDOWN             = config.getint("Device", "ScanCooldown")
    CHECKIN_CHECKOUT_DURATION = config.getint("Device", "StayDuration")
except Exception as e:
    print(f"Configure file error: {e}")
    raise SystemExit(1)

# -------------------- HELPERS --------------------
def drawText(frame, x, y, text, color=GREEN_COLOR):
    cv2.putText(frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2, cv2.LINE_AA)

def showResult(frame, roi_x, roi_y, reader_size, color):
    cv2.rectangle(frame, (roi_x, roi_y), (roi_x + reader_size, roi_y + reader_size), color, 3)

def get_serial_port(baudrate=115200, timeout=1):
    try:
        while True:
            ports = list(serial.tools.list_ports.comports())
            if not ports:
                print("No serial ports found. Retrying in 2 seconds...")
                time.sleep(2); continue
            for p in ports:
                try:
                    ser = serial.Serial(p.device, baudrate, timeout=timeout)
                    print(f"Connected to serial port: {p.device}")
                    return ser
                except serial.SerialException:
                    continue
            print("No available serial ports. Retrying in 2 seconds...")
            time.sleep(2)
    except KeyboardInterrupt:
        print("QR Code Reader is shutting down..."); raise SystemExit

def get_camera(max_index=5, retry_delay=2):
    while True:
        for cam in range(max_index):
            cap = Camera(camera_index=cam)  # ตั้งค่า FOURCC/FPS ใน camera.py
            if hasattr(cap, "cap") and cap.cap.isOpened():
                print(f"Camera index {cam} is available.")
                return cap
        print("No available camera devices. Retrying in 2 seconds...")
        time.sleep(retry_delay)

def safe_write_log(token, status, ts_now):
    """กันไฟล์ log พัง: ถ้าเขียนล้มเหลว จะรีเซ็ตเป็น [] แล้วลองใหม่"""
    try:
        QRData(token, LOCATION, status, int(ts_now)).write_data()
        return
    except Exception as e:
        print("log write error, trying to reset file:", e)
        LOG_FILE = "qr_log.json"
        try:
            if os.path.exists(LOG_FILE):
                os.replace(LOG_FILE, LOG_FILE + f".corrupt.{int(time.time())}.json")
            with open(LOG_FILE, "w", encoding="utf-8") as f:
                f.write("[]")
            QRData(token, LOCATION, status, int(ts_now)).write_data()
        except Exception as e2:
            print("fatal: cannot reset log file:", e2)

# -------------------- INIT --------------------
ser = get_serial_port()
cap = get_camera()

qr_reader = ReaderLogic(LOCATION, SCAN_COOLDOWN, CHECKIN_CHECKOUT_DURATION)
timezone   = pytz.timezone("Asia/Bangkok")
time_format = "%I:%M:%S %p"
token_format = re.compile(r"^[A-Za-z0-9_\-]{22}$")  # base64url 22 ตัว
check_mode = 1
scan_history = qr_reader.scan_history

cv2.namedWindow(CV2_FRAME, cv2.WINDOW_NORMAL)
cv2.setWindowProperty(CV2_FRAME, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)

# สถานะแสดงผลค้างหลังสแกน
last_info = None         # tuple: (message, color, roi_x, roi_y, reader_size, timestamp_str)
display_until = 0

# -------------------- MAIN LOOP --------------------
try:
    bad_frames = 0
    while True:
        try:
            check_mode = poll_mode_from_serial(ser, check_mode)

            ret, frame = cap.get_frame()
            if not ret or frame is None:
                bad_frames += 1
                if bad_frames >= 5:
                    cap.release(); cap = get_camera(); bad_frames = 0
                continue
            bad_frames = 0

            # ปิดโปรแกรมแบบนุ่มนวล
            if (cv2.waitKey(1) & 0xFF) == ord("q") or cv2.getWindowProperty(CV2_FRAME, cv2.WND_PROP_VISIBLE) < 1:
                print("QR Code Reading is shutting down.")
                break

            now_str = datetime.now(timezone).strftime(time_format)
            drawText(frame, 10, 30, now_str, YELLOW_COLOR)

            # ROI กลางจอ (ปรับใหญ่ช่วยเล็ง QR ที่มีโลโก้) + กันหลุดขอบ
            h, w, _ = frame.shape
            reader_size = int(min(h, w) * 0.7)
            roi_x = max(0, (w - reader_size) // 2)
            roi_y = max(0, (h - reader_size) // 2)
            roi_x2 = min(w, roi_x + reader_size)
            roi_y2 = min(h, roi_y + reader_size)

            # ถ้ายังอยู่ในช่วง "หน่วงแสดงผล" ให้โชว์ข้อความเดิมแล้วข้ามการสแกน
            if last_info and time.time() < display_until:
                msg, color, lx, ly, lsize, ts_str = last_info
                showResult(frame, lx, ly, lsize, color)
                drawText(frame, lx, ly - 50, f"{msg} at: {ts_str}", color)
                # UI ช่วยเล็ง + แสดงผล
                drawText(frame, roi_x, roi_y - 10, "Place QR Code here", BLUE_COLOR)
                cv2.rectangle(frame, (roi_x, roi_y), (roi_x + reader_size, roi_y + reader_size), (255,255,255), 3)
                cv2.imshow(CV2_FRAME, frame)
                continue
            else:
                last_info = None  # หมดเวลาแสดงผลแล้ว

            # จำกัดอัตราการสแกน/ส่ง
            if time.time() > message_expiry_time:
                # ----- เตรียมภาพสำหรับ pyzbar -----
                roi = frame[roi_y:roi_y2, roi_x:roi_x2]
                if roi is None or roi.size == 0:
                    print("No QR Code")
                    message_expiry_time = time.time() + SEND_INTERVAL_SEC
                    cv2.imshow(CV2_FRAME, frame)
                    continue

                gray  = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
                gray  = clahe.apply(gray)

                th1 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                            cv2.THRESH_BINARY, 31, 5)
                th2 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]

                candidates = [gray, th1, th2]
                for base in [gray, th1, th2]:
                    candidates.append(cv2.resize(base, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_LINEAR))

                token = None
                for img in candidates:
                    img = np.ascontiguousarray(img, dtype=np.uint8)
                    for k in range(4):
                        test = np.rot90(img, k)
                        try:
                            res = decode(test, symbols=[ZBarSymbol.QRCODE])
                        except Exception:
                            res = []
                        if not res:
                            continue
                        data_bytes = getattr(res[0], "data", b"")
                        if not data_bytes:
                            continue
                        token = data_bytes.decode("utf-8", errors="ignore").strip()
                        if token:
                            break
                    if token:
                        break

                if not token:
                    print("No QR Code")
                elif token_format.match(token):
                    result = qr_reader.read_qr(token)
                    result = apply_forced_mode(qr_reader, token, result, check_mode)

                    if result:
                        status = result["status"]
                        color  = GREEN_COLOR if status == 1 else RED_COLOR if status == 0 else WHITE_COLOR

                        if status != -1  and result.get("qr_data"):
                            safe_write_log(token, status, time.time())
                            try:
                                ser.write(f"{token},{status},{now_str}\n".encode("utf-8"))
                            except serial.SerialException:
                                print("Serial port disconnected. Attempting to reconnect...")
                                try: ser.close()
                                except Exception: pass
                                ser = get_serial_port()
                        else:
                            # กรณี 5 นาทีสุดท้ายก่อน checkout: ส่งเวลาเหลือ MM:SS ไปที่ Serial
                            next_checkout_str = result.get("next_checkout_str")
                            if next_checkout_str:
                                try:
                                    ser.write(f"TIME,-1,Checkout at {next_checkout_str}\n".encode("utf-8"))
                                except serial.SerialException:
                                    print("Serial port disconnected. Attempting to reconnect...")
                                    try: ser.close()
                                    except Exception: pass
                                    ser = get_serial_port()

                        print(
                            f'{result["message"]} at: {datetime.now(timezone).strftime(time_format)}'
                        )
                        extra = f" | Checkout time: {result.get('next_checkout_str')}" if result.get("next_checkout_str") else ""
                        showResult(frame, roi_x, roi_y, reader_size, color)
                        drawText(frame, roi_x, roi_y - 50, f"{result['message']}{extra} at: {now_str}", color)
                        last_info = (result["message"] + extra, color, roi_x, roi_y, reader_size, now_str)
                        display_until = time.time() + DISPLAY_HOLD_SEC
                        print(scan_history)

                message_expiry_time = time.time() + SEND_INTERVAL_SEC

            # UI ช่วยเล็ง
            drawText(frame, roi_x, roi_y - 10, "Place QR Code here", BLUE_COLOR)
            cv2.rectangle(frame, (roi_x, roi_y), (roi_x + reader_size, roi_y + reader_size), (255, 255, 255), 3)
            cv2.imshow(CV2_FRAME, frame)

        except serial.SerialException:
            print("Serial port disconnected. Attempting to reconnect...")
            try: ser.close()
            except Exception: pass
            ser = get_serial_port()
        except Exception as e:
            print(f"Error: {e} at: {datetime.now(timezone).strftime('%H:%M:%S')}")
            continue

except KeyboardInterrupt:
    print("QR Code Reader is shutting down...")
finally:
    cap.release()
    cv2.destroyAllWindows()
