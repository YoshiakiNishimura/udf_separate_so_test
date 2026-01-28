import shutil
import os
from pathlib import Path
import subprocess
import sys


def find_grpc_cpp_plugin(cli_value=None) -> Path:
    candidates = []
    if cli_value:
        candidates.append(cli_value)

    env_val = os.environ.get("GRPC_CPP_PLUGIN") or os.environ.get("PROTOC_GEN_GRPC")
    if env_val:
        candidates.append(env_val)

    which_val = shutil.which("grpc_cpp_plugin")
    if which_val:
        candidates.append(which_val)

    candidates += ["/usr/bin/grpc_cpp_plugin", "/usr/local/bin/grpc_cpp_plugin"]

    seen = set()
    for c in candidates:
        if c in seen:
            continue
        seen.add(c)
        p = Path(c)
        if p.exists() and p.is_file() and os.access(str(p), os.X_OK):
            return p

    raise SystemExit("grpc_cpp_plugin not found")


def build_protoc_cmd(includes, proto_files, desc_out, gen_dir, grpc_plugin_path):
    desc_out.parent.mkdir(parents=True, exist_ok=True)
    gen_dir.mkdir(parents=True, exist_ok=True)

    cmd = ["protoc"]
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


def run_protoc(cmd):
    print(" ".join(map(str, cmd)))
    try:
        r = subprocess.run(cmd, check=True, text=True, capture_output=True)
        if r.stderr:
            print(r.stderr, file=sys.stderr, end="")
    except subprocess.CalledProcessError as e:
        if e.stderr:
            print(e.stderr, file=sys.stderr)
        raise SystemExit(e.returncode)
