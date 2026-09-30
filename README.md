# Cross-build for Raspberry Pi 4 (ROS 2 Jazzy)

[日本語版](README_ja.md)

This guide cross-builds the realtime-enabled `urg_node2` and `ros2_realtime_support` for an AArch64 Raspberry Pi 4 from an Ubuntu 24.04 x86_64 host. The Raspberry Pi 4 needs Ubuntu 24.04 and ROS 2 Jazzy at `/opt/ros/jazzy`. The host needs Git, CMake, colcon, Python 3.12, AArch64 GCC/G++, `aarch64-linux-gnu-readelf`, SSH, rsync, and an AArch64 sysroot containing the Raspberry Pi 4's ROS 2 Jazzy installation.

In this guide, **build host** means the Ubuntu 24.04 x86_64 Host PC where cross-compilation runs. **Raspberry Pi 4** means the AArch64 target where the resulting binaries run. A “build host home directory” is the Host PC user's home directory, not the Raspberry Pi 4 user's home directory.

Use the `urg_lidar_app` checkout, its `urg_node2` submodule, and a separate Realtime Support checkout:

| Module | Target source | Purpose |
| --- | --- | --- |
| `urg_lidar_app` | `feature/urg_node_rt_support` | Build and packaging scripts |
| `urg_lidar_app/urg_node2` | Apply `urg_node2_rt.patch` from `patches/` to the `urg_node2` submodule | Driver source |
| `ros2_realtime_support` | Apply the mimick_vendor patch from `patches/` to the Realtime Support module | Realtime Support libraries |

Before building, the script applies [`urg_node2_rt.patch`](patches/urg_node2_rt.patch) to the submodule and [the mimick_vendor patch](patches/ros2-realtime-support-no-mimick.patch) to Realtime Support. Later runs recognize already-applied patches. If either source matches neither the original nor patched state, the script stops before building.

## Configure source and sysroot paths

Set these variables to your own absolute paths. Keep them exported in the same shell for the build and packaging commands.

```bash
export APP_DIR=/absolute/path/to/urg_lidar_app
export ROS_RT_SUPPORT_SOURCE=/absolute/path/to/ros2_realtime_support
export URG_RT_SYSROOT=/absolute/path/to/aarch64-sysroot

git -C "$APP_DIR" submodule update --init --recursive
```

## Create the sysroot from the Raspberry Pi 4

On the build host, copy the Raspberry Pi 4's `/usr/` contents to `$URG_RT_SYSROOT/usr/`. ROS 2 Jazzy is installed under `/opt/ros/jazzy/`, so copy that tree to `$URG_RT_SYSROOT/opt/ros/jazzy/` too. On the Raspberry Pi 4, `/lib` is a symbolic link to `usr/lib`; preserve that link as well. `rsync` must also be installed on the Raspberry Pi 4. Replace `user@raspberry-pi` with the Raspberry Pi 4 SSH account and host.

```bash
export PI_SSH=user@raspberry-pi
mkdir -p "$URG_RT_SYSROOT/usr" "$URG_RT_SYSROOT/opt/ros/jazzy"
rsync -a "${PI_SSH}:/usr/" "$URG_RT_SYSROOT/usr/"
rsync -a "${PI_SSH}:/opt/ros/jazzy/" "$URG_RT_SYSROOT/opt/ros/jazzy/"
rsync -a "${PI_SSH}:/lib" "$URG_RT_SYSROOT/"
```

`rsync -a` preserves symbolic links. Use files from a Raspberry Pi 4 with the matching Ubuntu 24.04 and ROS 2 Jazzy installation, and check that `$URG_RT_SYSROOT/usr/lib/aarch64-linux-gnu/` and `$URG_RT_SYSROOT/opt/ros/jazzy/` exist afterward.

By default, the build script uses `$APP_DIR/urg_node2`. `URG_NODE2_SOURCE` can override that path if needed, and the same patch check then runs on the selected checkout. The script also reads `ROS_RT_SUPPORT_SOURCE` and `URG_RT_SYSROOT`. It writes all build results under `APP_DIR`.

## Build without mimick_vendor

At the tested Realtime Support revision, `rclcpp_realtime/CMakeLists.txt` calls `find_package(mimick_vendor REQUIRED)` even with tests disabled. The build script automatically patches out that unconditional line, so a clean sysroot without `mimick_vendor` can be used for a normal build. The remaining lookups are in test-only CMake code and are skipped with `BUILD_TESTING=OFF`. To build the tests, provide their dependencies separately.

## Build and verify

```bash
cd "$APP_DIR"
./build-arm64.sh
aarch64-linux-gnu-readelf -h install/lib/urg_node2/urg_node2_node | grep Machine
aarch64-linux-gnu-readelf -d install/lib/urg_node2/urg_node2_node | grep realtime
```

The script first applies `urg_node2_rt.patch` to `$APP_DIR/urg_node2` and the `mimick_vendor` patch to Realtime Support if needed, then builds the driver and its Realtime Support dependencies in Release mode with tests disabled. Both checkouts appear modified in Git after patching; this is expected. It writes `build/`, `install/`, and `log/` under `APP_DIR`. The node is `install/lib/urg_node2/urg_node2_node`; shared libraries such as `librclcpp_realtime.so` are under `install/lib/`. The checks should show `AArch64` and Realtime Support library dependencies.

