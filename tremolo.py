import time
import threading
import sys
from typing import Final

import mido
from numpy import linspace, pi, cos

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

'''I plan on "shipping" this as a one-file script for
simplicity. Breaking out into files and modules is better, but python
deployment has been painful for me and I'd rather this than experience
it again.'''


# Series of trim level values. Default is Triangle wave.
# Sine as it is here matches up well with triangle.
WAVEFORM_SERIES: Final = {
    "triangle": tuple(range(127)) + tuple(range(127, 0, -1)),
    "square": tuple([0]*127 + [127]*127),
    "sine": tuple(map(round, cos(linspace(-pi, pi, 254)) * 64 + 64)),
    "sawtooth": tuple(map(round, linspace(0, 127, 254)))}

# idk if python will let me change the array I'm iterating over, but that's what I
# plan on doing. In C I'd have no trouble so long as the length stays the same.
tril, sqrl, sinl, sawl = map(len, WAVEFORM_SERIES.values())
assert(tril == sqrl == sinl == sawl)

# Cast to list for mutation by depth
# This must be the only assignment to series. Yes, it's global. Both classes need to see it. GUI alone modifies it. 
series = list(WAVEFORM_SERIES['triangle'])

def bpm2period(bpm):
    '''Convert beats per minute from rate slider to the MIDI CC
    message period in seconds.'''
    hz = bpm / 60
    period = 1/hz
    return period / len(series)

period_and_state = [bpm2period(1), True] # There is a better way, beyond my knowledge. 

class GUI(Gtk.ApplicationWindow):

    # https://github.com/Taiko2k/GTK4PythonTutorial
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.set_default_size(600, 250)
        self.set_title("MyApp")

        # Main layout containers
        self.box1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.set_child(self.box1)  # Horizontal box to window

        # Jonathan attempts to add a drop down
        self.waveform_dropdown = Gtk.DropDown.new_from_strings([
            'triangle',
            'square',
            'sine',
            'sawtooth'])
        # https://discourse.gnome.org/t/example-of-gtk-dropdown-with-search-enabled-without-gtk-expression/12748
        self.waveform_dropdown.connect("notify::selected-item", self.waveform_selected)
        self.box1.append(self.waveform_dropdown)
        
        self.rate = Gtk.Scale()
        self.rate.set_digits(0)  # Number of decimal places to use
        self.rate.set_range(1, 200)
        self.rate.set_draw_value(True)  # Show a label with current value
        self.rate.set_value(1)  # Sets the current value/position
        period_and_state[0] = bpm2period(self.rate.get_value())
        self.rate.connect('value-changed', self.rate_changed)
        self.box1.append(self.rate)

        self.depth = Gtk.Scale()
        self.depth.set_digits(0)  # Number of decimal places to use
        self.depth.set_range(0, 127)
        self.depth.set_draw_value(True)  # Show a label with current value
        self.depth.set_value(127)  # Sets the current value/position
        self.depth_value = self.depth.get_value()
        self.depth.connect('value-changed', self.depth_changed)
        self.box1.append(self.depth)

        # Add a box containing a switch
        self.switch_event = threading.Event()
        self.switch_box = Gtk.CenterBox(orientation=Gtk.Orientation.HORIZONTAL)
        self.switch = Gtk.Switch()
        switch_default = True # todo: remove this line of code and...
        self.switch.set_active(switch_default)
        period_and_state[1] = switch_default # ... set this directly from switch state
        self.switch.connect("state-set", self.switch_switched)  # Let's trigger a function on state change
        
        self.switch_box.set_center_widget(self.switch) # There's likely a better way.
        
        self.box1.append(self.switch_box)
        
        self.header = Gtk.HeaderBar()
        self.set_titlebar(self.header)

        # set app name
        GLib.set_application_name("My App")

        app = self.get_application()
        self.sm = app.get_style_manager()


    def rate_changed(self, slider):
        bpm = int(slider.get_value()) # todo: remove this 
        period_and_state[0] = bpm2period(bpm)
        print(bpm)# ... and this. The prints should be in the other class.

    def apply_depth(self):
        # "Typically a depth knob will allow you to dial the lowest volume point
        # https://tremolo-project.blogspot.com/2017/08/matthews-effects-conductor.html
        if self.depth_value < 127:
            bottom = 127 - self.depth_value  # lowest point
            for i in range(len(series)):
                if series[i] < bottom:
                    series[i] = bottom

    def depth_changed(self, slider):
        self.depth_value = int(slider.get_value())
        self.apply_depth()
        print(int(slider.get_value()))

    def switch_switched(self, switch, state):
        if state:
            period_and_state[1] = True
            self.sm.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)  # useful for on-off            
        else:
            period_and_state[1] = False
            self.sm.set_color_scheme(Adw.ColorScheme.PREFER_DARK)  # useful for on-off            
        print(f"The switch has been switched {'on' if state else 'off'}")

    def waveform_selected(self, dropdown, data):
        # https://discourse.gnome.org/t/example-of-gtk-dropdown-with-search-enabled-without-gtk-expression/12748
        selection = dropdown.get_selected_item().get_string()  # this API feels inane
        # An assignment seems to create a new list object. I need to keep the same obj.
        for i in range(len(series)):
            series[i] = WAVEFORM_SERIES[selection][i]
        self.apply_depth()
        print(selection)
            

class MyApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)

        # todo: this might be off by a factor of four?
        self.debug = True
        if not self.debug:
            inport = mido.open_input('Source Audio EQ2 MIDI 1')  # todo: try removing this line
            self.outport = mido.open_output('Source Audio EQ2 MIDI 1')
            self.set_trim = lambda v: mido.Message('control_change', channel=0, control=2,value=v)
        else:
            self.set_trim = lambda v: print("Channel 2 Trim set to ", v)        
        
        thread = threading.Thread(target=self.run_tremolo)
        thread.start()

    def on_activate(self, app):
        self.win = GUI(application=app)        
        self.win.present()

    def run_tremolo(self):
        while(True):
            # user can always ^C
            if period_and_state[1]:
                has_been_shut_down = False
                for l in series:
                    if period_and_state[1]:  # todo: this should be event-driven
                        if self.debug:
                            self.set_trim(l)
                        else:
                            self.outport.send(self.set_trim(l))
                        time.sleep(period_and_state[0])
                    elif not period_and_state[1]:
                        break
            else:
                if not has_been_shut_down:
                    self.set_trim(127)                    
                    has_been_shut_down = True


app = MyApp(application_id="com.example.GtkApplication")
app.run(sys.argv)
