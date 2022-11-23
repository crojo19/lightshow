try:
    import usocket as socket
except:
    import socket
try:
    import ustruct as struct
except:
    import struct
import time as tm
# (date(2000, 1, 1) - date(1900, 1, 1)).days * 24*60*60
NTP_DELTA = 3155673600

# The NTP host can be configured at runtime by doing: ntptime.host = 'myhost.org'
host = "pool.ntp.org"

def time():
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1B
    addr = socket.getaddrinfo(host, 123)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(1)
        res = s.sendto(NTP_QUERY, addr)
        msg = s.recv(48)
    finally:
        s.close()

    val = struct.unpack("!I", msg[40:44])[0]
    return val - NTP_DELTA, int((struct.unpack("!I", msg[44:48])[0] / 4294967296) * 1000000)

def time_raw():
    import machine
    import utime
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1B
    addr = socket.getaddrinfo(host, 123)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx_time = None
    rx_time = None
    try:
        s.settimeout(1)
        t1 = utime.time_ns()
        res = s.sendto(NTP_QUERY, addr)
        msg = s.recv(48)
        t4 = utime.time_ns()
    finally:
        s.close()
    t2 = (struct.unpack("!I", msg[32:36])[0] + (struct.unpack("!I", msg[36:40])[0] / 4294967296)-NTP_DELTA) * 1000000000
    t3 = (struct.unpack("!I", msg[40:44])[0] + (struct.unpack("!I", msg[44:48])[0] / 4294967296)-NTP_DELTA) * 1000000000
    t3_microseconds = int((struct.unpack("!I", msg[44:48])[0] / 4294967296) * 1000000)
    # offset = ((t2 - t1) + (t3 - t4))/2
    delay = (t4 - t1) - (t3 - t2)

    # print("t1: " + str(t1))
    # print("t2: " + str(int(t2)))
    # print("t3: " + str(int(t3)))
    # print("t4: " + str(t4))
    # print("offset: " + str(int(offset/1000)) + " microseconds")
    # print("delay: " + str(int(delay/1000)) + " microseconds")
    microseconds = int(t3_microseconds + delay/1000)
    tm = utime.gmtime(struct.unpack("!I", msg[40:44])[0]- NTP_DELTA)
    # print(machine.RTC().datetime())
    machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], microseconds))
    # print(machine.RTC().datetime())
    return


# There's currently no timezone support in MicroPython, and the RTC is set in UTC time.
def settime():
    try:
        time_raw()
    except Exception:
        try:
            t, micro_sec = time()
            import machine
            import utime
            print("server: " + str(host) + " Time: " + str(t))
            tm = utime.gmtime(t)
            machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], micro_sec))
        except Exception:
            print("Issue Syncing time with server")
            pass
        pass
    return
