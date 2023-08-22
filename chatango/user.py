import enum
import json, urllib
from typing import Any, Optional
import re
import time
import datetime
from collections import deque

from .utils import Styles, make_requests, public_attributes


class ModeratorFlags(enum.IntFlag):
    DELETED = 1 << 0
    EDIT_MODS = 1 << 1
    EDIT_MOD_VISIBILITY = 1 << 2
    EDIT_BW = 1 << 3
    EDIT_RESTRICTIONS = 1 << 4
    EDIT_GROUP = 1 << 5
    SEE_COUNTER = 1 << 6
    SEE_MOD_CHANNEL = 1 << 7
    SEE_MOD_ACTIONS = 1 << 8
    EDIT_NLP = 1 << 9
    EDIT_GP_ANNC = 1 << 10
    EDIT_ADMINS = 1 << 11
    EDIT_SUPERMODS = 1 << 12
    NO_SENDING_LIMITATIONS = 1 << 13
    SEE_IPS = 1 << 14
    CLOSE_GROUP = 1 << 15
    CAN_BROADCAST = 1 << 16
    MOD_ICON_VISIBLE = 1 << 17
    IS_STAFF = 1 << 18
    STAFF_ICON_VISIBLE = 1 << 19


AdminFlags = (
    ModeratorFlags.EDIT_MODS
    | ModeratorFlags.EDIT_RESTRICTIONS
    | ModeratorFlags.EDIT_GROUP
    | ModeratorFlags.EDIT_GP_ANNC
)


class User:
    """Chatango user object."""

    _users = {}

    def __new__(cls, name, **kwargs):
        key = name.lower()
        if key in cls._users:
            for attr, val in kwargs.items():
                if attr == "ip" and not val:
                    continue  # only valid ips
                setattr(cls._users[key], "_" + attr, val)
            return cls._users[key]
        self = super().__new__(cls)
        self._styles = Styles()
        cls._users[key] = self
        self._name = name.lower()
        self._ip = None
        self._flags = 0
        self._history = deque(maxlen=5)
        self._isanon = False
        self._sids = dict()
        self._showname = name
        self._is_premium = None
        self._puid = str()
        self._client = None
        self._last_time = None
        self._blend_name = None
        for attr, val in kwargs.items():
            setattr(self, "_" + attr, val)
        return self

    @classmethod
    def get(cls, name):
        """Get user object(s) by name."""
        return cls._users.get(name) or User(name)

    def __dir__(self):
        return public_attributes(self)

    def __repr__(self) -> str:
        return "<User: %s>" % self.showname

    @property
    def age(self):
        """User age."""
        return self.styles.profile["about"].get("age")

    @property
    def last_change(self):
        """Last change made to user's profile."""
        return self.styles.profile["about"].get("last_change")

    @property
    def gender(self):
        """User gender."""
        return self.styles.profile["about"].get("gender")

    @property
    def location(self):
        """User location."""
        return self.styles.profile["about"].get("location")

    @property
    def get_user_dir(self):
        if not self.isanon:
            return "/%s/%s/" % ("/".join((self.name * 2)[:2]), self.name)

    @property
    def fullpic(self):
        if not self.isanon:
            return f"{self._fp}{self.get_user_dir}full.jpg"
        return False

    @property
    def last_time(self):
        return self._last_time

    @property
    def msgbg(self):
        if not self.isanon:
            return f"{self._fp}{self.get_user_dir}msgbg.jpg"
        return False

    @property
    def styles(self):
        return self.user_styles

    @property
    def thumb(self):
        if not self.isanon:
            return f"{self._fp}{self.get_user_dir}thumb.jpg"
        return False

    @property
    def _fp(self):
        return "http://fp.chatango.com/profileimg"

    @property
    def _ust(self):
        return "http://ust.chatango.com/profileimg"

    @property
    def name(self):
        return self._name

    @property
    def user_styles(self):
        return self._styles

    @property
    def blend_name(self):
        return self._blend_name

    @property
    def puid(self):
        return self._puid

    @property
    def is_premium_user(self):
        return self._is_premium

    @property
    def showname(self):
        return self._showname

    @property
    def _links(self):
        return [
            ["msgstyles", f"{self._ust}{self.get_user_dir}msgstyles.json"],
            ["msgbg", f"{self._ust}{self.get_user_dir}msgbg.xml"],
            ["mod1", f"{self._ust}{self.get_user_dir}mod1.xml"],
            ["mod2", f"{self._ust}{self.get_user_dir}mod2.xml"],
        ]

    @property
    def isanon(self):
        return self._isanon

    def setName(self, val):
        self._showname = val
        self._name = val.lower()

    def del_profile(self):
        if self.user_styles.profile:
            del self.user_styles.profile
            self.user_styles.profile.update(dict(about={}, full={}))

    def addSessionId(self, room, sid):
        if room not in self._sids:
            self._sids[room] = set()
        self._sids[room].add(sid)

    def getSessionIds(self, room=None):
        if room:
            return self._sids.get(room, set())
        else:
            return set.union(*self._sids.values())

    def removeSessionId(self, room, sid):
        if room in self._sids:
            if not sid:
                self._sids[room].clear()
            elif sid in self._sids[room]:
                self._sids[room].remove(sid)
            if len(self._sids[room]) == 0:
                del self._sids[room]

    async def get_styles(self):
        position_dict = {
            "tl": "top left",
            "tr": "top right",
            "bl": "bottom left",
            "br": "bottom right",
        }
        if not self.isanon:
            tasks = await make_requests(self._links[:2])
            msg_styles = tasks["msgstyles"].result()
            msg_bg = tasks["msgbg"].result()
            if msg_bg:
                bg = msg_bg.replace('<?xml version="1.0" ?>', "")
                bg_dict = dict(url.replace('"', "").split("=") for url in re.findall('(\w+=".*?")', bg))
                self.user_styles.bgstyle.update(bg_dict)
                self.user_styles.bgstyle["align"] = position_dict.get(self.user_styles.bgstyle["align"])
            if msg_styles:
                try:
                    styles = json.loads(msg_styles)
                    self.user_styles.set_name_color(styles["nameColor"])
                    self.user_styles.set_font_face(int(styles["fontFamily"]))
                    self.user_styles.set_font_size(int(styles["fontSize"]))
                    self.user_styles.set_font_color(styles["textColor"])
                    self.user_styles.set_use_background(int(styles["usebackground"]))
                except json.JSONDecodeError:
                    pass

    def set_premium_user(self, premium):
        self._is_premium = premium

    async def get_main_profile(self):
        """Fetch user profile."""
        if not self.isanon:
            tasks = await make_requests(self._links[2:])
            items = tasks.get("mod1").result()
            if items is not None:
                about = items.replace('<?xml version="1.0" ?>', "")
                gender_start = about.find("<s>")
                gender_end = about.find("</s>", gender_start)
                gender = about[gender_start + 3 : gender_end] if gender_start != -1 else "?"
                self.user_styles.profile["about"]["gender"] = gender

                location_start = about.find("<l")
                location_end = about.find("</l>", location_start)
                location = about[location_start + 2 : location_end] if location_start != -1 else ""
                self.user_styles.profile["about"]["location"] = location

                last_change_start = about.find("<b>")
                last_change_end = about.find("</b>", last_change_start)
                last_change = about[last_change_start + 3 : last_change_end] if last_change_start != -1 else ""
                self.user_styles.profile["about"]["last_change"] = last_change

                if last_change:
                    age = abs(datetime.datetime.now().year - int(last_change.split("-")[0]))
                    self.user_styles.profile["about"]["age"] = age
                body_start = about.find("<body>")
                body_end = about.find("</body>", body_start)
                body = about[body_start + 6 : body_end] if body_start != -1 else ""
                self.user_styles.profile["about"].update({"body": urllib.parse.unquote(body)})

            try:
                full_prof = tasks.get("mod2").result()
                if full_prof is not None and str(full_prof)[:5] == "<?xml":
                    full_prof_start = full_prof.find("<body")
                    full_prof_end = full_prof.find("</body>", full_prof_start)
                    full_prof_body = (
                        full_prof[full_prof_start + len("<body") : full_prof_end] if full_prof_start != -1 else ""
                    )
                    self.user_styles.profile["full"] = full_prof_body
            except (AttributeError, KeyError):
                pass


