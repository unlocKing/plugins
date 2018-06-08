# back-to/plugins

- Issue Tracker: https://github.com/back-to/plugins/issues
- Github: https://github.com/back-to/plugins

# Guide

- https://liveproxy.github.io/plugins.html

### Linux Guide

clone it and make a symbolic link

```sh
git clone https://github.com/back-to/plugins.git
cd plugins
ln -s "$(pwd)/plugins/" "$HOME/.config/streamlink/"
```

# Plugin Matrix

...

# Special Plugin Matrix

## hlskeyuri.py

Repair a broken Key-URI.

You can reuse the none broken items:

    ${scheme} ${netloc} ${path} ${query}
    streamlink --hls-key-uri '${scheme}${netloc}${path}${query}'

Replace the broken part, like:

    streamlink --hls-key-uri 'https://${netloc}${path}${query}'

## hlssession.py

Allows a stream session reload for **hls urls that expire**,
use the prefix `hlssession://` for any url that can resolve a HLS stream.

### commands and LiveProxy examples:

> `--hlssession-time HH:MM:SS`

New session after a given time, also reloads on a StreamError

http://127.0.0.1:53422/play/?url=hlssession%3A%2F%2F--URL--&hlssession-time=300

> `--hlssession-segment`

New session if a normal playlist fails twice, also reloads on a StreamError

http://127.0.0.1:53422/play/?url=hlssession%3A%2F%2F--URL--&hlssession-segment=True

> `--hlssession-ignore-number SEGMENTS`

Allow invalid segment numbers

http://127.0.0.1:53422/play/?url=hlssession%3A%2F%2F--URL--&hlssession-ignore-number=20

## resolve.py

Plugin that will try to find a valid streamurl on every website

**Supported**

  - embedded url of an already existing plugin
  - website with an unencrypted fileurl in there source code,
    DASH, HDS, HLS and HTTP

**Unsupported**

  - websites with RTMP
    it will show the url in the debug log, but won't try to start it.
  - streams that require
      - an authentication
      - an API
  - streams that are hidden behind javascript or other encryption

> --resolve-blacklist-netloc NETLOC

```
Blacklist domains that should not be used,

by using a comma-separated list:

  'example.com,localhost,google.com'

Useful for websites with a lot of iframes.
```

> --resolve-blacklist-path PATH

```
Blacklist the path of a domain that should not be used,

by using a comma-separated list:

  'example.com/mypath,localhost/example,google.com/folder'

Useful for websites with different iframes of the same domain.
```

> --resolve-whitelist-netloc',

```
Whitelist domains that should only be searched for iframes,

by using a comma-separated list:

  'example.com,localhost,google.com'

Useful for websites with lots of iframes, where the main iframe always has the same hosting domain.
```


> --resolve-whitelist-path

```
Whitelist the path of a domain that should only be searched for iframes,

by using a comma-separated list:

  'example.com/mypath,localhost/example,google.com/folder'

Useful for websites with different iframes of the same domain, where the main iframe always has the same path.
```
