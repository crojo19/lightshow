import picoweb
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
    yield from resp.awrite("root")

site.run(host='0.0.0.0',debug=True, port=80)