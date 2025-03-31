from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class WriterABC(ABC, Generic[T]):
    @abstractmethod
    def write(self, message: T) -> None:
        raise NotImplementedError
