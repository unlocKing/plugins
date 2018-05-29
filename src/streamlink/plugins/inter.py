import re

from streamlink.plugin import Plugin
from streamlink.plugin.api import http
from streamlink.plugin.api import useragents
from streamlink.stream import HLSStream


class Inter(Plugin):
    '''streamlink Plugin for Livestreams of
        - http://inter.ua/ru/live
        - http://www.k1.ua/uk/live
        - http://ntn.ua/ru/live
    '''

    _url_re = re.compile(r'''https?://
        (?:www\.)?
        (?:
            inter
            |
            k1
            |
            ntn
        )
        \.ua/
        (?:
            uk|ua|ru
        )
        /live
        ''', re.VERBOSE | re.IGNORECASE)
    _playlist_re = re.compile(r'''hlssource:\s?["'](?P<url>[^"'\s]+)["']''', re.IGNORECASE)

    @classmethod
    def can_handle_url(cls, url):
        return cls._url_re.match(url)

    def _get_streams(self):
        self.logger.info('This is a custom plugin. '
                         'For support visit https://github.com/back-to/plugins')
        headers = {
            'Referer': self.url,
            'User-Agent': useragents.FIREFOX
        }

        res = http.get(self.url, headers=headers)

        m = self._playlist_re.search(res.text)
        if not m:
            return

        res = http.get(m.group('url'), headers=headers)
        if not res.text.startswith('#EXTM3U'):
            hls_url = http.json(res).get('redir')
        else:
            hls_url = m.group('url')

        if hls_url is not None:
            self.logger.debug('HLS URL: {0}'.format(hls_url))
            streams = HLSStream.parse_variant_playlist(self.session, hls_url, headers=headers)
            if not streams:
                return {'live': HLSStream(self.session, hls_url, headers=headers)}
            else:
                return streams


__plugin__ = Inter
