import time
import machine, neopixel
from . import configure

ms = 1000000

class ws2811:


    def __init__(self, light_count, pin=5, order="GRB"):
        self.PIXEL_COUNT = light_count
        self.np = neopixel.NeoPixel(machine.Pin(pin), self.PIXEL_COUNT)
        if order == "RGB":
            self.np.ORDER = (1, 0, 2, 3)
        elif order == "RBG":
            self.np.ORDER = (1, 2, 0, 3)
        elif order == "GRB":
            self.np.ORDER = (0, 1, 2, 3)
        elif order == "GBR":
            self.np.ORDER = (0, 2, 1, 3)
        elif order == "BRG":
            self.np.ORDER = (2, 1, 0, 3)
        elif order == "BGR":
            self.np.ORDER = (2, 0, 1, 3)
        else:
            self.np.ORDER = (1, 0, 2, 3)

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
        count = int((ttms / twms)/2)
        for x in range(count):
            self.same(p1)
            time.sleep_ms(twms)
            self.same(p2)
            time.sleep_ms(twms)

    def colorWipe(self, red=0, green=0, blue=0, timems=50):
        # to be depricated
        timems = timems*self.PIXEL_COUNT
        self.color_wipe_2(red,green,blue,timems)

    def color_wipe_2(self, p1=(0, 0, 0), ttms=200, dir=0):
        """Wipe color across display a pixel at a time over the total time alocated"""
        pixel_count = self.PIXEL_COUNT
        start_time = time.time_ns()
        time_per_change = int(ttms / pixel_count)*ms
        end_time = start_time + (ttms * ms)
        last_update = start_time - time_per_change
        if dir == 0:
            for i in range(pixel_count):
                self.np[i] = p1
                while time.time_ns() < last_update + time_per_change:
                    pass
                self.np.write()
                last_update = last_update + time_per_change
                if time.time_ns() > end_time:
                    return
        elif dir == 1:
            for i in range(pixel_count):
                self.np[pixel_count - i - 1] = p1
                while time.time_ns() < last_update + time_per_change:
                    pass
                self.np.write()
                last_update = last_update + time_per_change
                if time.time_ns() > end_time:
                    return

    def runner(self, p1=(0, 0, 0), count=1, ttms=200, dir=0):
        """Wipe small number of pixels across over the total time alocated"""
        pixel_count = self.PIXEL_COUNT
        start_time = time.time_ns()
        time_per_change = int(ttms / pixel_count)*ms
        end_time = start_time + (ttms * ms)
        last_update = start_time - time_per_change
        if count > pixel_count:
            count = pixel_count
        if dir == 0:
            for i in range(count):
                self.np[i] = p1
            self.np.write()
            last_update = last_update + time_per_change
            for i in range(pixel_count-count):
                self.np[i] = self.np[i+count]
                self.np[i + count] = p1
                while time.time_ns() < last_update + time_per_change:
                    pass
                self.np.write()
                last_update = last_update + time_per_change
                if time.time_ns() > end_time:
                    self.off()
                    return
        elif dir == 1:
            for i in range(count):
                self.np[pixel_count-1-i] = p1
            self.np.write()
            last_update = last_update + time_per_change
            for i in range(pixel_count-count):
                self.np[pixel_count-1-i] = self.np[pixel_count-1-count-i]
                self.np[pixel_count-1-count-i] = p1
                while time.time_ns() < last_update + time_per_change:
                    pass
                self.np.write()
                last_update = last_update + time_per_change
                if time.time_ns() > end_time:
                    self.off()
                    return
        while time.time_ns() < end_time:
            True
        self.off()

    def fade(self, p1=(0, 0, 0), p2=(0, 0, 0),  steps=10, ttms=1000):
        steps = round(ttms/50)
        start_time = time.time_ns()
        time_per_change = int(ttms*ms/steps)
        end_time = start_time + (ttms * ms)
        last_update = start_time - time_per_change


        for i in range(1, steps + 1):
            if time.time_ns() > end_time - time_per_change:
                print("ended fade early")
                return
            r = ((p1[0] * (steps - i)) + (p2[0] * i)) / steps
            g = ((p1[1] * (steps - i)) + (p2[1] * i)) / steps
            b = ((p1[2] * (steps - i)) + (p2[2] * i)) / steps

            while time.time_ns() < last_update + time_per_change:
                pass
            self.same((int(r), int(g), int(b)))
            last_update = last_update + time_per_change

    # used for rainbow cycle
    def wheel(self, pos):
        # Input a value 0 to 255 to get a color value.
        # The colours are a transition r - g - b - back to r.
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
        time_per_change = int(ttms*ms/self.PIXEL_COUNT)
        end_time = start_time + (ttms * ms)
        last_update = start_time - time_per_change
        for j in range(self.PIXEL_COUNT):
            if time.time_ns() > end_time - time_per_change:
                print("ended fade early")
                return
            for i in range(self.PIXEL_COUNT):
                rc_index = (i * 256 // self.PIXEL_COUNT) + j
                self.np[i] = self.wheel(rc_index & 255)
            while time.time_ns() < last_update + time_per_change:
                pass
            self.np.write()
            last_update = last_update + time_per_change

    # alternate color every other light
    def alternate(self, p1=(0, 0, 0), p2=(0, 0, 0), count=1):
        switch = False
        for i in range(self.PIXEL_COUNT):
            if i % (count+1) == 0:
                switch = not switch
            if switch:
                self.np[i] = p1
            else:
                self.np[i] = p2
        self.np.write()

    def slide(self, dir=0, ttms=1000, twms=50):
        pixel_count = self.PIXEL_COUNT
        start_time = time.time_ns()
        time_per_change = twms*ms
        end_time = start_time + (ttms * ms)
        last_update = start_time - time_per_change

        if dir == 0:
            while time.time_ns() < end_time:
                self.np = self.np[-1:] + self.np[:-1]
                while time.time_ns() < last_update + time_per_change:
                    pass
                self.np.write()
                last_update = last_update + time_per_change
                if time.time_ns() > end_time:
                    self.off()
                    return
        elif dir == 1:
            while time.time_ns() < end_time:
                self.np = self.np[-1:] + self.np[:-1]
                while time.time_ns() < last_update + time_per_change:
                    pass
                self.np.write()
                last_update = last_update + time_per_change
                if time.time_ns() > end_time:
                    self.off()
                    return


from . import picoweb
app = picoweb.WebApp(__name__)
order = "RGB"
if configure.read_config_file("ws2811_color_order") is not None:
    order = configure.read_config_file("ws2811_color_order")
lights = ws2811(int(configure.read_config_file("count")), order=order)

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
    qs = qs_parse(req.qs())
    lights.rgb(rgb=(int(qs['red']), int(qs['green']), int(qs['blue'])))


@app.route("/color/off", parameters="None", description="all lights off")
def color_off(req, resp):
    yield from picoweb.start_response(resp)
    lights.off()


@app.route("/routine/flash", parameters="red, green, blue, timems, count", description="flash on and off (legacy)")
def routine_flash2(req, resp):
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


@app.route("/routine/rainbow", parameters="timems", description="rainbow color accross strip (broken)")
def routine_rainbow(req, resp):
    yield from picoweb.start_response(resp)
    lights.rainbow_cycle(**qs_parse(req.qs))


@app.route("/routine/alternate", parameters="red1, green1, blue1, red2, green2, blue2", description="alternate colors of lights")
def routine_alternate(req, resp):
    yield from picoweb.start_response(resp)
    lights.alternate(**qs_parse(req.qs))

@app.route("/routine/fade", parameters="red1, green1, blue1, red2, green2, blue2, steps, timems", description="fade between 2 colors over time")
def routine_alternate(req, resp):
    yield from picoweb.start_response(resp)
    lights.fade(**qs_parse(req.qs))

@app.route("/routine/runner", parameters="red, green, blue, timems, count", description="run small # of lights accross led strand in a direction")
def routine_runner(req, resp):
    yield from picoweb.start_response(resp)
    lights.runner(**qs_parse(req.qs))


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
    else:
        print(f"WS2811 - UNKNOWN - {command[2]}")


if __name__ == "__main__":
    app.run(debug=True)
