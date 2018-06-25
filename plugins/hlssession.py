import argparse
import logging
import re

from time import time

from streamlink import StreamError
from streamlink.plugin import Plugin, PluginArgument, PluginArguments
from streamlink.plugin.api import http
from streamlink.plugin.api import useragents
from streamlink.plugin.plugin import parse_url_params
from streamlink.stream import HLSStream
from streamlink.stream.hls import HLSStreamWorker, HLSStreamReader
from streamlink.utils import update_scheme
from streamlink.utils.times import hours_minutes_seconds

log = logging.getLogger(__name__)


class TempData(object):
    pass


def num(type, min=None, max=None):
    def func(value):
        value = type(value)

        if min is not None and not (value > min):
            raise argparse.ArgumentTypeError(
                '{0} value must be more than {1} but is {2}'.format(
                    type.__name__, min, value
                )
            )

        if max is not None and not (value <= max):
            raise argparse.ArgumentTypeError(
                '{0} value must be at most {1} but is {2}'.format(
                    type.__name__, max, value
                )
            )

        return value

    func.__name__ = type.__name__

    return func


class HLSSessionHLSStreamWorker(HLSStreamWorker):
    def reload_session(self):
        '''Replaces the current stream with a new stream'''
        TempData.cached_data.update({'timestamp': int(time())})

        cache_stream_name = TempData.cached_data.get('stream_name')
        cache_stream_url = TempData.cached_data.get('url')

        if not (cache_stream_name and cache_stream_url):
            log.warning('Missing cached data for hlssession,'
                        'your Streamlink Application is not setup correctly.')
            return

        log.debug('Current stream: {0} - {1}'.format(
            cache_stream_name, cache_stream_url))
        log.debug('Reloading session playlist')
        streams = self.session.streams(
            cache_stream_url, stream_types=['hls'])

        if not streams:
            log.debug('No stream found for hls-session-reload,'
                      ' stream is not available.')
            return

        # overwrite the stream
        self.stream = streams[cache_stream_name]
        log.debug('New stream_url: {0}'.format(self.stream.url))

    def reload_session_invalid_sequence_check(self):
        # only allows reload_session(),
        # if the last reload is older than 10 seconds
        if TempData.session_reload_segment and (int(time() - TempData.cached_data['timestamp']) >= 10):
            # if a reload_playlist() fails because of invalid sequences,
            # it will allow the usage of reload_session() on the next
            # failed try of reload_playlist()
            TempData.session_reload_segment_status = True

    def process_sequences(self, playlist, sequences):
        first_sequence, last_sequence = sequences[0], sequences[-1]

        if first_sequence.segment.key and first_sequence.segment.key.method != 'NONE':
            log.debug('Segments in this playlist are encrypted')

        self.playlist_changed = ([s.num for s in self.playlist_sequences]
                                 != [s.num for s in sequences])
        self.playlist_reload_time = (playlist.target_duration
                                     or last_sequence.segment.duration)
        self.playlist_sequences = sequences

        if not self.playlist_changed:
            self.playlist_reload_time = max(self.playlist_reload_time / 2, 1)
            # uses reload_session() on the 2nd reload_playlist()
            # if the playlist did not change
            if TempData.session_reload_segment and TempData.session_reload_segment_status is True:
                log.debug('Expected reload_session() - invalid sequences')
                self.reload_session()
                TempData.session_reload_segment_status = False

        if playlist.is_endlist:
            self.playlist_end = last_sequence.num

        if self.playlist_sequence < 0:
            if self.playlist_end is None and not self.hls_live_restart:
                edge_index = -(min(len(sequences), max(int(self.live_edge), 1)))
                edge_sequence = sequences[edge_index]
                self.playlist_sequence = edge_sequence.num
            else:
                self.playlist_sequence = first_sequence.num

    def valid_sequence(self, sequence):
        if sequence.num >= self.playlist_sequence:
            return True
        elif TempData.sequence_ignore_number and sequence.num <= (self.playlist_sequence - TempData.sequence_ignore_number):
            log.warning('Added invalid segment number.')
            self.reload_session_invalid_sequence_check()
            return True
        else:
            self.reload_session_invalid_sequence_check()
            return False

    def duration_to_sequence(self, duration, sequences):
        d = 0
        default = -1

        sequences_order = sequences if duration >= 0 else reversed(sequences)

        for sequence in sequences_order:
            if d >= abs(duration):
                return sequence.num
            d += sequence.segment.duration
            default = sequence.num

        # could not skip far enough, so return the default
        return default

    def iter_segments(self):
        total_duration = 0
        while not self.closed:
            if TempData.session_reload_time and (
                    (TempData.cached_data['timestamp']
                     + TempData.session_reload_time) < int(time())):
                log.debug('Expected reload_session() - time')
                self.reload_session()
            for sequence in filter(self.valid_sequence, self.playlist_sequences):
                log.debug('Adding segment {0} to queue', sequence.num)
                yield sequence
                total_duration += sequence.segment.duration
                if self.duration_limit and total_duration >= self.duration_limit:
                    log.info('Stopping stream early after {0}'.format(self.duration_limit))
                    return

                # End of stream
                stream_end = self.playlist_end and sequence.num >= self.playlist_end
                if self.closed or stream_end:
                    return

                self.playlist_sequence = sequence.num + 1

            if self.wait(self.playlist_reload_time):
                try:
                    self.reload_playlist()
                except StreamError as err:
                    log.warning('Failed to reload playlist: {0}', err)
                    if (TempData.session_reload_time or TempData.session_reload_segment):
                        log.warning('Unexpected reload_session() - StreamError')
                        self.reload_session()


