import sys
import gi

gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, GLib

class MainWindow(Gtk.ApplicationWindow):

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
        self.rate.set_range(0, 200)
        self.rate.set_draw_value(True)  # Show a label with current value
        self.rate.set_value(100)  # Sets the current value/position
        self.rate.connect('value-changed', self.rate_changed)
        self.box1.append(self.rate)

        self.depth = Gtk.Scale()
        self.depth.set_digits(0)  # Number of decimal places to use
        self.depth.set_range(0, 127)
        self.depth.set_draw_value(True)  # Show a label with current value
        self.depth.set_value(127)  # Sets the current value/position
        self.depth.connect('value-changed', self.depth_changed)
        self.box1.append(self.depth)

        # Add a box containing a switch
        self.switch_box = Gtk.CenterBox(orientation=Gtk.Orientation.HORIZONTAL)
        self.switch = Gtk.Switch()
        self.switch.set_active(True)  # Let's default it to on
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
        print(int(slider.get_value()))

    def depth_changed(self, slider):
        print(int(slider.get_value()))

    def switch_switched(self, switch, state):
        if state:
            self.sm.set_color_scheme(Adw.ColorScheme.PREFER_LIGHT)  # useful for on-off            
        else:
            self.sm.set_color_scheme(Adw.ColorScheme.PREFER_DARK)  # useful for on-off            
        print(f"The switch has been switched {'on' if state else 'off'}")

    def waveform_selected(self, dropdown, data):
        # https://discourse.gnome.org/t/example-of-gtk-dropdown-with-search-enabled-without-gtk-expression/12748
        selection = dropdown.get_selected_item().get_string()  # this API feels inane
        self.waveform = selection
        print(selection)
            

class MyApp(Adw.Application):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        self.win = MainWindow(application=app)
        self.win.present()


app = MyApp(application_id="com.example.GtkApplication")
app.run(sys.argv)
