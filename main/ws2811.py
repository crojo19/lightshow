
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
        for x in range(self.PIXEL_COUNT):
            self.np[x] = self.pixel(r, g, b)
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

    def flash(self, brightness=55):
        for y in range(self.PIXEL_COUNT):
            for x in range(self.PIXEL_COUNT):
                self.np[x] = (brightness, brightness, brightness)
            self.np.write()
            time.sleep_ms(60)
            for x in range(self.PIXEL_COUNT):
                self.np[x] = (0, 0, 0)
            self.np.write()

    def rgb(self, red, green, blue):
        self.same(red, green, blue)

    def colorWipe(self, red, green, blue, wait_ms=50):
        """Wipe color across display a pixel at a time."""
        for i in range(self.PIXEL_COUNT):
            self.np[i] = self.pixel(red, green, blue)
            self.np.write()
            time.sleep(wait_ms / 1000.0)

    def relay(self, d): # todo index out of bounds and relay config outside
        RELAYS = [machine.Pin(i, machine.Pin.OUT) for i in (12, 13, 14, 15)]
        for relay, status in d.items():
            RELAYS[int(relay)].value(int(status))


import picoweb
app = picoweb.WebApp(__name__)

print("!!!!!")
lights = ws2811(int(configure.read_config_file("count")['count']), grb=True)

def qs_parse(qs):
    parameters = {}
    ampersandSplit = qs.split("&")
    for element in ampersandSplit:
        equalSplit = element.split("=")
        print(equalSplit[1])
        parameters[equalSplit[0]] = equalSplit[1]

    return parameters

@app.route("/")
def index(req, resp):
    yield from picoweb.start_response(resp)
    yield from resp.awrite("led home")

@app.route("/color/red")
def color_red(req, resp):
    yield from picoweb.start_response(resp)
    lights.red()
    yield from resp.awrite(req.qs)


@app.route("/color/green")
def color_green(req, resp):
    yield from picoweb.start_response(resp)
    lights.green()
    yield from resp.awrite(req.qs)

@app.route("/color/blue")
def color_blue(req, resp):
    yield from picoweb.start_response(resp)
    lights.blue()
    yield from resp.awrite(req.qs)

@app.route("/color/white")
def color_white(req, resp):
    yield from picoweb.start_response(resp)
    lights.white()
    yield from resp.awrite(req.qs)

@app.route("/color/rgb")
def color_rgb(req, resp):
    yield from picoweb.start_response(resp)
    yield from resp.awrite(req.qs)

@app.route("/color/off")
def color_off(req, resp):
    yield from picoweb.start_response(resp)
    lights.off()
    yield from resp.awrite(req.qs)

@app.route("/routine/flash")
def routine_flash(req, resp):
    yield from picoweb.start_response(resp)
    lights.flash(50)
    yield from resp.awrite(req.qs)

@app.route("/routine/colorwipe")
def routine_colorwipe(req, resp):
    yield from picoweb.start_response(resp)
    lights.colorWipe(0,0,255)
    yield from resp.awrite(req.qs)

if __name__ == "__main__":
    app.run(debug=True)

