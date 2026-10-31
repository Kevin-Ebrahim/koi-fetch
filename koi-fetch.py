#!/usr/bin/env python3
"""A tiny animated pond beside your existing Fastfetch information.

Steering and spine simulation adapted from ascii-sharks by drewdi (MIT).
See ASCII-SHARKS-LICENSE and https://github.com/stackedlol/ascii-sharks.
"""

import os
import math
from pathlib import Path
import random
import re
import shutil
import signal
import subprocess
import sys
import time


WIDTH = 58
HEIGHT = 25
TOP = 3                  # Matches the logo padding passed to Fastfetch.
LEFT = 3
FRAME_DELAY = 0.055      # Pause between frames; movement uses elapsed time.
ESC = "\x1b["
NODES = 20

def load_sprite():
    """Load a small, precomputed greyscale sprite without extra packages."""
    tokens = (Path(__file__).resolve().parent / 'koi-sprite.pgm').read_text().split()
    if tokens[:4] != ['P2', '128', '64', '255'] or len(tokens) != 128 * 64 + 4:
        raise ValueError('Invalid koi sprite')
    return bytes(map(int, tokens[4:]))


def new_swimmers():
    """Initialize three jointed fish at different sizes and colours."""
    rng = random.Random()
    swimmers = []
    for index, length in enumerate((49, 42, 36)):
        w, h = WIDTH * 2, HEIGHT * 4
        minimum = min(w, h)
        radius = minimum * rng.uniform(.28, .4)
        a = index * math.tau / 3 + rng.uniform(-.4, .4)
        direction = 1 if index % 2 == 0 else -1
        x = w / 2 + math.cos(a) * radius * (w / minimum) * .9
        y = h / 2 + math.sin(a) * radius
        heading = a + direction * math.pi / 2
        seg = length / (NODES - 1)
        nodes = [(x - math.cos(heading) * seg * n,
                  y - math.sin(heading) * seg * n) for n in range(NODES)]
        swimmers.append({
            'id': index + 1,
            'length': length,
            'colour': index,
            'nodes': nodes,
            'heading': heading,
            'wander': 0.0,
            'speed': 12.0,
            'turn': 0.0,
            'phase': rng.uniform(0, math.tau),
            'orbit_dir': direction,
            'orbit_radius': radius,
            'hunger': rng.uniform(.35, .75),
            'target': None,
            'retarget_at': 0.0,
            'rng': rng,
        })
    return swimmers


def clamp(value, lo, hi):
    return max(lo, min(hi, value))


def angle_diff(a, b):
    return (b - a + math.pi) % math.tau - math.pi


def new_food():
    rng = random.Random()
    food = []
    for _ in range(9):
        heading = rng.uniform(-math.pi, math.pi)
        speed = rng.uniform(3.0, 4.5)
        food.append({'x': rng.uniform(8, WIDTH * 2 - 8),
                     'y': rng.uniform(8, HEIGHT * 4 - 8),
                     'vx': math.cos(heading) * speed, 'vy': math.sin(heading) * speed,
                     'heading': heading, 'speed': speed, 'wander': 0.0,
                     'phase': rng.uniform(0, math.tau),
                     'alive': True, 'respawn_at': 0.0, 'rng': rng})
    return food


def step_food(food, swimmers, dt, elapsed):
    for pellet in food:
        if not pellet['alive']:
            if elapsed < pellet['respawn_at']:
                continue
            pellet['x'] = pellet['rng'].uniform(8, WIDTH * 2 - 8)
            pellet['y'] = pellet['rng'].uniform(8, HEIGHT * 4 - 8)
            pellet['heading'] = pellet['rng'].uniform(-math.pi, math.pi)
            pellet['wander'] = 0.0
            pellet['alive'] = True
        heading = pellet['heading']
        pellet['wander'] = clamp(pellet['wander'] + (pellet['rng'].random() - .5) * dt * 2.8,
                                 -1.0, 1.0)
        dx = math.cos(heading) + .55 * math.cos(heading + pellet['wander'])
        dy = math.sin(heading) + .55 * math.sin(heading + pellet['wander'])

        # Softly steer away from approaching koi and the edges of the pond.
        threatened = False
        for fish in swimmers:
            hx, hy = fish['nodes'][0]
            ox, oy = pellet['x'] - hx, pellet['y'] - hy
            distance = math.hypot(ox, oy)
            if .001 < distance < 22:
                weight = (1 - distance / 22) * 2
                dx += ox / distance * weight
                dy += oy / distance * weight
                threatened = True
        margin = 12
        dx += 3 * max(0, (margin - pellet['x']) / margin)
        dx -= 3 * max(0, (pellet['x'] - (WIDTH * 2 - margin)) / margin)
        dy += 3 * max(0, (margin - pellet['y']) / margin)
        dy -= 3 * max(0, (pellet['y'] - (HEIGHT * 4 - margin)) / margin)
        desired = math.atan2(dy, dx)
        pellet['heading'] += clamp(angle_diff(heading, desired), -1.7 * dt, 1.7 * dt)
        speed = pellet['speed'] * (1.25 if threatened else 1.0)
        pellet['vx'] = math.cos(pellet['heading']) * speed
        pellet['vy'] = math.sin(pellet['heading']) * speed
        pellet['x'] += pellet['vx'] * dt
        pellet['y'] += pellet['vy'] * dt
        pellet['phase'] += dt * (4 + speed * .4)


