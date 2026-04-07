"""High-level Divoom Ditoo / Ditoo Pro device interface."""

import time
from PIL import Image

from .protocol import BluetoothTransport, build_packet, chunk_payload
from .image import encode_palette_image, encode_animation_frame
from .font import draw_text, text_width


# Channel IDs for set_channel
CHANNEL_CLOCK = 0x00
CHANNEL_LIGHT = 0x01
CHANNEL_CLOUD = 0x02
CHANNEL_VJ = 0x03
CHANNEL_VISUALIZER = 0x04
CHANNEL_CUSTOM = 0x05

# Clock face styles
CLOCK_FULLSCREEN = 0x00
CLOCK_RAINBOW = 0x01
CLOCK_BOXED = 0x02
CLOCK_ANALOG_SQUARE = 0x03
CLOCK_FULLSCREEN_NEG = 0x04
CLOCK_ANALOG_ROUND = 0x05

# VJ effect IDs
VJ_SPARKLES = 0x00
VJ_LAVA = 0x01
VJ_RAINBOW_LINES = 0x02
VJ_DROPS = 0x03
VJ_RAINBOW_SWIRL = 0x04
VJ_CMY_FADE = 0x05
VJ_RAINBOW_LAVA = 0x06
VJ_PASTEL = 0x07
VJ_CMY_WAVE = 0x08
VJ_FIRE = 0x09
VJ_COUNTDOWN = 0x0A
VJ_PINK_BLUE_FADE = 0x0B
VJ_RAINBOW_POLYGONS = 0x0C
VJ_PINK_BLUE_WAVE = 0x0D
VJ_RAINBOW_CROSS = 0x0E
VJ_RAINBOW_SHAPES = 0x0F

# Weather types
WEATHER_CLEAR = 0x01
WEATHER_CLOUDY = 0x03
WEATHER_THUNDER = 0x05
WEATHER_RAIN = 0x06
WEATHER_SNOW = 0x08
WEATHER_FOG = 0x09

# Light modes
LIGHT_PLAIN = 0x00
LIGHT_LOVE = 0x01
LIGHT_PLANTS = 0x02
LIGHT_NO_MOSQUITO = 0x03
LIGHT_SLEEPING = 0x04


