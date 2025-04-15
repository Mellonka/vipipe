from abc import ABC
from typing import Generic

from .entity import T


class WriterABC(ABC, Generic[T]):
    def __enter__(self) -> "WriterABC":
        self.start()
        return self

    def __exit__(self, type, value, traceback) -> None:
        self.stop()

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def write(self, message: T) -> None:
        raise NotImplementedError


class MultipartWriterABC(WriterABC[T]):
    def write_multipart(self, message_parts: list[T]) -> None:
        raise NotImplementedError
