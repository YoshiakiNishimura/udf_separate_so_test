#!/bin/bash
set -e
TSURUGI_PROTO=${HOME}/git/tsurugi-udf/proto
python3 build.py -I ../proto -I ${TSURUGI_PROTO} --proto ../proto/plugin_a.proto ../proto/data/a_data.proto ../proto/data/company_data.proto ${HOME}/git/tsurugi-udf/proto/tsurugidb/udf/tsurugi_types.proto
