#!/usr/bin/env python3
"""Package the ARM64 install tree for a Raspberry Pi 4 with ROS 2 Jazzy."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile


REPO = Path(__file__).resolve().parent


def source_dir(variable: str, default_path: Path) -> Path:
    return Path(
        os.environ.get(variable, str(default_path))
    ).resolve()


def git_output(repo: Path, *args: str) -> str:
    return subprocess.check_output(
        ["git", "-C", str(repo), *args], text=True
    ).strip()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--name",
        default="urg-node2-jazzy-arm64",
        help="archive directory name and tarball stem (default: %(default)s)",
    )
    parser.add_argument(
        "--remote-home",
        type=Path,
        default=Path.home(),
        help="absolute Raspberry Pi 4 user home; if omitted, assumes the Host PC user's home path",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO / "dist",
        help="directory for the generated tarball (default: urg_lidar_app/dist)",
    )
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", args.name):
        parser.error("--name must be a single directory name")
    if not args.remote_home.is_absolute():
        parser.error("--remote-home must be an absolute path")

    source = REPO / "install"
    executable = source / "lib/urg_node2/urg_node2_node"
    if not executable.is_file():
        parser.error("build the workspace with ./build-arm64.sh first")

    urg_node2_source = source_dir("URG_NODE2_SOURCE", REPO / "urg_node2")
    rt_support_source = source_dir(
        "ROS_RT_SUPPORT_SOURCE", REPO.parent / "ros2_realtime_support"
    )

    sysroot = Path(
        os.environ.get(
            "URG_RT_SYSROOT",
            str(Path.home() / "ros2-realtime-cross-pi-jazzy/sysroot"),
        )
    )
    remote_root = args.remote_home / args.name
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(dir=output_dir) as temp:
        stage = Path(temp) / args.name
        install = stage / "install"
        shutil.copytree(source, install, symlinks=True)

        old_prefix = str(source)
        old_ros = str(sysroot / "opt/ros/jazzy")
        for path in install.rglob("*"):
            if not path.is_file() or path.is_symlink():
                continue
            data = path.read_bytes()
            if b"\0" in data:
                continue
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                continue
            updated = text.replace(old_prefix, str(remote_root / "install"))
            updated = updated.replace(old_ros, "/opt/ros/jazzy")
            if updated != text:
                path.write_text(updated)

        run_script = stage / "run.sh"
        shutil.copy2(REPO / "device/run.sh", run_script)
        run_script.chmod(0o755)
        binaries = list((install / "lib").glob("*.so"))
        binaries.append(install / "lib/urg_node2/urg_node2_node")
        hashes = {}
        for path in binaries:
            header = subprocess.check_output(
                ["aarch64-linux-gnu-readelf", "-h", str(path)], text=True
            )
            dynamic = subprocess.check_output(
                ["aarch64-linux-gnu-readelf", "-d", str(path)], text=True
            )
            if "AArch64" not in header or "(RPATH)" in dynamic or "(RUNPATH)" in dynamic:
                raise RuntimeError(f"unexpected architecture or runtime path: {path}")
            hashes[str(path.relative_to(stage))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()

        manifest = {
            "urg_node2_patch_sha256": hashlib.sha256(
                (REPO / "patches/urg_node2_rt.patch").read_bytes()
            ).hexdigest(),
            "ros2_realtime_support_patch_sha256": hashlib.sha256(
                (REPO / "patches/ros2-realtime-support-no-mimick.patch").read_bytes()
            ).hexdigest(),
            "urg_node2_commit": git_output(
                urg_node2_source, "rev-parse", "HEAD"
            ),
            "urg_library_commit": git_output(
                urg_node2_source / "urg_library", "rev-parse", "HEAD"
            ),
            "ros2_realtime_support_commit": git_output(
                rt_support_source, "rev-parse", "HEAD"
            ),
            "urg_node2_has_worktree_changes": bool(
                git_output(
                    urg_node2_source,
                    "-c", "core.fileMode=false",
                    "status", "--porcelain", "--ignore-submodules=dirty",
                )
            ),
            "ros2_realtime_support_has_worktree_changes": bool(
                git_output(rt_support_source, "status", "--porcelain")
            ),
            "target": "AArch64 / ROS 2 Jazzy / Release",
            "binaries": hashes,
        }
        (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")

        archive = output_dir / f"{args.name}.tar.gz"
        temporary_archive = Path(temp) / archive.name
        with tarfile.open(temporary_archive, "w:gz") as tar:
            tar.add(stage, arcname=args.name)
        shutil.move(temporary_archive, archive)

    print(f"{archive} sha256={hashlib.sha256(archive.read_bytes()).hexdigest()}")


if __name__ == "__main__":
    main()
