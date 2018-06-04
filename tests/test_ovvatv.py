import unittest

from src.streamlink.plugins.ovvatv import ovvaTV


class TestPluginovvaTV(unittest.TestCase):

    def test_can_handle_url(self):
        should_match = [
            'https://1plus1.video/tvguide/embed/1?autoplay=1&l=ua',
            'https://1plus1.video/tvguide/embed/16?autoplay=1&l=ua',
            'https://1plus1.video/tvguide/embed/2?autoplay=1&l=ua',
            'https://1plus1.video/tvguide/embed/3?autoplay=1&l=ua',
            'https://1plus1.video/tvguide/embed/4?autoplay=1&l=ua',
            'https://1plus1.video/tvguide/embed/5?autoplay=1&l=ua',
            'https://1plus1.video/tvguide/embed/7?autoplay=1&l=ua',
        ]
        for url in should_match:
            self.assertTrue(ovvaTV.can_handle_url(url))

        should_not_match = [
            'https://1plus1.video/',
            'https://1plus1.video/tvguide/1plus1/online',
            'https://1plus1.video/tvguide/1plus1in/online',
            'https://1plus1.video/tvguide/2plus2/online',
            'https://1plus1.video/tvguide/tet/online',
            'https://1plus1.video/tvguide/plusplus/online',
            'https://1plus1.video/tvguide/bigudi/online',
            'https://1plus1.video/tvguide/uniantv/online',
        ]
        for url in should_not_match:
            self.assertFalse(ovvaTV.can_handle_url(url))
