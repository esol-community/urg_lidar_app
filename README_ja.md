# Raspberry Pi 4 向けクロスビルド（ROS 2 Jazzy）

[English](README.md)

この手順では、Ubuntu 24.04 x86_64 ホストから、Realtime 対応の `urg_node2` と `ros2_realtime_support` を Raspberry Pi 4 向け AArch64 バイナリとしてビルドします。Raspberry Pi 4 には Ubuntu 24.04 と `/opt/ros/jazzy` の ROS 2 Jazzy が必要です。ホストには Git、CMake、colcon、Python 3.12、AArch64 向け GCC/G++、`aarch64-linux-gnu-readelf`、SSH、rsync、および Raspberry Pi 4 の ROS 2 Jazzy を含む AArch64 sysroot が必要です。

この文書の**ビルドホスト**は、クロスコンパイルを実行する Ubuntu 24.04 x86_64 の Host PC です。**Raspberry Pi 4** は生成したバイナリを実行する AArch64 ターゲットです。「ビルドホストのホームディレクトリ」は Host PC 側ユーザーのホームディレクトリであり、Raspberry Pi 4 側のホームディレクトリではありません。

`urg_lidar_app` のチェックアウトとその `urg_node2` サブモジュール、および別の Realtime Support チェックアウトを使用します。

| モジュール名 | 対象ソース | 用途 |
| --- | --- | --- |
| `urg_lidar_app` | `feature/urg_node_rt_support` | ビルド・配布スクリプト |
| `urg_lidar_app/urg_node2` | サブモジュールのurg_node2に`patches/` 内の `urg_node2_rt.patch` を適用 | ドライバのソース |
| `ros2_realtime_support` | サブモジュールのros2_realtime_supportに `patches/` 内の mimick_vendor 用 patch を適用 | Realtime Support ライブラリ |

ビルドスクリプトは、ビルド前に [`urg_node2_rt.patch`](patches/urg_node2_rt.patch) をサブモジュールへ、[mimick_vendor 用 patch](patches/ros2-realtime-support-no-mimick.patch) を Realtime Support へ適用します。適用済みなら二重適用せず、元の状態・適用済み状態のどちらにも一致しない場合はビルド前に停止します。

## ソースと sysroot のパスを設定

各自の絶対パスに置き換えてください。ビルドと配布を行う間は、同じシェルで環境変数を保持します。

```bash
export APP_DIR=/absolute/path/to/urg_lidar_app
export ROS_RT_SUPPORT_SOURCE=/absolute/path/to/ros2_realtime_support
export URG_RT_SYSROOT=/absolute/path/to/aarch64-sysroot

git -C "$APP_DIR" submodule update --init --recursive
```

## Raspberry Pi 4 から sysroot を作成

ビルドホストで、Raspberry Pi 4 の `/usr/` 以下を `$URG_RT_SYSROOT/usr/` にコピーします。ROS 2 Jazzy は `/opt/ros/jazzy/` にあるため、これも `$URG_RT_SYSROOT/opt/ros/jazzy/` にコピーします。Raspberry Pi 4 の `/lib` は `usr/lib` へのシンボリックリンクなので、そのリンクも保持します。Raspberry Pi 4 側にも `rsync` が必要です。`user@raspberry-pi` は Raspberry Pi 4 の SSH アカウントとホスト名に置き換えてください。

```bash
export PI_SSH=user@raspberry-pi
mkdir -p "$URG_RT_SYSROOT/usr" "$URG_RT_SYSROOT/opt/ros/jazzy"
rsync -a "${PI_SSH}:/usr/" "$URG_RT_SYSROOT/usr/"
rsync -a "${PI_SSH}:/opt/ros/jazzy/" "$URG_RT_SYSROOT/opt/ros/jazzy/"
rsync -a "${PI_SSH}:/lib" "$URG_RT_SYSROOT/"
```

`rsync -a` はシンボリックリンクを保持します。Raspberry Pi 4 と同じ Ubuntu 24.04・ROS 2 Jazzy のファイルを使用し、コピー後に `$URG_RT_SYSROOT/usr/lib/aarch64-linux-gnu/` と `$URG_RT_SYSROOT/opt/ros/jazzy/` があることを確認してください。

