import curses
import cursesplus
import pyaudio
import math
import array
import signal
import toml
import os

CONFIG_FILE = "config.toml"

MARK = 3
PATCH = 0

DEFAULT_CONFIG = """

sample_rate = 44100
volume = 0.3
wail_cycle = 3
port_ratio_n = 5
port_ratio_d = 6
low_freq = 100
high_freq = 800
winddown_time = 10000
wavetype = 1


"""
if not os.path.isfile(CONFIG_FILE):
    with open(CONFIG_FILE,"w+") as f:
        f.write(DEFAULT_CONFIG)

with open(CONFIG_FILE) as f:
    rd = f.read()
    APPDATA = toml.loads(rd)

def sinewave(freq:float|int,index:int,hv=False) -> float:
    """Creates a singular sine wave point based on frequency"""
    return _pv(VOLUME,hv) * math.sin(2 * math.pi * freq * index / SAMPLE_RATE)

def sawtoothwave(freq: float | int, index: int,hv=False) -> float:
    t = index / SAMPLE_RATE
    return _pv(VOLUME,hv) * (2 * (t * freq - math.floor(0.5 + t * freq)))

def linsinewave(tof:float,frof:float,duration:float,index:float,hv=False):
    return _pv(VOLUME,hv) * math.sin(2 * math.pi * (frof * index + (tof - frof) * index**2 / (2 * duration)))

def linsawtooth(tof,frof,duration,index,hv=False):
    return _pv(VOLUME,hv) * (2 * ((frof * index + (tof - frof) * index**2 / (2 * duration)) - math.floor(0.5 + frof * index + (tof - frof) * index**2 / (2 * duration))))

VOLUME = APPDATA["volume"]
WAIL_CYCLE = APPDATA["wail_cycle"]
SAMPLE_RATE = APPDATA["sample_rate"]
if APPDATA["wavetype"] == 0:
    WAVE_FUNCTION = sinewave
    LN_WAVE_FUNCTION = linsinewave
elif APPDATA["wavetype"] == 1:
    WAVE_FUNCTION = sawtoothwave
    LN_WAVE_FUNCTION = linsawtooth
PORT_RATIO:float = APPDATA["port_ratio_n"]/APPDATA["port_ratio_d"]
LOW_FREQUENCY = APPDATA["low_freq"]
HIGH_FREQUENCY = APPDATA["high_freq"]
WINDDOWN_TIME = APPDATA["winddown_time"]

def writeappdate():
    APPDATA = {"sample_rate":SAMPLE_RATE,"volume":VOLUME,"wail_cycle":WAIL_CYCLE,"port_ratio_n":PORT_RATIO.as_integer_ratio()[0],"port_ratio_d":PORT_RATIO.as_integer_ratio()[1],"low_freq":LOW_FREQUENCY,"high_freq":HIGH_FREQUENCY,"winddown_time":WINDDOWN_TIME}
    if WAVE_FUNCTION == sinewave:
        APPDATA["wavetype"] = 0
    elif WAVE_FUNCTION == sawtoothwave:
        APPDATA["wavetype"] = 1
    with open(CONFIG_FILE,"w+") as f:
        f.write(toml.dumps(APPDATA))

p = pyaudio.PyAudio()
stream = p.open(format=pyaudio.paFloat32,
                channels=1,
                rate=SAMPLE_RATE,
                output=True)

def _pv(vol,hv):
    if hv:
        return vol / 2
    else:
        return vol



def gw_double(frof:int|float,tof:int|float,overms:int) -> list[float]:
    """Generates a wind up from frof to tof (frequency) over (overms) milliseconds, simulating a 10-12 port siren"""
    s1 = gen_windup(frof,tof,overms)
    s2 = gen_windup(frof*(PORT_RATIO),tof*(PORT_RATIO),overms)
    return [(s1[i]+s2[i])/2 for i in range(len(s1))]

