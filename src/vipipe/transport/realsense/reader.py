from dataclasses import dataclass, field

import numpy as np
import pyrealsense2 as rs
from vipipe.transport.interface import ReaderABC


@dataclass
class RealsenseFrame:
    """Кадр с камеры RealSense"""

    color_image: np.ndarray | None
    """Цветное изображение"""

    depth_image: np.ndarray | None
    """Карта глубины"""

    infrared_image: np.ndarray | None
    """Инфракрасное изображение"""


@dataclass
class RealsenseConfig:
    """Конфигурация RealSense камеры"""

    width: int = 640
    """Ширина кадра"""

    height: int = 480
    """Высота кадра"""

    fps: int = 30
    """Частота кадров"""

    enable_color: bool = True
    """Включить цветную камеру"""

    enable_depth: bool = True
    """Включить датчик глубины"""

    enable_infrared: bool = False
    """Включить инфракрасную камеру"""


@dataclass
class RealsenseReader(ReaderABC[RealsenseFrame]):
    """Класс для чтения данных с камеры RealSense"""

    config: RealsenseConfig
    filters: list[rs.filter] = field(default_factory=list)

    pipeline: rs.pipeline = field(init=False)
    rs_config: rs.config = field(init=False)

    def __post_init__(self):
        self.pipeline = rs.pipeline()
        self.rs_config = rs.config()

        if self.config.enable_color:
            self.rs_config.enable_stream(
                rs.stream.color, self.config.width, self.config.height, rs.format.bgr8, self.config.fps
            )
        if self.config.enable_depth:
            self.rs_config.enable_stream(
                rs.stream.depth, self.config.width, self.config.height, rs.format.z16, self.config.fps
            )
        if self.config.enable_infrared:
            self.rs_config.enable_stream(
                rs.stream.infrared, self.config.width, self.config.height, rs.format.y8, self.config.fps
            )

    def start(self) -> None:
        """Запуск потока данных с камеры"""
        self.pipeline.start(self.rs_config)

    def stop(self) -> None:
        """Остановка потока данных с камеры"""
        self.pipeline.stop()

    def read(self) -> RealsenseFrame:
        """Чтение кадра с камеры

        Returns:
            RealsenseFrame: Кадр с цветным изображением и/или картой глубины
        """
        frames = self.pipeline.wait_for_frames()

        color_image = None
        if self.config.enable_color:
            color_frame = frames.get_color_frame()
            if color_frame:
                color_image = np.asanyarray(color_frame.get_data())

        depth_image = None
        if self.config.enable_depth:
            depth_frame = frames.get_depth_frame()
            if depth_frame:
                depth_image = np.asanyarray(depth_frame.get_data())
                for filter in self.filters:
                    depth_image = filter.process(depth_image)

        infrared_image = None
        if self.config.enable_infrared:
            infrared_frame = frames.get_infrared_frame()
            if infrared_frame:
                infrared_image = np.asanyarray(infrared_frame.get_data())

        return RealsenseFrame(color_image=color_image, depth_image=depth_image, infrared_image=infrared_image)
