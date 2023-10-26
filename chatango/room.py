from typing import Optional, List
from collections import deque, namedtuple
import sys
import html
import time
import enum
import re
import traceback
import asyncio
import urllib.request as urlreq
import aiohttp

from logger import LOGGER
from .utils import (
    get_aiohttp_session,
    get_server,
    gen_uid,
    get_anon_name,
    _id_gen,
    public_attributes,
)
from .message import Message, MessageFlags, _process, message_cut
from .user import User, ModeratorFlags, AdminFlags
from .exceptions import AlreadyConnectedError, InvalidRoomNameError
from .handler import EventHandler


class RoomFlags(enum.IntFlag):
    LIST_TAXONOMY = 1 << 0
    NO_ANONS = 1 << 2
    NO_FLAGGING = 1 << 3
    NO_COUNTER = 1 << 4
    NO_IMAGES = 1 << 5
    NO_LINKS = 1 << 6
    NO_VIDEOS = 1 << 7
    NO_STYLED_TEXT = 1 << 8
    NO_LINKS_CHATANGO = 1 << 9
    NO_BROADCAST_MSG_WITH_BW = 1 << 10
    RATE_LIMIT_REGIMEON = 1 << 11
    CHANNELS_DISABLED = 1 << 13
    NLP_SINGLEMSG = 1 << 14
    NLP_MSGQUEUE = 1 << 15
    BROADCAST_MODE = 1 << 16
    CLOSED_IF_NO_MODS = 1 << 17
    IS_CLOSED = 1 << 18
    SHOW_MOD_ICONS = 1 << 19
    MODS_CHOOSE_VISIBILITY = 1 << 20
    NLP_NGRAM = 1 << 21
    NO_PROXIES = 1 << 22
    HAS_XML = 1 << 28
    UNSAFE = 1 << 29


class Connection:
    """Connection manager ued to connect to chatrooms, PMs, etc."""

    def __init__(self, handler: EventHandler):
        self.handler = handler
        self._reset()

    def _reset(self):
        self._connected = False
        self._first_command = True
        self._connection: Optional[aiohttp.ClientWebSocketResponse] = None
        self._recv_task: Optional[asyncio.Task] = None
        self._ping_task: Optional[asyncio.Task] = None

    @property
    def connected(self) -> bool:
        """Connection status of client to a given room."""
        return self._connected

    async def _connect(self, server: str):
        try:
            self._connection = await get_aiohttp_session().ws_connect(
                f"ws://{server}:8080/", origin="http://st.chatango.com"
            )
            self._connected = True
            self._recv_task = asyncio.create_task(self._do_recv())
            self._ping_task = asyncio.create_task(self._do_ping())
        except aiohttp.ClientError as e:
            await self._disconnect()
            LOGGER.error(f"Could not connect to {server}: {e}")

    async def _disconnect(self):
        if self._ping_task:
            self._ping_task.cancel()
        if self._connection:
            await self._connection.close()
        self._reset()

    async def _send_command(self, *args, terminator="\r\n\0"):
        message = ":".join(args) + terminator
        if message != "\r\n\x00":  # ping
            LOGGER.info(f'OUT {":".join(args)}')
        if self._connection:
            await self._connection.send_str(message)

    async def _do_ping(self):
        """Ping the socket every minute to keep alive"""
        try:
            while True:
                await asyncio.sleep(90)
                if not self.connected:
                    break
                await self._send_command("\r\n", terminator="\x00")
                await self.handler.call_event("ping", self)
        except asyncio.exceptions.CancelledError:
            pass

    async def _do_recv(self):
        while self._connection:
            message = await self._connection.receive()
            if not self.connected:
                break
            if message.type == aiohttp.WSMsgType.TEXT:
                if message.data:
                    LOGGER.debug(f" IN {message.data}")
                    await self._do_process(message.data)
                else:
                    await self._do_process("pong")
            elif (
                message.type == aiohttp.WSMsgType.CLOSE
                or message.type == aiohttp.WSMsgType.CLOSING
                or message.type == aiohttp.WSMsgType.CLOSED
                or message.type == aiohttp.WSMsgType.ERROR
            ):
                await self._disconnect()
                break
            else:
                LOGGER.error(f"Unexpected aiohttp WSMsgType: {message.type}")
            await asyncio.sleep(0.0001)
        await self.handler.call_event("disconnect", self)

    async def _do_process(self, recv: str):
        """Process one command."""
        if recv:
            cmd, _, args = recv.partition(":")
            args = args.split(":")
        else:
            return
        if hasattr(self, f"_rcmd_{cmd}"):
            try:
                await getattr(self, f"_rcmd_{cmd}")(args)
            except Exception as e:
                LOGGER.error(f"Error while handling command `{cmd}`: {e}")
                traceback.print_exc(file=sys.stderr)
        LOGGER.error(f"Unhandled received command `{cmd}`")


