# pipe one byte from stdin to stdout

# raise OSError("test: asdf") # test exception
# import sys; sys.exit(123) # test error
# import time; time.sleep(999) # test timeout

import os

try:
  _bytes = os.read(0, 1)
except BlockingIOError as e:
  if e.errno == 11:
    # Resource temporarily unavailable
    import sys
    sys.exit(e.errno)
  raise e
except OSError as e:
  if e.errno == 9:
    # Bad file descriptor = pipe is closed
    import sys
    sys.exit(e.errno)
  raise e

os.write(1, _bytes)
