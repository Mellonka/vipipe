import argparse
import os

import gi
from utils.start_gst_pipeline import start_gst_pipeline

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # type: ignore

Gst.init(None)


if not Gst.ElementFactory.find("zeromq_sink"):
    raise RuntimeError("Плагин zeromq_sink не найден. Проверьте путь к плагинам.")


def parse_args():
    parser = argparse.ArgumentParser(
        description="Запустить публикацию тестового видеопотока"
    )
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

    return parser.parse_args()


def main(pub_address: str, pub_topic: str):
    pipeline_str = (
        "videotestsrc is-live=true ! video/x-raw,width=640,height=480,framerate=30/1 ! "
        f"videoconvert ! zeromq_sink address={pub_address} topic={pub_topic}"
    )

    print(f"Запуск сервера: {pub_address}, топик: {pub_topic}")
    start_gst_pipeline(pipeline_str)

    # Удаляем временный IPC файл при выходе
    if os.path.exists(pub_address):
        try:
            os.remove(pub_address)
            print(f"Удален IPC файл: {pub_address}")
        except:
            pass


if __name__ == "__main__":
    args = parse_args()
    print(args)
    main(args.pub_address, args.pub_topic)
