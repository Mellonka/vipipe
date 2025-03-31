import json
import logging

import gi

gi.require_version("Gst", "1.0")
gi.require_version("GstBase", "1.0")
import zmq
from gi.repository import GLib, GObject, Gst, GstBase  # type: ignore
from vipipe.zeromq.message import ZeroMQMessage
from vipipe.zeromq.writer import ZeroMQWriter

Gst.init(None)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


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
        self.buffer_length = 50
        self.buffer_size_oc = 1024 * 1024 * 10
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
        elif prop.name == "buffer-size-oc":
            return self.buffer_size_oc
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
        elif prop.name == "buffer-size-oc":
            self.buffer_size_oc = value
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

        self.writer = ZeroMQWriter(
            address=self.address,
            socket_type=zmq.SocketType.PUB,
            buffer_length=self.buffer_length,
            buffer_size_oc=self.buffer_size_oc,
            send_timeout=self.send_timeout,
            immediate=self.immediate,
            conflate=self.conflate,
            linger=self.linger,
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
            self.framerate = float(fps_n) / float(fps_d)

    def do_set_caps(self, caps):
        if not self.writer:
            raise RuntimeError("Сокет для публикации не инициализирован")

        self._parse_caps(caps)

        metadata = {
            "caps": self.caps_str,
            "width": self.width,
            "height": self.height,
            "format": self.format,
            "fps_n": self.fps_n,
            "fps_d": self.fps_d,
            "framerate": self.framerate,
        }

        try:
            self.writer.write(
                ZeroMQMessage(
                    None,
                    b"caps",
                    [json.dumps(metadata).encode("utf-8")],
                ),
            )
            logger.debug("Отправили капсы")
        except zmq.Again:
            pass

        return True

    def do_render(self, buffer):
        if self.writer is None:
            return Gst.FlowReturn.ERROR

        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            return Gst.FlowReturn.ERROR

        try:
            logger.debug("пытаемся отправить буфер")
            metadata = {
                "pts": buffer.pts,
                "dts": buffer.dts if buffer.dts != Gst.CLOCK_TIME_NONE else None,
                "duration": (buffer.duration if buffer.duration != Gst.CLOCK_TIME_NONE else None),
                "flags": buffer.get_flags(),
                "size": buffer.get_size(),
            }

            self.writer.write(
                ZeroMQMessage(
                    None,
                    message_type=b"buffer",
                    data=[json.dumps(metadata).encode(), map_info.data],
                )
            )
            logger.debug("Отправили буфер")

        finally:
            buffer.unmap(map_info)

        return Gst.FlowReturn.OK


# register plugin
GObject.type_register(GstZeroMQSink)
__gstelementfactory__ = (GstZeroMQSink.GST_PLUGIN_NAME, Gst.Rank.NONE, GstZeroMQSink)
