from abc import ABC
from dataclasses import dataclass
from enum import IntEnum, auto
from typing import Any

from vipipe.transport.gstreamer.entity import GstMessage
from vipipe.transport.gstreamer.reader import GstReader
from vipipe.transport.gstreamer.writer import GstWriter


class FLOW_RETURN_TYPES(IntEnum):
    SKIP = auto()
    STOP = auto()
    WRITE_ORIGINAL = auto()


@dataclass
class HandlerABC(ABC):
    reader: GstReader
    writer: GstWriter | None

    def start(self):
        self.reader.start()
        if self.writer is not None:
            self.writer.start()

    def stop(self):
        self.reader.stop()
        if self.writer is not None:
            self.writer.stop()

    def preprocess(self, message: GstMessage) -> tuple[Any, FLOW_RETURN_TYPES | None]:
        raise NotImplementedError

    def process(self, original: GstMessage, preprocessed: Any) -> tuple[Any, FLOW_RETURN_TYPES | None]:
        raise NotImplementedError

    def postprocess(self, original: GstMessage, processed: Any) -> GstMessage | None:
        raise NotImplementedError

    def run(self) -> None:
        self.start()

        try:
            for gst_message in self.reader.iread():
                if gst_message is None:
                    continue

                result, flow = self.preprocess(gst_message)

                if flow == FLOW_RETURN_TYPES.SKIP:
                    continue
                if flow == FLOW_RETURN_TYPES.WRITE_ORIGINAL:
                    if self.writer is not None:
                        self.writer.write(gst_message)
                    continue
                if flow == FLOW_RETURN_TYPES.STOP:
                    break

                result, flow = self.process(gst_message, result)
                if flow == FLOW_RETURN_TYPES.SKIP:
                    continue
                if flow == FLOW_RETURN_TYPES.WRITE_ORIGINAL:
                    if self.writer is not None:
                        self.writer.write(gst_message)
                    continue
                if flow == FLOW_RETURN_TYPES.STOP:
                    break

                result = self.postprocess(gst_message, result)
                if result is not None and self.writer is not None:
                    self.writer.write(result)
        finally:
            self.stop()
