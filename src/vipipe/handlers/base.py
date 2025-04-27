from __future__ import annotations

from abc import ABC
from dataclasses import dataclass
from enum import IntEnum, auto

from vipipe.transport.gstreamer.entity import GstMessage
from vipipe.transport.gstreamer.reader import GstReader
from vipipe.transport.gstreamer.writer import GstWriter


class FLOW_RETURN_TYPES(IntEnum):
    SKIP = auto()
    STOP = auto()
    WRITE_ORIGINAL = auto()
    NEW_BUFFER = auto()


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
            self.writer.stop()

        self.on_shutdown()
        self.is_running = False

    def handle_message(self, message: GstMessage) -> GstMessage | None:
        raise NotImplementedError

    def run(self) -> None:
        self._start()

        try:
            for gst_message in self.reader.iread():
                if gst_message is None:
                    continue

                message = self.handle_message(gst_message)

                if message is not None and self.writer is not None:
                    self.writer.write(message)

                if not self.is_running:
                    break
        finally:
            self._stop()
