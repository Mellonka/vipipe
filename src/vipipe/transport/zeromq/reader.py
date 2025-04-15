from dataclasses import dataclass, field

import zmq
from vipipe.transport.interface import MultipartReaderABC


@dataclass
class ZeroMQReaderConfig:
    address: str
    """Адрес сокета"""

    socket_type: zmq.SocketType
    """Тип сокета"""

    topic: str = ""
    """Тема сообщений, только для socket_type=zmq.SUB"""

    buffer_length: int = 10
    """Максимальное количество сообщений в очереди"""

    buffer_size_oc: int = 1024 * 1024 * 30
    """Размер буфера ОС (в байтах). По умолчанию 30 МБ"""

    read_timeout: int = 100
    """Максимальное время ожидания (в мс) для операции чтения"""

    conflate: bool = False
    """Сохранять только последнее сообщение в очереди"""

    dontwait: bool = False
    """Неблокирующее чтение. Не ждать если очередь полна"""


@dataclass
class ZeroMQReader(MultipartReaderABC[bytes]):
    config: ZeroMQReaderConfig

    context: zmq.SyncContext | None = field(init=False, default=None)
    socket: zmq.SyncSocket | None = field(init=False, default=None)

    def __post_init__(self):
        if self.config.topic and self.config.socket_type != zmq.SocketType.SUB:
            raise ValueError("topic is valid only for socket_type == SUB")

    def start(self):
        assert self.context is None
        assert self.socket is None

        self.context = zmq.Context()
        self.socket = self.context.socket(self.config.socket_type)

        if self.config.socket_type == zmq.SUB:
            self.socket.setsockopt(zmq.SUBSCRIBE, self.config.topic.encode() or b"")

        self.socket.setsockopt(zmq.RCVHWM, self.config.buffer_length)
        self.socket.setsockopt(zmq.RCVBUF, self.config.buffer_size_oc)
        self.socket.setsockopt(zmq.RCVTIMEO, self.config.read_timeout)
        self.socket.setsockopt(zmq.CONFLATE, self.config.conflate)

        self.socket.connect(self.config.address)

    def stop(self):
        assert self.context is not None
        assert self.socket is not None

        self.socket.close()
        self.context.term()

    def read_multipart(self) -> list[bytes] | None:
        assert self.socket is not None

        try:
            return self.socket.recv_multipart(flags=zmq.DONTWAIT if self.config.dontwait else 0)
        except zmq.Again:
            pass
