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
from gen_tpl import render_tpl_for_rpc_protos
from common_static import compile_common_objects, archive_common_static


def run(argv=None):
    args = CliArgs.from_cli(argv)

    script_dir = Path(__file__).resolve().parent
    templates_dir = script_dir / "templates"
    tsurugi_udf_common_dir = script_dir / "common" / "tsurugi_udf_common"

    includes = validate_includes(list(args.include))
    proto_files = validate_proto_files([Path(p) for p in args.proto_files])

    build_dir = Path(args.build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    OUT = build_dir / "desc"
    GEN = build_dir / "gen"
    OBJ = build_dir / "obj"
    TPL = build_dir / "tpl"
    LIB = build_dir / "lib"
    INI = build_dir / "ini"
    CMN = build_dir / "cmn"

    OUT.mkdir(exist_ok=True)
    GEN.mkdir(exist_ok=True)
    OBJ.mkdir(exist_ok=True)
    TPL.mkdir(exist_ok=True)
    LIB.mkdir(exist_ok=True)
    INI.mkdir(exist_ok=True)
    CMN.mkdir(exist_ok=True)

    grpc_plugin = find_grpc_cpp_plugin(args.grpc_plugin)

    desc_pb = OUT / "all.desc.pb"
    cmd = build_protoc_cmd(includes, proto_files, desc_pb, GEN, grpc_plugin)
    run_protoc(cmd)

    include_dirs = [str(GEN)] + includes
    jobs = int(os.environ.get("JOBS", "0")) or None

    fds = load_fds(desc_pb)
    graph = build_import_graph(fds)
    render_tpl_for_rpc_protos(
        fds=fds,
        templates_dir=templates_dir,
        tpl_dir=TPL,
        # fetch_add_name=fetch_add_name,
    )

    common_srcs = [
        tsurugi_udf_common_dir / "src" / "udf" / "descriptor_impl.cpp",
        tsurugi_udf_common_dir / "src" / "udf" / "error_info.cpp",
        tsurugi_udf_common_dir / "src" / "udf" / "generic_record_impl.cpp",
    ]
    common_include_dirs = [
        str(tsurugi_udf_common_dir / "include" / "udf"),
        str(GEN),
        *includes,
    ]
    common_objs = compile_common_objects(
        sources=common_srcs,
        obj_dir=CMN / "obj",
        include_dirs=common_include_dirs,
    )
    common_a = archive_common_static(
        objs=common_objs,
        out_dir=CMN,
        name="libtsurugi_udf_common.a",
    )
    print(f"# built common static: {common_a}")

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
        common_static=common_a,
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
