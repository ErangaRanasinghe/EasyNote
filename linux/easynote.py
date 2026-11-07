#!/usr/bin/env python3
# Easy Note for Linux - a tiny scratch pad that hides on the right edge of the screen.
# Publisher: EMR Industries
#
# Move the mouse to the far right edge of the screen and a small tab appears.
# Click it and a borderless, always-on-top note window opens at the bottom
# centre of the screen. It stays open until you click the tab again.
#
#   easynote            start (or show the note if it is already running)
#   easynote --toggle   open/close the note (bind this to a keyboard shortcut)
#   easynote --quit     close the running app

import os
import sys
import json
import socket
import threading
import datetime

APP_NAME = "Easy Note"
VERSION = "1.0.0"
PUBLISHER = "EMR Industries"
APP_ID = "easynote"

# The edge button and "always on top" need X11. Wayland desktops (Ubuntu, Fedora,
# KDE, Raspberry Pi OS) all run X11 apps through XWayland, so prefer that.
if os.environ.get("DISPLAY") and "GDK_BACKEND" not in os.environ:
    os.environ["GDK_BACKEND"] = "x11"

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Gtk, Gdk, GLib, Gio, Pango, PangoCairo, GdkPixbuf

GLib.set_prgname(APP_ID)
GLib.set_application_name(APP_NAME)

AppIndicator = None
for _name, _ver in (("AyatanaAppIndicator3", "0.1"), ("AppIndicator3", "0.1")):
    try:
        gi.require_version(_name, _ver)
        AppIndicator = __import__("gi.repository." + _name, fromlist=[_name])
        break
    except (ValueError, ImportError):
        pass

HERE = os.path.dirname(os.path.realpath(__file__))
CONFIG_DIR = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), APP_ID)
NOTE_PATH = os.path.join(CONFIG_DIR, "note.txt")
SETTINGS_PATH = os.path.join(CONFIG_DIR, "settings.json")
AUTOSTART_PATH = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
                              "autostart", APP_ID + ".desktop")
RUNTIME_DIR = os.environ.get("XDG_RUNTIME_DIR") or "/tmp"
SOCKET_PATH = os.path.join(RUNTIME_DIR, "%s-%d.sock" % (APP_ID, os.getuid()))

BLUE = (0 / 255, 120 / 255, 215 / 255)
BLUE_HOVER = (0 / 255, 98 / 255, 176 / 255)


def find_logo():
    for p in (os.path.join(HERE, "assets", "logo.png"),
              os.path.join(HERE, "..", "assets", "logo.png")):
        if os.path.exists(p):
            return os.path.abspath(p)
    return None


LOGO_PATH = find_logo()


