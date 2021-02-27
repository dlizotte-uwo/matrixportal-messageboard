import gc
from adafruit_display_text.label import Label
gc.collect()

import board
from digitalio import DigitalInOut, Direction, Pull
from adafruit_bitmap_font import bitmap_font
import displayio
import json
import time

# So all can use buttons

down_button = DigitalInOut(board.BUTTON_DOWN)
down_button.direction = Direction.INPUT
down_button.pull = Pull.UP

up_button = DigitalInOut(board.BUTTON_UP)
up_button.direction = Direction.INPUT
up_button.pull = Pull.UP

# =========================== Mode Classes ===========================

# Class implementing ON AIR / OFF AIR sign
# Construct, call set_mode, then show on display.
# Update in main loop

class AirMode(displayio.Group):

    def __init__(self, *):
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
        if temp < 0:
            return 0x5050F8
        elif temp > 0:
            return 0xF8D030
        else:
            return 0xF8F8F8

    def __init__(self,*,font=None,network=None,location=None,token=None):
        super().__init__(max_size=3)

        self.WEATHER_URL = "http://api.openweathermap.org/data/2.5/weather?q={}&units=metric&appid={}"\
            .format(location,token)

        self.weather_timeout = 600
        self.weather_timestamp = 0
        self.wdata = {}
        self.pressure = []
        self.pressure_slope = 0

        self.network = network

        if font is None:
            self.font = bitmap_font.load_font("fonts/6x10_DJL.bdf")
        else:
            self.font = font

        self.symfont = bitmap_font.load_font("fonts/6x10_DJL.bdf")
        self.symfont.load_glyphs('°Ckph%r↑↗→↘↓↙←↖↥↧\u33A9\u00AD')

        bb = self.font.get_bounding_box()
        (f_w,f_h) = bb[0], bb[1]

        self._bg_group = displayio.Group(max_size=1)
        self.weather1 = displayio.Group(max_size=6)

        UNIT_COLOR = 0x202020
        TEXT_COLOR = 0x301040
        WIND_COLOR = 0x78E078
        self.WDIR_COLOR = 0xF08070

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

    def fetch_weather(self):
        try:
            self.wdata = self.network.fetch_data(self.WEATHER_URL,json_path=([],))
            print("Response is", self.wdata)
            weather_timestamp = time.monotonic()
        except RuntimeError as e:
            print("Some error occured getting weather! -", e)

    def _winddir_char(self,d_string):
        d = float(d_string)
        didx = round(d / (360/8)) % 8
        return '↓↙←↖↑↗→↘'[didx]

    def update(self):
        now = time.monotonic()
        if not self.weather_timestamp or now - self.weather_timestamp > self.weather_timeout:
            self.weather_timestamp = now
            self.fetch_weather()

            self.temp_l.color = WeatherMode._temp_color(self.wdata["main"]["temp"])
            self.temp_l.text = u"{: 2.1f}".format(self.wdata["main"]["temp"])
            self.temp_unit_l.text = "°C"
            self.text_l.text = self.wdata["weather"][0]["main"]

            self.pressure.append(self.wdata["main"]["pressure"])
            if len(self.pressure) > 6:
                self.pressure.pop(0)
            n = len(self.pressure)
            mean_press = sum(self.pressure) / n
            self.pressure_slope = sum([(i - (n-1)/2) * (self.pressure[i] - mean_press) for i in range(n)])
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
        else:
            #Not time to re-fetch. What to do?
            if not down_button.value:
                # Wait for button release
                while not down_button.value:
                    pass
                # Avoid allocating new list?? idk...
                while self.pressure:
                    self.pressure.pop()
                self.pressure.append(self.wdata["main"]["pressure"])
                self.pressure_slope = 0
                gc.collect()
            if now % 15 < 5:
                self.windspeed_l.text = "{:3.0f} ".format(self.wdata["wind"]["speed"]*3.6) # m/s to kph
                self.windspeed_unit_l.text = "kph"
                self.winddir_l.text = self._winddir_char(self.wdata["wind"]["deg"])
                self.winddir_l.color = self.WDIR_COLOR
            elif now % 15 < 10:
                self.windspeed_l.text = "{:2.0f} ".format(self.wdata["main"]["humidity"])
                self.windspeed_unit_l.text = "%rh"
                self.winddir_l.text = ""
            else:
                self.windspeed_l.text = "{:4.0f}".format(self.wdata["main"]["pressure"])
                self.windspeed_unit_l.text = " h\u33A9"
                if self.pressure_slope > 0.1:
                    self.winddir_l.text = "↥"
                    self.winddir_l.color = 0x40C000
                elif self.pressure_slope < -0.1:
                    self.winddir_l.text = "↧"
                    self.winddir_l.color = 0xC04000
                else:
                    self.winddir_l.text = "\u00AD"
                    self.winddir_l.color = 0x444444


class MessageMode(displayio.Group):

    def __init__(self,msg_duration=5,*,font=None):
        super().__init__(max_size=2)
        self.msg_duration = msg_duration

        self.message_list = []
        self.current_message = 0
        self.display_message_timestamp = 0

        if not font:
            self.font = bitmap_font.load_font("fonts/c64.bdf")
        else:
            self.font = font

        self._bg_group = displayio.Group(max_size=1)
        self._text = Label(
            font=self.font,
            max_glyphs=33,
            x=0,y=-2,
            anchor_point=(0.0,0.0),
            color=0x0088FF,
            line_spacing=0.75
        )
        self.append(self._bg_group)
        self.append(self._text)
        self.timestamp = 0

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
            if now - self.timestamp < self.msg_duration:
                return bool(self.message_list)
        if not up_v:
            # If up button is pressed, wait for press to stop
            while not up_button.value:
                pass
        # Up and/or down buttons are pressed (active low), or it's time to update
        if not down_v:
            # If down button is pressed, wait for press to stop
            while not down_button.value:
                pass
            print("Down button release.")
            # delete this message and go to next.
            print("Deleting message {}.".format(self.current_message))
            self.message_list.pop(self.current_message)
            # This will be incremented below
            self.current_message -= 1
            if self._bg_group:
                self._bg_group.pop()
            gc.collect()
        if not self.message_list: # Could now be empty because of deletion
            self._text.text = ""
            self.current_message = 0
            gc.collect()
            return False
        # Advance current_message to next message
        self.current_message = (self.current_message + 1) % len(self.message_list)
        self.timestamp = now
        # Display next message
        gc.collect()
        try:
            self._text.text = ""
            self._text.text = self.message_list[self.current_message]['text']
        except KeyError:
            self._text.text = ""
        try:
            picture = self.message_list[self.current_message]['picture']
        except KeyError:
            picture = None
        print("Displaying {}, {}, {}.".format(self.current_message,self._text,picture))
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
        print("New message on topic {0}: {1}".format(topic, message))
        try:
            m = json.loads(message)
            self.message_list.append(m)
        except (ValueError, KeyError) as e:
            print(e)
        gc.collect()
        print("Free memory after adding message: %d" % gc.mem_free())


# ======================== End Mode Classes ===========================