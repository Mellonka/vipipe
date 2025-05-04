import argparse

import zmq

from ..reader import ZeroMQReaderConfig
from ..writer import ZeroMQWriterConfig


def parse_zmq_config_cli() -> tuple[ZeroMQReaderConfig, ZeroMQWriterConfig]:
    """Парсит конфигурацию ZeroMQReader из командной строки"""

    parser = argparse.ArgumentParser(description="ZeroMQ reader config")
    parser.add_argument("--reader_address", type=str, required=True, help="Socket address")
    parser.add_argument("--reader_socket-type", type=str, default="SUB", choices=["SUB", "PULL"], help="Socket type")
    parser.add_argument("--reader_topic", type=str, default="", help="Topic for SUB socket")
    parser.add_argument("--reader_buffer-length", type=int, default=10, help="Buffer length")
    parser.add_argument("--reader_buffer-size-oc", type=int, default=1024 * 1024 * 30, help="Buffer size in OS")
    parser.add_argument("--reader_read-timeout", type=int, default=100, help="Read timeout in ms")
    parser.add_argument("--reader_conflate", action="store_true", help="Conflate messages")
    parser.add_argument("--reader_dontwait", action="store_true", help="Non-blocking read")

    parser.add_argument("--writer_address", type=str, required=True, help="Socket address")
    parser.add_argument("--writer_socket-type", type=str, default="PUB", choices=["PUB", "PUSH"], help="Socket type")
    parser.add_argument("--writer_buffer-length", type=int, default=10, help="Buffer length")
    parser.add_argument("--writer_buffer-size-oc", type=int, default=1024 * 1024 * 30, help="Buffer size in OS")
    parser.add_argument("--writer_send-timeout", type=int, default=100, help="Send timeout in ms")
    parser.add_argument("--writer_immediate", action="store_true", help="Immediate send")
    parser.add_argument("--writer_conflate", action="store_true", help="Conflate messages")
    parser.add_argument("--writer_linger", type=int, default=500, help="Linger time in ms")
    parser.add_argument("--writer_dontwait", action="store_true", help="Non-blocking send")

    args = parser.parse_args()

    return ZeroMQReaderConfig(
        address=args.reader_address,
        socket_type=zmq.SocketType[args.reader_socket_type],
        topic=args.reader_topic,
        buffer_length=args.reader_buffer_length,
        buffer_size_os=args.reader_buffer_size_oc,
        read_timeout=args.reader_read_timeout,
        conflate=args.reader_conflate,
        dontwait=args.reader_dontwait,
    ), ZeroMQWriterConfig(
        address=args.writer_address,
        socket_type=zmq.SocketType[args.writer_socket_type],
        buffer_length=args.writer_buffer_length,
        buffer_size_os=args.writer_buffer_size_oc,
        send_timeout=args.writer_send_timeout,
        immediate=args.writer_immediate,
        conflate=args.writer_conflate,
        linger=args.writer_linger,
        dontwait=args.writer_dontwait,
    )
