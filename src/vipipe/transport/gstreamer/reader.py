from dataclasses import dataclass

from vipipe.transport.interface import MultipartReaderABC, ReaderABC

from .entity import GstMessage


@dataclass
class GstReader(ReaderABC[GstMessage]):
    reader: MultipartReaderABC[bytes]

    def start(self):
        self.reader.start()

    def stop(self):
        self.reader.stop()

    def read(self) -> GstMessage | None:
        message_parts = self.reader.read_multipart()
        if message_parts is None:
            return None

        return GstMessage.parse(message_parts)
