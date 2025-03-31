from dataclasses import dataclass, field
from typing import Literal

import zmq
from vipipe.interface.reader import ReaderABC
from vipipe.zeromq.message import NotValidMessageError, ZeroMQMessage


@dataclass
class ZeroMQReader(ReaderABC):
    address: str
    """Адрес сокета"""
    socket_type: Literal[zmq.SocketType.SUB, zmq.SocketType.PULL]
    """Тип сокета"""
    topic: bytes | None = None
    """Тема сообщений, только для socket_type=zmq.SUB"""
    buffer_length: int = 50
    """Максимальное количество сообщений в очереди"""
    buffer_size_oc: int = 1024 * 1024 * 10
    """Размер буфера ОС (в байтах). По умолчанию 10 МБ"""
    recv_timeout: int = 100
    """Максимальное время ожидания (в мс) для операции получения"""
    conflate: bool = False
    """Сохранять только последнее сообщение в очереди"""

    context: zmq.SyncContext | None = field(init=False, default=None)
    socket: zmq.SyncSocket | None = field(init=False, default=None)

    def __post_init__(self):
        if isinstance(self.topic, str):
            self.topic = self.topic.encode()

    def start(self):
        assert self.context is None
        assert self.socket is None

        self.context = zmq.Context()
        self.socket = self.context.socket(self.socket_type)

        if self.socket_type == zmq.SUB:
            self.socket.setsockopt(zmq.SUBSCRIBE, self.topic or b"")

        self.socket.setsockopt(zmq.RCVHWM, self.buffer_length)
        self.socket.setsockopt(zmq.RCVBUF, self.buffer_size_oc)
        self.socket.setsockopt(zmq.RCVTIMEO, self.recv_timeout)
        self.socket.setsockopt(zmq.CONFLATE, self.conflate)

        self.socket.connect(self.address)

    def stop(self):
        assert self.context is not None
        assert self.socket is not None

        self.socket.close()
        self.context.term()

    def read(self) -> ZeroMQMessage | None:
        assert self.socket is not None

        try:
            parts = self.socket.recv_multipart()
        except zmq.Again:
            return None

        if len(parts) < 3:
            raise NotValidMessageError

        return ZeroMQMessage(topic=parts[0], message_type=parts[1], data=parts[2:])
