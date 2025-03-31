import json
import logging
import time

import gi
from vipipe.zeromq.message import ZeroMQMessage

gi.require_version("Gst", "1.0")
gi.require_version("GstBase", "1.0")
import zmq
from gi.repository import GLib, GObject, Gst, GstBase  # type: ignore
from vipipe.zeromq.reader import ZeroMQReader

Gst.init(None)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


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
            50,  # Default
            GObject.ParamFlags.READWRITE,
        ),
        "buffer-size-oc": (
            int,
            "OS Buffer Size",
            "Size of the OS buffer in bytes",
            1,
            GLib.MAXINT,
            1024 * 1024 * 10,  # Default 10MB
            GObject.ParamFlags.READWRITE,
        ),
        "recv-timeout": (
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
        self.buffer_length = 50
        self.buffer_size_oc = 1024 * 1024 * 10
        self.recv_timeout = 5000
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
        elif prop.name == "buffer-size-oc":
            return self.buffer_size_oc
        elif prop.name == "recv-timeout":
            return self.recv_timeout
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
        elif prop.name == "buffer-size-oc":
            self.buffer_size_oc = value
        elif prop.name == "recv-timeout":
            self.recv_timeout = value
        elif prop.name == "conflate":
            self.conflate = value
        elif prop.name == "dontwait":
            self.dontwait = value
        else:
            raise AttributeError(f"Unknown property {prop.name}")

    def do_start(self):
        if self.reader:
            self.reader.stop()

        self.reader = ZeroMQReader(
            address=self.address,
            socket_type=zmq.SocketType.SUB,
            buffer_length=self.buffer_length,
            buffer_size_oc=self.buffer_size_oc,
            recv_timeout=self.recv_timeout,
            conflate=self.conflate,
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
            self.framerate = float(fps_n) / float(fps_d)

    def handle_caps_message(self, message: ZeroMQMessage):
        caps_info_json = message.data[0].decode()
        caps_info = json.loads(caps_info_json)
        caps = Gst.Caps.from_string(caps_info["caps"])
        self._parse_caps(caps)
        self.srcpad.push_event(Gst.Event.new_caps(caps))
        logger.debug("Получили капсы %s", caps.to_string())

    def handle_buffer_message(self, message: ZeroMQMessage):
        buffer_info_json = message.data[0].decode()
        buffer_info = json.loads(buffer_info_json)
        buffer_data = message.data[1]

        buffer = Gst.Buffer.new_allocate(None, len(buffer_data), None)
        if buffer is None:
            return Gst.FlowReturn.ERROR, None

        if (pts := buffer_info.get("pts")) is not None:
            buffer.pts = pts
        if (dts := buffer_info.get("dts")) is not None:
            buffer.dts = dts
        if (duration := buffer_info.get("duration")) is not None:
            buffer.duration = duration
        if (flags := buffer_info.get("flags")) is not None:
            buffer.set_flags(Gst.BufferFlags(flags))

        buffer.fill(0, buffer_data)

        logger.debug("Получили буффер размера %d", len(buffer_data))

        return Gst.FlowReturn.OK, buffer

    def do_create(self, offset, size, amount):
        if self.reader is None:
            return Gst.FlowReturn.ERROR

        logger.debug("Пытаемся получить сообщение")

        while True:
            message = self.reader.read()
            if message is None:
                logger.debug("Не получили сообщение, спим и пробуем снова")

                time.sleep(0.5)
                continue

            logger.debug("Получили сообщение, тип %s", message.message_type.decode())

            if message.message_type == b"caps":
                self.handle_caps_message(message)
            elif message.message_type == b"buffer":
                return self.handle_buffer_message(message)
            else:
                logger.warning("Неизвестный тип сообщения")


# register plugin
GObject.type_register(GstZeroMQSrc)
__gstelementfactory__ = (GstZeroMQSrc.GST_PLUGIN_NAME, Gst.Rank.NONE, GstZeroMQSrc)
