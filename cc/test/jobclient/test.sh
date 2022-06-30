#!/bin/sh

d="$(dirname "$(readlink -f "$0")")"

export DEBUG_JOBCLIENT=1
set -e
cd "$d"
set -x

#make # no jobserver

#make -j1 # no jobserver

make -j10
