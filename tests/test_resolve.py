import requests_mock
import six
import unittest

from streamlink import Streamlink
from streamlink.compat import urlparse
from streamlink.logger import Logger
from streamlink.plugin import api
from streamlink.plugin.plugin import HIGH_PRIORITY
from streamlink.plugin.plugin import NO_PRIORITY

from plugins.resolve import _iframe_re
from plugins.resolve import _playlist_re
from plugins.resolve import _rtmp_re
from plugins.resolve import Resolve

try:
    from unittest.mock import patch
except ImportError:
    # python 2.7
    from mock import patch

text_hls = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-MEDIA-SEQUENCE:3080235
#EXT-X-TARGETDURATION:2
#EXTINF:2.000,
3080235.ts
"""

text_master_hls = """#EXTM3U
#EXT-X-VERSION:3
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=1152000
index.m3u8
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=640000
index.m3u8
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=320000
index.m3u8
"""

text_f4m = """<?xml version="1.0" encoding="UTF-8"?>
<manifest xmlns="http://ns.adobe.com/f4m/1.0">
  <id>/files/smil/f4m/1.smil_0</id>
  <streamType>recorded</streamType>
  <duration>2308.160</duration>
  <streamBaseTime>0.000</streamBaseTime>
  <bootstrapInfo profile="named" id="bootstrap_123">AAAAi2Fic3QAAAAAAAAAAQAAAAPoAAAAAAAjOEAAAAAAAAAAAAAAAAAAAQAAABlhc3J0AAAAAAAAAAABAAAAAQAAAYABAAAARmFmcnQAAAAAAAAD6AAAAAADAAAAAQAAAAAAAAAAAAAXcAAAAYAAAAAAACMQkAAAJ7AAAAAAAAAAAAAAAAAAAAAAAA==</bootstrapInfo>
  <media bitrate="3283" url="123" bootstrapInfoId="bootstrap_123">
    <metadata>AgAKb25NZXRhRGF0YQgAAAAMAAhkdXJhdGlvbgBAoghR64UeuAAFd2lkdGgAQJQAAAAAAAAABmhlaWdodABAhoAAAAAAAAANdmlkZW9kYXRhcmF0ZQBAqOZxeomxVgAJZnJhbWVyYXRlAEA5AAAAAAAAAAx2aWRlb2NvZGVjaWQAQBwAAAAAAAAADWF1ZGlvZGF0YXJhdGUAQFgABXOU314AD2F1ZGlvc2FtcGxlcmF0ZQBA5YiAAAAAAAAPYXVkaW9zYW1wbGVzaXplAEAwAAAAAAAAAAZzdGVyZW8BAQAMYXVkaW9jb2RlY2lkAEAkAAAAAAAAAAhmaWxlc2l6ZQBBzDsi4YAAAAAACQ==</metadata>
  </media>
