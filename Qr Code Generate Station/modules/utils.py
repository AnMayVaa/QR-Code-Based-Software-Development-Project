# modules/utils.py
import os, time

def ensure_dir(path):
    os.makedirs(path, exist_ok=True)

def timestamp_name(prefix="file", ext="jpg"):
    return f"{prefix}_{time.strftime('%Y%m%d_%H%M%S')}.{ext}"
