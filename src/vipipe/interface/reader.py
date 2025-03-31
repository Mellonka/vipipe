from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class ReaderABC(ABC, Generic[T]):
    name: str

    @abstractmethod
    def read(self) -> T:
        raise NotImplementedError
