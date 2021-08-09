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
import uasyncio as asyncio


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
    loop = asyncio.get_event_loop()
    loop.create_task(reboot_ms(1000))

async def reboot_ms(time_ms):
    await asyncio.sleep_ms(time_ms)
    machine.reset()

@app.route("/currentversion")
def getcurrentversion(req, resp):
    yield from picoweb.start_response(resp)
    o = OTAUpdater(configure.read_config_file("update_repo"), github_auth_token=configure.read_config_file('update_repo_token'))
    current_version = o.get_current_version()
    yield from resp.awrite(current_version)


@app.route("/latestversion")
def getlatestversion(req, resp):
    yield from picoweb.start_response(resp)
    o = OTAUpdater(configure.read_config_file("update_repo"), github_auth_token=configure.read_config_file('update_repo_token'))
    latest_version = o.get_latest_version()
    yield from resp.awrite(latest_version)


@app.route("/checkforupdate")
def checkforupdate(req, resp):
    yield from picoweb.start_response(resp)
    o = OTAUpdater(configure.read_config_file("update_repo"), github_auth_token=configure.read_config_file('update_repo_token'))
    update_available, current_version, latest_version = o.check_for_update()
    if update_available:
        yield from resp.awrite("update available...")
        yield from resp.awrite("<p>Current Version: " + str(current_version) + "</>")
        yield from resp.awrite("Latest Version: " + str(latest_version) + "</p>")
        yield from resp.awrite("Reboot to update")
    else:
        yield from resp.awrite("no update available")
        yield from resp.awrite("Current Version: " + str(current_version))
        yield from resp.awrite("Latest Version: " + str(latest_version))

@app.route("/updatesoftware")
def updatesoftware(req, resp):
    yield from picoweb.start_response(resp)
    o = OTAUpdater(configure.read_config_file("update_repo"), github_auth_token=configure.read_config_file('update_repo_token'))
    update_available, current_version, latest_version = o.check_for_update()
    if update_available:
        yield from resp.awrite("<p>update available</p>")
        yield from resp.awrite("<p>Current Version: " + str(current_version) + "</p>")
        yield from resp.awrite("<p>Latest Version: " + str(latest_version) + "</p>")
        yield from resp.awrite("rebooting")
        o.set_version_on_reboot(latest_version)
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


@app.route("/config/get")
def config_get(req, resp):
    yield from picoweb.start_response(resp)
    yield from resp.awrite("<p>configuration: </p>")
    yield from resp.awrite("<p>" + str(configure.read_config_file()) + "</p>")


@app.route("/config/update")
def config_update(req, resp):
    yield from picoweb.start_response(resp)
    parsed_url = urldecode(req.qs)
    print(parsed_url)
    # parsed_url = unquote(parsed_url)
    d = qs_parse(parsed_url)

    if 'dataTable-1_length' in d:
        del d['dataTable-1_length']
    if '''b"b'dataTable-1_length''' in d:
        del d['''b"b'dataTable-1_length''']

    print(d)
    yield from resp.awrite(configure.put_config_items(d))
    time.sleep(2)
    machine.reset()


def urldecode(stuff):
    dic = {"%21":"!","%22":'"',"%23":"#","%24":"$","%26":"&","%27":"'","%28":"(","%29":")","%2A":"*","%2B":"+","%2C":",","%2F":"/","%3A":":","%3B":";","%3D":"=","%3F":"?","%40":"@","%5B":"[","%5D":"]","%7B":"{","%7D":"}"}
    for k,v in dic.items():
        stuff=stuff.replace(k,v)
    return stuff


@app.route("/config/add_ssid")
def config_add_ssid(req, resp):
    yield from picoweb.start_response(resp)
    d = qs_parse(req.qs)
    wifimgr.add_profile_item(d['ssid'], d['password'])
    time.sleep(2)
    machine.reset()


@app.route("/config/remove_ssid")
def config_add_ssid(req, resp):
    yield from picoweb.start_response(resp)
    d = qs_parse(req.qs)
    wifimgr.delete_profile_item(d['ssid'])
    time.sleep(2)
    machine.reset()


@app.route("/status/updateserver")
def status_updateserver(req, resp):
    yield from picoweb.start_response(resp)
    config = configure.read_config_file()
    try:
        update_server(port=config["check_in_port"], check_in_url=config["check_in_url"])
    except:
        print("check_in_port or check_in_url not in config file using defaults")
        update_server()


def update_server(port=80, check_in_url="/device/check_in/"):
    # perform post to server IP @ port in config with configuration data
    url = "http://" + str(configure.read_config_file('server_ip')) + ":" + str(port) + check_in_url +\
          str(configure.read_config_file('name'))
    print(url)
    pb_headers = {
        'Content-Type': 'application/json'
    }
    data = config()
    response = urequests.post(url, headers=pb_headers, json=data)
    response.close()


@app.route("/status")
def status(req, resp):
    yield from picoweb.start_response(resp)
    yield from resp.awrite(str(config()))


def config():
    data = {}
    data.update({'config_file': configure.read_config_file()})

    data['network'] = {}
    data['network'].update({'mac_address': ubinascii.hexlify(network.WLAN().config('mac'), ':').decode()})
    (ip, other, other1, other2) = network.WLAN().ifconfig()
    data['network'].update({'ip_address': ip})
    wifi = wifimgr.read_profiles()
    data['network'].update({'wifi': wifi})

    data['software'] = {}
    o = OTAUpdater(configure.read_config_file("update_repo"),
                   github_auth_token=configure.read_config_file('update_repo_token'))
    data['software'].update({'installed_version': o.get_current_version()})

    data['hardware'] = {}
    import os
    uname = os.uname()
    data['hardware'].update({'sysname': uname.sysname})
    data['hardware'].update({'machine': uname.machine})
    data['os'] = {}
    data['os'].update({'release': uname.release})
    data['os'].update({'version': uname.version})

    data['routes'] = {}
    items = {}
    i = 0
    for item in app.get_url_map():
        if str(item[0]).startswith('/'):
            items.update({i: str(item[0])})
        i = i+1
    data['routes'].update({'admin_routes': items})
    data.update({'config_version': "0.2"})
    return ujson.dumps(data)


if __name__ == "__main__":
    app.run(debug=True)
