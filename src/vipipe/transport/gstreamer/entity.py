import json
from dataclasses import dataclass
from enum import IntEnum, auto
from typing import ClassVar

from vipipe.transport.interface.entity import MultipartSerializableProtocol


class GST_MESSAGE_TYPES(IntEnum):
    CAPS = auto()
    BUFFER = auto()
    EOS = auto()


class GstMessage(MultipartSerializableProtocol):
    register: ClassVar[dict[GST_MESSAGE_TYPES, type["GstMessage"]]] = {}

    def __init_subclass__(cls, type: GST_MESSAGE_TYPES) -> None:
        if type in cls.register:
            raise ValueError(f"Gst message type: {type}, already defined")
        cls.register[type] = cls
        cls.message_type = type
        cls.encoded_message_type = type.value.to_bytes(1, "big")

    @classmethod
    def get_cls_by_type(cls, type: GST_MESSAGE_TYPES) -> "type[GstMessage]":
        return cls.register[type]

    @classmethod
    def define_message_type(cls, data: bytes) -> GST_MESSAGE_TYPES:
        return GST_MESSAGE_TYPES(int.from_bytes(data, "big"))

    @classmethod
    def parse(cls, parts: list[bytes] | tuple) -> "GstMessage":
        message_cls = cls.register[cls.define_message_type(parts[0])]
        return message_cls.parse(parts)


@dataclass
class BufferMessage(GstMessage, type=GST_MESSAGE_TYPES.BUFFER):
    pts: int
    dts: int | None
    duration: int | None
    width: int
    height: int
    flags: int
    caps_str: str | None
    appmeta: dict | None
    buffer: bytes

    def _pack_meta(self) -> bytes:
        return json.dumps(
            {
                "pts": self.pts,
                "dts": self.dts,
                "duration": self.duration,
                "width": self.width,
                "height": self.height,
                "flags": self.flags,
                "caps_str": self.caps_str,
                "appmeta": self.appmeta,
            }
        ).encode("UTF-8")

    def toparts(self) -> list[bytes]:
        return [self.encoded_message_type, self._pack_meta(), self.buffer]

    @classmethod
    def parse(cls, parts: list[bytes] | tuple[bytes, bytes, bytes]) -> "BufferMessage":
        message_type = cls.define_message_type(parts[0])
        if GST_MESSAGE_TYPES.BUFFER != message_type:
            raise ValueError(f"Invalid message type, expected: BUFFER, recieved: {message_type}")

        return cls(**json.loads(parts[1].decode("UTF-8")), buffer=parts[2])


class EndOfStreamMessage(GstMessage, type=GST_MESSAGE_TYPES.EOS):
    def toparts(self) -> list[bytes]:
        return [self.encoded_message_type]

    @classmethod
    def parse(cls, parts: list[bytes] | tuple[bytes]) -> "EndOfStreamMessage":
        message_type = cls.define_message_type(parts[0])
        if GST_MESSAGE_TYPES.EOS != message_type:
            raise ValueError(f"Invalid message type, expected: EOS, recieved: {message_type}")

        return cls()


@dataclass
class CapsMessage(GstMessage, type=GST_MESSAGE_TYPES.CAPS):
    caps_str: str
    width: int
    height: int
    format: str | None
    fps_n: float | None
    fps_d: float | None
    framerate: str | None

    def toparts(self) -> list[bytes]:
        return [
            self.encoded_message_type,
            json.dumps(
                {
                    "caps_str": self.caps_str,
                    "width": self.width,
                    "height": self.height,
                    "format": self.format,
                    "fps_n": self.fps_n,
                    "fps_d": self.fps_d,
                    "framerate": self.framerate,
                }
            ).encode("UTF-8"),
        ]

    @classmethod
    def parse(cls, parts: list[bytes] | tuple[bytes, bytes]) -> "CapsMessage":
        message_type = cls.define_message_type(parts[0])
        if GST_MESSAGE_TYPES.CAPS != message_type:
            raise ValueError(f"Invalid message type, expected: CAPS, recieved: {message_type}")

        return cls(**json.loads(parts[1].decode("UTF-8")))
