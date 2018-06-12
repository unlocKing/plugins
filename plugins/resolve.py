# -*- coding: utf-8 -*-
import logging
import re

from streamlink import NoPluginError
from streamlink import NoStreamsError
from streamlink.compat import is_py2
from streamlink.compat import unquote
from streamlink.compat import urljoin
from streamlink.compat import urlparse
from streamlink.plugin import Plugin
from streamlink.plugin import PluginArgument
from streamlink.plugin import PluginArguments
from streamlink.plugin.api import http
from streamlink.plugin.api import useragents
from streamlink.plugin.plugin import HIGH_PRIORITY
from streamlink.plugin.plugin import NO_PRIORITY
from streamlink.stream import HDSStream
from streamlink.stream import HLSStream
from streamlink.stream import HTTPStream
from streamlink.stream.dash import DASHStream
from streamlink.utils import update_scheme

# Regex for iFrames
_iframe_re = re.compile(r'''
    <ifr(?:["']\s?\+\s?["'])?ame
    (?!\sname=["']g_iFrame).*?src=
    ["'](?P<url>[^"'\s<>]+)["']
    .*?(?:/>|>(?:[^<>]+)?
    </ifr(?:["']\s?\+\s?["'])?ame(?:\s+)?>)
    ''', re.VERBOSE | re.IGNORECASE | re.DOTALL)

# Regex for playlist files
_playlist_re = re.compile(r'''
    (?:["']|=|&quot;)(?P<url>
        (?<!title=["'])
            [^"'<>\s\;{}]+\.(?:m3u8|f4m|mp3|mp4|mpd)
        (?:\?[^"'<>\s\\{}]+)?)
    (?:["']|(?<!;)\s|>|\\&quot;)
    ''', re.DOTALL | re.VERBOSE)

log = logging.getLogger(__name__)


def comma_list(values):
    if is_py2:
        return [val.decode('utf8').strip() for val in values.split(',')]
    return [val.strip() for val in values.split(',')]


class ResolveCache:
    '''used as temporary url cache
       - ResolveCache.cache_url_list
    '''
    pass


