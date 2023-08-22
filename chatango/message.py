"""Chatango Messages."""
import re
import time
import enum
from typing import Optional

from .utils import get_anon_name, _clean_message, _parseFont, public_attributes
from .user import User


class MessageFlags(enum.IntFlag):
    """Message flags."""

    PREMIUM = 1 << 2
    BG_ON = 1 << 3
    MEDIA_ON = 1 << 4
    CENSORED = 1 << 5
    SHOW_MOD_ICON = 1 << 6
    SHOW_STAFF_ICON = 1 << 7
    DEFAULT_ICON = 1 << 6
    CHANNEL_RED = 1 << 8
    CHANNEL_ORANGE = 1 << 9
    CHANNEL_GREEN = 1 << 10
    CHANNEL_CYAN = 1 << 11
    CHANNEL_BLUE = 1 << 12
    CHANNEL_PURPLE = 1 << 13
    CHANNEL_PINK = 1 << 14
    CHANNEL_MOD = 1 << 15


Fonts = {
    "0": "arial",
    "1": "comic",
    "2": "georgia",
    "3": "handwriting",
    "4": "impact",
    "5": "palatino",
    "6": "papirus",
    "7": "times",
    "8": "typewriter",
}


class Message:
    """Chatango message sent by client, to either `room` or via `pm`."""

    def __init__(self):
        self.user: Optional[User] = None
        self.room = None
        self.time = 0.0
        self.body = str()
        self.raw = str()
        self.styles = None
        self.channel: Optional[Channel] = None

    def __dir__(self):
        return public_attributes(self)

    def __repr__(self):
        return f'<Message {self.room} {self.user} "{self.body}">'


class PMMessage(Message):
    """Private message object."""

    def __init__(self):
        self.msgoff = False
        self.flags = str(0)


class RoomMessage(Message):
    """Room message object."""

    def __init__(self):
        self.id = None
        self.puid = str()
        self.ip = str()
        self.unid = str()
        self.flags = 0
        self.mentions = []

    def attach(self, room, msgid):
        """`Attach` message to room."""
        if self.id is not None:
            self.room = room
            self.id = msgid
            self.room.msgs.update({id: self})

    def detach(self):
        """`Detach` message from room."""
        if self.id is not None and self.id in self.room.msgs:
            self.room.msgs.pop(self.id)


async def _process(room, args):
    """Process message."""
    _time = float(args[0]) - room._correctiontime
    name, tname, puid, unid, msgid, ip, flags = args[1:8]
    body = ":".join(args[9:])
    msg = RoomMessage()
    msg.room = room
    msg.time = float(_time)
    msg.puid = str(puid)
    msg.id = msgid
    msg.unid = unid
    msg.ip = ip
    msg.raw = body
    body, n, f = _clean_message(body)
    strip_body = " ".join(body.split(" ")[:-1]) + " " + body.split(" ")[-1].replace("\n", "")
    msg.body = strip_body.strip()
    name_color = None
    isanon = False
    if name == "":
        isanon = True
        if not tname:
            if n in ["None"]:
                n = None
            if not isinstance(n, type(None)):
                name = get_anon_name(n, puid)
            else:
                name = get_anon_name("", puid)
        else:
            name = tname
    else:
        if n:
            name_color = n
        else:
            name_color = None
    msg.user = User(name, ip=ip, isanon=isanon)
    msg.user.user_styles.set_name_color(name_color)
    msg.styles = msg.user.user_styles
    # msg.styles.font_size, msg.styles._font_color, msg.styles._font_face = _parseFont(f.strip())
    if msg.styles.font_size is None:
        msg.styles.set_font_size(11)
    msg.flags = MessageFlags(int(flags))
    if MessageFlags.BG_ON in msg.flags:
        if MessageFlags.PREMIUM in msg.flags:
            msg.styles.set_use_background(1)
    msg.mentions = mentions(msg.body, room)
    msg.channel = Channel(msg.room, msg.user)
    is_premium = MessageFlags.PREMIUM in msg.flags
    if msg.user.is_premium_user != is_premium:
        evt = msg.user.is_premium_user is not None and is_premium is not None and _time > time.time() - 5
        msg.user.set_premium_user(is_premium)
        if evt:
            await room.handler._call_event("premium_change", msg.user, is_premium)
    return msg


async def _process_pm(room, args):
    name = args[0] or args[1]
    if not name:
        name = args[2]
    user = User(name)
    mtime = float(args[3]) - room._correctiontime
    rawmsg = ":".join(args[5:])
    body, n, f = _clean_message(rawmsg, pm=True)
    name_color = n or None
    font_size, font_color, font_face = _parseFont(f)
    msg = PMMessage()
    msg.room = room
    msg.user = user
    msg.time = mtime
    msg.body = body
    msg.raw = rawmsg
    msg.styles = msg.user.user_styles
    msg.styles.name_color = name_color
    msg.styles.font_size = font_size
    msg.styles.set_font_color(font_color)
    msg.styles.set_font_face(font_face)
    msg.channel = Channel(msg.room, msg.user)
    return msg


def message_cut(message, lenth):
    result = []
    for o in [message[x : x + lenth] for x in range(0, len(message), lenth)]:
        result.append(o)
    return result


def mentions(body, room):
    t = []
    for match in re.findall("(\s)?@([a-zA-Z0-9]{1,20})(\s)?", body):
        for participant in room.userlist:
            if participant.name.lower() == match[1].lower():
                if participant not in t:
                    t.append(participant)
    return t


class Channel:
    def __init__(self, room, user):
        self.is_pm = True if room.name == "<PM>" else False
        self.user = user
        self.room = room

    def __dir__(self):
        return public_attributes(self)

    async def send_message(self, message, use_html=False):
        messages = message_cut(message, self.room._maxlen)
        for message in messages:
            if self.is_pm:
                await self.room.send_message(self.user.name, message, use_html=use_html)
            else:
                await self.room.send_message(message, use_html=use_html)

    async def send_pm(self, message):
        self.is_pm = True
        await self.send_message(message)


# def format_videos(user, pmmessage): pass #TODO TESTING
#     msg = pmmessage
#     tag = 'i'
#     r = []
#     for word in msg.split(' '):
#         if msg.strip() != "":
#             regx = re.compile(r'(https?://)?(www\.)?(youtube|youtu|youtube-nocookie)\.(com|be)/(watch\?v=|embed/|v/|.+\?v=)?(?P<id>[A-Za-z0-9\-=_]{11})') #"<" + tag + "(.*?)>", msg)
#             match = regx.match(word)
#             w = "<g x{0._fontSize}s{0._fontColor}=\"{0._fontFace}\">".format(user)
#             if match:
#                 seek = match.group('id')
#                 word = f"<i s=\"vid','//yt','{seek}\" w=\"126\" h=\"93\"/>{w}"
#                 r.append(word)
#             else:
#                 if not r:
#                     r.append(w+word)
#                 else:
#                     r.append(word)
#             count = len([x for x in r if x == w])
#             print(count)

#     print(r)
#     return " ".join(r)
