from adafruit_display_text.label import Label
from adafruit_bitmap_font import bitmap_font
import board
from digitalio import DigitalInOut, Direction, Pull
import displayio
import json
import time
import gc
from terminalio import FONT
import os

down_button = DigitalInOut(board.BUTTON_DOWN)
down_button.direction = Direction.INPUT
down_button.pull = Pull.UP

up_button = DigitalInOut(board.BUTTON_UP)
up_button.direction = Direction.INPUT
up_button.pull = Pull.UP

class AirMode(displayio.Group):

    def __init__(self,*):
        super().__init__(max_size=3)

        self.mode = None
        self.R = 0
        self.G = 0
        self.B = 0
        self._bg_group = displayio.Group(max_size=1)

        self.font = bitmap_font.load_font("fonts/BellotaText-Bold-21_DJL.bdf")
        self.font.load_glyphs(b"ONAIRF")
        self.Line1 = Label(self.font, max_glyphs=3,anchored_position=(32,8),
            anchor_point = (0.5,0.5))
        self.Line2 = Label(self.font, max_glyphs=3,anchored_position=(32,8+17),
            anchor_point = (0.5,0.5))

        self.append(self._bg_group)
        self.append(self.Line1)
        self.append(self.Line2)

    def set_submode(self,mode):
        if self.mode == mode:
            return
        if not mode in ("OnAir","OffAir"):
            print("AirMode - unrecognized mode {}".format(mode))
            return
        if self._bg_group:
            self._bg_group.pop()
            gc.collect()
        if mode == "OnAir":
            bg_file = open("bmps/Wings_FF0000.bmp","rb")
            self.R = 0xFF
            self.G = 0x00
            self.B = 0x00
            self.Line1.text = "ON"
            self.Line2.text = "AIR"
        elif mode == "OffAir":
            bg_file = open("bmps/Wings_DD8000.bmp","rb")
            self.R = 0xDD
            self.G = 0x80
            self.B = 0x00
            self.Line1.text = "OFF"
            self.Line2.text = "AIR"
        self._bg_group.append(displayio.TileGrid(
            displayio.OnDiskBitmap(bg_file),pixel_shader=displayio.ColorConverter()))
        self.update()
        self.mode = mode
        gc.collect()

    def update(self):
        if not down_button.value:
            # Return False if "done" as indicated by down_button
            while not down_button.value:
                pass
            return False
        intensity = 1 - 0.925*abs(1 - (time.monotonic() % 4)/2)
        update_color = int(intensity*self.R) << 16 | int(intensity*self.G) << 8 | int(intensity*self.B)
        self.Line1.color = update_color
        self.Line2.color = update_color
        return True


