from dataclasses import dataclass
from typing import Sequence

from PIL.Image import Image
from PIL.ImageDraw import Draw


@dataclass
class Drawer:
    color: tuple[int, int, int] = (0, 255, 0)
    text_color: tuple[int, int, int] = (255, 255, 255)
    thickness: int = 2

    def process_bboxes(self, image: Image, bboxes: Sequence, confs: Sequence | None = None) -> None:
        draw = Draw(image)

        if confs is None or len(confs) != len(bboxes):
            confs = [None] * len(bboxes)

        for bbox, conf in zip(bboxes, confs):
            bbox = [int(b) for b in bbox]

            draw.rectangle([(bbox[0], bbox[1]), (bbox[2], bbox[3])], outline=self.color, width=self.thickness)

            if conf is not None:
                draw.text(
                    (bbox[0], bbox[1] - 15),
                    f"{conf:.2f}",
                    fill=self.text_color,
                )

    def process_polygons(self, image: Image, polygons: list) -> None:
        raise NotImplementedError
