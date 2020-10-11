from . import picoweb
from . import admin


site = picoweb.WebApp(__name__)
# always load admin module
site.mount("/admin", admin.app)

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

site.run(host='0.0.0.0',debug=True, port=80)