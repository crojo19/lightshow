from . import picoweb
from . import configure
from .timing import ntptime
from .error import write_error, send_error
import ujson
import time
from time import ticks_add, ticks_diff
import urequests
import gc
import uasyncio as asyncio
import network
from machine import Timer
import ubinascii
import machine

tim0 = Timer(0)
ROUTINE = []
ROUTINE_COMPLETE = False
ROUTINE_LENGTH = 0
DEBUG = False
LAST_COMMAND = 0
MAC_ADDRESS = ubinascii.hexlify(network.WLAN().config('mac'), ':').decode()

MAX_QUEUE = 50 if configure.read_config_file('max_routine_queue') is None else int(configure.read_config_file('max_routine_queue'))

(ip, other, other1, other2) = network.WLAN().ifconfig()
IPADDRESS = ip

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
from .admin import set_time
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


@site.route("/run_lightshow", parameters="starttime, server, port", description="Initiate light show function on device")
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
    loop.create_task(instructions(d['server'], d['port'], "/lightshow/nextcommand"))


async def lightshow(start_time):
    global ROUTINE_COMPLETE
    global ROUTINE
    global ROUTINE_LENGTH

    set_time()
    while ROUTINE_LENGTH == 0:
        await asyncio.sleep_ms(100)
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
                command_time = int(item[0])
                module = item[1]
                function = item[2]
                parameters = item[3]
                # wait till 9ms before command expected
                while time.time_ns() < command_time - 9000000:
                    # 200 ms then request to server
                    if time.time_ns() < command_time - 200000000:
                        # if DEBUG: print("awaiting more commands 200ms before next request")
                        await asyncio.sleep_ms(0)
                ms_delta = (time.time_ns() - command_time) / 1000000
                if DEBUG: print(
                    "Delta ms: " + str(ms_delta) + " : time:" + str(time.time_ns()) + " : expectedTime:" + str(
                        command_time) + " : Command: " + str(function))
                # if delta is less than 75 ms run command
                if ms_delta < 75:
                    run_command(module, function, parameters)
                else:
                    print(">75ms delay:{} {} ".format(str(command_time), function))
                if len(ROUTINE) == 0:
                    if DEBUG: print("awaiting more commands with none in queue")
                    await asyncio.sleep_ms(50)
            if DEBUG:
                print(f"main while true loop")
            if ROUTINE_COMPLETE:
                print("Routine Complete")
                break
            else:
                await asyncio.sleep_ms(50)
    end_show()


@site.route("/run_queue", parameters="queue_name, server, port", description="Initiate light show function on device")
def run_queue(req, resp):
    yield from picoweb.start_response(resp, content_type="application/json")
    data = {'received': 200}
    yield from resp.awrite(ujson.dumps(data))
    d = qs_parse(req.qs)
    loop = asyncio.get_event_loop()
    print(d)
    loop.create_task(queue(d['server'], d['port'], d['queue_name'], "/queue/next"))


async def queue(server_ip, server_port, queue_name, path):
    routine = None
    url = "http://" + server_ip + ":" + str(server_port) + path
    pb_headers = {'Content-Type': 'application/json'}

    data = ujson.dumps({'ip': IPADDRESS, 'queue': queue_name, 'id': 0})
    gc.collect()
    while True:
        try:
            response = urequests.post(url, headers=pb_headers, json=data)
            routine = response.json()
            print(routine)
            response.close()
        except Exception as e:
            print("Failed to retrieve commands: {}".format(e))
            pass
        if routine is not None:
            if 'time' in routine:
                while time.time_ns() < routine['time'] - 9000000:
                    time.sleep_ms(1)
            # print(time.time_ns())
            if time.time_ns() < routine['time']:
                run_command(routine['command']['command_type'], routine['command']['function'], routine['command']['parameters'])
            if "id" in routine:
                if routine['id'] == -1:
                    break
            if 'time' not in routine:
                if "sleepms" in routine['command']:
                    time.sleep_ms(routine['command']['sleepms'])
                data = ujson.dumps({'ip': IPADDRESS, 'queue': queue_name, 'id': routine['id']})
            else:
                data = ujson.dumps({'ip': IPADDRESS, 'queue': queue_name, 'id': routine['id'], 'time': routine['time']})
            routine = None
            gc.collect()


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


def run_command(module, function, parameters):
    try:
        if module == "lights":
            getattr(lights, function)(**parameters)
        elif module == "servo":
            getattr(servo, function)(**parameters)
    except Exception as e:
        print(str(e))
        print("ERROR - Command Failed to run: " + str(function))
        pass


