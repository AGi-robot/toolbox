import math
import unittest
from agi_toolbox.lighting_effects import LightingEffect, morse_units


class LightingTests(unittest.TestCase):
    def test_gradient_and_zero_steps(self):
        effect = LightingEffect(start_color='#FF0000', end_color='#0000FF', brightness=1,
                                transition_seconds=2, intermediate_steps=1)
        self.assertEqual(effect.color_at(0), (255, 0, 0))
        self.assertEqual(effect.color_at(1), (128, 0, 128))
        self.assertEqual(effect.color_at(2), (0, 0, 255))
        self.assertEqual(effect.color_at(4), (255, 0, 0))
        jump = LightingEffect(start_color='#FF0000', end_color='#0000FF', brightness=1,
                              transition_seconds=2, intermediate_steps=0, loop=False)
        self.assertEqual(jump.color_at(.9), (255, 0, 0))
        self.assertEqual(jump.color_at(1.9), (0, 0, 255))
        self.assertEqual(jump.color_at(2), (0, 0, 255))
        self.assertEqual(jump.color_at(20), (0, 0, 255))

    def test_morse_spacing(self):
        self.assertEqual(morse_units('ET'), tuple([1] + [0]*3 + [1]*3 + [0]*7))
        self.assertEqual(morse_units('E E'), tuple([1] + [0]*7 + [1] + [0]*7))
        effect = LightingEffect(start_color='#FFFFFF', brightness=1, rhythm='morse', morse_text='E')
        self.assertEqual(effect.color_at(0), (255, 255, 255))
        self.assertEqual(effect.color_at(.25), (0, 0, 0))

    def test_invalid_inputs(self):
        for arguments in ({'brightness': math.nan}, {'duration_seconds': math.inf},
                          {'intermediate_steps': True}, {'start_color': 'red'},
                          {'morse_text': 'é'}, {'rhythm': 'morse'}, {'rainbow': 1},
                          {'rhythm_seconds': .1}, {'transition_colors': ['#000000']*17}):
            with self.subTest(arguments=arguments), self.assertRaises((TypeError, ValueError)):
                LightingEffect(**arguments)

    def test_stationary_rainbow_and_rhythms(self):
        effect = LightingEffect(start_color='#123456', end_color='#FFFFFF', rhythm='stationary', brightness=1)
        self.assertEqual(effect.color_at(0), effect.color_at(5))
        rainbow = LightingEffect(rainbow=True, brightness=1, transition_seconds=6)
        self.assertNotEqual(rainbow.color_at(0), rainbow.color_at(2))
        blink = LightingEffect(start_color='#FFFFFF', brightness=1, rhythm='blink_fast')
        self.assertEqual(blink.color_at(.1), (255, 255, 255))
        self.assertEqual(blink.color_at(.6), (0, 0, 0))
        for rhythm in ('heartbeat', 'random'):
            effect = LightingEffect(rhythm=rhythm)
            self.assertEqual(effect.color_at(.2), effect.color_at(.2))

if __name__ == '__main__':
    unittest.main()
