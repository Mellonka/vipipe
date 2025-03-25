import argparse
import logging
import os

import gi
from scripts.sserver import start_server_on_thread
from utils.start_gst_pipeline import start_gst_pipeline

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # type: ignore

Gst.init(None)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


if not Gst.ElementFactory.find("zeromq_src"):
    raise RuntimeError("Плагин zeromq_src не найден. Проверьте путь к плагинам.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Запустить публикацию тестового видеопотока"
    )
    parser.add_argument(
        "--sub_address",
        type=str,
        help="Адрес сокета подключения",
        default="ipc:///tmp/test_pub.ipc",
    )
    parser.add_argument(
        "--sub_topic",
        type=str,
        help="Топик публикации",
        default="test_zeromq",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        help="Время ожидания буфера (мс)",
        default=60000,
    )
    parser.add_argument(
        "--hls_name",
        type=str,
        help="Название для HLS",
    )
    parser.add_argument(
        "--hls_port",
        type=int,
        help="Порт раздачи HLS",
        default=8081,
    )

    return parser.parse_args()


def main(
    sub_address: str, sub_topic: str, timeout: int, hls_name: str, hls_port: int = 8081
):
    os.makedirs("/app/tmp/" + hls_name, exist_ok=True)

    pipeline_str = (
        f"zeromq_src address={sub_address} topic={sub_topic} timeout={timeout} ! "
        "videoconvert ! x264enc ! "
        f"hlssink2 playlist-root=http://localhost:{hls_port}/tmp/{hls_name} playlist-length=5 "
        f"target-duration=5 max-files=10 location=/app/tmp/{hls_name}/segment_%05d.ts "
        f"playlist-location=/app/tmp/{hls_name}/playlist.m3u8"
    )
    logger.info("Команда gstreamer\n%s", pipeline_str)

    start_server_on_thread(hls_port)
    logger.info("Запустили сервер")

    logger.info(f"Подписываемся на сервер: {sub_address}, топик: {sub_topic}")
    logger.info(
        f"HLS доступен по адресу: http://localhost:{hls_port}/tmp/{hls_name}/playlist.m3u8"
    )
    start_gst_pipeline(pipeline_str)


if __name__ == "__main__":
    args = parse_args()
    logger.info(args)
    main(args.sub_address, args.sub_topic, args.timeout, args.hls_name, args.hls_port)
