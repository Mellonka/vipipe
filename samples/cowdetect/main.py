import argparse
import logging

import zmq
from PIL import Image
from ultralytics import YOLO
from vipipe.handlers.base import FLOW_RETURN_TYPES, HandlerABC
from vipipe.handlers.drawer import Drawer
from vipipe.transport.gstreamer import GST_MESSAGE_TYPES, GstMessage, GstReader, GstWriter
from vipipe.transport.zeromq import ZeroMQReader, ZeroMQReaderConfig, ZeroMQWriter, ZeroMQWriterConfig

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class CowDetectProcess(HandlerABC):
    def start(self):
        self.model = YOLO("/app/temp/model.pt")

        self.drawer = Drawer(thickness=10)
        self.reader.start()
        self.writer.start()  # type: ignore

    def preprocess(self, message: GstMessage) -> tuple[Image.Image | None, FLOW_RETURN_TYPES | None]:
        if message.message_type != GST_MESSAGE_TYPES.BUFFER:
            return None, FLOW_RETURN_TYPES.WRITE_ORIGINAL

        image = Image.frombuffer("RGB", (message.width, message.height), message.buffer)  # type: ignore
        return image, None

    def process(self, original: GstMessage, preprocessed: Image.Image) -> tuple[bytes | None, FLOW_RETURN_TYPES | None]:
        try:
            results = self.model.predict(preprocessed)
            if results is None or len(results) == 0:
                return None, FLOW_RETURN_TYPES.WRITE_ORIGINAL
            boxes = [result.boxes.xyxy[0] for result in results if result.boxes is not None]
            probs = [result.probs for result in results if result.probs is not None]
        except Exception as exc:
            logger.debug("Got error", exc_info=exc)
            return None, FLOW_RETURN_TYPES.WRITE_ORIGINAL

        logger.debug(f"Boxes: {boxes}")
        logger.debug(f"Probs: {probs}")

        if not boxes:
            return None, FLOW_RETURN_TYPES.WRITE_ORIGINAL

        logger.debug(f"Boxes: {boxes[0][0], boxes[0][1], boxes[0][2], boxes[0][3]}")

        self.drawer.process_bboxes(preprocessed, boxes, probs)
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
    CowDetectProcess(reader=reader, writer=writer).run()


if __name__ == "__main__":
    args = parse_args()
    main(args.reader_address, args.writer_address)
