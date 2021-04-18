import gc
import sys
from digitalio import DigitalInOut, Direction, Pull
import busio
import adafruit_requests as requests
import framebufferio
import rgbmatrix
from displayio import release_displays
import adafruit_minimqtt.adafruit_minimqtt as MQTT
import neopixel
from adafruit_esp32spi import adafruit_esp32spi
from adafruit_esp32spi import adafruit_esp32spi_wifimanager
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
import time
import board

from file_handler import FileHandler
import adafruit_logging as logging

gc.collect()

from display_modes import AirMode, WeatherMode, MessageMode, up_button

led = DigitalInOut(board.L)
led.direction = Direction.OUTPUT
led.value = False

if not up_button.value:
    error_file = open("error_log.txt", "w")
    print("Opened log file.",file=error_file)
    error_file.flush()
else:
    error_file = None

gc.collect()

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

# --- Display setup ---
release_displays()
matrix = rgbmatrix.RGBMatrix(
    width=64, bit_depth=5,
    rgb_pins=[board.MTX_R1, board.MTX_G1, board.MTX_B1,
              board.MTX_R2, board.MTX_G2, board.MTX_B2],
    addr_pins=[board.MTX_ADDRA, board.MTX_ADDRB,
               board.MTX_ADDRC, board.MTX_ADDRD],
    clock_pin=board.MTX_CLK,
    latch_pin=board.MTX_LAT,
    output_enable_pin=board.MTX_OE
)
display = framebufferio.FramebufferDisplay(matrix)
# Rotate display if needed
display.rotation = 180

# --- Network Setup ---
# If you are using a board with pre-defined ESP32 Pins:
esp32_cs = DigitalInOut(board.ESP_CS)
esp32_ready = DigitalInOut(board.ESP_BUSY)
esp32_reset = DigitalInOut(board.ESP_RESET)
spi = busio.SPI(board.SCK, board.MOSI, board.MISO)
esp = adafruit_esp32spi.ESP_SPIcontrol(spi, esp32_cs, esp32_ready, esp32_reset)

"""Use below for Most Boards"""
status_light = neopixel.NeoPixel(
    board.NEOPIXEL, 1, brightness=0.2
)
requests = adafruit_esp32spi_wifimanager.ESPSPI_WiFiManager(esp, secrets, status_light)
requests.connect()

gc.collect()

print(f"Free memory after network connect: {gc.mem_free()}")

air_mode = AirMode()
message_mode = MessageMode()
weather_mode = WeatherMode(network=requests,
                           location=secrets["openweather_location"],
                           token=secrets["openweather_token"])
current_mode = weather_mode

# Handle mqtt message to set display mode: On/Off Air, Messages, Weather
def display_mode(mqtt_client, topic, message):
    global current_mode
    print(f"New message on topic {topic}: {message}")
    if message in air_mode.submodes:
        air_mode.set_submode(message)
        current_mode = air_mode
    elif message == "Messages" and message_mode:
        message_mode.display_timestamp = 0
        message_mode.current_message = None
        message_mode.persist = True
        current_mode = message_mode
    elif message == "Weather":
        weather_mode.display_timestamp = time.monotonic()
        current_mode = weather_mode
        message_mode.persist = False
    # current_mode.update()
    display.show(current_mode)

# Handle display/message messages to add new message
def display_message(mqtt_client, topic, message):
    message_mode.json_message(mqtt_client, topic, message)

# ========= Set up MQTT ============

# Set socket for MQTT
#MQTT.set_socket(socket, network._wifi.esp)
MQTT.set_socket(socket, esp)

# Set up a MiniMQTT Client
mqtt_client = MQTT.MQTT(
    broker=secrets["mqtt_broker"],
    port=secrets["mqtt_port"],
    username=secrets["mqtt_username"],
    password=secrets["mqtt_passwd"],
    is_ssl=True,
    client_id=secrets["mqtt_client_id"]
)

mqtt_client.enable_logger(logging,log_level=logging.INFO)
if error_file:
    mqtt_client.logger.addHandler(FileHandler(error_file))

print(f"Attempting to connect to {mqtt_client.broker}")
mqtt_client.connect(clean_session=False)
if error_file:
    print("Connected at %s\n" % time.monotonic())
    error_file.write("Connected at %s\n" % time.monotonic())
    error_file.flush()

print("Subscribing to topics.")
mqtt_client.subscribe("display/#", qos=1)

# Dispatch to function for changing overall mode
mqtt_client.add_topic_callback("display/{}/mode".format(secrets['matrix_subtopic']), display_mode)
mqtt_client.add_topic_callback("display/mode", display_mode)

# Dispatch directly to text_message object
mqtt_client.add_topic_callback("display/{}/message".format(secrets['matrix_subtopic']), display_message)
mqtt_client.add_topic_callback("display/message", display_message)

gc.collect()

if current_mode:
    display.show(current_mode)
    gc.collect()

print(f"Free memory after show: {gc.mem_free()}")

while True:
    try:
        mqtt_client.loop(.01)
        if not up_button.value:
            if error_file:
                error_file.flush()
        if current_mode:
            if not current_mode.update():
                # Current mode returns False if it's "done"
                if (current_mode == message_mode) and message_mode.persist:
                    message_mode.display_timestamp = 0
                    message_mode.current_message = None
                elif (current_mode != message_mode) and message_mode:
                    # Switch to messages
                    current_mode = message_mode
                    current_mode.update()
                else:
                    # Switch to weather
                    weather_mode.display_timestamp = time.monotonic()
                    current_mode = weather_mode
                    current_mode.update()
                display.show(current_mode)
                gc.collect()
        # print(gc.mem_free())
    except MQTT.MMQTTException as e:
        led.value = True
        sys.print_exception(e)
        if error_file:
            error_file.write("MMQTT Exception: ")
            sys.print_exception(e, error_file)
            error_file.write("Trying to reconnect...")
            error_file.flush()
        try:
            mqtt_client.reconnect(qos=1)
        except BaseException as e:
            sys.print_exception(e)
            if error_file:
                sys.print_exception(e, error_file)
                error_file.close()
            raise e
    except RuntimeError as e:
        led.value = True
        sys.print_exception(e)
        if error_file:
            sys.print_exception(e, error_file)
            error_file.write("Timestamp: %s\n" % time.monotonic())
            error_file.write("Time since ping: {}\n".format(time.monotonic() - mqtt_client._timestamp))
            error_file.write("Trying to reconnect...\n")
            error_file.flush()
        try:
            # Try just reconnecting mqtt_client
            mqtt_client.reconnect(qos=1)
            if error_file:
                error_file.write("Reconnected at %s\n" % time.monotonic())
                error_file.flush()
        except BaseException as e:
            sys.print_exception(e)
            if error_file:
                sys.print_exception(e, error_file)
                error_file.write("Resetting ESP32\n")
                error_file.flush()
            # Reset the ESP32
            requests.reset()
            requests.connect()
            mqtt_client.reconnect(qos=1)
    except BaseException as e:
        led.value = True
        sys.print_exception(e)
        if error_file:
            sys.print_exception(e, error_file)
            error_file.close()
        raise e