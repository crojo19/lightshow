import machine
import urequests
import ujson
import time
import network


def write_error(error, data=""):
    with open("error.log", "a") as logf:
        logf.write(str(time.gmtime()) + "-" + str(error) + "-" + data)


def send_error(server_ip=None, server_port=80):
    if server_ip is None:
        write_error("server_ip not in configuration file")
        return
    reset = machine.reset_cause()
    url = "http://" + str(server_ip) + ":" + str(server_port) + "/error"
    pb_headers = {'Content-Type': 'application/json'}

    errors = []
    try:
        with open("error.log") as logf:
            while True:
                error = logf.readline()
                if error == '':
                    break
                errors.append(error)
        logf = open("error.log", "w")
        logf.close()
    except OSError as e:
        write_error(e)
        pass

    (ip, other, other1, other2) = network.WLAN().ifconfig()
    try:
        if len(errors) > 0:
            data = ujson.dumps({'reset_code': reset, 'error_count': len(errors), 'error': errors, 'ip': ip})
        if len(errors) == 0:
            data = ujson.dumps({'reset_code': reset, 'error_count': 0, 'ip': ip})
        urequests.post(url, headers=pb_headers, json=data)
    except Exception as e:
        write_error(e)
        pass

