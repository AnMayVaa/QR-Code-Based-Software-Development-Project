import time
import configparser
import pytz
import re
import serial
import serial.tools.list_ports
from qr_reader import QRData
from reader_logic import ReaderLogic, poll_mode_from_serial, apply_forced_mode
from datetime import datetime
from threading import Thread
from evdev import InputDevice, ecodes, categorize
from queue import Queue, Empty

CONFIG_FILE = "config.ini"
send_interval = 2
message_span = ""
message_expiry_time = 0

# อ่านไฟล์ config.ini
config = configparser.ConfigParser()

try:
    config.read(CONFIG_FILE)
    DEVICE_LOCATION = config.get("Device", "Location")
    SCAN_COOLDOWN = config.getint("Device", "ScanCooldown")
    CHECKIN_CHECKOUT_DURATION = config.getint("Device", "StayDuration")
except Exception as e:
    print(f"Configure file error: {e}")
    exit()

# --- evdev-based input for USB barcode scanner on Pi + xrdp ---

SHIFT_KEYS = {ecodes.KEY_LEFTSHIFT, ecodes.KEY_RIGHTSHIFT}

# แผนที่คีย์สำหรับ base64url-ish token: [A-Za-z0-9_-]
KEYMAP = {
    # digits row
    ecodes.KEY_0:'0', ecodes.KEY_1:'1', ecodes.KEY_2:'2', ecodes.KEY_3:'3', ecodes.KEY_4:'4',
    ecodes.KEY_5:'5', ecodes.KEY_6:'6', ecodes.KEY_7:'7', ecodes.KEY_8:'8', ecodes.KEY_9:'9',
    # letters
    ecodes.KEY_A:'a', ecodes.KEY_B:'b', ecodes.KEY_C:'c', ecodes.KEY_D:'d', ecodes.KEY_E:'e',
    ecodes.KEY_F:'f', ecodes.KEY_G:'g', ecodes.KEY_H:'h', ecodes.KEY_I:'i', ecodes.KEY_J:'j',
    ecodes.KEY_K:'k', ecodes.KEY_L:'l', ecodes.KEY_M:'m', ecodes.KEY_N:'n', ecodes.KEY_O:'o',
    ecodes.KEY_P:'p', ecodes.KEY_Q:'q', ecodes.KEY_R:'r', ecodes.KEY_S:'s', ecodes.KEY_T:'t',
    ecodes.KEY_U:'u', ecodes.KEY_V:'v', ecodes.KEY_W:'w', ecodes.KEY_X:'x', ecodes.KEY_Y:'y',
    ecodes.KEY_Z:'z',
    # symbols we accept
    ecodes.KEY_MINUS:'-',  # '_' จะมาจาก Shift + MINUS
    # keypad (รองรับ NumLock ทั้งคู่)
    ecodes.KEY_KP0:'0', ecodes.KEY_KP1:'1', ecodes.KEY_KP2:'2', ecodes.KEY_KP3:'3', ecodes.KEY_KP4:'4',
    ecodes.KEY_KP5:'5', ecodes.KEY_KP6:'6', ecodes.KEY_KP7:'7', ecodes.KEY_KP8:'8', ecodes.KEY_KP9:'9',
}

def evdev_reader(dev_path, q):
    dev = InputDevice(dev_path)
    buf = []
    shift = False
    for event in dev.read_loop():
        if event.type != ecodes.EV_KEY:
            continue
        ke = categorize(event)

        # track shift
        if ke.scancode in SHIFT_KEYS:
            shift = (ke.keystate == 1)  # 1=down, 0=up
            continue

        if ke.keystate != 1:  # key down only
            continue

        # ENTER or KEYPAD ENTER → ส่งหนึ่งบรรทัด
        if ke.keycode in ('KEY_ENTER', 'KEY_KPENTER'):
            token = ''.join(buf).strip()
            buf.clear()
            if token:
                q.put(token)
            continue

        ch = KEYMAP.get(ke.scancode)
        if not ch:
            continue

        # uppercase when shift
        if 'a' <= ch <= 'z' and shift:
            ch = ch.upper()
        # underscore when Shift + minus
        if ch == '-' and shift:
            ch = '_'

        buf.append(ch)


def get_serial_port(baudrate=115200, timeout=1):
    try:
        while True:
            ports = list(serial.tools.list_ports.comports())
            if not ports:
                print("No serial ports found. Retrying in 2 seconds...")
                time.sleep(2)
                continue
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
        print("QR Code Reading is shutting down.")
        exit()


ser = get_serial_port()
qr_reader = ReaderLogic(DEVICE_LOCATION, SCAN_COOLDOWN, CHECKIN_CHECKOUT_DURATION)
timezone = pytz.timezone("Asia/Bangkok")
time_format = "%I:%M:%S %p"
token_format = re.compile(r"^[A-Za-z0-9_\-]{22}$")
scan_history = qr_reader.scan_history
check_mode = 1

q = Queue()
DEV_PATH = "/dev/input/by-id/usb-SM_SM-2D_PRODUCT_HID_KBW_APP-000000000-event-kbd"
t = Thread(target=evdev_reader, args=(DEV_PATH, q), daemon=True)
t.start()


try:
    while True:
        try:
            current_time = time.time()
            check_mode = poll_mode_from_serial(ser, check_mode)
            if current_time > message_expiry_time:
                message_span = ""
                try:
                    token = q.get_nowait()
                except Empty:
                    time.sleep(0.01)
                    continue
                if token_format.match(token):
                    result = qr_reader.read_qr(token)
                    result = apply_forced_mode(qr_reader, token, result, check_mode)
                    status = result.get("status", -1)
                    if result["qr_data"] and result["status"] != -1:
                        qr_data = QRData(
                            token, DEVICE_LOCATION, result["status"], int(time.time())
                        )
                        try:
                            ser.write(
                                (
                                    f"{token},{result['status']},{datetime.now(timezone).strftime(time_format)}" + "\n"
                                ).encode("utf-8")
                            )
                            qr_data.write_data()
                            print(
                                f'{result["message"]} at: {datetime.now(timezone).strftime(time_format)}'
                            )
                        except serial.SerialException:
                            print("Serial port disconnected. Attempting to reconnect...")
                            ser.close()
                            ser = get_serial_port()
                    elif status == -1:
                        next_checkout_str = result.get("next_checkout_str")
                        if next_checkout_str:
                            try:
                                ser.write(f"TIME,-1,Checkout at {result['next_checkout_str']}\n".encode("utf-8"))
                                print(f'{result["message"]} | Checkout time: {next_checkout_str}')
                            except serial.SerialException:
                                print("Serial port disconnected. Attempting to reconnect...")
                                ser.close()
                                ser = get_serial_port()
                        else:
                            print(f'{result["message"]} at: {datetime.now(timezone).strftime(time_format)}')


                    message_expiry_time = time.time() + send_interval
                    print(scan_history)

        except serial.SerialException:
            print("Serial port disconnected. Attempting to reconnect...")
            ser = get_serial_port()
        except Exception as e:
            print(
                f'Error: {e} at: {datetime.now(timezone).strftime(time_format)}'
            )
            continue



except KeyboardInterrupt:
    print("QR Code Reader is shutting down...")
