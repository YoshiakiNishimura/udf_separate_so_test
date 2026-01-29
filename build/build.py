from pathlib import Path
import sys
import os

from args import CliArgs
from validate import validate_includes, validate_proto_files
from protoc import find_grpc_cpp_plugin, build_protoc_cmd, run_protoc
from desc import load_fds, build_import_graph
from compile_objects import build_objects_parallel
from link_shared import build_shared_libs_layered_parallel
from verify_links import verify_shared_libs
from analyze_rpcs import dump_rpc_so_report
from gen_ini import write_ini_files_for_rpc_libs


def run(argv=None):
    args = CliArgs.from_cli(argv)

    includes = validate_includes(list(args.include))
    proto_files = validate_proto_files([Path(p) for p in args.proto_files])

    build_dir = Path(args.build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    OUT = build_dir / "desc"
    GEN = build_dir / "gen"
    OBJ = build_dir / "obj"
    LIB = build_dir / "lib"
    INI = build_dir / "ini"

    OUT.mkdir(exist_ok=True)
    GEN.mkdir(exist_ok=True)
    OBJ.mkdir(exist_ok=True)
    LIB.mkdir(exist_ok=True)
    INI.mkdir(exist_ok=True)

    grpc_plugin = find_grpc_cpp_plugin(args.grpc_plugin)

    desc_pb = OUT / "all.desc.pb"
    cmd = build_protoc_cmd(includes, proto_files, desc_pb, GEN, grpc_plugin)
    run_protoc(cmd)

    # ---- compile .o in parallel ----
    include_dirs = [str(GEN)] + includes  # GEN is required for generated headers
    jobs = int(os.environ.get("JOBS", "0")) or None

    objs = build_objects_parallel(
        gen_dir=GEN,
        obj_dir=OBJ,
        include_dirs=include_dirs,
        jobs=jobs,
    )
    print(f"# compiled objects: {len(objs)}")

    fds = load_fds(desc_pb)
    graph = build_import_graph(fds)

    target_protos = set(graph.keys())

    exclude_protos = set()

    outputs = build_shared_libs_layered_parallel(
        import_graph=graph,
        target_protos=target_protos,
        obj_dir=OBJ,
        lib_dir=LIB,
        exclude_protos=exclude_protos,
        jobs=jobs,
    )
    print(f"# linked libs: {len(outputs)}")

    verify_shared_libs(
        outputs=outputs,
        import_graph=graph,
        require_origin_rpath=True,
        forbid_path_needed=True,
    )
    dump_rpc_so_report(fds)

    write_ini_files_for_rpc_libs(
        fds,
        lib_dir=LIB,
        ini_dir=INI,
        endpoint=args.grpc_endpoint,
        secure=False,
        enabled=True,
    )


def main():
    run(sys.argv[1:])


if __name__ == "__main__":
    main()
