#!/usr/bin/env python3

import time
import threading
import sys
from typing import Final

import mido
from numpy import concatenate, cos, linspace, pi, sqrt, square

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, GLib

"""I plan on "shipping" this as a one-file script for
simplicity. Breaking out into files and modules is better, but python
deployment has been painful for me and I'd rather this than experience
it again."""


DUTY_CYCLE_MAX: Final = 50  # Duty cycle denominator. I'm worried going too low would effectively DDoS the SA EQ2.
# The stress shifts from the EQ2's MIDI ingestion to this app..
WAVEFORM_SERIES: Final = {
    "triangle": tuple(range(127)) + tuple(range(127, 0, -1)),
    "square": tuple([127] * 127 + [0] * 127),
    "sine": tuple(map(round, cos(linspace(-pi, pi, 254)) * 63.5 + 63.5)),
    "sawtooth": tuple(map(round, linspace(0, 127, 254))),
    "reverse sawtooth": tuple(map(round, linspace(127, 0, 254))),
    "hill": tuple(map(round, sqrt(1 - square(linspace(-1, 1, 254))) * 127)),
    "valley": tuple(map(round, (1 - sqrt(1 - square(linspace(-1, 1, 254)))) * 127)),  # todo: offset so it works better with duty cycle
    # todo: add random
}
# Lengths of all series must be the same
assert len(set(map(len, WAVEFORM_SERIES.values()))) == 1


def make_waveform(series, depth, duty):
    """Return a series of trim level values.

    duty ∈ [0, DUTY_CYCLE_MAX]

            # "Typically a depth knob will allow you to dial the lowest volume point
        # https://tremolo-project.blogspot.com/2017/08/matthews-effects-conductor.html
    depth ∈ [0, 127]

    Initially, a static waveform series was modified in time to apply
    the duty cycle.  This didn't work on the initial try. This
    function is more expensive than a static dictionary of
    series. However, the expense is only paid when the new waveform
    series is calculated: when a slider is moved. This seemed easier
    to understand than the previous time-shifting method.
    """
    # todo: This function and the WAVEFORM_SERIES constant should be merged.
    # This is redundant and thus, error prone if one but not the other is changed.
    period = 254  # this permits a right triangle for triangle wave and a circular hill.
    duty = round(duty * (period / 2) / DUTY_CYCLE_MAX)

    if depth == 0:
        return [0] * period
    if duty == 0:
        return [127 - depth] * period

    if series == "triangle":
        # Sometimes this doesn't contain 127, but for duty>9 it always has something above 120.
        triangle = list(map(round, 127 - abs(linspace(1 - depth, depth, 2 * duty))))
        return triangle + [127 - depth] * (period - 2 * duty)
    elif series == "square":
        return [127] * duty + [127 - depth] * (period - duty)
    elif series == "sine":
        # Sine as it is here matches up well with triangle. Apologies for my dishonesty in using cosine.
        sinusoid = (cos(linspace(-pi, pi, 2 * duty)) + 1) / 2  # ∈ [0, 1]
        sinusoid = depth * sinusoid + 127 - depth  # ∈ [127-depth, 127]
        sinusoid = list(map(round, sinusoid))
        return sinusoid + [127 - depth] * (period - 2 * duty)
    elif series == "sawtooth":
        sawtooth = list(map(round, linspace(127 - depth, 127, 2 * duty)))
        return sawtooth + [127 - depth] * (period - 2 * duty)
    elif series == "reverse sawtooth":
        sawtooth = list(map(round, linspace(127, 127 - depth, 2 * duty)))
        return sawtooth + [127 - depth] * (period - 2 * duty)
    elif series == "hill" or series == "valley":
        # Hill and Valley use the equation for a circle.
        # Parabola could have worked as well and is simpler,
        # but is more similar to sine. Circle is more distinct, so I feel it's better than parabola.
        hill = lambda a, b, l: sqrt(1 - square(linspace(a, b, l)))
        if series == "hill":
            hill = depth * hill(-1, 1, 2 * duty) + 127 - depth  # same math from "sine".
            hill = list(map(round, hill))
            return hill + [127 - depth] * (period - 2 * duty)
        elif series == "valley":
            valley = 1 - concatenate((hill(0, 1, duty), hill(-1, 0, duty)))
            valley = depth * valley + 127 - depth
            valley = list(map(round, valley))
            return valley + [127 - depth] * (period - 2 * duty)


