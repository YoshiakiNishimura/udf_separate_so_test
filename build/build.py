#!/usr/bin/env python3
import subprocess
from pathlib import Path

PROTO_ROOT = Path("../proto")
TSURUGI_PROTO = Path.home() / "git" / "tsurugi-udf" / "proto"
OUT = Path("tmp/out")
GEN = Path("tmp/gen")

OUT.mkdir(parents=True, exist_ok=True)
GEN.mkdir(parents=True, exist_ok=True)

GRPC_CPP_PLUGIN = "/usr/bin/grpc_cpp_plugin"

cmd = [
    "protoc",
    f"-I{PROTO_ROOT}",
    f"-I{TSURUGI_PROTO}",
    "--include_imports",
    f"--descriptor_set_out={OUT}/plugin_a.desc.pb",
    f"--cpp_out={GEN}",
    f"--grpc_out={GEN}",
    f"--plugin=protoc-gen-grpc={GRPC_CPP_PLUGIN}",
    str(PROTO_ROOT / "plugin_a.proto"),
]

print(" ".join(cmd))
subprocess.run(cmd, check=True)
