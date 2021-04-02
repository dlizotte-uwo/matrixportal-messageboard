import board
from digitalio import DigitalInOut, Direction, Pull
up_button = DigitalInOut(board.BUTTON_UP)
up_button.direction = Direction.INPUT
up_button.pull = Pull.UP

if not up_button.value:
    import storage
    storage.remount("/", False)
    led = DigitalInOut(board.L)
    led.direction = Direction.OUTPUT
    led.value = True