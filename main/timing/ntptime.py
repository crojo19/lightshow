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

NEW = False
# The NTP host can be configured at runtime by doing: ntptime.host = 'myhost.org'
host = "pool.ntp.org"

def time():
    NTP_QUERY = bytearray(48)
    NTP_QUERY[0] = 0x1B
    addr = socket.getaddrinfo(host, 123)[0][-1]
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # s.settimeout(1)
        res = s.sendto(NTP_QUERY, addr)
        msg = s.recv(48)
    finally:
        s.close()

    val = struct.unpack("!I", msg[40:44])[0]
    return val - NTP_DELTA, int((struct.unpack("!I", msg[44:48])[0] / 4294967296) * 1000000)


# There's currently no timezone support in MicroPython, and the RTC is set in UTC time.
def settime():
    try:
        t, micro_sec = time()
        import machine
        import utime
        print("server: " + str(host) + " Time: " + str(t))
        tm = utime.gmtime(t)
        machine.RTC().datetime((tm[0], tm[1], tm[2], tm[6] + 1, tm[3], tm[4], tm[5], micro_sec))
    except Exception as e:
        print(e)
        print(host)
        print("Issue Syncing time with server")
        pass
    return
