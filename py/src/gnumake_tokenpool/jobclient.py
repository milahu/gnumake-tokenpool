import os, stat, select, signal, time, re
from datetime import datetime
from typing import List

__version__ = '0.0.1'

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

  def __init__(
      self,
      #makeflags: str or None = None, # TODO implement?
      #fds = List[int] or None = None, # TODO implement?
      named_pipes: List[str] or None = None,
      max_jobs: int or None = None,
      max_load: int or None = None,
      debug: bool or None = None,
      debug2: bool or None = None,
    ):

    self._fdRead = None
    self._fdReadDup = None
    self._fdWrite = None
    self._maxJobs = None
    self._maxLoad = None
    self._fileRead = None
    self._fileWrite = None

    self._debug = bool(os.environ.get("DEBUG_JOBCLIENT"))
    self._debug2 = bool(os.environ.get("DEBUG_JOBCLIENT_2")) # more verbose
    self._log = lambda *a, **k: print(f"jobclient.py {os.getpid()} {datetime.utcnow().strftime('%F %T.%f')}:", *a, **k)

    if debug != None:
      self._debug = debug

    if debug2 != None:
      self._debug2 = debug2

    makeFlags = os.environ.get("MAKEFLAGS", "")
    if makeFlags:
      self._debug and self._log(f"init: MAKEFLAGS: {makeFlags}")

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

    # test
    if False:
      if self._fdRead:
        print("test: using named pipes")
        pid = os.getpid()
        named_pipes = [
          f"/proc/{pid}/fd/{self._fdRead}",
          f"/proc/{pid}/fd/{self._fdWrite}",
        ]
        if (
          not os.path.exists(named_pipes[0]) or
          not os.path.exists(named_pipes[1])
        ):
          named_pipes = None

    if named_pipes:
      # useful to read/write pipes of other processes
      # example: f"/proc/{pid}/fd/3" and f"/proc/{pid}/fd/4"
      # note: when JobClient is destroyed
      # the file handles will be closed
      # but the pipes will stay open
      self._debug and self._log(f"init: using named pipes: {named_pipes}")
      self._fileRead = open(named_pipes[0], "r")
      self._fileWrite = open(named_pipes[1], "w")
      self._fdRead = self._fileRead.buffer.fileno()
      self._fdWrite = self._fileWrite.buffer.fileno()

    if max_jobs:
      self._debug and self._log(f"init: using max_jobs: {max_jobs}")
      self._maxJobs = max_jobs

    if max_load:
      self._debug and self._log(f"init: using max_load: {max_load}")
      self._maxLoad = max_load

    self._debug and self._log(f"init: fdRead = {self._fdRead}, fdWrite = {self._fdWrite}, " +
      f"maxJobs = {self._maxJobs}, maxLoad = {self._maxLoad}")

    if self._maxJobs == 1:
      self._debug and self._log(f"init failed: maxJobs == 1")
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
          self._debug and self._log(f"init failed: fd {self._fdRead} stat failed: {e}")
          raise NoJobServer()
        raise e # unexpected error

    # note: dont close the fds -> dont use open()

    self._debug and self._log("init: test fdRead stat")
    statsRead = get_stat(self._fdRead)

    self._debug and self._log("init: test fdRead pipe")
    if not is_pipe(statsRead):
      self._debug and self._log(f"init failed: fd {self._fdRead} is no pipe")
      raise NoJobServer()

    self._debug and self._log("init: test fdRead readable")
    if not check_access(statsRead, "r"):
      self._debug and self._log(f"init failed: fd {self._fdRead} is not readable")
      raise NoJobServer()

    self._debug and self._log("init: test fdWrite stat")
    statsWrite = get_stat(self._fdWrite)

    self._debug and self._log("init: test fdWrite pipe")
    if not is_pipe(statsWrite):
      self._debug and self._log(f"init failed: fd {self._fdWrite} is no pipe")
      raise NoJobServer()

    self._debug and self._log("init: test fdWrite writable")
    if not check_access(statsWrite, "w"):
      self._debug and self._log(f"init failed: fd {self._fdWrite} is not writable")
      raise NoJobServer()

    self._debug and self._log("init: test acquire ...")
    token = None
    try:
      token = self.acquire()
    except OSError as e:
      if e.errno == 9: # Bad file descriptor = pipe is closed
        self._debug and self._log(f"init failed: read error: {e}")
        raise NoJobServer()
      raise e
    if token == None:
      self._debug and self._log("init: test acquire failed. jobserver is full")
    else:
      self._debug and self._log("init: test acquire ok")
      self._debug and self._log("init: test release ...")
      self.release(token) # TODO handle errors
      self._debug and self._log("init: test release ok")
    self._debug and self._log("init: test ok")

  @property
  def maxJobs(self) -> int or None:
    return self._maxJobs

  @property
  def maxLoad(self) -> int or None:
    return self._maxLoad

  def acquire(self) -> int or None:
    # TODO? add timestamp to token so we can track it
    # http://make.mad-scientist.net/papers/jobserver-implementation/
    #buffer = os.read(self._fdRead, 1)
    # os.read blocks when fdRead is empty

    #os.close(self._fdRead) # test: read error: [Errno 9] Bad file descriptor
    #os.read(self._fdRead, 999) # test: fd is empty

    # is self._fdRead readable?
    # timeout 0 -> non-blocking
    rlist, _wlist, _xlist = select.select([self._fdRead], [], [], 0)
    if len(rlist) == 0:
      self._debug2 and self._log(f"acquire failed: fd is empty")
      return None

    #os.read(self._fdRead, 999) # test race condition: fd is empty 2

    # Handle potential race condition:
    #  - the above check succeeded, i.e. read() should not block
    #  - the character disappears before we call read()
    #
    # Create a duplicate of rfd_. The duplicate file descriptor dup_rfd_
    # can safely be closed by signal handlers without affecting rfd_.

    # 4.1. We use dup to create a duplicate of the read side of the jobserver pipe.
    # Note that we might already have a duplicate file descriptor
    # from a previous run: if so we don’t re-dup it.
    if not self._fdReadDup:
      self._fdReadDup = os.dup(self._fdRead)

    if not self._fdReadDup:
      self._debug and self._log(f"acquire: failed to duplicate fd")
      return None

    fdReadDupClose = lambda: os.close(self._fdReadDup)

    def read_timeout_handler(_signum, _frame):
      self._debug and self._log(f"acquire: read timeout")
      fdReadDupClose()

    # TODO remove SIGCHLD handler. too high-level. dont manage worker procs here.
    # 1. install a signal handler for SIGCHLD.
    # This signal handler will close the duplicate file descriptor self._fdReadDup.
    # SIGCHLD = one of our currently running jobs completed
    old_sigchld_handler = signal.signal(signal.SIGCHLD, read_timeout_handler)

    # 2. set the SA_RESTART flag on this signal handler
    # https://peps.python.org/pep-0475/
    # Python’s signal.signal() function clears the SA_RESTART flag
    # when setting the signal handler:
    # all system calls will probably fail with EINTR in Python.
    # https://stackoverflow.com/questions/5844364/linux-blocking-signals-to-python-init
    # 4.4. we disable SA_RESTART on the SIGCHLD signal.
    # This will allow the blocking read to be interrupted if a child process dies.
    signal.siginterrupt(signal.SIGCHLD, False) # Set SA_RESTART to limit EINTR occurrences.

    # TODO remove SIGALRM handler + signal.setitimer? not needed?
    # or keep it, to make sure we dont block?
    # same for signal SIGALRM
    # SIGALRM = timer has fired = read timeout
    old_sigalrm_handler = signal.signal(signal.SIGALRM, read_timeout_handler)
    signal.siginterrupt(signal.SIGALRM, False) # Set SA_RESTART to limit EINTR occurrences.

    read_timeout = 0.1
    #read_timeout = 0.5 # debug
    signal.setitimer(signal.ITIMER_REAL, read_timeout) # set timer for SIGALRM. unix only

    # 4.5. perform a blocking read of one byte
    # on the duplicate jobserver file descriptor
    self._debug and self._log(f"acquire: read with timeout {read_timeout} ...")
    buffer = b""
    try:
      buffer = os.read(self._fdReadDup, 1)
      #time.sleep(100); buffer = b"" # test. note: this is not killed by fdReadDupClose
    except BlockingIOError as e:
      if e.errno == 11: # Resource temporarily unavailable
        self._debug2 and self._log(f"acquire failed: fd is empty 2")
        return None # jobserver is full, try again later
      raise e # unexpected error
    except OSError as e:
      if e.errno == 9: # EBADF: Bad file descriptor = pipe is closed
        # self._fdReadDup was closed by fdReadDupClose
        self._debug and self._log(f"acquire: read failed: {e}")
        return None # jobserver is full, try again later
      raise e # unexpected error

    #fdReadDupClose() # keep self._fdReadDup for next call to acquire

    signal.setitimer(signal.ITIMER_REAL, 0) # clear timer. unix only

    # clear signal handlers
    signal.signal(signal.SIGCHLD, old_sigchld_handler)
    signal.signal(signal.SIGALRM, old_sigalrm_handler)

    #if len(buffer) == 0:
    #  return None
    assert len(buffer) == 1
    token = ord(buffer) # byte -> int8
    self._debug and self._log(f"acquire: read ok. token = {token}")
    return token

  def release(self, token: int = 43) -> None:
    # default token: int 43 = char +
    _validateToken(token)
    buffer = token.to_bytes(1, byteorder='big') # int8 -> byte
    while True:
      self._debug and self._log(f"release: write token {token} ...")
      try:
        bytesWritten = os.write(self._fdWrite, buffer)
        assert bytesWritten == 1
        self._debug and self._log(f"release: write ok")
        return
      except (OSError, select.error) as e:
        # handle EINTR = interrupt
        # FIXME be more specific?
        # https://stackoverflow.com/questions/15474072/how-to-catch-eintr-in-python
        write_retry = 0.1
        self._debug and self._log(f"release: write failed: {e} -> retry after {write_retry} seconds")
        time.sleep(write_retry) # throttle retry
