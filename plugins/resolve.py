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
        (?:[^"'<>\s\\{}]+)?)
    (?:["']|(?<!;)\s|>|\\&quot;)
    ''', re.DOTALL | re.VERBOSE)

# Regex for rtmp
_rtmp_re = re.compile(r'''["'](?P<url>rtmp(?:e|s|t|te)?://[^"']+)["']''')

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
          HDS, HLS and HTTP

    Unsupported
        - websites with DASH or RTMP
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
    _stream_base_re = re.compile(r'''streamBasePath\s?(?::|=)\s?["'](?P<base>[^"']+)["']''', re.IGNORECASE)
    # Regex for: javascript redirection
    _window_location_re = re.compile(r'''<script[^<]+window\.location\.href\s?=\s?["'](?P<url>[^"']+)["'];[^<>]+''', re.DOTALL)
    _unescape_iframe_re = re.compile(r'''unescape\050["'](?P<data>%3C(?:iframe|%69%66%72%61%6d%65)%20[^"']+)["']''', re.IGNORECASE)
    # Regex for obviously ad paths
    _ads_path = re.compile(r'''(?:/(?:static|\d+))?/ads?/?(?:\w+)?(?:\d+x\d+)?(?:_\w+)?\.(?:html?|php)''')

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
    # Not allowed at the end of the parsed url netloc and the start of the path
    blacklist_path = [
        ('expressen.se', '/_livetvpreview/'),
        ('facebook.com', '/connect'),
        ('facebook.com', '/plugins'),
        ('haber7.com', '/radyohome/station-widget/'),
        ('static.tvr.by', '/upload/video/atn/promo'),
        ('twitter.com', '/widgets'),
        ('vesti.ru', '/native_widget.html'),
    ]
    # Only allowed as a valid file format in playlist urls
    whitelist_endswith = (
        '.f4m',
        '.hls',
        '.m3u',
        '.m3u8',
        '.mp3',
        '.mp4',
        '.mpd',
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

            Useful for websites with lots of iframes, where the main iframe always has the same hosting domain.
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

            Useful for websites with different iframes of the same domain, where the main iframe always has the same path.
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

        http.headers.update({'Referer': self.referer})

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
            if parsed_url.netloc.endswith(netloc) and parsed_url.path.startswith(path):
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
        # creates a valid url from path only urls and adds missing scheme for // urls
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
                    whitelist_endswith
            stream_base: basically same as base_url, but used for .f4m files.

        Returns:
            (list) A new valid list of urls.
        '''

        blacklist_netloc_user = self.get_option('blacklist_netloc')
        whitelist_netloc_user = self.get_option('whitelist_netloc')

        # repairs scheme of --resolve-blacklist-path and merges it into blacklist_path
        blacklist_path_user = self.get_option('blacklist_path')
        if blacklist_path_user is not None:
            self.blacklist_path = self.merge_path_list(self.blacklist_path, blacklist_path_user)

        # repairs scheme of --resolve-whitelist-path and merges it into whitelist_path
        whitelist_path_user = self.get_option('whitelist_path')
        if whitelist_path_user is not None:
            whitelist_path = self.merge_path_list([], whitelist_path_user)

        # sorted after the way streamlink will try to remove an url
        status_remove = [
            'SAME-URL',   # - Removes an already used iframe url
            'SCHEME',     # - Allow only an url with a valid scheme
            'WL-netloc',  # - Allow only whitelisted domains --resolve-whitelist-netloc
            'WL-path',    # - Allow only whitelisted paths from a domain --resolve-whitelist-path
            'BL-static',  # - Removes blacklisted domains
            'BL-netloc',  # - Removes blacklisted domains --resolve-blacklist-netloc
            'BL-path',    # - Removes blacklisted paths from a domain --resolve-blacklist-path
            'BL-ew',      # - Removes unwanted endswith images and chatrooms
            'WL-ew',      # - Allow only valid file formats for playlists
            'ADS',        # - Remove obviously ad urls
        ]

        new_list = []
        for url in old_list:
            new_url = self.repair_url(url, base_url, stream_base)
            # parse the url
            parse_new_url = urlparse(new_url)

            # START - removal of unwanted urls
            REMOVE = False
            count = 0

            for url_status in ((new_url in ResolveCache.cache_url_list),
                               (not parse_new_url.scheme.startswith(('http'))),
                               (url_type == 'iframe'
                                and whitelist_netloc_user is not None
                                and parse_new_url.netloc.endswith(tuple(whitelist_netloc_user)) is False),
                               (url_type == 'iframe'
                                and whitelist_path_user is not None
                                and self.compare_url_path(parse_new_url, whitelist_path) is False),
                               (parse_new_url.netloc.endswith(self.blacklist_netloc)),
                               (blacklist_netloc_user is not None
                                and parse_new_url.netloc.endswith(tuple(blacklist_netloc_user))),
                               (self.compare_url_path(parse_new_url, self.blacklist_path) is True),
                               (parse_new_url.path.endswith(self.blacklist_endswith)),
                               ((url_type == 'playlist'
                                 and not parse_new_url.path.endswith(self.whitelist_endswith))),
                               (self._ads_path.match(parse_new_url.path))):

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
                return unescape_iframe
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
            return match.group('url')
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
                    log.info('Found mpd: {0}'.format(url))
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

    def _get_streams(self):
        log.info('This is a custom plugin. '
                 'For support visit https://github.com/back-to/plugins')
        '''Try to find streams on every website.

        Returns:
            Playable video
                or
            New session url
        Raises:
            NoPluginError: if no video was found.
        '''
        new_session_url = False

        self.url = update_scheme('http://', self.url)
        log.debug('resolve.py - {0}'.format(self.url))

        # GET website content
        o_res = self._res_text(self.url)

        # rtmp search, will only print the url.
        m_rtmp = _rtmp_re.search(o_res)
        if m_rtmp:
            log.info('Found RTMP: {0}'.format(m_rtmp.group('url')))

        # Playlist URL
        playlist_all = _playlist_re.findall(o_res)
        if playlist_all:
            # m_base is used for .f4m files that doesn't have a base_url
            m_base = self._stream_base_re.search(o_res)
            if m_base:
                stream_base = m_base.group('base')
            else:
                stream_base = ''

            playlist_list = self._make_url_list(playlist_all, self.url, url_type='playlist', stream_base=stream_base)
            if playlist_list:
                log.debug('Found URL: {0}'.format(', '.join(playlist_list)))
                return self._resolve_playlist(playlist_list)

        # iFrame URL
        iframe_list = []
        for _iframe_list in (_iframe_re.findall(o_res),
                             self._iframe_unescape(o_res)):
            if not _iframe_list:
                continue
            iframe_list += _iframe_list

        if iframe_list:
            # repair and filter iframe url list
            new_iframe_list = self._make_url_list(iframe_list, self.url, url_type='iframe')
            if new_iframe_list:
                log.info('Found iframes: {0}'.format(', '.join(new_iframe_list)))
                new_session_url = new_iframe_list[0]

        if not new_session_url:
            # search for window.location.href
            new_session_url = self._window_location(o_res)

        if new_session_url:
            return self.session.streams(new_session_url)

        raise NoPluginError


__plugin__ = Resolve
