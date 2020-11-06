from . import picoweb
from . import admin
import ujson
import time
import ucollections
import urequests
from .timing import ntptime

site = picoweb.WebApp(__name__)
# always load admin module
site.mount("/admin", admin.app)

try:
    admin.update_server()
except:
    print("unable to contact server")
    pass

# create schedule
schedule = {}

# if module in config load module
from . import ws2811
from .ws2811 import lights
site.mount("/led", ws2811.app)

@site.route("/")
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


@site.route("/status")
def status(req, resp):
    yield from picoweb.start_response(resp, content_type="application/json")
    data = {}
    data.update({'status': 200})
    yield from resp.awrite(ujson.dumps(data))


@site.route("/config")
def config(req, resp):
    yield from picoweb.start_response(resp, content_type="application/json")
    from . import configure
    data = configure.read_config_file()
    import ubinascii
    import network
    data.update({'mac_address': ubinascii.hexlify(network.WLAN().config('mac'), ':').decode()})
    (ip, other, other1, other2) = network.WLAN().ifconfig()
    data.update({'ip_address': ip})

    from .ota_updater import OTAUpdater
    o = OTAUpdater(configure.read_config_file("update_repo"))
    current_version = o.get_current_version()
    data.update({'installed_version': current_version})

    import os
    data.update({'os_info': os.uname()})

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


@site.route("/run_lightshow")
def status(req, resp):
    routine_complete = False
    routine = {}

    # sync time with server
    ntptime.host = "192.168.152.3"
    ntptime.settime()

    # TODO parse start_time from request
    start_time = time.time_ns() + 10000000000

    # get first X commands
    routine, end_of_show = get_next_instructions("192.168.152.3","/lighshow/nextcommand", 5)
    # print(routine)
    if len(routine) > 0:
        print("local_time: " + str(time.time_ns()))
        print("start_time: " + str(start_time))
        print("################")
        preshow()
        # check start time
        while time.time_ns() < start_time:
            True
        print("####### START #########")
        print("local_time: " + str(time.time_ns()))
        print("start_time: " + str(start_time))
        while True:
            for item in routine:
                str_key = str(item)
                int_key = int(item)
                while time.time_ns() < int_key:
                    True
                print("Delta ms: " + str((time.time_ns() - int_key)/1000000) + " : time:" + str(time.time_ns()) + " : expectedTime:" + str_key + " : Command: " + str(routine[str_key]))
                run_command(routine[str_key])
            # get next commands
            routine, end_of_show = get_next_instructions("192.168.152.3", "/lighshow/nextcommand", 5)
            if end_of_show:
                end_show()
                break

    yield from picoweb.start_response(resp, content_type="application/json")
    data = {}
    data.update({'status': 200})
    yield from resp.awrite(ujson.dumps(data))


def preshow():
    lights.rgb(55, 0, 0)
    time.sleep_ms(50)
    lights.rgb(0, 55, 0)
    time.sleep_ms(50)
    lights.rgb(0, 0, 55)
    time.sleep_ms(50)
    lights.rgb(0, 0, 0)

def end_show():
    lights.rgb(0, 0, 0)

def run_command(command):
    try:
        if command['command_type'] == "lights":
            getattr(lights, command['function'])(**command['parameters'])
    except Exception as e:
        print(str(e))
        print("ERROR - Command Failed to run: " + str(command))
        pass


def get_next_instructions(server_ip, path, number_of_commands):
    routine = {}
    end_of_show = False
    url = "http://" + server_ip + path
    print(url)
    pb_headers = {
        'Content-Type': 'application/json'
    }
    data = ujson.dumps({'limit': number_of_commands})
    try:
        response = urequests.post(url, headers=pb_headers, json=data)
        routine = response.json()
        routine = ucollections.OrderedDict(sorted(routine.items()))
    except:
        print("unable to get next set of commands")
        end_of_show = True
        pass
    if len(routine) == 0:
        end_of_show = True
    if end_of_show:
        print("end of show reached")
    return routine, end_of_show


site.run(host='0.0.0.0', debug=True, port=80)
