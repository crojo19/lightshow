import picoweb
app = picoweb.WebApp(__name__)

@app.route("/")
def index(req, resp):
    yield from picoweb.start_response(resp)
    yield from resp.awrite("Admin_Home")

@app.route("/reboot")
def reboot(req, resp):
    yield from picoweb.start_response(resp)
    yield from resp.awrite("rebooting")
    import machine
    machine.reset()

@app.route("/getcurrentversion")
def getcurrentversion(req, resp):
    yield from picoweb.start_response(resp)
    from .ota_updater import OTAUpdater
    o = OTAUpdater('https://github.com/crojo19/lightshow')
    current_version = o.get_current_version()
    yield from resp.awrite("Current Version: " + current_version)

@app.route("/checkforupdate")
def checkforupdate(req, resp):
    yield from picoweb.start_response(resp)
    from .ota_updater import OTAUpdater
    o = OTAUpdater('https://github.com/crojo19/lightshow')
    update_available, current_version, latest_version = o.check_for_update_to_install_during_next_reboot()
    if update_available:
        yield from resp.awrite("update available...")
        yield from resp.awrite("Current Version: " + str(current_version))
        yield from resp.awrite("Latest Version: " + str(latest_version))
        yield from resp.awrite("Reboot to update")
    else:
        yield from resp.awrite("no update available")
        yield from resp.awrite("Current Version: " + str(current_version))
        yield from resp.awrite("Latest Version: " + str(latest_version))


@app.route("/config/get")
def index(req, resp):
    yield from picoweb.start_response(resp)
    from . import configure
    yield from resp.awrite("configuration" + str(configure.read_config_file(None)))


if __name__ == "__main__":
    app.run(debug=True)