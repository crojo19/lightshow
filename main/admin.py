from . import picoweb
import urequests
import ubinascii
import network
import machine
from .ota_updater import OTAUpdater
from . import configure
from . import wifimgr
import time
import ujson
from .timing import ntptime


app = picoweb.WebApp(__name__)

@app.route("/")
def index(req, resp):
    yield from picoweb.start_response(resp)
    for item in app.get_url_map():
        yield from resp.awrite("<p>")
        yield from resp.awrite(str(item[0]))
        yield from resp.awrite("</p>")

@app.route("/reboot")
def reboot(req, resp):
    yield from picoweb.start_response(resp)
    yield from resp.awrite("rebooting")
    machine.reset()

@app.route("/getcurrentversion")
def getcurrentversion(req, resp):
    yield from picoweb.start_response(resp)
    o = OTAUpdater(configure.read_config_file("update_repo"))
    current_version = o.get_current_version()
    yield from resp.awrite(current_version)


@app.route("/getlatestversion")
def getlatestversion(req, resp):
    yield from picoweb.start_response(resp)
    o = OTAUpdater(configure.read_config_file("update_repo"))
    latest_version = o.get_latest_version()
    yield from resp.awrite(latest_version)


@app.route("/checkforupdate")
def checkforupdate(req, resp):
    yield from picoweb.start_response(resp)
    o = OTAUpdater(configure.read_config_file("update_repo"))
    update_available, current_version, latest_version = o.check_for_update()
    if update_available:
        yield from resp.awrite("update available...")
        yield from resp.awrite("Current Version: " + str(current_version))
        yield from resp.awrite("Latest Version: " + str(latest_version))
        yield from resp.awrite("Reboot to update")
    else:
        yield from resp.awrite("no update available")
        yield from resp.awrite("Current Version: " + str(current_version))
        yield from resp.awrite("Latest Version: " + str(latest_version))

@app.route("/updatesoftware")
def updatesoftware(req, resp):
    yield from picoweb.start_response(resp)
    o = OTAUpdater(configure.read_config_file("update_repo"))
    update_available, current_version, latest_version = o.check_for_update_to_install_during_next_reboot()
    if update_available:
        yield from resp.awrite("<p>update available</p>")
        yield from resp.awrite("<p>Current Version: " + str(current_version) + "</p>")
        yield from resp.awrite("<p>Latest Version: " + str(latest_version) + "</p>")
        yield from resp.awrite("rebooting")
        machine.reset()

    else:
        yield from resp.awrite("<p>no update available</p>")
        yield from resp.awrite("<p>Current Version: " + str(current_version) + "</p>")
        yield from resp.awrite("<p>Latest Version: " + str(latest_version) + "</p>")


@app.route("/time/set")
def config_get(req, resp):
    yield from picoweb.start_response(resp)
    # try:
        # sync time with server
    print("Syncing with time server")
    if str(req.qs) == "":
        ntptime.host = str(configure.read_config_file('server_ip'))
    else:
        d = qs_parse(req.qs)
        ntptime.host = str(d['ntp'])
    ntptime.settime()
    timess = str(time.time_ns())
    print(timess)
    yield from resp.awrite(timess)



@app.route("/config/get")
def config_get(req, resp):
    yield from picoweb.start_response(resp)
    yield from resp.awrite("<p>configuration: </p>")
    yield from resp.awrite("<p>" + str(configure.read_config_file()) + "</p>")


def try_int(val):
    try:
        return int(val)
    except ValueError:
        return val


def qs_parse(qs):
    if qs is None:
        return {}
    res = {}
    for el in qs.split('&'):
        key, val = el.split('=')
        res[key] = try_int(val)
    return res

# TODO
@app.route("/config/update")
def config_update(req, resp):
    yield from picoweb.start_response(resp)
    d = qs_parse(req.qs)
    yield from resp.awrite(configure.put_config_items(d))
    time.sleep(2)
    machine.reset()


@app.route("/config/add_ssid")
def config_add_ssid(req, resp):
    yield from picoweb.start_response(resp)
    d = qs_parse(req.qs)
    wlan = wifimgr.add_profile_item(d['ssid'], d['password'])
    time.sleep(2)
    machine.reset()


@app.route("/status/updateserver")
def status_updateserver(req, resp):
    yield from picoweb.start_response(resp)
    update_server()

def update_server():
    # perform post to server IP @ port in config with configuration data
    url = "http://" + str(configure.read_config_file('server_ip')) + "/device/check_in/" +\
          str(configure.read_config_file('name'))
    print(url)
    pb_headers = {
        'Content-Type': 'application/json'
    }
    data = config()
    # data = ujson.dumps(config())
    response = urequests.post(url, headers=pb_headers, json=data)


@app.route("/status")
def status(req, resp):
    yield from picoweb.start_response(resp)
    yield from resp.awrite(str(config()))


def config():
    # Create based on config file
    data = configure.read_config_file()
    # add Mac address
    data.update({'mac_address': ubinascii.hexlify(network.WLAN().config('mac'), ':').decode()})
    # add ip address
    (ip, other, other1, other2) = network.WLAN().ifconfig()
    data.update({'ip_address': ip})
    # get current installed app version
    o = OTAUpdater(configure.read_config_file("update_repo"))
    current_version = o.get_current_version()
    data.update({'installed_version': current_version})
    import os
    uname = os.uname()
    data.update({'sysname': uname.sysname})
    data.update({'release': uname.release})
    data.update({'version': uname.version})
    data.update({'machine': uname.machine})
    
    wifi = wifimgr.read_profiles()
    data.update({'wifi': wifi})
    items = {}
    i = 0
    for item in app.get_url_map():
        if str(item[0]).startswith('/'):
            items.update({i: str(item[0])})
        i = i+1
    data.update({'admin_routes': items})
    return data


if __name__ == "__main__":
    app.run(debug=True)
