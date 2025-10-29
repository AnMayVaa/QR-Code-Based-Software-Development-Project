import qrcode
from PIL import Image, ImageDraw
import os
import base64, secrets

def gen_token(length=22):
    """สร้าง token base64url แบบสั้น ใช้เป็นรหัสใน QR"""
    return base64.urlsafe_b64encode(secrets.token_bytes(length)).decode("utf-8")[:length]

def generate_qr_with_logo(token,
                          logo_path,
                          output_dir="output/qr",
                          logo_scale=0.3,        # โลโก้ ~30% ของ QR
                          border_ratio=0.15):   # ขอบขาว 15% ของโลโก้
    os.makedirs(output_dir, exist_ok=True)

    # -------------------------------
    # สร้าง QR code
    # -------------------------------
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_H)
    qr.add_data(token)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # -------------------------------
    # ใส่ logo วงกลม + ขอบขาวกลม
    # -------------------------------
    if logo_path and os.path.exists(logo_path):
        logo = Image.open(logo_path).convert("RGBA")

        # ทำให้โลโก้เป็นวงกลม
        size = min(logo.size)
        mask = Image.new("L", (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        logo = logo.resize((size, size), Image.LANCZOS)
        logo.putalpha(mask)

        # resize logo ตามสัดส่วน QR
        w, h = img.size
        logo_size = int(w * logo_scale)
        logo = logo.resize((logo_size, logo_size), Image.LANCZOS)

        # สร้างวงกลมขอบขาว
        border_size = int(logo_size * border_ratio)
        bordered_size = logo_size + border_size * 2
        bordered_logo = Image.new("RGBA", (bordered_size, bordered_size), (255, 255, 255, 0))
        mask = Image.new("L", (bordered_size, bordered_size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, bordered_size, bordered_size), fill=255)

        # วาดพื้นหลังวงกลมสีขาว
        white_circle = Image.new("RGBA", (bordered_size, bordered_size), (255, 255, 255, 255))
        bordered_logo.paste(white_circle, (0, 0), mask)

        # วางโลโก้ลงบนวงกลมขาว
        bordered_logo.paste(logo, (border_size, border_size), logo)

        # วางลงกลาง QR
        pos = ((w - bordered_size) // 2, (h - bordered_size) // 2)
        img.paste(bordered_logo, pos, bordered_logo)

    # -------------------------------
    # Save file
    # -------------------------------
    path = os.path.join(output_dir, "qr_with_logo.png")
    img.save(path)
    return path
