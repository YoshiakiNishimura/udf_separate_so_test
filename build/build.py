#!/usr/bin/env python3
import argparse
import shutil
import subprocess
import sys
import os
from pathlib import Path

def find_grpc_cpp_plugin(cli_value: str | None) -> Path:
    """
    grpc_cpp_plugin path resolution priority:
      1) Command-line option --grpc-plugin
      2) Environment variables: GRPC_CPP_PLUGIN or PROTOC_GEN_GRPC
      3) PATH lookup (which grpc_cpp_plugin)
      4) Well-known fallback locations
    """
    candidates: list[str] = []

    if cli_value:
        candidates.append(cli_value)

    env_val = os.environ.get("GRPC_CPP_PLUGIN") or os.environ.get("PROTOC_GEN_GRPC")
    if env_val:
        candidates.append(env_val)

    which_val = shutil.which("grpc_cpp_plugin")
    if which_val:
        candidates.append(which_val)

    candidates += [
        "/usr/bin/grpc_cpp_plugin",
        "/usr/local/bin/grpc_cpp_plugin",
    ]

    seen = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        p = Path(c)
        if p.exists() and p.is_file() and os.access(str(p), os.X_OK):
            return p

    raise SystemExit(
        "grpc_cpp_plugin not found. Tried:\n  - "
        + "\n  - ".join(candidates or ["(no candidates)"])
        + "\nInstall it or pass --grpc-plugin / set GRPC_CPP_PLUGIN."
    )

def allocate_build_dir(base: Path) -> Path:
    if not base.exists():
        return base
    i = 1
    while True:
        cand = base.with_name(f"{base.name}_{i}")
        if not cand.exists():
            return cand
        i += 1

def run(args=None):
    args = parse_args(args)

    proto_file = Path(args.proto_file)
    if not proto_file.exists():
        raise SystemExit(f"--proto-file not found: {proto_file}")
    name = args.name or proto_file.stem
    build_base = allocate_build_dir(Path(args.build_dir))
    build_base.mkdir(parents=True, exist_ok=True)
    OUT = build_base / "desc"
    GEN = build_base / "gen"
    OUT.mkdir(parents=True, exist_ok=True)
    GEN.mkdir(parents=True, exist_ok=True)

    grpc_plugin_path = find_grpc_cpp_plugin(args.grpc_plugin)

    PROTO_ROOT = Path("../proto")
    TSURUGI_PROTO = Path.home() / "git" / "tsurugi-udf" / "proto"

    cmd = [
        "protoc",
        f"-I{PROTO_ROOT}",
        f"-I{TSURUGI_PROTO}",
        "--include_imports",
        f"--descriptor_set_out={OUT}/{name}.desc.pb",
        f"--cpp_out={GEN}",
        f"--grpc_out={GEN}",
        f"--plugin=protoc-gen-grpc={grpc_plugin_path}",
        str(proto_file),
    ]

    print(" ".join(cmd))
    subprocess.run(cmd, check=True)

def parse_args(args=None):
    parser = argparse.ArgumentParser(description="protoc wrapper")
    parser.add_argument(
        "--proto-file",
        required=True,
        help=".proto",
    )
    parser.add_argument(
        "--build-dir", default="tmp", help="Temporary directory for generated files"
    )
    parser.add_argument(
        "--grpc-plugin",
        default=None,
        help="Path to grpc_cpp_plugin (default: auto-detect, fallback /usr/bin/grpc_cpp_plugin)",
    )
    parser.add_argument(
        "-I", "--include",
        action="append",
        default=[],
        help="proto include path (can be specified multiple times)"
    )
    parser.add_argument(
        "--grpc-endpoint", default="dns:///localhost:50051", help="gRPC server endpoint"
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Path to write the generated ini file.",
    )
    parser.add_argument(
        "--name",
        required=False,
        help="Base name used for the generated plugin library (.so) and configuration file (.ini).",
    )
    return parser.parse_args(args)

def main():
    run(sys.argv[1:])

if __name__ == "__main__":
    main()
