def to_thai_message(result: dict, current_loc: str) -> str:
    msg = (result.get("message") or "").strip()
    prev_loc = result.get("prev_location")
    next_checkout_str = result.get("next_checkout_str")

    mapping = {
        "Checked in": "เช็คอินแล้ว",
        "Rechecked in": "เช็คอินอีกครั้ง",
        "Checked out": "เช็คเอาท์แล้ว",
        "Too soon to checkout": "ยังไม่ถึงเวลาที่จะเช็คเอาท์",
        "Wait...": "กรุณารอสักครู่",
    }
    if msg in mapping:
        th = mapping[msg]
        if next_checkout_str:
            th += f" | เช็คเอาท์ได้เวลา {next_checkout_str}"
        return th

    if "Already checked in at" in msg and "Please checkout there first" in msg:
        where = prev_loc or msg.split("at")[-1].split(".")[0].strip()
        return f"คุณเช็คอินอยู่ที่ “{where}” โปรดเช็คเอาท์ที่จุดนั้นก่อน"

    if "You haven't checked in" in msg and "Please check in here first" in msg:
        return f"ยังไม่ได้เช็คอินที่ “{current_loc}” กรุณาเช็คอินที่จุดนี้ก่อน"

    if "Checkout at" in msg and "booth" in msg:
        where = prev_loc or msg.split("at")[-1].split("booth")[0].strip()
        return f"กรุณาเช็คเอาท์ที่ “{where}” ก่อน"

    return msg
