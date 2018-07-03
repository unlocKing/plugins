import logging
import re

from Crypto.Cipher import AES

from streamlink import StreamError
from streamlink.compat import urlparse
from streamlink.plugin import Plugin, PluginArgument, PluginArguments
from streamlink.plugin.api import http
from streamlink.plugin.api import useragents
from streamlink.plugin.plugin import parse_url_params
from streamlink.stream import HLSStream
from streamlink.stream.hls import HLSStreamWriter, HLSStreamReader, num_to_iv
from streamlink.utils import update_scheme

log = logging.getLogger(__name__)


class KeyUriHLSStreamWriter(HLSStreamWriter):
    def create_decryptor(self, key, sequence):

        if key.method != 'AES-128':
            raise StreamError('Unable to decrypt cipher {0}', key.method)

        if not key.uri:
            raise StreamError('Missing URI to decryption key')

        if self.key_uri != key.uri:
            log.debug('Diff Key-URI')
            new_key_uri = key.uri
            if HLSKeyUriPlugin.get_option('key_uri'):
                # Repair a broken key-uri
                log.debug('Old Key-URI: {0}'.format(new_key_uri))
                parsed_uri = urlparse(new_key_uri)
                new_key_uri = HLSKeyUriPlugin.get_option('key_uri')
                new_data_list = [
                    (r'\$\{scheme\}', '{0}://'.format(parsed_uri.scheme)),
                    (r'\$\{netloc\}', parsed_uri.netloc),
                    (r'\$\{path\}', parsed_uri.path),
                    (r'\$\{query\}', '?{0}'.format(parsed_uri.query)),
                ]
                for _at_re, _old_data in new_data_list:
                    new_key_uri = re.sub(_at_re, _old_data, new_key_uri)
                log.debug('New Key-URI: {0}'.format(new_key_uri))
            res = self.session.http.get(new_key_uri, exception=StreamError,
                                        retries=self.retries,
                                        **self.reader.request_params)
            self.key_data = res.content
            self.key_uri = key.uri

        iv = key.iv or num_to_iv(sequence)

        # Pad IV if needed
        iv = b'\x00' * (16 - len(iv)) + iv

        return AES.new(self.key_data, AES.MODE_CBC, iv)


class KeyUriHLSStreamReader(HLSStreamReader):
    __writer__ = KeyUriHLSStreamWriter


class KeyUriHLSStream(HLSStream):
    def open(self):
        reader = KeyUriHLSStreamReader(self)
        reader.open()

        return reader


class HLSKeyUriPlugin(Plugin):
    _url_re = re.compile(r'(hlskeyuri://)(.+(?:\.m3u8)?.*)')

    arguments = PluginArguments(
        PluginArgument(
            'key-uri',
            argument_name='hls-key-uri',
            required=True,
            metavar='KEY-URI',
            help='''
            Repair a broken Key-URI.

            You can reuse the none broken items:

              ${scheme} ${netloc} ${path} ${query}
              streamlink --hls-key-uri '${scheme}${netloc}${path}${query}'

            Replace the broken part, like:

              streamlink --hls-key-uri 'https://${netloc}${path}${query}'

            '''
        ),
    )

    @classmethod
    def can_handle_url(cls, url):
        return cls._url_re.match(url)

    def _get_streams(self):
        http.headers.update({'User-Agent': useragents.FIREFOX})
        log.debug('Version 2018-07-01')
        log.info('This is a custom plugin. '
                 'For support visit https://github.com/back-to/plugins')

        url, params = parse_url_params(self.url)
        urlnoproto = self._url_re.match(url).group(2)
        urlnoproto = update_scheme('http://', urlnoproto)

        streams = self.session.streams(
            urlnoproto, stream_types=['hls'])

        if not streams:
            log.debug('No stream found for hls-key-uri,'
                      ' stream is not available.')
            return

        stream = streams['best']
        urlnoproto = stream.url

        log.debug('URL={0}; params={1}', urlnoproto, params)
        streams = KeyUriHLSStream.parse_variant_playlist(self.session, urlnoproto, **params)
        if not streams:
            return {'live': KeyUriHLSStream(self.session, urlnoproto, **params)}
        else:
            return streams


__plugin__ = HLSKeyUriPlugin
