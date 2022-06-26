#!/bin/sh

set -x

make -C test/ -j4

make -C test/ -j4 -l4
