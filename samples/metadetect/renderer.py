from PIL import Image
from vipipe.handlers.base import HandlerABC
from vipipe.handlers.drawer import Drawer
from vipipe.logging import get_logger
from vipipe.transport.gstreamer import BufferMessage, GstMessage, GstReader, GstWriter
from vipipe.transport.gstreamer.entity import ObjectsMetaMessage
from vipipe.transport.zeromq import ZeroMQReader, ZeroMQWriter
from vipipe.transport.zeromq.utils.cli import parse_zmq_config_cli

logger = get_logger("vipipe.handler.metadetect.renderer")


class ObjectRendererHandler(HandlerABC):
    def on_startup(self):
        self.drawer = Drawer(thickness=4)
        logger.info("Рендерер инициализирован")

    def handle_buffer_message(self, message: BufferMessage) -> GstMessage | None:
        if message.buffer_meta is None:
            logger.debug("Buffer meta is None, skipping message")
            return message

        objects_meta = message.custom_meta and ObjectsMetaMessage(message.custom_meta.metadata)
        if objects_meta and len(objects_meta.objects) > 0:
            logger.debug(f"Получено {len(objects_meta.objects)} объектов для отрисовки")
        else:
            logger.debug("Нет метаданных объектов для отрисовки")
            return message

        img_width = message.buffer_meta.width
        img_height = message.buffer_meta.height
        try:
            image = Image.frombuffer("RGB", (img_width, img_height), message.buffer)
        except Exception as e:
            logger.error(f"Ошибка создания изображения: {e}")
            return message

        self.drawer.draw_objects(image, objects_meta.objects)

        message.buffer = image.tobytes()
        return message


def main():
    reader_config, writer_config = parse_zmq_config_cli()

    logger.info("Запуск рендерера объектов")
    logger.info(f"Чтение из: {reader_config.address}")
    logger.info(f"Запись в: {writer_config.address}")

    reader = GstReader(ZeroMQReader(reader_config))
    writer = GstWriter(ZeroMQWriter(writer_config))

    ObjectRendererHandler(reader=reader, writer=writer).run()
    logger.info("Работа рендерера завершена")


if __name__ == "__main__":
    main()
