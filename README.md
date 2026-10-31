# Koi Fetch

An animated terminal pond where koi swim and hunt tiny food creatures. By
default, the pond appears beside your existing Fastfetch information.

## Install

Requires Python 3.9 or newer and a terminal with Unicode Braille and true-colour
support. Fastfetch is needed for the default mode; Omarchy is optional.

To install from a local checkout with [pipx](https://pipx.pypa.io/):

```sh
pipx install .
```

Alternatively, run directly from the checkout:

```sh
PYTHONPATH=src python3 -m koi_fetch
```

## Use

```sh
koi-fetch                            # Pond beside Fastfetch; automatic colours
koi-fetch --fullscreen               # Pond fills the terminal; no Fastfetch needed
koi-fetch --theme classic            # Fixed original colours
koi-fetch --theme omarchy            # Follow the active Omarchy theme
koi-fetch --fullscreen --theme classic
koi-fetch --help
```

The default `--theme auto` follows Omarchy when its palette is available, and
otherwise uses the classic colours. With Omarchy, the fish, food and particles
update when the theme changes. Explicit `--theme omarchy` reports an error if
the active palette is unavailable. Fastfetch information is captured at startup.

Press **Ctrl+C** to leave the pond. The pond responds to terminal resizing;
when the terminal is too small, it displays the required minimum size.

## Development

```sh
PYTHONPATH=src python3 -m unittest discover -s tests
```

`src/koi_fetch/data/koi-sprite.pgm` is bundled with the package.
`koi-source.png` is the source artwork used to make that sprite.

## Attribution

Koi steering, hunting and spine motion are adapted from
[ascii-sharks](https://github.com/stackedlol/ascii-sharks) by drewdi. Its MIT
license is included in [ASCII-SHARKS-LICENSE](ASCII-SHARKS-LICENSE).
