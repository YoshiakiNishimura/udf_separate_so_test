# args.py
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class CliArgs:
    proto_file: str
    build_dir: str = "tmp"
    grpc_plugin: str | None = None
    include: list[str] = None
    grpc_endpoint: str = "dns:///localhost:50051"
    output_dir: str | None = None
    name: str | None = None

    @staticmethod
    def build_parser() -> argparse.ArgumentParser:
        p = argparse.ArgumentParser(description="protoc wrapper")
        p.add_argument("--proto-file", required=True, help=".proto")
        p.add_argument(
            "--build-dir", default="tmp", help="Temporary directory for generated files"
        )
        p.add_argument(
            "--grpc-plugin",
            default=None,
            help="Path to grpc_cpp_plugin (default: auto-detect, fallback /usr/bin/grpc_cpp_plugin)",
        )
        p.add_argument(
            "-I",
            "--include",
            action="append",
            default=[],
            help="proto include path (can be specified multiple times)",
        )
        p.add_argument(
            "--grpc-endpoint",
            default="dns:///localhost:50051",
            help="gRPC server endpoint",
        )
        p.add_argument(
            "--output-dir", default=None, help="Path to write the generated ini file."
        )
        p.add_argument(
            "--name",
            required=False,
            help="Base name used for the generated plugin library (.so) and configuration file (.ini).",
        )
        return p

    @classmethod
    def from_cli(cls, argv: Sequence[str] | None = None) -> "CliArgs":
        ns = cls.build_parser().parse_args(argv)
        return cls(
            proto_file=ns.proto_file,
            build_dir=ns.build_dir,
            grpc_plugin=ns.grpc_plugin,
            include=list(ns.include),
            grpc_endpoint=ns.grpc_endpoint,
            output_dir=ns.output_dir,
            name=ns.name,
        )
