import queue

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstBase", "1.0")
import json
import logging
import threading
import time
import traceback

import zmq
from gi.repository import GLib, GObject, Gst, GstBase  # type: ignore

Gst.init(None)


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class ZeroMQSrc(GstBase.BaseSrc):
    """
    ZeroMQ Source - GStreamer элемент для получения медиа-данных через ZeroMQ.

    Получает буферы и метаданные из ZeroMQ сокета и передает их в GStreamer pipeline.
    """

    __gstmetadata__ = (
        "ZeroMQ Source",
        "Source",
        "Получает буферы из ZeroMQ сокета",
        "Author",
    )

    __gsttemplates__ = (
        Gst.PadTemplate.new(
            "src", Gst.PadDirection.SRC, Gst.PadPresence.ALWAYS, Gst.Caps.new_any()
        ),
    )

    __gproperties__ = {
        "address": (
            str,
            "Адрес ZeroMQ сокета",
            "Адрес ZeroMQ сокета для подключения (по умолчанию: tcp://127.0.0.1:5555)",
            "tcp://127.0.0.1:5555",
            GObject.ParamFlags.READWRITE,
        ),
        "topic": (
            str,
            "Тема подписки",
            "Тема для ZeroMQ PUB/SUB (по умолчанию: gst-media)",
            "gst-media",
            GObject.ParamFlags.READWRITE,
        ),
        "is-live": (
            bool,
            "Использование режима реального времени",
            "Использование режима реального времени (по умолчанию: true)",
            True,
            GObject.ParamFlags.READWRITE,
        ),
        "timeout": (
            int,
            "Таймаут (мс)",
            "Таймаут ожидания буфера в миллисекундах (-1 для блокировки, по умолчанию: 5000 мс)",
            -1,
            60000,
            5000,
            GObject.ParamFlags.READWRITE,
        ),
        "max-queue-size": (
            int,
            "Максимальный размер очереди",
            "Максимальное количество буферов в очереди (по умолчанию: 30)",
            1,
            1000,
            30,
            GObject.ParamFlags.READWRITE,
        ),
    }

    def __init__(self):
        super(ZeroMQSrc, self).__init__()

        # Параметры подключения
        self._address = "tcp://127.0.0.1:5555"
        self._is_live = True
        self._topic = "gst-media"
        self._max_queue_size = 30

        # ZeroMQ и потоки
        self._context = None
        self._socket = None
        self._running = False
        self._poll_thread = None
        self._timeout = 5000  # мс

        # Данные медиа
        self._caps_received = False
        self._current_caps_str = None

        # Используем потокобезопасную очередь вместо списка с блокировкой
        self._buffer_queue = queue.Queue(maxsize=self._max_queue_size)

        self.set_live(self._is_live)
        self.set_format(Gst.Format.TIME)

    def do_get_property(self, prop):
        """Получение значения свойства элемента."""
        if prop.name == "address":
            return self._address
        elif prop.name == "is-live":
            return self._is_live
        elif prop.name == "topic":
            return self._topic
        elif prop.name == "timeout":
            return self._timeout
        elif prop.name == "max-queue-size":
            return self._max_queue_size
        else:
            raise AttributeError(f"Неизвестное свойство {prop.name}")

    def do_set_property(self, prop, value):
        """Установка значения свойства элемента."""
        if prop.name == "address":
            self._address = value
        elif prop.name == "is-live":
            self._is_live = value
        elif prop.name == "topic":
            self._topic = value
        elif prop.name == "timeout":
            self._timeout = value
        elif prop.name == "max-queue-size":
            self._max_queue_size = value
            if not self._running:
                self._buffer_queue = queue.Queue(maxsize=self._max_queue_size)
            else:
                raise RuntimeError(
                    "Очередь уже запущена, невозможно изменить ее размер"
                )
        else:
            raise AttributeError(f"Неизвестное свойство {prop.name}")

    def _handle_metadata_message(self, metadata_bytes):
        """Обрабатывает метаданные, полученные из ZeroMQ."""
        try:
            metadata_json = metadata_bytes.decode("utf-8")
            metadata = json.loads(metadata_json)
            logger.info(f"ZeroMQSrc: получены метаданные: {metadata}")

            # Устанавливаем caps для элемента в основном потоке GStreamer
            if "caps" in metadata:
                self._current_caps_str = metadata["caps"]
                GLib.idle_add(self._update_caps)
        except Exception as e:
            logger.error(f"ZeroMQSrc: ошибка при обработке метаданных: {e}")

    def _handle_buffer_message(self, buffer_parts):
        """Обрабатывает буфер данных, полученный из ZeroMQ."""
        try:
            buffer_info_json = buffer_parts[0].decode("utf-8")
            buffer_info = json.loads(buffer_info_json)
            buffer_data = buffer_parts[1]

            # Создаем новый буфер GStreamer
            buf = Gst.Buffer.new_allocate(None, len(buffer_data), None)
            if buf is None:
                logger.error("ZeroMQSrc: не удалось создать буфер")
                return

            buf.fill(0, buffer_data)

            # Устанавливаем информацию о времени
            if "pts" in buffer_info and buffer_info["pts"] is not None:
                buf.pts = buffer_info["pts"]
            if "dts" in buffer_info and buffer_info["dts"] is not None:
                buf.dts = buffer_info["dts"]
            if "duration" in buffer_info and buffer_info["duration"] is not None:
                buf.duration = buffer_info["duration"]

            # Добавляем буфер в очередь, если она полна - удаляем старейший буфер
            try:
                if self._buffer_queue.full():
                    # Удаляем старейший буфер, чтобы освободить место
                    try:
                        self._buffer_queue.get_nowait()
                    except queue.Empty:
                        pass  # Маловероятно, но на всякий случай

                self._buffer_queue.put_nowait(buf)

                # Сигнализируем GStreamer, что у нас есть данные
                self.srcpad.push_event(
                    Gst.Event.new_custom(
                        Gst.EventType.CUSTOM_DOWNSTREAM,
                        Gst.Structure.new_empty("have-data"),
                    )
                )
            except queue.Full:
                logger.warning("ZeroMQSrc: очередь буферов переполнена, буфер отброшен")
        except Exception as e:
            logger.error(f"ZeroMQSrc: ошибка при обработке буфера: {e}")
            logger.error(traceback.format_exc())

    def _receive_thread(self):
        """Фоновый поток для получения данных из ZeroMQ."""

        if not self._socket:
            raise RuntimeError("Сокет для получения данных не инициализирован")

        logger.info("ZeroMQSrc: поток получения данных запущен")

        poller = zmq.Poller()
        poller.register(self._socket, zmq.POLLIN)

        reconnect_delay = 1.0  # начальная задержка для переподключения (секунды)
        max_reconnect_delay = 15.0  # максимальная задержка (секунды)

        while self._running:
            try:
                # Ожидаем данные 500 мс
                sockets = dict(poller.poll(500))

                if self._socket in sockets and sockets[self._socket] == zmq.POLLIN:
                    # Сброс задержки при успешном получении
                    reconnect_delay = 1.0

                    # Получаем многокомпонентное сообщение
                    multipart_msg = self._socket.recv_multipart()

                    if len(multipart_msg) < 3:
                        logger.warning("ZeroMQSrc: получено неверное сообщение")
                        continue

                    _ = multipart_msg[0]  # Тема сообщения
                    msg_type = multipart_msg[1]  # Тип сообщения

                    if msg_type == b"metadata":
                        self._handle_metadata_message(multipart_msg[2])
                    elif msg_type == b"buffer":
                        self._handle_buffer_message(multipart_msg[2:])
                    else:
                        logger.warning(
                            f"ZeroMQSrc: неизвестный тип сообщения: {msg_type}"
                        )
                else:
                    logger.debug("ZeroMQSrc: Не получили данных")

            except zmq.ZMQError as e:
                if self._running:  # Игнорируем ошибки при остановке
                    logger.error(f"ZeroMQSrc: ошибка ZMQ: {e}")
                    time.sleep(reconnect_delay)
                    reconnect_delay = min(reconnect_delay * 1.5, max_reconnect_delay)
                    self._reconnect_socket()
            except Exception as e:
                if self._running:
                    logger.error(f"ZeroMQSrc: ошибка в потоке получения: {e}")
                    logger.error(traceback.format_exc())
                    time.sleep(1.0)

        logger.debug("ZeroMQSrc: поток получения данных остановлен")

    def _reconnect_socket(self):
        """Переподключает ZeroMQ сокет в случае ошибки."""
        if not self._context:
            raise RuntimeError("Контекст ZeroMQ не инициализирован")

        try:
            logger.info(f"ZeroMQSrc: попытка переподключения к {self._address}")

            # Закрываем старый сокет
            if self._socket:
                try:
                    self._socket.close()
                except:
                    pass

            # Создаем новый сокет
            self._socket = self._context.socket(zmq.SUB)
            self._socket.connect(self._address)
            self._socket.setsockopt_string(zmq.SUBSCRIBE, self._topic)

            logger.info("ZeroMQSrc: переподключение успешно")
            return True
        except Exception as e:
            logger.error(f"ZeroMQSrc: ошибка при переподключении: {e}")
            return False

    def _update_caps(self):
        """Обновляет caps элемента в основном потоке GStreamer."""
        if self._current_caps_str:
            try:
                new_caps = Gst.Caps.from_string(self._current_caps_str)
                if new_caps:
                    logger.info(f"ZeroMQSrc: установка caps: {self._current_caps_str}")
                    self.srcpad.push_event(Gst.Event.new_caps(new_caps))
                    self._caps_received = True
            except Exception as e:
                logger.error(f"ZeroMQSrc: ошибка при установке caps: {e}")
        return False  # Одноразовый вызов для GLib.idle_add

    def do_start(self):
        """Запускает элемент и подключается к ZeroMQ."""
        if not self._address:
            logger.error("ZeroMQSrc: адрес не установлен")
            return False

        try:
            # Инициализация ZeroMQ
            self._context = zmq.Context()
            self._reconnect_socket()

            # Сбрасываем очередь перед запуском
            self._buffer_queue = queue.Queue(maxsize=self._max_queue_size)

            # Запускаем фоновый поток для получения данных
            self._running = True
            self._poll_thread = threading.Thread(target=self._receive_thread)
            self._poll_thread.daemon = True
            self._poll_thread.start()

            logger.info(
                f"ZeroMQSrc: подключен к {self._address} с топиком '{self._topic}'"
            )
            return True
        except Exception as e:
            logger.error(f"ZeroMQSrc: ошибка при запуске: {e}")
            logger.error(traceback.format_exc())
            return False

    def do_stop(self):
        """Останавливает элемент и освобождает ресурсы."""
        # Останавливаем поток получения данных
        self._running = False
        if self._poll_thread and self._poll_thread.is_alive():
            self._poll_thread.join(1.0)  # Ждем не более 1 секунды

        # Закрываем сокет и контекст
        try:
            if self._socket:
                self._socket.close()
                self._socket = None
            if self._context:
                self._context.term()
                self._context = None
        except Exception as e:
            logger.warning(f"ZeroMQSrc: ошибка при закрытии ресурсов: {e}")

        # Очищаем данные
        self._buffer_queue = queue.Queue(maxsize=self._max_queue_size)
        self._caps_received = False
        self._current_caps_str = None

        logger.info("ZeroMQSrc: остановлен")
        return True

    def do_create(self, offset, size, amount):
        """Создает новый буфер для выдачи из элемента."""
        start_time = time.time()
        timeout = self._timeout

        while self._running and (
            timeout is None or (time.time() - start_time) * 1000 < timeout
        ):
            try:
                buf = self._buffer_queue.get_nowait()
                logger.debug("ZeroMQSrc: Получили буффер")
                return Gst.FlowReturn.OK, buf
            except queue.Empty:
                time.sleep(0.01)
                continue

        return Gst.FlowReturn.EOS, None


# Регистрируем плагин
GObject.type_register(ZeroMQSrc)
__gstelementfactory__ = ("zeromq_src", Gst.Rank.NONE, ZeroMQSrc)
