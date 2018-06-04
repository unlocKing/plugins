import re

from streamlink import PluginError
from streamlink.plugin import Plugin
from streamlink.plugin.api import http
from streamlink.plugin.api import useragents
from streamlink.stream import HLSStream


class Plexstorm(Plugin):

    verify_url = 'https://plexstorm.com/age-verification'

    _url_re = re.compile(r'https?://(?:www\.)?plexstorm\.com/stream/(?P<username>[^/]+)')
    _hls_re = re.compile(r'''["'](?P<url>[^"']+\.m3u8)["']''')
    _token_re = re.compile(r'''name=["']csrf-token["']\scontent=["'](?P<data>[^"']+)["']''')

    @classmethod
    def can_handle_url(cls, url):
        return cls._url_re.match(url) is not None

    def _get_streams(self):
        http.headers.update({'User-Agent': useragents.FIREFOX})
        self.logger.info('This is a custom plugin. '
                         'For support visit https://github.com/back-to/plugins')
        res = http.get(self.url)

        m = self._token_re.search(res.text)
        if not m:
            raise PluginError('No token found.')

        data = {
            '_method': 'PATCH',
            '_token': m.group('data')
        }
        http.post(self.verify_url, data=data)

        res = http.get(self.url)
        m = self._hls_re.search(res.text)
        if not m:
            self.logger.debug('No video url found.')
            return

        hls_url = m.group('url')
        self.logger.debug('URL={0}'.format(hls_url))
        streams = HLSStream.parse_variant_playlist(self.session, hls_url)
        if not streams:
            return {'live': HLSStream(self.session, hls_url)}
        else:
            return streams


__plugin__ = Plexstorm
