# modules/qr_scanner.py
import cv2
from pyzbar.pyzbar import decode

def scan_qr(frame, target_token):
    qrs = decode(frame)
    for qr in qrs:
        data = qr.data.decode("utf-8")
        if data == target_token:
            (x, y, w, h) = qr.rect
            cv2.rectangle(frame, (x, y), (x+w, y+h), (0,255,0), 3)
            return True, frame
    return False, frame
