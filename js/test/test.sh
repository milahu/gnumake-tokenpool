#!/bin/sh

d="$(dirname "$(readlink -f "$0")")"
cd "$d"

set -x

./jobclient/test.sh
