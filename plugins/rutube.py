import logging
import re

from streamlink.exceptions import NoStreamsError
from streamlink.plugin import Plugin
from streamlink.plugin.api import http
from streamlink.plugin.api import useragents
from streamlink.plugin.api import validate
from streamlink.stream import HDSStream
from streamlink.stream import HLSStream

log = logging.getLogger(__name__)


class RUtube(Plugin):
    ''' https://rutube.ru/feeds/live/ '''

    api_play = 'https://rutube.ru/api/play/options/{0}/?format=json&no_404=true&referer={1}'

    _url_re = re.compile(r'''https?://(\w+\.)?rutube\.ru/(?:play|video)/(?:embed/)?(?P<id>[a-z0-9]+)''')

    _video_schema = validate.Schema(
        validate.any({
            'live_streams': {
                validate.text: [{
                    'url': validate.text,
                }]
            },
            'video_balancer': {
                validate.text: validate.text,
            },
        }, {}
        )
    )

    @classmethod
    def can_handle_url(cls, url):
        return cls._url_re.match(url) is not None

    def _get_streams(self):
        log.debug('Version 2018-07-01')
        log.info('This is a custom plugin. '
                 'For support visit https://github.com/back-to/plugins')
        hls_urls = []
        hds_urls = []

        http.headers.update({'User-Agent': useragents.FIREFOX})

        match = self._url_re.match(self.url)
        if match is None:
            return

        video_id = match.group('id')
        log.debug('video_id: {0}'.format(video_id))

        res = http.get(self.api_play.format(video_id, self.url))
        data = http.json(res, schema=self._video_schema)

        live_data = data.get('live_streams')
        vod_data = data.get('video_balancer')

        if live_data:
            log.debug('Found live_data')
            for d in live_data['hls']:
                hls_urls.append(d['url'])
            for e in live_data['hds']:
                hds_urls.append(e['url'])
        elif vod_data:
            log.debug('Found vod_data')
            hls_urls.append(vod_data['m3u8'])
            hds_urls.append(vod_data['default'])
        else:
            log.error('This video is not available in your region.')
            raise NoStreamsError(self.url)

        for hls_url in hls_urls:
            log.debug('HLS URL: {0}'.format(hls_url))
            for s in HLSStream.parse_variant_playlist(self.session, hls_url).items():
                yield s

        for hds_url in hds_urls:
            log.debug('HDS URL: {0}'.format(hds_url))
            for s in HDSStream.parse_manifest(self.session, hds_url).items():
                yield s


__plugin__ = RUtube
