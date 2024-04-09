import time
import sys

import mido


if __name__ == '__main__':
    # https://stackoverflow.com/a/29501455
    inport = mido.open_input('Source Audio EQ2 MIDI 1')
    outport = mido.open_output('Source Audio EQ2 MIDI 1')  # todo: try removing this line

    # todo: this might be off by a factor of four?
    bpm = int(sys.argv[1])
    hz = bpm / 60
    period = 1/hz  # in seconds
    cc_period = period / 128*2 # volume granularity permits 128 options, but we have to go both up and down.

    # todo: rename this function
    tk2v = lambda v: mido.Message('control_change', channel=0, control=2,value=v)

    # There is likely a better way
    trim_levels = list(range(127)) + list(range(127, 0, -1))
    
    while(True):
        # user can always ^C
        for l in trim_levels:
            outport.send(tk2v(l))
            time.sleep(cc_period)

    
