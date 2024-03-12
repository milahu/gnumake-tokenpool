import sys, os, stat, select, time, re, subprocess, _compat_pickle

from datetime import datetime
from typing import List, Any, Iterator, Never

__version__ = '0.0.7'


class NoJobServer(Exception):
  pass


class InvalidToken(Exception):
  pass


def _parse_exception(_bytes):
  print("_bytes", repr(_bytes))
  e_msg = _bytes.strip()
  e_trace = b""
  e_name = b""
  parts = e_msg.rsplit(b"\n", 1)
  print("parts", repr(parts))
  if len(parts) == 2:
    e_trace, e_msg = parts
  parts = e_msg.split(b": ", 1)
  print("parts", repr(parts))
  if len(parts) == 2:
    e_name, e_msg = parts
  e_class = Exception
  if re.fullmatch(rb"[A-Z][A-Za-z]+", e_name):
    # eval is evil...
    # e_class_2 = eval(e_name)
    # if issubclass(e_class_2, BaseException):
    #   e_class = e_class_2
    # also check e_name versus list of built-in exceptions
    # https://docs.python.org/3/library/exceptions.html
    e_name = e_name.decode("ascii")
    if (
      e_name in _compat_pickle.PYTHON2_EXCEPTIONS or
      e_name in _compat_pickle.PYTHON3_OSERROR_EXCEPTIONS or
      e_name in _compat_pickle.PYTHON3_IMPORTERROR_EXCEPTIONS or
      e_name in _compat_pickle.MULTIPROCESSING_EXCEPTIONS or
      e_name == "OSError" or
      e_name == "ImportError"
    ):
      e_class = eval(e_name)
  try:
    e_msg = e_msg.decode("utf8")
  except UnicodeDecodeError:
    pass
  try:
    e_trace = e_trace.decode("utf8")
  except UnicodeDecodeError:
    pass
  try:
    text = _bytes.decode("utf8").strip()
  except UnicodeDecodeError:
    text = repr(stderr)
  return e_class, e_msg + "\n\nexception parsed from inner exception:\n\n" + text


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
    ):

    self._fdRead: int | None = None
    self._fdWrite: int | None = None
    self._fifoPath = None
    self._fdFifo = None
    self._maxJobs = None
    self._maxLoad = None
    self._fileRead = None
    self._fileWrite = None

    self._read_byte_py_path = os.path.dirname(__file__) + "/read_byte.py"

    self._debug = bool(os.environ.get("DEBUG_JOBCLIENT"))
    self._debug2 = bool(os.environ.get("DEBUG_JOBCLIENT_2")) # more verbose

    if debug is not None:
      self._debug = debug
    if debug2 is not None:
      self._debug2 = debug2

    self._log = self._get_log(self._debug)
    self._log2 = self._get_log(self._debug2)

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


  def acquire(
      self,
      # a successful read takes about 0.1 to 0.2 seconds
      timeout=0.5,
    ) -> int | None:
    # http://make.mad-scientist.net/papers/jobserver-implementation/

    # check if fdRead is readable
    rlist, _wlist, _xlist = select.select([self._fdRead], [], [], 0)
    if len(rlist) == 0:
      self._log2(f"acquire failed: fd is empty")
      return None

    args = [
      sys.executable, # python
      self._read_byte_py_path,
    ]

    self._log(f"acquire: read with timeout {timeout} ...")
    buffer = b""
    t1 = time.time()
    try:
      proc = subprocess.run(
        args,
        capture_output=True,
        timeout=timeout,
        stdin=self._fdRead,
        #check=True, # raise CalledProcessError
      )
      buffer = proc.stdout
      t2 = time.time()
      self._log(f"acquire: read done after {t2 - t1} seconds")
    except subprocess.TimeoutExpired:
      self._log(f"acquire: read timeout")
      return None
      #raise TimeoutError
    #except subprocess.CalledProcessError as proc:
    if proc.returncode != 0:
      if proc.returncode == 11: # Resource temporarily unavailable
        self._log2(f"acquire failed: fd is empty 2")
        return None # jobserver is full, try again later
      if proc.returncode == 9: # EBADF: Bad file descriptor = pipe is closed
        #self._log(f"acquire: read failed: {e}")
        self._log(f"acquire: read failed: Bad file descriptor")
        return None # jobserver is full, try again later
      if proc.returncode == 1:
        e_class, e_msg = _parse_exception(proc.stderr)
        raise e_class(e_msg) # unexpected error
      e_msg = f"read_byte_py process returned {proc.returncode}. stdout={repr(proc.stdout)}. stderr={repr(proc.stderr)}"
      raise Exception(e_msg) # unexpected error

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
