import os, re

__version__ = '0.0.1'

_debug = lambda *a, **k: print("JobClient:", *a, **k) if os.environ.get("DEBUG_JOBCLIENT") else lambda *a, **k: None

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
      raise NoJobServer()
    _debug(f"makeFlags = {repr(makeFlags)}")

    self._fdRead = None
    self._fdWrite = None
    self._maxJobs = None
    self._maxLoad = None
    for flag in re.split(r"\s+", makeFlags):
      m = re.fullmatch(r"--jobserver-auth=(\d+),(\d+)", flag)
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
    _debug(f"_fdRead = {self._fdRead}, _fdWrite = {self._fdWrite}, " +
      f"maxJobs = {self._maxJobs}, maxLoad = {self._maxLoad}")

    if self._maxJobs == 1:
      _debug(f"maxJobs == 1 -> jobserver off")
      raise NoJobServer()
    if self._fdRead == None:
      raise NoJobServer()

    _debug("init: test acquire")
    try:
      token = self.acquire()
    except OSError as e:
      if e.errno == 9:
        _debug(f"read error -> jobserver off")
        raise NoJobServer()
      raise e
    _debug("init: test release")
    self.release(token)
    _debug("init: test ok")

  @property
  def maxJobs(self) -> int:
    return self._maxJobs

  @property
  def maxLoad(self) -> int or None:
    return self._maxLoad

  def acquire(self) -> int or None:
    try:
      buffer = os.read(self._fdRead, 1)
    except BlockingIOError as e:
      if e.errno == 11: # Resource temporarily unavailable
        _debug(f"acquire: token = None")
        return None # jobserver is full, try again later
      raise e

    assert len(buffer) == 1
    token = ord(buffer) # byte -> int8
    _debug(f"acquire: token = {token}")
    return token

  def release(self, token: int) -> None:
    _validateToken(token)
    _debug(f"release: token = {token}")
    buffer = token.to_bytes(1, byteorder='big') # int8 -> byte
    bytesWritten = os.write(self._fdWrite, buffer)
    assert bytesWritten == 1
