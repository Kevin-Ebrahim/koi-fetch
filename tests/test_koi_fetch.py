import math
import re
import unittest
from unittest.mock import patch

from koi_fetch import cli, render, world
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
        world.resize(fish, food, 120, 35, 20, 10)
        for swimmer in fish:
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


if __name__ == '__main__':
    unittest.main()
