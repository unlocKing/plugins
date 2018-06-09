import unittest

from plugins.mediaklikk import Mediaklikk


class TestPluginMediaklikk(unittest.TestCase):

    def test_can_handle_url(self):
        should_match = [
            'https://www.mediaklikk.hu/m1-elo',
            'https://www.mediaklikk.hu/m2-elo',
            'https://www.mediaklikk.hu/m4-elo',
            'https://www.mediaklikk.hu/m5-elo',
            'https://www.mediaklikk.hu/duna-elo',
            'https://www.mediaklikk.hu/duna-world-elo',
        ]
        for url in should_match:
            self.assertTrue(Mediaklikk.can_handle_url(url))

        should_not_match = [
            'https://example.com/index.html',
        ]
        for url in should_not_match:
            self.assertFalse(Mediaklikk.can_handle_url(url))
