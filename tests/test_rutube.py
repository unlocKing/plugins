import unittest

from src.streamlink.plugins.rutube import RUtube


class TestPluginRUtube(unittest.TestCase):
    def test_can_handle_url(self):
        should_match = [
            'https://rutube.ru/play/embed/10711575?bmstart=0',
            'https://rutube.ru/video/11bbbec75a2ceb8cf446ad16813c6eec/?pl_type=source',
            'https://rutube.ru/video/cdc953e94e354afcbd312602c2005b9f/'
        ]
        for url in should_match:
            self.assertTrue(RUtube.can_handle_url(url))

        should_not_match = [
            'https://rutube.ru',
        ]
        for url in should_not_match:
            self.assertFalse(RUtube.can_handle_url(url))
