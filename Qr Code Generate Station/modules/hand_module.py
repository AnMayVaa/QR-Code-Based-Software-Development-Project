# modules/hand_module.py
# Debug-friendly MediaPipe Hands wrapper

from dataclasses import dataclass
from typing import Optional, Tuple, List
import cv2
import numpy as np

try:
    import mediapipe as mp
    MP_OK = True
except Exception as e:
    mp = None
    MP_OK = False
    MP_IMPORT_ERROR = e


@dataclass
class HandInfo:
    handedness: Optional[str] = None     # 'Left' / 'Right'
    landmarks: Optional[List[Tuple[int, int]]] = None  # pixel coords
    gesture: Optional[str] = None        # 'thumbs_up' / 'none'
    debug_text: str = ""                 # status for on-screen debug


class HandTracker:
    """
    process(frame_bgr, draw=True) -> (annotated_bgr, HandInfo)
    - จะรีไซซ์ลงก่อนประมวลผลให้เบา (default ย่อฝั่งยาวสุด ~640 px)
    - วาดโครงร่าง + เขียน debug_text ลงมุมซ้ายบน
    """

    def __init__(
        self,
        static_mode: bool = False,
        max_hands: int = 2,
        min_detection_confidence: float = 0.6,
        min_tracking_confidence: float = 0.5,
        max_side: int = 640,   # รีไซซ์ภาพเข้ากับ mediapipe เพื่อความเร็ว/เสถียร
    ):
        if not MP_OK:
            raise ImportError(
                f"mediapipe import failed: {MP_IMPORT_ERROR}\n"
                "ติดตั้งใน venv: pip install mediapipe==0.10.14"
            )

        self.max_side = max_side
        self.mp_hands = mp.solutions.hands
        self.mp_draw = mp.solutions.drawing_utils
        self.mp_style = mp.solutions.drawing_styles

        # model_complexity=0 เร็วขึ้น เหมาะกับ Pi
        self.hands = self.mp_hands.Hands(
            static_image_mode=static_mode,
            max_num_hands=max_hands,
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
            model_complexity=0,
        )

        # เวอร์ชันไว้ดีบัก
        try:
            import pkg_resources
            self.mp_version = pkg_resources.get_distribution("mediapipe").version
        except Exception:
            self.mp_version = "unknown"

    def process(self, frame_bgr: np.ndarray, draw: bool = True) -> Tuple[np.ndarray, HandInfo]:
        info = HandInfo(gesture="none", debug_text=f"MP v{self.mp_version} | ")

        if frame_bgr is None or frame_bgr.size == 0:
            info.debug_text += "no_frame"
            return frame_bgr, info

        # รีไซซ์ให้ด้านยาวสุด = self.max_side (รักษาอัตราส่วน)
        h0, w0 = frame_bgr.shape[:2]
        scale = 1.0
        if max(h0, w0) > self.max_side:
            if h0 >= w0:
                scale = self.max_side / float(h0)
            else:
                scale = self.max_side / float(w0)
        resized = cv2.resize(frame_bgr, (int(w0 * scale), int(h0 * scale)), interpolation=cv2.INTER_LINEAR)

        # BGR -> RGB (สำคัญมากสำหรับ mediapipe)
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        # ตามคู่มือ mediapipe: set writeable=False ก่อน process
        rgb.flags.writeable = False
        results = self.hands.process(rgb)
        rgb.flags.writeable = True

        annotated = resized.copy()
        hands_count = 0

        if results.multi_hand_landmarks:
            hands_count = len(results.multi_hand_landmarks)
            # เอาเฉพาะมือแรก (ตาม max_hands=1)
            hand_landmarks = results.multi_hand_landmarks[0]
            handedness = None
            if results.multi_handedness:
                handedness = results.multi_handedness[0].classification[0].label  # 'Left'/'Right'
            info.handedness = handedness

            # แปลง landmark -> พิกัดภาพ resized
            h, w = annotated.shape[:2]
            pts = []
            for lm in hand_landmarks.landmark:
                x = int(lm.x * w)
                y = int(lm.y * h)
                pts.append((x, y))
            info.landmarks = pts

            # ตรวจท่า thumbs up แบบ heuristic
            if self._is_thumbs_up(pts):
                info.gesture = "thumbs_up"

            if draw:
                self.mp_draw.draw_landmarks(
                    annotated,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_style.get_default_hand_landmarks_style(),
                    self.mp_style.get_default_hand_connections_style(),
                )
        else:
            info.handedness = None
            info.landmarks = None

        info.debug_text += f"hands:{hands_count} | gest:{info.gesture}"

        # ขยายกลับขนาดเดิม เพื่อให้ overlay กลับไปพอดีกับ UI เดิม
        if scale != 1.0:
            annotated = cv2.resize(annotated, (w0, h0), interpolation=cv2.INTER_LINEAR)

        # เขียน debug_text ลงบนภาพ (มุมซ้ายบน)
        cv2.rectangle(annotated, (8, 8), (8 + 420, 8 + 36), (0, 0, 0), -1)
        cv2.putText(annotated, info.debug_text, (16, 34),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2, cv2.LINE_AA)

        return annotated, info

    @staticmethod
    @staticmethod
    def _is_thumbs_up(pts):
        """
        เงื่อนไขเข้มขึ้น:
        - Thumb TIP(4) สูงกว่า (y น้อยกว่า) ข้อมือ WRIST(0) และปลายนิ้วอื่น ๆ (8,12,16,20) ทั้งหมด
        - Pinky TIP(20) ต้องต่ำกว่า (y มากกว่า) WRIST(0)
        - ใช้ margin ตามสัดส่วนความสูงมือเพื่อลด false positive
        หมายเหตุ: ค่าพิกัดภาพ y มาก = ต่ำลง
        """
        if not pts or len(pts) < 21:
            return False

        # ดึงจุดสำคัญ
        WRIST = 0
        THUMB_TIP = 4
        INDEX_TIP = 8
        MIDDLE_TIP = 12
        RING_TIP = 16
        PINKY_TIP = 20

        wrist_y = pts[WRIST][1]
        thumb_tip_y = pts[THUMB_TIP][1]
        index_tip_y = pts[INDEX_TIP][1]
        middle_tip_y = pts[MIDDLE_TIP][1]
        ring_tip_y = pts[RING_TIP][1]
        pinky_tip_y = pts[PINKY_TIP][1]

        # === คำนวณ margin จาก "ความสูงมือ" แบบคร่าว ๆ ===
        # ใช้ระยะ y ระหว่าง WRIST กับจุดกลางฝ่ามือ (MIDDLE_MCP=9) ถ้าไม่มี ใช้ช่วง y ทั้งหมด
        MIDDLE_MCP = 9
        if len(pts) > MIDDLE_MCP:
            base_span = abs(pts[MIDDLE_MCP][1] - wrist_y)
        else:
            ys = [p[1] for p in pts]
            base_span = max(ys) - min(ys)

        # กันเคสมือเล็กมากในภาพ
        if base_span < 1:
            base_span = 40  # ดีฟอลต์ขั้นต่ำ

        # margin ประมาณ 8% ของความสูงมือ (ปรับได้ 0.05–0.12)
        margin = int(0.08 * base_span)

        # === เงื่อนไข 1: นิ้วโป้งต้อง "สูงกว่า" ทุกนิ้วอื่น + สูงกว่าข้อมือ (เผื่อ margin) ===
        # y น้อยกว่า = สูงกว่า
        higher_than_wrist = thumb_tip_y < (wrist_y - margin)
        higher_than_other_tips = all(
            thumb_tip_y < (other_y - margin)
            for other_y in (index_tip_y, middle_tip_y, ring_tip_y, pinky_tip_y)
        )

        # === เงื่อนไข 2: ปลายนิ้วก้อยต้อง "ต่ำกว่า" ข้อมือ (เผื่อ margin) ===
        pinky_below_wrist = pinky_tip_y > (wrist_y + margin)

        # (ออปชัน) กันนิ้วชี้ไม่ชี้ขึ้นเกินไป: ให้ปลายนิ้วชี้ต่ำกว่า MCP ของตัวเอง (งอคร่าว ๆ)
        INDEX_MCP = 5
        if len(pts) > INDEX_MCP:
            index_curled = index_tip_y > (pts[INDEX_MCP][1] - margin // 2)
        else:
            index_curled = True  # ถ้าไม่มีจุด ถือว่าผ่านเพื่อไม่ strict เกินไป

        # สรุป
        return higher_than_wrist and higher_than_other_tips and pinky_below_wrist and index_curled

