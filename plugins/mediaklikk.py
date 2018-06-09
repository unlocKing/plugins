import logging
import re

from streamlink.plugin import Plugin
from streamlink.plugin.api import http

log = logging.getLogger(__name__)


class Mediaklikk(Plugin):

    _url_re = re.compile(r'https?://(?:www\.)?mediaklikk\.hu/')
    _id_re = re.compile(r'''(?P<q>["'])(?:streamId|token)(?P=q):(?P=q)(?P<id>[^"']+)(?P=q)''')

    new_self_url = 'https://player.mediaklikk.hu/playernew/player.php?video={0}'

    @classmethod
    def can_handle_url(cls, url):
        return cls._url_re.match(url)

    def _get_streams(self):
        log.info('This is a custom plugin. '
                 'For support visit https://github.com/back-to/plugins')
        res = http.get(self.url)

        m = self._id_re.search(res.text)
        if not m:
            log.info('Found no videoid.')
            self.url = 'resolve://{0}'.format(self.url)
            return self.session.streams(self.url)

        video_id = m.group('id')
        if video_id:
            log.debug('Found id: {0}'.format(video_id))
            self.url = self.new_self_url.format(video_id)

            return self.session.streams(self.url)


__plugin__ = Mediaklikk
