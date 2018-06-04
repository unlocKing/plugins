import unittest

from src.streamlink.plugins.fc2 import FC2


class TestPluginFC2(unittest.TestCase):
    def test_can_handle_url(self):
        should_match = [
            'https://live.fc2.com/12345678/',
            'https://live.fc2.com/87654321',
        ]
        for url in should_match:
            self.assertTrue(FC2.can_handle_url(url))

        should_not_match = [
            'https://live.fc2.com/',
            'https://live.fc2.com/2_12378733/',
        ]
        for url in should_not_match:
            self.assertFalse(FC2.can_handle_url(url))
