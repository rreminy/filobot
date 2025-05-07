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
