from typing import Tuple, Optional
import asyncio
import random
import mimetypes
import html
import re
import string
import aiohttp
import urllib
import logging

# fmt: off
specials = {
    'mitvcanal': 56, 'animeultimacom': 34, 'cricket365live': 21,
    'pokemonepisodeorg': 22, 'animelinkz': 20, 'sport24lt': 56,
    'narutowire': 10, 'watchanimeonn': 22, 'cricvid-hitcric-': 51,
    'narutochatt': 70, 'leeplarp': 27, 'stream2watch3': 56, 'ttvsports': 56,
    'ver-anime': 8, 'vipstand': 21, 'eafangames': 56, 'soccerjumbo': 21,
    'myfoxdfw': 67, 'kiiiikiii': 21, 'de-livechat': 5, 'rgsmotrisport': 51,
    'dbzepisodeorg': 10, 'watch-dragonball': 8, 'peliculas-flv': 69,
    'tvanimefreak': 54, 'tvtvanimefreak': 54
}

# order matters
tsweights = [
    [5, 75], [6, 75], [7, 75], [8, 75], [16, 75],
    [17, 75], [18, 75], [9, 95], [11, 95], [12, 95],
    [13, 95], [14, 95], [15, 95], [19, 110], [23, 110],
    [24, 110], [25, 110], [26, 110], [28, 104], [29, 104],
    [30, 104], [31, 104], [32, 104], [33, 104], [35, 101],
    [36, 101], [37, 101], [38, 101], [39, 101], [40, 101],
    [41, 101], [42, 101], [43, 101], [44, 101], [45, 101],
    [46, 101], [47, 101], [48, 101], [49, 101], [50, 101],
    [52, 110], [53, 110], [55, 110], [57, 110],
    [58, 110], [59, 110], [60, 110], [61, 110],
    [62, 110], [63, 110], [64, 110], [65, 110],
    [66, 110], [68, 95], [71, 116], [72, 116],
    [73, 116], [74, 116], [75, 116], [76, 116],
    [77, 116], [78, 116], [79, 116], [80, 116],
    [81, 116], [82, 116], [83, 116], [84, 116]
]
# fmt: on


def get_server(group: str):
    """
    Get the server host for a certain room.

    :param str group: room name

    :returns: str
    """
    try:
        sn = specials[group]
    except KeyError:
        group = group.replace("_", "q")
        group = group.replace("-", "q")
        fnv = int(group[:5], 36)
        lnv = group[6:9]
        if lnv:
            lnv = int(lnv, 36)
            lnv = max(lnv, 1000)
        else:
            lnv = 1000
        num = (fnv % lnv) / lnv
        maxnum = sum(y for x, y in tsweights)
        cumfreq = 0
        sn = 0
        for x, y in tsweights:
            cumfreq += float(y) / maxnum
            if num <= cumfreq:
                sn = x
                break
    return f"s{sn}.chatango.com"


def public_attributes(obj):
    return [x for x in set(list(obj.__dict__.keys()) + list(dir(type(obj)))) if x[0] != "_"]


async def on_request_exception(session, context, params):
    logging.getLogger("aiohttp.client").debug(f"on request exception: <{params}>")


def trace():
    trace_config = aiohttp.TraceConfig()
    trace_config.on_request_exception.append(on_request_exception)
    return trace_config


_aiohttp_session = None


def get_aiohttp_session():
    global _aiohttp_session
    if _aiohttp_session is None:
        _aiohttp_session = aiohttp.ClientSession(trace_configs=[trace()])
    return _aiohttp_session


async def get_token(user_name, passwd):
    chatango, token = ["http://chatango.com/login", "auth.chatango.com"], None
    payload = {
        "user_id": str(user_name).lower(),
        "password": str(passwd),
        "storecookie": "on",
        "checkerrors": "yes",
    }
    # Use fresh session to retrieve auth cookies
    async with aiohttp.ClientSession().post(chatango[0], data=payload) as resp:
        if chatango[1] in resp.cookies:
            token = str(resp.cookies[chatango[1]]).split("=")[1].split(";")[0]
    return token


