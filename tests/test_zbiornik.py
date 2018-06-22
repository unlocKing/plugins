import unittest

from plugins.zbiornik import Zbiornik


class TestPluginZbiornik(unittest.TestCase):
    def test_can_handle_url(self):
        should_match = [
            'http://zbiornik.tv/username',
            'https://zbiornik.tv/username',
            'https://zbiornik.tv/username/',
        ]
        for url in should_match:
            self.assertTrue(Zbiornik.can_handle_url(url))

        should_not_match = [
            'https://example.com/index.html',
            'https://zbiornik.tv/username/video/123ABC',
        ]
        for url in should_not_match:
            self.assertFalse(Zbiornik.can_handle_url(url))
