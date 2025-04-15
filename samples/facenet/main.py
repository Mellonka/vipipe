import argparse
import logging

import zmq
from facenet_pytorch import MTCNN
from PIL import Image
from vipipe.handlers.base import FLOW_RETURN_TYPES, HandlerABC
from vipipe.handlers.drawer import Drawer
from vipipe.transport.gstreamer import GST_MESSAGE_TYPES, GstMessage, GstReader, GstWriter
from vipipe.transport.zeromq import ZeroMQReader, ZeroMQReaderConfig, ZeroMQWriter, ZeroMQWriterConfig

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class FacenetProcess(HandlerABC):
    def start(self):
        self.model = MTCNN(keep_all=True)
        self.drawer = Drawer()
        self.reader.start()
        self.writer.start()  # type: ignore

    def preprocess(self, message: GstMessage) -> tuple[Image.Image | None, FLOW_RETURN_TYPES | None]:
        if message.message_type != GST_MESSAGE_TYPES.BUFFER:
            return None, FLOW_RETURN_TYPES.WRITE_ORIGINAL

        image = Image.frombuffer("RGB", (message.width, message.height), message.buffer)  # type: ignore
        return image, None

    def process(self, original: GstMessage, preprocessed: Image.Image) -> tuple[bytes | None, FLOW_RETURN_TYPES | None]:
        try:
            boxes, probs = self.model.detect(preprocessed)  # type: ignore
        except Exception:
            return None, FLOW_RETURN_TYPES.WRITE_ORIGINAL

        self.drawer.process_bboxes(preprocessed, boxes, probs)  # type: ignore
        return preprocessed.tobytes(), None

    def postprocess(self, original: GstMessage, processed: bytes) -> GstMessage | None:
        original.buffer = processed  # type: ignore
        return original


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Запустить сервер для раздачи файлов")
    parser.add_argument("--reader_address", type=str, help="Сокет откуда читаем кадры")
    parser.add_argument("--writer_address", type=str, help="Сокет куда пишем отрисованные кадры")
    return parser.parse_args()


def main(reader_address: str, writer_address: str):
    reader = GstReader(ZeroMQReader(ZeroMQReaderConfig(address=reader_address, socket_type=zmq.SocketType.SUB)))
    writer = GstWriter(ZeroMQWriter(ZeroMQWriterConfig(address=writer_address, socket_type=zmq.SocketType.PUB)))
    FacenetProcess(reader=reader, writer=writer).run()


if __name__ == "__main__":
    args = parse_args()
    main(args.reader_address, args.writer_address)
