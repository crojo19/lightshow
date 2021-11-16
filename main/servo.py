import time
import machine
from . import configure

class Servo:
    def __init__(self, pin=5, frequency=55):
        p2 = machine.Pin(pin)
        self.servo = machine.PWM(p2)
        self.max_duty = int(configure.read_config_file("servo_max"))
        self.min_duty = int(configure.read_config_file("servo_min"))
        self.up_duty = int(configure.read_config_file("servo_up"))
        self.down_duty = int(configure.read_config_file("servo_down"))

        self.servo.freq(frequency)
        self.servo.duty(self.down_duty)

    def move(self, duty=None, totaltimems=0):
        if duty is None:
            return
        elif duty > self.max_duty:
            return
        elif duty < self.min_duty:
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

    def up(self, totaltimems=0):
        self.move(duty=self.up_duty, totaltimems=totaltimems)

    def down(self, totaltimems=0):
        self.move(duty=self.down_duty, totaltimems=totaltimems)


from . import picoweb

app = picoweb.WebApp(__name__)

servo = Servo()


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
    servo.move(**qs_parse(req.qs))


@app.route("/up", parameters="totaltimems", description="")
def up(req, resp):
    yield from picoweb.start_response(resp)
    servo.up(**qs_parse(req.qs))


@app.route("/down", parameters="totaltimems", description="")
def move(req, resp):
    yield from picoweb.start_response(resp)
    servo.down(**qs_parse(req.qs))


if __name__ == "__main__":
    app.run(debug=True)
