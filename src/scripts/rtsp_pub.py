import argparse
import logging
import os

import gi
from utils.start_gst_pipeline import start_gst_pipeline

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # type: ignore

Gst.init(None)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


if not Gst.ElementFactory.find("zeromq_sink"):
    raise RuntimeError("Плагин zeromq_sink не найден. Проверьте путь к плагинам.")


def parse_args():
    parser = argparse.ArgumentParser(description="Запустить публикацию RTSP потока")
    parser.add_argument(
        "--pub_address",
        type=str,
        help="Адрес сокета",
        default="ipc:///tmp/test_pub.ipc",
    )
    parser.add_argument(
        "--pub_topic",
        type=str,
        help="Топик публикации",
        default="test_zeromq",
    )
    parser.add_argument(
        "--rtsp_address",
        type=str,
        help="Адрес RTSP потока",
    )

    return parser.parse_args()


def main(pub_address: str, pub_topic: str, rtsp_address: str):
    pipeline_str = (
        f"rtspsrc location={rtsp_address} latency=0 ! rtph264depay ! h264parse ! "
        "avdec_h264 ! videoconvert ! "
        f"zeromq_sink address={pub_address} topic={pub_topic}"
    )
    logger.info("Команда gstreamer\n%s", pipeline_str)

    logger.info(f"Запуск сервера: {pub_address}, топик: {pub_topic}")
    start_gst_pipeline(pipeline_str)

    # Удаляем временный IPC файл при выходе
    if os.path.exists(pub_address):
        try:
            os.remove(pub_address)
            logger.info(f"Удален IPC файл: {pub_address}")
        except:
            pass


if __name__ == "__main__":
    args = parse_args()
    logger.info(args)
    main(args.pub_address, args.pub_topic, args.rtsp_address)
