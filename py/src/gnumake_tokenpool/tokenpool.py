import sys, os, stat, select, signal, time, re

from contextlib import contextmanager
from datetime import datetime
from typing import List, Any, Iterator, Never

__version__ = '0.0.7'


class NoJobServer(Exception):
  pass


class InvalidToken(Exception):
  pass


class JobClient:
  "jobclient for the gnumake jobserver"

  def __init__(
      self,
      #makeflags: str or None = None, # TODO implement?
      #fds = List[int] or None = None, # TODO implement?
      named_pipes: List[str] | None = None,
      max_jobs: int | None = None,
      max_load: int | None = None,
      debug: bool | None = None,
      debug2: bool | None = None,
      use_cysignals: bool | None = None,
    ):

    self._fdRead: int | None = None
    self._fdReadDup: int | None = None
    self._fdWrite: int | None = None
    self._fifoPath = None
    self._fdFifo = None
    self._maxJobs = None
    self._maxLoad = None
    self._fileRead = None
    self._fileWrite = None

    self._debug = bool(os.environ.get("DEBUG_JOBCLIENT"))
    self._debug2 = bool(os.environ.get("DEBUG_JOBCLIENT_2")) # more verbose

    if debug is not None:
      self._debug = debug
    if debug2 is not None:
      self._debug2 = debug2

    self._log = self._get_log(self._debug)
    self._log2 = self._get_log(self._debug2)

    if use_cysignals is not False:
      try:
        from cysignals.pysignals import changesignal
      except ImportError:
        if use_cysignals:
          raise
      else:
        self._log("init: using cysignals.pysignals.changesignal")
        self._changesignal = changesignal   # type: ignore

    makeFlags = os.environ.get("MAKEFLAGS", "")
    if makeFlags:
      self._log(f"init: MAKEFLAGS: {makeFlags}")

    # parse

    for flag in re.split(r"\s+", makeFlags):
      m = re.fullmatch(r"--jobserver-(?:auth|fds)=(?:(\d+),(\d+)|fifo:(.*))", flag)
      if m:
        if m.group(1) and m.group(2):
          self._fdRead = int(m.group(1))
          self._fdWrite = int(m.group(2))
          self._log(f"init: found jobserver pipes: {self._fdRead},{self._fdWrite}")
        elif m.group(3):
          self._fifoPath = m.group(3)
          self._log(f"init: found jobserver fifo: {self._fifoPath}")
        continue
      m = re.fullmatch(r"-j(\d+)", flag)
      if m:
        self._maxJobs = int(m.group(1))
        continue
      m = re.fullmatch(r"-l(\d+)", flag)
      if m:
        self._maxLoad = int(m.group(1))
        continue

    # eval + validate

    if named_pipes:
      # read/write pipes of other process: /proc/{pid}/fd/{fdRead}
      self._log(f"init: using named pipes: {named_pipes}")
      self._fileRead = open(named_pipes[0], "r")
      self._fileWrite = open(named_pipes[1], "w")
      self._fdRead = self._fileRead.buffer.fileno()
      self._fdWrite = self._fileWrite.buffer.fileno()
    elif self._fifoPath:
      self._log(f"init: using jobserver fifo: {self._fifoPath}")
      self._fdFifo = os.open(self._fifoPath, os.O_RDWR)
      self._fdRead = self._fdFifo
      self._fdWrite = self._fdFifo

    if max_jobs:
      self._log(f"init: using max_jobs: {max_jobs}")
      self._maxJobs = max_jobs

    if max_load:
      self._log(f"init: using max_load: {max_load}")
      self._maxLoad = max_load

    self._log(f"init: fdRead = {self._fdRead}, fdWrite = {self._fdWrite}, " +
      f"maxJobs = {self._maxJobs}, maxLoad = {self._maxLoad}")

    if self._maxJobs == 1:
      self._log(f"init failed: maxJobs == 1")
      raise NoJobServer()

    if self._fdRead is None or self._fdWrite is None:
      self._log(f"init failed: no fds")
      raise NoJobServer()

    self._log("init: test fdRead stat")
    statsRead = self._get_stat(self._fdRead)

    self._log("init: test fdRead pipe")
    if not self._is_pipe(statsRead):
      self._log(f"init failed: fd {self._fdRead} is no pipe")
      raise NoJobServer()

    self._log("init: test fdRead readable")
    if not self._check_access(statsRead, "r"):
      self._log(f"init failed: fd {self._fdRead} is not readable")
      raise NoJobServer()

    self._log("init: test fdWrite stat")
    statsWrite = self._get_stat(self._fdWrite)

    self._log("init: test fdWrite pipe")
    if not self._is_pipe(statsWrite):
      self._log(f"init failed: fd {self._fdWrite} is no pipe")
      raise NoJobServer()

    self._log("init: test fdWrite writable")
    if not self._check_access(statsWrite, "w"):
      self._log(f"init failed: fd {self._fdWrite} is not writable")
      raise NoJobServer()

    self._log("init: test acquire ...")
    token = None
    try:
      token = self.acquire()
    except OSError as e:
      if e.errno == 9: # Bad file descriptor = pipe is closed
        self._log(f"init failed: read error: {e}")
        raise NoJobServer()
      raise e
    if token is None:
      self._log("init: test acquire failed. jobserver is full")
    else:
      self._log("init: test acquire ok")
      self._log("init: test release ...")
      self.release(token) # TODO handle errors
      self._log("init: test release ok")
    self._log("init: test ok")


  def __del__(self) -> None:
    if self._fdFifo:
      os.close(self._fdFifo)


  @property
  def maxJobs(self) -> int | None:
    return self._maxJobs


  @property
  def maxLoad(self) -> int | None:
    return self._maxLoad


  def acquire(self) -> int | None:
    # http://make.mad-scientist.net/papers/jobserver-implementation/

    # check if fdRead is readable
    rlist, _wlist, _xlist = select.select([self._fdRead], [], [], 0)
    if len(rlist) == 0:
      self._log2(f"acquire failed: fd is empty")
      return None

    # handle race condition:
    # between select and read, another process can read from the pipe.
    # when the pipe is empty, read can block forever.
    # by closing fdReadDup, we interrupt read
    if self._fdRead and not self._fdReadDup:
      self._fdReadDup = os.dup(self._fdRead)

    if not self._fdReadDup:
      self._log(f"acquire: failed to duplicate fd")
      return None

    def read_timeout_handler(_signum: int, _frame: Any) -> None:
      self._log(f"acquire: read timeout")
      assert self._fdReadDup
      os.close(self._fdReadDup)

    # SIGALRM = timer has fired = read timeout
    with self._changesignal(signal.SIGALRM, read_timeout_handler):
      try:
        # Set SA_RESTART to limit EINTR occurrences.
        # by default, signal.signal clears the SA_RESTART flag.
        # TODO is this necessary?
        signal.siginterrupt(signal.SIGALRM, False)

        read_timeout = 0.1
        signal.setitimer(signal.ITIMER_REAL, read_timeout) # set timer for SIGALRM. unix only

        # blocking read
        self._log(f"acquire: read with timeout {read_timeout} ...")
        buffer = b""
        try:
          buffer = os.read(self._fdReadDup, 1)
        except BlockingIOError as e:
          if e.errno == 11: # Resource temporarily unavailable
            self._log2(f"acquire failed: fd is empty 2")
            return None # jobserver is full, try again later
          raise e # unexpected error
        except OSError as e:
          if e.errno == 9: # EBADF: Bad file descriptor = pipe is closed
            self._log(f"acquire: read failed: {e}")
            return None # jobserver is full, try again later
          raise e # unexpected error
      finally:
        signal.setitimer(signal.ITIMER_REAL, 0) # clear timer. unix only

    #if len(buffer) == 0:
    #  return None
    assert len(buffer) == 1

    token = ord(buffer) # byte -> int8
    self._log(f"acquire: read ok. token = {token}")
    return token


  def release(self, token: int = 43) -> None:
    # default token: int 43 = char +
    assert self._fdWrite
    self._validateToken(token)
    buffer = token.to_bytes(1, byteorder='big') # int8 -> byte
    while True: # retry loop
      self._log(f"release: write token {token} ...")
      try:
        bytesWritten = os.write(self._fdWrite, buffer)
        assert bytesWritten == 1
        self._log(f"release: write ok")
        return
      except (OSError, select.error) as e:
        # handle EINTR = interrupt
        # FIXME be more specific?
        # https://stackoverflow.com/questions/15474072/how-to-catch-eintr-in-python
        write_retry = 0.1
        self._log(f"release: write failed: {e} -> retry after {write_retry} seconds")
        time.sleep(write_retry) # throttle retry


  def _validateToken(self, token: int) -> None:
    if type(token) != int or token < 0 or 255 < token:
      raise InvalidToken()


  def _get_log(self, debug: bool) -> Any:
    if debug:
      def _log(*a: Any, **k: Any) -> None:
        k['file'] = sys.stderr
        print(f"debug jobclient.py {os.getpid()} {datetime.utcnow().strftime('%F %T.%f')[:-3]}:", *a, **k)
      return _log
    else:
      def _log(*a: Any, **k: Any) -> None:
        pass
      return _log


  def _check_access(self, s: os.stat_result, check: str = "r") -> int:
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


  def _is_pipe(self, s: os.stat_result) -> bool:
    if not stat.S_ISFIFO(s.st_mode):
      return False
    return True


  def _get_stat(self, fd: int) -> os.stat_result:
    try:
      return os.stat(fd)
    except OSError as e:
      if e.errno == 9: # Bad file descriptor = pipe is closed
        self._log(f"init failed: fd {fd} stat failed: {e}")
        raise NoJobServer()
      raise e # unexpected error

  @staticmethod
  @contextmanager
  def _changesignal(sig: int, action: Any) -> Iterator[None]:
    old_sig_handler = signal.signal(sig, action)
    try:
      yield
    finally:
      # clear signal handler
      signal.signal(sig, old_sig_handler)
