from . import picoweb
from . import configure
from .timing import ntptime
from .error import write_error, send_error
import ujson
import time
import urequests
import gc
import uasyncio as asyncio

ROUTINE = []
ROUTINE_COMPLETE = False
ROUTINE_LENGTH = 0
DEBUG = False
LAST_COMMAND = 0
MAX_QUEUE = 50 if configure.read_config_file('max_routine_queue') is None else int(configure.read_config_file('max_routine_queue'))

site = picoweb.WebApp(__name__)

# if module in config load module
modules = ""
try:
    modules = configure.read_config_file('modules')
    modules = modules.split(',')
except Exception as e:
    write_error(e)
    pass

# always load admin module
from . import admin
print("Module admin Loading")
site.mount("/admin", admin.app)

try:
    if 'ws2811' in modules:
        print("Module ws2811 Loading")
        from . import ws2811
        from .ws2811 import lights
        site.mount("/led", ws2811.app)
    if 'servo' in modules:
        print("Module Servo Loading")
        from . import servo as servo_mod
        from.servo import servo
        site.mount("/servo", servo_mod.app)
except Exception as e:
    write_error(e)
    pass


@site.route("/", parameters="None", description="Show Site Map")
def index(req, resp):
    yield from picoweb.start_response(resp)
    for item in site.get_url_map():
        yield from resp.awrite("<p>")
        yield from resp.awrite(str(item[0]))
        yield from resp.awrite("</p>")
    for mount in site.get_mounts():
        for item in mount.get_url_map():
            if not str(item[0]).endswith("/"):
                yield from resp.awrite("<p>")
                yield from resp.awrite(str(mount.url) + str(item[0]))
                yield from resp.awrite("</p>")


@site.route("/status", parameters="None", description="Returns json 200")
def status(req, resp):
    yield from picoweb.start_response(resp, content_type="application/json")
    yield from resp.awrite(ujson.dumps({'status': 200}))


@site.route("/config", parameters="None", description="Returns device configuraration")
def config(req, resp):
    yield from picoweb.start_response(resp, content_type="application/json")
    yield from resp.awrite(str(admin.config()))


@site.route("/run_lightshow", parameters="starttime, server", description="Initiate light show function on device")
def run_lightshow(req, resp):
    yield from picoweb.start_response(resp, content_type="application/json")
    data = {}
    data.update({'received': 200})
    yield from resp.awrite(ujson.dumps(data))
    global ROUTINE_COMPLETE
    ROUTINE_COMPLETE = False
    global LAST_COMMAND
    global ROUTINE_LENGTH
    d = qs_parse(req.qs)
    LAST_COMMAND = 0
    ROUTINE_LENGTH = 0
    loop = asyncio.get_event_loop()
    # Wait for server to build lightshow index
    time.sleep_ms(200)
    print(d)
    loop.create_task(lightshow(d['starttime']))
    loop.create_task(instructions(d['server'], "/lightshow/nextcommand"))


async def lightshow(start_time):
    global ROUTINE_COMPLETE
    global ROUTINE
    global ROUTINE_LENGTH

    while ROUTINE_LENGTH == 0:
        await asyncio.sleep_ms(0)
    if ROUTINE_LENGTH > 0:
        print("################")
        print("local_time: " + str(time.time_ns()))
        print("start_time: " + str(start_time))
        preshow()
        while True:
            command = ""
            while ROUTINE_LENGTH > 0:
                item = ROUTINE.pop(0)
                ROUTINE_LENGTH = len(ROUTINE)
                command = item[1]
                command_time = int(item[0])
                # wait till 9ms before command expected
                while time.time_ns() < command_time - 9000000:
                    # 200 ms then request to server
                    if time.time_ns() < command_time - 200000000:
                        await asyncio.sleep_ms(0)
                ms_delta = (time.time_ns() - command_time) / 1000000
                if DEBUG: print(
                    "Delta ms: " + str(ms_delta) + " : time:" + str(time.time_ns()) + " : expectedTime:" + str(
                        command_time) + " : Command: " + str(command))
                # if delta is less than 75 ms run command
                if ms_delta < 75:
                    run_command(command)
                else:
                    print(">75ms delay:{} {} ".format(str(command_time), command))
                if len(ROUTINE) == 0:
                    await asyncio.sleep_ms(0)
            if ROUTINE_COMPLETE:
                print("Routine Complete")
                break
    end_show()


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


def preshow():
    try:
        lights.rgb(55, 0, 0)
        time.sleep_ms(50)
        lights.rgb(0, 55, 0)
        time.sleep_ms(50)
        lights.rgb(0, 0, 55)
        time.sleep_ms(50)
        lights.rgb(0, 0, 0)
    except Exception as e:
        write_error(e)
        pass
    return


def end_show():
    try:
        lights.rgb(25, 25, 25)
    except Exception as es:
        write_error(es)
        pass


def run_command(command):
    try:
        if command['command_type'] == "lights":
            getattr(lights, command['function'])(**command['parameters'])
        elif command['command_type'] == "servo":
            getattr(servo, command['function'])(**command['parameters'])
    except Exception as e:
        print(str(e))
        print("ERROR - Command Failed to run: " + str(command))
        pass


async def instructions(server_ip, path):
    global ROUTINE
    global ROUTINE_COMPLETE
    global LAST_COMMAND
    global ROUTINE_LENGTH
    routine = []
    url = "http://" + server_ip + path
    pb_headers = {'Content-Type': 'application/json'}
    while not ROUTINE_COMPLETE:
        while ROUTINE_LENGTH >= MAX_QUEUE - 1:
            await asyncio.sleep_ms(0)
        number_of_commands = MAX_QUEUE - ROUTINE_LENGTH
        data = ujson.dumps({'limit': number_of_commands, 'last_command': str(LAST_COMMAND)})
        retry_max = 5
        i = 0
        gc.collect()
        while len(routine) == 0:
            try:
                response = urequests.post(url, headers=pb_headers, json=data)
                if i > 0:
                    asyncio.sleep_ms(i * 100)
                routine_json = response.json()
                response.close()
                routine = list(sorted(routine_json.items()))
            except Exception as e:
                print("Failed to retrieve commands: {}".format(e))
                pass
            if i >= retry_max + 1:
                print("Max Retry reached")
                ROUTINE_COMPLETE = True
                break
            i = i + 1
        if len(routine) == 1:
            if routine[0][0] is 'end':
                ROUTINE_COMPLETE = True
        if ROUTINE_COMPLETE:
            print("Last Command Received")
            await asyncio.sleep_ms(0)
        else:
            if len(routine) > 0:
                LAST_COMMAND = int(routine[-1][0])
                ROUTINE.extend(routine)
                routine = []
                ROUTINE_LENGTH = len(ROUTINE)
                await asyncio.sleep_ms(0)


def active_routine_check():
    loop = asyncio.get_event_loop()
    loop.create_task(lightshow(time.time_ns()))
    loop.create_task(instructions(str(configure.read_config_file('server_ip')), "/lightshow/nextcommand"))


def initilize():
    # initial Communication
    try:
        print("Checking in with server")
        admin.update_server()
    except:
        print("unable to contact server")
        pass
    try:
        # sync time with server
        print("Syncing with time server")
        ntptime.host = str(configure.read_config_file('server_ip'))
        ntptime.settime()
    except:
        print("unable to update time")
        pass
    try:
        send_error(server_ip=str(configure.read_config_file('server_ip')))
    except Exception as e:
        write_error(e)

initilize()
active_routine_check()
site.run(host='0.0.0.0', debug=False, port=80)
