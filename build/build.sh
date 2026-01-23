#!/bin/bash
set -e
OUT=tmp/out
GEN=tmp/gen
TSURUGI_PROTO=${HOME}/git/tsurugi-udf/proto

mkdir -p ${OUT} ${GEN}

protoc -I../proto -I${TSURUGI_PROTO} \
  --include_imports \
  --descriptor_set_out="${OUT}/plugin_a.desc.pb" \
  --cpp_out="${GEN}" \
  --grpc_out="${GEN}" \
  --plugin=protoc-gen-grpc=$(which grpc_cpp_plugin) \
  ../proto/plugin_a.proto
