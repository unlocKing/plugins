import unittest

from plugins.plexstorm import Plexstorm


class TestPluginPlexstorm(unittest.TestCase):
    def test_can_handle_url(self):
        should_match = [
            'https://plexstorm.com/stream/username',
        ]
        for url in should_match:
            self.assertTrue(Plexstorm.can_handle_url(url))

        should_not_match = [
            'https://plexstorm.com/',
        ]
        for url in should_not_match:
            self.assertFalse(Plexstorm.can_handle_url(url))
