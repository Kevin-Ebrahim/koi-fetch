"""Render a pond as coloured Unicode Braille characters."""

import math

from .world import NODES, clamp

ESC = "\x1b["


def pond(t, sprite, swimmers, food, colours, width, height):
    """Draw koi with Unicode Braille dots, eight pixels per character cell."""
    pixel_width, pixel_height = width * 2, height * 4
    canvas = [[0] * pixel_width for _ in range(pixel_height)]
    tints = [[0] * pixel_width for _ in range(pixel_height)]

    # Scattered amber glints, like the reference's dark-water particles.
    for index in range(min(800, max(20, round(52 * width * height / (58 * 25))))):
        x = (index * 37 + 3) % pixel_width
        y = (index * 29 + 2) % pixel_height
        if math.sin(t * 0.8 + index * 2.3) > 0.35:
            canvas[y][x] = 55 + (index % 3) * 20
            tints[y][x] = 4

    for fish in swimmers:
        fish_width, phase, nodes = fish['length'], fish['phase'], fish['nodes']
        swim = clamp(fish['speed'] / 24, .4, 1.4)
        spine = []
        for k in range(NODES):
            s = k / (NODES - 1)
            a, b = nodes[max(0, k - 1)], nodes[min(NODES - 1, k + 1)]
            tx, ty = a[0] - b[0], a[1] - b[1]
            norm = math.hypot(tx, ty) or 1
            tx, ty = tx / norm, ty / norm
            amplitude = fish_width * .05 * (.1 + .9 * s ** 1.8) * swim
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
                offset = across * (fish_width / 2) * spread
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
    lines = []
    for row in range(height):
        previous = None
        parts = []
        for col in range(width):
            bits = 0
            values = []
            colour_weights = [0, 0, 0, 0, 0]
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
            colour = max(range(5), key=colour_weights.__getitem__)
            style = (colour, level)
            if style != previous:
                parts.append(f'{ESC}{colours[colour][level]}m' if level else f'{ESC}0m')
                previous = style
            parts.append(chr(0x2800 + bits) if bits else ' ')
        lines.append(''.join(parts) + f'{ESC}0m')
    return lines

