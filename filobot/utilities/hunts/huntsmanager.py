from filobot.utilities.hunts.hunt import Hunt


class HuntsManager:
    def __init__(self):  # (some big thing goes here)
        pass

    def get(self, key: str) -> Hunt:
        return Hunt(0, 0, 1)

    def set(self, key: str, hunt: Hunt):
        return

    def on_find(self, key: str, update_time: float, source: str):
        return

    def on_kill(self, key: str, update_time: float, source: str):
        return

    def on_maybe_kill(self, key: str, update_time: float, source: str):
        return
