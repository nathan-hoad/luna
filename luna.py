#!/usr/bin/python
import asyncio
import itertools
import json
import os
import weakref

import gbulb
from gi.repository import Gtk, Vte, Gio, GLib, Pango, Gdk

base00 = "#000000"
base01 = "#3a3432"
base02 = "#4a4543"
base03 = "#5c5855"
base04 = "#807d7c"
base05 = "#a5a2a2"
base06 = "#d6d5d4"
base07 = "#f7f7f7"
base08 = "#db2d20"
base09 = "#e8bbd0"
base0A = "#fded02"
base0B = "#01a252"
base0C = "#b5e4f4"
base0D = "#01a0e4"
base0E = "#a16a94"
base0F = "#cdab53"

FOREGROUND = '#fff'
BACKGROUND = base00
FONTS = [
    'AnonymicePowerline Nerd Font 9',
    'Anonymous Pro 9',
    'FuraCode Nerd Font 9',
    'SpaceMono Nerd Font 9',
    'SauceCodePro Nerd Font 9',
    'ProFontIIx Nerd Font 9',
    'mononoki Nerd Font 9',
    '3270Medium Nerd Font 9',
    'AurulentSansMono Nerd Font 9',
]

SCROLLBACK = 100_000
SHELL = [Vte.get_user_shell()]

COLORS = [
    base00,
    base08,
    base0B,
    base0A,
    base0D,
    base0E,
    base0A,
    base05,

    base05,
    base08,
    base0B,
    base0A,
    base0D,
    base0E,
    base0A,
    base05,
]


def change_font(terminal, *, left=None, name=None):
    if left is not None:
        terminal.font_position += -1 if left else 1

        if terminal.font_position < 0:
            terminal.font_position = len(FONTS) - 1
        elif terminal.font_position >= len(FONTS):
            terminal.font_position = 0
        name = FONTS[terminal.font_position]

    font = Pango.FontDescription.from_string(name)

    old_font = terminal.get_font()
    if old_font is not None:
        font.set_size(old_font.get_size())

    terminal.set_font(font)


