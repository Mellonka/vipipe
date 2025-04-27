from __future__ import annotations

from typing import Protocol, TypeVar

T = TypeVar("T")


class SerializableProtocol(Protocol):
    def tobytes(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def parse(cls, data: bytes) -> SerializableProtocol:
        raise NotImplementedError


class MultipartSerializableProtocol(Protocol):
    def toparts(self) -> list[bytes]:
        raise NotImplementedError

    @classmethod
    def parse(cls, parts: list[bytes]) -> MultipartSerializableProtocol:
        raise NotImplementedError
