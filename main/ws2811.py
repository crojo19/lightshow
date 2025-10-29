import time
import machine, neopixel
from . import configure
import gc

ms = 1000000

# Cache config values at module load
_led_count = int(configure.read_config_file("count"))
_led_pin = int(configure.read_config_file("ws2811_pin"))
_color_order = configure.read_config_file("ws2811_color_order") or "RGB"
_led_type = configure.read_config_file("type")

# Pre-compute wheel colors at module load for rainbow_cycle efficiency
_wheel_cache = []
for pos in range(256):
    if pos < 85:
        _wheel_cache.append((255 - pos * 3, pos * 3, 0))
    elif pos < 170:
        p = pos - 85
        _wheel_cache.append((0, 255 - p * 3, p * 3))
    else:
        p = pos - 170
        _wheel_cache.append((p * 3, 0, 255 - p * 3))

class ws2811:

    def __init__(self, light_count, pin=48, order="GRB", timing=1):
        self.PIXEL_COUNT = light_count

        # Use == for value comparison, not 'is'
        if timing == 0:
            self.np = neopixel.NeoPixel(machine.Pin(pin), self.PIXEL_COUNT, timing=0)
        elif timing == 2:
            self.np = neopixel.NeoPixel(machine.Pin(pin), self.PIXEL_COUNT, timing=(350, 700, 800, 600))
        else:  # Default timing=1
            self.np = neopixel.NeoPixel(machine.Pin(pin), self.PIXEL_COUNT, timing=1)

        # Set color order using dictionary lookup
        order_map = {
            "RGB": (1, 0, 2, 3),
            "RBG": (1, 2, 0, 3),
            "GRB": (0, 1, 2, 3),
            "GBR": (0, 2, 1, 3),
            "BRG": (2, 1, 0, 3),
            "BGR": (2, 0, 1, 3)
        }
        self.np.ORDER = order_map.get(order, (1, 0, 2, 3))

    def same(self, rgb=(0, 0, 0)):
        self.np.fill(rgb)
        self.np.write()

    def rgb(self, rgb=(0, 0, 0)):
        self.same(rgb=rgb)

    def red(self, brt=55):
        self.same(rgb=(brt, 0, 0))

    def green(self, brt=55):
        self.same(rgb=(0, brt, 0))

    def blue(self, brt=55):
        self.same(rgb=(0, 0, brt))

    def off(self):
        self.same(rgb=(0, 0, 0))

    def white(self, brt=55):
        self.same(rgb=(brt, brt, brt))

    def flash(self, red=0, green=0, blue=0, timems=60, count=10):
        # to be deprecated
        for y in range(count):
            for x in range(self.PIXEL_COUNT):
                self.np[x] = red, green, blue
            self.np.write()
            time.sleep_ms(timems)
            for x in range(self.PIXEL_COUNT):
                self.np[x] = (0, 0, 0)
            self.np.write()
            time.sleep_ms(timems)

    def flash_2(self, p1=(0, 0, 0), p2=(0, 0, 0), ttms=1000, twms=100):
        start_time = time.time_ns()
        time_per_change = twms * ms
        end_time = start_time + (ttms * ms)
        last_update = start_time

        toggle = True
        while time.time_ns() < end_time:
            self.np.fill(p1 if toggle else p2)
            self.np.write()
            toggle = not toggle

            last_update += time_per_change
            while time.time_ns() < last_update:
                time.sleep_us(10)

            # Exit if we've exceeded total time
            if time.time_ns() >= end_time:
                break

    def colorWipe(self, red=0, green=0, blue=0, timems=50):
        # to be deprecated - pass as tuple to new function
        self.color_wipe_2((red, green, blue), timems * self.PIXEL_COUNT)

    def color_wipe_2(self, p1=(0, 0, 0), ttms=200, dir=0):
        """Wipe color across display a pixel at a time over the total time allocated"""
        pixel_count = self.PIXEL_COUNT

        # Calculate divider based on pixel count
        if pixel_count > 300:
            divider = 4
        elif pixel_count >= 250:
            divider = 3
        elif pixel_count >= 150:
            divider = 2
        else:
            divider = 1

        start_time = time.time_ns()
        time_per_change = int(ttms / (pixel_count / divider)) * ms
        end_time = start_time + (ttms * ms)
        last_update = start_time - time_per_change
        steps = int(pixel_count / divider)

        if dir == 0:
            for i in range(steps):
                if time.time_ns() > end_time:
                    return
                for x in range(divider):
                    idx = i * divider + x
                    if idx < pixel_count:
                        self.np[idx] = p1

                while time.time_ns() < last_update + time_per_change:
                    time.sleep_us(10)
                self.np.write()
                last_update = last_update + time_per_change

        elif dir == 1:
            for i in range(steps):
                if time.time_ns() > end_time:
                    return
                for x in range(divider):
                    idx = pixel_count - (i * divider + x) - 1
                    if idx >= 0:
                        self.np[idx] = p1

                while time.time_ns() < last_update + time_per_change:
                    time.sleep_us(10)
                self.np.write()
                last_update = last_update + time_per_change

    def runner(self, p1=(0, 0, 0), count=1, ttms=200, dir=0):
        """Wipe small number of pixels across over the total time allocated"""
        pixel_count = self.PIXEL_COUNT

        if pixel_count > 300:
            divider = 4
        elif pixel_count >= 250:
            divider = 3
        elif pixel_count >= 150:
            divider = 2
        else:
            divider = 1

        start_time = time.time_ns()
        time_per_change = int(ttms / (pixel_count / divider)) * ms
        end_time = start_time + (ttms * ms)
        last_update = start_time - time_per_change

        if count > pixel_count:
            count = pixel_count

        if dir == 0:
            for i in range(min(count, pixel_count)):
                self.np[i] = p1
            self.np.write()
            last_update = last_update + time_per_change

            for i in range(pixel_count - count):
                if time.time_ns() > end_time:
                    self.off()
                    return

                for x in range(divider):
                    idx = i * divider + x
                    if idx < pixel_count and idx + count < pixel_count:
                        self.np[idx] = (0, 0, 0)
                        self.np[idx + count] = p1

                while time.time_ns() < last_update + time_per_change:
                    time.sleep_us(10)
                self.np.write()
                last_update = last_update + time_per_change

        elif dir == 1:
            for i in range(min(count, pixel_count)):
                self.np[pixel_count - 1 - i] = p1
            self.np.write()
            last_update = last_update + time_per_change

            for i in range(pixel_count - count):
                if time.time_ns() > end_time:
                    self.off()
                    return

                for x in range(divider):
                    idx = pixel_count - 1 - (i * divider) - x
                    if idx >= count and idx >= 0:
                        self.np[idx] = (0, 0, 0)
                        self.np[idx - count] = p1

                while time.time_ns() < last_update + time_per_change:
                    time.sleep_us(10)
                self.np.write()
                last_update = last_update + time_per_change

        remaining = end_time - time.time_ns()
        if remaining > 0:
            time.sleep_us(remaining // 1000)
        self.off()

    def runner_r(self, p0=(200, 0, 0), p1=(100, 100, 100), count=9, ttms=200, dir=0):
        """Wipe small number of pixels across over the total time allocated
        p0 is the first light and p1 are the rest of the lights this was for santas sleigh"""
        pixel_count = self.PIXEL_COUNT
        start_time = time.time_ns()
        time_per_change = int(ttms / pixel_count) * ms
        end_time = start_time + (ttms * ms)
        last_update = start_time - time_per_change

        if count > pixel_count:
            count = pixel_count

        if dir == 0:
            for i in range(count):
                if i == count - 1:
                    self.np[i] = p0
                else:
                    self.np[i] = p1
            self.np.write()
            last_update = last_update + time_per_change

            for i in range(pixel_count - count):
                if time.time_ns() > end_time:
                    self.off()
                    return

                self.np[i] = (0, 0, 0)
                self.np[i + count - 1] = p1
                self.np[i + count] = p0

                while time.time_ns() < last_update + time_per_change:
                    time.sleep_us(10)
                self.np.write()
                last_update = last_update + time_per_change

        elif dir == 1:
            for i in range(count):
                self.np[pixel_count - 1 - i] = p1
            self.np[pixel_count - count] = p0
            self.np.write()
            last_update = last_update + time_per_change

            for i in range(pixel_count - count):
                if time.time_ns() > end_time:
                    self.off()
                    return

                self.np[pixel_count - 1 - i] = (0, 0, 0)
                self.np[pixel_count - 1 - count - i] = p0
                self.np[pixel_count - count - i] = p1

                while time.time_ns() < last_update + time_per_change:
                    time.sleep_us(10)
                self.np.write()
                last_update = last_update + time_per_change

        self.off()

    def runner_r_trail(self, p0=(200, 0, 0), p1=(100, 100, 100), p2=(100, 0, 0), count=9, ttms=200, dir=0):
        """Wipe small number of pixels across over the total time allocated
        p0 is the first light and p1 are the rest of the lights this was for santas sleigh"""
        pixel_count = self.PIXEL_COUNT
        start_time = time.time_ns()
        time_per_change = int(ttms / pixel_count) * ms
        end_time = start_time + (ttms * ms)
        last_update = start_time - time_per_change

        if count > pixel_count:
            count = pixel_count

        if dir == 0:
            for i in range(count):
                if i == count - 1:
                    self.np[i] = p0
                else:
                    self.np[i] = p1
            self.np.write()
            last_update = last_update + time_per_change

            for i in range(pixel_count - count):
                if time.time_ns() > end_time:
                    self.rgb(p2)
                    return

                self.np[i] = p2
                self.np[i + count - 1] = p1
                self.np[i + count] = p0

                while time.time_ns() < last_update + time_per_change:
                    time.sleep_us(10)
                self.np.write()
                last_update = last_update + time_per_change

        elif dir == 1:
            for i in range(count):
                self.np[pixel_count - 1 - i] = p1
            self.np[pixel_count - count] = p0
            self.np.write()
            last_update = last_update + time_per_change

            for i in range(pixel_count - count):
                if time.time_ns() > end_time:
                    self.rgb(p2)
                    return

                self.np[pixel_count - 1 - i] = p2
                self.np[pixel_count - 1 - count - i] = p0
                self.np[pixel_count - count - i] = p1

                while time.time_ns() < last_update + time_per_change:
                    time.sleep_us(10)
                self.np.write()
                last_update = last_update + time_per_change

        self.rgb(p2)

    def fade(self, p1=(0, 0, 0), p2=(0, 0, 0), steps=10, ttms=1000):
        steps = max(10, min(100, round(ttms / 50)))

        start_time = time.time_ns()
        time_per_change = int(ttms * ms / steps)
        end_time = start_time + (ttms * ms)
        last_update = start_time - time_per_change

        for i in range(1, steps + 1):
            if time.time_ns() > end_time - time_per_change:
                self.same(p2)
                return

            r = ((p1[0] * (steps - i)) + (p2[0] * i)) // steps
            g = ((p1[1] * (steps - i)) + (p2[1] * i)) // steps
            b = ((p1[2] * (steps - i)) + (p2[2] * i)) // steps

            while time.time_ns() < last_update + time_per_change:
                time.sleep_us(10)
            self.same((r, g, b))
            last_update = last_update + time_per_change

    def wheel(self, pos):
        """Input a value 0 to 255 to get a color value.
        The colours are a transition r - g - b - back to r."""
        if pos < 0 or pos > 255:
            return (0, 0, 0)
        if pos < 85:
            return (255 - pos * 3, pos * 3, 0)
        if pos < 170:
            pos -= 85
            return (0, 255 - pos * 3, pos * 3)
        pos -= 170
        return (pos * 3, 0, 255 - pos * 3)

    def rainbow_cycle(self, ttms=500):
        start_time = time.time_ns()
        # Use optimal frame count for smoother animation
        frames = min(256, max(self.PIXEL_COUNT, 64))
        time_per_change = int(ttms * ms / frames)
        end_time = start_time + (ttms * ms)
        last_update = start_time - time_per_change

        # Pre-calculate pixel spacing for color wheel
        pixel_scale = 256 / self.PIXEL_COUNT if self.PIXEL_COUNT > 0 else 1

        for j in range(frames):
            if time.time_ns() > end_time - time_per_change:
                return

            # Update all pixels for this frame using module-level cache
            for i in range(self.PIXEL_COUNT):
                wheel_pos = int((i * pixel_scale) + j) & 255
                self.np[i] = _wheel_cache[wheel_pos]

            while time.time_ns() < last_update + time_per_change:
                time.sleep_us(10)
            self.np.write()
            last_update = last_update + time_per_change

    def alternate(self, p1=(0, 0, 0), p2=(0, 0, 0), count=1):
        """Alternate color every other light"""
        switch = False
        for i in range(self.PIXEL_COUNT):
            if i % (count + 1) == 0:
                switch = not switch
            self.np[i] = p1 if switch else p2
        self.np.write()

    def slide(self, dir=0, ttms=1000, twms=50):
        """Slide existing pattern across LEDs"""
        pixel_count = self.PIXEL_COUNT
        start_time = time.time_ns()
        time_per_change = twms * ms
        end_time = start_time + (ttms * ms)
        last_update = start_time - time_per_change

        original = [self.np[i] for i in range(pixel_count)]

        iterations = int(ttms / twms)
        for iteration in range(iterations):
            if time.time_ns() > end_time:
                self.off()
                return

            if dir == 0:
                for i in range(pixel_count):
                    self.np[i] = original[(i - iteration) % pixel_count]
            else:
                for i in range(pixel_count):
                    self.np[i] = original[(i + iteration) % pixel_count]

            while time.time_ns() < last_update + time_per_change:
                time.sleep_us(100)
            self.np.write()
            last_update = last_update + time_per_change

            if iteration % 10 == 0:
                gc.collect()

    # ========== NEW ANIMATIONS ==========

    def sparkle(self, p1=(255, 255, 255), density=10, ttms=1000, fade_out=True):
        """Random sparkle effect - lights randomly appear and optionally fade
        density: percentage of lights to sparkle (1-100)
        fade_out: if True, lights fade out, else they turn off instantly"""
        import urandom

        start_time = time.time_ns()
        end_time = start_time + (ttms * ms)

        while time.time_ns() < end_time:
            for _ in range(max(1, self.PIXEL_COUNT * density // 100)):
                idx = urandom.getrandbits(8) % self.PIXEL_COUNT
                self.np[idx] = p1

            self.np.write()
            time.sleep_ms(50)

            if fade_out:
                for i in range(self.PIXEL_COUNT):
                    r, g, b = self.np[i]
                    self.np[i] = (r * 3 // 4, g * 3 // 4, b * 3 // 4)
            else:
                for i in range(self.PIXEL_COUNT):
                    self.np[i] = (0, 0, 0)

        self.off()

    def theater_chase(self, p1=(255, 0, 0), spacing=3, ttms=1000, dir=0):
        """Theater marquee chase - lights move in groups with gaps
        spacing: gap between lit groups (typically 3 for theater effect)"""

        start_time = time.time_ns()
        time_per_change = 100 * ms
        end_time = start_time + (ttms * ms)
        last_update = start_time
        offset = 0

        while time.time_ns() < end_time:
            for i in range(self.PIXEL_COUNT):
                if (i + offset) % spacing == 0:
                    self.np[i] = p1
                else:
                    self.np[i] = (0, 0, 0)

            while time.time_ns() < last_update + time_per_change:
                time.sleep_us(10)

            self.np.write()
            last_update = last_update + time_per_change
            offset = (offset + (1 if dir == 0 else -1)) % spacing

    def comet(self, p1=(255, 255, 255), tail_length=10, ttms=1000, dir=0):
        """Comet/meteor with fading tail
        tail_length: length of trailing fade"""

        pixel_count = self.PIXEL_COUNT
        start_time = time.time_ns()
        time_per_change = int(ttms / (pixel_count + tail_length)) * ms
        end_time = start_time + (ttms * ms)
        last_update = start_time

        for pos in range(pixel_count + tail_length):
            if time.time_ns() > end_time:
                break

            for i in range(pixel_count):
                self.np[i] = (0, 0, 0)

            for i in range(tail_length):
                if dir == 0:
                    pixel_pos = pos - i
                else:
                    pixel_pos = pixel_count - 1 - pos + i

                if 0 <= pixel_pos < pixel_count:
                    brightness = (tail_length - i) / tail_length
                    self.np[pixel_pos] = (
                        int(p1[0] * brightness),
                        int(p1[1] * brightness),
                        int(p1[2] * brightness)
                    )

            while time.time_ns() < last_update + time_per_change:
                time.sleep_us(10)

            self.np.write()
            last_update = last_update + time_per_change

        self.off()

    def breathe(self, p1=(255, 0, 0), cycles=3, ttms=3000):
        """Smooth breathing effect - pulse brightness in and out
        cycles: number of breath cycles"""

        import math

        steps_per_cycle = 50
        total_steps = steps_per_cycle * cycles
        start_time = time.time_ns()
        time_per_step = int(ttms / total_steps) * ms
        end_time = start_time + (ttms * ms)
        last_update = start_time

        for step in range(total_steps):
            if time.time_ns() > end_time:
                break

            angle = (step % steps_per_cycle) / steps_per_cycle * math.pi * 2
            brightness = (math.sin(angle) + 1) / 2

            color = (
                int(p1[0] * brightness),
                int(p1[1] * brightness),
                int(p1[2] * brightness)
            )

            self.np.fill(color)
            self.np.write()

            while time.time_ns() < last_update + time_per_step:
                time.sleep_us(10)
            last_update = last_update + time_per_step

        self.off()

    def fire(self, ttms=2000, cooling=50, sparking=120):
        """Realistic fire/flame effect
        cooling: how much heat dissipates (higher = cooler fire)
        sparking: chance of new sparks (higher = more active)"""

        import urandom

        heat = [0] * self.PIXEL_COUNT

        start_time = time.time_ns()
        end_time = start_time + (ttms * ms)

        while time.time_ns() < end_time:
            for i in range(self.PIXEL_COUNT):
                cooldown = urandom.getrandbits(8) % ((cooling * 10) // self.PIXEL_COUNT + 2)
                heat[i] = max(0, heat[i] - cooldown)

            for i in range(self.PIXEL_COUNT - 1, 1, -1):
                heat[i] = (heat[i - 1] + heat[i - 2] + heat[i - 2]) // 3

            if urandom.getrandbits(8) < sparking:
                y = urandom.getrandbits(8) % 7
                heat[y] = min(255, heat[y] + urandom.getrandbits(8) % (255 - 160) + 160)

            for i in range(self.PIXEL_COUNT):
                temp = heat[i]
                if temp < 85:
                    self.np[i] = (temp * 3, 0, 0)
                elif temp < 170:
                    self.np[i] = (255, (temp - 85) * 3, 0)
                else:
                    self.np[i] = (255, 255, (temp - 170) * 3)

            self.np.write()
            time.sleep_ms(50)

        self.off()

    def wave(self, p1=(0, 0, 255), p2=(0, 0, 0), wave_length=10, waves=3, ttms=2000):
        """Wave pulse effect - multiple waves travel down strip
        wave_length: width of each wave
        waves: number of waves simultaneously"""

        import math

        # Validate parameters to prevent division by zero
        waves = max(1, min(waves, self.PIXEL_COUNT))
        wave_length = max(1, wave_length)

        start_time = time.time_ns()
        time_per_change = 30 * ms
        end_time = start_time + (ttms * ms)
        last_update = start_time
        offset = 0

        # Calculate wave segment length (guaranteed > 0)
        segment_length = max(1, self.PIXEL_COUNT // waves)

        while time.time_ns() < end_time:
            for i in range(self.PIXEL_COUNT):
                wave_pos = (i + offset) % segment_length
                brightness = abs(math.sin(wave_pos * 3.14159 / wave_length))

                r = int(p2[0] + (p1[0] - p2[0]) * brightness)
                g = int(p2[1] + (p1[1] - p2[1]) * brightness)
                b = int(p2[2] + (p1[2] - p2[2]) * brightness)

                self.np[i] = (r, g, b)

            while time.time_ns() < last_update + time_per_change:
                time.sleep_us(10)

            self.np.write()
            last_update = last_update + time_per_change
            offset = (offset + 1) % segment_length

        self.off()

    def scanner(self, p1=(255, 0, 0), tail_length=5, bounces=5, ttms=2000):
        """Knight Rider / Cylon eye scanner effect
        tail_length: length of trailing fade
        bounces: number of back-and-forth cycles"""

        start_time = time.time_ns()
        bounce_time = ttms / bounces
        time_per_step = int(bounce_time / (self.PIXEL_COUNT * 2)) * ms
        end_time = start_time + (ttms * ms)
        last_update = start_time

        for bounce in range(bounces * 2):
            direction = 1 if bounce % 2 == 0 else -1
            start_pos = 0 if direction == 1 else self.PIXEL_COUNT - 1
            end_pos = self.PIXEL_COUNT if direction == 1 else -1

            pos = start_pos
            while pos != end_pos:
                if time.time_ns() > end_time:
                    self.off()
                    return

                for i in range(self.PIXEL_COUNT):
                    self.np[i] = (0, 0, 0)

                for i in range(tail_length):
                    pixel_pos = pos - (i * direction)
                    if 0 <= pixel_pos < self.PIXEL_COUNT:
                        brightness = (tail_length - i) / tail_length
                        self.np[pixel_pos] = (
                            int(p1[0] * brightness),
                            int(p1[1] * brightness),
                            int(p1[2] * brightness)
                        )

                while time.time_ns() < last_update + time_per_step:
                    time.sleep_us(10)

                self.np.write()
                last_update = last_update + time_per_step
                pos += direction

        self.off()

    def gradient(self, p1=(255, 0, 0), p2=(0, 0, 255), ttms=0):
        """Fill strip with smooth gradient between colors
        ttms: if >0, animate the gradient fill"""

        if ttms == 0:
            for i in range(self.PIXEL_COUNT):
                ratio = i / (self.PIXEL_COUNT - 1) if self.PIXEL_COUNT > 1 else 0
                r = int(p1[0] + (p2[0] - p1[0]) * ratio)
                g = int(p1[1] + (p2[1] - p1[1]) * ratio)
                b = int(p1[2] + (p2[2] - p1[2]) * ratio)
                self.np[i] = (r, g, b)
            self.np.write()
        else:
            start_time = time.time_ns()
            time_per_pixel = int(ttms / self.PIXEL_COUNT) * ms
            end_time = start_time + (ttms * ms)
            last_update = start_time

            for i in range(self.PIXEL_COUNT):
                if time.time_ns() > end_time:
                    break

                ratio = i / (self.PIXEL_COUNT - 1) if self.PIXEL_COUNT > 1 else 0
                r = int(p1[0] + (p2[0] - p1[0]) * ratio)
                g = int(p1[1] + (p2[1] - p1[1]) * ratio)
                b = int(p1[2] + (p2[2] - p1[2]) * ratio)
                self.np[i] = (r, g, b)

                while time.time_ns() < last_update + time_per_pixel:
                    time.sleep_us(10)

                self.np.write()
                last_update = last_update + time_per_pixel


from . import picoweb
app = picoweb.WebApp(__name__)

# Use cached config values
if _led_type == "WS2812":
    lights = ws2811(_led_count, order=_color_order, timing=2, pin=_led_pin)
elif _led_type == "WS2812B":
    lights = ws2811(_led_count, order=_color_order, timing=1, pin=_led_pin)
else:
    lights = ws2811(_led_count, order=_color_order, pin=_led_pin)

def try_int(val):
    try:
        return int(val)
    except ValueError:
        return val


def qs_parse(qs):
    if len(qs) < 3:
        return {}
    res = {}
    for el in qs.split('&'):
        key, val = el.split('=')
        res[key] = try_int(val)
    return res


@app.route("/", parameters="None", description="Show LED Site Map")
def index(req, resp):
    yield from picoweb.start_response(resp)
    for item in app.get_url_map():
        yield from resp.awrite("<p>")
        yield from resp.awrite(str(item[0]))
        yield from resp.awrite("</p>")


@app.route("/color/rgb", parameters="red, green, blue", description="all lights r,g,b")
def color_rgb(req, resp):
    yield from picoweb.start_response(resp)
    qs = qs_parse(req.qs)
    lights.rgb(rgb=(int(qs['red']), int(qs['green']), int(qs['blue'])))


@app.route("/color/off", parameters="None", description="all lights off")
def color_off(req, resp):
    yield from picoweb.start_response(resp)
    lights.off()


@app.route("/routine/flash", parameters="red, green, blue, timems, count", description="flash on and off (legacy)")
def routine_flash(req, resp):
    yield from picoweb.start_response(resp)
    lights.flash(**qs_parse(req.qs))

@app.route("/routine/flash_2", parameters="red1, green1, blue1, red2, green2, blue2, totaltimems, timewaitms", description="flash lights between 2 colors")
def routine_flash2(req, resp):
    yield from picoweb.start_response(resp)
    lights.flash_2(**qs_parse(req.qs))


@app.route("/routine/colorWipe", parameters="red, green, blue, timems", description="wipe color accross LEDs (legacy)")
def routine_colorwipe(req, resp):
    yield from picoweb.start_response(resp)
    lights.colorWipe(**qs_parse(req.qs))


@app.route("/routine/color_wipe", parameters="red, green, blue, timems, direction", description="wipe color accross LEDs")
def routine_color_wipe(req, resp):
    yield from picoweb.start_response(resp)
    lights.color_wipe_2(**qs_parse(req.qs))


@app.route("/routine/rainbow", parameters="timems", description="rainbow color accross strip")
def routine_rainbow(req, resp):
    yield from picoweb.start_response(resp)
    lights.rainbow_cycle(**qs_parse(req.qs))


@app.route("/routine/alternate", parameters="red1, green1, blue1, red2, green2, blue2", description="alternate colors of lights")
def routine_alternate(req, resp):
    yield from picoweb.start_response(resp)
    lights.alternate(**qs_parse(req.qs))

@app.route("/routine/fade", parameters="red1, green1, blue1, red2, green2, blue2, steps, timems", description="fade between 2 colors over time")
def routine_fade(req, resp):
    yield from picoweb.start_response(resp)
    lights.fade(**qs_parse(req.qs))

@app.route("/routine/runner", parameters="red, green, blue, timems, count", description="run small # of lights accross led strand in a direction")
def routine_runner(req, resp):
    yield from picoweb.start_response(resp)
    lights.runner(**qs_parse(req.qs))

@app.route("/routine/runner_r", parameters="red, green, blue, ttms, dir", description="run small # of lights accross led strand in a direction")
def routine_runner_r(req, resp):
    yield from picoweb.start_response(resp)
    qs = qs_parse(req.qs)
    lights.runner_r(ttms=int(qs['ttms']), dir=int(qs['dir']))

# ========== NEW ANIMATION ROUTES ==========

@app.route("/routine/sparkle", parameters="red, green, blue, density, timems, fade_out", description="random sparkle/twinkle effect")
def routine_sparkle(req, resp):
    yield from picoweb.start_response(resp)
    lights.sparkle(**qs_parse(req.qs))

@app.route("/routine/theater_chase", parameters="red, green, blue, spacing, timems, dir", description="theater marquee chase effect")
def routine_theater_chase(req, resp):
    yield from picoweb.start_response(resp)
    lights.theater_chase(**qs_parse(req.qs))

@app.route("/routine/comet", parameters="red, green, blue, tail_length, timems, dir", description="comet/meteor with fading tail")
def routine_comet(req, resp):
    yield from picoweb.start_response(resp)
    lights.comet(**qs_parse(req.qs))

@app.route("/routine/breathe", parameters="red, green, blue, cycles, timems", description="smooth breathing pulse effect")
def routine_breathe(req, resp):
    yield from picoweb.start_response(resp)
    lights.breathe(**qs_parse(req.qs))

@app.route("/routine/fire", parameters="timems, cooling, sparking", description="realistic fire/flame effect")
def routine_fire(req, resp):
    yield from picoweb.start_response(resp)
    lights.fire(**qs_parse(req.qs))

@app.route("/routine/wave", parameters="red1, green1, blue1, red2, green2, blue2, wave_length, waves, timems", description="wave pulse effect")
def routine_wave(req, resp):
    yield from picoweb.start_response(resp)
    lights.wave(**qs_parse(req.qs))

@app.route("/routine/scanner", parameters="red, green, blue, tail_length, bounces, timems", description="Knight Rider/Cylon scanner effect")
def routine_scanner(req, resp):
    yield from picoweb.start_response(resp)
    lights.scanner(**qs_parse(req.qs))

@app.route("/routine/gradient", parameters="red1, green1, blue1, red2, green2, blue2, timems", description="smooth color gradient fill")
def routine_gradient(req, resp):
    yield from picoweb.start_response(resp)
    lights.gradient(**qs_parse(req.qs))

def run_command(command):
    if command[1] == 0:
        print("WS2811 - OFF")
        lights.same(rgb=(0, 0, 0))
    elif command[1] == 1:
        print(f"WS2811 - RGB - {command[2]}")
        lights.same(**command[2])
    elif command[1] == 2:
        print(f"WS2811 - Routine Fade - {command[2]}")
        lights.fade(**command[2])
    elif command[1] == 3:
        print(f"WS2811 - Routine Flash - {command[2]}")
        lights.flash_2(**command[2])
    elif command[1] == 4:
        print(f"WS2811 - Routine Color Wipe - {command[2]}")
        lights.color_wipe_2(**command[2])
    elif command[1] == 5:
        print(f"WS2811 - Routine Rainbow - {command[2]}")
        lights.rainbow_cycle(**command[2])
    elif command[1] == 6:
        print(f"WS2811 - Routine Runner - {command[2]}")
        lights.runner(**command[2])
    elif command[1] == 7:
        print(f"WS2811 - Routine Alternate - {command[2]}")
        lights.alternate(**command[2])
    elif command[1] == 8:
        print(f"WS2811 - Routine slide - {command[2]}")
        lights.slide(**command[2])
    # New animation commands
    elif command[1] == 9:
        print(f"WS2811 - Routine Sparkle - {command[2]}")
        lights.sparkle(**command[2])
    elif command[1] == 10:
        print(f"WS2811 - Routine Theater Chase - {command[2]}")
        lights.theater_chase(**command[2])
    elif command[1] == 11:
        print(f"WS2811 - Routine Comet - {command[2]}")
        lights.comet(**command[2])
    elif command[1] == 12:
        print(f"WS2811 - Routine Breathe - {command[2]}")
        lights.breathe(**command[2])
    elif command[1] == 13:
        print(f"WS2811 - Routine Fire - {command[2]}")
        lights.fire(**command[2])
    elif command[1] == 14:
        print(f"WS2811 - Routine Wave - {command[2]}")
        lights.wave(**command[2])
    elif command[1] == 15:
        print(f"WS2811 - Routine Scanner - {command[2]}")
        lights.scanner(**command[2])
    elif command[1] == 16:
        print(f"WS2811 - Routine Gradient - {command[2]}")
        lights.gradient(**command[2])
    else:
        print(f"WS2811 - UNKNOWN - {command[2]}")


if __name__ == "__main__":
    app.run(debug=True)
