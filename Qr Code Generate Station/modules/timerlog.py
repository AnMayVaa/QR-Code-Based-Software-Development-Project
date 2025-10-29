# modules/timerlog.py
import time, os, csv, logging
from contextlib import contextmanager
from typing import List, Tuple

def _mk_logger(log_path: str):
    os.makedirs(os.path.dirname(log_path), exist_ok=True)
    logger = logging.getLogger("KIOS-TIMER")
    logger.setLevel(logging.INFO)

    # กันซ้อน handler หากถูก import ซ้ำ
    if logger.handlers:
        return logger

    fmt = logging.Formatter("[%(asctime)s] %(levelname)s: %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S.%f")
    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    fh = logging.FileHandler(log_path, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(ch)
    logger.addHandler(fh)
    return logger

class TimeTracker:
    """
    ใช้สำหรับจับเวลาแบบ end-to-end (wall-clock) ด้วย time.perf_counter()
    และเขียนทั้ง console + logs/kios.log + logs/timings.csv
    """
    def __init__(self, run_id: str, log_dir: str = "./logs"):
        os.makedirs(log_dir, exist_ok=True)
        self.run_id = run_id
        self.t0 = time.perf_counter()
        self.marks: List[Tuple[str, float]] = [("START", self.t0)]
        self.log_path = os.path.join(log_dir, "kios.log")
        self.csv_path = os.path.join(log_dir, "timings.csv")
        self.logger = _mk_logger(self.log_path)
        self.logger.info(f"[{self.run_id}] RUN START")

        # สร้างหัว CSV ถ้ายังไม่มี
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["run_id","stage","elapsed_ms","since_start_ms","wall_time"])

    def mark(self, stage: str):
        t = time.perf_counter()
        self.marks.append((stage, t))
        dt = (t - self.marks[-2][1]) * 1000.0
        since0 = (t - self.t0) * 1000.0
        # พิมพ์หน้าจอ + เขียนไฟล์ .log
        self.logger.info(f"[{self.run_id}] {stage} +{dt:.1f} ms (since {since0:.1f} ms)")
        # เขียนแถวลง CSV
        with open(self.csv_path, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([
                self.run_id,
                stage,
                f"{dt:.3f}",
                f"{since0:.3f}",
                time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            ])

    def finish(self):
        self.mark("END")
        total_ms = (self.marks[-1][1] - self.t0) * 1000.0
        self.logger.info(f"[{self.run_id}] TOTAL {total_ms:.1f} ms")

@contextmanager
def stage(tt: TimeTracker, name: str):
    tt.mark(f"{name}:BEGIN")
    try:
        yield
    finally:
        tt.mark(f"{name}:END")

def cpu_ms(fn, *args, **kwargs) -> float:
    """
    วัด CPU time ของฟังก์ชัน (ไม่รวม IO/wait) เพื่อใช้คู่กับ wall-clock
    """
    t0 = time.process_time()
    fn(*args, **kwargs)
    return (time.process_time() - t0) * 1000.0
