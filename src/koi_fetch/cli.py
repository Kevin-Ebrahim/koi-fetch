"""Command-line interface and terminal lifecycle for Koi Fetch."""

import argparse
from importlib.resources import files
import math
import re
import shutil
import signal
import subprocess
import sys
import time

from . import render, world
from .theme import ThemeColours

ESC = "\x1b["
FRAME_DELAY = .055
FETCH_WIDTH, FETCH_HEIGHT = 58, 25


def load_sprite():
    tokens = files('koi_fetch').joinpath('data', 'koi-sprite.pgm').read_text(encoding='ascii').split()
    if tokens[:4] != ['P2', '128', '64', '255'] or len(tokens) != 128 * 64 + 4:
        raise ValueError('Invalid koi sprite')
    return bytes(map(int, tokens[4:]))


def fastfetch_output():
    blank_logo = '\n'.join([' ' * FETCH_WIDTH] * FETCH_HEIGHT)
    return subprocess.run(
        ['fastfetch', '--data', blank_logo, '--logo-padding-left', '2',
         '--logo-padding-right', '4', '--logo-padding-top', '2', '--pipe', 'false'],
        check=True, text=True, capture_output=True,
    ).stdout.splitlines()


def parser():
    result = argparse.ArgumentParser(
        prog='koi-fetch', description='Watch koi swim and hunt in your terminal.',
    )
    modes = result.add_mutually_exclusive_group()
    modes.add_argument('--fetch', action='store_true', help='show the pond beside Fastfetch (default)')
    modes.add_argument('--fullscreen', action='store_true', help='fill the terminal with the pond')
    result.add_argument('--theme', choices=('classic', 'omarchy', 'auto'), default='auto',
                        help='pond colours: auto (default), classic, or omarchy')
    return result


def main(argv=None):
    args = parser().parse_args(argv)
    use_fetch = not args.fullscreen
    if not sys.stdout.isatty() or not sys.stdin.isatty():
        print('Run koi-fetch directly in a terminal.', file=sys.stderr)
        return 1
    if use_fetch and not shutil.which('fastfetch'):
        print('Fastfetch is required for this mode. Use --fullscreen for the pond alone.', file=sys.stderr)
        return 1

    try:
        sprite = load_sprite()
        info = fastfetch_output() if use_fetch else []
    except (OSError, ValueError) as error:
        print(f'Could not start koi-fetch: {error}', file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print(error.stderr or 'Fastfetch failed.', file=sys.stderr)
        return error.returncode or 1

    theme = ThemeColours()
    if args.theme != 'classic':
        theme.poll(time.monotonic())
        if args.theme == 'omarchy' and theme.signature is None:
            print('Could not load the active Omarchy theme. Use --theme classic or auto.', file=sys.stderr)
            return 1

    ansi = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
    min_columns = max((len(ansi.sub('', line)) for line in info), default=20)
    min_rows = max(len(info), 27) if use_fetch else 10

    def stop(_signum, _frame):
        raise KeyboardInterrupt

    old_term = signal.signal(signal.SIGTERM, stop)
    out = sys.stdout
    last_size = None
    pond_size = None
    swimmers = food = None
    last_tick = time.monotonic()
    elapsed = 0.0
    try:
        out.write(f'{ESC}?1049h{ESC}?25l{ESC}?7l')
        out.flush()
        while True:
            size = shutil.get_terminal_size()
            enough_room = size.columns >= min_columns and size.lines >= min_rows
            if size != last_size:
                out.write(f'{ESC}2J{ESC}H')
                if enough_room:
                    new_size = (FETCH_WIDTH, FETCH_HEIGHT) if use_fetch else (size.columns, size.lines)
                    if pond_size is None:
                        area_ratio = new_size[0] * new_size[1] / (FETCH_WIDTH * FETCH_HEIGHT)
                        count = min(8, max(3, round(3 * math.sqrt(area_ratio))))
                        food_count = min(30, max(9, round(9 * math.sqrt(area_ratio))))
                        swimmers = world.new_swimmers(*new_size, count=count)
                        food = world.new_food(*new_size, count=food_count)
                    elif new_size != pond_size:
                        world.resize(swimmers, food, *pond_size, *new_size)
                    pond_size = new_size
                    for row, line in enumerate(info, 1):
                        out.write(f'{ESC}{row};1H{line}')
                    out.write(f'{ESC}?7l')
                else:
                    out.write(f'Make the terminal at least {min_columns} columns wide and '
                              f'{min_rows} rows tall. Ctrl+C to exit.')
                last_size = size
            if enough_room:
                now = time.monotonic()
                dt = min(now - last_tick, .25)
                elapsed += dt
                if args.theme != 'classic':
                    theme.poll(now)
                width, height = pond_size
                world.step_food(food, swimmers, dt, elapsed, width, height)
                world.step_swimmers(swimmers, food, dt, elapsed, width, height)
                top, left = (3, 3) if use_fetch else (1, 1)
                for row, line in enumerate(render.pond(elapsed, sprite, swimmers, food,
                                                       theme.colours, width, height), top):
                    out.write(f'{ESC}{row};{left}H{line}')
                if use_fetch and size.lines > len(info):
                    out.write(f'{ESC}{size.lines};3H{ESC}90mCtrl+C to leave the pond{ESC}0m')
            out.flush()
            last_tick = time.monotonic() if not enough_room else now
            time.sleep(FRAME_DELAY)
    except KeyboardInterrupt:
        pass
    finally:
        out.write(f'{ESC}0m{ESC}?7h{ESC}?25h{ESC}?1049l')
        out.flush()
        signal.signal(signal.SIGTERM, old_term)
    return 0