class Resolve(Plugin):
    '''Plugin that will try to find a valid streamurl on every website

    Supported
        - embedded url of an already existing plugin
        - website with an unencrypted fileurl in there source code,
          DASH, HDS, HLS and HTTP

    Unsupported
        - websites with RTMP
          it will show the url in the debug log, but won't try to start it.
        - streams that require
            - an authentication
            - an API
        - streams that are hidden behind javascript or other encryption
    '''

    _url_re = re.compile(r'''(resolve://)?(?P<url>.+)''')
    # Regex for: .mp3 and mp4 files
    _httpstream_bitrate_re = re.compile(r'''_(?P<bitrate>\d{1,4})\.mp(?:3|4)''')
    # Regex for: streamBasePath for .f4m urls
    _stream_base_re = re.compile(
        r'''streamBasePath\s?(?::|=)\s?["'](?P<base>[^"']+)["']''',
        re.IGNORECASE)
    # Regex for: javascript redirection
    _window_location_re = re.compile(
        r'''<script[^<]+window\.location\.href\s?=\s?["'](?P<url>[^"']+)["'];[^<>]+''',
        re.DOTALL)
    _unescape_iframe_re = re.compile(
        r'''unescape\050["'](?P<data>%3C(?:iframe|%69%66%72%61%6d%65)%20[^"']+)["']''',
        re.IGNORECASE)
    # Regex for obviously ad paths
    _ads_path = re.compile(
        r'''(?:/(?:static|\d+))?/ads?/?(?:\w+)?(?:\d+x\d+)?(?:_\w+)?\.(?:html?|php)''')

    # START - _make_url_list
    # Not allowed at the end of the parsed url path
    blacklist_endswith = (
        '.gif',
        '.jpg',
        '.png',
        '.svg',
        '.vtt',
        '/chat.html',
        '/chat',
    )
    # Not allowed at the end of the parsed url netloc
    blacklist_netloc = (
        '127.0.0.1',
        'about:blank',
        'abv.bg',
        'adfox.ru',
        'googletagmanager.com',
        'javascript:false',
    )
    # END - _make_url_list

    arguments = PluginArguments(
        PluginArgument(
            'blacklist-netloc',
            metavar='NETLOC',
            type=comma_list,
            help='''
            Blacklist domains that should not be used,

            by using a comma-separated list:

              'example.com,localhost,google.com'

            Useful for websites with a lot of iframes.
            '''
        ),
        PluginArgument(
            'blacklist-path',
            metavar='PATH',
            type=comma_list,
            help='''
            Blacklist the path of a domain that should not be used,

            by using a comma-separated list:

              'example.com/mypath,localhost/example,google.com/folder'

            Useful for websites with different iframes of the same domain.
            '''
        ),
        PluginArgument(
            'whitelist-netloc',
            metavar='NETLOC',
            type=comma_list,
            help='''
            Whitelist domains that should only be searched for iframes,

            by using a comma-separated list:

              'example.com,localhost,google.com'

            Useful for websites with lots of iframes,
            where the main iframe always has the same hosting domain.
            '''
        ),
        PluginArgument(
            'whitelist-path',
            metavar='PATH',
            type=comma_list,
            help='''
            Whitelist the path of a domain that should only be searched for iframes,

            by using a comma-separated list:

              'example.com/mypath,localhost/example,google.com/folder'

            Useful for websites with different iframes of the same domain,
            where the main iframe always has the same path.
            '''
        ),
    )

    def __init__(self, url):
        super(Resolve, self).__init__(url)
        # Remove prefix
        self.url = self.url.replace('resolve://', '')
        # cache every used url, this will avoid a loop
        if hasattr(ResolveCache, 'cache_url_list'):
            ResolveCache.cache_url_list += [self.url]
            # set the last url as a referer
            self.referer = ResolveCache.cache_url_list[-2]
        else:
            ResolveCache.cache_url_list = [self.url]
            self.referer = self.url

        self._run = len(ResolveCache.cache_url_list)

        http.headers.update({'Referer': self.referer})
        if http.headers['User-Agent'].startswith('python-requests'):
            http.headers.update({'User-Agent': useragents.FIREFOX})

    @classmethod
    def priority(cls, url):
        '''
        Returns
        - NO priority if the URL is not prefixed
        - HIGH priority if the URL is prefixed
        :param url: the URL to find the plugin priority for
        :return: plugin priority for the given URL
        '''
        m = cls._url_re.match(url)
        if m:
            prefix, url = cls._url_re.match(url).groups()
            if prefix is not None:
                return HIGH_PRIORITY
        return NO_PRIORITY

    @classmethod
    def can_handle_url(cls, url):
        m = cls._url_re.match(url)
        if m:
            return m.group('url') is not None

    def compare_url_path(self, parsed_url, check_list):
        '''compare a parsed url, if it matches an item from a list

        Args:
           parsed_url: an url that was used with urlparse
           check_list: a list of urls that should get checked

        Returns:
            True
                if parsed_url in check_list
            False
                if parsed_url not in check_list
        '''
        status = False
        for netloc, path in check_list:
            if (parsed_url.netloc.endswith(netloc)
                    and parsed_url.path.startswith(path)):
                status = True
        return status

    def merge_path_list(self, static, user):
        '''merge the static list, with an user list

        Args:
           static (list): static list from this plugin
           user (list): list from an user command

        Returns:
            A new valid list
        '''
        for _path_url in user:
            if not _path_url.startswith(('http', '//')):
                _path_url = update_scheme('http://', _path_url)
            _parsed_path_url = urlparse(_path_url)
            if _parsed_path_url.netloc and _parsed_path_url.path:
                static += [(_parsed_path_url.netloc, _parsed_path_url.path)]
        return static

    def repair_url(self, url, base_url, stream_base):
        '''repair a broken url'''
        # remove \
        new_url = url.replace('\\', '')
        # repairs broken scheme
        if new_url.startswith('http&#58;//'):
            new_url = 'http:' + new_url[9:]
        elif new_url.startswith('https&#58;//'):
            new_url = 'https:' + new_url[10:]
        # creates a valid url from path only urls
        # and adds missing scheme for // urls
        if stream_base and new_url[1] is not '/':
            if new_url[0] is '/':
                new_url = new_url[1:]
            new_url = urljoin(stream_base, new_url)
        else:
            new_url = urljoin(base_url, new_url)
        return new_url

    def _make_url_list(self, old_list, base_url, url_type='', stream_base=''):
        '''creates a list of valid urls
           - removes unwanted urls

        Args:
            old_list: list of urls
            base_url: url that will get used for scheme and netloc repairs
            url_type: can be ... and is used for ...
                - iframe
                    --resolve-whitelist-netloc
                - playlist

            stream_base: basically same as base_url, but used for .f4m files.

        Returns:
            (list) A new valid list of urls.
        '''

        # sorted after the way streamlink will try to remove an url
        status_remove = [
            'SAME-URL',
            'SCHEME',
            'WL-netloc',
            'WL-path',
            'BL-static',
            'BL-netloc',
            'BL-path',
            'BL-ew',
            'ADS',
        ]

        new_list = []
        for url in old_list:
            new_url = self.repair_url(url, base_url, stream_base)
            # parse the url
            parse_new_url = urlparse(new_url)

            # START - removal of unwanted urls
            REMOVE = False
            count = 0

            # status_remove must be updated on changes
            for url_status in (
                    # Removes an already used iframe url
                    (new_url in ResolveCache.cache_url_list),
                    # Allow only an url with a valid scheme
                    (not parse_new_url.scheme.startswith(('http'))),
                    # Allow only whitelisted domains for iFrames
                    # --resolve-whitelist-netloc
                    (url_type == 'iframe'
                     and self.get_option('whitelist_netloc')
                     and parse_new_url.netloc.endswith(tuple(self.get_option('whitelist_netloc'))) is False),
                    # Allow only whitelisted paths from a domain for iFrames
                    # --resolve-whitelist-path
                    (url_type == 'iframe'
                     and ResolveCache.whitelist_path
                     and self.compare_url_path(parse_new_url, ResolveCache.whitelist_path) is False),
                    # Removes blacklisted domains from a static list
                    # self.blacklist_netloc
                    (parse_new_url.netloc.endswith(self.blacklist_netloc)),
                    # Removes blacklisted domains
                    # --resolve-blacklist-netloc
                    (self.get_option('blacklist_netloc')
                     and parse_new_url.netloc.endswith(tuple(self.get_option('blacklist_netloc')))),
                    # Removes blacklisted paths from a domain
                    # --resolve-blacklist-path
                    (self.compare_url_path(parse_new_url, ResolveCache.blacklist_path) is True),
                    # Removes unwanted endswith images and chatrooms
                    (parse_new_url.path.endswith(self.blacklist_endswith)),
                    # Removes obviously AD URL
                    (self._ads_path.match(parse_new_url.path)),
            ):

                count += 1
                if url_status:
                    REMOVE = True
                    break

            if REMOVE is True:
                log.debug('{0} - Removed: {1}'.format(status_remove[count - 1], new_url))
                continue
            # END - removal of unwanted urls

            # Add repaired url
            new_list += [new_url]
        # Remove duplicates
        log.debug('List length: {0} (with duplicates)'.format(len(new_list)))
        new_list = sorted(list(set(new_list)))
        return new_list

    def _iframe_unescape(self, res):
        '''Try to find iframes from unescape('%3Ciframe%20

        Args:
            res: Content from self._res_text

        Returns:
            (list) A list of iframe urls
              or
            False
                if no iframe was found
        '''
        unescape_iframe = self._unescape_iframe_re.findall(res)
        if unescape_iframe:
            unescape_text = []
            for data in unescape_iframe:
                unescape_text += [unquote(data)]
            unescape_text = ','.join(unescape_text)
            unescape_iframe = _iframe_re.findall(unescape_text)
            if unescape_iframe:
                log.debug('Found {0} unescape_iframe'.format(len(unescape_iframe)))
                return unescape_iframe
        log.debug('No unescape_iframe')
        return False

    def _window_location(self, res):
        '''Try to find a script with window.location.href

        Args:
            res: Content from self._res_text

        Returns:
            (str) url
              or
            False
                if no url was found.
        '''

        match = self._window_location_re.search(res)
        if match:
            temp_url = urljoin(self.url, match.group('url'))
            log.debug('Found window_location: {0}'.format(temp_url))
            return temp_url

        log.debug('No window_location')
        return False

    def _resolve_playlist(self, playlist_all):
        ''' create streams

        Args:
            playlist_all: List of stream urls

        Returns:
            all streams
        '''
        http.headers.update({'Referer': self.url})
        for url in playlist_all:
            parsed_url = urlparse(url)
            if parsed_url.path.endswith(('.m3u8')):
                try:
                    streams = HLSStream.parse_variant_playlist(self.session, url).items()
                    if not streams:
                        yield 'live', HLSStream(self.session, url)
                    for s in streams:
                        yield s
                except Exception as e:
                    log.error('Skipping hls_url - {0}'.format(str(e)))
            elif parsed_url.path.endswith(('.f4m')):
                try:
                    for s in HDSStream.parse_manifest(self.session, url).items():
                        yield s
                except Exception as e:
                    log.error('Skipping hds_url - {0}'.format(str(e)))
            elif parsed_url.path.endswith(('.mp3', '.mp4')):
                try:
                    name = 'live'
                    m = self._httpstream_bitrate_re.search(url)
                    if m:
                        name = '{0}k'.format(m.group('bitrate'))
                    yield name, HTTPStream(self.session, url)
                except Exception as e:
                    log.error('Skipping http_url - {0}'.format(str(e)))
            elif parsed_url.path.endswith(('.mpd')):
                try:
                    for s in DASHStream.parse_manifest(self.session,
                                                       url).items():
                        yield s
                except Exception as e:
                    log.error('Skipping mpd_url - {0}'.format(str(e)))

    def _res_text(self, url):
        '''Content of a website

        Args:
            url: URL with an embedded Video Player.

        Returns:
            Content of the response
        '''
        try:
            res = http.get(url, allow_redirects=True)
        except Exception as e:
            if 'Received response with content-encoding: gzip' in str(e):
                headers = {
                    'User-Agent': useragents.FIREFOX,
                    'Referer': self.referer,
                    'Accept-Encoding': 'deflate'
                }
                res = http.get(url, headers=headers, allow_redirects=True)
            elif '403 Client Error' in str(e):
                log.error('Website Access Denied/Forbidden, you might be geo-blocked or other params are missing.')
                raise NoStreamsError(self.url)
            elif '404 Client Error' in str(e):
                log.error('Website was not found, the link is broken or dead.')
                raise NoStreamsError(self.url)
            else:
                raise e

        if res.history:
            for resp in res.history:
                log.debug('Redirect: {0} - {1}'.format(resp.status_code, resp.url))
            log.debug('URL: {0}'.format(res.url))
        return res.text

    def _set_defaults(self):
        ''' generates default options
            and caches them into ResolveCache class
        '''
        # START - List for not allowed URL Paths
        # --resolve-blacklist-path
        if not hasattr(ResolveCache, 'blacklist_path'):

            # static list
            blacklist_path = [
                ('expressen.se', '/_livetvpreview/'),
                ('facebook.com', '/connect'),
                ('facebook.com', '/plugins'),
                ('haber7.com', '/radyohome/station-widget/'),
                ('static.tvr.by', '/upload/video/atn/promo'),
                ('twitter.com', '/widgets'),
                ('vesti.ru', '/native_widget.html'),
            ]

            # merge user and static list
            blacklist_path_user = self.get_option('blacklist_path')
            if blacklist_path_user is not None:
                blacklist_path = self.merge_path_list(
                    blacklist_path, blacklist_path_user)

            ResolveCache.blacklist_path = blacklist_path
        # END

        # START - List of only allowed URL Paths for Iframes
        # --resolve-whitelist-path
        if not hasattr(ResolveCache, 'whitelist_path'):
            whitelist_path = []
            whitelist_path_user = self.get_option('whitelist_path')
            if whitelist_path_user is not None:
                whitelist_path = self.merge_path_list(
                    [], whitelist_path_user)
            ResolveCache.whitelist_path = whitelist_path
        # END

    def _get_streams(self):
        '''Try to find streams on every website.

        Returns:
            Playable video
                or
            New session url
        Raises:
            NoPluginError: if no video was found.
        '''
        self._set_defaults()
        if self._run <= 1:
            log.info('This is a custom plugin. '
                     'For support visit https://github.com/back-to/plugins')

        new_session_url = False

        self.url = update_scheme('http://', self.url)
        log.info('--- {0} ---'.format(self._run))
        log.info('--- URL={0}'.format(self.url))

        # GET website content
        o_res = self._res_text(self.url)

        # Playlist URL
        playlist_all = _playlist_re.findall(o_res)
        if playlist_all:
            log.debug('Found Playlists: {0}'.format(len(playlist_all)))
            # m_base is used for .f4m files that doesn't have a base_url
            m_base = self._stream_base_re.search(o_res)
            if m_base:
                stream_base = m_base.group('base')
            else:
                stream_base = ''

            playlist_list = self._make_url_list(playlist_all,
                                                self.url,
                                                url_type='playlist',
                                                stream_base=stream_base)
            if playlist_list:
                log.debug('Found Playlists: {0} (valid)'.format(len(playlist_list)))
                log.debug('Found URL: {0}'.format(', '.join(playlist_list)))
                return self._resolve_playlist(playlist_list)
        else:
            log.debug('No Playlists')

        # iFrame URL
        iframe_list = []
        for _iframe_list in (_iframe_re.findall(o_res),
                             self._iframe_unescape(o_res)):
            if not _iframe_list:
                continue
            iframe_list += _iframe_list

        if iframe_list:
            log.debug('Found Iframes: {0}'.format(len(iframe_list)))
            # repair and filter iframe url list
            new_iframe_list = self._make_url_list(iframe_list,
                                                  self.url,
                                                  url_type='iframe')
            if new_iframe_list:
                log.debug('Found Iframes: {0} (valid)'.format(len(new_iframe_list)))
                log.info('URL Iframes: {0}'.format(', '.join(new_iframe_list)))
                new_session_url = new_iframe_list[0]
        else:
            log.debug('No Iframes')

        if not new_session_url:
            # search for window.location.href
            new_session_url = self._window_location(o_res)

        if new_session_url:
            # the Dailymotion Plugin does not work with this Referer
            if 'dailymotion.com' in new_session_url:
                del http.headers['Referer']

            return self.session.streams(new_session_url)

        raise NoPluginError


__plugin__ = Resolve
