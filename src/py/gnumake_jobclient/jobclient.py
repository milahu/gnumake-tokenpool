import os, stat, re
from datetime import datetime

__version__ = '0.0.1'

_debug = bool(os.environ.get("DEBUG_JOBCLIENT"))

_log = lambda *a, **k: print(f"jobclient.py {os.getpid()} {datetime.utcnow().strftime('%F %T.%f')[:-3]}:", *a, **k)

def _validateToken(token: int) -> None:
  if type(token) != int or token < 0 or 255 < token:
    raise InvalidToken()

class NoJobServer(Exception):
  pass

class InvalidToken(Exception):
  pass

class JobClient:
  """
  jobclient for the gnumake jobserver

  based on https://github.com/olsner/jobClient/blob/master/jobClient.h
  license: MIT
  copyright: (c) 2022 Milan Hauth <milahu@gmail.com>

  NOTE n-1 error
  make counts this jobclient as one job
  so we dont need a token for the first worker (serial processing).
  we only need tokens for 2 or more workers (parallel processing).

  NOTE maxJobs
  maxJobs is the global limit for all make jobs,
  so this jobclient can get less than (maxJobs-1) tokens.
  to find the maximum number of free tokens,
  you must acquire them all.
  """

  def __init__(self):
    makeFlags = os.environ.get("MAKEFLAGS")
    if not makeFlags:
      _debug and _log(f"init failed: MAKEFLAGS is empty")
      raise NoJobServer()
    _debug and _log(f"init: MAKEFLAGS: {makeFlags}")

    self._fdRead = None
    self._fdWrite = None
    self._maxJobs = None
    self._maxLoad = None
    for flag in re.split(r"\s+", makeFlags):
      m = (
        re.fullmatch(r"--jobserver-auth=(\d+),(\d+)", flag) or
        re.fullmatch(r"--jobserver-fds=(\d+),(\d+)", flag)
      )
      if m:
        self._fdRead = int(m.group(1))
        self._fdWrite = int(m.group(2))
        continue
      m = re.fullmatch(r"-j(\d+)", flag)
      if m:
        self._maxJobs = int(m.group(1))
        continue
      m = re.fullmatch(r"-l(\d+)", flag)
      if m:
        self._maxLoad = int(m.group(1))
        continue
    _debug and _log(f"init: fdRead = {self._fdRead}, fdWrite = {self._fdWrite}, " +
      f"maxJobs = {self._maxJobs}, maxLoad = {self._maxLoad}")

    if self._maxJobs == 1:
      _debug and _log(f"init failed: maxJobs == 1")
      raise NoJobServer()
    if self._fdRead == None:
      raise NoJobServer()

    # TODO check fds
    # examples:
    # MAKEFLAGS="--jobserver-auth=3,4 -l32"
    # ls -nlv /proc/self/fd/
    #
    # jobserver on:
    # lr-x------ 1 1000 100 64 Jun 27 14:29 3 -> pipe:[102600042]
    # l-wx------ 1 1000 100 64 Jun 27 14:29 4 -> pipe:[102600042]
    #
    # jobserver off:
    # lr-x------ 1 1000 100 64 Jun 27 14:29 3 -> /proc/2370722/fd
    #
    # conditions for jobserver on:
    # * maxJobs is undefined
    # * fds 3 and 4 are connected
    # * fd 3 is readable
    # * fd 4 is writable
    # * fds 3 and 4 are pipes
    # * fds 3 and 4 are pipes with the same ID (?)

    def check_access(s, check="r"):
      #import stat
      #s = os.stat(path)
      u = os.geteuid()
      g = os.getegid()
      m = s.st_mode
      if check == "r":
        return (
          ((s[stat.ST_UID] == u) and (m & stat.S_IRUSR)) or
          ((s[stat.ST_GID] == g) and (m & stat.S_IRGRP)) or
          (m & stat.S_IROTH)
        )
      if check == "w":
        return (
          ((s[stat.ST_UID] == u) and (m & stat.S_IWUSR)) or
          ((s[stat.ST_GID] == g) and (m & stat.S_IWGRP)) or
          (m & stat.S_IWOTH)
        )
      raise ValueError("check must be r or w")

    def is_pipe(s):
      if not stat.S_ISFIFO(s.st_mode):
        return False
      return True

    def get_stat(fd):
      try:
        return os.stat(self._fdRead)
      except OSError as e:
        if e.errno == 9: # Bad file descriptor = pipe is closed
          _debug and _log(f"init failed: fd {self._fdRead} stat failed: {e}")
          raise NoJobServer()
        raise e # unexpected error

    # note: dont close the fds -> dont use open()

    _debug and _log("init: test fdRead stat")
    statsRead = get_stat(self._fdRead)

    _debug and _log("init: test fdRead pipe")
    if not is_pipe(statsRead):
      _debug and _log(f"init failed: fd {self._fdRead} is no pipe")
      raise NoJobServer()

    _debug and _log("init: test fdRead readable")
    if not check_access(statsRead, "r"):
      _debug and _log(f"init failed: fd {self._fdRead} is not readable")
      raise NoJobServer()

    _debug and _log("init: test fdWrite stat")
    statsWrite = get_stat(self._fdWrite)

    _debug and _log("init: test fdWrite pipe")
    if not is_pipe(statsWrite):
      _debug and _log(f"init failed: fd {self._fdWrite} is no pipe")
      raise NoJobServer()

    _debug and _log("init: test fdWrite writable")
    if not check_access(statsWrite, "w"):
      _debug and _log(f"init failed: fd {self._fdWrite} is not writable")
      raise NoJobServer()

    _debug and _log("init: test acquire")
    try:
      token = self.acquire()
    except OSError as e:
      if e.errno == 9: # Bad file descriptor = pipe is closed
        _debug and _log(f"init failed: read error: {e}")
        raise NoJobServer()
      raise e
    _debug and _log("init: test release")
    self.release(token) # TODO handle errors
    _debug and _log("init: test ok")

  @property
  def maxJobs(self) -> int or None:
    return self._maxJobs

  @property
  def maxLoad(self) -> int or None:
    return self._maxLoad

  def acquire(self) -> int or None:
    try:
      buffer = os.read(self._fdRead, 1)
    except BlockingIOError as e:
      if e.errno == 11: # Resource temporarily unavailable
        _debug and _log(f"acquire: token = None")
        return None # jobserver is full, try again later
      raise e

    assert len(buffer) == 1
    token = ord(buffer) # byte -> int8
    _debug and _log(f"acquire: token = {token}")
    return token

  def release(self, token: int) -> None:
    _validateToken(token)
    _debug and _log(f"release: token = {token}")
    buffer = token.to_bytes(1, byteorder='big') # int8 -> byte
    bytesWritten = os.write(self._fdWrite, buffer)
    assert bytesWritten == 1
