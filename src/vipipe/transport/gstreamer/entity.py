from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from enum import IntEnum, auto
from functools import cached_property
from typing import Any, ClassVar, TypedDict

from vipipe.transport.interface.entity import MultipartSerializableProtocol


class GST_MESSAGE_TYPES(IntEnum):
    """Типы сообщений GStreamer."""

    CAPS = auto()  # Информация о возможностях медиапотока
    BUFFER = auto()  # Медиаданные и буфер
    BUFFER_META = auto()  # Метаданные буфера
    CUSTOM_META = auto()  # Кастомные метаданные
    EOS = auto()  # Конец потока


class GstMessage(MultipartSerializableProtocol):
    """
    Базовый класс для сообщений GStreamer.

    Предоставляет базовую функциональность для сериализации и десериализации сообщений.
    Автоматически регистрирует все подклассы для последующей маршрутизации сообщений.
    """

    registry: ClassVar[dict[GST_MESSAGE_TYPES, type[GstMessage]]] = {}
    """Регистрация подклассов по типу сообщения."""

    MESSAGE_TYPE: ClassVar[GST_MESSAGE_TYPES]
    """Тип сообщения GStreamer."""

    PARTS_LENGTH: ClassVar[int] = 1
    """Количество частей сообщения по умолчанию."""

    def __init_subclass__(cls, type: GST_MESSAGE_TYPES | None = None) -> None:
        """
        Автоматическая регистрация подклассов.

        Args:
            type: Тип сообщения для регистрации
        Raises:
            ValueError: Если тип сообщения не указан и не может быть определен автоматически
        """

        if type is None:
            if cls.MESSAGE_TYPE is None:
                raise ValueError("Тип сообщения не указан и не может быть определен автоматически")
            return

        if type in cls.registry:
            raise ValueError(f"Тип сообщения {type.name} уже зарегистрирован")

        cls.registry[type] = cls
        cls.MESSAGE_TYPE = type

    @cached_property
    def encoded_message_type(self) -> bytes:
        """Возвращает байтовое представление типа сообщения (с кэшированием)."""
        return self.MESSAGE_TYPE.value.to_bytes(1, "big")

    @classmethod
    def decode_message_type(cls, data: bytes) -> GST_MESSAGE_TYPES:
        """
        Преобразует байтовое представление в тип сообщения.

        Args:
            data: Байтовое представление типа
        Returns:
            Тип сообщения
        """
        return GST_MESSAGE_TYPES(int.from_bytes(data, "big"))

    @classmethod
    def get_message_class(cls, type: GST_MESSAGE_TYPES) -> type[GstMessage]:
        """
        Получает класс сообщения по его типу.

        Args:
            type: Тип сообщения
        Returns:
            Класс сообщения соответствующего типа
        """
        return cls.registry[type]

    @classmethod
    def parse(cls, parts: list[bytes] | tuple[bytes, ...]) -> GstMessage:
        """
        Разбирает сообщение из бинарных частей.

        Args:
            parts: Список байтовых частей сообщения
        Returns:
            Объект сообщения соответствующего типа
        Raises:
            ValueError: При пустом списке частей или несоответствии типа
        """
        if not parts:
            raise ValueError("Получен пустой список частей сообщения")

        message_type = cls.decode_message_type(parts[0])

        if cls is GstMessage:
            return cls.registry[message_type].parse(parts)

        if cls.MESSAGE_TYPE != message_type:
            raise ValueError(f"Несоответствие типа: ожидался {cls.MESSAGE_TYPE.name}, получен {message_type.name}")
        if len(parts) != cls.PARTS_LENGTH:
            raise ValueError(f"Несоответствие длины частей: ожидалось {cls.PARTS_LENGTH}, получено {len(parts)}")

        return cls._parse_implementation(parts)

    @classmethod
    def _parse_implementation(cls, parts: list[bytes] | tuple[bytes, ...]) -> GstMessage:
        """
        Реализация разбора в конкретном подклассе.

        Args:
            parts: Список байтовых частей сообщения
        Returns:
            Объект сообщения
        """
        raise NotImplementedError("Подклассы должны реализовать _parse_implementation")

    def toparts(self) -> list[bytes]:
        """Преобразует сообщение в список байтовых частей."""
        return [self.encoded_message_type]


@dataclass(slots=True, frozen=True)
class EndOfStreamMessage(GstMessage, type=GST_MESSAGE_TYPES.EOS):
    """Сообщение о конце потока данных."""

    PARTS_LENGTH: ClassVar[int] = 1

    @classmethod
    def _parse_implementation(cls, parts: list[bytes] | tuple[bytes, ...]) -> EndOfStreamMessage:
        return cls()


