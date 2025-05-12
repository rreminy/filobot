from .time_utils import RemainingTime

def parse_name(name: str) -> str:
    return name.lower().strip()

def parse_duration_string(start: float, end: float):
    # Uptime
    seconds = round(end - start)
    duration = []
    if seconds > 3600:
        duration.append(f"""{int(seconds / 3600)} hours""")
        seconds -= int(seconds / 3600) * 3600
    if seconds > 60:
        duration.append(f"""{int(seconds / 60)} minutes""")
        seconds -= int(seconds / 60) * 60

    duration.append(f"""{int(seconds)} seconds""")
    return ', '.join(duration)

def get_killed_text(seconds, is_jp):
    return f"""**Killed {"殺された" if is_jp else ""}**""" #  *(after {RemainingTime(seconds).to_verbose()}{"後" if is_jp else ""})*

def get_expired_text(seconds, is_jp):
    return f"""**Expired {"期限切れ" if is_jp else ""}**""" #  *(after {RemainingTime(seconds).to_verbose()}{"後" if is_jp else ""})*