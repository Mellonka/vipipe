from dataclasses import dataclass

from vipipe.transport.interface import MultipartWriterABC, WriterABC

from .entity import GstMessage


@dataclass
class GstWriter(WriterABC[GstMessage]):
    writer: MultipartWriterABC[bytes]

    def start(self):
        self.writer.start()

    def stop(self):
        self.writer.stop()

    def write(self, message: GstMessage) -> None:
        self.writer.write_multipart(message.toparts())
