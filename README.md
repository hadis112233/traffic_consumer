# 流量消耗器 (Traffic Consumer)

一个简单高效的流量消耗工具，用于测试网络带宽和流量消耗。支持命令行模式和Web UI模式。
## 目录

- [功能特点](#功能特点)
- [安装与使用](#安装与使用)
  - [Docker 部署（推荐）](#docker-部署推荐)
    - [拉取镜像](#拉取镜像)
    - [运行容器](#运行容器)
    - [管理容器](#管理容器)
    - [数据持久化](#数据持久化)
  - [本地运行](#本地运行)
- [命令行参数](#命令行参数)
- [Web UI 使用指南](#web-ui-使用指南)
- [使用示例](#使用示例)
- [配置管理](#配置管理)
- [从源码构建](#从源码构建)
- [贡献](#贡献)
- [注意事项](#注意事项)
- [许可证](#许可证)


## 功能特点

- **双模式操作**: 支持传统的命令行界面和全新的Web UI界面。
- **Web UI**: 通过浏览器轻松配置和监控流量消耗任务，实时查看状态、日志和线程详情。
- **多线程下载**: 默认8线程，可自定义线程数。
- **多URL支持**: 支持多个下载源，提高稳定性和速度。
- **智能URL选择**: 支持随机和轮询两种URL选择策略。
- **内存下载**: 不缓存到硬盘，纯内存操作。
- **速度控制**: 可配置下载速度限制。
- **流量统计**: 实时显示流量消耗和URL使用情况。
- **定时执行**: 支持Cron表达式和间隔时间。
- **灵活控制**: 支持设置持续时间、下载次数或流量限制。
- **配置管理**: 保存和加载配置，支持多套配置方案。
- **跨平台**: 支持Windows和Linux平台。
- **Docker部署**: 提供Docker镜像，一键部署。

## 安装与使用

### Docker 部署（推荐）

使用Docker是部署和运行流量消耗器最简单的方法。

#### 拉取镜像

```bash
docker pull baitaotao521/traffic_consumer:latest
```

#### 运行容器

**Web UI 模式 (默认)**

```bash
# 运行并在后台启动，将容器的5001端口映射到主机的5001端口
docker run -d -p 5001:5001 --name traffic_consumer baitaotao521/traffic_consumer

# 然后在浏览器中打开 http://主机ip:5001
```

**命令行模式**

```bash
# 使用 --no-gui 参数启动命令行模式
docker run -d --name traffic_consumer_cli baitaotao521/traffic_consumer --no-gui
```

#### 管理容器

- **查看日志**:
  ```bash
  # 实时查看Web UI模式的日志
  docker logs -f traffic_consumer

  # 实时查看命令行模式的日志
  docker logs -f traffic_consumer_cli
  ```

- **停止容器**:
  ```bash
  docker stop traffic_consumer
  ```

- **启动容器**:
  ```bash
  docker start traffic_consumer
  ```

- **删除容器**:
  ```bash
  # 删除前请先停止容器
  docker rm traffic_consumer
  ```

#### 数据持久化

默认情况下，容器内的配置和统计数据是临时的，当容器被删除后数据会丢失。为了持久化保存数据，您可以将主机的目录挂载到容器的 `/root/.traffic_consumer` 目录。

```bash
# 在Linux/macOS上创建本地目录
mkdir -p ~/.traffic_consumer_data

# 在Windows (PowerShell)上创建本地目录
New-Item -ItemType Directory -Force -Path $HOME\.traffic_consumer_data

# 运行时挂载该目录 (示例为Linux/macOS)
docker run -d -p 5001:5001 \
  -v ~/.traffic_consumer_data:/root/.traffic_consumer \
  --name traffic_consumer_persistent \
  baitaotao521/traffic_consumer
```
> **Windows用户请注意**:
> 在 `cmd` 中，使用 `%USERPROFILE%\.traffic_consumer_data` 代替 `~/.traffic_consumer_data`。
> 在 `PowerShell` 中，使用 `$HOME\.traffic_consumer_data`。

这样，即使容器被删除和重建，您的配置和历史统计数据依然会保留在本地目录中。

### 本地运行

#### 1. 克隆仓库

```bash
git clone https://github.com/baitaotao521/traffic_consumer.git
cd traffic_consumer
```

#### 2. 安装依赖

```bash
pip install -r requirements.txt
```

#### 3. 运行

**Web UI 模式 (默认)**

```bash
python traffic_consumer.py
# 在浏览器中打开 http://127.0.0.1:5001
```

**命令行模式**

```bash
python traffic_consumer.py --no-gui [其他参数]
```

## 命令行参数

```
usage: traffic_consumer.py [-h] [-u URLS [URLS ...]] [--url-strategy {random,round_robin}] [-t THREADS] [-l LIMIT] [-d DURATION] [-c COUNT] [--cron CRON] [--traffic-limit TRAFFIC_LIMIT] [--interval INTERVAL] [--config CONFIG] [--save-config]
                           [--load-config] [--list-configs] [--delete-config] [--show-stats] [--stats-limit STATS_LIMIT] [--no-gui]

流量消耗器 - 用于测试网络带宽和流量消耗

options:
  -h, --help            show this help message and exit
  -u URLS [URLS ...], --urls URLS [URLS ...]
                        要下载的URL列表，可以指定多个URL (默认: 使用内置的2个测试URL)
  --url-strategy {random,round_robin}
                        URL选择策略: random(随机选择) 或 round_robin(轮询选择) (默认: random)
  -t THREADS, --threads THREADS
                        下载线程数 (默认: 8)
  -l LIMIT, --limit LIMIT
                        下载速度限制，单位MB/s，0表示不限速 (默认: 0)
  -d DURATION, --duration DURATION
                        持续时间，单位秒 (默认: 无限制)
  -c COUNT, --count COUNT
                        下载次数 (默认: 无限制)
  --cron CRON           Cron表达式，格式: '分 时 日 月 周'，例如: '0 * * * *' 表示每小时执行一次
  --traffic-limit TRAFFIC_LIMIT
                        流量限制，单位MB (默认: 无限制)
  --interval INTERVAL   间隔执行时间，单位分钟，例如: 60 表示每60分钟执行一次 (默认: 无限制)
  --config CONFIG       配置名称 (默认: default)
  --save-config         保存当前配置
  --load-config         加载指定配置
  --list-configs        列出所有保存的配置
  --delete-config       删除指定配置
  --show-stats          显示历史统计数据
  --stats-limit STATS_LIMIT
                        显示的历史统计数据条数 (默认: 5)
  --no-gui              不启动Web UI，仅使用命令行
```

## Web UI 使用指南

Web UI 提供了一个美观且功能强大的图形化界面，让您可以更直观地配置和监控流量消耗任务。界面主要分为左右两个部分。

![Web UI Screenshot](https://raw.githubusercontent.com/baitaotao521/traffic_consumer/main/screenshots/web_ui_overview.png)

### 左侧：核心仪表盘

这是任务控制和状态监控的核心区域。

-   **状态**: 显示任务是“运行中”还是“已停止”。
-   **实时数据**:
    -   **实时速度**: 当前总下载速度。
    -   **总消耗**: 本次任务已消耗的总流量。
    -   **下载数**: 已完成的下载请求次数。
-   **配置加载**:
    -   通过下拉菜单快速选择并加载已保存的配置。
-   **控制按钮**:
    -   **启动**: 使用当前选定或编辑器中的配置来启动任务。
    -   **停止**: 立即停止当前正在运行的任务。
    -   **停止计划**: 如果任务是通过调度器（Cron或间隔）启动的，此按钮可以停止未来的计划任务，但不会影响当前正在运行的任务。

### 右侧：信息中心

右侧包含一个实时速度图和带有多个选项卡的信息面板。

#### 1. 实时速度图

一个动态图表，可视化展示最近30秒的下载速度变化趋势。

#### 2. 信息选项卡

-   **调度与历史**:
    -   **调度状态**: 查看当前是否有计划任务，以及下次运行的时间和倒计时。
    -   **执行历史**: 一个可滚动的表格，显示最近50次任务的执行记录，包括时间、结果和消耗的流量。

-   **配置编辑器**:
    这是创建和修改任务配置的核心区域，布局清晰，分为几个部分：
    -   **配置名称**: 为您的配置命名，方便保存和识别。
    -   **URLs**: 输入一个或多个下载链接，每行一个。
    -   **基础设置**:
        -   **线程数**: 设置并发下载的线程数量。
        -   **限速 (MB/s)**: 设置总下载速度上限，0表示无限制。
    -   **停止条件 (任一满足即停止)**:
        -   **流量 (MB)**: 任务消耗的总流量上限。
        -   **时长 (秒)**: 任务运行的总时长。
        -   **下载数**: 总下载文件次数。
    -   **调度设置 (二选一)**:
        -   **间隔 (分钟)**: 设置任务循环执行的间隔。
        -   **Cron 表达式**: 使用Cron语法设置更灵活的定时启动，提供常用预设和实时预览功能。
    -   **保存配置**: 点击按钮将当前编辑器中的配置保存起来。

-   **实时日志**:
    一个强大的日志查看器，用于调试和监控任务的详细过程。
    -   **日志开关**: 默认关闭，需要手动开启才会从后端接收并显示日志，以节省浏览器资源。
    -   **彩色输出**: 能够解析并显示带有 ANSI 颜色的日志，使输出更具可读性。
    -   **自动滚动**: 新的日志会自动显示在底部，并使面板滚动到最新位置。
    -   **清空按钮**: 快速清除所有日志。
    -   **日志条数限制**: 为了防止浏览器卡顿，最多保留最新的200条日志。

## 使用示例

### 示例 1: 限制速度和时长

以最大 5 MB/s 的速度下载10分钟。

```bash
python traffic_consumer.py --limit 5 --duration 600
```

### 示例 2: 使用指定的URL列表和轮询策略

使用您自己的两个URL，并采用轮询方式选择。

```bash
python traffic_consumer.py --urls http://example.com/file1.zip http://example.com/file2.zip --url-strategy round_robin
```

### 示例 3: 保存配置

将当前参数保存为一个名为 `daily_test` 的配置。

```bash
python traffic_consumer.py -t 16 -l 10 --save-config --config daily_test
# 这将保存一个16线程、10MB/s限速的配置，但不会立即运行。
```

### 示例 4: 加载并运行配置

加载 `daily_test` 配置并立即开始任务。

```bash
python traffic_consumer.py --load-config --config daily_test
```

### 示例 5: 定时任务

每天凌晨3点执行任务。

> **常用 Cron 表达式推荐**:
> - `0 * * * *` - 每小时的第0分钟执行 (即每小时整点)。
> - `*/30 * * * *` - 每30分钟执行一次。
> - `0 0 * * *` - 每天凌晨0点0分执行。
> - `0 9-17 * * 1-5` - 周一至周五，上午9点到下午5点，每小时的第0分钟执行。
> - `0 0 1 * *` - 每月1号的凌晨0点0分执行。
>
> 您可以根据自己的需求调整这些表达式。

```bash
python traffic_consumer.py --load-config --config daily_test --cron "0 3 * * *"
```

## 配置管理

该工具支持保存和加载多套配置方案，方便在不同测试场景下快速切换。

-   **配置文件位置**: 所有配置和历史数据都保存在用户主目录下的 `.traffic_consumer` 文件夹内。
    -   配置文件: `~/.traffic_consumer/configs.json`
    -   统计数据: `~/.traffic_consumer/stats.json`
-   **保存配置**: 使用 `--save-config` 会将命令行中提供的其他参数（如 `-t`, `-l`）以 `--config` 指定的名称保存。
-   **加载配置**: 使用 `--load-config` 会加载指定名称的配置并覆盖命令行中的其他参数。
-   **列出配置**: 使用 `--list-configs` 查看所有已保存的配置名称。
-   **删除配置**: 使用 `--delete-config` 删除一个指定的配置。

## 从源码构建

如果您想自行构建可执行文件或Docker镜像，请参考构建指南。

-   **构建指南**: [`BUILD_GUIDE.md`](./BUILD_GUIDE.md)

## 贡献

欢迎任何形式的贡献！

1.  **报告问题**: 如果您发现任何错误或有功能建议，请随时[创建 Issue](https://github.com/baitaotao521/traffic_consumer/issues)。
2.  **提交代码**:
    -   Fork 本仓库。
    -   创建您的功能分支 (`git checkout -b feature/AmazingFeature`)。
    -   提交您的更改 (`git commit -m 'Add some AmazingFeature'`)。
    -   将分支推送到远程 (`git push origin feature/AmazingFeature`)。
    -   创建 Pull Request。

## 注意事项

1.  该工具会消耗大量网络流量，请确保您有足够的流量配额。
2.  长时间运行可能会导致设备发热，请注意设备温度。
3.  请合理使用，避免对网络造成不必要的负担。
4.  配置文件和统计数据保存在用户主目录的`.traffic_consumer`文件夹中。

## 许可证

MIT