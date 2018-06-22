import unittest

from plugins.showup import ShowUp


class TestPluginShowUp(unittest.TestCase):
    def test_can_handle_url(self):
        should_match = [
            'https://showup.tv/example',
            'http://showup.tv/example',
        ]
        for url in should_match:
            self.assertTrue(ShowUp.can_handle_url(url))

        should_not_match = [
            'https://example.com/index.html',
        ]
        for url in should_not_match:
            self.assertFalse(ShowUp.can_handle_url(url))
