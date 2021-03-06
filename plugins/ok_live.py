# -*- coding: utf-8 -*-
import logging
import re

from streamlink.compat import html_unescape, unquote
from streamlink.plugin import Plugin
from streamlink.plugin.api import http, useragents, validate
from streamlink.stream import HLSStream, HTTPStream, RTMPStream
from streamlink.utils import parse_json

log = logging.getLogger(__name__)


class OK_live(Plugin):
    '''Plugin for ok.ru'''

    _data_re = re.compile(r'''data-options=(?P<q>["'])(?P<data>{[^"']+})(?P=q)''')
    _url_re = re.compile(r'''https?://(?:www\.)?ok\.ru/''')

    _metadata_schema = validate.Schema(
        validate.transform(parse_json),
        validate.any({
            'videos': validate.any(
                [],
                [
                    {
                        'name': validate.text,
                        'url': validate.text,
                    }
                ]
            ),
            validate.optional('hlsManifestUrl'): validate.text,
            validate.optional('hlsMasterPlaylistUrl'): validate.text,
            validate.optional('liveDashManifestUrl'): validate.text,
            validate.optional('rtmpUrl'): validate.text,
        }, None)
    )

    _data_schema = validate.Schema(
        validate.all(
            validate.transform(_data_re.search),
            validate.get('data'),
            validate.transform(html_unescape),
            validate.transform(parse_json),
            validate.get('flashvars'),
            validate.any(
                {
                    'metadata': _metadata_schema

                },
                {
                    'metadataUrl': validate.transform(unquote)
                },
                None
            )
        )
    )

    QUALITY_WEIGHTS = {
        'full': 1080,
        '1080': 1080,
        'hd': 720,
        '720': 720,
        'sd': 480,
        '480': 480,
        '360': 360,
        'low': 360,
        'lowest': 240,
        'mobile': 144,
    }

    @classmethod
    def can_handle_url(cls, url):
        return cls._url_re.match(url)

    @classmethod
    def stream_weight(cls, key):
        weight = cls.QUALITY_WEIGHTS.get(key)
        if weight:
            return weight, 'ok_live'

        return Plugin.stream_weight(key)

    def _get_streams(self):
        log.debug('Version 2018-07-01')
        log.info('This is a custom plugin. '
                 'For support visit https://github.com/back-to/plugins')
        headers = {
            'User-Agent': useragents.FIREFOX,
            'Referer': self.url
        }
        http.headers.update(headers)
        data = http.get(self.url, schema=self._data_schema)
        metadata = data.get('metadata')
        metadata_url = data.get('metadataUrl')
        if metadata_url:
            metadata = http.post(metadata_url, schema=self._metadata_schema)

        if metadata:
            list_hls = [
                metadata.get('hlsManifestUrl'),
                metadata.get('hlsMasterPlaylistUrl'),
            ]
            for hls_url in list_hls:
                if hls_url is not None:
                    for s in HLSStream.parse_variant_playlist(self.session, hls_url).items():
                        yield s

            if metadata.get('videos'):
                for http_stream in metadata['videos']:
                    http_name = http_stream['name']
                    http_url = http_stream['url']
                    try:
                        http_name = '{0}p'.format(self.QUALITY_WEIGHTS[http_name])
                    except KeyError:
                        pass
                    yield http_name, HTTPStream(self.session, http_url)

            if metadata.get('rtmpUrl'):
                yield 'live', RTMPStream(self.session, params={'rtmp': metadata['rtmpUrl']})


__plugin__ = OK_live
