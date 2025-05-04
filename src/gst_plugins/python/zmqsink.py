import gi
import zmq
from vipipe.logging import get_logger
from vipipe.transport.gstreamer import BufferMessage, BufferMetaMessage, CapsMessage, CustomMetaMessage, GstWriter
from vipipe.transport.zeromq import ZeroMQWriter, ZeroMQWriterConfig

gi.require_version("Gst", "1.0")
gi.require_version("GstBase", "1.0")
gi.require_version("GObject", "2.0")
from gi.repository import GLib, GObject, Gst, GstBase  # type: ignore

Gst.init(None)

logger = get_logger("vipipe.gst_plugins.zmqsink")


class GstZeroMQSink(GstBase.BaseSink):
    GST_PLUGIN_NAME = "zmqsink"

    __gstmetadata__ = (
        "ZeroMQ Sink",
        "Sink",
        "Отправляет буферы",
        "mellonka",
    )

    __gsttemplates__ = (Gst.PadTemplate.new("sink", Gst.PadDirection.SINK, Gst.PadPresence.ALWAYS, Gst.Caps.new_any()),)

    # Define properties
    __gproperties__ = {
        "address": (
            str,
            "ZeroMQ Socket Address",
            "The address of the ZeroMQ socket (e.g., tcp://127.0.0.1:5555)",
            "",
            GObject.ParamFlags.READWRITE,
        ),
        "buffer-length": (
            int,
            "Buffer Length",
            "Maximum number of messages in the queue",
            1,
            GLib.MAXINT,
            10,  # Default
            GObject.ParamFlags.READWRITE,
        ),
        "buffer-size-os": (
            int,
            "OS Buffer Size",
            "Size of the OS buffer in bytes",
            1,
            GLib.MAXINT,
            1024 * 1024 * 30,  # Default 10MB
            GObject.ParamFlags.READWRITE,
        ),
        "send-timeout": (
            int,
            "Send Timeout",
            "Maximum wait time (ms) for send operation",
            0,
            GLib.MAXINT,
            100,  # Default
            GObject.ParamFlags.READWRITE,
        ),
        "immediate": (
            bool,
            "Immediate",
            "Send messages only when clients are active",
            True,  # Default
            GObject.ParamFlags.READWRITE,
        ),
        "conflate": (
            bool,
            "Conflate",
            "Keep only the last message in the queue",
            False,  # Default
            GObject.ParamFlags.READWRITE,
        ),
        "linger": (
            int,
            "Linger",
            "Time (ms) to try sending remaining messages",
            -1,
            GLib.MAXINT,
            500,  # Default
            GObject.ParamFlags.READWRITE,
        ),
        "dontwait": (
            bool,
            "Don't Wait",
            "Don't wait if message cannot be sent immediately",
            False,  # Default
            GObject.ParamFlags.READWRITE,
        ),
    }

    def __init__(self):
        super(GstZeroMQSink, self).__init__()

        self.address = ""
        self.buffer_length = 10
        self.buffer_size_os = 1024 * 1024 * 30
        self.send_timeout = 100
        self.immediate = True
        self.conflate = False
        self.linger = 500
        self.dontwait = False

        # caps params
        self.caps_str = None
        self.format = None
        self.width = None
        self.height = None
        self.fps_n = None
        self.fps_d = None
        self.framerate = None

        self.writer = None

    def do_get_property(self, prop):
        if prop.name == "address":
            return self.address
        elif prop.name == "buffer-length":
            return self.buffer_length
        elif prop.name == "buffer-size-os":
            return self.buffer_size_os
        elif prop.name == "send-timeout":
            return self.send_timeout
        elif prop.name == "immediate":
            return self.immediate
        elif prop.name == "conflate":
            return self.conflate
        elif prop.name == "linger":
            return self.linger
        elif prop.name == "dontwait":
            return self.dontwait
        else:
            raise AttributeError(f"Unknown property {prop.name}")

    def do_set_property(self, prop, value):
        if prop.name == "address":
            self.address = value
        elif prop.name == "buffer-length":
            self.buffer_length = value
        elif prop.name == "buffer-size-os":
            self.buffer_size_os = value
        elif prop.name == "send-timeout":
            self.send_timeout = value
        elif prop.name == "immediate":
            self.immediate = value
        elif prop.name == "conflate":
            self.conflate = value
        elif prop.name == "linger":
            self.linger = value
        elif prop.name == "dontwait":
            self.dontwait = value
        else:
            raise AttributeError(f"Unknown property {prop.name}")

    def do_start(self):
        if self.writer:
            self.writer.stop()

        self.writer = GstWriter(
            ZeroMQWriter(
                ZeroMQWriterConfig(
                    address=self.address,
                    socket_type=zmq.SocketType.PUB,
                    buffer_length=self.buffer_length,
                    buffer_size_os=self.buffer_size_os,
                    send_timeout=self.send_timeout,
                    immediate=self.immediate,
                    conflate=self.conflate,
                    linger=self.linger,
                )
            )
        )

        try:
            self.writer.start()
            return True
        except Exception as e:
            Gst.error(f"Failed to start ZeroMQ publisher: {e}")
            return False

    def do_stop(self):
        if self.writer:
            try:
                self.writer.stop()
                self.writer = None
                return True
            except Exception as e:
                Gst.error(f"Failed to stop ZeroMQ publisher: {e}")
                return False
        return True

    def _parse_caps(self, caps):
        """Извлекает информацию из GstCaps"""
        structure = caps.get_structure(0)
        self.caps_str = caps.to_string()

        if structure.has_field("format"):
            self.format = structure.get_string("format")

        if structure.has_field("width"):
            self.width = structure.get_int("width").value

        if structure.has_field("height"):
            self.height = structure.get_int("height").value

        if structure.has_field("framerate"):
            _, fps_n, fps_d = structure.get_fraction("framerate")
            self.fps_n = fps_n
            self.fps_d = fps_d
            self.framerate = f"{fps_n}/{fps_d}"

    def do_set_caps(self, caps):
        if not self.writer:
            raise RuntimeError("Сокет для публикации не инициализирован")

        self._parse_caps(caps)
        assert self.caps_str is not None

        try:
            self.writer.write(
                CapsMessage(
                    width=self.width,  # type: ignore
                    height=self.height,  # type: ignore
                    format=self.format,
                    fps_n=self.fps_n,
                    fps_d=self.fps_d,
                    framerate=self.framerate,
                    caps_str=self.caps_str,
                )
            )
            logger.debug("Отправили капсы")
        except zmq.Again:
            pass

        return True

    def do_render(self, buffer):
        if self.writer is None:
            logger.error("Сокет для публикации не инициализирован")
            return Gst.FlowReturn.ERROR

        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            logger.error("Ошибка при чтении буфера")
            return Gst.FlowReturn.ERROR

        try:
            # Извлекаем пользовательские метаданные, если они есть
            custom_meta_data = buffer.get_custom_meta("VipipeCustomMeta") or None
            logger.info(f"custom_meta_data: {custom_meta_data}")
            custom_meta_data = custom_meta_data and custom_meta_data.get_structure().get_value("vipipe_custom_meta")
            logger.info(f"custom_meta_data: {custom_meta_data}")
            custom_meta = custom_meta_data and CustomMetaMessage.from_json(custom_meta_data)

            buffer_meta = BufferMetaMessage(
                pts=buffer.pts,
                dts=buffer.dts if buffer.dts != Gst.CLOCK_TIME_NONE else None,
                duration=buffer.duration if buffer.duration != Gst.CLOCK_TIME_NONE else None,
                width=self.width,  # type: ignore
                height=self.height,  # type: ignore
                flags=buffer.get_flags(),
                caps_str=self.caps_str,
            )

            buffer_message = BufferMessage(
                buffer=bytes(map_info.data),
                buffer_meta=buffer_meta,
                custom_meta=custom_meta,
            )

            self.writer.write(buffer_message)
            logger.debug("Буфер отправлен")

            return Gst.FlowReturn.OK
        except zmq.Again:
            logger.warning("Передача буфера отклонена (zmq.Again)")
            return Gst.FlowReturn.OK
        except Exception as e:
            logger.error("Ошибка публикации буфера: %s", e)
            return Gst.FlowReturn.ERROR
        finally:
            buffer.unmap(map_info)


# register plugin
GObject.type_register(GstZeroMQSink)
__gstelementfactory__ = (GstZeroMQSink.GST_PLUGIN_NAME, Gst.Rank.NONE, GstZeroMQSink)
