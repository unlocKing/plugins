import unittest

from src.streamlink.plugins.ok_live import OK_live


class TestPluginOKru(unittest.TestCase):
    def test_can_handle_url(self):
        should_match = [
            "https://www.ok.ru/live/73314",
            "https://www.ok.ru/video/549049207439",
        ]
        for url in should_match:
            self.assertTrue(OK_live.can_handle_url(url))

        should_not_match = [
            "https://www.ok.ru",
        ]
        for url in should_not_match:
            self.assertFalse(OK_live.can_handle_url(url))
