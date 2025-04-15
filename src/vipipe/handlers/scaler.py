from PIL.Image import Image


class Scaler:
    def process(self, image: Image, target_width: int, target_height: int):
        raise NotImplementedError
