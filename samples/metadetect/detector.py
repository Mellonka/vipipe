from PIL import Image
from ultralytics import YOLO
from vipipe.handlers.base import HandlerABC
from vipipe.logging import get_logger
from vipipe.transport.gstreamer import BufferMessage, GstMessage, GstReader, GstWriter
from vipipe.transport.gstreamer.entity import ObjectsMetaMessage
from vipipe.transport.zeromq import ZeroMQReader, ZeroMQWriter
from vipipe.transport.zeromq.utils.cli import parse_zmq_config_cli

logger = get_logger("vipipe.handler.metadetect.detector")


class ObjectDetectorHandler(HandlerABC):
    def on_startup(self):
        # Загрузка модели YOLOv5 для обнаружения объектов
        self.model = YOLO("/app/models/yolov5s.pt")
        # Настраиваем порог уверенности и классы для детекции
        self.conf_threshold = 0.25

        logger.info("Модель детектора инициализирована")

    def handle_buffer_message(self, message: BufferMessage) -> GstMessage | None:
        if message.buffer_meta is None:
            logger.debug("Buffer meta is None, skipping message")
            return message

        img_width = message.buffer_meta.width
        img_height = message.buffer_meta.height
        try:
            image = Image.frombuffer("RGB", (img_width, img_height), message.buffer)
        except Exception as exc:
            logger.error(f"Ошибка создания изображения: {exc}")
            return message

        try:
            results = self.model.predict(image, conf=self.conf_threshold)

            objects_meta = ObjectsMetaMessage(metadata={"objects": []})

            if results and len(results) > 0:
                for result in results:
                    if result.boxes is None or len(result.boxes) == 0:
                        continue

                    for _, box in enumerate(result.boxes):  # type: ignore
                        bbox = box.xyxy[0].tolist()  # [x1, y1, x2, y2]
                        conf = float(box.conf[0]) if box.conf is not None else 0.0
                        class_id = int(box.cls[0]) if box.cls is not None else -1
                        label = result.names[class_id] if class_id in result.names else f"class_{class_id}"

                        logger.debug(f"Обнаружен объект: {label} с вероятностью {conf}, координаты: {bbox}")

                        # Добавляем объект в метаданные
                        objects_meta.add_object(
                            bbox=tuple(bbox),
                            conf=conf,
                            class_id=class_id,
                            label=label,
                            attributes={"detection_source": "yolov5"},
                        )

                logger.debug(f"Обнаружено {len(objects_meta.objects)} объектов")

            message.custom_meta = objects_meta

        except Exception as exc:
            logger.error(f"Ошибка обработки изображения: {exc}")

        return message


def main():
    reader_config, writer_config = parse_zmq_config_cli()

    logger.info("Запуск рендерера объектов")
    logger.info(f"Чтение из: {reader_config.address}")
    logger.info(f"Запись в: {writer_config.address}")

    reader = GstReader(ZeroMQReader(reader_config))
    writer = GstWriter(ZeroMQWriter(writer_config))

    ObjectDetectorHandler(reader=reader, writer=writer).run()
    logger.info("Работа детектора завершена")


if __name__ == "__main__":
    main()
