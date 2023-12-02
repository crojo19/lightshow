import uasyncio as a
import json
from machine import Pin
import machine, neopixel
import gc
import ubinascii
from .ws import AsyncWebsocketClient
import network as net
from . import configure
from .ws2811 import ws2811
from . import application
import json

(ip, other, other1, other2) = net.WLAN().ifconfig()
IPADDRESS = ip

async def main():
    tasks = [read_loop()]
    await a.gather(*tasks)

led = ws2811(1, pin=48, order="RGB")

print("Create WS instance...")
# create instance of websocket-poc
ws = AsyncWebsocketClient(configure.read_config_file('ws_socket_delay_ms'))
print("Created.")

# this lock will be used for data interchange between loops --------------------
# better choice is to use uasynio.queue, but it is not documented yet
lock = a.Lock()
# this array stores messages from server
data_from_ws = []
config = {}
config['ws_server'] = configure.read_config_file('ws_server')

# ------------------------------------------------------
async def color(color):
    led.rgb(color)


async def run_command(cmd: dict):
    global lock
    global data_from_ws
    global ws
    command = cmd['cmd']
    if cmd['cmd'] == "run_lightshow":
        print("Command: run_lightshow")
        if ws is not None:
            if await ws.open():
                loop = a.get_event_loop()
                await a.sleep_ms(2500)
                loop.create_task(application.instructions_request_ws(ws))
                loop.create_task(application.lightshow(cmd['starttime']))
            gc.collect()
    elif cmd['cmd'] == "NextCommand":
        print("Command: NextCommand")
        print(f"data: {cmd['data']}")
        await application.instructions_process_ws(cmd['data'])
    elif cmd['cmd'] == "color":
        await color(cmd['data'])
        print("Command: color")
    elif cmd['cmd'] == "ws_close":
        print("Command: ws_close")
        await ws.close()
        await a.sleep_ms(500)
    else:
        print("Command: " + command + " not found")


# ------------------------------------------------------
# Task for read loop
async def read_loop():
    global config
    global lock
    global data_from_ws

    while True:
        gc.collect()
        try:
            print("Handshaking...")
            # connect to test socket server with random client number
            mac = ubinascii.hexlify(net.WLAN().config('mac'), '-').decode()
            print("{}{}".format(config["ws_server"], mac))
            if not await ws.handshake("{}{}".format(config["ws_server"], mac)):
                raise Exception('Handshake error.')
            print("...handshaked.")

            mes_count = 0
            while await ws.open():
                data = await ws.recv()
                print("Data: " + str(data) + "; " + str(mes_count))
                try:
                    if data is not None:
                        data = json.loads(data)
                        print("loaded json")
                        await run_command(data)
                except:
                    print("issue parsing json")
                data_from_ws = []
                # close socket for every 10 messages (even ping/pong)
                if mes_count == 20:
                    await ws.close()
                    print("ws is open: " + str(await ws.open()))
                mes_count += 1

                if data is not None:
                    await lock.acquire()
                    data_from_ws.append(data)
                    lock.release()

                await a.sleep_ms(50)
        except Exception as ex:
            print("Exception: {}".format(ex))
            await a.sleep(1)