async def instructions(server_ip, server_port, path):
    global ROUTINE
    global ROUTINE_COMPLETE
    global LAST_COMMAND
    global ROUTINE_LENGTH
    routine = []
    url = ""
    if int(server_port) == 80:
        url = "http://" + server_ip + path
    else:
        url = "http://" + server_ip + ":" + str(server_port) + path

    if DEBUG: print(f"{url}")
    pb_headers = {'Content-Type': 'application/json'}
    while not ROUTINE_COMPLETE:
        if DEBUG: print(f"instructions: top of loop")
        while ROUTINE_LENGTH >= MAX_QUEUE - 1:
            if DEBUG: print(f"instructions: await queue is max length")
            await asyncio.sleep_ms(0)
        number_of_commands = MAX_QUEUE - ROUTINE_LENGTH
        data = ujson.dumps({'ip': IPADDRESS, 'limit': number_of_commands, 'last_command': str(LAST_COMMAND)})
        retry_max = 5
        i = 0
        gc.collect()
        if DEBUG: print(f"number of requested commands {str(number_of_commands)}")
        while len(routine) == 0:
            gc.collect()
            try:
                if DEBUG: print("Making Request for more commands")
                response = urequests.post(url, headers=pb_headers, json=data)
                if i > 0:
                    asyncio.sleep_ms(i * 200)
                if DEBUG: print("getting response")
                routine = response.json()
                if DEBUG: print(f"Routine Length = {str(len(routine))}")
            except Exception as e:
                print("Failed to retrieve commands: {}".format(e))
                pass
            if i >= retry_max + 1:
                print("Max Retry reached rebooting")
                machine.reset()
                ROUTINE_COMPLETE = True
                break
            i = i + 1
        if DEBUG: print(f"in loop")
        if len(routine) == 1:
            if routine[0][0] is 'end':
                ROUTINE_COMPLETE = True
        if ROUTINE_COMPLETE:
            print("Last Command Received")
            try:
                response.close()
            except Exception:
                print("response close failed")
                pass
            return
        else:
            if len(routine) > 0:
                if DEBUG: print(f"extend routine")
                LAST_COMMAND = int(routine[-1][0])
                ROUTINE.extend(routine)
                routine = []
                ROUTINE_LENGTH = len(ROUTINE)
                await asyncio.sleep_ms(0)


def active_routine_check():
    print("checking for active show")
    loop = asyncio.get_event_loop()
    loop.create_task(lightshow(time.time_ns()))
    loop.create_task(instructions(str(configure.read_config_file('server_ip')), configure.read_config_file('check_in_port'), "/lightshow/nextcommand"))


def initilize():
    # initial Communication
    try:
        print("Checking in with server")
        check_in_url = configure.read_config_file('check_in_url')
        admin.update_server(check_in_url=check_in_url)
    except:
        print("unable to contact server")
        pass
    try:
        print("Checking state")
        state()
    except Exception as e:
        print(e)
        write_error(e)
        print("unable to check state")
        pass
    try:
        # sync time with server
        print("Syncing with time server")
        ntptime.host = str(configure.read_config_file('server_ip'))
        ntptime.settime()
    except Exception as e:
        print(e)
        write_error(e)
        print("unable to update time")
        pass
    try:
        send_error(server_ip=str(configure.read_config_file('server_ip')), server_port=configure.read_config_file('check_in_port'))
    except Exception as e:
        write_error(e)


def state(check_in_url="https://ssg0hg9fta.execute-api.us-west-2.amazonaws.com/dev/device/state"):
    print(check_in_url)
    pb_headers = {'Content-Type': 'application/json'}
    data = ujson.dumps({'serial': MAC_ADDRESS, 'max_msg': 50})
    response = urequests.post(check_in_url, headers=pb_headers, json=data)
    response_data = ujson.loads(response.text)
    response.close()
    print(response_data)
    if response_data['len'] > 0:
        for item in ujson.loads(response_data['data']):
            print(item)
            aws_run_command(item)



def aws_run_command(command):
    # command [module, function, parameter, time]
    if len(command) == 4:
        deadline = ticks_add(time.ticks_ms(), command[3])
    else:
        deadline = ticks_add(time.ticks_ms(), 1)
    # ADMIN Functions
    if command[0] == 0:
        admin.run_command(command)
    # WS2811 Functions
    elif command[0] == 1:
        ws2811.run_command(command)
    # Servo Functions
    elif command[0] == 2:
        servo.run_command(command)
    # Lightshow Functions
    elif command[0] == 3:
        servo.run_command(command)
    # Bad Command
    else:
        print(f"UNASSIGNED - UNKNOWN - {command}")
    while ticks_diff(deadline, time.ticks_ms()) > 0:
        time.sleep_ms(10)

print("initilizing application")
initilize()
print("initilizing active routine check")
active_routine_check()
print("initilizing website")
site.run(host='0.0.0.0', debug=False, port=80)
