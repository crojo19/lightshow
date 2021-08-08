from . import picoweb
from . import admin
from . import configure
from .timing import ntptime
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
# always load admin module
site.mount("/admin", admin.app)

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
    pass

# create schedule
# schedule = {}

# if module in config load module
from . import ws2811
from .ws2811 import lights
site.mount("/led", ws2811.app)

@site.route("/", parameters="None")
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


@site.route("/status", parameters="", description="Return 200 if available")
def status(req, resp):
    yield from picoweb.start_response(resp, content_type="application/json")
    yield from resp.awrite(ujson.dumps({'status': 200}))


@site.route("/config", parameters="None")
def config(req, resp):
    yield from picoweb.start_response(resp, content_type="application/json")

    data = configure.read_config_file()
    import ubinascii
    import network
    data.update({'mac_address': ubinascii.hexlify(network.WLAN().config('mac'), ':').decode()})
    (ip, other, other1, other2) = network.WLAN().ifconfig()
    data.update({'ip_address': ip})

    from .ota_updater import OTAUpdater
    o = OTAUpdater(configure.read_config_file("update_repo"), github_auth_token=configure.read_config_file('update_repo_token'))
    current_version = o.get_current_version()
    data.update({'installed_version': current_version})

    import os
    uname = os.uname()
    data.update({'sysname': uname.sysname})
    data.update({'release': uname.release})
    data.update({'version': uname.version})
    data.update({'machine': uname.machine})

    from . import wifimgr
    wifi = wifimgr.read_profiles()
    data.update({'wifi': wifi})

    items = {}
    i = 0
    for item in site.get_url_map():
        if str(item[0]).startswith('/'):
            items.update({i: str(item[0])})
            i = i + 1
    for mount in site.get_mounts():
        for item in mount.get_url_map():
            if not str(item[0]).endswith("/"):
                items.update({i: str(item[0])})
                i = i + 1
    data.update({'admin_routes': items})
    yield from resp.awrite(ujson.dumps(data))


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

@site.route("/run_lightshow", parameters="Not Sure")
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
    loop.create_task(lightshow(d['starttime']))
    loop.create_task(instructions(d['server'], "/lighshow/nextcommand"))


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
    lights.rgb(55, 0, 0)
    time.sleep_ms(50)
    lights.rgb(0, 55, 0)
    time.sleep_ms(50)
    lights.rgb(0, 0, 55)
    time.sleep_ms(50)
    lights.rgb(0, 0, 0)


def end_show():
    lights.rgb(25, 25, 25)


def run_command(command):
    try:
        if command['command_type'] == "lights":
            getattr(lights, command['function'])(**command['parameters'])
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


site.run(host='0.0.0.0', debug=False, port=80)
