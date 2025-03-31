from dataclasses import dataclass, field
from typing import Literal

import zmq
from vipipe.interface.writer import WriterABC
from vipipe.zeromq.message import ZeroMQMessage


@dataclass
class ZeroMQWriter(WriterABC):
    address: str
    """Адрес сокета"""
    socket_type: Literal[zmq.SocketType.PUB, zmq.SocketType.PUSH]
    """Тип публикации (PUB - получат все клиенты, PUSH - равномерное распеределение между клиентами)"""
    buffer_length: int = 50
    """Максимальное количество сообщений в очереди"""
    buffer_size_oc: int = 1024 * 1024 * 10
    """Размер буфера ОС (в байтах). По умолчанию 10 МБ"""
    send_timeout: int = 100
    """Максимальное время ожидания (в мс) для операции отправки"""
    immediate: bool = True
    """Отправлять сообщения только при активных клиентах"""
    conflate: bool = False
    """Сохранять только последнее сообщение в очереди"""
    linger: int = 500
    """Какое время (мс) пытаемся отправить оставшиеся сообщения. 
    Особенности: 0 — сообщения отбрасываются сразу, -1 — бесконечное ожидание"""

    context: zmq.SyncContext | None = field(init=False, default=None)
    socket: zmq.SyncSocket | None = field(init=False, default=None)

    def start(self):
        assert self.context is None
        assert self.socket is None

        self.context = zmq.Context()
        self.socket = self.context.socket(self.socket_type)

        self.socket.setsockopt(zmq.SNDHWM, self.buffer_length)
        self.socket.setsockopt(zmq.SNDBUF, self.buffer_size_oc)
        self.socket.setsockopt(zmq.SNDTIMEO, self.send_timeout)
        self.socket.setsockopt(zmq.IMMEDIATE, self.immediate)
        self.socket.setsockopt(zmq.CONFLATE, self.conflate)
        self.socket.setsockopt(zmq.LINGER, self.linger)

        self.socket.bind(self.address)

    def stop(self):
        assert self.context is not None
        assert self.socket is not None

        self.socket.close()
        self.context.term()

    def write(self, message: ZeroMQMessage) -> None:
        assert self.socket is not None

        self.socket.send_multipart(
            [
                message.topic or b"",
                message.message_type,
                *message.data,
            ],
            flags=zmq.DONTWAIT if message.dontwait else 0,
        )
