from vipipe.logging import get_logger
from vipipe.handlers.fpstest import FPSTestHandler
from vipipe.transport.gstreamer import GstReader
from vipipe.transport.zeromq import ZeroMQReader
from vipipe.transport.zeromq.utils.cli import parse_zmq_reader_config_cli

logger = get_logger("vipipe.handler.metadetect.fpstest")


def main():
    reader_config = parse_zmq_reader_config_cli()

    logger.info(f"Чтение из: {reader_config.address}")

    reader = GstReader(ZeroMQReader(reader_config))
    FPSTestHandler(reader=reader, writer=None).run()
    logger.info("Работа FPS теста завершена")


if __name__ == "__main__":
    main()
