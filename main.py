from main.ota_updater import OTAUpdater


def download_and_install_update_if_available():
    o = OTAUpdater('https://github.com/crojo19/lightshow')
    # o.check_for_update_to_install_during_next_reboot()
    o.download_and_install_update_if_available('', '')


def start():
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
    from main import wifimgr
    wlan = wifimgr.get_connection("CC_", "password")
    if wlan is None:
        print("Could not initialize the network connection.")
        while True:
            pass
    print("ESP Connected to Network - " + str(wlan.ifconfig()[0]))

    download_and_install_update_if_available()
    start()


boot()



# Connect to Wifi


# import upip
# upip.install('picoweb')
# upip.install('pycopy-ulogging')
# Memory Cleanup


# Main Code



