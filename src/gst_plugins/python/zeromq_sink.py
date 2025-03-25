import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstBase", "1.0")
import json
import logging

import zmq
from gi.repository import GObject, Gst, GstBase  # type: ignore

Gst.init(None)


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class ZeroMQSink(GstBase.BaseSink):
    __gstmetadata__ = (
        "ZeroMQ Sink",
        "Sink",
        "Отправляет буферы в ZeroMQ сокет с поддержкой множественных подключений",
        "Author",
    )

    __gsttemplates__ = (
        Gst.PadTemplate.new(
            "sink", Gst.PadDirection.SINK, Gst.PadPresence.ALWAYS, Gst.Caps.new_any()
        ),
    )

    __gproperties__ = {
        "address": (
            str,
            "Адрес ZeroMQ сокета",
            "Адрес ZeroMQ сокета для привязки (по умолчанию: tcp://127.0.0.1:5555)",
            "tcp://127.0.0.1:5555",
            GObject.ParamFlags.READWRITE,
        ),
        "topic": (
            str,
            "Тема публикации",
            "Тема для ZeroMQ PUB/SUB (по умолчанию: gst-media)",
            "gst-media",
            GObject.ParamFlags.READWRITE,
        ),
    }

    def __init__(self):
        super(ZeroMQSink, self).__init__()
        self.address = "tcp://127.0.0.1:5555"
        self.topic = "gst-media"
        self.context = None
        self.socket = None
        self.caps_str = None
        self.framerate = None
        self.width = None
        self.height = None
        self.format = None
        self.set_sync(False)  # Асинхронный режим для лучшей производительности

    def do_get_property(self, prop):
        if prop.name == "address":
            return self.address
        elif prop.name == "topic":
            return self.topic
        else:
            raise AttributeError("Неизвестное свойство %s" % prop.name)

    def do_set_property(self, prop, value):
        if prop.name == "address":
            self.address = value
        elif prop.name == "topic":
            self.topic = value
        else:
            raise AttributeError("Неизвестное свойство %s" % prop.name)

    def do_start(self):
        try:
            # Пересоздаем контекст при каждом запуске
            if self.context:
                self.context.term()

            self.context = zmq.Context()
            self.socket = self.context.socket(zmq.PUB)

            # Лимит очереди отправки
            self.socket.setsockopt(zmq.SNDHWM, 2)
            # Увеличим таймаут для медленных соединений
            self.socket.setsockopt(zmq.SNDTIMEO, 1000)

            self.socket.bind(self.address)

            logging.info(f"ZeroMQSink: привязан к {self.address}")
            return True
        except zmq.ZMQError as e:
            logging.error(f"ZeroMQSink: ZMQ ошибка: {e}")
            return False
        except Exception as e:
            logging.error(f"ZeroMQSink: общая ошибка: {e}")
            return False

    def do_stop(self):
        try:
            if self.socket:
                self.socket.setsockopt(zmq.LINGER, 0)  # Быстрое закрытие
                self.socket.close()
            if self.context:
                self.context.term()
        except Exception as e:
            logging.error(f"ZeroMQSink: ошибка при остановке: {e}")
        finally:
            self.socket = None
            self.context = None

        logging.info("ZeroMQSink: остановлен")
        return True

    def _parse_caps(self, caps):
        """Извлекает информацию из GstCaps"""
        structure = caps.get_structure(0)
        self.caps_str = caps.to_string()

        # Получаем базовую информацию о формате
        if structure.has_field("format"):
            self.format = structure.get_string("format")

        # Для видео получаем размер и частоту кадров
        if structure.has_field("width") and structure.has_field("height"):
            self.width = structure.get_int("width").value
            self.height = structure.get_int("height").value

        if structure.has_field("framerate"):
            _, fps_n, fps_d = structure.get_fraction("framerate")
            self.framerate = float(fps_n) / float(fps_d)

    def do_set_caps(self, caps):
        if not self.socket:
            raise RuntimeError("Сокет для публикации не инициализирован")

        self._parse_caps(caps)

        metadata = {
            "caps": self.caps_str,
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "framerate": self.framerate,
        }

        try:
            self.socket.send_multipart(
                [
                    self.topic.encode("utf-8"),
                    b"metadata",
                    json.dumps(metadata).encode("utf-8"),
                ],
                zmq.NOBLOCK,  # Не блокировать при отсутствии подключений
            )
        except zmq.Again:
            logging.info("ZeroMQSink: нет подключенных клиентов для метаданных")
        except Exception as e:
            logging.error(f"ZeroMQSink: ошибка отправки метаданных: {e}")

        return True

    def do_render(self, buffer):
        if not self.socket:
            raise RuntimeError("Сокет для публикации не инициализирован")

        try:
            success, map_info = buffer.map(Gst.MapFlags.READ)
            if not success:
                logging.error("ZeroMQSink: не удалось прочитать буфер")
                return Gst.FlowReturn.ERROR

            try:
                buffer_info = {
                    "pts": buffer.pts,
                    "dts": buffer.dts,
                    "duration": buffer.duration,
                    "size": len(map_info.data),
                    "type": "buffer",
                }

                # Отправляем многокомпонентное сообщение
                self.socket.send_multipart(
                    [
                        self.topic.encode("utf-8"),
                        b"buffer",
                        json.dumps(buffer_info).encode("utf-8"),
                        map_info.data,
                    ]
                )
                logging.debug(
                    f"ZeroMQSink: Отправлен буфер размером {len(map_info.data)} байт, pts={buffer.pts}"
                )

            finally:
                # Гарантированно анмапим буфер даже при ошибке отправки
                buffer.unmap(map_info)

            return Gst.FlowReturn.OK

        except Exception as e:
            logging.error(f"ZeroMQSink: ошибка при отправке: {e}")
            return Gst.FlowReturn.ERROR


GObject.type_register(ZeroMQSink)
__gstelementfactory__ = ("zeromq_sink", Gst.Rank.NONE, ZeroMQSink)
