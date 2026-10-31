"""Command-line interface and terminal lifecycle for Koi Fetch."""

import argparse
from importlib.resources import files
import math
import os
import shutil
import signal
import subprocess
import sys
import time

from . import layout, render, world
from .theme import ThemeColours

ESC = "\x1b["
FRAME_DELAY = .055
FETCH_WIDTH, FETCH_HEIGHT = 58, 25


def load_sprite():
    tokens = files('koi_fetch').joinpath('data').joinpath('koi-sprite.pgm').read_text(encoding='ascii').split()
    if tokens[:4] != ['P2', '128', '64', '255'] or len(tokens) != 128 * 64 + 4:
        raise ValueError('Invalid koi sprite')
    return bytes(map(int, tokens[4:]))


def fastfetch_output(config=None):
    command = ['fastfetch']
    if config is not None:
        command += ['--config', config]
    # Preserve the user's modules and formatting while replacing the logo.
    command += ['--logo', 'none', '--pipe', 'false']
    return subprocess.run(
        command, check=True, text=True, encoding='utf-8', errors='replace', capture_output=True,
    ).stdout.splitlines()


def parser():
    result = argparse.ArgumentParser(
        prog='koi-fetch', description='Watch koi swim and hunt in your terminal.',
    )
    modes = result.add_mutually_exclusive_group()
    modes.add_argument('--fetch', action='store_true', help='show the pond beside Fastfetch (default)')
    modes.add_argument('--fullscreen', action='store_true', help='fill the terminal with the pond')
    result.add_argument('--theme', choices=('classic', 'terminal', 'omarchy', 'auto'), default='auto',
                        help='pond colours: auto (default), terminal, classic, or omarchy')
    result.add_argument('--config', metavar='PATH', help='Fastfetch config file or preset')
    return result


def enable_windows_vt():
    """Enable ANSI control sequences in the native Windows console if needed."""
    if sys.platform != 'win32':
        return lambda: None
    import ctypes
    import msvcrt
    from ctypes import wintypes

    kernel = ctypes.windll.kernel32
    kernel.GetConsoleMode.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
    kernel.GetConsoleMode.restype = wintypes.BOOL
    kernel.SetConsoleMode.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.SetConsoleMode.restype = wintypes.BOOL
    handle = wintypes.HANDLE(msvcrt.get_osfhandle(sys.stdout.fileno()))
    mode = wintypes.DWORD()
    if kernel.GetConsoleMode(handle, ctypes.byref(mode)):
        previous = mode.value
        if kernel.SetConsoleMode(handle, previous | 0x0001 | 0x0004):
            return lambda: kernel.SetConsoleMode(handle, previous)
        raise OSError('Windows console could not enable ANSI support; try Windows Terminal.')
    return lambda: None


def main(argv=None):
    argument_parser = parser()
    args = argument_parser.parse_args(argv)
    use_fetch = not args.fullscreen
    if args.config and not use_fetch:
        argument_parser.error('--config requires Fastfetch mode')
    if not sys.stdout.isatty() or not sys.stdin.isatty():
        print('Run koi-fetch directly in a terminal.', file=sys.stderr)
        return 1
    if os.environ.get('TERM') == 'dumb':
        print('Koi Fetch needs a terminal with ANSI escape sequence support (TERM is dumb).', file=sys.stderr)
        return 1
    if use_fetch and not shutil.which('fastfetch'):
        print('Fastfetch is required for this mode. Use --fullscreen for the pond alone.', file=sys.stderr)
        return 1

    try:
        sprite = load_sprite()
        info = fastfetch_output(args.config) if use_fetch else []
    except (OSError, ValueError) as error:
        print(f'Could not start koi-fetch: {error}', file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print(error.stderr or 'Fastfetch failed.', file=sys.stderr)
        return error.returncode or 1

    theme = ThemeColours(args.theme)
    if args.theme in ('auto', 'omarchy'):
        theme.poll(time.monotonic())
        if args.theme == 'omarchy' and theme.signature is None:
            print('Could not load the active Omarchy theme. Use --theme classic or auto.', file=sys.stderr)
            return 1

    min_columns, min_rows = (30, 10) if use_fetch else (20, 10)

    def stop(_signum, _frame):
        raise KeyboardInterrupt

    old_term = signal.signal(signal.SIGTERM, stop)
    out = sys.stdout
    last_size = None
    pond_size = None
    pages = []
    last_page = None
    swimmers = food = None
    last_tick = time.monotonic()
    elapsed = 0.0
    try:
        restore_vt = enable_windows_vt()
    except OSError as error:
        signal.signal(signal.SIGTERM, old_term)
        print(str(error), file=sys.stderr)
        return 1
    try:
        out.write(f'{ESC}?1049h{ESC}?25l{ESC}?7l')
        out.flush()
        while True:
            size = shutil.get_terminal_size()
            enough_room = size.columns >= min_columns and size.lines >= min_rows
            if size != last_size:
                out.write(f'{ESC}2J{ESC}H')
                if enough_room:
                    if use_fetch:
                        pond_width, _info_width, pages = layout.arrange(info, size.columns, size.lines)
                        new_size = (pond_width, size.lines)
                    else:
                        new_size = (size.columns, size.lines)
                    if pond_size is None:
                        area_ratio = new_size[0] * new_size[1] / (FETCH_WIDTH * FETCH_HEIGHT)
                        count = min(8, max(3, round(3 * math.sqrt(area_ratio))))
                        food_count = min(30, max(9, round(9 * math.sqrt(area_ratio))))
                        swimmers = world.new_swimmers(*new_size, count=count)
                        food = world.new_food(*new_size, count=food_count)
                    elif new_size != pond_size:
                        world.resize(swimmers, food, *pond_size, *new_size)
                    pond_size = new_size
                    last_page = None
                else:
                    out.write(f'Make the terminal at least {min_columns} columns wide and '
                              f'{min_rows} rows tall. Ctrl+C to exit.')
                last_size = size
            if enough_room:
                now = time.monotonic()
                dt = min(now - last_tick, .25)
                elapsed += dt
                if args.theme in ('auto', 'omarchy'):
                    theme.poll(now)
                width, height = pond_size
                if use_fetch:
                    page = int(elapsed / 6) % len(pages)
                    if page != last_page:
                        for row in range(size.lines):
                            line = pages[page][row] if row < len(pages[page]) else ''
                            out.write(f'{ESC}{row + 1};{width + 3}H{ESC}K{line}{ESC}0m')
                        last_page = page
                world.step_food(food, swimmers, dt, elapsed, width, height)
                world.step_swimmers(swimmers, food, dt, elapsed, width, height)
                for row, line in enumerate(render.pond(elapsed, sprite, swimmers, food,
                                                       theme.colours, width, height), 1):
                    out.write(f'{ESC}{row};1H{line}')
            out.flush()
            last_tick = time.monotonic() if not enough_room else now
            time.sleep(FRAME_DELAY)
    except KeyboardInterrupt:
        pass
    finally:
        out.write(f'{ESC}0m{ESC}?7h{ESC}?25h{ESC}?1049l')
        out.flush()
        signal.signal(signal.SIGTERM, old_term)
        restore_vt()
    return 0
