import unittest

from plugins.onetv import OneTV


class TestPluginPerviyKanal(unittest.TestCase):
    def test_can_handle_url(self):
        regex_test_list = [
            "https://media.1tv.ru/embed/ctcmedia/ctc-che.html?start=auto",
            "https://media.1tv.ru/embed/ctcmedia/ctc-dom.html?start=auto",
            "https://media.1tv.ru/embed/ctcmedia/ctc-love.html?start=auto",
            "https://stream.1tv.ru/live",
            "https://www.1tv.ru/embedlive?start=auto",
            "https://www.1tv.ru/live",
            "https://www.chetv.ru/online/",
            "https://www.ctc.ru/online/",
            "https://www.ctclove.ru/online/",
            "https://domashniy.ru/online",
            "https://ren.tv/live",
            "https://media.1tv.ru/embed/nmg/nmg-ren.html",
        ]

        for url in regex_test_list:
            self.assertTrue(OneTV.can_handle_url(url))
