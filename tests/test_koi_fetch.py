import math
import json
import io
import os
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr
from unittest.mock import patch, Mock

from koi_fetch import cli, layout, render, world
from koi_fetch.theme import ThemeColours


class KoiFetchTests(unittest.TestCase):
    def test_command_defaults_and_modes(self):
        args = cli.parser().parse_args([])
        self.assertFalse(args.fullscreen)
        self.assertEqual(args.theme, 'auto')
        args = cli.parser().parse_args(['--fullscreen', '--theme', 'classic'])
        self.assertTrue(args.fullscreen)
        self.assertEqual(args.theme, 'classic')

    def test_render_dimensions_and_bundled_sprite(self):
        sprite = cli.load_sprite()
        self.assertEqual(len(sprite), 128 * 64)
        colours = ThemeColours().colours
        for width, height in ((20, 10), (58, 25), (120, 35)):
            fish = world.new_swimmers(width, height)
            food = world.new_food(width, height)
            lines = render.pond(0, sprite, fish, food, colours, width, height)
            self.assertEqual(len(lines), height)
            self.assertTrue(all(len(re.sub(r'\x1b\[[0-9;]*m', '', line)) == width
                                for line in lines))

    def test_resize_preserves_joint_lengths_and_food(self):
        fish = world.new_swimmers(58, 25)
        food = world.new_food(58, 25)
        original_food = food[0]
        world.resize(fish, food, 58, 25, 120, 35)
        self.assertIs(food[0], original_food)
        for swimmer in fish:
            for a, b in zip(swimmer['nodes'], swimmer['nodes'][1:]):
                self.assertAlmostEqual(math.dist(a, b), swimmer['length'] / (world.NODES - 1))
        speeds_before = [swimmer['speed'] for swimmer in fish]
        world.resize(fish, food, 120, 35, 20, 10)
        for swimmer, previous_speed in zip(fish, speeds_before):
            self.assertLess(swimmer['speed'], previous_speed)
            for a, b in zip(swimmer['nodes'], swimmer['nodes'][1:]):
                self.assertAlmostEqual(math.dist(a, b), swimmer['length'] / (world.NODES - 1))

    def test_fish_targets_eats_and_food_respawns(self):
        fish = world.new_swimmers(58, 25, 1)[0]
        food = world.new_food(58, 25, 1)
        fish.update(heading=0.0, hunger=.8, target=None, retarget_at=0.0)
        fish['nodes'] = [(50 - i * fish['length'] / (world.NODES - 1), 50)
                         for i in range(world.NODES)]
        pellet = food[0]
        pellet.update(x=58, y=50, vx=0.0, vy=0.0, alive=True)
        world.step_swimmers([fish], food, .08, .08, 58, 25)
        self.assertIs(fish['target'], pellet)
        for i in range(1, 100):
            world.step_swimmers([fish], food, .08, (i + 1) * .08, 58, 25)
            if not pellet['alive']:
                break
        self.assertFalse(pellet['alive'])
        world.step_food(food, [fish], .08, pellet['respawn_at'] + .01, 58, 25)
        self.assertTrue(pellet['alive'])

    def test_classic_does_not_need_omarchy(self):
        with patch('koi_fetch.theme.subprocess.run', side_effect=FileNotFoundError):
            theme = ThemeColours()
            before = theme.colours
            theme.poll(1)
            self.assertEqual(theme.colours, before)
            self.assertIsNone(theme.signature)

    def test_auto_falls_back_to_terminal_palette(self):
        with tempfile.TemporaryDirectory() as directory:
            theme = ThemeColours('auto', Path(directory) / 'missing.toml')
            terminal = ThemeColours('terminal')
            theme.poll(1)
            self.assertEqual(theme.colours, terminal.colours)
            self.assertNotEqual(theme.colours, ThemeColours('classic').colours)
            self.assertTrue(all('38;2;' not in colour for palette in theme.colours for colour in palette))

    def test_fastfetch_receives_requested_config_once(self):
        result = Mock(stdout='custom information\n')
        with patch('koi_fetch.cli.subprocess.run', return_value=result) as run:
            self.assertEqual(cli.fastfetch_output('my preset.jsonc'), ['custom information'])
        args = run.call_args.args[0]
        self.assertEqual(args, ['fastfetch', '--config', 'my preset.jsonc', '--logo', 'none', '--pipe', 'false'])
        run.assert_called_once()

    @unittest.skipUnless(shutil.which('fastfetch'), 'Fastfetch is not installed')
    def test_custom_fastfetch_logo_positions_do_not_change_information(self):
        with tempfile.TemporaryDirectory() as directory:
            config = Path(directory) / 'config.jsonc'
            for position in ('left', 'right', 'top'):
                config.write_text(json.dumps({'logo': {'position': position},
                                              'modules': [{'type': 'custom', 'format': 'USER_MODULE'}]}))
                lines = cli.fastfetch_output(str(config))
                text = [layout.ESCAPE.sub('', line) for line in lines]
                self.assertIn('USER_MODULE', text)

    def test_responsive_layout_wraps_and_paginates(self):
        info = ['\x1b[31m' + 'x' * 60 + '\x1b[0m'] + [f'line {i}' for i in range(35)]
        pond_width, info_width, pages = layout.arrange(info, 80, 24)
        self.assertGreaterEqual(pond_width, 16)
        self.assertEqual(pond_width + info_width + 2, 80)
        self.assertGreater(len(pages), 1)
        for page in pages:
            self.assertEqual(len(page), 24)
            self.assertTrue(all(layout.text_width(line) <= info_width for line in page))
        visible = ''.join(layout.ESCAPE.sub('', line) for page in pages for line in page)
        self.assertIn('x' * 60, visible)
        self.assertIn('line 34', visible)

    def test_width_counts_wide_and_combining_characters(self):
        self.assertEqual(layout.text_width('\x1b[31m界e\u0301\x1b[0m'), 3)
        self.assertEqual(len(layout.wrap_line('界界界', 4)), 2)

    def test_missing_fastfetch_explains_fullscreen_option(self):
        message = io.StringIO()
        with patch.object(cli.sys.stdin, 'isatty', return_value=True), \
             patch.object(cli.sys.stdout, 'isatty', return_value=True), \
             patch.dict(os.environ, {'TERM': 'xterm-256color'}), \
             patch('koi_fetch.cli.shutil.which', return_value=None), redirect_stderr(message):
            self.assertEqual(cli.main([]), 1)
        self.assertIn('--fullscreen', message.getvalue())


if __name__ == '__main__':
    unittest.main()
