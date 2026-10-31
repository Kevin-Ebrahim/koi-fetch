# Koi Fetch

An animated pond of koi that swim beside your existing Fastfetch information.
The koi pursue small swimming food creatures, which reappear after being eaten.
Press **Ctrl+C** to leave the pond and return to the terminal.

## Run

You need Python 3, Fastfetch, and a terminal with Unicode Braille and true-colour
support. The animation needs enough terminal space for the pond and Fastfetch;
it displays the required size if the window is too small.

From this directory, run the original, fixed-colour version:

```sh
python3 koi-fetch.py
```

On Omarchy, run the theme-aware version instead:

```sh
python3 koi-fetch-themed.py
```

The theme-aware version reads the active Omarchy palette and updates the koi,
food and water particles when the theme changes. If the palette is unavailable,
it retains the last valid colours or uses its built-in defaults. Fastfetch's
system information is captured at startup.

Both versions load `koi-sprite.pgm` from the same directory as the script.
`koi-source.png` is the source artwork used to make that sprite.

## Attribution

Koi steering, hunting and spine motion are adapted from
[ascii-sharks](https://github.com/stackedlol/ascii-sharks) by drewdi. Its MIT
license is included in [ASCII-SHARKS-LICENSE](ASCII-SHARKS-LICENSE).
