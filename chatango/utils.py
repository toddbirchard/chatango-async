from typing import Tuple
import asyncio
import random
import mimetypes
import html
import re
import string
import aiohttp
from .hasher import Hasher

from logger import LOGGER
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
    sn = specials.get(group)
    if not sn:
        hash = Hasher().hash(group)
        sn = tshashes.get(hash)
    if not sn:
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


def public_attributes(obj):
    return [
        x for x in set(list(obj.__dict__.keys()) + list(dir(type(obj)))) if x[0] != "_"
    ]


async def on_request_exception(session, context, params):
    LOGGER.debug(f"on request exception: <{params}>")


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
    lineas = []

    def escape_quote(s):
        return s.replace('"', '\\"')

    if boundary == None:
        boundary = "".join(random.choice(string.digits + string.ascii_letters) for x in range(30))
    for nombre, valor in data.items():
        lineas.extend(
            (
                "--%s" % boundary,
                'Content-Disposition: form-data; name="%s"' % nombre,
                "",
                str(valor),
            )
        )
    for nombre, valor in files.items():
        filename = valor["filename"]
        if "mimetype" in valor:
            mimetype = valor["mimetype"]
        else:
            mimetype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        lineas.extend(
            (
                "--%s" % boundary,
                'Content-Disposition: form-data; name="%s"; '
                'filename="%s"' % (escape_quote(nombre), escape_quote(filename)),
                "Content-Type: %s" % mimetype,
                "",
                valor["content"],
            )
        )
    lineas.extend(
        (
            "--%s--" % boundary,
            "",
        )
    )
    body = "\r\n".join(lineas)
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
        except:
            return None


def gen_uid() -> str:
    """
    Generate an uid
    """
    return str(random.randrange(10**15, 10**16))


def _clean_message(msg: str, pm: bool = False) -> Tuple[str, str, str]:
    n = re.search("<n(.*?)/>", msg)
    tag = pm and "g" or "f"
    f = re.search("<" + tag + "(.*?)>", msg)
    msg = re.sub("<" + tag + ".*?>" + '|"<i s=sm://(.*)"', "", msg)
    if n:
        n = n.group(1)
    if f:
        f = f.group(1)
    msg = re.sub("<n.*?/>", "", msg)
    msg = _strip_html(msg)
    msg = html.unescape(msg).replace("\r", "\n")
    return msg, n or "", f or ""


def _strip_html(msg: str) -> str:
    li = msg.split("<")
    if len(li) == 1:
        return li[0]
    else:
        ret = list()
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
    # TODO check
    """Converts */_ into whattsap like formats"""
    formats = {"/": "I", "\*": "B", "_": "U"}
    for f in formats:
        f1, f2 = set(formats.keys()) - {f}
        # find = ' <?[BUI]?>?[{0}{1}]?{2}(.+?[\S]){2}'.format(f1, f2, f+'{1}')
        find = " <?[BUI]?>?[{0}{1}]?{2}(.+?[\S]?[{2}]?){2}[{0}{1}]?[\s]".format(
            f1, f2, f
        )
        for x in re.findall(find, " " + text + " "):
            original = f[-1] + x + f[-1]
            cambio = "<" + formats[f] + ">" + x + "</" + formats[f] + ">"
            text = text.replace(original, cambio)
    return text


def _parseFont(f: str, pm=False) -> Tuple[str, str, str]:
    """
    Lee el contendido de un etiqueta f y regresa
    tamaño color y fuente (en ese orden)
    @param f: El texto con la etiqueta f incrustada
    @return: Tamaño, Color, Fuente
    """
    if pm:
        regex = r'x(\d{1,2})?s([a-fA-F0-9]{6}|[a-fA-F0-9]{3})="|\'(.*?)"|\''
    else:
        regex = r'x(\d{1,2})?([a-fA-F0-9]{6}|[a-fA-F0-9]{3})="(.*?)"'
    match = re.search(regex, f)
    if not match:
        return "11", "000000", "0"
    else:
        return match.groups()


def _videoImagePMFormat(text):
    """Returns text with formatted video and image for PM sending"""
    for x in re.findall("(http[s]?://[^\s]+outube.com/watch\?v=([^\s]+))", text):
        original = x[0]
        cambio = '<i s="vid://yt:%s" w="126" h="96"/>' % x[1]
        text = text.replace(original, cambio)
    for x in re.findall("(http[s]?://[\S]+outu.be/([^\s]+))", text):
        original = x[0]
        cambio = '<i s="vid://yt:%s" w="126" h="96"/>' % x[1]
        text = text.replace(original, cambio)
    for x in re.findall("http[s]?://[\S]+?.jpg", text):
        text = text.replace(x, '<i s="%s" w="70.45" h="125"/>' % x)
    return text