from main.ota_updater import OTAUpdater


def update_software():
    from main import configure
    o = OTAUpdater(configure.read_config_file("update_repo"), github_auth_token=configure.read_config_file('update_repo_token'))
    if str(o.get_current_version()) == "0.0.0":
        o.set_version_on_reboot(o.get_latest_version())
    o.update_software()


def start_app():
    import gc
    gc.collect()
    try:
        from main import application
        application()
    except Exception as e:
        print(str(e))
        import machine
        machine.reset()


def boot():
    from main import wifimgr, configure
    wlan = wifimgr.get_connection(configure.read_config_file("setup_wifi_prefix"), configure.read_config_file("setup_wifi_password"), configure.read_config_file("name"))
    while wlan is None:
        print("WLAN not yet connected")
    print("ESP Connected to Network - " + str(wlan.ifconfig()[0]))

    update_software()
    start_app()


boot()


