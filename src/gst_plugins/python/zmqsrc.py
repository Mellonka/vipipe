import gi
import zmq
from vipipe.logging import get_logger
from vipipe.transport.gstreamer import GST_MESSAGE_TYPES, BufferMessage, GstReader
from vipipe.transport.zeromq import ZeroMQReader, ZeroMQReaderConfig

gi.require_version("Gst", "1.0")
gi.require_version("GstBase", "1.0")
gi.require_version("GObject", "2.0")
from gi.repository import GLib, GObject, Gst, GstBase  # type: ignore

Gst.init(None)


logger = get_logger("vipipe.gst_plugins.zmqsrc")


class GstZeroMQSrc(GstBase.BaseSrc):
    GST_PLUGIN_NAME = "zmqsrc"

    __gstmetadata__ = (
        "ZeroMQ Src",
        "Src",
        "Получает буферы",
        "mellonka",
    )

    __gsttemplates__ = (Gst.PadTemplate.new("src", Gst.PadDirection.SRC, Gst.PadPresence.ALWAYS, Gst.Caps.new_any()),)

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
        "read-timeout": (
            int,
            "Send Timeout",
            "Maximum wait time (ms) for receive operation",
            0,
            GLib.MAXINT,
            5000,  # Default
            GObject.ParamFlags.READWRITE,
        ),
        "conflate": (
            bool,
            "Conflate",
            "Keep only the last message in the queue",
            False,  # Default
            GObject.ParamFlags.READWRITE,
        ),
        "dontwait": (
            bool,
            "Don't Wait",
            "Don't wait if message cannot be received immediately",
            False,  # Default
            GObject.ParamFlags.READWRITE,
        ),
    }

    def __init__(self):
        super(GstZeroMQSrc, self).__init__()
        self.set_format(Gst.Format.TIME)
        self.set_live(True)

        self.address = ""
        self.buffer_length = 10
        self.buffer_size_os = 1024 * 1024 * 30
        self.read_timeout = 5000
        self.conflate = False
        self.dontwait = False

        # caps params
        self.caps_str = None
        self.format = None
        self.width = None
        self.height = None
        self.fps_n = None
        self.fps_d = None
        self.framerate = None

        self.reader = None

    def do_is_seekable(self):
        return False

    def do_get_property(self, prop):
        if prop.name == "address":
            return self.address
        elif prop.name == "buffer-length":
            return self.buffer_length
        elif prop.name == "buffer-size-os":
            return self.buffer_size_os
        elif prop.name == "read-timeout":
            return self.read_timeout
        elif prop.name == "conflate":
            return self.conflate
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
        elif prop.name == "read-timeout":
            self.read_timeout = value
        elif prop.name == "conflate":
            self.conflate = value
        elif prop.name == "dontwait":
            self.dontwait = value
        else:
            raise AttributeError(f"Unknown property {prop.name}")

    def do_start(self):
        if self.reader:
            self.reader.stop()

        self.reader = GstReader(
            ZeroMQReader(
                ZeroMQReaderConfig(
                    address=self.address,
                    socket_type=zmq.SocketType.SUB,
                    buffer_length=self.buffer_length,
                    buffer_size_os=self.buffer_size_os,
                    read_timeout=self.read_timeout,
                    conflate=self.conflate,
                )
            )
        )

        try:
            self.reader.start()
            return True
        except Exception as e:
            Gst.error(f"Failed to start ZeroMQ reader: {e}")
            return False

    def do_stop(self):
        if not self.reader:
            return True
        try:
            self.reader.stop()
            self.reader = None
        except Exception as e:
            Gst.error(f"Failed to stop ZeroMQ reader: {e}")
            return False
        return True

    def _parse_caps(self, caps_str: str):
        """Извлекает информацию из GstCaps"""

        if self.caps_str == caps_str:
            return

        self.caps_str = caps_str

        caps = Gst.Caps.from_string(caps_str)
        self.srcpad.push_event(Gst.Event.new_caps(caps))
        structure = caps.get_structure(0)

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

        logger.debug("Получили капсы %s", caps_str)

    def handle_buffer_message(self, message: BufferMessage):
        logger.debug("Получили буффер размера %d", len(message.buffer))

        assert message.buffer_meta is not None, "Buffer is None"

        if message.buffer_meta.caps_str and message.buffer_meta.caps_str != self.caps_str:
            self._parse_caps(message.buffer_meta.caps_str)

        buffer = Gst.Buffer.new_allocate(None, len(message.buffer), None)
        if buffer is None:
            return Gst.FlowReturn.ERROR, None

        buffer.pts = message.buffer_meta.pts
        if message.buffer_meta.dts is not None:
            buffer.dts = message.buffer_meta.dts
        if message.buffer_meta.duration is not None:
            buffer.duration = message.buffer_meta.duration
        if message.buffer_meta.flags is not None:
            buffer.set_flags(Gst.BufferFlags(message.buffer_meta.flags))

        # Добавляем пользовательские метаданные, если они есть
        if message.custom_meta is not None:
            custom_meta = buffer.add_custom_meta("VipipeCustomMeta")
            struct = custom_meta.get_structure()
            struct.set_value("vipipe_custom_meta", message.custom_meta.to_json())
            logger.info(f"structure: {struct.to_string()}")
            logger.info(f"custom_meta: {custom_meta}")

        buffer.fill(0, message.buffer)
        return Gst.FlowReturn.OK, buffer

    def do_create(self, offset, size, amount):
        if self.reader is None:
            return Gst.FlowReturn.ERROR

        logger.debug("Trying to read message from ZeroMQ")

        while True:
            message = self.reader.read()
            if message is None:
                logger.debug("No message received")
                continue

            match message.MESSAGE_TYPE:
                case GST_MESSAGE_TYPES.BUFFER:
                    return self.handle_buffer_message(message)  # type: ignore
                case GST_MESSAGE_TYPES.CAPS:
                    self._parse_caps(message.caps_str)  # type: ignore
                case GST_MESSAGE_TYPES.EOS:
                    return Gst.FlowReturn.EOS, None
                case _:
                    logger.debug("Got message type %s", message.MESSAGE_TYPE)


# register plugin
GObject.type_register(GstZeroMQSrc)
__gstelementfactory__ = (GstZeroMQSrc.GST_PLUGIN_NAME, Gst.Rank.NONE, GstZeroMQSrc)
