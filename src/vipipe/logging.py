import logging

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s:%(filename)s:%(lineno)d - %(levelname)s - %(message)s",
)


def get_logger(name: str, level: int = logging.DEBUG) -> logging.Logger:
    """
    Получает логгер с заданным именем.

    Args:
        name: Имя логгера
        level: Уровень логирования (по умолчанию DEBUG)

    Returns:
        Логгер с заданным именем
    """

    logger = logging.getLogger(name)
    logger.setLevel(level)
    return logger
