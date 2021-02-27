import gc
print("Free memory: %d" % gc.mem_free())
from adafruit_matrixportal.matrixportal import Graphics,Network
gc.collect()
import adafruit_minimqtt.adafruit_minimqtt as MQTT
gc.collect()
import adafruit_esp32spi.adafruit_esp32spi_socket as socket
gc.collect()
import time
import board
import terminalio
gc.collect()
# import adafruit_logging as logging
from display_modes import AirMode, WeatherMode, MessageMode
gc.collect()

print("Free memory after imports: %d" % gc.mem_free())

# Get wifi details and more from a secrets.py file
try:
    from secrets import secrets
except ImportError:
    print("WiFi secrets are kept in secrets.py, please add them there!")
    raise

# --- Display setup ---
network = Network(status_neopixel=board.NEOPIXEL)
gc.collect()
graphics = Graphics(bit_depth=5)
display = graphics.display
gc.collect()

# Rotate display if needed
display.rotation = 180

network.connect()
gc.collect()
print("Free memory after network connect: %d" % gc.mem_free())

font = terminalio.FONT

air_mode = AirMode()
message_mode = MessageMode(font=font)
weather_mode = WeatherMode(font=font,network=network,
    location=secrets["openweather_location"],token=secrets["openweather_token"])
current_mode = weather_mode

gc.collect()

# Handle mqtt message to set display mode: On/Off Air, Messages, Weather
def display_mode(mqtt_client, topic, message):
    global current_mode
    print("New message on topic {0}: {1}".format(topic, message))
    if message == "OnAir":
        air_mode.set_submode("OnAir")
        current_mode = air_mode
    elif message == "OffAir":
        air_mode.set_submode("OffAir")
        current_mode = air_mode
    elif message == "Messages":
        current_mode = message_mode
    elif message == "Weather":
        current_mode = weather_mode
    display.show(current_mode)

# Handle display/message messages to add new message
# Switch display mode to Messages automatically
def display_message(mqtt_client, topic, message):
    global current_mode
    message_mode.json_message(mqtt_client, topic, message)
    if not current_mode == message_mode:
        gc.collect()
        current_mode = message_mode
        display.show(current_mode)


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

# mqtt_client.enable_logger(logging,logging.DEBUG)

print("Attempting to connect to %s" % mqtt_client.broker)
mqtt_client.connect(keep_alive=60)

print("Subscribing to topics.")
mqtt_client.subscribe("display/#")

# Dispatch to function for changing overall mode
mqtt_client.add_topic_callback("display/mode", display_mode)

# Dispatch directly to text_message object
mqtt_client.add_topic_callback("display/message", display_message)

gc.collect()

print("Free memory after collect: %d" % gc.mem_free())

if current_mode:
    display.show(current_mode)
    gc.collect()

while True:
    try:
        mqtt_client.loop(.001)
        if current_mode:
            if not current_mode.update():
                if message_mode: # If there are messages
                    current_mode = message_mode
                else: # If there are no messages
                    current_mode = weather_mode
                display.show(current_mode)
                gc.collect()
        #print(gc.mem_free())
    except (MQTT.MMQTTException, RuntimeError) as e:
        print(e)
        mqtt_client.reconnect()