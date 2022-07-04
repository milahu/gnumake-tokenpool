#!/usr/bin/env bash

_debug() {
  echo "$$ $(date +'%F %T.%N') $@" >&2
}

jobclient_init() {
  if [ -z "$MAKEFLAGS" ]; then
    _debug "jobclient init: MAKEFLAGS is empty"
    return 1
  fi
  _debug "jobclient init: MAKEFLAGS = $MAKEFLAGS"
  # set globals
  read -r _jobclient_fd_read _jobclient_fd_write \
    < <(echo "$MAKEFLAGS" | sed -E 's/.* ?--jobserver-(auth|fds)=([0-9]+),([0-9]+) ?.*/\2 \3/')
  _debug "jobclient init: fds = $_jobclient_fd_read $_jobclient_fd_write"
}

jobclient_acquire() {
  local _token
  read -r -n1 -t0.1 _token <"/proc/self/fd/$_jobclient_fd_read"
  #_debug "jobclient_acquire: token = '$_token' (char)"
  if [ -z "$_token" ]; then
    _debug "jobclient_acquire: no token"
    return 1
  fi
  # ord: byte -> int
  # + -> 43
  _token=$(LC_CTYPE=C printf %d "'$_token") # ord()
  _debug "jobclient_acquire: token = $_token (int)"
  printf '%b' "$_token"
}

jobclient_release() {
  local _token="$1"
  [ -z "$_token" ] && _token=43 # default
  [ "$_token" -lt 256 ] || return 1
  _debug "jobclient_release: token = $_token (int)"
  _token=$(printf '%b' "$(printf '\\x%x' "$1")") # chr()
  printf '%b' "$_token" >"/proc/self/fd/$_jobclient_fd_write"
}
