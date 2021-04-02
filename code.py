import gc
import sys
from adafruit_matrixportal.matrixportal import Graphics,Network
import adafruit_minimqtt.adafruit_minimqtt as MQTT
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
import time
import board

gc.collect()

from display_modes import AirMode, WeatherMode, MessageMode, up_button

if not up_button.value:
    error_file = open("error_log.txt","aw")
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
network = Network(status_neopixel=board.NEOPIXEL)
graphics = Graphics(bit_depth=5)
display = graphics.display

# Rotate display if needed
display.rotation = 180

network.connect()
gc.collect()
print(f"Free memory after network connect: {gc.mem_free()}")

air_mode = AirMode()
message_mode = MessageMode()
weather_mode = WeatherMode(network=network,location=secrets["openweather_location"],token=secrets["openweather_token"])
current_mode = weather_mode

# Handle mqtt message to set display mode: On/Off Air, Messages, Weather
def display_mode(mqtt_client, topic, message):
    global current_mode
    print(f"New message on topic {topic}: {message}")
    if message == "OnAir":
        air_mode.set_submode("OnAir")
        current_mode = air_mode
    elif message == "OffAir":
        air_mode.set_submode("OffAir")
        current_mode = air_mode
    elif message == "Messages" and message_mode:
        message_mode.display_timestamp = 0
        message_mode.current_message = None
        message_mode.persist = True
        current_mode = message_mode
    elif message == "Weather":
        weather_mode.display_timestamp = time.monotonic()
        current_mode = weather_mode
    current_mode.update()
    display.show(current_mode)

# Handle display/message messages to add new message
def display_message(mqtt_client, topic, message):
    message_mode.json_message(mqtt_client, topic, message)

# ========= Set up MQTT ============

# Set socket for MQTT
MQTT.set_socket(socket, network._wifi.esp)

# Set up a MiniMQTT Client
mqtt_client = MQTT.MQTT(
    broker=secrets["mqtt_broker"],
    port=secrets["mqtt_port"],
    username=secrets["mqtt_username"],
    password=secrets["mqtt_passwd"],
    is_ssl=True,
)

#mqtt_client.enable_logger(logging,logging.DEBUG)

print(f"Attempting to connect to {mqtt_client.broker}")
mqtt_client.connect(keep_alive=60)

print("Subscribing to topics.")
mqtt_client.subscribe("display/#",qos=1)

# Dispatch to function for changing overall mode
mqtt_client.add_topic_callback("display/mode", display_mode)

# Dispatch directly to text_message object
mqtt_client.add_topic_callback("display/message", display_message)

gc.collect()

if current_mode:
    display.show(current_mode)
    gc.collect()

print(f"Free memory after show: {gc.mem_free()}")

while True:
    try:
        mqtt_client.loop(.01)
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
        #print(gc.mem_free())
    except BaseException as e:
        print(str(e))
        if error_file:
            sys.print_exception(e,error_file)
            error_file.close()
        raise e
