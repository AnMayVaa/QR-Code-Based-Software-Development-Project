# modules/paint_model.py
# ใช้ AnimeGAN2 ผ่าน torch.hub + face2paint
# รองรับการเปลี่ยน style ได้ง่าย เช่น "celeba_distill", "paprika"

import os
import cv2
import torch
import numpy as np
from PIL import Image

# เลือกอุปกรณ์ (Pi4 จะได้ "cpu")
_DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

# cache โมเดลไว้ ไม่ต้องโหลดซ้ำทุกครั้ง
_CACHED = {"style": None, "size": None, "gen": None, "face2paint": None}


def _get_models(style: str = "face_paint_512_v2", size: int = 512):
    """
    โหลด/คืนค่าโมเดล generator + face2paint ตาม style/size
    """
    global _CACHED

    reload_needed = (
        _CACHED["gen"] is None
        or _CACHED["style"] != style
        or _CACHED["size"] != size
    )
    if reload_needed:
        print(f"⬇ Loading AnimeGAN2 ({style}, size={size}) on {_DEVICE} ...")
        gen = torch.hub.load(
            "bryandlee/animegan2-pytorch:main",
            "generator",
            pretrained=style
        ).to(_DEVICE).eval()

        face2paint = torch.hub.load(
            "bryandlee/animegan2-pytorch:main",
            "face2paint",
            size=size
        )

        _CACHED.update({
            "style": style,
            "size": size,
            "gen": gen,
            "face2paint": face2paint,
        })
        print("✅ Model ready (cached).")

    return _CACHED["gen"], _CACHED["face2paint"]


def cartoonize_bgr(bgr_frame: np.ndarray,
                   style: str = "face_paint_512_v2",
                   size: int = 512) -> np.ndarray:
    """
    รับเฟรม BGR (จาก OpenCV) -> คืนภาพ BGR ที่ผ่านสไตล์เพนท์แล้ว
    """
    gen, face2paint = _get_models(style=style, size=size)

    # BGR -> RGB -> PIL
    rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
    pil = Image.fromarray(rgb)

    # inference ผ่าน face2paint
    out_pil = face2paint(gen, pil)

    # กลับเป็น BGR ให้ OpenCV
    out_bgr = cv2.cvtColor(np.array(out_pil), cv2.COLOR_RGB2BGR)
    return out_bgr


def generate_paint(input_path: str,
                   output_dir: str = "output/paint",
                   style: str = "face_paint_512_v2",
                   size: int = 512) -> str:
    """
    รับพาธรูป (เช่น output/raw/capture.jpg) แล้วเซฟภาพแนวเพนท์ลงโฟลเดอร์ output/paint
    คืนพาธไฟล์ผลลัพธ์
    """
    os.makedirs(output_dir, exist_ok=True)

    # โหลดภาพจากไฟล์เป็น BGR (OpenCV)
    bgr = cv2.imread(input_path)
    if bgr is None:
        raise FileNotFoundError(f"ไม่พบภาพ: {input_path}")

    # แปลงเป็นแนวเพนท์
    out_bgr = cartoonize_bgr(bgr, style=style, size=size)

    # พาธที่จะเซฟ
    output_path = os.path.join(output_dir, f"painted_{style}.jpg")

    success = cv2.imwrite(output_path, out_bgr)
    if not success:
        raise RuntimeError(f"❌ ไม่สามารถบันทึกไฟล์ได้: {output_path}")

    print(f"🎨 Saved painted image: {output_path}")
    return output_path
