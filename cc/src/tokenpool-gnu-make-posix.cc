// Copyright 2016-2018 Google Inc. All Rights Reserved.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

#include "tokenpool-gnu-make-posix.h"

#include <errno.h>
#include <fcntl.h>
#include <poll.h>
#include <unistd.h>
#include <sys/time.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

GNUmakeTokenPoolPosix::GNUmakeTokenPoolPosix() : rfd_(-1), wfd_(-1), restore_(false) {
}

GNUmakeTokenPoolPosix::~GNUmakeTokenPoolPosix() {
  Clear();
  if (restore_)
    sigaction(SIGALRM, &old_act_, NULL);
}

bool GNUmakeTokenPoolPosix::CheckFd(int fd) {
  if (fd < 0)
    return false;
  int ret = fcntl(fd, F_GETFD);
  return ret >= 0;
}

int GNUmakeTokenPoolPosix::dup_rfd_ = -1;

void GNUmakeTokenPoolPosix::CloseDupRfd(int signum) {
  close(dup_rfd_);
  dup_rfd_ = -1;
}

bool GNUmakeTokenPoolPosix::SetAlarmHandler() {
  struct sigaction act;
  memset(&act, 0, sizeof(act));
  act.sa_handler = CloseDupRfd;
  if (sigaction(SIGALRM, &act, &old_act_) < 0) {
    perror("sigaction:");
    return false;
  }
  restore_ = true;
  return true;
}

bool GNUmakeTokenPoolPosix::ParseAuth(const char* jobserver) {
  int rfd = -1;
  int wfd = -1;
  if ((sscanf(jobserver, "%*[^=]=%d,%d", &rfd, &wfd) == 2) &&
      CheckFd(rfd) &&
      CheckFd(wfd) &&
      SetAlarmHandler()) {
    rfd_ = rfd;
    wfd_ = wfd;
    printf("GNUmakeTokenPoolPosix::ParseAuth: parsed fds %i, %i\n", rfd_, wfd_);
    return true;
  }
  printf("GNUmakeTokenPoolPosix::ParseAuth: failed to parse fds from jobserver arg: %s\n", jobserver);

  return false;
}

bool GNUmakeTokenPoolPosix::CreatePool(int parallelism, std::string* auth) {
  // create jobserver pipe
  int fds[2];
  if (pipe(fds) < 0)
    return false;

  // add N tokens to pipe
  const char token = '+'; // see make/posixos.c
  while (parallelism--) {
    if (write(fds[1], &token, 1) < 1) {
      close(fds[1]);
      close(fds[0]);
      return false;
    }
  }

  // initialize file descriptors for this instance
  rfd_ = fds[0];
  wfd_ = fds[1];

  // generate auth parameter for child processes
  char buffer[32];
  snprintf(buffer, sizeof(buffer), "%d,%d", rfd_, wfd_);
  *auth = buffer;

  return true;
}

int GNUmakeTokenPoolPosix::AcquireToken() {
  //printf("GNUmakeTokenPoolPosix::AcquireToken: rfd_ = %i\n", rfd_);
  // Please read
  //
  //   http://make.mad-scientist.net/papers/jobserver-implementation/
  //
  // for the reasoning behind the following code.
  //
  // Try to read one character from the pipe. Returns true on success.
  //
  // First check if read() would succeed without blocking.
#ifdef USE_PPOLL
  //printf("GNUmakeTokenPoolPosix::AcquireToken USE_PPOLL=1\n");
  pollfd pollfds[] = {{rfd_, POLLIN, 0}};
  int ret = poll(pollfds, 1, 0);
#else
  //printf("GNUmakeTokenPoolPosix::AcquireToken USE_PPOLL=0\n");
  fd_set set;
  struct timeval timeout = { 0, 0 };
  FD_ZERO(&set);
  FD_SET(rfd_, &set);
  int ret = select(rfd_ + 1, &set, NULL, NULL, &timeout);
#endif
  if (ret > 0) {
    // Handle potential race condition:
    //  - the above check succeeded, i.e. read() should not block
    //  - the character disappears before we call read()
    //
    // Create a duplicate of rfd_. The duplicate file descriptor dup_rfd_
    // can safely be closed by signal handlers without affecting rfd_.
    dup_rfd_ = dup(rfd_);

    if (dup_rfd_ != -1) {
      struct sigaction act, old_act;
      int ret = 0;

      // Temporarily replace SIGCHLD handler with our own
      memset(&act, 0, sizeof(act));
      act.sa_handler = CloseDupRfd;
      char buf;
      if (sigaction(SIGCHLD, &act, &old_act) == 0) {
        struct itimerval timeout;

        // install a 100ms timeout that generates SIGALARM on expiration
        memset(&timeout, 0, sizeof(timeout));
        timeout.it_value.tv_usec = 100 * 1000; // [ms] -> [usec]
        if (setitimer(ITIMER_REAL, &timeout, NULL) == 0) {
          // Now try to read() from dup_rfd_. Return values from read():
          //
          // 1. token read                               ->  1
          // 2. pipe closed                              ->  0
          // 3. alarm expires                            -> -1 (EINTR)
          // 4. child exits                              -> -1 (EINTR)
          // 5. alarm expired before entering read()     -> -1 (EBADF)
          // 6. child exited before entering read()      -> -1 (EBADF)
          // 7. child exited before handler is installed -> go to 1 - 3
          ret = read(dup_rfd_, &buf, 1);

          // disarm timer
          memset(&timeout, 0, sizeof(timeout));
          setitimer(ITIMER_REAL, &timeout, NULL);
        }

        sigaction(SIGCHLD, &old_act, NULL);
      }

      CloseDupRfd(0);

      // Case 1 from above list
      if (ret > 0)
        return (int) buf; // 0 <= token <= 255
    }
  }

  // read() would block, i.e. no token available,
  // cases 2-6 from above list or
  // select() / poll() / dup() / sigaction() / setitimer() failed
  return -1; // error: no token
}

bool GNUmakeTokenPoolPosix::ReleaseToken(int token = 43) {
  // default token is char + == int 43
  //const char buf = '+';
  char buf = (char) token;
  printf("GNUmakeTokenPoolPosix::ReleaseToken: token = int %i = char %c\n", token, buf);
  while (1) {
    int ret = write(wfd_, &buf, 1);
    if (ret > 0)
      return true;
    if ((ret != -1) || (errno != EINTR))
      return false;
    // write got interrupted - retry
  }
}

int GNUmakeTokenPoolPosix::GetMonitorFd() {
  return rfd_;
}

TokenPool* TokenPool::Get() {
  return new GNUmakeTokenPoolPosix;
}
