"""Fit coloured Fastfetch output beside the pond on a terminal screen."""

import math
import re
import unicodedata

ESCAPE = re.compile(
    r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07\x1b]*(?:\x07|\x1b\\)'
    r'|[PX^_].*?\x1b\\|[ -/]*[0-~])', re.DOTALL,
)
SGR = re.compile(r'\x1b\[[0-9:;]*m\Z')


def cell_width(char):
    if unicodedata.combining(char) or unicodedata.category(char) in ('Cf', 'Cc', 'Mn', 'Me'):
        return 0
    return 2 if unicodedata.east_asian_width(char) in ('W', 'F') else 1


def text_width(text):
    """Measure common Unicode characters while ignoring terminal escapes."""
    return sum(cell_width(char) for char in ESCAPE.sub('', text))


def wrap_line(line, width):
    """Wrap coloured text into cells, keeping SGR colours across wraps."""
    parts, active, output, cells = [], [], [], 0
    tokens = ESCAPE.split(line)
    escapes = ESCAPE.findall(line)
    for index, text in enumerate(tokens):
        for char in text:
            if char == '\t':
                char = ' '
            if unicodedata.category(char) == 'Cc':
                continue
            size = cell_width(char)
            if cells + size > width and cells:
                output.append(''.join(parts) + '\x1b[0m')
                parts, cells = list(active), 0
            parts.append(char)
            cells += size
        if index < len(escapes) and SGR.fullmatch(escapes[index]):
            code = escapes[index]
            if code in ('\x1b[m', '\x1b[0m'):
                active = []
            else:
                active.append(code)
            parts.append(code)
    output.append(''.join(parts) + '\x1b[0m')
    return output


def arrange(info, columns, rows):
    """Return pond width, information width and pages for this screen size."""
    widest = max((text_width(line) for line in info), default=0)
    pond_width = min(58, max(16, columns - widest - 2))
    info_width = columns - pond_width - 2
    # Preserve spacing whenever it fits; compact empty lines on shorter screens.
    source = info if len(info) <= rows else [line for line in info if text_width(line)]
    wrapped = [part for line in source for part in wrap_line(line, info_width)]
    if len(wrapped) <= rows:
        return pond_width, info_width, [wrapped]
    page_height = max(1, rows - 1)
    page_count = math.ceil(len(wrapped) / page_height)
    pages = []
    for i in range(page_count):
        page = wrapped[i * page_height:(i + 1) * page_height]
        page += [''] * (page_height - len(page))
        page.append(f'\x1b[2m[{i + 1}/{page_count}]\x1b[0m')
        pages.append(page)
    return pond_width, info_width, pages
