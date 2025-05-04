from facenet_pytorch import MTCNN
from PIL import Image
from vipipe.handlers import Drawer, HandlerABC
from vipipe.logging import get_logger
from vipipe.transport.gstreamer import BufferMessage, GstMessage, GstReader, GstWriter
from vipipe.transport.zeromq import ZeroMQReader, ZeroMQWriter
from vipipe.transport.zeromq.utils.cli import parse_zmq_config_cli

logger = get_logger("vipipe.handler.facenet")


class FacenetHandler(HandlerABC):
    def on_startup(self):
        self.model = MTCNN(keep_all=True)
        self.drawer = Drawer()

    def handle_buffer_message(self, message: BufferMessage) -> GstMessage | None:
        if message.buffer_meta is None:
            logger.debug("Buffer meta is None, skipping message")
            return message

        image = Image.frombuffer("RGB", (message.buffer_meta.width, message.buffer_meta.height), message.buffer)

        boxes, probs = self.model.detect(image)  # type: ignore
        self.drawer.draw_bboxes(image, boxes, probs)  # type: ignore

        logger.debug(f"Detected {len(boxes)} faces")

        message.buffer = image.tobytes()
        return message


def main():
    reader_config, writer_config = parse_zmq_config_cli()

    reader = GstReader(ZeroMQReader(reader_config))
    writer = GstWriter(ZeroMQWriter(writer_config))

    logger.debug("Starting Facenet process")
    FacenetHandler(reader=reader, writer=writer).run()
    logger.debug("Facenet process finished")


if __name__ == "__main__":
    main()
