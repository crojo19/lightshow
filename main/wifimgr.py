import network
import ubinascii
import gc
from . import picoweb
import ujson
import time

ap_ssid = None
ap_password = None
ap_device_name = None
ap_authmode = 3  # WPA2

NETWORK_PROFILES = 'wifi.dat'

wlan_ap = network.WLAN(network.AP_IF)
wlan_sta = network.WLAN(network.STA_IF)
site = picoweb.WebApp(__name__)


def get_connection(ssid_prefix, password, device_name):
    gc.collect()
    """return a working WLAN(STA_IF) instance or None"""
    global ap_ssid
    if password is None:
        password = "password"
    if ssid_prefix is None:
        ssid_prefix = "CC_"
    global ap_device_name
    if device_name is None:
        ap_device_name = ""
    else:
        ap_device_name = "_" + str(device_name)
    ap_ssid = ssid_prefix + ubinascii.hexlify(network.WLAN().config('mac'), ':').decode() + ap_device_name
    global ap_password
    ap_password = password
    # First check if there already is any connection:
    if wlan_sta.isconnected():
        return wlan_sta

    connected = False
    try:
        # ESP connecting to WiFi takes time, wait a bit and try again:
        time.sleep(3)
        if wlan_sta.isconnected():
            return wlan_sta

        # Read known network profiles from file
        profiles = read_profiles()

        # Search WiFis in range
        wlan_sta.active(True)
        networks = wlan_sta.scan()

        AUTHMODE = {0: "open", 1: "WEP", 2: "WPA-PSK", 3: "WPA2-PSK", 4: "WPA/WPA2-PSK"}
        for ssid, bssid, channel, rssi, authmode, hidden in sorted(networks, key=lambda x: x[3], reverse=True):
            ssid = ssid.decode('utf-8')
            encrypted = authmode > 0
            print("ssid: %s chan: %d rssi: %d authmode: %s" % (ssid, channel, rssi, AUTHMODE.get(authmode, '?')))
            if encrypted:
                if ssid in profiles:
                    password = profiles[ssid]
                    connected = do_connect(ssid, password)
                else:
                    print("skipping unknown encrypted network")
            else:
                pass  # don't connect to OPEN networks
            if connected:
                return wlan_sta
    except OSError as e:
        print("exception", str(e))
    # start web server for connection manager:
    if not connected:
        wlan_sta.active(True)
        wlan_ap.active(True)
        wlan_ap.config(essid=ap_ssid, password=ap_password, authmode=ap_authmode)
        site.run(host='0.0.0.0', debug=False, port=80)


def read_profiles():
    try:
        with open(NETWORK_PROFILES) as f:
            lines = f.readlines()
        profiles = {}
        for line in lines:
            ssid, password = line.strip("\n").split(";")
            profiles[ssid] = password
        return profiles
    except:
        return {}


def write_profiles(profiles):
    lines = []
    for ssid, password in profiles.items():
        lines.append("%s;%s\n" % (ssid, password))
    with open(NETWORK_PROFILES, "w") as f:
        f.write(''.join(lines))


def add_profile_item(ssid, password):
    try:
        profiles = read_profiles()
    except OSError:
        profiles = {}
    profiles[ssid] = password
    write_profiles(profiles)


def delete_profile_item(ssid):
    try:
        profiles = read_profiles()
    except OSError:
        profiles = {}
    profiles.pop(ssid)
    write_profiles(profiles)


def do_connect(ssid, password):
    wlan_sta.active(True)
    wlan_sta.disconnect()
    if wlan_sta.isconnected():
        return True
    print('Trying to connect to %s...' % ssid)
    wlan_sta.connect(ssid, password)
    for retry in range(100):
        connected = wlan_sta.isconnected()
        if connected:
            break
        time.sleep(0.1)
        print('.', end='')
    if connected:
        print('\nConnected. Network config: ', wlan_sta.ifconfig())
    else:
        print('\nFailed. Not Connected to: ' + ssid)
    return connected


@site.route("/")
def wifi_config(req, resp):
    yield from picoweb.start_response(resp, content_type="application/json")
    data = {}
    received_data = True
    d = qs_parse(req.qs)
    if d.get('ssid') is None:
        received_data = False
        yield from resp.awrite(ujson.dumps({'expected_keys': ['ssid', 'password']}))
    if d.get('password') is None:
        received_data = False
        yield from resp.awrite(ujson.dumps({'expected_keys': ['ssid', 'password']}))
    data.update({'received data': 'yes'})
    if received_data:
        if do_connect(d['ssid'], d['password']):
            add_profile_item(d['ssid'], d['password'])
            yield from resp.awrite(ujson.dumps({'connection_status': 'successful'}))
            wlan_ap.active(False)
            time.sleep_ms(1500)
            import machine
            machine.reset()
        yield from resp.awrite(ujson.dumps({'connection_status': 'Unable to connect'}))
        
        
@site.route("/reboot")
def reboot(req, resp):
    yield from picoweb.start_response(resp, content_type="application/json")
    yield from resp.awrite(ujson.dumps({'reboot': 'yes'}))
    wlan_ap.active(False)
    time.sleep_ms(1500)
    import machine
    machine.reset()


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
