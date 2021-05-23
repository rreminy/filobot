import re

time_regex_p = re.compile("([0-9]*:)?[0-9]{2}:[0-9]{2}")

class RemainingTime:
    JP_DAYS = "日"
    JP_HOURS = "時間"
    JP_MINUTES = "分"
    JP_SECONDS = "秒"
    JP_LESS_THAN_A_SECOND = "秒未満"

    def __init__(self, seconds: int):
        self.minutes = int(seconds / 60)
        self.seconds = int(seconds % 60)

        self.hours = int(self.minutes / 60)
        self.minutes = int(self.minutes % 60)

        self.days = int(self.hours / 24)
        self.hours = int(self.hours % 24)

    def __str__(self) -> str:
        return self.to_simple()

    def to_simple(self) -> str:
        hours_str = f"{self.hours + (self.days * 24)}:" if self.hours > 0 else ""
        minutes_str = f"{self.minutes:02d}:"
        seconds_str = f"{self.seconds:02d}"
        return f"{hours_str}{minutes_str}{seconds_str}"

    def to_verbose(self, jp: bool = False) -> str:
        days_str = f"""{self.days}{self.JP_DAYS if jp else ""} day{"s" if self.days > 1 else ""}""" if self.days > 0 else None
        hours_str = f"""{self.hours}{self.JP_HOURS if jp else ""} hour{"s" if self.hours > 1 else ""}""" if self.hours > 0 else None
        minutes_str = f"""{self.minutes}{self.JP_MINUTES if jp else ""} minute{"s" if self.minutes > 1 else ""}""" if self.minutes > 0 else None
        seconds_str = f"""{self.seconds}{self.JP_SECONDS if jp else ""} second{"s" if self.seconds > 1 else ""}""" if self.seconds > 0 else None

        ret = ""
        if (days_str is not None): ret += f"{days_str}, "
        if (hours_str is not None): ret += f"{hours_str}, "
        if (minutes_str is not None): ret += f"{minutes_str}, "
        if (seconds_str is not None): ret += f"{seconds_str}, "
        if (len(ret) == 0): ret = f"""{self.JP_LESS_THAN_A_SECOND if jp else ""}less than a second, """

        # This is the reason of my insistence with the ", " at the end
        return ret[0:-2]

    def to_seconds(self):
        hours = int(self.hours + self.days * 24)
        minutes = int(self.minutes + hours * 60)
        seconds = int(self.seconds + minutes * 60)
        return int(seconds)

    def from_simple_time(time_str: str):
        time_str = time_regex_p.search(time_str)[0]
        time_parts = time_str.rsplit(" ")[0].rsplit(":")

        seconds = int(0)
        for units in time_parts:
            seconds = int(seconds * 60) + int(units)

        return RemainingTime(seconds)


def seconds_to_time_str(seconds: int) -> str:
    return RemainingTime(seconds).__str__()

def seconds_to_time_str_verbose(seconds: int, jp: bool = False) -> str:
    return RemainingTime(seconds).to_verbose(jp)


test_time = 2110
test_time_obj = RemainingTime(test_time)
test_time_str = f"""{test_time_obj}"""
test_time_int = test_time_obj.to_seconds()

print(f"""{test_time} => {test_time_str} => {test_time_obj} => {test_time_int}""")