@dataclass(slots=True)
class CapsMessage(GstMessage, type=GST_MESSAGE_TYPES.CAPS):
    """Сообщение с информацией о возможностях медиапотока."""

    PARTS_LENGTH: ClassVar[int] = 2

    caps_str: str
    width: int
    height: int
    format: str | None = None
    fps_n: float | None = None
    fps_d: float | None = None
    framerate: str | None = None

    def toparts(self) -> list[bytes]:
        return [self.encoded_message_type, json.dumps(asdict(self)).encode("UTF-8")]

    @classmethod
    def _parse_implementation(cls, parts: list[bytes] | tuple[bytes, ...]) -> CapsMessage:
        return cls(**json.loads(parts[1].decode("UTF-8")))


@dataclass(slots=True)
class BufferMetaMessage(GstMessage, type=GST_MESSAGE_TYPES.BUFFER_META):
    """Метаданные буфера."""

    PARTS_LENGTH: ClassVar[int] = 2

    pts: int
    width: int
    height: int
    flags: int
    dts: int | None = None
    duration: int | None = None
    caps_str: str | None = None

    def toparts(self) -> list[bytes]:
        return [self.encoded_message_type, json.dumps(asdict(self)).encode("UTF-8")]

    @classmethod
    def _parse_implementation(cls, parts: list[bytes] | tuple[bytes, ...]) -> BufferMetaMessage:
        return cls(**json.loads(parts[1].decode("UTF-8")))


@dataclass(slots=True)
class CustomMetaMessage(GstMessage, type=GST_MESSAGE_TYPES.CUSTOM_META):
    """Кастомные метаданные буфера."""

    metadata: dict[str, Any]

    PARTS_LENGTH: ClassVar[int] = 2

    def toparts(self) -> list[bytes]:
        return [self.encoded_message_type, json.dumps(self.metadata).encode("UTF-8")]

    @classmethod
    def _parse_implementation(cls, parts: list[bytes] | tuple[bytes, ...]) -> CustomMetaMessage:
        return cls(
            metadata=json.loads(parts[1].decode("UTF-8")),
        )

    def to_json(self) -> str:
        return json.dumps(self.metadata)

    @classmethod
    def from_json(cls, json_str: str) -> CustomMetaMessage:
        return cls(metadata=json.loads(json_str))


class ObjectMeta(TypedDict):
    bbox: tuple[float, float, float, float]
    conf: float
    class_id: int | None
    label: str | None
    attributes: dict[str, Any] | None


@dataclass(slots=True)
class ObjectsMetaMessage(CustomMetaMessage):
    """Метаданные с объектами и их координатами."""

    @property
    def objects(self) -> list[ObjectMeta]:
        """Возвращает список объектов с их метаданными."""
        if "objects" not in self.metadata:
            self.metadata["objects"] = []
        return self.metadata["objects"]

    @objects.setter
    def objects(self, value: list[ObjectMeta]) -> None:
        """Устанавливает список объектов с их метаданными."""
        self.metadata["objects"] = value

    def add_object(
        self,
        bbox: tuple[float, float, float, float],
        conf: float,
        class_id: int | None = None,
        label: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> None:
        """Добавляет объект с его метаданными в список объектов."""
        if "objects" not in self.metadata:
            self.metadata["objects"] = []
        self.metadata["objects"].append(
            {
                "bbox": bbox,
                "conf": conf,
                "class_id": class_id,
                "label": label,
                "attributes": attributes,
            }
        )


@dataclass(slots=True)
class BufferMessage(GstMessage, type=GST_MESSAGE_TYPES.BUFFER):
    """Сообщение с медиаданными и метаданными."""

    PARTS_LENGTH: ClassVar[int] = 2 + BufferMetaMessage.PARTS_LENGTH + CustomMetaMessage.PARTS_LENGTH

    buffer: bytes
    buffer_meta: BufferMetaMessage | None = None
    custom_meta: CustomMetaMessage | None = None

    def toparts(self) -> list[bytes]:
        """Преобразует сообщение в список байтовых частей."""

        parts = [self.encoded_message_type]

        if self.buffer_meta:
            parts.extend(self.buffer_meta.toparts())
        else:
            parts.extend([b""] * BufferMetaMessage.PARTS_LENGTH)

        if self.custom_meta:
            parts.extend(self.custom_meta.toparts())
        else:
            parts.extend([b""] * CustomMetaMessage.PARTS_LENGTH)

        parts.extend([self.buffer])
        return parts

    @classmethod
    def _parse_implementation(cls, parts: list[bytes] | tuple[bytes, ...]) -> BufferMessage:
        buffer_meta_parts = parts[1 : 1 + BufferMetaMessage.PARTS_LENGTH]
        custom_meta_parts = parts[1 + BufferMetaMessage.PARTS_LENGTH : cls.PARTS_LENGTH - 1]

        buffer_meta = None
        if buffer_meta_parts[0] != b"":
            buffer_meta = BufferMetaMessage.parse(buffer_meta_parts)

        custom_meta = None
        if custom_meta_parts[0] != b"":
            custom_meta = CustomMetaMessage.parse(custom_meta_parts)

        return cls(
            buffer=parts[-1],
            buffer_meta=buffer_meta,  # type: ignore
            custom_meta=custom_meta,  # type: ignore
        )
