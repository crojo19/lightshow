
import time
import machine, neopixel
from . import configure

class ws2811:
    def __init__(self, light_count, rgb=False, gbr=False, rbg=False, grb=False, brg=False):
        self.PIXEL_COUNT = light_count
        self.np = neopixel.NeoPixel(machine.Pin(5), self.PIXEL_COUNT)
        self.GRB = grb
        self.GBR = gbr
        self.RBG = rbg
        self.RGB = rgb
        self.BRG = brg

    def pixel(self, r, g, b):
        if self.GRB:
            return g, r, b
        elif self.GBR:
            return g, b, r
        elif self.RBG:
            return r, b, g
        elif self.RGB:
            return r, g, b
        elif self.BRG:
            return b, r, g

    def same(self, r, g, b):
        col = self.pixel(r, g, b)
        self.np.fill(col)
        self.np.write()

    def red(self, brightness=55):
        self.same(brightness, 0, 0)

    def green(self, brightness=55):
        self.same(0, brightness, 0)

    def blue(self, brightness=55):
        self.same(0, 0, brightness)

    def off(self):
        self.same(0, 0, 0)

    def white(self, brightness=55):
        self.same(brightness, brightness, brightness)

    def flash(self, red=0, green=0, blue=0, timems=60, count=10):
        for y in range(count):
            for x in range(self.PIXEL_COUNT):
                self.np[x] = self.pixel(red, green, blue)
            self.np.write()
            time.sleep_ms(timems)
            for x in range(self.PIXEL_COUNT):
                self.np[x] = (0, 0, 0)
            self.np.write()
            time.sleep_ms(timems)

    def rgb(self, red, green, blue):
        self.same(red, green, blue)

    def colorWipe(self, red=0, green=0, blue=0, timems=50):
        """Wipe color across display a pixel at a time."""
        for i in range(self.PIXEL_COUNT):
            self.np[i] = self.pixel(red, green, blue)
            self.np.write()
            time.sleep_ms(timems)

    def color_wipe_2(self, red=0, green=0, blue=0, timems=200, direction=0):
        """Wipe color across display a pixel at a time."""
        time_per_pixel = int(timems/self.PIXEL_COUNT)
        pixel_count = self.PIXEL_COUNT
        if direction == 0:
            for i in range(self.PIXEL_COUNT):
                self.np[i] = self.pixel(red, green, blue)
                self.np.write()
                time.sleep_ms(time_per_pixel)
        elif direction == 1:
            for i in range(self.PIXEL_COUNT):
                self.np[pixel_count - i] = self.pixel(red, green, blue)
                self.np.write()
                time.sleep_ms(time_per_pixel)

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

    def rainbow_cycle(self, timems=50):
        for j in range(255):
            for i in range(self.PIXEL_COUNT):
                rc_index = (i * 256 // self.PIXEL_COUNT) + j
                self.np[i] = self.wheel(rc_index & 255)
            self.np.write()
            time.sleep_ms(timems)


    # alternate color every other light
    def alternate(self, red1=0, green1=0, blue1=0, red2=0, green2=0, blue2=0):
        for i in range(self.PIXEL_COUNT):
            if i % 2 == 0:
                self.np[i] = self.pixel(red1, green1, blue1)
            else:
                self.np[i] = self.pixel(red2, green2, blue2)
            self.np.write()


from . import picoweb
app = picoweb.WebApp(__name__)

lights = ws2811(int(configure.read_config_file("count")), grb=True)


def try_int(val):
    try:
        return int(val)
    except ValueError:
        return val


def qs_parse(qs):
    res = {}
    for el in qs.split('&'):
        key, val = el.split('=')
        res[key] = try_int(val)
    return res


@app.route("/")
def index(req, resp):
    yield from picoweb.start_response(resp)
    for item in app.get_url_map():
        yield from resp.awrite("<p>")
        yield from resp.awrite(str(item[0]))
        yield from resp.awrite("</p>")


@app.route("/color/red")
def color_red(req, resp):
    yield from picoweb.start_response(resp)
    lights.red(**qs_parse(req.qs))


@app.route("/color/green")
def color_green(req, resp):
    yield from picoweb.start_response(resp)
    lights.green(**qs_parse(req.qs))


@app.route("/color/blue")
def color_blue(req, resp):
    yield from picoweb.start_response(resp)
    lights.blue(**qs_parse(req.qs))


@app.route("/color/white")
def color_white(req, resp):
    yield from picoweb.start_response(resp)
    lights.white(**qs_parse(req.qs))


@app.route("/color/rgb")
def color_rgb(req, resp):
    yield from picoweb.start_response(resp)
    lights.rgb(**qs_parse(req.qs))


@app.route("/color/off")
def color_off(req, resp):
    yield from picoweb.start_response(resp)
    lights.off()
    yield from resp.awrite(req.qs)


@app.route("/routine/flash")
def routine_flash2(req, resp):
    yield from picoweb.start_response(resp)
    lights.flash(**qs_parse(req.qs))


@app.route("/routine/colorwipe")
def routine_colorwipe(req, resp):
    yield from picoweb.start_response(resp)
    lights.colorWipe(**qs_parse(req.qs))


@app.route("/routine/color_wipe")
def routine_color_wipe(req, resp):
    yield from picoweb.start_response(resp)
    lights.color_wipe_2(**qs_parse(req.qs))


@app.route("/routine/rainbow")
def routine_rainbow(req, resp):
    yield from picoweb.start_response(resp)
    lights.rainbow_cycle(**qs_parse(req.qs))


@app.route("/routine/alternate")
def routine_alternate(req, resp):
    yield from picoweb.start_response(resp)
    lights.rainbow_cycle(**qs_parse(req.qs))



if __name__ == "__main__":
    app.run(debug=True)

