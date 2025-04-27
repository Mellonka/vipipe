import argparse
import logging
from typing import cast

import zmq
from PIL import Image
from ultralytics import YOLO
from vipipe.handlers.base import HandlerABC
from vipipe.handlers.drawer import Drawer
from vipipe.transport.gstreamer import GST_MESSAGE_TYPES, BufferMessage, GstMessage, GstReader, GstWriter
from vipipe.transport.zeromq import ZeroMQReader, ZeroMQReaderConfig, ZeroMQWriter, ZeroMQWriterConfig

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class CowDetectProcess(HandlerABC):
    model: YOLO
    drawer: Drawer

    def on_startup(self):
        self.model = YOLO("/app/temp/counting.pt")
        self.drawer = Drawer()

    def handle_message(self, message: GstMessage) -> GstMessage | None:
        if message.message_type != GST_MESSAGE_TYPES.BUFFER:
            return message
        message = cast(BufferMessage, message)

        image = Image.frombuffer("RGB", (message.width, message.height), message.buffer)
        try:
            results = self.model.predict(image)
            if results is None or len(results) == 0:
                return message
        except Exception as exc:
            logger.debug("Got error", exc_info=exc)
            return message

        boxes = [result.boxes.xyxy[0] for result in results if result.boxes is not None and len(result.boxes.xyxy) > 0]
        probs = [result.probs for result in results if result.probs is not None]

        if not boxes:
            return message

        self.drawer.process_bboxes(image, boxes, probs)
        message.buffer = image.tobytes()
        return message


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
