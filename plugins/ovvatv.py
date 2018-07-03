import logging
import re

from base64 import b64decode
from datetime import datetime

from streamlink import PluginError
from streamlink.plugin import Plugin
from streamlink.plugin.api import http
from streamlink.plugin.api import useragents
from streamlink.plugin.api import validate
from streamlink.stream import HLSStream
from streamlink.utils import parse_json

log = logging.getLogger(__name__)


class ovvaTV(Plugin):
    url_re = re.compile(r'https?://(?:www\.)?1plus1\.video/tvguide/embed/[^/]')
    data_re = re.compile(r'''ovva-player["'],["'](.*?)["']\)};''')
    next_date_re = re.compile(r'''<div\sclass=["']o-message-timer['']\sdata-timer=["'](\d+)["']''')
    ovva_data_schema = validate.Schema({
        'balancer': validate.url()
    }, validate.get('balancer'))
    ovva_redirect_schema = validate.Schema(validate.all(
        validate.transform(lambda x: x.split('=')),
        ['302', validate.url()],
        validate.get(1)
    ))

    @classmethod
    def can_handle_url(cls, url):
        return cls.url_re.match(url) is not None

    def _get_streams(self):
        http.headers.update({'User-Agent': useragents.FIREFOX})
        log.debug('Version 2018-07-01')
        log.info('This is a custom plugin. '
                 'For support visit https://github.com/back-to/plugins')
        res = http.get(self.url)
        data = self.data_re.search(res.text)
        next_date = self.next_date_re.search(res.text)
        if data:
            try:
                ovva_url = parse_json(b64decode(data.group(1)).decode('utf8'), schema=self.ovva_data_schema)
                stream_url = http.get(ovva_url, schema=self.ovva_redirect_schema)
            except PluginError as e:
                log.error('Could not find stream URL: {0}', e)
            else:
                return HLSStream.parse_variant_playlist(self.session, stream_url)
        elif next_date:
            log.info('The broadcast will be available at {0}'.format(
                datetime.fromtimestamp(int(next_date.group(1))).strftime('%Y-%m-%d %H:%M:%S')))
        else:
            log.error('Could not find player data.')


__plugin__ = ovvaTV
