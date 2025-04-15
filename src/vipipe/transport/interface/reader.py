from abc import ABC
from dataclasses import dataclass
from typing import Generic, Iterator

from .entity import T


class ReaderABC(ABC, Generic[T]):
    def __enter__(self) -> "ReaderABC":
        self.start()
        return self

    def __exit__(self, type, value, traceback) -> None:
        self.stop()

    def iread(self, with_none: bool = True) -> Iterator[T | None]:
        return ReadIterator(self, with_none=with_none)

    def start(self) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        raise NotImplementedError

    def read(self) -> T | None:
        raise NotImplementedError


@dataclass(slots=True)
class ReadIterator(Generic[T]):
    reader: ReaderABC[T]
    with_none: bool = True

    def __iter__(self) -> "ReadIterator":
        return self

    def __next__(self) -> T | None:
        message = self.reader.read()
        if not self.with_none and message is None:
            raise StopIteration
        return message


class MultipartReaderABC(ReaderABC[T]):
    def iread_multipart(self, with_none: bool = True) -> Iterator[list[T] | None]:
        return ReadMultipartIterator(self, with_none=with_none)

    def read_multipart(self) -> list[T] | None:
        raise NotImplementedError


@dataclass(slots=True)
class ReadMultipartIterator(Generic[T]):
    reader: MultipartReaderABC[T]
    with_none: bool = True

    def __iter__(self) -> "ReadMultipartIterator":
        return self

    def __next__(self) -> list[T] | None:
        message = self.reader.read_multipart()
        if not self.with_none and message is None:
            raise StopIteration
        return message
