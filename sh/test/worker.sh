#!/bin/sh

cd "$(dirname "$0")"

. "../src/tokenpool.sh"

log() {
  echo "$$ $(date +'%F %T.%N') $*"
}

if jobclient_init; then
  log test: init ok

  # TODO acquire more tokens
  # start multiple workers in parallel
  # release all tokens

  token=''
  if token="$(jobclient_acquire)" && [ -n "$token" ]; then
    log "test: token = $token"
    log "test: sleep ..."
    sleep 2
    jobclient_release "$token"
  else
    log "test: jobserver is full"
  fi

else
  log test: init failed
fi

log "test: fds = $_jobclient_fd_read $_jobclient_fd_write"
