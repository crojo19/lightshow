from . import picoweb
from . import admin
import ujson

site = picoweb.WebApp(__name__)
# always load admin module
site.mount("/admin", admin.app)

admin.update_server()

# if module in config load module
from . import ws2811
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

site.run(host='0.0.0.0',debug=True, port=80)