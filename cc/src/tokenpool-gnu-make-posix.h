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

#include "tokenpool-gnu-make.h"

#include <signal.h>

// TokenPool implementation for GNU make jobserver - POSIX implementation
// (http://make.mad-scientist.net/papers/jobserver-implementation/)
struct GNUmakeTokenPoolPosix : public GNUmakeTokenPool {
  GNUmakeTokenPoolPosix();
  virtual ~GNUmakeTokenPoolPosix();

  virtual int GetMonitorFd();

  virtual const char* GetEnv(const char* name) { return getenv(name); }
  virtual bool SetEnv(const char* name, const char* value) {
    return setenv(name, value, 1) == 0;
  }
  virtual bool ParseAuth(const char* jobserver);
  virtual bool CreatePool(int parallelism, std::string* auth);
  virtual int AcquireToken();
  virtual bool ReleaseToken(int token);

 private:
  int rfd_;
  int wfd_;

  struct sigaction old_act_;
  bool restore_;

  static int dup_rfd_;
  static void CloseDupRfd(int signum);

  bool CheckFd(int fd);
  bool SetAlarmHandler();
};
