#!/usr/bin/env python3
import argparse
import shutil
import subprocess
import sys
import os
from pathlib import Path
from google.protobuf.descriptor_pb2 import FileDescriptorSet
from collections import defaultdict, deque

from args import CliArgs

EXCLUDE_PREFIXES = ("google/protobuf/",)
EXCLUDE_EXACT = ("tsurugidb/udf/tsurugi_types.proto",)

def load_fds(desc_pb: Path) -> FileDescriptorSet:
    fds = FileDescriptorSet()
    fds.ParseFromString(desc_pb.read_bytes())
    return fds

def build_import_graph(fds: FileDescriptorSet) -> dict[str, set[str]]:
    g: dict[str, set[str]] = {}
    for fd in fds.file:
        g[fd.name] = set(fd.dependency)
    return g


def is_excluded(name: str) -> bool:
    if name in EXCLUDE_EXACT:
        return True
    return any(name.startswith(p) for p in EXCLUDE_PREFIXES)


def reachable_from_root(graph: dict[str, set[str]], root: str) -> set[str]:
    """Return set of nodes reachable from root following dependency edges (root excluded or included? included)."""
    seen: set[str] = set()
    stack = [root]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        for dep in graph.get(cur, ()):
            stack.append(dep)
    return seen


def filter_graph(
    graph: dict[str, set[str]],
    *,
    keep_nodes: set[str],
    exclude: bool = True,
) -> dict[str, set[str]]:
    """
    Keep only nodes in keep_nodes, and optionally drop excluded nodes.
    Also prunes edges to only kept nodes.
    """
    kept = set(keep_nodes)
    if exclude:
        kept = {n for n in kept if not is_excluded(n)}

    out: dict[str, set[str]] = {}
    for n in kept:
        deps = graph.get(n, set())
        deps2 = {d for d in deps if d in kept}
        out[n] = deps2
    return out


def topo_layers(graph: dict[str, set[str]]) -> list[list[str]]:
    """
    Topologically group nodes into layers.
    Each layer can be processed in parallel once previous layers are done.

    graph: node -> dependencies
    """
    nodes = set(graph.keys())
    # reverse edges: dep -> users
    users: dict[str, set[str]] = defaultdict(set)
    indeg: dict[str, int] = {n: 0 for n in nodes}

    for n, deps in graph.items():
        indeg[n] = len(deps)
        for d in deps:
            users[d].add(n)

    q = deque(sorted([n for n in nodes if indeg[n] == 0]))
    layers: list[list[str]] = []
    processed = 0

    while q:
        layer = list(q)
        layers.append(layer)
        q.clear()

        for n in layer:
            processed += 1
            for u in users.get(n, ()):
                indeg[u] -= 1
                if indeg[u] == 0:
                    q.append(u)

        # deterministic order within a layer
        q = deque(sorted(q))

    if processed != len(nodes):
        # cycle or missing nodes
        remaining = sorted([n for n in nodes if indeg[n] > 0])
        raise RuntimeError(f"cycle detected or graph not reducible; remaining: {remaining}")

    return layers

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


def build_protoc_cmd(
    *,
    includes: list[str],
    proto_files: list[Path],
    desc_out: Path,
    gen_dir: Path,
    grpc_plugin_path: Path,
) -> list[str]:

    if not proto_files:
        raise ValueError("no proto_files specified")

    for p in proto_files:
        if not p.exists():
            raise FileNotFoundError(f"proto_file not found: {p}")

    # Ensure output dirs exist
    desc_out.parent.mkdir(parents=True, exist_ok=True)
    gen_dir.mkdir(parents=True, exist_ok=True)

    cmd: list[str] = ["protoc"]

    for inc in includes:
        cmd.append(f"-I{inc}")

    cmd += [
        "--include_imports",
        f"--descriptor_set_out={desc_out}",
        f"--cpp_out={gen_dir}",
        f"--grpc_out={gen_dir}",
        f"--plugin=protoc-gen-grpc={grpc_plugin_path}",
    ]
    cmd += [str(p) for p in proto_files]

    return cmd

def run(argv=None):
    args = CliArgs.from_cli(argv)

    proto_files = [Path(p) for p in args.proto_files]
    for p in proto_files:
        if not p.exists():
            raise SystemExit(f"--proto not found: {p}")

    build_base = allocate_build_dir(Path(args.build_dir))
    build_base.mkdir(parents=True, exist_ok=True)

    OUT = build_base / "desc"
    GEN = build_base / "gen"
    OUT.mkdir(parents=True, exist_ok=True)
    GEN.mkdir(parents=True, exist_ok=True)

    grpc_plugin_path = find_grpc_cpp_plugin(args.grpc_plugin)

    cmd = build_protoc_cmd(
        includes=args.include,
        proto_files=proto_files,
        desc_out=OUT / "all.desc.pb",
        gen_dir=GEN,
        grpc_plugin_path=grpc_plugin_path,
    )
    subprocess.run(cmd, check=True)

    desc_pb = OUT / "all.desc.pb"
    fds = load_fds(desc_pb)
    graph_all = build_import_graph(fds)

def main():
    run(sys.argv[1:])


if __name__ == "__main__":
    main()
