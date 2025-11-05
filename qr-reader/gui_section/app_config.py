import re, configparser, pytz

CONFIG_FILE = "config.ini"
cfg = configparser.ConfigParser()
cfg.read(CONFIG_FILE)

DEFAULT_LOCATION = cfg.get("Device", "Location", fallback="จุดที่ 1")
SCAN_COOLDOWN = cfg.getint("Device", "ScanCooldown", fallback=5)
STAY_DURATION = cfg.getint("Device", "StayDuration", fallback=600)


def booth_list():
    raw = cfg.get("BoothList", "Names", fallback="").strip()
    items = [s.strip() for s in raw.split(",") if s.strip()] if raw else []
    if DEFAULT_LOCATION not in items:
        items = [DEFAULT_LOCATION] + items
    # de-duplicate case-insensitively
    seen, out = set(), []
    for s in items:
        k = s.lower()
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
    return (
        out
        if out
        else [DEFAULT_LOCATION, "จุดที่ 2", "จุดที่ 3", "ประตูเข้า", "ประตูออก", "อื่น ๆ"]
    )


# Scanner settings
SC_TERM = cfg.get("Scanner", "Terminator", fallback="CRLF").upper()
SC_MINLEN = cfg.getint("Scanner", "MinLength", fallback=6)
SC_TMO_MS = cfg.getint("Scanner", "TimeoutMs", fallback=250)
TERM_MAP = {"CR": "\r", "LF": "\n", "CRLF": "\r\n", "NONE": ""}
TERMINATOR = TERM_MAP.get(SC_TERM, "\r\n")

# Misc
TZ = pytz.timezone("Asia/Bangkok")
TIME_FMT_HMS = "%H:%M:%S"
TOKEN_RE = re.compile(r"^[A-Za-z0-9_\-]{22}$")
RATE_LIMIT_S = 1.0