class DitooDevice:
    """Interface to a Divoom Ditoo or Ditoo Pro."""

    MAX_RETRIES = 5
    RETRY_DELAY = 3

    def __init__(self, mac_address, port=2):
        self.transport = BluetoothTransport(mac_address, port)

    @property
    def connected(self):
        return self.transport.connected

    # -- Connection management --

    def connect(self):
        """Connect to the device."""
        self.transport.connect()

    def disconnect(self):
        """Disconnect from the device."""
        self.transport.disconnect()

    def connect_with_retry(self, max_retries=None):
        """Connect with automatic retries on failure."""
        retries = max_retries or self.MAX_RETRIES
        for attempt in range(1, retries + 1):
            try:
                self.connect()
                return
            except (OSError, ConnectionError) as e:
                print(f"Connection attempt {attempt}/{retries} failed: {e}")
                self.disconnect()
                if attempt < retries:
                    time.sleep(self.RETRY_DELAY)
        raise ConnectionError(f"Failed to connect after {retries} attempts")

    def _send(self, command, args=None):
        """Send a command, auto-reconnecting once on failure."""
        try:
            self.transport.send_command(command, args)
        except (OSError, ConnectionError):
            self.disconnect()
            self.connect_with_retry()
            self.transport.send_command(command, args)

    # -- Display --

    def set_brightness(self, brightness):
        """Set display brightness (0-100)."""
        self._send(0x74, [max(0, min(100, brightness))])

    def screen_off(self):
        """Turn the display off."""
        self.set_brightness(0)
        self.set_light(0, 0, 0, brightness=0, power=False)

    def screen_on(self, brightness=80):
        """Turn the display on at given brightness."""
        self.set_brightness(brightness)

    # -- Channels --

    def set_channel(self, channel):
        """Switch display channel by ID."""
        self._send(0x45, [channel])

    def set_clock(self, style=CLOCK_FULLSCREEN, show_time=True, show_weather=True,
                  show_temp=True, show_calendar=True, color=(255, 255, 255)):
        """Switch to clock channel with options."""
        r, g, b = color
        self._send(0x45, [
            CHANNEL_CLOCK, 0x01, style,
            int(show_time), int(show_weather), int(show_temp), int(show_calendar),
            r, g, b
        ])

    def set_light(self, r, g, b, brightness=100, mode=LIGHT_PLAIN, power=True):
        """Switch to light/lamp channel."""
        self._send(0x45, [
            CHANNEL_LIGHT, r, g, b, brightness, mode, int(power), 0x00, 0x00, 0x00
        ])

    def set_cloud(self):
        """Switch to cloud/community channel."""
        self._send(0x45, [CHANNEL_CLOUD])

    def set_vj(self, effect=VJ_FIRE):
        """Switch to VJ effects channel."""
        self._send(0x45, [CHANNEL_VJ, effect])

    def set_visualizer(self, style=0):
        """Switch to audio visualizer channel."""
        self._send(0x45, [CHANNEL_VISUALIZER, style])

    def set_custom(self):
        """Switch to custom image push channel."""
        self._send(0x45, [CHANNEL_CUSTOM])

    def set_scoreboard(self, red=0, blue=0):
        """Show scoreboard with red and blue team scores (0-999)."""
        self._send(0x45, [
            0x06, 0x00,
            red & 0xFF, (red >> 8) & 0xFF,
            blue & 0xFF, (blue >> 8) & 0xFF,
        ])

    # -- Images --

    def send_image(self, img):
        """Send a 16x16 PIL Image to the display.

        Automatically switches to custom channel if not already there.
        """
        frame_data = encode_palette_image(img)
        args = [0x00, 0x0A, 0x0A, 0x04] + frame_data
        self._send(0x44, args)

    def send_animation(self, frames, duration_ms=100):
        """Send a multi-frame animation.

        Args:
            frames: list of 16x16 PIL Images
            duration_ms: milliseconds per frame (or list of per-frame durations)
        """
        if isinstance(duration_ms, int):
            durations = [duration_ms] * len(frames)
        else:
            durations = duration_ms

        all_frame_data = []
        for i, (frame_img, dur) in enumerate(zip(frames, durations)):
            reset = i > 0  # reuse palette from frame 0 for efficiency
            frame_bytes = encode_animation_frame(frame_img, dur, reset_palette=False)
            all_frame_data.extend(frame_bytes)

        total_size = len(all_frame_data)
        chunks = chunk_payload(all_frame_data)

        for pkt_num, chunk in enumerate(chunks):
            args = [total_size & 0xFF, (total_size >> 8) & 0xFF, pkt_num] + chunk
            self._send(0x49, args)
            time.sleep(0.05)

    def send_text(self, text, color=(255, 255, 255), bg_color=(0, 0, 0),
                  y=5, scroll_speed_ms=80):
        """Render text and send as a scrolling animation.

        For text that fits in 16px, sends a static image.
        For wider text, sends a scrolling animation.
        """
        tw = text_width(text)

        if tw <= 16:
            img = Image.new("RGB", (16, 16), bg_color)
            x = max(0, (16 - tw) // 2)
            draw_text(img, text, x, y, color)
            self.set_custom()
            time.sleep(0.1)
            self.send_image(img)
            return

        # Render full-width image then slice into scrolling frames
        pad = 16
        full_width = tw + pad * 2
        full_img = Image.new("RGB", (full_width, 16), bg_color)
        draw_text(full_img, text, pad, y, color)

        frames = []
        for offset in range(full_width - 15):
            frame = full_img.crop((offset, 0, offset + 16, 16))
            frames.append(frame)

        self.set_custom()
        time.sleep(0.1)
        self.send_animation(frames, duration_ms=scroll_speed_ms)

    # -- Time --

    def set_datetime(self, dt=None):
        """Set the device clock. Uses current local time if dt is None."""
        if dt is None:
            import datetime
            dt = datetime.datetime.now()
        self._send(0x18, [
            dt.year % 100, dt.year // 100,
            dt.month, dt.day, dt.hour, dt.minute, dt.second, 0x00
        ])

    def set_time_format(self, use_24h=True):
        """Set 12/24 hour display format."""
        self._send(0x2D, [0x01 if use_24h else 0x00])

    # -- Weather --

    def set_weather(self, temperature, weather_type=WEATHER_CLEAR):
        """Set weather display.

        Args:
            temperature: degrees (negative values use two's complement)
            weather_type: one of the WEATHER_* constants
        """
        temp_byte = temperature if temperature >= 0 else (256 + temperature)
        self._send(0x5F, [temp_byte & 0xFF, weather_type])

    def set_temp_unit(self, fahrenheit=False):
        """Set temperature display unit."""
        self._send(0x4C, [0x01 if fahrenheit else 0x00])

    # -- Audio --

    def set_volume(self, percent):
        """Set volume (0-100), mapped to hardware 0-15 scale."""
        hw_vol = max(0, min(15, int(percent * 15 / 100)))
        self._send(0x08, [hw_vol])

    def play(self):
        """Resume audio playback."""
        self._send(0x0A, [0x01])

    def pause(self):
        """Pause audio playback."""
        self._send(0x0A, [0x00])

    def set_radio(self, on=True):
        """Turn FM radio on or off."""
        self._send(0x05, [0x01 if on else 0x00])

    def set_radio_frequency(self, freq_mhz):
        """Set FM radio frequency (e.g., 101.1)."""
        freq_val = int(freq_mhz * 10)
        self._send(0x61, [freq_val & 0xFF, (freq_val >> 8) & 0xFF])

    # -- Tools --

    def start_timer(self):
        """Start the stopwatch/timer."""
        self._send(0x72, [0x00, 0x01])

    def stop_timer(self):
        """Stop the stopwatch/timer."""
        self._send(0x72, [0x00, 0x00])

    def start_countdown(self, minutes, seconds=0):
        """Start a countdown timer."""
        self._send(0x72, [0x03, 0x01, min(99, minutes), min(59, seconds)])

    def stop_countdown(self):
        """Stop the countdown timer."""
        self._send(0x72, [0x03, 0x00, 0x00, 0x00])

    def start_noise_meter(self):
        """Start the noise/decibel meter."""
        self._send(0x72, [0x02, 0x01])

    def stop_noise_meter(self):
        """Stop the noise/decibel meter."""
        self._send(0x72, [0x02, 0x00])

    def set_scoreboard_tool(self, red=0, blue=0):
        """Update scoreboard via tool command."""
        self._send(0x72, [
            0x01, 0x01,
            red & 0xFF, (red >> 8) & 0xFF,
            blue & 0xFF, (blue >> 8) & 0xFF,
        ])

    # -- Alarms --

    def set_alarm(self, slot, hour, minute, weekdays=0x7F, enabled=True, volume=8):
        """Set an alarm.

        Args:
            slot: alarm slot (0-2)
            hour: 0-23
            minute: 0-59
            weekdays: bitmask (bit0=Mon...bit6=Sun, 0x7F=daily)
            enabled: True/False
            volume: 0-16
        """
        self._send(0x43, [
            slot, int(enabled), hour, minute, weekdays,
            0x00, 0x00,  # mode, trigger
            0x00, 0x00,  # freq
            min(16, volume),
        ])

    def disable_alarm(self, slot):
        """Disable an alarm slot."""
        self._send(0x43, [slot, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])

    # -- Sleep --

    def set_sleep_timer(self, minutes):
        """Set sleep timer (0 to disable)."""
        self._send(0x40, [
            min(120, minutes), 0x00, 0x01 if minutes > 0 else 0x00,
            0x00, 0x00, 0x00,  # freq, volume
            0x00, 0x00, 0x00,  # R, G, B
            0x00,              # brightness
        ])

    # -- Keyboard (Ditoo-specific) --

    def keyboard_led_toggle(self):
        """Toggle keyboard backlight on/off."""
        self._send(0x23, [0x02])

    def keyboard_led_next(self):
        """Switch to next keyboard LED effect."""
        self._send(0x23, [0x01])

    def keyboard_led_prev(self):
        """Switch to previous keyboard LED effect."""
        self._send(0x23, [0x00])

    # -- Games --

    def start_game(self, game_id):
        """Launch a built-in game."""
        self._send(0xA0, [0x01, game_id])

    def stop_game(self):
        """Stop the current game."""
        self._send(0xA0, [0x00, 0x00])

    # -- Device info --

    def get_settings(self):
        """Request current device settings. Returns raw response bytes."""
        self._send(0x46)
        return self.transport.receive(timeout=3)

    def get_temperature(self):
        """Request temperature sensor reading. Returns raw response bytes."""
        self._send(0x59)
        return self.transport.receive(timeout=3)

    # -- Context manager --

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc):
        self.disconnect()