def find_food(fish, food):
    """Use the source project's forward cone, scoring and target persistence."""
    hx, hy = fish['nodes'][0]
    fx, fy = math.cos(fish['heading']), math.sin(fish['heading'])
    best, best_score, current_score = None, math.inf, math.inf
    for pellet in food:
        if not pellet['alive']:
            continue
        dx, dy = pellet['x'] - hx, pellet['y'] - hy
        distance = math.hypot(dx, dy)
        if distance > fish['length'] * .9 + 64 or distance < .001:
            continue
        cosine = (dx * fx + dy * fy) / distance
        if cosine < .2:
            continue
        score = distance * (1 + (1 - cosine) * .8)
        if score < best_score:
            best, best_score = pellet, score
        if pellet is fish['target']:
            current_score = score
    if fish['target'] is not None and current_score < best_score * 1.3:
        return fish['target']
    return best


def step_swimmers(swimmers, food, dt, elapsed):
    """Port ascii-sharks' hunting, steering and follow-the-leader spine."""
    if dt <= 0:
        return
    w, h = WIDTH * 2, HEIGHT * 4
    minimum, center_x, center_y = min(w, h), w / 2, h / 2
    for fish in swimmers:
        length = fish['length']
        heading = fish['heading']
        hx, hy = fish['nodes'][0]
        fish['hunger'] = min(1.0, fish['hunger'] + dt * .03)
        fish['wander'] = clamp(fish['wander'] + (fish['rng'].random() - .5) * dt * 3.2, -1.1, 1.1)
        dx = math.cos(heading) + .45 * math.cos(heading + fish['wander'])
        dy = math.sin(heading) + .45 * math.sin(heading + fish['wander'])

        if elapsed >= fish['retarget_at']:
            fish['target'] = find_food(fish, food)
            fish['retarget_at'] = elapsed + .45
        target = fish['target']
        hunting = target is not None and target['alive'] and fish['hunger'] > .3
        closing = 0.0
        if hunting:
            tx = target['x'] + target['vx'] * .35 - hx
            ty = target['y'] + target['vy'] * .35 - hy
            distance = math.hypot(tx, ty) or 1
            weight = 1.4 + 2.6 * fish['hunger']
            dx += tx / distance * weight
            dy += ty / distance * weight
            closing = clamp(1 - distance / (length * .9), 0, 1)
        else:
            rx, ry = (hx - center_x) / (w / minimum), hy - center_y
            r = math.hypot(rx, ry) or 1
            radius = fish['orbit_radius'] * (1 + .15 * math.sin(elapsed * .05 + fish['id']))
            radial = clamp((radius - r) / radius, -1, 1)
            dx += ((-ry / r) * fish['orbit_dir'] + (rx / r) * radial * .9) * .55
            dy += ((rx / r) * fish['orbit_dir'] + (ry / r) * radial * .9) * .55

        # The original checks every fourth joint of other sharks.
        for other in swimmers:
            if other is fish:
                continue
            for ox, oy in other['nodes'][::4]:
                ox, oy = hx - ox, hy - oy
                distance = math.hypot(ox, oy)
                separation = (length + other['length']) * .45
                if .001 < distance < separation:
                    weight = (1 - distance / separation) * 3
                    dx += ox / distance * weight
                    dy += oy / distance * weight

        # The terminal pond is much tighter than the source's full-page canvas,
        # so apply the same edge force slightly before the visible edge.
        inset = length * .60
        over = max(inset - hx, hx - (w - inset), inset - hy, hy - (h - inset))
        if over > -length * .05:
            weight = clamp((over + length * .05) / (length * .35), 0, 1) * (7.0 if hunting else 3.5)
            to_x, to_y = center_x - hx, center_y - hy
            distance = math.hypot(to_x, to_y) or 1
            dx += to_x / distance * weight
            dy += to_y / distance * weight

        # Speed constants scale down the web canvas to this small dot grid.
        desired = math.atan2(dy, dx)
        agility = min(1.7 + closing if hunting else .8, fish['speed'] / (length * .22))
        turn = clamp(angle_diff(heading, desired), -agility * dt, agility * dt)
        fish['heading'] += turn
        fish['turn'] += (turn / dt - fish['turn']) * min(1, dt * 3)
        target_speed = min(24, (12 + length * .016) * (1.45 + closing * 1.5 if hunting else 1))
        fish['speed'] += (target_speed - fish['speed']) * min(1, dt * 1.1)
        fish['phase'] += dt * (2 + fish['speed'] / 9.6)
        fish['nodes'][0] = (hx + math.cos(fish['heading']) * fish['speed'] * dt,
                            hy + math.sin(fish['heading']) * fish['speed'] * dt)

        segment, max_bend = length / (NODES - 1), .16
        previous_angle = fish['heading'] + math.pi
        for k in range(1, NODES):
            px, py = fish['nodes'][k - 1]
            nx, ny = fish['nodes'][k]
            angle = math.atan2(ny - py, nx - px)
            angle = previous_angle + clamp(angle_diff(previous_angle, angle), -max_bend, max_bend)
            fish['nodes'][k] = (px + math.cos(angle) * segment, py + math.sin(angle) * segment)
            previous_angle = angle

        if fish['hunger'] > .15:
            mx, my = fish['nodes'][0]
            mouth_radius = length * .05 + 3.2
            for pellet in food:
                if pellet['alive'] and math.hypot(pellet['x'] - mx, pellet['y'] - my) < mouth_radius:
                    pellet['alive'] = False
                    pellet['respawn_at'] = elapsed + fish['rng'].uniform(3, 8)
                    fish['hunger'] = max(0, fish['hunger'] - .16)


