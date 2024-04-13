# SAEQ TREMOLO: Source Audio EQ2 Tremolo Interface

Turn your equalizer into a tremolo.

## Features

* Waveforms: Triangle, Square, Sine, Sawtooth, Reverse Sawtooth, Hill, Valley
* Rate Slider
* Depth Slider
* On-off switch

## Usage

Debian Dependencies:

* python3-numpy, for math
* python3-mido and python3-rtmidi, for MIDI communication
* python3-gi, for the GUI

Running:

1. Connect your device to your EQ2 via MIDI.
2. Set `self.debug = False` within the script
3. Run `./tremolo.py` in a terminal.

By default, this effects the second EQ channel and assumes the EQ is on MIDI channel 1, its default. Modify the script if your setup differs.

If you're using Linux, you can edit `tremolo.desktop` to use the path corresponding to your system. Then you can copy it to ~/.local/share/applications, and follow it to see where everything else should go. This then lets you tap or click on an app instead of using a terminal.


## Potential Future Features
* Select between Channels 1, 2, or both
* Pick a rhythm / pattern tremolo. Add a drop-down next to the button, or have two drop downs side by side on top.
* Random waveshape. Certainly no more shapes than the TWA Side Step, which has six shapes and the reversals of two shapes for eight options. This would be the last one.
* Duty Cycle slider. [TTP's Helix Review](https://tremolo-project.blogspot.com/2017/09/line-6-helix-all-tremolo-modes-examined.html) seems to be a decent starting point. I think this would require the WAVEFORM_SERIES to perhaps be functions that take a duty param to squeeze the waveform into the duty and leave the rest at zero. This could make the app slower.
* A switch to increase rate range into ring modulation territory?
* Rhythm ratios / division. I don't know how this would mesh with pattern trem,
  which to me is more important. Maybe just have them in the same
  menu, or maybe find a way to mathematically combine them for more flexibilty.
* Real-time audio.

## Features That Would Require More Hardware
* Expression pedal
* Engage footswitch (though you could do this with just the expression pedal)
* Tap Tempo footswitch

## Goals
* One page program for easy deployment. 
* Only use dependencies available via apt on Debian's/Mobian's repositories. No pip.
* Good user interface

## Non-Goals
* Harmonic Tremolo. I'd like to have it, and it *is* possible with the EQ2. However, the resulting harmonic trem would be shallow. Moreover, I'd loose some EQ bands, or else perhaps have to reverse-engineer the Neuro protocol to access the existing EQ settings so as to not loose them. I'd rather buy a Pisound or the JHS Harmonic Trem than reverse-engineer this. 
* Envelope-control. I'd need to buy more hardware.
* Panning. This could be easy with a switch and then an offset message stream to the other channel. But I only have one amp, and I plan on using both channel inputs for equalization. This is what I think the code might change to:

```
self.set_trim1 = lambda v: mido.Message("control_change", channel=0, control=1, value=v)  
self.set_trim2 = lambda v: mido.Message("control_change", channel=0, control=2, value=v)  
length = len(series)  
half = int(length/2)  
for i in range(length):  
	self.outport.send(self.set_trim1(series[i]))  
	if panning:  
		offset = i+half if i+half < length else i-half
		self.outport.send(self.set_trim2(series[offset]))  
	time.sleep(period_and_state[0])  
```

Better would likely be  

```
self.set_trim1 = lambda v: mido.Message("control_change", channel=0, control=1, value=v)  
self.set_trim2 = lambda v: mido.Message("control_change", channel=0, control=2, value=v)  
for level in series:  
	self.outport.send(self.set_trim1(level))  
	if panning:
		self.outport.send(self.set_trim2(127 - level))  
	time.sleep(period_and_state[0])  
```
