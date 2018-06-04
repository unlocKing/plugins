import unittest

from plugins.inter import Inter


class TestPluginInter(unittest.TestCase):

    def test_can_handle_url(self):
        should_match = [
            "http://inter.ua/ru/live",
            "http://www.k1.ua/uk/live",
            "http://ntn.ua/ru/live",
        ]
        for url in should_match:
            self.assertTrue(Inter.can_handle_url(url))

        should_not_match = [
            "https://example.com/index.html",
        ]
        for url in should_not_match:
            self.assertFalse(Inter.can_handle_url(url))
