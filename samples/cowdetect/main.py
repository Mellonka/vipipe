from PIL import Image
from ultralytics import YOLO
from vipipe.handlers.base import HandlerABC
from vipipe.handlers.drawer import Drawer
from vipipe.logging import get_logger
from vipipe.transport.gstreamer import BufferMessage, GstMessage, GstReader, GstWriter
from vipipe.transport.zeromq import ZeroMQReader, ZeroMQWriter
from vipipe.transport.zeromq.utils.cli import parse_zmq_config_cli

logger = get_logger("vipipe.handler.cowdetect")


class CowDetectHandler(HandlerABC):
    model: YOLO
    drawer: Drawer

    def on_startup(self):
        self.model = YOLO("/app/temp/counting.pt")
        self.drawer = Drawer()

    def handle_buffer_message(self, message: BufferMessage) -> GstMessage | None:
        if message.buffer_meta is None:
            logger.debug("Buffer meta is None, skipping message")
            return message

        image = Image.frombuffer("RGB", (message.buffer_meta.width, message.buffer_meta.height), message.buffer)
        try:
            results = self.model.predict(image)
            if results is None or len(results) == 0:
                logger.debug("No results from model, skipping message")
                return message
        except Exception as exc:
            logger.debug("Got error", exc_info=exc)
            return message

        boxes = [result.boxes.xyxy[0] for result in results if result.boxes is not None and len(result.boxes.xyxy) > 0]
        probs = [result.probs for result in results if result.probs is not None]

        if not boxes:
            return message

        self.drawer.draw_bboxes(image, boxes, probs)

        message.buffer = image.tobytes()
        return message


def main():
    reader_config, writer_config = parse_zmq_config_cli()
    logger.debug("Reader config: %s", reader_config)
    logger.debug("Writer config: %s", writer_config)

    reader = GstReader(ZeroMQReader(reader_config))
    writer = GstWriter(ZeroMQWriter(writer_config))

    logger.debug("Starting CowDetectProcess")
    CowDetectHandler(reader=reader, writer=writer).run()
    logger.debug("CowDetectProcess finished")


if __name__ == "__main__":
    main()
