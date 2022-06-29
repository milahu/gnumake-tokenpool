#!/bin/sh

d="$(dirname "$(readlink -f "$0")")"

export PYTHONPATH="$PYTHONPATH:$d/../src"
echo "PYTHONPATH = $PYTHONPATH"

cd "$d"

set -x

./jobclient/test.sh