def multipart(data, files, boundary=None):
    lines = []

    def escape_quote(s):
        return s.replace('"', '\\"')

    if boundary == None:
        boundary = "".join(random.choice(string.digits + string.ascii_letters) for x in range(30))
    for name, value in data.items():
        lines.extend(
            (
                "--%s" % boundary,
                'Content-Disposition: form-data; name="%s"' % name,
                "",
                str(value),
            )
        )
    for name, value in files.items():
        filename = value["filename"]
        if "mimetype" in value:
            mimetype = value["mimetype"]
        else:
            mimetype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        lines.extend(
            (
                "--%s" % boundary,
                'Content-Disposition: form-data; name="%s"; '
                'filename="%s"' % (escape_quote(name), escape_quote(filename)),
                "Content-Type: %s" % mimetype,
                "",
                value["content"],
            )
        )
    lines.extend(
        (
            "--%s--" % boundary,
            "",
        )
    )
    body = "\r\n".join(lines)
    headers = {
        "Content-Type": "multipart/form-data; boundary=%s" % boundary,
        "Content-Length": str(len(body)),
    }
    return body, headers


async def http_get(url: str, session: Optional[aiohttp.ClientSession] = None):
    if not session:
        session = get_aiohttp_session()
    async with session.get(url) as resp:
        assert resp.status == 200
        try:
            resp = await resp.text()
            return resp
        except Exception as e:
            return None


async def session_get(session: aiohttp.ClientSession, url: str):
    async with session.get(url) as resp:
        assert resp.status == 200
        try:
            resp = await resp.text()
            return resp
        except Exception as e:
            return None


async def make_requests(urls):
    r = {}
    for x in urls:
        task = asyncio.create_task(session_get(get_aiohttp_session(), x[1]))
        r[x[0]] = task
    await asyncio.gather(*r.values())
    return r


def gen_uid() -> str:
    """Generate an uid."""
    return str(random.randrange(10**15, 10**16))


def _clean_message(msg: str, pm: bool = False) -> Tuple[str, str, str]:
    n = re.search(r"<n(.*?)/>", msg)
    tag = pm and "g" or "f"
    f = re.search(r"<" + tag + "(.*?)>", msg)
    msg = re.sub(r"<" + tag + ".*?>" + '|"<i s=sm://(.*)"', "", msg)
    if n:
        n = n.group(1)
    if f:
        f = f.group(1)
    msg = re.sub(r"<n.*?/>", "", msg)
    msg = _strip_html(msg)
    msg = html.unescape(msg).replace("\r", "\n")
    return msg, n or "", f or ""


def _strip_html(msg: str) -> str:
    li = msg.split("<")
    if len(li) == 1:
        return li[0]
    else:
        ret = []
        for data in li:
            data = data.split(">", 1)
            if len(data) == 1:
                ret.append(data[0])
            elif len(data) == 2:
                if data[0].startswith("br"):
                    ret.append("\n")
                ret.append(data[1])
        return "".join(ret)


def _id_gen():
    return "".join(random.choice(string.ascii_uppercase) for i in range(4)).lower()


def get_anon_name(tssid: str, puid: str) -> str:
    puid = puid.zfill(8)[4:8]
    ts = str(tssid)
    if not ts or len(ts) < 4:
        ts = "3452"
    else:
        ts = ts.split(".")[0][-4:]
    __reg5 = ""
    __reg1 = 0
    while __reg1 < len(puid):
        __reg4 = int(puid[__reg1])
        __reg3 = int(ts[__reg1])
        __reg2 = str(__reg4 + __reg3)
        __reg5 += __reg2[-1:]
        __reg1 += 1
    return "anon" + __reg5.zfill(4)


