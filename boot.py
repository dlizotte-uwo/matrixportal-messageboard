import board
from digitalio import DigitalInOut, Direction, Pull
up_button = DigitalInOut(board.BUTTON_UP)
up_button.direction = Direction.INPUT
up_button.pull = Pull.UP

if not up_button.value:
    import storage
    storage.remount("/", False)
    error_file = open("error_log.txt",'w')
else:
    error_file = None