class Friend:
    """Friend user object."""

    _FRIENDS = dict()

    def __init__(self, user: User, client: Optional[Any] = None):
        self.user = user
        self.name = user.name
        self._client = client

        self._status = None
        self._idle = None
        self._last_active = None

    def __repr__(self):
        if self.is_friend():
            return f"<Friend {self.name}>"
        return f"<User: {self.name}>"

    def __str__(self):
        return self.name

    @classmethod
    def get(cls, name):
        """Get friend user by username."""
        return cls._FRIENDS.get(name) or Friend(name)

    def __dir__(self):
        return [x for x in set(list(self.__dict__.keys()) + list(dir(type(self)))) if x[0] != "_"]

    @property
    def showname(self):
        """User showname."""
        return self.user.showname

    @property
    def client(self):
        """User client."""
        return self._client

    @property
    def status(self):
        """User status."""
        return self._status

    @property
    def last_active(self):
        """Last time user was active."""
        return self._last_active

    @property
    def idle(self):
        """Check if user is idle."""
        return self._idle

    def is_friend(self):
        """Check if user is friend."""
        if self.client and not self.user.isanon:
            if self.name in self.client.friends:
                return True
            return False
        return None

    async def send_friend_request(self):
        """Send a friend request."""
        if self.client and self.is_friend() is False:
            return await self.client.addfriend(self.name)

    async def unfriend(self):
        """Delete friend."""
        if self.client and self.is_friend() is True:
            return await self.client.unfriend(self.name)

    @property
    def is_online(self):
        """Check if user is online."""
        return self.status == "online"

    @property
    def is_offline(self):
        """Check if user is offline."""
        return self.status in ["offline", "app"]

    @property
    def is_on_app(self):
        """Check if user is using Android app client."""
        return self.status == "app"

    async def reply(self, message):
        """Reply to user."""
        if self.client:
            await self.client.send_message(self.name, message)

    def _check_status(self, _time=None, _idle=None, idle_time=None):
        if _time is None and idle_time is None:
            self._last_active = None
            return
        if _idle is not None:
            self._idle = _idle
        if self.status == "online" and int(idle_time) >= 1:
            self._last_active = time.time() - (int(idle_time) * 60)
            self._idle = True
        else:
            self._last_active = float(_time)
