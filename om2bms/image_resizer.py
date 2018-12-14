"""
Resizes BG to 256x256
"""
from PIL import Image


def black_background_thumbnail(path_to_image, thumbnail_size=(256, 256)):
    """
    Resizes image to 256x256. Add black borders if image is widescreen.
    """
    background = Image.new('RGB', thumbnail_size, "black")
    source_image = Image.open(path_to_image).convert("RGB")
    # if source_image.verify():
    source_image.thumbnail(thumbnail_size)
    (w, h) = source_image.size
    background.paste(source_image, ((thumbnail_size[0] - w) // 2, (thumbnail_size[1] - h) // 2))

    background.save(path_to_image)
    background.close()
