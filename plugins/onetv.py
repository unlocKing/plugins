import logging
import random
import re
import time

from streamlink.plugin import Plugin
from streamlink.plugin.api import http
from streamlink.plugin.api import useragents
from streamlink.plugin.api import validate
from streamlink.stream import HLSStream

log = logging.getLogger(__name__)


class OneTV(Plugin):

    API_HLS_SESSION = 'https://stream.1tv.ru/get_hls_session'

    channel_map = {
        '1tv': '1tv',
        'chetv': 'ctc-che',
        'ctc': 'ctc',
        'ctclove': 'ctc-love',
        'domashniy': 'ctc-dom',
        'ren': 'ren-tv',
        '5-tv': 'tv-5',
        '5tv': 'tv-5',
    }

    _session_schema = validate.Schema(
        {
            's': validate.text
        }
    )

    _url_re = re.compile(r'''https?://
        (?:(?:media|stream|www)?\.)?
        (?:
        (?P<domain>
            1tv
            |
            chetv
            |
            ctc(?:love)?
            |
            domashniy
            |
            5-tv
            )\.ru/
                (?:
                embed/ctcmedia/(?P<channel>[^/?]+.).html
                |
                embedlive
                |
                iframed
                |
                live
                |
                online
                |
                embed/nmg/nmg-(?P<channel2>[^/?]+.)\.html
                )
        |
        (?P<domain2>
            ren
            )\.tv/
                (?:
                live
                )
        )
        ''', re.VERBOSE)

    @classmethod
    def can_handle_url(cls, url):
        return cls._url_re.match(url)

    def _get_streams(self):
        log.info('This is a custom plugin. '
                 'For support visit https://github.com/back-to/plugins')
        headers = {
            'Referer': self.url,
            'User-Agent': useragents.FIREFOX
        }
        http.headers.update(headers)

        match = self._url_re.match(self.url)
        channel = match.group('channel')
        if not channel:
            channel = (match.group('domain2')
                       or match.group('channel2')
                       or match.group('domain'))
            try:
                channel = self.channel_map[channel]
            except KeyError:
                log.error('This channel is currently not supported.')

        cdn = random.choice(['cdn8', 'edge1', 'edge3'])
        query_e = 'e={0}'.format(int(time.time()))
        server = random.choice(['9', '10'])
        hls_url = 'https://mobdrm.1tv.ru/hls-live{server}/streams/{channel}/{channel}.m3u8?cdn=https://{cdn}.1internet.tv&{query}'.format(
            cdn=cdn,
            channel=channel,
            query=query_e,
            server=server,
        )

        res = http.get(self.API_HLS_SESSION)
        json_session = http.json(res, schema=self._session_schema)
        hls_url = '{url}&s={session}'.format(url=hls_url, session=json_session['s'])

        if hls_url:
            log.debug('HLS URL: {0}'.format(hls_url))
            streams = HLSStream.parse_variant_playlist(self.session, hls_url, name_fmt='{pixels}_{bitrate}')
            if not streams:
                return {'live': HLSStream(self.session, hls_url)}
            else:
                return streams


__plugin__ = OneTV
