import logging

import gi

gi.require_version("Gst", "1.0")
from gi.repository import GLib, Gst  # type: ignore

Gst.init(None)

logger = logging.getLogger(__name__)


def start_gst_pipeline(pipeline_str):
    pipeline = Gst.parse_launch(pipeline_str)
    pipeline.set_state(Gst.State.PLAYING)

    try:
        GLib.MainLoop().run()
    except KeyboardInterrupt:
        logger.info("Остановка GST по запросу пользователя")

    pipeline.set_state(Gst.State.NULL)
    logger.info("Пайплайн GST остановлен")
