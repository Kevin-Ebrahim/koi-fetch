"""Fish and prey simulation, adapted from ascii-sharks (MIT)."""

import math
import random

NODES = 20


def motion_scale(width, height):
    """Keep turning and swimming proportional in unusually small ponds."""
    return max(.35, min(1.0, width / 58, height / 25))


def new_swimmers(width, height, count=3):
    """Initialize three jointed fish at different sizes and colours."""
    rng = random.Random()
    swimmers = []
    for index in range(count):
        scale = min(1.0, width / 58, height / 25)
        length = max(12, round((49, 42, 36)[index % 3] * scale))
        w, h = width * 2, height * 4
        minimum = min(w, h)
        radius = minimum * rng.uniform(.28, .4)
        a = index * math.tau / count + rng.uniform(-.4, .4)
        direction = 1 if index % 2 == 0 else -1
        x = w / 2 + math.cos(a) * radius * (w / minimum) * .9
        y = h / 2 + math.sin(a) * radius
        heading = a + direction * math.pi / 2
        seg = length / (NODES - 1)
        nodes = [(x - math.cos(heading) * seg * n,
                  y - math.sin(heading) * seg * n) for n in range(NODES)]
        swimmers.append({
            'id': index + 1,
            'base_length': (49, 42, 36)[index % 3],
            'length': length,
            'colour': index % 3,
            'nodes': nodes,
            'heading': heading,
            'wander': 0.0,
            'speed': 12.0 * motion_scale(width, height),
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


def resize(swimmers, food, old_width, old_height, width, height):
    """Move the existing population into a resized pond without resetting it."""
    x_ratio, y_ratio = width / old_width, height / old_height
    speed_ratio = motion_scale(width, height) / motion_scale(old_width, old_height)
    scale = min(1.0, width / 58, height / 25)
    for fish in swimmers:
        hx, hy = fish['nodes'][0]
        new_hx = clamp(hx * x_ratio, 0, width * 2 - 1)
        new_hy = clamp(hy * y_ratio, 0, height * 4 - 1)
        length = max(12, round(fish['base_length'] * scale))
        length_ratio = length / fish['length']
        fish['nodes'] = [(new_hx + (x - hx) * length_ratio,
                          new_hy + (y - hy) * length_ratio)
                         for x, y in fish['nodes']]
        fish['length'] = length
        fish['speed'] *= speed_ratio
        fish['orbit_radius'] *= min(width, height * 2) / min(old_width, old_height * 2)
    for pellet in food:
        pellet['x'] = clamp(pellet['x'] * x_ratio, 0, width * 2 - 1)
        pellet['y'] = clamp(pellet['y'] * y_ratio, 0, height * 4 - 1)
        pellet['speed'] *= speed_ratio
        pellet['vx'] *= speed_ratio
        pellet['vy'] *= speed_ratio


def new_food(width, height, count=9):
    rng = random.Random()
    food = []
    for _ in range(count):
        heading = rng.uniform(-math.pi, math.pi)
        speed = rng.uniform(3.0, 4.5) * motion_scale(width, height)
        food.append({'x': rng.uniform(8, width * 2 - 8),
                     'y': rng.uniform(8, height * 4 - 8),
                     'vx': math.cos(heading) * speed, 'vy': math.sin(heading) * speed,
                     'heading': heading, 'speed': speed, 'wander': 0.0,
                     'phase': rng.uniform(0, math.tau),
                     'alive': True, 'respawn_at': 0.0, 'rng': rng})
    return food


def step_food(food, swimmers, dt, elapsed, width, height):
    scale = motion_scale(width, height)
    for pellet in food:
        if not pellet['alive']:
            if elapsed < pellet['respawn_at']:
                continue
            pellet['x'] = pellet['rng'].uniform(8, width * 2 - 8)
            pellet['y'] = pellet['rng'].uniform(8, height * 4 - 8)
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
            if .001 < distance < 22 * scale:
                weight = (1 - distance / (22 * scale)) * 2
                dx += ox / distance * weight
                dy += oy / distance * weight
                threatened = True
        margin = 12 * scale
        dx += 3 * max(0, (margin - pellet['x']) / margin)
        dx -= 3 * max(0, (pellet['x'] - (width * 2 - margin)) / margin)
        dy += 3 * max(0, (margin - pellet['y']) / margin)
        dy -= 3 * max(0, (pellet['y'] - (height * 4 - margin)) / margin)
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


def step_swimmers(swimmers, food, dt, elapsed, width, height):
    """Port ascii-sharks' hunting, steering and follow-the-leader spine."""
    if dt <= 0:
        return
    w, h = width * 2, height * 4
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
        scale = motion_scale(width, height)
        target_speed = min(24, (12 + length * .016) * (1.45 + closing * 1.5 if hunting else 1)) * scale
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

