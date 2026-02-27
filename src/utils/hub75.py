import os
import platform

from PIL import Image
import pygame
from pygame.image import tobytes
from pygame.time import get_ticks

if platform.system() != "Darwin":
    from rgbmatrix import graphics, RGBMatrix, RGBMatrixOptions
    import rgbmatrix
else:
    from RGBMatrixEmulator import graphics, RGBMatrix, RGBMatrixOptions
    import RGBMatrixEmulator
from typing import Union

matrix: RGBMatrix = None
offscreen_canvas: Union["RGBMatrixEmulator.emulation.canvas.Canvas","RGBMatrix.Canvas"] = None


def create_rgbmatrix(display_type: str = None) -> Union["RGBMatrixEmulator.RGBMatrix", "rgbmatrix.RGBMatrix"]:
    options = RGBMatrixOptions()

    options.brightness = 100
    options.disable_hardware_pulsing = False
    options.drop_privileges = False
    options.hardware_mapping = "regular"
    options.led_rgb_sequence = "RGB"
    options.pwm_bits = 11
    options.pwm_lsb_nanoseconds = 130

    if display_type is None:
        display_type = os.environ.get("LED_DISPLAY_TYPE", "large")

    if platform.system() == "Darwin":
        options.rows = 256
        options.cols = 192
        options.chain_length = 1
        options.parallel = 1
        options.gpio_slowdown = 5
        options.multiplexing = 1
        options.pixel_mapper_config = ""
        options.row_address_type = 0
    elif display_type == "large":
        options.rows = 32
        options.cols = 64
        options.chain_length = 8
        options.parallel = 3
        options.gpio_slowdown = 5
        options.multiplexing = 1
        options.panel_type = ""
        options.pixel_mapper_config = "U-mapper"
        options.row_address_type = 0
    else:  # mini
        options.rows = 64
        options.cols = 128
        options.chain_length = 2
        options.parallel = 3
        options.gpio_slowdown = 5
        options.multiplexing = 0
        options.panel_type = ""
        options.pixel_mapper_config = ""
        options.row_address_type = 3

    return RGBMatrix(options=options)


def init(display_type: str = None) -> None:
    global matrix, offscreen_canvas

    if display_type is None:
        display_type = os.environ.get("LED_DISPLAY_TYPE", "large")

    matrix = create_rgbmatrix(display_type)
    offscreen_canvas = matrix.CreateFrameCanvas()
    font = graphics.Font()
    font.LoadFont("7x13.bdf")
    textColor = graphics.Color(255, 255, 0)
    pos = offscreen_canvas.width - 40
    my_text = "HELLO"
    graphics.DrawText(offscreen_canvas, font, pos, 10, textColor, my_text)
    offscreen_canvas = matrix.SwapOnVSync(offscreen_canvas)

last_image: bytes = b''
update_count = 0
total_time = 1
display_type_cache: str = None
def update(screen: pygame.Surface) -> None:
    global last_image, total_time, update_count, offscreen_canvas, display_type_cache

    # Skip update if hub75 not initialized (e.g., in tests)
    if matrix is None:
        return

    pixels = tobytes(screen, "RGB")
    if pixels == last_image:
        return
    last_image = pixels
    img = Image.frombytes("RGB", (screen.get_width(), screen.get_height()), pixels)

    if platform.system() != "Darwin":
        # Transpose (rotate 90) is faster than rotate(270) and avoids reallocation
# mypy: disable-error-code=attr-defined
        img = img.transpose(Image.ROTATE_270)

        # For mini display, apply panel row/column swap in software
        if display_type_cache is None:
            display_type_cache = os.environ.get("LED_DISPLAY_TYPE", "large")

        if display_type_cache == "mini":
            # Swap top and bottom rows, then rotate 180 degrees
            w, h = img.size
            band_height = h // 3

            # Split into 3 bands
            top = img.crop((0, 0, w, band_height))
            middle = img.crop((0, band_height, w, 2 * band_height))
            bottom = img.crop((0, 2 * band_height, w, h))

            # Swap top and bottom
            img = Image.new(img.mode, (w, h))
            img.paste(bottom, (0, 0))
            img.paste(middle, (0, band_height))
            img.paste(top, (0, 2 * band_height))

            # Rotate 180 degrees
            img = img.rotate(180, Image.NEAREST)

    start = get_ticks()
    offscreen_canvas.SetImage(img, 0, 0)
    offscreen_canvas = matrix.SwapOnVSync(offscreen_canvas)
    total_time += get_ticks() - start
    update_count += 1