class HLSSessionHLSStreamReader(HLSStreamReader):
    __worker__ = HLSSessionHLSStreamWorker


class HLSSessionHLSStream(HLSStream):
    def open(self):
        reader = HLSSessionHLSStreamReader(self)
        reader.open()

        return reader


class HLSSessionPlugin(Plugin):
    _url_re = re.compile(r'(hlssession://)(.+(?:\.m3u8)?.*)')

    arguments = PluginArguments(
        PluginArgument(
            'ignore_number',
            # dest='hls-segment-ignore-number',
            type=num(int, min=5),
            metavar='SEGMENTS',
            help='''
            Ignore invalid segment numbers,
            this option is the max. difference between the valid and invalid number.

            If the valid segment is 100 and this option is set to 20,

            only a segment of 1-80 will be allowed and added,
            everything between 81-99 will be invalid and not added.

            Default is Disabled.
            '''
        ),
        PluginArgument(
            'segment',
            # dest='hls-session-reload-segment',
            action='store_true',
            help='''
            Reloads a Streamlink session, if the playlist reload fails twice.

            Default is False.

            Note: This command is meant as a fallback for --hlssession-time
            if the time is set incorrectly, it might not work for every stream.
            '''
        ),
        PluginArgument(
            'time',
            # dest='hls-session-reload-time',
            type=hours_minutes_seconds,
            metavar='HH:MM:SS',
            default=None,
            help='''
            Reloads a Streamlink session after the given time.

            Useful for playlists that expire after an amount of time.

            Default is Disabled.

            Note: --hlssession-ignore-number can be used for new playlists
            that contain different segment numbers
            '''
        ),
    )

    @classmethod
    def can_handle_url(cls, url):
        return cls._url_re.match(url)

    def _get_streams(self):
        http.headers.update({'User-Agent': useragents.FIREFOX})
        log.info('This is a custom plugin. '
                 'For support visit https://github.com/back-to/plugins')

        url, params = parse_url_params(self.url)
        urlnoproto = self._url_re.match(url).group(2)
        urlnoproto = update_scheme('http://', urlnoproto)

        if not hasattr(TempData, 'sequence_ignore_number'):
            TempData.sequence_ignore_number = (
                HLSSessionPlugin.get_option('ignore_number')
                or 0)

        if not hasattr(TempData, 'session_reload_segment'):
            TempData.session_reload_segment = (
                HLSSessionPlugin.get_option('segment')
                or False)
        if not hasattr(TempData, 'session_reload_segment_status'):
            TempData.session_reload_segment_status = False

        if not hasattr(TempData, 'session_reload_time'):
            TempData.session_reload_time = int(
                HLSSessionPlugin.get_option('time')
                or 0)

        if not hasattr(TempData, 'cached_data'):
            TempData.cached_data = {}
            # set a timestamp, if it was not set previously
            if not TempData.cached_data.get('timestamp'):
                TempData.cached_data.update({'timestamp': int(time())})

            TempData.cached_data.update({'stream_name': 'best'})
            TempData.cached_data.update({'url': urlnoproto})

        streams = self.session.streams(
            urlnoproto, stream_types=['hls'])

        if not streams:
            log.debug('No stream found for hls-session-reload,'
                      ' stream is not available.')
            return

        stream = streams['best']
        urlnoproto = stream.url

        self.logger.debug('URL={0}; params={1}', urlnoproto, params)
        streams = HLSSessionHLSStream.parse_variant_playlist(self.session, urlnoproto, **params)
        if not streams:
            return {'live': HLSSessionHLSStream(self.session, urlnoproto, **params)}
        else:
            return streams


__plugin__ = HLSSessionPlugin
