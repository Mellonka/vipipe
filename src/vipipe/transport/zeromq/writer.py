from dataclasses import dataclass, field
from typing import Literal

import zmq
from vipipe.transport.interface import MultipartWriterABC


@dataclass
class ZeroMQWriterConfig:
    address: str
    """Адрес сокета"""

    socket_type: Literal[zmq.SocketType.PUB, zmq.SocketType.PUSH]
    """Тип публикации (PUB - получат все клиенты, PUSH - равномерное распеределение между клиентами)"""

    buffer_length: int = 10
    """Максимальное количество сообщений в очереди"""

    buffer_size_oc: int = 1024 * 1024 * 30
    """Размер буфера ОС (в байтах). По умолчанию 30 МБ"""

    send_timeout: int = 10
    """Максимальное время ожидания (в мс) для операции отправки"""

    immediate: bool = True
    """Отправлять сообщения только при активных клиентах"""

    conflate: bool = False
    """Сохранять только последнее сообщение в очереди"""

    linger: int = 500
    """Какое время (мс) пытаемся отправить оставшиеся сообщения при закрытии сокета. 
    Особенности: 0 — сообщения отбрасываются сразу, -1 — бесконечное ожидание"""

    dontwait: bool = False
    """Неблокирующая запись. Не ждать если нет готовых данных"""


@dataclass
class ZeroMQWriter(MultipartWriterABC[bytes]):
    config: ZeroMQWriterConfig

    context: zmq.SyncContext | None = field(init=False, default=None)
    socket: zmq.SyncSocket | None = field(init=False, default=None)

    def start(self):
        assert self.context is None
        assert self.socket is None

        self.context = zmq.Context()
        self.socket = self.context.socket(self.config.socket_type)

        self.socket.setsockopt(zmq.SNDHWM, self.config.buffer_length)
        self.socket.setsockopt(zmq.SNDBUF, self.config.buffer_size_oc)
        self.socket.setsockopt(zmq.SNDTIMEO, self.config.send_timeout)
        self.socket.setsockopt(zmq.IMMEDIATE, self.config.immediate)
        self.socket.setsockopt(zmq.CONFLATE, self.config.conflate)
        self.socket.setsockopt(zmq.LINGER, self.config.linger)

        self.socket.bind(self.config.address)

    def stop(self):
        assert self.context is not None
        assert self.socket is not None

        self.socket.close()
        self.context.term()

    def write_multipart(self, message_parts: list[bytes]) -> None:
        assert self.socket is not None

        self.socket.send_multipart(message_parts, flags=zmq.DONTWAIT if self.config.dontwait else 0)