def bpm2period(bpm):
    """Convert beats per minute from rate slider to the MIDI CC
    message period in seconds."""
    hz = bpm / 60
    period = 1 / hz
    return period / len(WAVEFORM_SERIES["triangle"])


def make_slider(a, b, default, callback):
    # One could set the properties using the property string-names.
    # The "set_range" would then be obviated by the "adjustment property", it seems.
    # But setting the adjustment property looks like more work than making this function.
    slider = Gtk.Scale()
    slider.set_digits(0)  # Number of decimal places to use
    slider.set_range(a, b)
    slider.set_draw_value(True)  # Show a label with current value
    slider.set_value(default)  # Sets the current value/position
    slider.connect("value-changed", callback)
    return slider


# Objects for cross-thread communication. They can only be declared once: here. GUI alone modifies these.
# Cast to list for mutation by depth
# todo: save the setting when closing the app. I'd just edit this same tremolo.py file wherever it's deployed, if !DEBUG.
series = make_waveform("triangle", 127, DUTY_CYCLE_MAX)
thd_period_in_seconds = bpm2period(
    60
)  # period is the MIDI CC period between messages: a number.
thd_event_effect_engaged = (
    threading.Event()
)  # official docs & https://stackoverflow.com/a/14804328
thd_division = [1]


class GUI(Gtk.ApplicationWindow):
    # https://github.com/Taiko2k/GTK4PythonTutorial
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.set_default_size(600, 250)
        self.set_title("SAEQ TREMOLO")

        # Main layout containers
        self.box1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self.set_child(self.box1)  # Horizontal box to window

        # Drop down for waveforms
        self.waveform_dropdown = Gtk.DropDown.new_from_strings(
            tuple(WAVEFORM_SERIES.keys())
        )
        # https://discourse.gnome.org/t/example-of-gtk-dropdown-with-search-enabled-without-gtk-expression/12748
        self.waveform_dropdown.connect("notify::selected-item", self.waveform_selected)

        # self.division = Gtk.Entry()
        # self.division.set_text('Enter Division (e.g. "1 4 4 3 3 3 2)"')
        # self.division.connect('activate', self.division_entered)
        self.box1.append(
            self.waveform_dropdown
        )  # comment or delete line if working on division
        # self.waveform_and_divison_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        # self.waveform_and_divison_box.append(self.waveform_dropdown)
        # self.waveform_and_divison_box.append(self.division)
        # self.box1.append(self.waveform_and_divison_box)

        # arguments are range start, end, start value, callback
        self.rate = make_slider(1, 200, 1, self.rate_changed)
        self.depth = make_slider(0, 127, 127, self.depth_changed)
        self.duty = make_slider(0, DUTY_CYCLE_MAX, DUTY_CYCLE_MAX, self.duty_changed)

        thd_period_in_seconds = bpm2period(self.rate.get_value())
        self.depth_value = self.depth.get_value()
        self.duty_value = self.duty.get_value()
        self.waveform_name = "triangle"

        self.box1.append(self.rate)
        self.box1.append(self.depth)
        self.box1.append(
            self.duty
        )  # todo: this doesn't seem to be working. At least it doesn't seem to be interfering.

        # Add a box containing a switch
        self.switch_box = Gtk.CenterBox(orientation=Gtk.Orientation.HORIZONTAL)
        self.switch = Gtk.Switch()
        self.switch.set_active(thd_event_effect_engaged.is_set())
        self.switch.connect("state-set", self.switch_switched)
        self.switch_box.set_center_widget(self.switch)  # There's likely a better way.
        self.box1.append(self.switch_box)

        self.header = Gtk.HeaderBar()
        self.set_titlebar(self.header)

        # set app name
        GLib.set_application_name("SAEQ TREMOLO")

        app = self.get_application()
        self.sm = app.get_style_manager()
        if not thd_event_effect_engaged.is_set():
            self.sm.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

    def depth_changed(self, slider):
        self.depth_value = int(slider.get_value())
        self.update_series()
        print(int(slider.get_value()))

    def division_entered(self, entry_box):
        # todo: error handling. I might never get to this...
        divisor_string = entry_box.get_buffer().get_text()
        print(divisor_string)
        divisor_string, new_divisors = divisor_string.split(), []
        global thd_division  # the necessity of the global keywords feels like a sign of bad code.

        for ds in divisor_string:
            if "/" in ds:
                n, d = map(int, ds.split("/"))
                new_divisors.append(n // d)
            else:
                # obviously this can easily fail. I could also just not enter bad text.
                new_divisors.append(int(ds))
        if len(new_divisors) > 0:
            thd_division = new_divisors
        else:
            thd_division = [1]
        print(thd_division)

    def duty_changed(self, slider):
        # "Duty Cycle should actually be ... Controlling the on/off time ratio in the cycle.
        # So at 0% there is no sound, at 100% all signal is let through. "
        # https://tremolo-project.blogspot.com/2017/09/line-6-helix-all-tremolo-modes-examined.html
        self.duty_value = slider.get_value()
        self.update_series()
        print("duty", slider.get_value())

    def rate_changed(self, slider):
        bpm = int(slider.get_value())  # todo: remove this
        thd_period_in_seconds = bpm2period(bpm)
        print(bpm)  # ... and this. The prints should be in the other class.

    def switch_switched(self, switch, state):
        if state:
            thd_event_effect_engaged.set()
            self.sm.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)  # useful for on-off
        else:
            thd_event_effect_engaged.clear()
            self.sm.set_color_scheme(Adw.ColorScheme.PREFER_DARK)
        print(f"The switch has been switched {'on' if state else 'off'}")

    def update_series(self):
        new_waveform_series = make_waveform(
            self.waveform_name, self.depth_value, self.duty_value
        )
        for i in range(len(series)):
            series[i] = new_waveform_series[i]

    def waveform_selected(self, dropdown, data):
        # https://discourse.gnome.org/t/example-of-gtk-dropdown-with-search-enabled-without-gtk-expression/12748
        self.waveform_name = (
            dropdown.get_selected_item().get_string()
        )  # this API feels inane
        # An assignment seems to create a new list object. I need to keep the same obj for thread communication.
        self.update_series()
        print(self.waveform_name)


class MyApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect("activate", self.on_activate)

        # todo: this might be off by a factor of four?
        self.debug = True
        if not self.debug:
            inport = mido.open_input(
                "Source Audio EQ2 MIDI 1"
            )  # todo: try removing this line
            outport = mido.open_output("Source Audio EQ2 MIDI 1")
            self.set_trim = lambda v: outport.send(
                mido.Message("control_change", channel=0, control=2, value=v)
            )
        else:
            self.set_trim = lambda v: print("Channel 2 Trim set to ", v)

        self.closing = False
        self.thread = threading.Thread(target=self.run_tremolo)
        self.thread.start()

    def on_activate(self, app):
        self.win = GUI(application=app)
        self.win.present()

    def run_tremolo(self):
        has_been_reset = False

        while not self.closing:
            # update list. Don't use division directly to avoid size change isssues while looping.
            divisors = thd_division

            if thd_event_effect_engaged.is_set():
                has_been_reset = False
                for divisor in divisors:
                    if self.closing or not thd_event_effect_engaged.is_set():
                        break  # if window is closing or effect is not engaged
                    for level in series:
                        if self.closing or not thd_event_effect_engaged.is_set():
                            break  # if window is closing or effect is not engaged

                        self.set_trim(level)
                        time.sleep(thd_period_in_seconds / divisor)
                    if thd_event_effect_engaged.is_set():
                        cycle_count = len(WAVEFORM_SERIES["triangle"])
                        time.sleep(cycle_count * thd_period_in_seconds)

            else:  # if not engaged
                if not has_been_reset:
                    self.set_trim(127)
                    has_been_reset = True
                else:
                    self.blocking = True
                    thd_event_effect_engaged.wait()
                    self.blocking = False

    def close(self):
        print("Starting shutdown...")
        self.closing = True  # Tell run_tremolo to terminate
        if self.blocking:
            thd_event_effect_engaged.set()
        self.thread.join()  # Wait for thread to terminate
        self.set_trim(127)
        # todo: save the current settings. See above.
        print("...exiting")
        sys.exit()


app = MyApp(application_id="com.example.GtkApplication")
app.run(sys.argv)
app.close()
