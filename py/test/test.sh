#!/bin/sh

d="$(dirname "$(readlink -f "$0")")"
cd "$d"

./jobclient/test.sh
