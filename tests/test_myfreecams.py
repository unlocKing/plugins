import unittest

from plugins.myfreecams import MyFreeCams


class TestPluginMyFreeCams(unittest.TestCase):
    def test_can_handle_url(self):
        should_match = [
            "https://m.myfreecams.com/models/UserName",
            "https://myfreecams.com/?id=10101010",
            "https://myfreecams.com/#UserName",
            "https://profiles.myfreecams.com/UserName",
            "https://www.myfreecams.com/#UserName",
            "https://www.myfreecams.com/UserName",
        ]
        for url in should_match:
            self.assertTrue(MyFreeCams.can_handle_url(url))

        should_not_match = [
            "https://www.myfreecams.com",
        ]
        for url in should_not_match:
            self.assertFalse(MyFreeCams.can_handle_url(url))
