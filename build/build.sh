#!/bin/bash
set -e
TSURUGI_PROTO=${HOME}/git/tsurugi-udf/proto
python3 build.py -I ../proto -I ${TSURUGI_PROTO} --proto-file ../proto/plugin_a.proto