ビルドスクリプトは既定で `$APP_DIR/urg_node2` を使用します。必要な場合は `URG_NODE2_SOURCE` で別のチェックアウトを指定でき、その場合も選択したソースに対して同じ patch 確認を行います。`ROS_RT_SUPPORT_SOURCE` と `URG_RT_SYSROOT` も読み取り、成果物を `APP_DIR` 配下に出力します。

## mimick_vendor を使わない通常ビルド

確認済みの Realtime Support リビジョンでは、テストを無効にしても `rclcpp_realtime/CMakeLists.txt` が `find_package(mimick_vendor REQUIRED)` を実行します。ビルドスクリプトはこの1行を patch で自動的に削除するため、クリーンな sysroot に `mimick_vendor` がなくても通常ビルドができます。残りの検索はテスト用の CMake コードにあり、`BUILD_TESTING=OFF` では実行されません。テストをビルドする場合は必要な依存パッケージを別途用意してください。

## ビルドと確認

```bash
cd "$APP_DIR"
./build-arm64.sh
aarch64-linux-gnu-readelf -h install/lib/urg_node2/urg_node2_node | grep Machine
aarch64-linux-gnu-readelf -d install/lib/urg_node2/urg_node2_node | grep realtime
```

スクリプトは必要なら最初に `$APP_DIR/urg_node2` へ `urg_node2_rt.patch` を、`Realtime Support` へ `mimick_vendor 用 patch` を適用し、ドライバと Realtime Support パッケージを Release モード、テスト無効でビルドします。適用後に両方のチェックアウトが Git 上で変更ありと表示されるのは正常です。`APP_DIR` 配下の `build/` にビルドファイル、`install/` に AArch64 バイナリと ROS パッケージファイル、`log/` にログを出力します。ノードは `install/lib/urg_node2/urg_node2_node`、`librclcpp_realtime.so` などの共有ライブラリは `install/lib/` にあります。検査結果に `AArch64` と Realtime Support への依存が表示されることを確認してください。

## 配布アーカイブの作成と転送

`package-arm64.py` は既存の `$APP_DIR/install/` を使用し、バイナリ自体はビルドしません。バイナリのアーキテクチャと実行時パスを検査し、テキスト形式のセットアップファイル内のビルドホストのパスを書き換えて、tar アーカイブを作成します。

| オプション | 既定値 | 説明 |
| --- | --- | --- |
| `--name NAME` | `urg-node2-jazzy-arm64` | アーカイブ内の最上位ディレクトリ名と `NAME.tar.gz` のファイル名に使用します。1つのディレクトリ名を指定し、先頭は英数字、残りは英数字・`.`・`_`・`-` を使用できます。 |
| `--remote-home PATH` | 省略すると、Host PC 側ユーザーのホームディレクトリのパスを **Raspberry Pi 4 側のパスと仮定**します。 | 指定する値は **Raspberry Pi 4 側ユーザーの**ホームディレクトリの絶対パスです。配布物内のセットアップファイルにこの転送先パスが埋め込まれます。省略時の仮定が正しいのは、両方のホームディレクトリのパスが同じ場合だけです。 |
| `--output-dir PATH` | `$APP_DIR/dist` | tar アーカイブの出力先です。相対パスはコマンド実行時のカレントディレクトリから解決します。 |
| `-h`, `--help` | — | オプションの一覧を表示します。 |

例えば、Host PC 側ユーザーのホームが `/home/builduser`、Raspberry Pi 4 側ユーザーのホームが `/home/deviceuser` の場合は、`--remote-home` を省略すると、配布物には `/home/builduser/urg-node2-jazzy-arm64/install` が埋め込まれ、`/home/deviceuser` に展開した配置と一致しません。`--remote-home /home/deviceuser` を指定すれば、埋め込まれる install パスが Raspberry Pi 4 側の配置と一致します。ユーザー名は説明用の例です。実際には以下の SSH コマンドで取得したパスを使用してください。

