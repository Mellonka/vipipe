import argparse
import http.server
import logging
import threading

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def start_server(port: int):
    httpd = http.server.HTTPServer(("", port), http.server.SimpleHTTPRequestHandler)

    logger.info("Запускаем сервер")
    httpd.serve_forever()


def start_server_on_thread(port: int):
    server_thread = threading.Thread(target=start_server, args=(port,), daemon=True)
    server_thread.start()


def parse_args():
    parser = argparse.ArgumentParser(description="Запустить сервер для раздачи файлов")
    parser.add_argument("--port", type=int, help="Порт", default=8081)

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    start_server(args.port)
