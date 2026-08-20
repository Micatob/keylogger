from abc import ABC, abstractmethod


class C2Channel(ABC):
    name = ""

    @abstractmethod
    def send(self, payload: dict) -> bool:
        pass

    @abstractmethod
    def receive(self) -> list:
        pass

    @abstractmethod
    def close(self):
        pass