class Room(Connection):
    _BANDATA = namedtuple("BanData", ["unid", "ip", "target", "time", "src"])

    def __dir__(self):
        return public_attributes(self)

    def __init__(self, handler, name: str):
        super().__init__(handler)
        self.assert_valid_name(name)
        self.name = name
        self.server = get_server(name)
        self.reconnect = False
        self.owner: Optional[User] = None
        self._uid = gen_uid()
        self._bwqueue = str()
        self._user = None
        self._silent = False
        self._mods = {}
        self._userhistory = deque(maxlen=10)
        self._userdict = {}
        self._mqueue = {}
        self._uqueue = {}
        self.msgs = {}
        self._users = {}
        self._unid = str()
        self._ban_list = {}
        self._unbanlist = {}
        self._unban_queue = deque(maxlen=500)
        self._user_count = 0
        self._del_dict = {}
        self._maxlen = 2700
        self._history = deque(maxlen=self._maxlen + 300)
        self._bgmode = 0
        self._nomore = False
        self._connectiontime = None
        self.message_flags = 0
        self._announcement = [0, 0, ""]
        self._badge = 0

    def __repr__(self):
        return f"<Room {self.name}>"

    @property
    def is_pm(self):
        """Whether current session is a PM."""
        return False

    @property
    def badge(self):
        if not self._badge:
            return 0
        elif self._badge == 1:
            return MessageFlags.SHOW_MOD_ICON.value
        elif self._badge == 2:
            return MessageFlags.SHOW_STAFF_ICON.value
        else:
            return 0

    @property
    def get_maxlen(self):
        """Maximum message length."""
        return self._maxlen

    @property
    def unban_list(self):
        """List of unbanned users from room."""
        return list(set(x.target.name for x in self._unban_queue))

    @property
    def history(self):
        """Get room chat history."""
        return self._history

    @property
    def silent(self):
        return self._silent

    @property
    def ban_list(self):
        """Get current room's list of banned usernames."""
        return list(self._ban_list.keys())

    @property
    def flags(self):
        return self._flags

    @property
    def user(self):
        """Chatango user present in room."""
        return self._user

    @property
    def mods(self) -> List[str]:
        """Usernames of moderators in chatroom."""
        return set(self._mods.keys())

    @property
    def user_list(self):
        """List of users currently in chatroom."""
        return self._get_user_list()

    @property
    def anon_list(self):
        """List of anonymous users currently in chatroom."""
        return list(set(self.all_user_list) - set(self.user_list))

    @property
    def user_count(self):
        """Number of users currently in chatroom."""
        if RoomFlags.NO_COUNTER in self.flags:
            return len(self.all_user_list)
        return self._user_count

    @property
    def all_user_list(self):
        """List of all users (including anons)"""
        return sorted([x[1] for x in list(self._userdict.values())], key=lambda z: z.name.lower())

    @classmethod
    def assert_valid_name(cls, room_name: str):
        """
        Confirm that Chatango room name is valid.

        :param str room_name: Name of Chatango room to validate.
        """
        expr = re.compile(r"^([a-z0-9-]{1,20})$")
        if not expr.match(room_name):
            raise InvalidRoomNameError(room_name)

    async def connect(self, user_name: str = "", password: str = ""):
        """
        Connect and login to the room
        """
        if self.connected:
            raise AlreadyConnectedError(self.name)
        await self._connect(self.server)
        await self._auth(user_name, password)

    async def connection_wait(self):
        """
        Wait until the connection is closed
        """
        if self._recv_task:
            await self._recv_task

    async def disconnect(self):
        """
        Force this room to disconnect
        """
        for x in self.user_list:
            x.removeSessionId(self, 0)
        self.reconnect = False
        await self._disconnect()

    async def bounce(self):
        """Disconnect, but allow reconnection."""
        await self._disconnect()

    async def listen(self, user_name: str = "", password: str = "", reconnect=False):
        """
        Join and wait on room connection.

        :param str user_name: User attempting to join room.
        :param str password : Password of user attempting to join room.
        :param bool reconnect: Whether to attempt reconnection upon failure.
        """
        self.reconnect = reconnect
        while True:
            await self.connect(user_name, password)
            await self.connection_wait()
            if not self.reconnect:
                break
            await asyncio.sleep(3)

    async def _auth(self, user_name: str, password: str):
        """
        Login when joining a room.

        :param str user_name: Name of Chatango user to authenticate as.
        :param str password: Password of Chatango user to authenticate with.
        """
        await self._send_command("bauth", self.name, self._uid, user_name, password)

    async def _login(self, user_name: str, password: str):
        """
        Login after having connected as anon.

        :param str user_name: Name of Chatango user to authenticate as.
        :param str password: Password of Chatango user to authenticate with.
        """
        self._user = User(user_name, isanon=not password)
        await self._send_command("blogin", user_name, password)

    async def _logout(self):
        """Log out of current Chatango user account"""
        await self._send_command("blogout")

    async def send_message(self, message: Message, use_html=True, flags=None):
        """
        Send chat message to Chatango room.

        :param RoomMessage message: Message to send to Chatango room.
        :param bool use_html: Whether to use HTML formatting.
        """
        if not self.silent:
            message_flags = flags if flags else self.message_flags + self.badge or 0 + self.badge
            msg = str(message)
            if not use_html:
                msg = html.escape(msg, quote=False)
            msg = msg.replace("\n", "\r").replace("~", "&#126;")
            for msg in message_cut(msg, self._maxlen):
                message = f'<n{self.user.styles.name_color}/><f x{self.user.styles.font_size}{self.user.styles.font_color}="{self.user.styles.font_face}">{msg}</f>'
                await self._send_command("bm", _id_gen(), str(message_flags), message)

    def set_font(self, name_color=None, font_color=None, font_size=None, font_face=None):
        """Set custom font style for messages."""
        if name_color:
            self._user.user_styles.set_name_color(str(name_color))
        if font_color:
            self._user.user_styles.set_font_color(str(font_color))
        if font_size:
            self._user.user_styles.set_font_size(int(font_size))
        if font_face:
            self._user.user_styles.set_font_face(int(font_face))

    async def enable_bg(self):
        """Enable background images for messages in room."""
        await self.set_bg_mode(1)

    async def disable_bg(self):
        """Disable background images for messages in room."""
        await self.set_bg_mode(0)

    def get_session_list(self, mode=0, memory=0):
        if mode < 2:
            return [(x.name if mode else x, len(x.getSessionIds(self))) for x in self._get_user_list(1, memory)]
        else:
            return [(x.showname, len(x.getSessionIds(self))) for x in self._get_user_list(1, memory)]

    def _get_user_list(self, unique=1, memory=0, anons=False):
        ul = []
        if not memory:
            ul = [x[1] for x in self._userdict.copy().values() if anons or not x[1].isanon]
        elif type(memory) == int:
            ul = set(
                map(
                    lambda x: x.user,
                    list(self._history)[min(-memory, len(self._history)) :],
                )
            )
        if unique:
            ul = set(ul)
        return sorted(list(ul), key=lambda x: x.name.lower())

    def get_level(self, user):
        if isinstance(user, str):
            user = User(user)
        if user == self.owner:
            return 3
        if user in self._mods:
            if self._mods.get(user).isadmin:
                return 2
            else:
                return 1
        return 0

    def ban_record(self, user: User) -> Optional[List[User]]:
        """
        Get record of rooms a given user has been banned from.

        :param User user: User to get ban record for.
        """
        if isinstance(user, User):
            user = user.name
        if user.lower() in [x.name for x in self._ban_list]:
            return self._ban_list[User(user)]
        return None

    def get_last_message(self, user: Optional[User] = None) -> Optional[List[User]]:
        """
        Get last message sent by a given user.

        :param Optional[User] user: User to get last message for.

        :returns: Optional[List[User]]
        """
        if not user:
            return self._history and self._history[-1] or None
        if isinstance(user, User):
            user = user.name
        for x in reversed(self.history):
            if x.user.name == user:
                return x
        return None

    async def _raw_unban(self, name, ip, unid):
        await self._send_command("removeblock", unid, ip, name)

    def _add_history(self, msg):
        if len(self._history) == 2900:
            rest = self._history.popleft()
            rest.detach()
        self._history.append(msg)

    async def unban_user(self, user: User) -> bool:
        """
        Unban user from room (if applicable).

        :param User user: User to unban from room (if user is banned).

        :returns: bool
        """
        rec = self.ban_record(user)
        print("rec", rec)
        if rec:
            await self._raw_unban(rec.target.name, rec.ip, rec.unid)
            return True
        return False

    async def ban_message(self, msg: Message) -> bool:
        """
        Ban a user based on message sent.

        :param Message msg: Message to ban user from room (if applicable).

        :returns: bool
        """
        if self.get_level(self.user) > 0:
            name = "" if msg.user.is_anon else msg.user.name
            await self._raw_ban(msg.unid, msg.ip, name)
            return True
        return False

    async def _raw_ban(self, msgid: str, ip: str, name: str) -> bool:
        """
        Ban user with received data.

        :param str msgid: Message ID.
        :param str ip: User's IP address.
        :param: str name: chatango user name

        :returns: bool
        """
        await self._send_command("block", msgid, ip, name)

    async def ban_user(self, username: str) -> bool:
        """
        Ban a user from room based on username (if privileges allow).

        :param str username: Username of user to ban.

        :returns: bool
        """
        msg = self.get_last_message(username)
        if msg and msg.user not in self.ban_list:
            return await self.ban_message(msg)
        return False

    async def clear_all(self):
        """Purge all messages in a room (if privileges allow)."""
        if self.user in self._mods and ModeratorFlags.EDIT_GROUP in self._mods[self.user] or self.user == self.owner:
            await self._send_command("clearall")
            return True
        else:
            return False

    async def clear_user(self, user):
        if self.get_level(self.user) > 0:
            msg = self.get_last_message(user)
            if msg:
                name = "" if msg.user.isanon else msg.user.name
                await self._send_command("delallmsg", msg.unid, msg.ip, name)
                return True
        return False

    async def delete_message(self, message):
        if self.get_level(self.user) > 0 and message.id:
            await self._send_command("delmsg", message.id)
            return True
        return False

    async def delete_user(self, user):
        if self.get_level(self.user) > 0:
            msg = self.get_last_message(user)
            if msg:
                await self.delete_message(msg)
        return False

    async def request_unbanlist(self):
        await self._send_command(
            "blocklist",
            "unblock",
            str(int(time.time() + self._correctiontime)),
            "next",
            "500",
            "anons",
            "1",
        )

    async def request_banlist(self):  # TODO revisar
        await self._send_command(
            "blocklist",
            "block",
            str(int(time.time() + self._correctiontime)),
            "next",
            "500",
            "anons",
            "1",
        )

    async def set_banned_words(self, part="", whole=""):
        """
        Actualiza las palabras baneadas para que coincidan con las recibidas
        @param part: Las partes de palabras que serán baneadas (separadas por
        coma, 4 carácteres o más)
        @param whole: Las palabras completas que serán baneadas, (separadas
        por coma, cualquier tamaño)
        """
        if self.user in self._mods and ModeratorFlags.EDIT_BW in self._mods[self.user]:
            await self._send_command("setbannedwords", urlreq.quote(part), urlreq.quote(whole))
            return True
        return False

    async def _reload(self):
        if self._user_count <= 1000:
            await self._send_command("g_participants:start")
        else:
            await self._send_command("gparticipants:start")
        await self._send_command("getpremium", "l")
        await self._send_command("getannouncement")
        await self._send_command("getbannedwords")
        await self._send_command("getratelimit")
        await self.request_banlist()
        await self.request_unbanlist()
        if self.user.is_premium_user:
            await self._style_init(self._user)

    async def set_bg_mode(self, mode):
        self._bgmode = mode
        if self.connected:
            await self._send_command("getpremium", "l")
            if self.user.is_premium_user:
                await self._send_command("msgbg", str(self._bgmode))

    async def _style_init(self, user):
        if not user.isanon:
            if self.user.is_premium_user:
                await user.get_styles()
            await user.get_main_profile()
        else:
            self.set_font(name_color="000000", font_color="000000", font_size=11, font_face=1)

    async def _rcmd_ok(self, args):  # TODO
        self.owner = User(args[0])
        self._puid = args[1]
        self._login_as = args[2]
        self._currentname = args[3]
        self._connectiontime = args[4]
        self._correctiontime = int(float(self._connectiontime) - time.time())
        self._currentIP = args[5]
        self._flags = RoomFlags(int(args[7]))
        if self._login_as == "C":
            uname = get_anon_name(
                str(self._correctiontime).split(".")[0][-4:].replace("-", ""),
                self._puid,
            )
            self._user = User(uname, isanon=True, ip=self._currentIP)
        elif self._login_as == "M":
            self._user = User(self._currentname, puid=self._puid, ip=self._currentIP)
        elif self._login_as == "N":
            pass
        for mod in args[6].split(";"):
            if len(mod.split(",")) > 1:
                mod, power = mod.split(",")
                self._mods[User(mod)] = ModeratorFlags(int(power))
                self._mods[User(mod)].isadmin = ModeratorFlags(int(power)) & AdminFlags != 0
        await self.handler.call_event("connect", self)

    async def _rcmd_inited(self, args):
        await self._reload()

    async def _rcmd_pwdok(self, args):
        self._user._isanon = False
        await self._send_command("getpremium", "l")
        await self._style_init(self._user)

    async def _rcmd_annc(self, args):
        self._announcement[0] = int(args[0])
        anc = ":".join(args[2:])
        if anc != self._announcement[2]:
            self._announcement[2] = anc
            await self.handler.call_event("AnnouncementUpdate", args[0] != "0")
        await self.handler.call_event("Announcement", anc)

    async def _rcmd_pong(self, args):
        await self.handler.call_event("pong", self)

    async def _rcmd_nomore(self, args):  # TODO
        """No more past messages"""
        pass

    async def _rcmd_n(self, args):
        """user count"""
        self._user_count = int(args[0], 16)

    async def _rcmd_i(self, args):
        """history past messages"""
        msg = await _process(self, args)
        msg.attach(self, msg.id)
        self._add_history(msg)

    async def _rcmd_b(self, args):  # TODO
        msg = await _process(self, args)
        if self._del_dict:
            for message_inwait in self._del_dict:
                if self._del_dict[message_inwait]["m"] == msg.body and self.user == msg.user:
                    self._del_dict[message_inwait].update({"i": msg})
        if args[5] in self._uqueue:
            msgid = self._uqueue.pop(args[5])
            if msg.user != self._user:
                pass
            msg.attach(self, msgid)
            self._add_history(msg)
            await self.handler.call_event("message", msg)
        else:
            self._mqueue[msg.id] = msg

    async def _rcmd_premium(self, args):  # TODO
        if self._bgmode and (args[0] == "210" or (isinstance(self, Room) and self.owner == self.user)):
            self.user.is_premium_user = True
            await self._send_command("msgbg", str(self._bgmode))

    async def _rcmd_show_fw(self, args=None):
        await self.handler.call_event("flood_warning")

    async def _rcmd_u(self, args):
        """Attachs and call event on_message"""
        if args[0] in self._mqueue:
            msg = self._mqueue.pop(args[0])
            if msg.user != self._user:
                pass
            msg.attach(self, args[1])
            self._add_history(msg)
            await self.handler.call_event("message", msg)
        else:
            self._uqueue[args[0]] = args[1]

    async def _rcmd_gparticipants(self, args):
        """Old command, chatango keep sending it."""
        await self._rcmd_g_participants(len(args) > 1 and args[1:] or "")

    async def _rcmd_g_participants(self, args):
        self._userdict = {}
        args = ":".join(args).split(";")  # return if not args
        for data in args:
            data = data.split(":")  # Lista de un solo usuario
            ssid = data[0]
            contime = data[1]  # Hora de conexión a la sala
            puid = data[2]
            name = data[3]
            tname = data[4]
            isanon = False
            if str(name) == "None":
                isanon = True
                if str(tname) != "None":
                    name = tname
                else:
                    name = get_anon_name(contime, puid)
            user = User(name, isanon=isanon, puid=puid)
            if user in ({self.owner} | self.mods):
                user.setName(name)
            user.addSessionId(self, ssid)
            self._userdict[ssid] = [contime, user]

    async def _rcmd_participant(self, args):
        cambio = args[0]  # Leave Join Change
        ssid = args[1]  # session
        puid = args[2]  # UID
        name = args[3]  # username
        tname = args[4]  # Anon Name
        unknown = args[5]  # ip
        contime = args[6]  # time
        isanon = False
        if name == "None":
            if tname != "None":
                name = tname
            else:
                name = get_anon_name(contime, puid)
            isanon = True
        user = User(name, isanon=isanon, puid=puid, ip=unknown)
        user.setName(name)
        before = None
        if ssid in self._userdict:
            before = self._userdict[ssid][1]
        if cambio == "0":  # Leave
            user.removeSessionId(self, ssid)
            if ssid in self._userdict:
                usr = self._userdict.pop(ssid)[1]
                lista = [x[1] for x in self._userhistory]
                if usr not in lista:
                    self._userhistory.append([contime, usr])
                else:
                    self._userhistory.remove([x for x in self._userhistory if x[1] == usr][0])
                    self._userhistory.append([contime, usr])
            if user.is_anon:
                await self.handler.call_event("anon_leave", self, user, puid)
            else:
                await self.handler.call_event("leave", self, user, puid)
        elif cambio == "1" or not before:  # Join
            user.addSessionId(self, ssid)
            if not user.is_anon and user not in self.user_list:
                await self.handler.call_event("join", self, user, puid)
            elif user.is_anon:
                await self.handler.call_event("anon_join", self, user, puid)
            self._userdict[ssid] = [contime, user]
            lista = [x[1] for x in self._userhistory]
            if user in lista:
                self._userhistory.remove([x for x in self._userhistory if x[1] == user][0])
        else:  # TODO
            if before.isanon:  # Login
                if user.is_anon:
                    await self.handler.call_event("anon_login", self, before, user, puid)
                else:
                    await self.handler.call_event("user_login", self, before, user, puid)
            elif not before.isanon:  # Logout
                if before in self.user_list:
                    lista = [x[1] for x in self._userhistory]

                    if before not in lista:
                        self._userhistory.append([contime, before])
                    else:
                        lst = [x for x in self._userhistory if before == x[1]]
                        if lst:
                            self._userhistory.remove(lst[0])
                        self._userhistory.append([contime, before])
                    await self.handler.call_event("user_logout", self, before, user, puid)

            self._userdict[ssid] = [contime, user]

    async def _rcmd_mods(self, args):
        pre = self._mods
        mods = self._mods = {}
        # Load current mods
        for mod in args:
            name, powers = mod.split(",", 1)
            utmp = User.get(name)
            self._mods[utmp] = ModeratorFlags(int(powers))
            self._mods[utmp].isadmin = ModeratorFlags(int(powers)) & AdminFlags != 0
        tuser = User(self._currentname)
        if (self.user not in pre and self.user in mods) or (tuser not in pre and tuser in mods):
            if self.user == tuser:
                await self.handler.call_event("mod_added", self.user)
            return

        for user in self.mods - set(pre.keys()):
            await self.handler.call_event("mod_added", user)
        for user in set(pre.keys()) - self.mods:
            await self.handler.call_event("mod_remove", user)
        for user in set(pre.keys()) & self.mods:
            privs = set(
                x
                for x in dir(mods.get(user))
                if not x.startswith("_") and getattr(mods.get(user), x) != getattr(pre.get(user), x)
            )
            privs = privs - {"MOD_ICON_VISIBLE", "value"}
            if privs:
                await self.handler.call_event("mods_change", user, privs)

    async def _rcmd_groupflagsupdate(self, args):
        flags = args[0]
        self._flags = self._flags = RoomFlags(int(flags))
        await self.handler.call_event("flags_update")

    async def _rcmd_blocked(self, args):  # TODO
        target = args[2] and User(args[2]) or ""
        user = User(args[3])
        if not target:
            msx = [msg for msg in self._history if msg.unid == args[0]]
            target = msx and msx[0].user or User("ANON")
            await self.handler.call_event("anon_ban", user, target)
        else:
            await self.handler.call_event("ban", user, target)
        self._ban_list[target] = self._BANDATA(args[0], args[1], target, float(args[4]), user)

    async def _rcmd_blocklist(self, args):  # TODO
        self._ban_list = {}
        sections = ":".join(args).split(";")
        for section in sections:
            params = section.split(":")
            if len(params) != 5:
                continue
            if params[2] == "":
                continue
            user = User(params[2])
            self._ban_list[user] = self._BANDATA(params[0], params[1], user, float(params[3]), User(params[4]))
        await self.handler.call_event("banlist_update")

    async def _rcmd_unblocked(self, args):
        """Unban event"""
        unid = args[0]
        ip = args[1]
        target = args[2].split(";")[0]
        # bnsrc = args[-3]
        ubsrc = User(args[-2])
        time = args[-1]
        self._unban_queue.append(self._BANDATA(unid, ip, target, float(time), ubsrc))
        if target == "":
            msx = [msg for msg in self._history if msg.unid == unid]
            target = msx and msx[0].user or User("anon", isanon=True)
            await self.handler.call_event("anon_unban", ubsrc, target)
        else:
            target = User(target)
            if target in self._ban_list:
                self._ban_list.pop(target)
            await self.handler.call_event("unban", ubsrc, target)

    async def _rcmd_unblocklist(self, args):
        sections = ":".join(args).split(";")
        for section in sections[::-1]:
            params = section.split(":")
            if len(params) != 5:
                continue
            unid = params[0]
            ip = params[1]
            target = User(params[2] or "Anon")
            time = float(params[3])
            src = User(params[4])
            self._unban_queue.append(self._BANDATA(unid, ip, target, time, src))
        await self.handler.call_event("unbanlist_update")

    async def _rcmd_clearall(self, args):
        await self.handler.call_event("clearall", args[0])

    async def _rcmd_denied(self, args):
        await self.disconnect()
        await self.handler.call_event("room_denied", self)

    async def _rcmd_updatemoderr(self, args):
        await self.handler.call_event("mod_update_error", User(args[1]), args[0])

    async def _rcmd_proxybanned(self, args):
        await self.handler.call_event("proxy_banned")

    async def _rcmd_show_tb(self, args):
        await self.handler.call_event("show_tmp_ban", int(args[0]))

    async def _rcmd_miu(self, args):
        await self.handler.call_event("bg_reload", User(args[0]))

    async def _rcmd_delete(self, args):
        """Borrar un mensaje de mi vista actual"""
        msg = self.msgs.get(args[0])
        if msg and msg in self._history:
            self._history.remove(msg)
            await self.handler.call_event("message_delete", msg.user, msg)
            msg.detach()
        #
        if len(self._history) < 20 and not self._nomore:
            await self._send_command("get_more:20:0")

    async def _rcmd_deleteall(self, args):
        """Mensajes han sido borrados"""
        user = None  # usuario borrado
        msgs = []  # mensajes borrados
        for msgid in args:
            msg = self.msgs.get(msgid)
            if msg and msg in self._history:
                self._history.remove(msg)
                user = msg.user
                msg.detach()
                msgs.append(msg)
        if msgs:
            await self.handler.call_event("delete_user", user, msgs)

    async def _rcmd_bw(self, args):  # Palabras baneadas en el chat
        # TODO, actualizar el registro del chat
        part, whole = "", ""
        if args:
            part = urlreq.unquote(args[0])
        if len(args) > 1:
            whole = urlreq.unquote(args[1])
        if hasattr(self, "_bwqueue"):
            # self._bwqueue = [self._bwqueue.split(':', 1)[0] + ',' + args[0],
            #                  self._bwqueue.split(':', 1)[1] + ',' + args[1]]
            # TODO agregar un callEvent
            await self.set_banned_words(*self._bwqueue)
        await self.handler.call_event("bannedwords_update", part, whole)

    async def _rcmd_getannc(self, args):
        # ['3', 'pythonrpg', '5', '60', '<nE20/><f x1100F="1">hola']
        # Enabled, Room, ?, Time, Message
        # TODO que significa el tercer elemento?
        if len(args) < 4 or args[0] == "none":
            return
        self._announcement = [int(args[0]), int(args[3]), ":".join(args[4:])]
        if hasattr(self, "_ancqueue"):
            # del self._ancqueue
            # self._announcement[0] = args[0] == '0' and 3 or 0
            # await self._send_command('updateannouncement', self._announcement[0],
            #                   ':'.join(args[3:]))
            pass

    async def _rcmd_getratelimit(self, args):
        pass  # print("GETRATELIMIT -> ", args)

    async def _rcmd_msglexceeded(self, args):
        # print(f"_rcmd_msglexceeded ->", args)
        await self.handler.call_event("room_message_length_exceeded")

    async def _rcmd_show_fw(self, args):
        # print(f"{self.name}_rcmd_show_fw ->", args)
        pass  # Show flood warning

    async def _rcmd_ubw(self, args):  # TODO palabas desbaneadas ?)
        self._ubw = args
        # print(f"{self.name}_rcmd_ubw", args)

    async def _rcmd_climited(self, args):
        # print(f"{self.name}_rcmd_climited", args)
        pass  # Climited

    async def _rcmd_show_nlp(self, args):
        # print(f"{self.name}_rcmd_show_nlp", args)
        pass  # Auto moderation

    async def _rcmd_nlptb(self, args):
        # print(f"{self.name}_rcmd_nlptb", args)
        pass  # Auto moderation temporary ban

    async def _rcmd_tb(self, args):
        """Temporary ban sigue activo con el tiempo indicado."""
        # print(f"{self.name}_rcmd_tb", args)
        await self.handler.call_event("flood_ban_repeat", int(args[0]))

    async def _rcmd_logoutfirst(self, args):
        # print(f"{self.name}_rcmd_logoutfirst", args)
        pass

    async def _rcmd_logoutok(self, args, Force=False):
        """Me he desconectado, ahora usaré mi nombre de anon"""
        name = get_anon_name(str(self._correctiontime).split(".")[0][-4:], self._puid)
        self._user = User(name, isanon=True, ip=self._currentIP)
        # TODO fail aquiCLOSE
        await self.handler.call_event("logout", self._user, "?")

    async def _rcmd_updateprofile(self, args):
        """Cuando alguien actualiza su perfil en un chat"""
        user = User.get(args[0])
        user.profile = None
        await self.handler.call_event("profile_changes", user)

    async def _rcmd_reload_profile(self, args):
        user = User.get(args[0])
        user.profile = None
        await self.handler.call_event("profile_reload", user)