class WeatherMode(displayio.Group):

    def _temp_color(temp):
        if temp <= -10:
            return 0x2068B0
        elif temp < -0.05:
            return 0x5050F8
        elif temp < 0.05:
            return 0xF8F8F8
        elif temp < 10:
            return 0xFFE020
        elif temp < 20:
            return 0xFF9000
        elif temp < 30:
            return 0xFF4000
        else:
            return 0xFF0000


    def __init__(self,*,network=None,location=None,token=None):
        super().__init__(max_size=3)

        self.WEATHER_URL = "http://api.openweathermap.org/data/2.5/weather?q={}&units=metric&appid={}"\
            .format(location,token)

        now = time.monotonic()

        self.data_timeout = 600
        self.data_timestamp = 0
        self.wdata = {}
        self.pressure = []
        self.pressure_slope = None

        self.network = network

        self.font = FONT

        self.symfont = bitmap_font.load_font("fonts/6x10_DJL.bdf")
        self.symfont.load_glyphs('°Ckph%r↑↗→↘↓↙←↖↥↧\u33A9\u00AD ')

        bb = self.font.get_bounding_box()
        (f_w,f_h) = bb[0], bb[1]

        self._bg_group = displayio.Group(max_size=1)
        self.weather1 = displayio.Group(max_size=6)

        UNIT_COLOR = 0x202020
        TEXT_COLOR = 0x301040
        WIND_COLOR = 0x78E078
        self.WDIR_COLOR = 0xF08070

        self.display_timestamp = now
        self.display_timeout = 5
        self.display_mode = 0
        self.display_modes = 3

        self.temp_l = Label(self.font,max_glyphs=5,color=0x5050F8,
            anchored_position=(64-2*f_w,-3),anchor_point=(1.0,0.0),line_spacing=1.0)
        self.temp_unit_l = Label(self.symfont,max_glyphs=2,color=UNIT_COLOR,
            anchored_position=(64,1),anchor_point=(1.0,0.0),line_spacing=1.0)
        self.windspeed_l = Label(self.font,max_glyphs=3,color=WIND_COLOR,
            anchored_position=(64-(4*f_w)+4,15),anchor_point=(1.0,0.5),line_spacing=1.0)
        self.windspeed_unit_l = Label(self.symfont,max_glyphs=3,color=UNIT_COLOR,
            anchored_position=(64-(3*f_w/2)+2,17),anchor_point=(1.0,0.5),line_spacing=1.0)
        self.winddir_l = Label(self.symfont,max_glyphs=1,color=self.WDIR_COLOR,
            anchored_position=(64,16),anchor_point=(1.0,0.5),line_spacing=1.0)
        self.text_l = Label(self.font,max_glyphs=12,color=TEXT_COLOR,
            anchored_position=(1,32),anchor_point=(0.0,1.0),line_spacing=1.0)
        self.weather1.append(self.temp_l)
        self.weather1.append(self.temp_unit_l)
        self.weather1.append(self.windspeed_l)
        self.weather1.append(self.windspeed_unit_l)
        self.weather1.append(self.winddir_l)
        self.weather1.append(self.text_l)
        self.append(self._bg_group)
        self.append(self.weather1)

    def update(self):
        now = time.monotonic()
        if not self.data_timestamp or now - self.data_timestamp > self.data_timeout:
            try:
                self.wdata = self.network.fetch_data(self.WEATHER_URL,json_path=([],))
                print("Response is", self.wdata)
                self.data_timestamp = now
            except RuntimeError as e:
                print("Some error occurred getting weather! -", e)
                self.data_timestamp = (now - self.data_timeout) + 30
                if not self.wdata:
                    return True
            self.temp_l.color = WeatherMode._temp_color(self.wdata["main"]["temp"])
            self.temp_l.text = u"{: 2.1f}".format(self.wdata["main"]["temp"])
            self.temp_unit_l.text = "°C"
            self.text_l.text = self.wdata["weather"][0]["main"]

            self.pressure.append(self.wdata["main"]["pressure"])
            if len(self.pressure) > 6:
                self.pressure.pop(0)
            elif len(self.pressure) >= 2:
                n = len(self.pressure)
                mean_press = sum(self.pressure) / n
                self.pressure_slope = sum([(i - (n-1)/2) * (self.pressure[i] - mean_press) for i in range(n)])
            else:
                self.pressure_slope = None
            print("Pressure readings: {}".format(self.pressure))
            print("Pressure slope: {}".format(self.pressure_slope))

            icon = self.wdata["weather"][0]["icon"]
            bg_file = open("bmps/weather/{}.bmp".format(icon),"rb")
            while self._bg_group:
                self._bg_group.pop()
                gc.collect()
            self._bg_group.append(displayio.TileGrid(
                displayio.OnDiskBitmap(bg_file),x=1,y=1,
                pixel_shader=displayio.ColorConverter()))
            gc.collect()

        if not down_button.value:
            # Wait for button release
            while not down_button.value:
                pass
            # Avoid allocating new list?? idk...
            while self.pressure:
                self.pressure.pop()
            self.pressure.append(self.wdata["main"]["pressure"])
            self.pressure_slope = None
            gc.collect()

        if now - self.display_timestamp > self.display_timeout:
            self.display_timestamp = now
            self.display_mode = (self.display_mode + 1) % self.display_modes
            if self.display_mode == 0:
                return False

        if self.display_mode == 0:
            self.windspeed_l.text = "{:3.0f} ".format(self.wdata["wind"]["speed"]*3.6) # m/s to kph
            self.windspeed_unit_l.text = "kph"
            if self.wdata["wind"]["speed"] > 0:
                didx = round(float(self.wdata["wind"]["deg"]) / (360/8)) % 8
                self.winddir_l.text = '↓↙←↖↑↗→↘'[didx]
            else:
                self.winddir_l.text = ""
            self.winddir_l.color = self.WDIR_COLOR
        elif self.display_mode == 1:
            self.windspeed_l.text = "{:2.0f} ".format(self.wdata["main"]["humidity"])
            self.windspeed_unit_l.text = "%rh"
            self.winddir_l.text = ""
        else:
            self.windspeed_l.text = "{:4.0f}".format(self.wdata["main"]["pressure"])
            self.windspeed_unit_l.text = " h\u33A9"
            if self.pressure_slope is None:
                self.winddir_l.text = ""
            elif self.pressure_slope > 0.1:
                self.winddir_l.text = "↥"
                self.winddir_l.color = 0x40C000
            elif self.pressure_slope < -0.1:
                self.winddir_l.text = "↧"
                self.winddir_l.color = 0xC04000
            else:
                self.winddir_l.text = "\u00AD"
                self.winddir_l.color = 0x444444
        return True


