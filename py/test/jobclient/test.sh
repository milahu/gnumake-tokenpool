#!/bin/sh

d="$(dirname "$(readlink -f "$0")")"

export DEBUG_JOBCLIENT=1
set -e
cd "$d"
set -x

make_exe=$(which make)

for jobserver_style in pipe fifo; do

echo testing "make --jobserver-style=$jobserver_style"

function make() {
  $make_exe --jobserver-style=$jobserver_style "$@"
}

make -j1 # 0 workers -> no jobserver

make -j2 # 1 worker

make -j3 # 2 workers

make -j4 # 3 workers

make -j4 -l4 # 3 workers + maxLoad 4

done

echo all tests passed
