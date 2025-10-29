# modules/camera_module.py
import cv2, time, os

def open_camera(index=0, width=1280, height=720):
    cap = cv2.VideoCapture(index)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
    return cap

def draw_overlay(frame, countdown_active=False, countdown_start=None, countdown_time=3):
    h, w, _ = frame.shape
    cx, cy = w // 2, h // 2
    radius = 256  # 512x512 ครอบกลางภาพ
    cv2.circle(frame, (cx, cy), radius, (0, 255, 0), 3)

    if countdown_active:
        elapsed = time.time() - countdown_start
        remaining = countdown_time - int(elapsed)
        if remaining > 0:
            cv2.putText(frame, str(remaining),
                        (cx - 30, cy - radius - 20),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        3, (0, 255, 0), 5, cv2.LINE_AA)
        else:
            return True  # หมายถึง countdown จบ
    return False