def gen_windup(frof:int|float,tof:int|float,overms:int) -> list[float]:
    """Generates a single frequency wind up from frof to tof over overms milliseconds."""
    samples_needed = round(SAMPLE_RATE / 1000 * overms)
    t = [i / SAMPLE_RATE for i in range(samples_needed)]

    duration = overms / 1000.0
    final_samples = [
        LN_WAVE_FUNCTION(tof,frof,duration,ti)
        for ti in t
    ]
    return final_samples

def gd_double(frof:int|float,tof:int|float,overms:int) -> list[float]:
    """Generates a wind up from frof to tof (frequency) over (overms) milliseconds, simulating a 10-12 port siren"""
    s1 = gen_winddown(frof,tof,overms)
    s2 = gen_winddown(frof*(PORT_RATIO),tof*(PORT_RATIO),overms)
    return [(s1[i]+s2[i])/2 for i in range(len(s1))]

def gen_winddown(frof:int|float,tof:int|float,overms:int) -> list[float]:
    """Generates a single frequency wind down from frof to tof over overms milliseconds."""
    
    samples_needed = round(SAMPLE_RATE / 1000 * overms)
    t = [i / SAMPLE_RATE for i in range(samples_needed)]

    duration = overms / 1000.0
    final_samples = [
        LN_WAVE_FUNCTION(tof,frof,duration,ti)
        for ti in t
    ]
    return final_samples

def parse_samples(inp:list[float]) -> bytes:
    return array.array('f', inp).tobytes()

def alert_double(bodyms:int,frequency:int|float) -> list[float]:
    s1 = alert(bodyms,frequency,True)
    s2 = alert(bodyms,frequency*(PORT_RATIO),True)
    return [(s1[i]+s2[i])/2 for i in range(len(s1))]

def alert(bodyms:int,frequency:int|float,isondouble=False) -> list[float]:
    samples_needed = round(SAMPLE_RATE / 1000 * bodyms)
    final_samples:list[float] = []

    for i in range(samples_needed):
        final_samples.append(WAVE_FUNCTION(frequency,i,not isondouble))

    return final_samples
    

def signal_handler(sig, frame):
    stream.stop_stream()
    stream.close()
    p.terminate()

def chunks(xs, n):
    n = max(1, n)
    return [xs[i:i+n] for i in range(0, len(xs), n)]

def silence(ms:int) -> list[float]:
    return [0 for _ in range(round(ms/1000*SAMPLE_RATE))]