</manifest>
"""

text_with_playlist = """
<html>source: "%s"
<player src="http://mocked/playlist/manifest.mpd">
</html>
"""

data_stream = [
    # hlsstream
    {
        "test_name": "hls_stream",
        "stream_type": "hls",
        "website_text": """
        <iframe src="http://mocked/default/iframe" width="650">iframe</iframe>
        """,
    },
    # hlsvariant stream
    {
        "test_name": "hlsvariant_stream",
        "stream_type": "hlsvariant",
        "website_text": """
        <iframe src="http://mocked/default/iframe" width="650">iframe</iframe>
        """,
    },
    # mp3 stream
    {
        "test_name": "mp3_stream",
        "stream_type": "mp3",
        "website_text": """
        <iframe src="http://mocked/default/iframe" width="650">iframe</iframe>
        """,
    },
    # mp4 stream
    {
        "test_name": "mp4_stream",
        "stream_type": "mp4",
        "website_text": """
        <iframe src="http://mocked/default/iframe" width="650">iframe</iframe>
        """,
    },
    # hds
    {
        "test_name": "hds_stream",
        "stream_type": "hds",
        "website_text": """
        <iframe src="http://mocked/default/iframe" width="650">iframe</iframe>
        """,
    },
    # remove iframes
    {
        "test_name": "iframe_script",
        "stream_type": "hlsvariant",
        "website_text": """
        <iframe src="about:blank" width="650">iframe</iframe>
        <iframe src="javascript:false" width="650">iframe</iframe>
        <iframe src="http://mocked/default/iframe" width="650">iframe</iframe>
        <iframe src="http://about:blank" width="650">iframe</iframe>
        <iframe src="https://127.0.0.1" width="650">iframe</iframe>
        <iframe src="https://javascript:false"></iframe>,
        """,
    },
    # remove _ads_path
    {
        "test_name": "iframe_ads",
        "stream_type": "hlsvariant",
        "website_text": """
            <iframe src="https://example.com/1/ads.htm">iframe</iframe>
            <iframe src="https://example.com/ad.php">iframe</iframe>
            <iframe src="https://example.com/ad20.php">iframe</iframe>
            <iframe src="https://example.com/ad5.php"></iframe>,
            <iframe src="https://example.com/ads.htm"></iframe>,
            <iframe src="https://example.com/ads.html"></iframe>,
            <iframe src="https://example.com/ads/ads300x250.php"></iframe>,
            <iframe src="https://example.com/ads468x60.htm"></iframe>,
            <iframe src="https://example.com/ads468x60.html"></iframe>,
            <iframe src="https://example.com/static/ads.htm"></iframe>,
            <iframe src="https://example.com/static/ads.html"></iframe>,
            <iframe src="http://mocked/default/iframe">iframe</iframe>
            <iframe src="https://example.com/static/ads/300x250_1217n.htm"></iframe>,
            <iframe src="https://example.com/static/ads/300x250_1217n.html"></iframe>
            <iframe src="https://example.com/static/ads/468x60.htm"></iframe>,
            <iframe src="https://example.com/static/ads/468x60.html"></iframe>,
            <iframe src="https://example.com/static/ads468x60.htm"></iframe>,
            <iframe src="https://example.com/static/ads468x60.html"></iframe>,
        """,
    },
    # remove blacklist_endswith
    {
        "test_name": "iframe_endswith",
        "stream_type": "hls",
        "website_text": """
            <iframe src="https://example.com/test.gif"></iframe>,
            <iframe src="https://example.com/test.jpg"></iframe>,
            <iframe src="https://example.com/test.png"></iframe>,
            <iframe src="https://example.com/test.svg"></iframe>,
            <iframe src="https://example.com/test.vtt"></iframe>,
            <iframe src="https://example.com/test/chat.html"></iframe>,
            <iframe src="https://example.com/test/chat"></iframe>,
            <iframe src="http://mocked/default/iframe" width="650">iframe</iframe>
        """,
    },
    # remove blacklist_netloc and blacklist_path
    {
        "test_name": "iframe_blacklisted",
        "stream_type": "hls",
        "website_text": """
            <iframe src="http://expressen.se/_livetvpreview/123.html"></iframe>,
            <iframe src="https://adfox.ru"></iframe>,
            <iframe src="https://facebook.com/plugins123"></iframe>,
            <iframe src="https://googletagmanager.com"></iframe>,
            <iframe src="https://vesti.ru/native_widget.html"></iframe>,
            <iframe src="http://mocked/default/iframe" width="650">iframe</iframe>
        """,
    },
    # find unescape iframe and print rtmp
    {
        "test_name": "iframe_unescape",
        "stream_type": "hls",
        "website_text": """
            <video src="rtmpte://local:1935">
            <div id="player">
                <script language='javascript'> document.write(unescape('%3Ciframe%20width%3D%22730%22%20height%3D%22440%22%20src%3D%22http%3A%2F%2Fmocked%2Fdefault%2Fiframe%22%20frameborder%3D%220%22%20gesture%3D%22media%22%20allow%3D%22encrypted-media%22%20allowfullscreen%3E%3C%2Fiframe%3E'));</script>
            </div>
        """,
    },
    # find window.location.href
    {
        "test_name": "iframe_unescape",
        "stream_type": "hls",
        "website_text": """
            <script type="text/javascript">
            window.location.href = 'http://mocked/default/iframe';
            </script>
        """,
    },
]

stream_data = {
    "hls": {
        "url": "http://mocked/playlist/index.m3u8",
        "name": "live",
        "text": text_hls
    },
    "hlsvariant": {
        "url": "http://mocked/playlist/master.m3u8",
        "name": "640k",
        "text": text_master_hls
    },
    "mp3": {
        "url": "http://mocked/music.mp3",
        "name": "live",
        "text": ""
    },
    "mp4": {
        "url": "http://mocked/video_2000.mp4",
        "name": "2000k",
        "text": ""
    },
    "hds": {
        "url": "http://mocked/playlist/manifest.f4m",
        "name": "3283k",
        "text": text_f4m
    },
}


class PluginResolveTestMeta(type):
    def __new__(mcs, name, bases, dict):

        def gen_test(_website_text, _stream_data):

            @patch("plugins.resolve.http")
            def test(self, mock_http):
                self.session = Streamlink()
                self.session.load_plugins('plugins')

                mock_http.get = api.HTTPSession().get
                mock_http.json = api.HTTPSession().json

                Resolve.bind(self.session, "test.resolve")

                default_iframe = "http://mocked/default/iframe"
                file_url = _stream_data["url"]
                self_url = "http://mocked/live"

                with requests_mock.Mocker() as mock:
                    mock.get(default_iframe, text=text_with_playlist % file_url)
                    mock.get(file_url, text=_stream_data["text"])
                    mock.get(self_url, text=_website_text)

                    self.session.set_plugin_option("resolve", "whitelist_netloc", ["mocked"])

                    plugin = Resolve(self_url)
                    streams = plugin._get_streams()
                    self.assertIn(_stream_data["name"], streams)

            return test

        for test_dict in data_stream:
            _website_text = test_dict["website_text"]
            _stream_data = stream_data[test_dict["stream_type"]]
            test_name = "test_%s" % test_dict["test_name"]

            dict[test_name] = gen_test(_website_text, _stream_data)

        return type.__new__(mcs, name, bases, dict)


@six.add_metaclass(PluginResolveTestMeta)
class TestPluginResolve_get_streams(unittest.TestCase):
    """
    run basic website requests for _get_streams
    this is a test for _make_url_list
    """


class TestPluginResolve(unittest.TestCase):

    @patch("plugins.resolve.http")
    def setUp(self, mock_http):
        self.res_plugin = Resolve("resolve://https://example.com")
        self.res_plugin.manager = Logger()
        self.res_plugin.logger = self.res_plugin.manager.new_module("test")
        self.session = Streamlink()
        self.session.load_plugins('src/streamlink/plugins')

    def test_priority(self):
        test_data = [
            ("resolve://https://example.com/index", HIGH_PRIORITY),
            ("https://example.com/index.html", NO_PRIORITY),
        ]
        for url, status in test_data:
            self.assertEqual(Resolve.priority(url), status)

    def test_can_handle_url(self):
        # it should match everything
        self.assertTrue(Resolve.can_handle_url("resolve://local.local"))
        self.assertTrue(Resolve.can_handle_url("local.local"))

    def test_compare_url_path(self):
        test_url = "https://www.facebook.com/plugins/123.html"
        parse_new_url = urlparse(test_url)
        self.assertTrue(self.res_plugin.compare_url_path(parse_new_url, self.res_plugin.blacklist_path))

        test_url = "https://example.com/123.html"
        parse_new_url = urlparse(test_url)
        self.assertFalse(self.res_plugin.compare_url_path(parse_new_url, self.res_plugin.blacklist_path))

    def test_merge_path_list(self):
        blacklist_path_user = [
            "example.com/plugins",
            "http://example.com/myplugins",
        ]

        blacklist_path = self.res_plugin.merge_path_list(self.res_plugin.blacklist_path, blacklist_path_user)

        blacklist_path_user_test = [
            ("example.com", "/plugins"),
            ("example.com", "/myplugins"),
        ]

        for test_url in blacklist_path_user_test:
            self.assertIn(test_url, blacklist_path)

    def test_repair_url(self):
        base_url = "https://example.com/test/index.html"

        test_list = [
            {
                "url": r"\/\/example.com/true1",
                "result": "https://example.com/true1",
            },
            {
                "url": "http&#58;//example.com/true2",
                "result": "http://example.com/true2",
            },
            {
                "url": "https&#58;//example.com/true3",
                "result": "https://example.com/true3",
            },
            {
                "url": "/true4_no_base/123.html",
                "result": "https://example.com/true4_no_base/123.html",
            },
            {
                "url": "//example.com/true5",
                "result": "https://example.com/true5",
            },
            {
                "url": "https://example.com/true6",
                "result": "https://example.com/true6",
            },
            {
                "url": "/true7_base/123.html",
                "stream_base": "http://new.example.com/",
                "result": "http://new.example.com/true7_base/123.html",
            },
        ]
        for test_dict in test_list:
            new_url = self.res_plugin.repair_url(test_dict["url"], base_url, test_dict.get("stream_base"))
            self.assertEqual(test_dict["result"], new_url)

    def test_iframe_unescape(self):
        # Tests for _unescape_iframe_re
        test_list = [
            {
                "data": """
                    <div id="player">
                        <script language='javascript'> document.write(unescape('%3Ciframe%20width%3D%22730%22%20height%3D%22440%22%20src%3D%22https%3A%2F%2Fwww.youtube.com%2Fembed%2Faqz-KE-bpKQ%3Fautoplay%3D1%22%20frameborder%3D%220%22%20gesture%3D%22media%22%20allow%3D%22encrypted-media%22%20allowfullscreen%3E%3C%2Fiframe%3E'));</script>
                    </div>
                        """,
                "result": ["https://www.youtube.com/embed/aqz-KE-bpKQ?autoplay=1"]
            },
            {
                "data": """
                        <div id="player">
                            <script language='javascript'> document.write(unescape('%3C%69%66%72%61%6d%65%20width%3D%22730%22%20height%3D%22440%22%20src%3D%22https%3A%2F%2Fwww.youtube.com%2Fembed%2Faqz-KE-bpKQ%3Fautoplay%3D1%22%20frameborder%3D%220%22%20gesture%3D%22media%22%20allow%3D%22encrypted-media%22%20allowfullscreen%3E%3C%2Fiframe%3E'));</script>
                        </div>
                        """,
                "result": ["https://www.youtube.com/embed/aqz-KE-bpKQ?autoplay=1"]
            },
        ]
        for test_dict in test_list:
            result_url_list = self.res_plugin._iframe_unescape(test_dict["data"])
            self.assertIsNotNone(result_url_list)
            self.assertListEqual(sorted(test_dict["result"]), sorted(result_url_list))

        # test_iframe_unescape - False
        res_test_list_false = [
            """<html><body><h1>ABC</h1><p>123</p></body></html>
            """,
        ]
        for test_res in res_test_list_false:
            m = self.res_plugin._iframe_unescape(test_res)
            self.assertFalse(m)

    def test_window_location(self):
        # Tests for _window_location and _window_location_re
        test_list = [
            {
                "data": """
                    <script type="text/javascript">
                    window.location.href = 'https://www.youtube.com/embed/aqz-KE-bpKQ';
                    </script>
                        """,
                "result": "https://www.youtube.com/embed/aqz-KE-bpKQ"
            },
            {
                "data": """
                    <script type="text/javascript">
                    window.location.href = "https://www.youtube.com/watch?v=aqz-KE-bpKQ";
                    </script>
                        """,
                "result": "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
            },
        ]
        for test_dict in test_list:
            result_url = self.res_plugin._window_location(test_dict["data"])
            self.assertIsNotNone(result_url)
            self.assertEqual(test_dict["result"], result_url)

        res_test_list_false = [
            """<html><body><h1>ABC</h1><p>123</p></body></html>""",
        ]

        for test_res in res_test_list_false:
            m = self.res_plugin._window_location(test_res)
            self.assertFalse(m)

    def test_regex_ads_path(self):
        regex_test_list = [
            "/ad.php",
            "/ad20.php",
            "/ad5.php",
            "/ads.htm",
            "/ads.html",
            "/ads/ads300x250.php",
            "/ads468x60.htm",
            "/ads468x60.html",
            "/static/ads.htm",
            "/static/ads.html",
            "/static/ads/300x250_1217n.htm",
            "/static/ads/300x250_1217n.html"
            "/static/ads/468x60.htm",
            "/static/ads/468x60.html",
            "/static/ads468x60.htm",
            "/static/ads468x60.html",
        ]
        for test_url in regex_test_list:
            m = self.res_plugin._ads_path.match(test_url)
            self.assertIsNotNone(m)

    def test_iframe_re(self):
        test_list = [
            # _iframe_re
            {
                "data": """
                        <iframe src="http://local2.local">    </iframe>
                        <iframe frameborder="0" src="http://local.local" width="650">iframe</iframe>""",
                "result": ["http://local.local", "http://local2.local"]
            },
            {
                "data": """<iframe src="http://local3.local" width="800px"></iframe>""",
                "result": ["http://local3.local"]
            },
            {
                "data": """<iframe height="600px" src="http://local4.local"></iframe>""",
                "result": ["http://local4.local"]
            },
            {
                "data": """<iframe height='600px' src='http://local5.local'></iframe>""",
                "result": ["http://local5.local"]
            },
            {
                "data": """</div>
                        <script type="text/javascript">_satellite.pageBottom();</script>
                        <iframe style="height:0px;width:0px;visibility:hidden" src="https://example.com/">
                            this frame prevents back forward cache
                            </iframe>
                        </body>""",
                "result": ["https://example.com/"]
            },
            {
                "data": """
                        <iframe src="https://example.com/123.php" width="720" height="500" allowtransparency="true"/>
                        """,
                "result": ["https://example.com/123.php"]
            },
            {
                "data": """
                        <script>
                            document.write('<ifr' + 'ame id="video" src="https://example.com/123.php" height="500" ></ifr' + 'ame>');
                        </script>
                        """,
                "result": ["https://example.com/123.php"]
            },
            {
                "data": """
                        <script>
                            document.write('<ifr'+'ame id="video" src="https://example.com/123.php" height="500" ></ifr'+'ame>');
                        </script>
                        """,
                "result": ["https://example.com/123.php"]
            },
            {
                "data": """
                        <iframe src="https://player.twitch.tv/?channel=monstercat" frameborder="0" allowfullscreen="true" scrolling="no" height="378" width="620"></iframe>
                        """,
                "result": ["https://player.twitch.tv/?channel=monstercat"]
            },
            {
                "data": """
                        <iframe width="560" height="315" src="https://www.youtube.com/embed/aqz-KE-bpKQ" frameborder="0" gesture="media" allow="encrypted-media" allowfullscreen></iframe>
                        """,
                "result": ["https://www.youtube.com/embed/aqz-KE-bpKQ"]
            },
            {
                "data": """
                        <iframe frameborder="0" width="480" height="270" src="//www.dailymotion.com/embed/video/xigbvx" allowfullscreen></iframe>
                        """,
                "result": ["//www.dailymotion.com/embed/video/xigbvx"]
            },
            {
                "data": """
                        <iframe src="https://player.vgtrk.com/iframe/live/id/2961/showZoomBtn/false/isPlay/true/" scrolling="No" border="0" frameborder="0" width="660" height="494" mozallowfullscreen webkitallowfullscreen allowfullscreen></iframe>
                        """,
                "result": ["https://player.vgtrk.com/iframe/live/id/2961/showZoomBtn/false/isPlay/true/"]
            },
            {
                "data": """
                        <iframe SRC="/web/playeriframe.jsp"  frameborder="0" WIDTH=500 HEIGHT=400></iframe>
                        """,
                "result": ["/web/playeriframe.jsp"]
            },
            {
                "data": """
                        <iframe width="470" height="270" src="http&#58;//example.example/live/ABC123ABC" frameborder="0"></iframe>
                        """,
                "result": ["http&#58;//example.example/live/ABC123ABC"]
            },
            {
                "data": """
                    <iframe     id="random"
                        name="iframe"
                        src="https://example.com/dotall/iframe"
                        width="100%"
                        height="500"
                        scrolling="auto"
                        frameborder="1"
                        class="wrapper">
                        </iframe>
                    </div></div></div>
                    """,
                "result": ["https://example.com/dotall/iframe"]
            },
            {
                "data": """
                    <iframe src="https://example.com/123.php" width="720" height="500" allowtransparency="true"/>
                    """,
                "result": ["https://example.com/123.php"]
            },
        ]
        for test_dict in test_list:
            result_url_list = _iframe_re.findall(test_dict["data"])
            self.assertIsNotNone(result_url_list)
            self.assertListEqual(sorted(test_dict["result"]), sorted(result_url_list))

    def test_iframe_re_false(self):
        regex_test_list = [
            """<iframe id="iframe" title="" frameborder="0" width="0" height="0" src=""></iframe>""",
            """<iframe name="g_iFrame1" width="70" src="logo"></iframe>""",
            """<iframe id="<%- uploadIframe %>" name="" style="display:none;"></iframe>
               <img src="<%- val.thumbUrl %>" alt=""/>""",
            """<iframe id="<%- uploadIframe %>" name="" style="display:none;"></iframe>
               <img src="<%-val.thumbUrl%>" alt=""/>""",
            """<iframe src="invalid url" />""",
        ]
        if not hasattr(self, 'assertNotRegex'):
            self.assertNotRegex = self.assertNotRegexpMatches

        for data in regex_test_list:
            self.assertNotRegex(data, _iframe_re)

    def test_playlist_re(self):
        regex_test_list = [
            {
                "data": """<player frameborder="0" src="http://local.m3u8">""",
                "result": "http://local.m3u8"
            },
            {
                "data": """<player frameborder="0" src="http://local.m3u8?local">""",
                "result": "http://local.m3u8?local"
            },
            {
                "data": """<player frameborder="0" src="//local.m3u8?local">""",
                "result": "//local.m3u8?local"
            },
            {
                "data": """
                        file: "http://example.com:8081/edge/playlist.m3u8?wmsAuthSign=c9JnZbWludXR4",
                        """,
                "result": "http://example.com:8081/edge/playlist.m3u8?wmsAuthSign=c9JnZbWludXR4"
            },
            {
                "data": r"""
                        "hlsLivestreamURL": "https:\/\/live-http.example.com\/live\/_definst_\/mp4:123\/playlist.m3u8",
                        "appnameLive": "live",
                        "streaming": "true",
                        "autostart": "true",
                        """,
                "result": r"https:\/\/live-http.example.com\/live\/_definst_\/mp4:123\/playlist.m3u8"
            },
            {
                "data": """
                        var player = new Clappr.Player({source: '/tv/tv.m3u8', mimeType: 'application/x-mpegURL'
                        """,
                "result": "/tv/tv.m3u8"
            },
            {
                "data": """
                        <player frameborder="0" src="local.m3u8?local">
                        """,
                "result": "local.m3u8?local"
            },
            {
                "data": """<player frameborder="0" src="http://local.f4m">""",
                "result": "http://local.f4m"
            },
            {
                "data": """<player frameborder="0" src="http://local.f4m?local">""",
                "result": "http://local.f4m?local"
            },
            {
                "data": """<player frameborder="0" src="//local.f4m?local">""",
                "result": "//local.f4m?local"
            },
            {
                "data": """<video src="http://local.mp3">""",
                "result": "http://local.mp3"
            },
            {
                "data": """<video src="http://local.mp4">""",
                "result": "http://local.mp4"
            },
            {
                "data": """<video src="//example.com/local.mp4">""",
                "result": "//example.com/local.mp4"
            },
            {
                "data": """
                        <video id='player_el' src='//example.com/video.mp4' width='100%' height='100%'
                        """,
                "result": "//example.com/video.mp4"
            },
            {
                "data": """
                        document.write( "<video src=http://999.999.999.999/live/playlist.m3u8?at=123 autoplay png> </video>");
                        """,
                "result": "http://999.999.999.999/live/playlist.m3u8?at=123"
            },
            {
                "data": """
                        document.write( "<video src=http://999.999.999.999/live/playlist.m3u8?at=123> </video>");
                        """,
                "result": "http://999.999.999.999/live/playlist.m3u8?at=123"
            },
            {
                "data": r"""
                        \&quot;hlsMasterPlaylistUrl\&quot;:\&quot;https://example.com/hls/video.m3u8?p\&quot;,
                        """,
                "result": "https://example.com/hls/video.m3u8?p"
            },
        ]
        for test_dict in regex_test_list:
            m = _playlist_re.search(test_dict["data"])
            self.assertIsNotNone(m)
            self.assertEqual(test_dict["result"], m.group("url"))

    def test_playlist_re_false(self):
        regex_test_list = [
            """<player frameborder="0" src="local.apk?local">""",
            """<player frameborder="0" src="http://local.mpk">""",
            """meta title="broken_title_url.mp4">""",
            """video">broken_title_url22.mp4</span></div><div style="float""",
            """video">broken_title_url22.mp4"float""",
            """if(options.livestream==true){
                 PlayerSetup.source.hls=options.m3u8;
               }
            """,
            """getCurrentVideoSrc: function(){
                 return $("#player").data("player").mp4;
               },
            """,
            """
                data-u="{upload_url=https://example.com/mobile.mp4,poster=https://example.com/mobile.jpg,id=123,flow=full}"
            """,
        ]
        if not hasattr(self, 'assertNotRegex'):
            self.assertNotRegex = self.assertNotRegexpMatches

        for data in regex_test_list:
            self.assertNotRegex(data, _playlist_re)

    def test_rtmp_re(self):
        regex_test_list = [
            {
                "data": """<player frameborder="0" src="rtmp://local">""",
                "result": "rtmp://local"
            },
            {
                "data": """<player frameborder="0" src="rtmpe://local?local">""",
                "result": "rtmpe://local?local"
            },
            {
                "data": """<player frameborder="0" src="rtmps://local?local">""",
                "result": "rtmps://local?local"
            },
            {
                "data": """<video src="rtmpte://local:1935">""",
                "result": "rtmpte://local:1935"
            },

        ]
        for test_dict in regex_test_list:
            m = _rtmp_re.search(test_dict["data"])
            self.assertIsNotNone(m)
            self.assertEqual(test_dict["result"], m.group("url"))
