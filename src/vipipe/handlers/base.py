from abc import ABC
from dataclasses import dataclass

from vipipe.logging import get_logger
from vipipe.transport.gstreamer import (
    BufferMessage,
    BufferMetaMessage,
    CapsMessage,
    CustomMetaMessage,
    EndOfStreamMessage,
    GstMessage,
    GstReader,
    GstWriter,
)

logger = get_logger("vipipe.handler")


@dataclass
class HandlerABC(ABC):
    reader: GstReader
    writer: GstWriter | None
    is_running: bool = False

    def on_startup(self):
        pass

    def on_shutdown(self):
        pass

    def set_stop(self):
        self.is_running = False

    def _start(self):
        self.reader.start()
        if self.writer is not None:
            self.writer.start()

        self.on_startup()
        self.is_running = True

    def _stop(self):
        self.reader.stop()
        if self.writer is not None:
            self.writer.write(EndOfStreamMessage())
            self.writer.stop()

        self.on_shutdown()
        self.is_running = False

    def handle_buffer_message(self, message: BufferMessage) -> GstMessage | None:
        return message

    def handle_custom_meta_message(self, message: CustomMetaMessage) -> GstMessage | None:
        return message

    def handle_buffer_meta_message(self, message: BufferMetaMessage) -> GstMessage | None:
        return message

    def handle_caps_message(self, message: CapsMessage) -> GstMessage | None:
        return message

    def handle_eos_message(self, message: EndOfStreamMessage) -> GstMessage | None:
        self.set_stop()
        return message

    def handle_message(self, message: GstMessage) -> GstMessage | None:
        match message.MESSAGE_TYPE:
            case EndOfStreamMessage.MESSAGE_TYPE:
                return self.handle_eos_message(message)  # type: ignore
            case CapsMessage.MESSAGE_TYPE:
                return self.handle_caps_message(message)  # type: ignore
            case BufferMessage.MESSAGE_TYPE:
                return self.handle_buffer_message(message)  # type: ignore
            case CustomMetaMessage.MESSAGE_TYPE:
                return self.handle_custom_meta_message(message)  # type: ignore
            case BufferMetaMessage.MESSAGE_TYPE:
                return self.handle_buffer_meta_message(message)  # type: ignore
            case _:
                raise ValueError(f"Unknown message type: {message.MESSAGE_TYPE}")

    def __enter__(self) -> "HandlerABC":
        self._start()
        return self

    def __exit__(self, type, value, traceback) -> None:
        if type is not None:
            logger.exception(f"Exception: {value}")
        self._stop()

    def run(self) -> None:
        with self:
            for gst_message in self.reader.iread():
                if gst_message is None:
                    continue

                message = self.handle_message(gst_message)

                if message is not None and self.writer is not None:
                    self.writer.write(message)

                if not self.is_running:
                    break