def main(stdscr):
    global WAVE_FUNCTION
    global LN_WAVE_FUNCTION
    signal.signal(signal.SIGINT, signal_handler)
    while True:
        op = cursesplus.coloured_option_menu(stdscr,["QUIT","SETTINGS","Dual Alert","Dual Wail","Dual Fast Wail","Alternate Alert","Alternate Wail","Alternate Fast Wail","Dual Whoop","Single Chimes","Single Alert","Single Wail","Single Fast Wail","Dual Chimes"],"Choose a signal",[["quit",cursesplus.RED],["settings",cursesplus.CYAN]],f"Enderbyte Programs Digital Siren Controller (EPDSC) mk. {MARK} p. {PATCH} (c) 2025 no rights reserved")
        if op == 0:
            return
        elif op == 1:
            while True:
                smen = cursesplus.optionmenu(stdscr,["Back","Wave Type"],"Settings")
                if smen == 0:
                    writeappdate()
                    break
                elif smen == 1:
                    wt = cursesplus.optionmenu(stdscr,["Back","Sine","Sawtootth"])
                    if wt == 1:
                        LN_WAVE_FUNCTION = linsinewave
                        WAVE_FUNCTION = sinewave
                    elif wt == 2:
                        LN_WAVE_FUNCTION = linsawtooth
                        WAVE_FUNCTION = sawtoothwave
        elif op == 2:
            howlong = int(cursesplus.numericinput(stdscr,message="How long in seconds should the alert last?",allowdecimals=True,allownegatives=False,minimum=0.1)*1000)
            cursesplus.displaymsg(stdscr,["Playing"],False)
            #stream.stop_stream()
            stream.write(parse_samples(gw_double(LOW_FREQUENCY,HIGH_FREQUENCY,3000) + alert_double(howlong,HIGH_FREQUENCY) + gd_double(HIGH_FREQUENCY,LOW_FREQUENCY,WINDDOWN_TIME)))
            #stream.write()
            #stream.start_stream()
        elif op == 3:
            cursesplus.displaymsg(stdscr,["Playing"],False)
            fnarray = gw_double(LOW_FREQUENCY,HIGH_FREQUENCY,3000)
            
            for _ in range(WAIL_CYCLE):
                fnarray += alert_double(2000,HIGH_FREQUENCY)
                fnarray += gd_double(HIGH_FREQUENCY,200,4000)
                
                fnarray += gw_double(200,HIGH_FREQUENCY,3000)

            fnarray += alert_double(2000,HIGH_FREQUENCY)
            fnarray += gd_double(HIGH_FREQUENCY,LOW_FREQUENCY,WINDDOWN_TIME)

            stream.write(parse_samples(fnarray))
        elif op == 4:
            cursesplus.displaymsg(stdscr,["Playing"],False)
            fnarray = gw_double(LOW_FREQUENCY,HIGH_FREQUENCY,3000)
            fnarray += alert_double(2000,HIGH_FREQUENCY)
            for _ in range(WAIL_CYCLE):
                
                fnarray += gd_double(HIGH_FREQUENCY,HIGH_FREQUENCY-200,1000)
                
                fnarray += gw_double(HIGH_FREQUENCY-200,HIGH_FREQUENCY,1000)

            fnarray += alert_double(2000,HIGH_FREQUENCY)
            fnarray += gd_double(HIGH_FREQUENCY,LOW_FREQUENCY,WINDDOWN_TIME)

            stream.write(parse_samples(fnarray))
        elif op == 5:
            cursesplus.displaymsg(stdscr,["Playing"],False)
            fnarray = gw_double(LOW_FREQUENCY,622.25,3000)
            fnarray += alert_double(500,622.25)
            for _ in range(WAIL_CYCLE*2):
                
                fnarray += alert(500,622.25)
                fnarray += alert(500,622.25*(PORT_RATIO))
            fnarray += alert_double(500,622.25) 
            fnarray += gd_double(622.25,LOW_FREQUENCY,WINDDOWN_TIME)

            stream.write(parse_samples(fnarray))

        elif op == 6:
            cursesplus.displaymsg(stdscr,["Generating..."],False)
            #First, I will create the high stream and the low stream. Then I will commit them together
            histream = [a/2 for a in gen_windup(LOW_FREQUENCY,HIGH_FREQUENCY,3000)]
            lostream = [a/2 for a in gen_windup(LOW_FREQUENCY*(PORT_RATIO),HIGH_FREQUENCY*(PORT_RATIO),3000)]

            for _ in range(WAIL_CYCLE):
                #histream += alert(2000,1200)
                histream += [a/2 for a in gen_winddown(HIGH_FREQUENCY,200,4000)]
                
                histream += [a/2 for a in gen_windup(200,HIGH_FREQUENCY,3000)]

                #lostream += alert(2000,1200*(PORT_RATIO))
                lostream += [a/2 for a in gen_winddown(HIGH_FREQUENCY*(PORT_RATIO),200*(PORT_RATIO),4000)]
                
                lostream += [a/2 for a in gen_windup(200*(PORT_RATIO),HIGH_FREQUENCY*(PORT_RATIO),3000)]

            fnarray:list[float] = []
            chunksize = math.floor(0.5 * SAMPLE_RATE) #Copy hi-lo in chunks
            chunkedhi = chunks(histream,chunksize)
            chunkedlo = chunks(lostream,chunksize)

            selector = False
            sell = [chunkedhi,chunkedlo]
            for i in range(len(chunkedhi)):
                fnarray += sell[int(selector)][i]
                selector = not selector
            
            fnarray += gd_double(HIGH_FREQUENCY,100,WINDDOWN_TIME)

            cursesplus.displaymsg(stdscr,["Playing"],False)
            stream.write(parse_samples(fnarray))
        elif op == 7:
            cursesplus.displaymsg(stdscr,["Generating..."],False)
            #First, I will create the high stream and the low stream. Then I will commit them together
            histream = [a/2 for a in gen_windup(LOW_FREQUENCY,HIGH_FREQUENCY,3000)]
            lostream = [a/2 for a in gen_windup(LOW_FREQUENCY*(PORT_RATIO),HIGH_FREQUENCY*(PORT_RATIO),3000)]

            for _ in range(WAIL_CYCLE):
                #histream += alert(2000,1200)
                histream += [a/2 for a in gen_winddown(HIGH_FREQUENCY,HIGH_FREQUENCY-200,1000)]
                
                histream += [a/2 for a in gen_windup(HIGH_FREQUENCY-200,HIGH_FREQUENCY,1000)]

                #lostream += alert(2000,1200*(PORT_RATIO))
                lostream += [a/2 for a in gen_winddown(HIGH_FREQUENCY*(PORT_RATIO),HIGH_FREQUENCY-200*(PORT_RATIO),1000)]
                
                lostream += [a/2 for a in gen_windup(HIGH_FREQUENCY-200*(PORT_RATIO),HIGH_FREQUENCY*(PORT_RATIO),1000)]

            fnarray:list[float] = []
            chunksize = math.floor(0.5 * SAMPLE_RATE) #Copy hi-lo in chunks
            chunkedhi = chunks(histream,chunksize)
            chunkedlo = chunks(lostream,chunksize)

            selector = False
            sell = [chunkedhi,chunkedlo]
            for i in range(len(chunkedhi)):
                fnarray += sell[int(selector)][i]
                selector = not selector
            
            fnarray += gd_double(HIGH_FREQUENCY,100,WINDDOWN_TIME)

            cursesplus.displaymsg(stdscr,["Playing"],False)
            stream.write(parse_samples(fnarray))
        
        elif op == 8:
            cursesplus.displaymsg(stdscr,["Generating"],False)
            fnarray = []
            for _ in range(WAIL_CYCLE*2):
                fnarray += gw_double(LOW_FREQUENCY,HIGH_FREQUENCY,1500)
                fnarray += silence(500)
            cursesplus.displaymsg(stdscr,["Playing"],False)
            stream.write(parse_samples(fnarray))
        
        elif op == 9:
            cursesplus.displaymsg(stdscr,["Playing"],False)
            fnarray = []
            NOTE_FSHARP = 740
            NOTE_GSHARP = 830.61
            NOTE_ASHARP = 932.33
            NOTE_CSHARP = 554.37
            fnarray += alert(750,NOTE_FSHARP)
            fnarray += alert(750,NOTE_ASHARP)
            fnarray += alert(750,NOTE_GSHARP)
            fnarray += alert(750,NOTE_CSHARP)
            fnarray += silence(750)
            fnarray += alert(750,NOTE_FSHARP)
            fnarray += alert(750,NOTE_GSHARP)
            fnarray += alert(750,NOTE_ASHARP)
            fnarray += alert(750,NOTE_FSHARP)
            fnarray += silence(750)
            fnarray += alert(750,NOTE_ASHARP)
            fnarray += alert(750,NOTE_FSHARP)
            fnarray += alert(750,NOTE_GSHARP)
            fnarray += alert(750,NOTE_CSHARP)
            fnarray += silence(750)
            fnarray += alert(750,NOTE_CSHARP)
            fnarray += alert(750,NOTE_GSHARP)
            fnarray += alert(750,NOTE_ASHARP)
            fnarray += alert(750,NOTE_FSHARP)
            fnarray += silence(750)
            stream.write(parse_samples(fnarray))
        elif op == 10:
            howlong = int(cursesplus.numericinput(stdscr,message="How long in seconds should the alert last?",allowdecimals=True,allownegatives=False,minimum=0.1)*1000)
            cursesplus.displaymsg(stdscr,["Playing"],False)
            stream.write(parse_samples(
                gen_windup(LOW_FREQUENCY,HIGH_FREQUENCY,3000)+
                alert(howlong,HIGH_FREQUENCY,True)+
                gen_winddown(HIGH_FREQUENCY,LOW_FREQUENCY,WINDDOWN_TIME)
            ))
        elif op == 11:
            cursesplus.displaymsg(stdscr,["Playing"],False)
            fnarray = gen_windup(LOW_FREQUENCY,HIGH_FREQUENCY,3000)
            
            for _ in range(WAIL_CYCLE):
                fnarray += alert(2000,HIGH_FREQUENCY,True)
                fnarray += gen_winddown(HIGH_FREQUENCY,200,4000)
                
                fnarray += gen_windup(200,HIGH_FREQUENCY,3000)

            fnarray += alert(2000,HIGH_FREQUENCY,True)
            fnarray += gen_winddown(HIGH_FREQUENCY,LOW_FREQUENCY,WINDDOWN_TIME)

            stream.write(parse_samples(fnarray))
        elif op == 12:
            cursesplus.displaymsg(stdscr,["Playing"],False)
            fnarray = gen_windup(LOW_FREQUENCY,HIGH_FREQUENCY,3000)
            
            for _ in range(WAIL_CYCLE):
                fnarray += gen_winddown(HIGH_FREQUENCY,HIGH_FREQUENCY-200,1000)
                
                fnarray += gen_windup(HIGH_FREQUENCY-200,HIGH_FREQUENCY,1000)

            fnarray += alert(2000,HIGH_FREQUENCY,True)
            fnarray += gen_winddown(HIGH_FREQUENCY,LOW_FREQUENCY,WINDDOWN_TIME)

            stream.write(parse_samples(fnarray))
        elif op == 13:
            cursesplus.displaymsg(stdscr,["Playing"],False)
            tape1 = []
            tape2 = []

            tape1.extend(alert(750,622.25))
            tape1.extend(alert(750,783.99))
            tape1.extend(alert(750,698.46))
            tape1.extend(alert(750,466.16))
            tape1.extend(silence(750))

            tape1.extend(alert(750,622.25))
            tape1.extend(alert(750,698.46))
            tape1.extend(alert(750,783.99))
            tape1.extend(alert(750,622.25))
            tape1.extend(silence(750))

            tape1.extend(alert(750,783.99))
            tape1.extend(alert(750,622.25))
            tape1.extend(alert(750,689.46))
            tape1.extend(alert(750,466.16))
            tape1.extend(silence(750))

            tape1.extend(alert(750,466.16))
            tape1.extend(alert(750,689.46))
            tape1.extend(alert(750,783.99))
            tape1.extend(alert(750,622.25))
            tape1.extend(silence(750))

            tape2.extend(alert(750,392))
            tape2.extend(alert(750,622.25))
            tape2.extend(alert(750,466.16))
            tape2.extend(alert(750,392))
            tape2.extend(silence(750))

            tape2.extend(alert(750,392))
            tape2.extend(alert(750,466.16))
            tape2.extend(alert(750,622.25))
            tape2.extend(alert(750,392))
            tape2.extend(silence(750))
            
            tape2.extend(alert(750,466.16))
            tape2.extend(alert(750,392))
            tape2.extend(alert(750,415.3))
            tape2.extend(alert(750,293.66))
            tape2.extend(silence(750))

            tape2.extend(alert(750,392))
            tape2.extend(alert(750,466.16))
            tape2.extend(alert(750,622.25))
            tape2.extend(alert(750,392))
            tape2.extend(silence(750))

            stream.write(parse_samples([(tape1[i] + tape2[i]) / 2 for i in range(len(tape1))]))

curses.wrapper(main)

#Shutdown
stream.stop_stream()
stream.close()
p.terminate()