# ---------------------------------------------------------------------------
# Saved text and settings  (~/.config/easynote)
# ---------------------------------------------------------------------------
class Store:
    defaults = {"font": "Sans 11", "opacity": 0.85}

    def __init__(self):
        self.data = dict(self.defaults)
        try:
            with open(SETTINGS_PATH) as f:
                self.data.update(json.load(f))
        except Exception:
            pass

    def get(self, key):
        return self.data.get(key, self.defaults.get(key))

    def set(self, key, value):
        self.data[key] = value
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(SETTINGS_PATH, "w") as f:
                json.dump(self.data, f, indent=2)
        except Exception:
            pass

    @staticmethod
    def load_text():
        try:
            with open(NOTE_PATH, encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    @staticmethod
    def save_text(text):
        try:
            os.makedirs(CONFIG_DIR, exist_ok=True)
            with open(NOTE_PATH, "w", encoding="utf-8") as f:
                f.write(text)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Light / dark theme, read from the desktop settings
# ---------------------------------------------------------------------------
class Theme:
    def __init__(self, dark):
        self.dark = dark
        if dark:
            self.back, self.bar, self.text = "#202020", "#2b2b2b", "#f0f0f0"
            self.muted, self.line, self.hover, self.pressed = "#a0a0a0", "#464646", "#3d3d3d", "#4b4b4b"
        else:
            self.back, self.bar, self.text = "#ffffff", "#f3f3f3", "#1c1c1c"
            self.muted, self.line, self.hover, self.pressed = "#606060", "#c8c8c8", "#e4e4e4", "#d6d6d6"

    @staticmethod
    def detect():
        try:
            src = Gio.SettingsSchemaSource.get_default()
            if src and src.lookup("org.gnome.desktop.interface", True):
                s = Gio.Settings.new("org.gnome.desktop.interface")
                if s.props.settings_schema.has_key("color-scheme") and s.get_string("color-scheme") == "prefer-dark":
                    return Theme(True)
        except Exception:
            pass
        st = Gtk.Settings.get_default()
        try:
            if st.get_property("gtk-application-prefer-dark-theme"):
                return Theme(True)
        except Exception:
            pass
        name = (st.get_property("gtk-theme-name") or "").lower()
        return Theme("dark" in name)


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def rounded_rect(cr, x, y, w, h, r, left=True, right=True):
    import math
    cr.new_sub_path()
    if right:
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    else:
        cr.line_to(x + w, y)
        cr.line_to(x + w, y + h)
    if left:
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    else:
        cr.line_to(x, y + h)
        cr.line_to(x, y)
    cr.close_path()


def draw_pencil(cr, cx, cy, size):
    """White pencil, same shape as the Windows version."""
    import math
    cr.save()
    cr.translate(cx, cy)
    cr.rotate(-math.pi / 4)
    L, W = size * 1.25, size * 0.28
    cr.set_source_rgb(1, 1, 1)
    cr.rectangle(-L / 2 + W, -W / 2, L - W * 1.6, W)
    cr.fill()
    cr.move_to(-L / 2 + W * 0.85, -W / 2)
    cr.line_to(-L / 2, 0)
    cr.line_to(-L / 2 + W * 0.85, W / 2)
    cr.close_path()
    cr.fill()
    cr.rectangle(L / 2 - W * 0.45, -W / 2, W * 0.45, W)
    cr.fill()
    cr.restore()


def use_rgba(win):
    """Give a window a transparent background when a compositor is running."""
    screen = win.get_screen()
    visual = screen.get_rgba_visual()
    if visual is not None and screen.is_composited():
        win.set_visual(visual)
        return True
    return False


def outer_right_monitor():
    """The monitor whose right edge is the right edge of the whole desktop."""
    display = Gdk.Display.get_default()
    best = None
    for i in range(display.get_n_monitors()):
        g = display.get_monitor(i).get_geometry()
        if best is None or g.x + g.width > best.x + best.width:
            best = g
    return best


def primary_monitor():
    display = Gdk.Display.get_default()
    return display.get_primary_monitor() or display.get_monitor(0)


# ---------------------------------------------------------------------------
# Invisible 2px strip on the right edge - detects the mouse arriving there
# ---------------------------------------------------------------------------
class EdgeStrip(Gtk.Window):
    WIDTH = 2

    def __init__(self, on_enter, on_leave):
        Gtk.Window.__init__(self, type=Gtk.WindowType.POPUP)
        self.rgba = use_rgba(self)
        self.set_app_paintable(True)
        self.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("draw", self.on_draw)
        self.connect("enter-notify-event", lambda w, e: on_enter(int(e.y_root)))
        self.connect("leave-notify-event", lambda w, e: on_leave())
        self.line = "#808080"

    def place(self):
        g = outer_right_monitor()
        top = g.y + int(g.height * 0.08)            # leave the corners free
        self.resize(self.WIDTH, int(g.height * 0.84))
        self.move(g.x + g.width - self.WIDTH, top)

    def on_draw(self, w, cr):
        import cairo
        if self.rgba:
            cr.set_source_rgba(0, 0, 0, 0)          # fully see-through but still catches the mouse
        else:
            cr.set_source_rgb(*hex_rgb(self.line))  # no compositor: a hairline
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        return True


# ---------------------------------------------------------------------------
# The blue tab that slides in on the right edge
# ---------------------------------------------------------------------------
class EdgeTab(Gtk.Window):
    W, H = 28, 84

    def __init__(self, on_click, on_menu, on_enter, on_leave):
        Gtk.Window.__init__(self, type=Gtk.WindowType.POPUP)
        self.rgba = use_rgba(self)
        self.set_app_paintable(True)
        self.set_size_request(self.W, self.H)
        self.resize(self.W, self.H)
        self.hover = False
        self.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK |
                        Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK)
        self.connect("draw", self.on_draw)
        self.connect("enter-notify-event", self._enter, on_enter)
        self.connect("leave-notify-event", self._leave, on_leave)
        self.connect("button-release-event", self._release, on_click, on_menu)

    def _enter(self, w, e, cb):
        self.hover = True
        self.queue_draw()
        cb()

    def _leave(self, w, e, cb):
        if e.detail == Gdk.NotifyType.INFERIOR:
            return
        self.hover = False
        self.queue_draw()
        cb()

    def _release(self, w, e, on_click, on_menu):
        if e.button == 1:
            on_click(e)
        elif e.button == 3:
            on_menu(e)

    def show_at(self, y):
        g = outer_right_monitor()
        y = max(g.y + 4, min(y - self.H // 2, g.y + g.height - self.H - 4))
        self.move(g.x + g.width - self.W, y)
        self.show()

    def on_draw(self, w, cr):
        import cairo
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.set_source_rgb(*(BLUE_HOVER if self.hover else BLUE))
        if self.rgba:
            rounded_rect(cr, 0, 0, self.W + 12, self.H, 10, left=True, right=False)
            cr.fill()
        else:
            cr.paint()
        draw_pencil(cr, self.W / 2, self.H / 2, self.W * 0.64)
        return True


# ---------------------------------------------------------------------------
# Start-up window: logo, name, version, build and publisher
# ---------------------------------------------------------------------------
class Splash(Gtk.Window):
    def __init__(self, theme):
        Gtk.Window.__init__(self, type=Gtk.WindowType.POPUP)
        self.theme = theme
        self.rgba = use_rgba(self)
        self.set_app_paintable(True)
        self.W, self.H = 360, 132
        self.resize(self.W, self.H)
        self.logo = None
        if LOGO_PATH:
            try:
                self.logo = GdkPixbuf.Pixbuf.new_from_file_at_scale(LOGO_PATH, 88, 88, True)
            except Exception:
                pass
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", lambda *a: self.destroy())
        self.connect("draw", self.on_draw)

    def show_for(self, ms=2000):
        g = primary_monitor().get_geometry()
        self.move(g.x + (g.width - self.W) // 2, g.y + (g.height - self.H) // 2)
        self.show_all()
        GLib.timeout_add(ms, self._close)

    def _close(self):
        self.destroy()
        return False

    def on_draw(self, w, cr):
        import cairo
        t = self.theme
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        r = 10 if self.rgba else 0
        rounded_rect(cr, 0.5, 0.5, self.W - 1, self.H - 1, max(r, 0.1))
        cr.set_source_rgb(*hex_rgb(t.back))
        cr.fill_preserve()
        cr.set_source_rgb(*hex_rgb(t.line))
        cr.set_line_width(1)
        cr.stroke()
        # blue strip along the bottom
        cr.save()
        rounded_rect(cr, 0.5, 0.5, self.W - 1, self.H - 1, max(r, 0.1))
        cr.clip()
        cr.set_source_rgb(*BLUE)
        cr.rectangle(0, self.H - 4, self.W, 4)
        cr.fill()
        cr.restore()

        if self.logo:
            Gdk.cairo_set_source_pixbuf(cr, self.logo, 22, (self.H - 88) / 2)
            cr.paint()

        x, y = 22 + 88 + 18, 24
        layout = PangoCairo.create_layout(cr)
        layout.set_font_description(Pango.FontDescription("Sans Bold 16"))
        layout.set_text(APP_NAME, -1)
        cr.set_source_rgb(*hex_rgb(t.text))
        cr.move_to(x, y)
        PangoCairo.show_layout(cr, layout)

        layout.set_font_description(Pango.FontDescription("Sans 9"))
        cr.set_source_rgb(*hex_rgb(t.muted))
        for i, line in enumerate(("Version %s   ·   Build %s" % (VERSION, build_date()),
                                  "Publisher: " + PUBLISHER)):
            layout.set_text(line, -1)
            cr.move_to(x, y + 38 + i * 20)
            PangoCairo.show_layout(cr, layout)
        return True


def build_date():
    try:
        ts = os.path.getmtime(os.path.realpath(__file__))
        return datetime.date.fromtimestamp(ts).strftime("%-d %b %Y")
    except Exception:
        return ""


# ---------------------------------------------------------------------------
# The note window: no title bar, ~2 inches tall, bottom centre, always on top
# ---------------------------------------------------------------------------
class NoteWindow(Gtk.Window):
    def __init__(self, app):
        Gtk.Window.__init__(self, title=APP_NAME)
        self.app = app
        self.set_decorated(False)
        self.set_keep_above(True)
        self.set_skip_taskbar_hint(True)
        self.set_skip_pager_hint(True)
        self.rgba = use_rgba(self)
        self.set_app_paintable(True)
        if LOGO_PATH:
            try:
                self.set_icon_from_file(LOGO_PATH)
            except Exception:
                pass
        self.get_style_context().add_class("en-window")

        dpi = Gdk.Screen.get_default().get_resolution()
        if dpi is None or dpi <= 0:
            dpi = 96.0
        self.set_default_size(int(4.2 * dpi), int(2.0 * dpi))   # about 4.2 x 2 inches  <- change width here

        frame = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        frame.get_style_context().add_class("en-frame")
        self.add(frame)

        # --- top strip: drag handle + buttons ---
        bar_events = Gtk.EventBox()
        bar_events.connect("button-press-event", self.on_bar_press)
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        bar.get_style_context().add_class("en-bar")
        bar_events.add(bar)
        frame.pack_start(bar_events, False, False, 0)

        self.status = Gtk.Label(label=APP_NAME, xalign=0)
        self.status.get_style_context().add_class("en-status")
        bar.pack_start(self.status, True, True, 0)

        for text, tip, cb in (("Aa", "Change font", lambda b: self.choose_font()),
                              ("Copy", "Copy selection, or everything if nothing is selected", lambda b: self.copy_text()),
                              ("Clear", "Clear all text (Ctrl+Z right after brings it back)", lambda b: self.clear_text()),
                              ("⋯", "Menu: font, transparency, start at login, Exit", self.on_menu_button)):
            b = Gtk.Button(label=text)
            b.set_relief(Gtk.ReliefStyle.NONE)
            b.set_can_focus(False)
            b.set_tooltip_text(tip)
            b.get_style_context().add_class("en-btn")
            b.connect("clicked", cb)
            bar.pack_start(b, False, False, 0)

        # --- typing area ---
        scroller = Gtk.ScrolledWindow()
        scroller.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroller.get_style_context().add_class("en-scroll")
        self.view = Gtk.TextView()
        self.view.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.view.set_left_margin(10)
        self.view.set_right_margin(6)
        self.view.set_top_margin(6)
        self.view.set_bottom_margin(4)
        self.view.get_style_context().add_class("en-text")
        self.buf = self.view.get_buffer()
        self.buf.set_text(Store.load_text())
        self.buf.connect("changed", self.on_changed)
        self.view.connect("key-press-event", self.on_key)
        scroller.add(self.view)
        frame.pack_start(scroller, True, True, 0)

        self.save_id = 0
        self.flash_id = 0
        self.cleared = None
        self.font_css = Gtk.CssProvider()
        self.view.get_style_context().add_provider(self.font_css, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION + 1)
        self.apply_font(app.store.get("font"))
        Gtk.Widget.set_opacity(self, app.store.get("opacity"))
        self.connect("delete-event", lambda *a: self.hide_note() or True)
        frame.show_all()

    # --- showing / hiding ---
    def show_note(self, event_time=None):
        mon = Gdk.Display.get_default().get_monitor_at_point(*self.app.pointer())
        wa = mon.get_workarea()
        w, h = self.get_size()
        self.move(wa.x + (wa.width - w) // 2, wa.y + wa.height - h - 8)   # bottom centre
        self.show()
        self.set_keep_above(True)
        self.present_with_time(event_time or Gtk.get_current_event_time())
        self.view.grab_focus()
        end = self.buf.get_end_iter()
        self.buf.place_cursor(end)
        self.view.scroll_to_iter(end, 0, False, 0, 0)

    def hide_note(self):
        self.save_now()
        self.hide()

    # --- top strip ---
    def on_bar_press(self, w, e):
        if e.button == 1:
            self.begin_move_drag(e.button, int(e.x_root), int(e.y_root), e.time)
        elif e.button == 3:
            self.app.popup_menu(e)
        return True

    def on_menu_button(self, button):
        self.app.popup_menu(None, button)

    # --- text ---
    def on_key(self, w, e):
        ctrl = e.state & Gdk.ModifierType.CONTROL_MASK
        shift = e.state & Gdk.ModifierType.SHIFT_MASK
        key = Gdk.keyval_to_lower(e.keyval)
        if ctrl and shift and key == Gdk.KEY_c:
            self.copy_text()
            return True
        if ctrl and not shift and key == Gdk.KEY_z and self.cleared is not None:
            self.buf.set_text(self.cleared)
            self.cleared = None
            self.flash("Restored")
            return True
        return False

    def on_changed(self, buf):
        if self.save_id:
            GLib.source_remove(self.save_id)
        self.save_id = GLib.timeout_add(700, self._autosave)

    def _autosave(self):
        self.save_id = 0
        self.save_now()
        return False

    def text(self):
        return self.buf.get_text(self.buf.get_start_iter(), self.buf.get_end_iter(), True)

    def save_now(self):
        Store.save_text(self.text())

    def copy_text(self):
        bounds = self.buf.get_selection_bounds()
        t = self.buf.get_text(bounds[0], bounds[1], True) if bounds else self.text()
        if not t:
            self.flash("Nothing to copy")
            return
        cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        cb.set_text(t, -1)
        cb.store()
        self.flash("Selection copied" if bounds else "All text copied")
        self.view.grab_focus()

    def clear_text(self):
        t = self.text()
        if not t:
            return
        self.cleared = t
        self.buf.set_text("")
        self.flash("Cleared (Ctrl+Z to undo)")
        self.view.grab_focus()

    def flash(self, msg):
        self.status.set_text(msg)
        if self.flash_id:
            GLib.source_remove(self.flash_id)
        self.flash_id = GLib.timeout_add(1600, self._unflash)

    def _unflash(self):
        self.flash_id = 0
        self.status.set_text(APP_NAME)
        return False

    # --- font ---
    def choose_font(self):
        dlg = Gtk.FontChooserDialog(title="Choose a font", transient_for=self if self.get_visible() else None)
        dlg.set_keep_above(True)
        dlg.set_font(self.app.store.get("font"))
        self.app.busy += 1
        try:
            if dlg.run() == Gtk.ResponseType.OK and dlg.get_font():
                self.app.store.set("font", dlg.get_font())
                self.apply_font(dlg.get_font())
        finally:
            self.app.busy -= 1
            dlg.destroy()
        if self.get_visible():
            self.view.grab_focus()

    def apply_font(self, font):
        d = Pango.FontDescription(font)
        size = d.get_size() / Pango.SCALE if d.get_size() else 11
        css = "textview, textview text { font-family: \"%s\"; font-size: %gpt; font-weight: %d; font-style: %s; }" % (
            (d.get_family() or "Sans").replace('"', ''), size, int(d.get_weight()),
            "italic" if d.get_style() == Pango.Style.ITALIC else "normal")
        self.font_css.load_from_data(css.encode())


# ---------------------------------------------------------------------------
# The app: edge strip, tab, note, menu, tray icon, single instance
# ---------------------------------------------------------------------------
class EasyNoteApp:
    def __init__(self):
        self.store = Store()
        self.busy = 0                       # menus/dialogs open: don't restack windows over them
        self.hide_id = 0
        self.css = Gtk.CssProvider()
        Gtk.StyleContext.add_provider_for_screen(Gdk.Screen.get_default(), self.css,
                                                 Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        self.note = NoteWindow(self)
        self.tab = EdgeTab(self.on_tab_click, self.popup_menu, self.cancel_hide, self.schedule_hide)
        self.strip = EdgeStrip(self.on_edge, self.schedule_hide)
        self.strip.place()
        self.strip.show()

        screen = Gdk.Screen.get_default()
        screen.connect("monitors-changed", lambda s: self.strip.place())
        screen.connect("size-changed", lambda s: self.strip.place())

        self.apply_theme()
        settings = Gtk.Settings.get_default()
        settings.connect("notify::gtk-theme-name", lambda *a: self.apply_theme())
        settings.connect("notify::gtk-application-prefer-dark-theme", lambda *a: self.apply_theme())
        self.gsettings = None
        try:
            src = Gio.SettingsSchemaSource.get_default()
            if src and src.lookup("org.gnome.desktop.interface", True):
                self.gsettings = Gio.Settings.new("org.gnome.desktop.interface")
                self.gsettings.connect("changed", lambda s, k: self.apply_theme()
                                       if k in ("color-scheme", "gtk-theme") else None)
        except Exception:
            pass

        self.indicator = None
        if AppIndicator is not None:
            try:
                self.indicator = AppIndicator.Indicator.new(
                    APP_ID, LOGO_PATH or "accessories-text-editor",
                    AppIndicator.IndicatorCategory.APPLICATION_STATUS)
                self.indicator.set_title(APP_NAME)
                self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
                self.refresh_tray_menu()
            except Exception:
                self.indicator = None

        GLib.timeout_add(700, self.keep_on_top)
        Splash(self.theme).show_for(2000)

    # --- pointer position (for picking the monitor) ---
    def pointer(self):
        seat = Gdk.Display.get_default().get_default_seat()
        _, x, y = seat.get_pointer().get_position()
        return x, y

    # --- edge behaviour ---
    def on_edge(self, y):
        self.cancel_hide()
        if not self.tab.get_visible():
            self.tab.show_at(y)

    def cancel_hide(self):
        if self.hide_id:
            GLib.source_remove(self.hide_id)
            self.hide_id = 0

    def schedule_hide(self):
        self.cancel_hide()
        self.hide_id = GLib.timeout_add(1200, self._hide_tab)

    def _hide_tab(self):
        self.hide_id = 0
        if self.busy == 0:
            self.tab.hide()
        return False

    def on_tab_click(self, event):
        self.toggle(event.time)

    def toggle(self, event_time=None):
        if self.note.get_visible():
            self.note.hide_note()
        else:
            self.note.show_note(event_time)

    # Like the Windows version: keep the edge strip and note above other windows
    def keep_on_top(self):
        if self.busy == 0:
            for w in (self.strip, self.tab, self.note):
                if w.get_visible() and w.get_window():
                    w.get_window().raise_()
        return True

    # --- theme ---
    def apply_theme(self):
        t = Theme.detect()
        self.theme = t
        radius = 8 if self.note.rgba else 0
        css = """
        .en-window {{ background-color: transparent; }}
        .en-frame {{ background-color: {back}; border: 1px solid {line}; border-radius: {r}px; }}
        .en-bar {{ background-color: {bar}; border-radius: {r}px {r}px 0 0; min-height: 26px; }}
        .en-status {{ color: {muted}; font-size: 8.5pt; padding-left: 8px; }}
        .en-btn {{ color: {text}; background: none; border: none; box-shadow: none; border-radius: 0;
                   padding: 2px 9px; min-height: 0; min-width: 0; font-size: 8.5pt; }}
        .en-btn:hover {{ background-color: {hover}; }}
        .en-btn:active {{ background-color: {pressed}; }}
        .en-scroll, .en-scroll > viewport {{ background-color: {back}; border-radius: 0 0 {r}px {r}px; }}
        .en-text, .en-text text {{ background-color: {back}; color: {text}; caret-color: {text}; }}
        .en-text text selection {{ background-color: #0078d7; color: #ffffff; }}
        """.format(back=t.back, bar=t.bar, text=t.text, muted=t.muted, line=t.line,
                   hover=t.hover, pressed=t.pressed, r=radius)
        self.css.load_from_data(css.encode())
        self.strip.line = t.line
        self.strip.queue_draw()

    # --- menu ---
    def build_menu(self):
        menu = Gtk.Menu()

        def item(label, cb):
            mi = Gtk.MenuItem(label=label)
            mi.connect("activate", lambda *a: cb())
            menu.append(mi)

        item("Open note", lambda: self.note.show_note() if not self.note.get_visible() else None)
        item("Change font...", self.note.choose_font)

        trans = Gtk.MenuItem(label="Transparency")
        sub = Gtk.Menu()
        group = None
        current = int(round(self.store.get("opacity") * 100))
        for level in (100, 95, 90, 85, 80, 70, 60):
            label = "None (solid)" if level == 100 else "%d%% see-through" % (100 - level)
            mi = Gtk.RadioMenuItem.new_with_label_from_widget(group, label)
            group = mi
            mi.set_active(level == current)
            mi.connect("toggled", self.on_transparency, level)
            sub.append(mi)
        trans.set_submenu(sub)
        menu.append(trans)

        auto = Gtk.CheckMenuItem(label="Start at login")
        auto.set_active(os.path.exists(AUTOSTART_PATH))
        auto.connect("toggled", self.on_autostart)
        menu.append(auto)

        menu.append(Gtk.SeparatorMenuItem())
        item("About " + APP_NAME, lambda: Splash(self.theme).show_for(2000))
        item("Exit", self.quit)
        menu.show_all()
        return menu

    def popup_menu(self, event, widget=None):
        menu = self.build_menu()
        self.busy += 1
        menu.connect("deactivate", self._menu_closed)
        if widget is not None:
            menu.popup_at_widget(widget, Gdk.Gravity.SOUTH_EAST, Gdk.Gravity.NORTH_EAST, None)
        else:
            menu.popup_at_pointer(event)

    def _menu_closed(self, menu):
        self.busy = max(0, self.busy - 1)
        self.schedule_hide()

    def refresh_tray_menu(self):
        if self.indicator is not None:
            self.indicator.set_menu(self.build_menu())

    def on_transparency(self, mi, level):
        if mi.get_active():
            self.store.set("opacity", level / 100.0)
            Gtk.Widget.set_opacity(self.note, level / 100.0)
            GLib.idle_add(lambda: self.refresh_tray_menu() and False)

    def on_autostart(self, mi):
        try:
            if mi.get_active():
                os.makedirs(os.path.dirname(AUTOSTART_PATH), exist_ok=True)
                with open(AUTOSTART_PATH, "w") as f:
                    f.write(desktop_entry(autostart=True))
            elif os.path.exists(AUTOSTART_PATH):
                os.remove(AUTOSTART_PATH)
        except Exception as ex:
            print("Could not change the start-at-login setting:", ex, file=sys.stderr)
        GLib.idle_add(lambda: self.refresh_tray_menu() and False)

    # --- commands from a second launch (easynote --toggle etc.) ---
    def on_command(self, cmd):
        if cmd == "toggle":
            self.toggle()
        elif cmd == "show":
            if not self.note.get_visible():
                self.note.show_note()
            else:
                self.note.present()
        elif cmd == "quit":
            self.quit()
        return False

    def quit(self):
        self.note.save_now()
        Gtk.main_quit()


def launcher_command():
    installed = os.path.expanduser("~/.local/bin/easynote")
    if os.path.exists(installed):
        return installed
    return "/usr/bin/env python3 " + os.path.realpath(__file__)


def desktop_entry(autostart=False):
    lines = ["[Desktop Entry]", "Type=Application", "Name=" + APP_NAME,
             "Comment=Quick scratch pad on the edge of your screen",
             "Exec=" + launcher_command(),
             "Icon=" + (LOGO_PATH or "accessories-text-editor"),
             "Terminal=false", "Categories=Utility;TextEditor;"]
    if autostart:
        lines.append("X-GNOME-Autostart-enabled=true")
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Single instance: a second launch passes its command to the running app
# ---------------------------------------------------------------------------
def send_to_running(cmd):
    try:
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(1.0)
        s.connect(SOCKET_PATH)
        s.sendall(cmd.encode())
        s.close()
        return True
    except OSError:
        return False


def listen(app):
    try:
        os.unlink(SOCKET_PATH)
    except OSError:
        pass
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCKET_PATH)
    os.chmod(SOCKET_PATH, 0o600)
    srv.listen(4)

    def loop():
        while True:
            try:
                conn, _ = srv.accept()
                cmd = conn.recv(64).decode(errors="ignore").strip()
                conn.close()
                if cmd in ("toggle", "show", "quit"):
                    GLib.idle_add(app.on_command, cmd)
            except OSError:
                break

    t = threading.Thread(target=loop, daemon=True)
    t.start()
    return srv


def main():
    args = sys.argv[1:]
    if "--version" in args:
        print("%s %s - %s" % (APP_NAME, VERSION, PUBLISHER))
        return
    cmd = "toggle" if "--toggle" in args else "quit" if "--quit" in args else "show"
    if send_to_running(cmd):
        return
    if cmd == "quit":
        return
    if Gdk.Display.get_default() is None:
        print("Easy Note needs a graphical desktop session.", file=sys.stderr)
        sys.exit(1)

    import signal
    app = EasyNoteApp()
    srv = listen(app)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, lambda: app.quit() or False)
    GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, lambda: app.quit() or False)
    if cmd == "toggle":
        GLib.timeout_add(300, lambda: app.toggle() or False)
    Gtk.main()
    srv.close()
    try:
        os.unlink(SOCKET_PATH)
    except OSError:
        pass


if __name__ == "__main__":
    main()
