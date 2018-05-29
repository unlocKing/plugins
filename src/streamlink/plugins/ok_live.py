# -*- coding: utf-8 -*-
import re

from streamlink.compat import unquote
from streamlink.plugin import Plugin
from streamlink.plugin.api import http
from streamlink.plugin.api import useragents
from streamlink.plugin.api import validate
from streamlink.stream import HLSStream
from streamlink.stream import HTTPStream
from streamlink.stream import RTMPStream
from streamlink.utils import parse_json

try:
    # python 3.4+
    from html import unescape as compat_unescape
except ImportError:
    # python 2.7
    from HTMLParser import HTMLParser
    compat_unescape = HTMLParser().unescape


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
            validate.transform(compat_unescape),
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
            return weight, 'okru'

        return Plugin.stream_weight(key)

    def _get_streams(self):
        self.logger.info('This is a custom plugin. '
                         'For support visit https://github.com/back-to/plugins')
        headers = {
            'User-Agent': useragents.FIREFOX,
            'Referer': self.url
        }
        data = http.get(self.url, headers=headers, schema=self._data_schema)
        metadata = data.get('metadata')
        metadata_url = data.get('metadataUrl')
        if metadata_url:
            metadata = http.post(metadata_url, headers=headers, schema=self._metadata_schema)

        if metadata:
            list_hls = [
                metadata.get('hlsManifestUrl'),
                metadata.get('hlsMasterPlaylistUrl'),
            ]
            for hls_url in list_hls:
                if hls_url is not None:
                    for s in HLSStream.parse_variant_playlist(self.session, hls_url, headers=headers).items():
                        yield s

            if metadata.get('videos'):
                for http_stream in metadata.get('videos'):
                    http_name = http_stream['name']
                    http_url = http_stream['url']
                    yield http_name, HTTPStream(self.session, http_url, headers=headers)

            if metadata.get('rtmpUrl'):
                yield 'live', RTMPStream(self.session, params={'rtmp': metadata.get('rtmpUrl')})


__plugin__ = OK_live