class Luna(Gtk.Application):
    terminals = weakref.WeakValueDictionary()

    def __init__(self):
        super().__init__(
            application_id='com.nhoad.luna',
            flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)

        self.id_count = itertools.count()
        self.connect('command-line', self.on_command_line)

    def new_window(self, command_line):
        window = Gtk.Window(title='Luna')
        terminal = Vte.Terminal.new()
        terminal.connect('child-exited', self.on_child_exited, window)
        terminal.connect('window-title-changed', self.set_window_title, window)

        self.setup_terminal(terminal)
        self.configure_terminal(terminal)

        char_width = terminal.get_char_width()
        geo_hints = Gdk.Geometry()
        geo_hints.base_width = char_width
        geo_hints.base_height = char_width
        geo_hints.min_width = char_width
        geo_hints.min_height = char_width
        geo_hints.width_inc = char_width
        geo_hints.height_inc = char_width
        window.set_geometry_hints(
            terminal, geo_hints,
            Gdk.WindowHints.RESIZE_INC | Gdk.WindowHints.MIN_SIZE | Gdk.WindowHints.BASE_SIZE)

        b = Gtk.VBox()
        b.add(terminal)
        window.add(b)
        window.show_all()
        self.add_window(window)

    def configure_terminal(self, terminal):
        terminal.set_rewrap_on_resize(True)
        terminal.font_position = -1
        change_font(terminal, left=False)

        terminal.set_cursor_shape(Vte.CursorShape.BLOCK)
        terminal.set_cursor_blink_mode(Vte.CursorBlinkMode.OFF)
        terminal.set_word_char_exceptions("-A-Za-z0-9:./?%&#_=+@~")
        terminal.set_scrollback_lines(SCROLLBACK)
        terminal.set_colors(self.fg, self.bg, self.colors)

    def set_window_title(self, terminal, window):
        window.set_title(terminal.get_window_title())

    def on_child_exited(self, terminal, status, window):
        window.destroy()

    def on_key_press(self, terminal, event):
        keyval = Gdk.keyval_to_upper(event.keyval)
        if event.state & Gdk.ModifierType.CONTROL_MASK:
            if keyval == Gdk.KEY_Up:
                self.resize_font(terminal, +1)
                return True
            elif keyval == Gdk.KEY_Down:
                self.resize_font(terminal, -1)
                return True
            elif keyval == Gdk.KEY_Left:
                change_font(terminal, left=True)
                return True
            elif keyval == Gdk.KEY_Right:
                change_font(terminal, left=False)
                return True
        elif event.state & Gdk.ModifierType.SUPER_MASK:
            if keyval == Gdk.KEY_C:
                terminal.copy_clipboard()
                terminal.copy_primary()
                return True
            elif keyval == Gdk.KEY_V:
                terminal.paste_primary()
                return True

    def on_selection_changed(self, terminal):
        terminal.copy_clipboard()

    def resize_font(self, terminal, step):
        font = terminal.get_font()
        font.set_size((font.get_size() / Pango.SCALE + step) * Pango.SCALE)
        terminal.set_font(font)

    def setup_terminal(self, terminal):
        terminal.id = next(self.id_count)
        self.terminals[terminal.id] = terminal
        pty = Vte.Terminal.pty_new_sync(terminal, Vte.PtyFlags.NO_HELPER)

        terminal.connect('key-press-event', self.on_key_press)
        terminal.connect('selection-changed', self.on_selection_changed)

        flags = (
            GLib.SpawnFlags.DO_NOT_REAP_CHILD |
            GLib.SpawnFlags.SEARCH_PATH |
            GLib.SpawnFlags.LEAVE_DESCRIPTORS_OPEN
        )

        env = dict(os.environ)
        env['LUNA_PORT'] = str(SERVER_PORT)
        env['LUNA_ID'] = str(terminal.id)
        env = ['{}={}'.format(k, v) for k, v in env.items()]

        pid, *streams = GLib.spawn_async(
            SHELL,
            envp=env,
            flags=flags,
            child_setup=Vte.Pty.child_setup,
            user_data=pty,
        )

        terminal.set_pty(pty)
        terminal.watch_child(pid)
        return terminal

    def setup(self):
        self.fg = Gdk.RGBA()
        self.bg = Gdk.RGBA()

        self.fg.parse(FOREGROUND)
        self.bg.parse(BACKGROUND)

        self.colors = [Gdk.RGBA() for c in COLORS]
        [color.parse(s) for (color, s) in zip(self.colors, COLORS)]

    def on_command_line(self, another_self, command_line):
        if not command_line.get_is_remote():
            self.setup()

        self.new_window(command_line)

        return 0

class IPC:
    def font(self, terminal, font):
        if font:
            change_font(terminal, left=None, name=font)
        return terminal.get_font().get_family()

    def shell(self, terminal, shell):
        global SHELL
        if shell:
            SHELL = shell
        return str(SHELL)

    def __call__(self, message):
        cmd = message.pop('cmd')

        func = getattr(self, cmd, None)

        if func is None:
            return {'status': 'ERROR', 'message': 'No command by that name'}

        id = message.pop('id')
        terminal = Luna.terminals[id]
        try:
            ret = func(terminal, **message)
        except Exception as e:
            return {'status': 'ERROR', 'message': str(e)}
        else:
            return {'status': 'OK', 'message': ret or 'Nothing much to say'}

ipc = IPC()
del IPC


async def client_connected(reader, writer):
    line = await reader.readline()
    if not line:
        writer.close()
        return
    print('line', line)
    j = json.loads(line)
    print('json', j)

    r = ipc(j)

    writer.write(json.dumps(r).encode('utf8'))
    writer.write(b'\n')
    await writer.drain()
    writer.close()


if __name__ == '__main__':
    style_text = b"GtkWindow { background: black; }"

    style_provider = Gtk.CssProvider()
    style_provider.load_from_data(style_text)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(), style_provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
    )
    application = Luna()

    gbulb.install(gtk=True)
    loop = gbulb.get_event_loop()

    server = loop.run_until_complete(asyncio.start_server(client_connected, host='127.0.0.1', port=0))
    SERVER_PORT = server.sockets[0].getsockname()[1]

    loop.run_forever(application=application)
