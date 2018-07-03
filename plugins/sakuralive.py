# -*- coding: utf-8 -*-
import logging
import random
import re

from io import BytesIO

from streamlink.packages.flashmedia import AMFPacket
from streamlink.plugin import Plugin, PluginError
from streamlink.plugin.api import http
from streamlink.plugin.api import useragents
from streamlink.stream import RTMPStream

log = logging.getLogger(__name__)


class SakuraLive(Plugin):

    url_gateway = 'http://chat.sakuralive.com/flashservices/gateway'
    url_id = 'http://chat.sakuralive.com/json/getPerformer/{0}'
    url_swf = 'http://chat.sakuralive.com/flash/chat/limited_preview.swf'

    # http://www.sakuralive.com/preview.php?CHANNELNAME
    _url_re = re.compile(r'https?://(?:www\.)?sakuralive\.com/preview.php\?(?P<channel>[^?&]+)')

    # CHANNELNAME = new Pf('CHANNELNAME', '12121212', '12/12/1212');
    _channel_id_re = re.compile(r'''
    \(
    (?P<q>["'])(?P<name>[^"']+)(?P=q),\s
    (?P=q)(?P<id>[^"']+)(?P=q),\s
    (?P=q)(?P<date>[^"']+)(?P=q)
    \);
    ''', re.VERBOSE)

    msg_1 = 'PAID content is not supported.'

    error_code = {
        '1': msg_1,
        '1006': 'Network disconnection.',
        '1115': 'The performer is offline.',
        '3001': msg_1,
        '3002': 'Session does not exist.',
        '3003': msg_1,
        '3004': msg_1,
        '3005': 'The performer is offline.',
        '3006': 'Free session started.',
    }

    @classmethod
    def can_handle_url(cls, url):
        return cls._url_re.match(url) is not None

    def _get_streams(self):
        log.debug('Version 2018-07-01')
        log.info('This is a custom plugin. '
                 'For support visit https://github.com/back-to/plugins')
        log.info('only FREE content is available.')
        http.headers.update({'User-Agent': useragents.FIREFOX})

        channel = self._url_re.match(self.url).group('channel')
        log.info('Channel: {0}'.format(channel))

        res = http.get(self.url_id.format(channel))
        m = self._channel_id_re.search(res.text)
        if not m:
            raise PluginError('Invalid channel name, can\'t find channel id.')

        channel_id = m.group('id')

        data = (
            b'\x00\x00\x00\x00\x00\x01\x00\x10remoting.doEvent\x00\x02/1'
            + b'\x00\x00\x00;\n\x00\x00\x00\x02\x02\x00\n'
            + b'getChannel\x03\x00\x0bperformerID\x02\x00\x08'
            + channel_id.encode('ascii')
            + b'\x00\x04type\x02\x00\x04free\x00\x00\x09'
        )

        res = http.post(
            self.url_gateway,
            headers={
                'Content-Type': 'application/x-amf',
                'Referer': self.url_swf,
            },
            data=data,
        )
        data = AMFPacket.deserialize(BytesIO(res.content))
        result = data.messages[0].value

        log.debug('--- DEBUG DATA ---'.format())
        for _r in result:
            log.debug('{0}: {1}'.format(_r, result[_r]))
        log.debug('--- DEBUG DATA ---'.format())

        if result['result'] != 'true':
            _err = self.error_code.get(str(int(result['errorCode'])))
            if _err:
                raise PluginError(_err)
            else:
                raise PluginError('Unknown error_code')

        channel_seq = result['channelSeq']
        host = random.choice(result['freeServerIP'].split(','))
        app = 'video_chat3_free_dx/{0}'.format(channel_seq)

        conn = [
            'O:1',
            'NS:channel:{0}'.format(channel_id, result['channelID']),
            'NS:pServer:{0}'.format(result['serverIP']),
            'NS:langID:en',
            'NS:channelSeq:{0}'.format(result['channelSeq']),
            'O:O',
        ]

        params = {
            'app': app,
            'flashVer': 'WIN 29,0,0,171',
            'swfVfy': self.url_swf,
            'rtmp': 'rtmp://{0}/{1}'.format(host, app),
            'live': True,
            'pageUrl': self.url,
            'playpath': 'free_performer',
            'conn': conn
        }

        yield 'live', RTMPStream(self.session, params)


__plugin__ = SakuraLive
