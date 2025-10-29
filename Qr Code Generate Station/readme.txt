Pi server: 
tightvncserver :1
tightvncserver :1 -geometry 1920x1080 -depth 24 #for set resolution

tightvncserver -kill :1

su - usr #change user name

Download: 
# 0) ออกจาก venv เดิม (ถ้าเปิดค้าง)
deactivate 2>/dev/null || true

# 1) ติดตั้ง PyQt5 แบบระบบ (ห้าม pip)
sudo apt update
sudo apt install -y python3-pyqt5

# 2) (แนะนำ) สร้าง venv ใหม่ให้มองเห็นแพ็กเกจระบบ
cd ~/KIOS/KIOS
rm -rf venv
python3 -m venv --system-site-packages venv
source venv/bin/activate

# 3) ไลบรารีระบบที่จำเป็น (OpenCV/pyzbar/printing/BLAS/Qt X11)
sudo apt install -y libgl1 libglib2.0-0 libzbar0 ffmpeg python3-cupshelpers python3-cups
sudo apt install -y libopenblas0 libgfortran5
sudo apt install -y libxcb-xinerama0 libxkbcommon-x11-0 libxcb-cursor0

# 4) อัปเกรดเครื่องมือ และติดตั้งตาม requirements (ไม่มี PyQt5 ในไฟล์)
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt

# 5) ติดตั้ง PyTorch + Torchvision (CPU wheels สำหรับ Py3.11/aarch64)
pip install --index-url https://download.pytorch.org/whl/cpu \
  --only-binary=:all: \
  torch==2.2.2 torchvision==0.17.2

# 6) บังคับใช้ OpenCV แบบ headless (กันชนกับ Qt)
pip uninstall -y opencv-python opencv-contrib-python opencv-python-headless
pip install opencv-python-headless==4.11.0.86

Service: 
sudo nano /etc/systemd/system/kios.service

[Unit]
Description=KIOS GUI (PyQt5) for team1
# ผูกลำดับให้แน่ ๆ ว่า VNC :1 และ user manager ขึ้นก่อน
After=tightvnc-team1.service user@1001.service
Requires=tightvnc-team1.service

[Service]
Type=simple
User=team1
Group=team1
WorkingDirectory=/home/team1/KIOS/KIOS

# --- ENV จำเป็นสำหรับ GUI บน VNC :1 ภายใต้ user team1 ---
Environment=DISPLAY=:1
Environment=XAUTHORITY=/home/team1/.Xauthority
Environment=PYTHONUNBUFFERED=1
Environment=XDG_RUNTIME_DIR=/run/user/1001
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1001/bus

# รอให้ X socket (:1) และ dbus session พร้อมก่อน (สูงสุด 60s)
ExecStartPre=/bin/sh -c 'for i in $(seq 1 60); do [ -S /tmp/.X11-unix/X1 ] && [ -S /run/user/1001/bus ] && exit 0; sleep 1; done; exit 1'

# เรียก python จาก venv โดยตรง (ไม่ต้อง activate)
ExecStart=/home/team1/KIOS/KIOS/venv/bin/python /home/team1/KIOS/KIOS/main.py

Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
_______________
sudo nano /etc/systemd/system/tightvnc-team1.service

[Unit]
Description=TightVNC Server :1 (1920x1080) for team1
After=network-online.target
Wants=network-online.target

[Service]
Type=forking
User=team1
Group=team1
# ไม่ใส่ PIDFile เพื่อตัดปัญหาชื่อไฟล์
ExecStart=/usr/bin/tightvncserver :1 -geometry 1920x1080 -depth 24
ExecStop=/usr/bin/tightvncserver -kill :1
Restart=on-failure
RestartSec=3
TimeoutStartSec=30

[Install]
WantedBy=multi-user.target

_______________
sudo systemctl daemon-reload
sudo systemctl restart kios.service
systemctl status kios.service
_______________
# สถานะ / ล็อก
systemctl status kios.service
journalctl -u kios.service -e

# ควบคุม
sudo systemctl restart kios.service
sudo systemctl stop kios.service

# เปิด/ปิดออโต้บูต
sudo systemctl enable kios.service
sudo systemctl disable kios.service




