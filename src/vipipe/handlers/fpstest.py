import time
from dataclasses import dataclass, field
from typing import Optional
from collections import deque

from vipipe.handlers.base import HandlerABC
from vipipe.logging import get_logger
from vipipe.transport.gstreamer import BufferMessage, GstMessage

logger = get_logger("vipipe.handler.fpstest")


@dataclass
class FPSCounter:
    """Класс для подсчета FPS (кадров в секунду)."""

    window_size: int = 500
    timestamps: deque[float] = field(default_factory=deque)
    last_fps_report_time: float = field(default_factory=time.time)
    report_interval: float = 1.0

    def update(self) -> None:
        """Обновляет список временных меток для расчета FPS."""
        current_time = time.monotonic()
        self.timestamps.append(current_time)

        # Ограничиваем размер списка временных меток
        while len(self.timestamps) > self.window_size:
            self.timestamps.popleft()

    def get_fps(self) -> float:
        """Рассчитывает текущий FPS на основе временных меток."""
        if len(self.timestamps) < 2:
            return 0.0

        # Рассчитываем FPS на основе разницы между первой и последней временной меткой
        time_diff = self.timestamps[-1] - self.timestamps[0]
        if time_diff <= 0:
            return 0.0

        return (len(self.timestamps) - 1) / time_diff

    def report_if_needed(self) -> None:
        """Выводит информацию о FPS с заданным интервалом."""
        current_time = time.time()
        if current_time - self.last_fps_report_time >= self.report_interval:
            fps = self.get_fps()
            logger.info(f"Текущий FPS: {fps:.2f}")
            self.last_fps_report_time = current_time


class FPSTestHandler(HandlerABC):
    """Обработчик для измерения FPS видеопотока."""

    def on_startup(self) -> None:
        """Инициализация при запуске обработчика."""
        self.fps_counter = FPSCounter()
        logger.info("FPS тестовый обработчик запущен")

    def handle_buffer_message(self, message: BufferMessage) -> Optional[GstMessage]:
        """Обрабатывает буферное сообщение и обновляет счетчик FPS."""
        # Обновляем счетчик FPS
        self.fps_counter.update()
        self.fps_counter.report_if_needed()

        # Пропускаем сообщение дальше без изменений
        return message

    def on_shutdown(self) -> None:
        """Действия при завершении работы обработчика."""
        logger.info(f"FPS тестовый обработчик завершен. Средний FPS: {self.fps_counter.get_fps():.2f}")
