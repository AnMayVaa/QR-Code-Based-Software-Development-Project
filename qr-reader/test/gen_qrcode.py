import qrcode
import PIL
import secrets
import base64


class QRGen:
    def __init__(self):
        self.qr = qrcode.QRCode(
            version=2, error_correction=qrcode.constants.ERROR_CORRECT_H
        )

    def generate_token(self, length=22):
        return base64.urlsafe_b64encode(secrets.token_bytes(length)).decode("utf-8")[
            :length
        ]

    def generate_qrcode(self, data, filename=("qrcode.png")):
        self.qr.add_data(data)
        self.qr.make(fit=True)
        img = self.qr.make_image(fill_color="black", back_color="white")
        img.save(filename)
        print(f"QR code successfully saved as '{filename}'")
        self.qr.clear()


if __name__ == "__main__":
    qr_generator = QRGen()
    token = qr_generator.generate_token()
    print(token, len(token))
    qr_generator.generate_qrcode(token)
