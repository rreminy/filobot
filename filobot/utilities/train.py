import typing

from filobot.utilities.manager import HuntManager


class Conductor:

    def __init__(self, hunt_manager: HuntManager, world: str):
        self._hunt_manager = hunt_manager

        self.world = world.strip().lower().title()
        self._hunts = [
            self._hunt_manager.get(self.world, 'erle'),
            self._hunt_manager.get(self.world, 'orcus'),
            self._hunt_manager.get(self.world, 'vochstein'),
            self._hunt_manager.get(self.world, 'aqrabuamelu'),
            self._hunt_manager.get(self.world, 'mahisha'),
            self._hunt_manager.get(self.world, 'luminare'),
            self._hunt_manager.get(self.world, 'funa yurei'),
            self._hunt_manager.get(self.world, 'oni yumemi'),
            self._hunt_manager.get(self.world, 'gajasura'),
            self._hunt_manager.get(self.world, 'angada'),
            self._hunt_manager.get(self.world, 'girimekhala'),
            self._hunt_manager.get(self.world, 'sum')
        ]
        self._hunts = list(filter(lambda h: h[0].status != h[0].STATUS_DIED, self._hunts))
        self._current = None

        self.total = 0

    def __next__(self):
        pass

    def __len__(self):
        pass