## Package and transfer

`package-arm64.py` reads the existing `$APP_DIR/install/` tree; it does not build the binaries. It checks their architecture and runtime paths, rewrites build-host paths in text setup files, and creates a tar archive.

| Option | Default | Description |
| --- | --- | --- |
| `--name NAME` | `urg-node2-jazzy-arm64` | Name of the top-level directory inside the archive and stem of the `NAME.tar.gz` file. Use one directory name starting with a letter or digit; the remaining characters may also include `.`, `_`, or `-`. |
| `--remote-home PATH` | If omitted, the Host PC user's home path is **assumed** to be the Raspberry Pi 4 user's home path. | Supply the **Raspberry Pi 4 user's** absolute home path. The packaging script embeds this target path in the setup files. The assumed value is correct only when both home paths are identical. |
| `--output-dir PATH` | `$APP_DIR/dist` | Directory in which to write the tarball; a relative path is resolved from the command's current directory. |
| `-h`, `--help` | — | Show the script's option summary. |

For example, suppose the Host PC user's home is `/home/builduser` and the Raspberry Pi 4 user's home is `/home/deviceuser`. Omitting `--remote-home` would embed `/home/builduser/urg-node2-jazzy-arm64/install` in the package, which is wrong for a package extracted under `/home/deviceuser`. Specify `--remote-home /home/deviceuser` so the embedded install path matches the Raspberry Pi 4 destination. These usernames are examples; use the actual path returned by SSH below.

The script uses `URG_RT_SYSROOT` when rewriting ROS paths. To avoid relying on the home-path assumption, the example reads the Raspberry Pi 4 account's actual home directory and passes it explicitly to `--remote-home`. Replace `user@raspberry-pi` with that account and host.

```bash
export PI_SSH=user@raspberry-pi
PI_HOME=$(ssh "$PI_SSH" 'printf %s "$HOME"')
cd "$APP_DIR"
python3 package-arm64.py --remote-home "$PI_HOME" --name urg-node2-jazzy-arm64
scp dist/urg-node2-jazzy-arm64.tar.gz "$PI_SSH:"
ssh "$PI_SSH" 'tar -xzf "$HOME/urg-node2-jazzy-arm64.tar.gz" -C "$HOME"'
```

The archive is `$APP_DIR/dist/urg-node2-jazzy-arm64.tar.gz` and contains `install/` and `run.sh`. The final `tar` command creates `$HOME/urg-node2-jazzy-arm64/` on the Raspberry Pi 4; its name comes from `--name`. The `install/share/urg_node2/config/` directory inside it comes from this project's build. Neither directory exists by default on the Raspberry Pi 4. ROS 2 Jazzy is a separate installation at `/opt/ros/jazzy` and must already be present.

## Configure and run on the Raspberry Pi 4

Edit `$HOME/urg-node2-jazzy-arm64/install/share/urg_node2/config/params_ether.yaml` on the Raspberry Pi 4 to set the LiDAR's `ip_address` and `ip_port`. The installed launch file reads this file. It does not offer a `thread_attrs_file` argument, so pass the thread attributes through `ROS_THREAD_ATTRS_FILE`. Save the FIFO configuration verified on the device as `$HOME/urg-node2-jazzy-arm64/thread_attrs.yaml` on the Raspberry Pi 4:

```yaml
- tag: RCLCPP_EXECUTOR_SINGLE_THREADED
  scheduling_policy: FIFO
  priority: 10
  core_affinity: []
- tag: URG_SCAN_THREAD
  scheduling_policy: FIFO
  priority: 20
  core_affinity: []
```

Before starting on the Raspberry Pi 4, check that `ulimit -r` is at least `20`.

Start the node in a Raspberry Pi 4 shell:

```bash
export ROS_THREAD_ATTRS_FILE="$HOME/urg-node2-jazzy-arm64/thread_attrs.yaml"
"$HOME/urg-node2-jazzy-arm64/run.sh"
```

`run.sh` sources ROS 2 Jazzy and the packaged install tree, sets `ROS_DOMAIN_ID=203` and `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST`, then starts the lifecycle node. The Raspberry Pi 4 user needs permission to set the realtime priority used above. The installed launch file comes from the patched `urg_node2` submodule; the files under `urg_lidar_app/launch` are not installed by this build.

Check the node from another Raspberry Pi 4 shell with the same domain and discovery settings:

```bash
source /opt/ros/jazzy/setup.bash
source "$HOME/urg-node2-jazzy-arm64/install/local_setup.bash"
export ROS_DOMAIN_ID=203 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 service call /urg_node2/get_state lifecycle_msgs/srv/GetState '{}'
ros2 topic hz /scan
```

The AArch64 cross-build was verified from clean `urg_node2` and Realtime Support checkouts using a sysroot without `mimick_vendor`. Both patches were applied automatically. The same build was run on a Raspberry Pi 4 with Ubuntu 24.04 and ROS 2 Jazzy: it connected to the LiDAR at `192.168.0.10:10940`, reached lifecycle state `active`, and published `/scan`. The executor ran with FIFO priority 10 and the scan thread with FIFO priority 20. Over about 12 seconds, `/scan` averaged about 39.8 Hz. The test processes were stopped afterward.