class MessageMode(displayio.Group):

    def _justify(strings):
        new = "\n".join(["{:>10}".format(s) for s in strings.split('\n')])
        return new

    def __init__(self,msg_duration=5,*,font=None):
        super().__init__(max_size=2)
        self.msg_duration = msg_duration
        self.persist = False

        self.message_list = []
        self.current_message = None
        self.display_timestamp = time.monotonic()

        if not font:
            self.font = FONT
        else:
            self.font = font

        self._bg_group = displayio.Group(max_size=1)
        self._text = Label(
            font=self.font,
            max_glyphs=50,
            anchored_position=(64,32),
            anchor_point=(1.0,1.0),
            color=0x787878,
            line_spacing=0.8
        )
        self.append(self._bg_group)
        self.append(self._text)

    # Returns True if there are still messages
    # Returns False otherwise
    def update(self):
        if not self.message_list: # No messages anyway; just exit
            return False
        now = time.monotonic()
        # Get button values, active low
        up_v = up_button.value
        down_v = down_button.value
        if up_v and down_v:
            # If no buttons are pressed, do this check.
            if now - self.display_timestamp < self.msg_duration:
                return bool(self.message_list)
        if not up_v:
            # If up button is pressed, wait for press to stop
            while not up_button.value:
                pass
            self.persist = False
            self.current_message = None
            self.display_timestamp = 0
            return False
        # Up and/or down buttons are pressed (active low), or it's time to update
        if not down_v:
            # If down button is pressed, wait for press to stop
            while not down_button.value:
                pass
            print("Down button release.")
            # delete this message and go to previous one.
            print("Deleting message {}.".format(self.current_message))
            self.message_list.pop(self.current_message)
            if self._bg_group:
                self._bg_group.pop()
            if self.message_list:
                self.current_message = (self.current_message - 1) % len(self.message_list)
                if self.current_message == len(self.message_list) - 1:
                    self.current_message = None # Fresh start
            else:
                self._text.text = ""
                self.persist = False
                return False
        # No buttons pressed if we got here
        self.display_timestamp = now
        if self.current_message is not None:
            next_message = (self.current_message + 1) % len(self.message_list)
            if next_message == 0:
                self.current_message = None
                return False
        else:
            next_message = 0
        self.current_message = next_message
        try:
            self._text.text = ""
            self._text.text = MessageMode._justify(self.message_list[self.current_message]['text'])
        except KeyError:
            self._text.text = ""
        try:
            picture = self.message_list[self.current_message]['picture']
            if not picture:
                raise KeyError
        except KeyError:
            try:
                emoji = self.message_list[self.current_message]['emoji']
                full_emoji = "bmps/emojis/" + "-".join(["{:x}".format(ord(cp)) for cp in emoji]) + ".bmp"
                try:
                    os.stat(full_emoji)
                    picture = full_emoji
                except OSError:
                    print("Backing off to simpler emoji.")
                    picture = "bmps/emojis/{:x}.bmp".format(ord(emoji[0]))
            except (KeyError,IndexError):
                picture = None
        print("Displaying {}, {}, {}.".format(self.current_message,self._text.text,picture))
        if self._bg_group:
            self._bg_group.pop()
        gc.collect()
        if picture:
            try:
                bg_file = open(picture,"rb")
                self._bg_group.append(displayio.TileGrid(
                    displayio.OnDiskBitmap(bg_file),
                    pixel_shader=displayio.ColorConverter()))
            except OSError as e:
                print(e)
        gc.collect()
        return True

    # True iff there are messages in the list
    def __bool__(self):
        return bool(self.message_list)

    def json_message(self, mqtt_client, topic, message):
        print(f"New message on topic {topic}: {message}")
        try:
            m = json.loads(message)
            self.message_list.append(m)
        except (ValueError, KeyError) as e:
            print(e)
        gc.collect()
        print(f"Free memory after adding message: {gc.mem_free()}")