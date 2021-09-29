import time
import machine, neopixel
from . import configure


class servo:
    def __init__(self, pin=2, frequency=55):
        p2 = machine.Pin(pin)
        self.servo = machine.PWM(p2)
        self.servo.freq(frequency)
        self.servo.duty(frequency)

    def move(self, duty=None, totaltimems=0):
        if duty is None:
            return
        if totaltimems == 0:
            self.servo.duty(duty)
        elif totaltimems > 0:
            duty_delta = abs(self.servo.duty() - duty)
            if duty_delta == 0:
                return
            time_per_duty = int(totaltimems / duty_delta)
            current_duty = self.servo.duty()
            increment = -1
            if self.servo.duty() < duty:
                increment = 1
            for i in range(current_duty, duty, increment):
                self.servo.duty(i)
                time.sleep_ms(time_per_duty)



from . import picoweb

app = picoweb.WebApp(__name__)

active_servo = servo()


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


@app.route("/move", parameters="duty, totaltimems", description="")
def move(req, resp):
    yield from picoweb.start_response(resp)
    active_servo.move(**qs_parse(req.qs))


if __name__ == "__main__":
    app.run(debug=True)