def _fontFormat(text):
    """Converts */_ into whattsap like formats"""
    formats = {"/": "I", "\*": "B", "_": "U"}
    for f in formats:
        f1, f2 = set(formats.keys()) - {f}
        # find = ' <?[BUI]?>?[{0}{1}]?{2}(.+?[\S]){2}'.format(f1, f2, f+'{1}')
        find = r" <?[BUI]?>?[{0}{1}]?{2}(.+?[\S]?[{2}]?){2}[{0}{1}]?[\s]".format(f1, f2, f)
        for x in re.findall(find, " " + text + " "):
            original = f[-1] + x + f[-1]
            cambio = "<" + formats[f] + ">" + x + "</" + formats[f] + ">"
            text = text.replace(original, cambio)
    return text


def _parseFont(f: str, pm=False) -> Tuple[str, str, str]:
    """
    Fetches font size, color and font from a message.

    :returns: Tuple[str, str, str]
    """
    if pm:
        regex = r'x(\d{1,2})?s([a-fA-F0-9]{6}|[a-fA-F0-9]{3})="|\'(.*?)"|\''
    else:
        regex = r'x(\d{1,2})?([a-fA-F0-9]{6}|[a-fA-F0-9]{3})="(.*?)"'
    match = re.search(regex, f)
    if not match:
        return "11", "000000", "0"
    return match.groups()


def _videoImagePMFormat(text):
    """Returns text with formatted video and image for PM sending."""
    for x in re.findall(r"(http[s]?://[^\s]+outube.com/watch\?v=([^\s]+))", text):
        original = x[0]
        cambio = '<i s="vid://yt:%s" w="126" h="96"/>' % x[1]
        text = text.replace(original, cambio)
    for x in re.findall(r"(http[s]?://[\S]+outu.be/([^\s]+))", text):
        original = x[0]
        cambio = '<i s="vid://yt:%s" w="126" h="96"/>' % x[1]
        text = text.replace(original, cambio)
    for x in re.findall(r"http[s]?://[\S]+?.jpg", text):
        text = text.replace(x, '<i s="%s" w="70.45" h="125"/>' % x)
    return text


class Styles:
    """User message styles."""

    def __init__(
        self,
        name_color=None,
        font_color=None,
        font_face=None,
        font_size=None,
        use_background=None,
    ):
        self._name_color = name_color if name_color else str("000000")
        self._font_color = font_color if font_color else str("000000")
        self._font_size = font_size if font_size else 11
        self._font_face = font_face if font_face else 0
        self._use_background = int(use_background) if use_background else 0

        self._blend_name = None
        self.bgstyle = {
            "align": "",
            "bgc": "",
            "bgalp": "",
            "hasrec": "0",
            "ialp": "",
            "isvid": "0",
            "tile": "0",
            "useimg": "0",
        }
        self._profile = dict(
            about=dict(age="", last_change="", gender="?", location="", d="", body=""),
            full=dict(),
        )

    def __dir__(self):
        return public_attributes(self)

    def __repr__(self):
        return f"nc:{self.name_color} |bg:{self.use_background} |{self.default}"

    @property
    def profile(self):
        return self._profile

    @property
    def aboutme(self):
        return self._profile["about"]

    @property
    def fullhtml(self):
        o = html.escape(urllib.parse.unquote(self._profile["full"] or "")).replace("\r\n", "\n")
        if o:
            return o
        return None

    @property
    def fullmini(self):
        o = html.escape(urllib.parse.unquote(self._profile["about"]["body"] or "")).replace("\r\n", "\n")
        if o:
            return o
        return None

    @property
    def use_background(self):
        return self._use_background

    @property
    def default(self):
        size = str(self.font_size)
        face = str(self.font_face)
        return f"<f x{size}{self.font_color}='{face}'>"

    @property
    def name_color(self):
        return self._name_color

    @property
    def font_color(self):
        return self._font_color

    @property
    def font_size(self):
        return self._font_size

    @property
    def font_face(self):
        return self._font_face

    def set_name_color(self, color):
        self._name_color = color

    def set_font_color(self, color):
        self._font_color = color

    def set_font_face(self, face):
        self._font_face = face

    def set_font_size(self, size):
        self._font_size = size

    def set_use_background(self, use_background):
        self._use_background = use_background


def _convert_dict(src):
    r = {}
    m = src.split(" ")
    for w in m:
        k, v = w.split("=")
        r.update({k: v})
    return r
