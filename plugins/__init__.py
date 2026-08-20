from abc import ABC, abstractmethod


class Plugin(ABC):
    name = ""
    interval = 0

    def __init__(self):
        self.buffer = ""
        self._running = False

    @abstractmethod
    def start(self):
        pass

    @abstractmethod
    def stop(self):
        pass

    def poll(self):
        if not self.buffer:
            return None
        data = self.buffer
        self.buffer = ""
        return {"type": self.name, "data": data}

    def handle_command(self, action: str, args: list):
        return None
