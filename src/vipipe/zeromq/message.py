from dataclasses import dataclass


@dataclass
class ZeroMQMessage:
    topic: bytes | None
    message_type: bytes
    data: list[bytes]
    dontwait: bool = False


class NotValidMessageError(Exception):
    pass
