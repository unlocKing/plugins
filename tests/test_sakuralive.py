import unittest

from plugins.sakuralive import SakuraLive


class TestPluginSakuraLive(unittest.TestCase):
    def test_can_handle_url(self):
        should_match = [
            'http://www.sakuralive.com/preview.php?CHANNELNAME',
        ]
        for url in should_match:
            self.assertTrue(SakuraLive.can_handle_url(url))

        should_not_match = [
            'https://example.com/index.html',
        ]
        for url in should_not_match:
            self.assertFalse(SakuraLive.can_handle_url(url))
