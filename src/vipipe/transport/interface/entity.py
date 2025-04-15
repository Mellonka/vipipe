import json
from dataclasses import asdict
from typing import Protocol, TypeVar

T = TypeVar("T")


class SerializableProtocol(Protocol):
    def tobytes(self) -> bytes:
        raise NotImplementedError

    @classmethod
    def parse(cls, data: bytes) -> "SerializableProtocol":
        raise NotImplementedError


class MultipartSerializableProtocol(Protocol):
    def toparts(self) -> list[bytes]:
        raise NotImplementedError

    @classmethod
    def parse(cls, parts: list[bytes]) -> "MultipartSerializableProtocol":
        raise NotImplementedError


class DataclassJsonSerializable(SerializableProtocol):
    def tobytes(self) -> bytes:
        return json.dumps(asdict(self)).encode("UTF-8")  # type: ignore

    @classmethod
    def parse(cls, data: bytes):
        jdata = json.loads(data.decode("UTF-8"))
        return cls(**jdata)
