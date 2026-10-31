"""Classic and Omarchy-derived terminal palettes."""

from pathlib import Path
import re
import subprocess

THEME_FILE = Path.home() / ".local/state/omarchy/current/theme/colors.toml"


def theme_palettes(theme_file):
    """Resolve Omarchy's semantic colours into shaded terminal palettes."""
    result = subprocess.run(
        ['omarchy', 'theme', 'color', '--file', str(theme_file), '--all'],
        capture_output=True, text=True, check=True, timeout=2,
    )
    resolved = dict(line.split('\t', 1) for line in result.stdout.splitlines() if '\t' in line)

    def colour(*keys):
        for key in keys:
            value = resolved.get(key, '')
            if re.fullmatch(r'#[0-9a-fA-F]{6}', value):
                return tuple(int(value[i:i + 2], 16) for i in (1, 3, 5))
        raise ValueError(f'Missing theme colour: {keys[0]}')

    background = colour('background', 'bg', 'color0')
    foreground = colour('bright_foreground', 'foreground', 'fg', 'color7')
    bases = (
        colour('yellow', 'orange', 'accent', 'color3', 'foreground'),
        colour('red', 'magenta', 'accent', 'color1', 'foreground'),
        colour('blue', 'cyan', 'accent', 'color4', 'foreground'),
        colour('green', 'cyan', 'accent', 'color2', 'foreground'),
        colour('cyan', 'muted', 'accent', 'color6', 'foreground'),
    )

    def mix(start, end, amount):
        return tuple(round(a + (b - a) * amount) for a, b in zip(start, end))

    palettes = []
    for base in bases:
        shades = [mix(background, base, amount) for amount in (.35, .5, .65, .8, 1.0)]
        shades += [mix(base, foreground, .32), mix(base, foreground, .62)]
        palettes.append(('',) + tuple(f'38;2;{r};{g};{b}' for r, g, b in shades))
    return tuple(palettes)


class ThemeColours:
    """Refresh after a theme change, retaining the last valid palette on errors."""

    def __init__(self, theme_file=THEME_FILE):
        self.theme_file = theme_file
        self.signature = None
        self.next_check = 0.0
        # Fallback used until Omarchy's palette is available.
        self.colours = tuple(
            ('',) + tuple(f'38;2;{r};{g};{b}' for r, g, b in shades)
            for shades in (
                ((104,55,25),(186,91,31),(224,122,42),(244,151,61),(255,180,87),(255,206,131),(255,226,170)),
                ((105,37,33),(159,54,48),(203,75,65),(233,105,88),(250,142,118),(255,181,156),(255,220,199)),
                ((42,67,96),(59,100,145),(78,133,183),(103,163,209),(141,192,227),(179,218,240),(218,239,247)),
                ((39,94,75),(54,140,104),(71,178,128),(101,208,154),(142,229,182),(180,241,207),(215,250,228)),
                ((104,55,25),(186,91,31),(224,122,42),(244,151,61),(255,180,87),(255,206,131),(255,226,170)),
            )
        )

    def poll(self, now):
        if now < self.next_check:
            return
        self.next_check = now + 1.0
        try:
            stat = self.theme_file.stat()
            signature = (stat.st_dev, stat.st_ino, stat.st_mtime_ns, stat.st_size)
            if signature == self.signature:
                return
            colours = theme_palettes(self.theme_file)
        except (OSError, ValueError, subprocess.SubprocessError):
            return
        self.colours = colours
        self.signature = signature