def pond(t, sprite, swimmers, food):
    """Draw koi with Unicode Braille dots, eight pixels per character cell."""
    pixel_width, pixel_height = WIDTH * 2, HEIGHT * 4
    canvas = [[0] * pixel_width for _ in range(pixel_height)]
    tints = [[0] * pixel_width for _ in range(pixel_height)]

    # Scattered amber glints, like the reference's dark-water particles.
    for index in range(52):
        x = (index * 37 + 3) % pixel_width
        y = (index * 29 + 2) % pixel_height
        if math.sin(t * 0.8 + index * 2.3) > 0.35:
            canvas[y][x] = 55 + (index % 3) * 20

    for fish in swimmers:
        width, phase, nodes = fish['length'], fish['phase'], fish['nodes']
        swim = clamp(fish['speed'] / 24, .4, 1.4)
        spine = []
        for k in range(NODES):
            s = k / (NODES - 1)
            a, b = nodes[max(0, k - 1)], nodes[min(NODES - 1, k + 1)]
            tx, ty = a[0] - b[0], a[1] - b[1]
            norm = math.hypot(tx, ty) or 1
            tx, ty = tx / norm, ty / norm
            amplitude = width * .05 * (.1 + .9 * s ** 1.8) * swim
            offset = amplitude * math.sin(phase - s * 5.2)
            spine.append((nodes[k][0] - ty * offset, nodes[k][1] + tx * offset))

        # Map the existing koi texture onto the moving spine. Fins fan and
        # bank with the turn while the head and body follow the joint chain.
        bank = clamp(fish['turn'] * .45, -.35, .35)
        for column in range(128):
            u = column / 127
            position = u * (NODES - 1)
            k = min(NODES - 2, int(position))
            fraction = position - k
            a, b = spine[k], spine[k + 1]
            cx = a[0] + (b[0] - a[0]) * fraction
            cy = a[1] + (b[1] - a[1]) * fraction
            dx, dy = b[0] - a[0], b[1] - a[1]
            norm = math.hypot(dx, dy) or 1
            nx, ny = -dy / norm, dx / norm
            fin = (max(0.0, 1 - abs(u - .38) / .24) * .20
                   + max(0.0, 1 - abs(u - .85) / .20) * .15)
            for row in range(64):
                value = sprite[row * 128 + column]
                if value <= 25:
                    continue
                across = row / 63 - .5
                outer = clamp((abs(across) - .08) * 4, 0, 1)
                fan = fin * math.sin(phase * .75 - u * 3 + (0.8 if across > 0 else 0))
                side_bank = bank if across > 0 else -bank
                spread = 1 + outer * (fan + side_bank * fin)
                offset = across * (width / 2) * spread
                x, y = round(cx + nx * offset), round(cy + ny * offset)
                if 0 <= x < pixel_width and 0 <= y < pixel_height:
                    if value > canvas[y][x]:
                        canvas[y][x] = value
                        tints[y][x] = fish['colour']

    # Tiny tapered swimmers with a flicking, forked tail instead of pellets.
    for pellet in food:
        if pellet['alive']:
            c, s = math.cos(pellet['heading']), math.sin(pellet['heading'])
            tail = math.sin(pellet['phase']) * .9
            points = ((3, 0), (2, 0), (1, -1), (1, 0), (1, 1),
                      (0, -1), (0, 0), (0, 1), (-1, 0),
                      (-2, tail - 1), (-2, tail + 1))
            for along, across in points:
                x = round(pellet['x'] + c * along - s * across)
                y = round(pellet['y'] + s * along + c * across)
                if 0 <= x < pixel_width and 0 <= y < pixel_height:
                    canvas[y][x] = 235 if along >= 0 else 160
                    tints[y][x] = 3

    # Ordered dithering preserves shading using a small regular dot grid.
    dither = ((0, 8, 2, 10), (12, 4, 14, 6),
              (3, 11, 1, 9), (15, 7, 13, 5))
    dot_bits = ((0, 3), (1, 4), (2, 5), (6, 7))
    colours = ((
        '', '38;2;104;55;25', '38;2;186;91;31', '38;2;224;122;42',
        '38;2;244;151;61', '38;2;255;180;87', '38;2;255;206;131',
        '38;2;255;226;170',
    ), (
        '', '38;2;105;37;33', '38;2;159;54;48', '38;2;203;75;65',
        '38;2;233;105;88', '38;2;250;142;118', '38;2;255;181;156', '38;2;255;220;199',
    ), (
        '', '38;2;42;67;96', '38;2;59;100;145', '38;2;78;133;183',
        '38;2;103;163;209', '38;2;141;192;227', '38;2;179;218;240', '38;2;218;239;247',
    ), (
        '', '38;2;39;94;75', '38;2;54;140;104', '38;2;71;178;128',
        '38;2;101;208;154', '38;2;142;229;182', '38;2;180;241;207', '38;2;215;250;228',
    ))
    lines = []
    for row in range(HEIGHT):
        previous = None
        parts = []
        for col in range(WIDTH):
            bits = 0
            values = []
            colour_weights = [0, 0, 0, 0]
            for dy in range(4):
                for dx in range(2):
                    x, y = col * 2 + dx, row * 4 + dy
                    value = canvas[y][x]
                    if value > 14 + dither[y % 4][x % 4] * 6:
                        bits |= 1 << dot_bits[dy][dx]
                        values.append(value)
                        colour_weights[tints[y][x]] += value
            value = sum(values) // len(values) if values else 0
            level = 0 if not bits else min(7, 1 + value * 7 // 256)
            colour = max(range(4), key=colour_weights.__getitem__)
            style = (colour, level)
            if style != previous:
                parts.append(f'{ESC}{colours[colour][level]}m' if level else f'{ESC}0m')
                previous = style
            parts.append(chr(0x2800 + bits) if bits else ' ')
        lines.append(''.join(parts) + f'{ESC}0m')
    return lines


def fastfetch_output():
    blank_logo = '\n'.join([' ' * WIDTH] * HEIGHT)
    command = [
        'fastfetch', '--data', blank_logo, '--logo-padding-left', '2',
        '--logo-padding-right', '4', '--logo-padding-top', '2',
        '--pipe', 'false',
    ]
    return subprocess.run(command, check=True, text=True, capture_output=True).stdout.splitlines()


def main():
    if not sys.stdout.isatty() or not sys.stdin.isatty():
        print('Run koi-fetch.py directly in a terminal.', file=sys.stderr)
        return 1
    if not shutil.which('fastfetch'):
        print('Fastfetch is not installed or is not on PATH.', file=sys.stderr)
        return 1

    try:
        sprite = load_sprite()
        info = fastfetch_output()
    except (OSError, ValueError) as error:
        print(f'Could not load the koi sprite: {error}', file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print(error.stderr or 'Fastfetch failed.', file=sys.stderr)
        return error.returncode or 1

    ansi = re.compile(r'\x1b\[[0-?]*[ -/]*[@-~]')
    min_columns = max(len(ansi.sub('', line)) for line in info)
    min_rows = max(len(info), TOP + HEIGHT - 1)

    # Restore the terminal on SIGTERM as well as Ctrl+C.
    def stop(_signum, _frame):
        raise KeyboardInterrupt

    old_term = signal.signal(signal.SIGTERM, stop)
    out = sys.stdout
    last_size = None
    swimmers = new_swimmers()
    food = new_food()
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
                step_food(food, swimmers, dt, elapsed)
                step_swimmers(swimmers, food, dt, elapsed)
                for row, line in enumerate(pond(elapsed, sprite, swimmers, food), TOP):
                    out.write(f'{ESC}{row};{LEFT}H{line}')
                if size.lines > len(info):
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


if __name__ == '__main__':
    raise SystemExit(main())