ROS のパスの書き換えには `URG_RT_SYSROOT` を使用します。省略時の仮定に依存しないよう、以下の例では Raspberry Pi 4 側アカウントの実際のホームディレクトリを取得して `--remote-home` に明示的に渡します。`user@raspberry-pi` はそのアカウントとホストに置き換えてください。

```bash
export PI_SSH=user@raspberry-pi
PI_HOME=$(ssh "$PI_SSH" 'printf %s "$HOME"')
cd "$APP_DIR"
python3 package-arm64.py --remote-home "$PI_HOME" --name urg-node2-jazzy-arm64
scp dist/urg-node2-jazzy-arm64.tar.gz "$PI_SSH:"
ssh "$PI_SSH" 'tar -xzf "$HOME/urg-node2-jazzy-arm64.tar.gz" -C "$HOME"'
```

アーカイブは `$APP_DIR/dist/urg-node2-jazzy-arm64.tar.gz` で、`install/` と `run.sh` を含みます。最後の `tar` コマンドで Raspberry Pi 4 の `$HOME/urg-node2-jazzy-arm64/` が作られます。この名前は `--name` の指定値です。その中の `install/share/urg_node2/config/` は今回のビルドで作られた内容です。どちらも Raspberry Pi 4 に最初からあるディレクトリではありません。ROS 2 Jazzy は別の `/opt/ros/jazzy` に事前にインストールしてください。

## Raspberry Pi 4 での設定と起動

Raspberry Pi 4 上の `$HOME/urg-node2-jazzy-arm64/install/share/urg_node2/config/params_ether.yaml` を編集し、LiDAR の `ip_address` と `ip_port` を設定します。インストールされた launch ファイルはこの設定を読み込みます。`thread_attrs_file` 引数はないため、環境変数 `ROS_THREAD_ATTRS_FILE` でスレッド属性を渡します。実機で確認した FIFO 設定を、Raspberry Pi 4 上の `$HOME/urg-node2-jazzy-arm64/thread_attrs.yaml` に保存します。

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

起動前に Raspberry Pi 4 側で `ulimit -r` が少なくとも `20` であることを確認してください。

Raspberry Pi 4 のシェルでノードを起動します。

```bash
export ROS_THREAD_ATTRS_FILE="$HOME/urg-node2-jazzy-arm64/thread_attrs.yaml"
"$HOME/urg-node2-jazzy-arm64/run.sh"
```

`run.sh` は ROS 2 Jazzy と同梱の install ツリーを読み込み、`ROS_DOMAIN_ID=203` と `ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST` を設定してライフサイクルノードを起動します。上の FIFO 設定を使うには、Raspberry Pi 4 側ユーザーにリアルタイム優先度を設定する権限が必要です。インストールされる launch ファイルは patch 適用済みの `urg_node2` サブモジュールから取得され、`urg_lidar_app/launch` 内のファイルはこのビルドではインストールされません。

Raspberry Pi 4 の別のシェルでも同じ ROS ドメインと探索設定を指定して確認します。

```bash
source /opt/ros/jazzy/setup.bash
source "$HOME/urg-node2-jazzy-arm64/install/local_setup.bash"
export ROS_DOMAIN_ID=203 ROS_AUTOMATIC_DISCOVERY_RANGE=LOCALHOST
ros2 service call /urg_node2/get_state lifecycle_msgs/srv/GetState '{}'
ros2 topic hz /scan
```

- urg_node2 と Realtime Support を未変更の状態から用意し、mimick_vendor のない sysroot で両方の patch の自動適用と AArch64 クロスビルドを確認しました。

- 成果物を Ubuntu 24.04・ROS 2 Jazzy の Raspberry Pi 4 で起動し、LiDAR（`192.168.0.10:10940`）へ接続、ライフサイクル `active`、`/scan` の受信を確認しました。
- executor は FIFO 優先度 10、スキャンスレッドは FIFO 優先度 20 で動作し、約12秒間の `/scan` 観測で平均約39.8 Hz でした。
