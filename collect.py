import argparse
import os
import time
import re
import numpy as np
from telnetlib import Telnet
from serial import Serial

# TODO detect end of capture (second trigger)
# Config
SAVE_PATH = "capture/"

MICROCONTROLLER_PORT = "/dev/ttyACM0"
MICROCONTROLLER_BAUD = "9600"

IP_REGEX = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$")

# Rigol cst
PORT = 5555
BIG_WAIT = 10
SMALLWAIT = 1
COMPANY = 0
MODEL = 1
SERIAL = 2
READ_STEP = 250000  # Number of point readeable at once in byte mode
CHANNELS = ["CHAN1", "CHAN2", "CHAN3", "CHAN4"]

def send_to_microcontroller(payload, serial):
    serial.write(payload.encode())

def payload_generator():
    pass  # TODO
    return ["PLOP\n", "plap\n"]

def command(tn, scpi, decode=True, wait=True):
    answer_wait_s = 1
    response = ""
    while response != b"1\n":
        tn.write(b"*OPC?\n")  # previous operation(s) has completed ?
        response = tn.read_until(b"\n", 1)  # wait max 1s for an answer

    tn.write(scpi.encode() + b"\n")
    if not wait:
        return
    response = tn.read_until(b"\n", answer_wait_s)
    if decode:
        response = response.decode().strip()
    return response

def get_trace(tn, chan, start):
    command(tn, ":WAV:SOUR "+ chan, wait=False)
    command(tn, ":WAV:MODE RAW", wait=False)  #  TODO math channel accept only normal
    command(tn, ":WAV:FORM BYTE", wait=False)

    info = command(tn, ":WAV:PRE?").strip().split(",")
    mdepth = int(info[2])
    yor = float(info[8])
    yref = float(info[9])
    yinc = float(info[7])
    print(mdepth)

    datas = np.empty(0)
    for i in range(start, mdepth, READ_STEP):
        stop = min(mdepth, i + READ_STEP - 1)
        command(tn, ":WAV:STAR " + str(i), wait=False)
        command(tn, ":WAV:STOP " + str(stop), wait=False)
        raw = command(tn, ":WAV:DATA?", decode=False).strip()
        raw = raw[11:]
        datas = np.append(datas, list(raw))

    datas = (datas - yor - yref) * yinc
    return datas

def data_loop(tn, savefile, serial, channels):
    for payload in payload_generator():
        command(tn, ":SING")
        send_to_microcontroller(payload, serial)

        while int(command(tn, ":TRIG:POS?")) < 0:
            pass
        start = command(tn, ":TRIG:POS?")
        print(start)

        for chan in channels:
            print(chan)
            print(get_trace(tn, chan, int(start)))
            # TODO: save

def test_ip(ip):
    if not IP_REGEX.match(ip):
        print("This is not a valid ip.")
        exit(-1)
    if os.system("ping -c 1 " + ip + " > /dev/null") != 0:
        print("Can't ping oscilloscope.\n")
        exit(-1)


def main(ip, path, port, baud):
    test_ip(ip)
    tn = Telnet(ip, PORT)
    serial = Serial(port, baud)

    instrument_id = command(tn, "*IDN?").strip()
    if "RIGOL TECHNOLOGIES" not in instrument_id or\
        "DS1" not in instrument_id:
            print("The instrument id isn't from a Rigol device "
                    "({})".format(instrument_id))
            exit(-1)
    print("Id of oscilloscope: {}.".format(instrument_id))

    savefilename = time.strftime("%Y-%m-%d_%H:%M:%S", time.localtime())  # TODO set extension
    print(savefilename)

    channels = []
    for chan in CHANNELS:
        if command(tn, ":{}:DISP?".format(chan)) == "1":
            print(chan)
            channels.append(chan)

    freq = float(command(tn, ":ACQ:SRAT?").strip())
    print("Data sampeling frequency: {:,}.".format(freq))
    with open(os.path.join(path, savefilename), "w") as savefile:
        data_loop(tn, savefile, serial, channels)



if __name__ == "__main__":
    parser = argparse.ArgumentParser(
            description='Connect to a Rigol ocsilloscope to gather traces \
                    while performing side channel attack.')
    parser.add_argument('ip', help="Ip of the Oscilloscope to connect to.")
    parser.add_argument("-d", "--path",
            help="Path to save the traces, default : `{}`.".format(SAVE_PATH),
            default=SAVE_PATH)
    parser.add_argument("-p", "--port",
            help="The file used to connect to the microcontroller, "
            "default: {}".format(MICROCONTROLLER_PORT),
            default=MICROCONTROLLER_PORT)
    parser.add_argument("-b", "--baud",
            help="The baudrate used to connect to the microcontroller, "
            "default: {}".format(MICROCONTROLLER_BAUD),
            default=MICROCONTROLLER_BAUD)
    args = parser.parse_args()
    main(args.ip, args.path, args.port, args.baud)
