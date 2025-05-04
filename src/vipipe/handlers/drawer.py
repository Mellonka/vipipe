from dataclasses import dataclass
from typing import Sequence

from PIL.Image import Image
from PIL.ImageDraw import Draw
from vipipe.transport.gstreamer.entity import ObjectMeta


@dataclass
class Drawer:
    color: tuple[int, int, int] = (0, 255, 0)
    text_color: tuple[int, int, int] = (255, 255, 255)
    thickness: int = 2

    def draw_bboxes(
        self,
        image: Image,
        bboxes: Sequence[Sequence[float | int]],
        labels: Sequence[str | None] | None = None,
        confs: Sequence[float | None] | None = None,
    ) -> None:
        draw = Draw(image)

        if confs is None or len(confs) != len(bboxes):
            confs = [None] * len(bboxes)

        if labels is None or len(labels) != len(bboxes):
            labels = [None] * len(bboxes)

        for bbox, label, conf in zip(bboxes, labels, confs):
            bbox = [int(b) for b in bbox]

            draw.rectangle([(bbox[0], bbox[1]), (bbox[2], bbox[3])], outline=self.color, width=self.thickness)

            if conf is not None:
                draw.text((bbox[0], bbox[1] - 15), f"{conf:.2f}", fill=self.text_color)

            if label is not None:
                draw.text((bbox[0], bbox[3] - 15), label, fill=self.text_color)

    def render_polygons(self, image: Image, polygons: Sequence[Sequence[float | int]]) -> None:
        draw = Draw(image)

        for polygon in polygons:
            draw.polygon([int(p) for p in polygon], outline=self.color, fill=None)

    def draw_objects(self, image: Image, objects: Sequence[ObjectMeta]) -> None:
        return self.draw_bboxes(
            image,
            [object["bbox"] for object in objects],
            [object["label"] for object in objects],
            [object["conf"] for object in objects],
        )
