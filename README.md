# 流量消耗器 (Traffic Consumer)

一个简单高效的流量消耗工具，用于测试网络带宽和流量消耗。

## 功能特点

- **多线程下载**：默认8线程，可自定义线程数
- **多URL支持**：支持多个下载源，提高稳定性和速度
- **智能URL选择**：支持随机和轮询两种URL选择策略
- **固定界面显示**：实时更新状态，不滚动日志，界面清晰
- **内存下载**：不缓存到硬盘，纯内存操作
- **速度控制**：可配置下载速度限制
- **流量统计**：实时显示流量消耗和URL使用情况
- **定时执行**：支持Cron表达式和间隔时间
- **灵活控制**：支持设置持续时间、下载次数或流量限制
- **配置管理**：保存和加载配置，支持多套配置方案
- **跨平台**：支持Windows和Linux平台
- **Docker部署**：提供Docker镜像，一键部署

## 安装

### Docker 部署（推荐）

使用Docker是部署和运行流量消耗器最简单的方法，无需担心环境依赖问题。

#### 从Docker Hub拉取镜像

```bash
docker pull baitaotao521/traffic_consumer:latest
```

#### 运行Docker容器

```bash
docker run -d --name traffic_consumer baitaotao521/traffic_consumer
```

默认参数为 `--threads 8`。如需自定义参数，可以在运行命令后添加：

```bash
docker run -d --name traffic_consumer baitaotao521/traffic_consumer --threads 16 --limit 2
```

#### Docker使用示例

以下是一些使用Docker运行流量消耗器的常用示例：

| 示例 | 命令 | 说明 |
|------|------|------|
| **默认启动** | `docker run -d --name tc baitaotao521/traffic_consumer` | 使用默认设置启动，无限流量消耗 |
| **指定多个URL** | `docker run -d --name tc baitaotao521/traffic_consumer -u "url1" "url2" "url3"` | 使用自定义的多个URL,(默认随机选择) |
| **轮询策略** | `docker run -d --name tc baitaotao521/traffic_consumer --url-strategy round_robin` | 线程轮流使用不同URL |
| **随机策略** | `docker run -d --name tc baitaotao521/traffic_consumer random` | 智能随机选择URL（默认） |
| **多线程下载** | `docker run -d --name tc baitaotao521/traffic_consumer --threads 16` | 使用16个线程下载 |
| **限制下载速度** | `docker run -d --name tc baitaotao521/traffic_consumer --limit 1` | 限制下载速度为1MB/s |
| **流量限制** | `docker run -d --name tc baitaotao521/traffic_consumer --traffic-limit 100` | 消耗100MB流量后自动停止 |
| **限时运行** | `docker run -d --name tc baitaotao521/traffic_consumer --duration 600` | 运行10分钟后自动停止 |
| **查看容器日志** | `docker logs -f tc` | 查看实时流量消耗情况 |
| **停止容器** | `docker stop tc` | 停止流量消耗 |
| **重启容器** | `docker restart tc` | 重新开始流量消耗 |
| **删除容器** | `docker rm tc` | 删除流量消耗容器 |


## 具体说明(以linux预编译版本为例,参数docker版通用)

### 基本使用

最简单的使用方式是直接运行可执行文件：

```bash
./traffic_consumer
```

如果已将可执行文件移动到系统路径，可以直接使用：

```bash
traffic_consumer
```

这将使用默认设置启动流量消耗器：
- URLs: 4个内置测试URL（包括Cloudflare、OVH等测试文件）
- URL选择策略: 随机选择（智能加权，确保分布均匀）
- 线程数: 8
- 不限速
- 固定界面显示，实时更新状态
- 无限制运行，直到手动停止(Ctrl+C)

| 示例 | 命令 | 说明 |
|------|------|------|
| **默认启动** | `./traffic_consumer` | 使用4个内置URL，随机策略，8线程，固定界面显示 |
| **指定多个URL** | `./traffic_consumer -u "url1" "url2" "url3"` | 使用自定义的多个URL |
| **轮询策略** | `./traffic_consumer --url-strategy round_robin` | 线程轮流使用不同URL |
| **随机策略** | `./traffic_consumer --url-strategy random` | 智能随机选择URL（默认） |
| **多线程下载** | `./traffic_consumer -t 16` | 使用16个线程下载，固定界面显示线程状态 |
| **低线程下载** | `./traffic_consumer -t 4` | 使用4个线程下载，适合网络条件较差的环境 |
| **限制下载速度** | `./traffic_consumer -l 1` | 限制下载速度为1MB/s，实时显示速度 |
| **高速下载** | `./traffic_consumer -l 10` | 限制下载速度为10MB/s，适合测试高速网络 |
| **限时运行** | `./traffic_consumer -d 600` | 运行10分钟后自动停止 |
| **短时测试** | `./traffic_consumer -d 60` | 运行1分钟后自动停止，适合快速测试 |
| **限制下载次数** | `./traffic_consumer -c 100` | 下载100次后自动停止，显示URL使用统计 |
| **组合使用** | `./traffic_consumer -t 8 -c 50 --url-strategy round_robin` | 8线程，轮询策略，50次后停止 |

### 命令行参数

```
usage: traffic_consumer [-h] [-u URLS [URLS ...]] [--url-strategy {random,round_robin}]
                        [-t THREADS] [-l LIMIT] [-d DURATION] [-c COUNT] [--cron CRON]
                        [--traffic-limit TRAFFIC_LIMIT] [--interval INTERVAL]
                        [--config CONFIG] [--save-config] [--load-config] [--list-configs] [--delete-config]
                        [--show-stats] [--stats-limit STATS_LIMIT]

流量消耗器 - 用于测试网络带宽和流量消耗

主要参数:
  -h, --help            显示帮助信息并退出
  -u URLS [URLS ...], --urls URLS [URLS ...]
                        要下载的URL列表，可以指定多个URL (默认: 使用内置的4个测试URL)
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
                        流量限制，单位MB，达到后停止 (默认: 无限制)
  --interval INTERVAL   间隔执行时间，单位分钟，例如: 60 表示每60分钟执行一次 (默认: 无限制)

配置管理:
  --config CONFIG       配置名称 (默认: default)
  --save-config         保存当前配置
  --load-config         加载指定配置
  --list-configs        列出所有保存的配置
  --delete-config       删除指定配置

统计数据:
  --show-stats          显示历史统计数据
  --stats-limit STATS_LIMIT
                        显示的历史统计数据条数 (默认: 5)
```

## 使用示例

### 目录
- [基本使用](#基本使用)
- [多URL和策略](#多url和策略)
- [流量控制](#流量控制)
- [定时执行](#定时执行)
- [配置管理](#配置管理)
- [统计数据](#统计数据)
- [高级示例](#高级示例)

---

### 基本使用

| 示例 | 命令 | 说明 |
|------|------|------|
| **默认启动** | `./traffic_consumer` | 使用内置URL，随机策略，8线程，固定界面显示 |
| **多线程下载** | `./traffic_consumer -t 16` | 使用16个线程下载，实时显示每个线程状态 |
| **低线程下载** | `./traffic_consumer -t 4` | 使用4个线程下载，适合网络条件较差的环境 |
| **限制下载速度** | `./traffic_consumer -l 1` | 限制下载速度为1MB/s，实时显示速度 |
| **高速下载** | `./traffic_consumer -l 10` | 限制下载速度为10MB/s，适合测试高速网络 |
| **限时运行** | `./traffic_consumer -d 600` | 运行10分钟后自动停止 |
| **短时测试** | `./traffic_consumer -d 60` | 运行1分钟后自动停止，适合快速测试 |
| **限制下载次数** | `./traffic_consumer -c 100` | 下载100次后自动停止，显示URL使用统计 |

---

### 多URL和策略

| 示例 | 命令 | 说明 |
|------|------|------|
| **指定单个URL** | `./traffic_consumer -u "https://example.com/file.zip"` | 使用单个自定义URL |
| **指定多个URL** | `./traffic_consumer -u "url1" "url2" "url3"` | 使用多个自定义URL |
| **随机策略** | `./traffic_consumer --url-strategy random` | 智能随机选择URL，确保分布均匀（默认） |
| **轮询策略** | `./traffic_consumer --url-strategy round_robin` | 线程按顺序轮流使用不同URL |
| **多URL+轮询** | `./traffic_consumer -u "url1" "url2" --url-strategy round_robin -t 4` | 4个线程轮流使用2个URL |
| **多URL+随机** | `./traffic_consumer -u "url1" "url2" "url3" --url-strategy random -c 20` | 随机选择3个URL，下载20次后显示使用统计 |
| **测试URL分布** | `./traffic_consumer -c 50 --url-strategy random` | 下载50次，查看随机策略的URL分布情况 |

---

### 流量控制

| 示例 | 命令 | 说明 |
|------|------|------|
| **限制流量消耗** | `./traffic_consumer --traffic-limit 100` | 消耗100MB流量后自动停止 |
| **小流量测试** | `./traffic_consumer --traffic-limit 10` | 消耗10MB流量后自动停止，适合快速测试 |
| **高速消耗特定流量** | `./traffic_consumer -t 16 -l 0 --traffic-limit 500` | 16线程，不限速，消耗500MB后停止 |
| **限制流量消耗(GB级别)** | `./traffic_consumer --traffic-limit 1024` | 消耗1GB流量后自动停止 |
| **限速+流量限制** | `./traffic_consumer -l 2 --traffic-limit 200` | 限速2MB/s，消耗200MB流量后停止 |
| **精确流量控制** | `./traffic_consumer -t 1 -l 1 --traffic-limit 50` | 单线程，限速1MB/s，消耗50MB后停止，适合精确控制流量 |

---

### 定时执行

| 示例 | 命令 | 说明 |
|------|------|------|
| **间隔执行** | `./traffic_consumer --interval 30` | 每30分钟执行一次，每次无限流量消耗 |
| **短间隔执行** | `./traffic_consumer --interval 5` | 每5分钟执行一次，适合频繁测试网络状态 |
| **间隔执行+次数限制** | `./traffic_consumer --interval 60 -c 100` | 每小时执行一次，每次下载100次后停止 |
| **间隔执行+流量限制** | `./traffic_consumer --interval 30 --traffic-limit 50` | 每30分钟消耗50MB流量，达到后自动停止，等待下一次执行 |
| **间隔执行+限速** | `./traffic_consumer --interval 15 -l 2` | 每15分钟执行一次，限速2MB/s |
| **实时显示执行状态** | `./traffic_consumer --interval 1 --traffic-limit 20` | 实时显示当前状态和下一次执行的倒计时 |
| **Cron表达式** | `./traffic_consumer --cron "0 * * * *"` | 使用Cron表达式定时执行，每小时执行一次 |
| **每日定时任务** | `./traffic_consumer --cron "0 2 * * *" --traffic-limit 200` | 每天凌晨2点执行，每次消耗200MB后停止 |
| **工作日定时任务** | `./traffic_consumer --cron "0 9-18 * * 1-5" --traffic-limit 100 -l 2` | 工作日每小时消耗100MB流量，限速为2MB/s |
| **周末定时任务** | `./traffic_consumer --cron "0 10-20 * * 0,6" --traffic-limit 500` | 周末10点到20点每小时消耗500MB流量 |
| **每30分钟执行** | `./traffic_consumer --cron "*/30 * * * *"` | 每30分钟执行一次，使用Cron表达式 |

---

### 配置管理

| 示例 | 命令 | 说明 |
|------|------|------|
| **保存配置** | `./traffic_consumer -t 16 -l 1000 --config "高速下载" --save-config` | 保存当前配置为"高速下载" |
| **加载配置** | `./traffic_consumer --config "高速下载" --load-config` | 加载名为"高速下载"的配置 |
| **列出所有配置** | `./traffic_consumer --list-configs` | 查看所有保存的配置列表 |
| **保存定时任务配置** | `./traffic_consumer --interval 60 --traffic-limit 200 -t 16 --config "hourly_task" --save-config` | 创建定时流量消耗任务并保存为配置 |
| **删除配置** | `./traffic_consumer --config "测试配置" --delete-config` | 删除名为"测试配置"的配置 |
| **保存低速配置** | `./traffic_consumer -t 4 -l 0.5 --config "低速下载" --save-config` | 保存低速下载配置 |

---

### 统计数据

| 示例 | 命令 | 说明 |
|------|------|------|
| **查看历史统计** | `./traffic_consumer --show-stats` | 显示历史流量消耗统计数据 |
| **指定显示数量** | `./traffic_consumer --show-stats --stats-limit 10` | 显示最近10条历史统计记录 |
| **查看详细统计** | `./traffic_consumer --show-stats --stats-limit 3` | 显示最近3条历史统计记录的详细信息 |

---

### 高级示例

以下是一些高级示例，展示如何组合使用多个参数来满足复杂需求：

#### 精确流量控制方案

```bash
# 工作日白天每小时消耗100MB流量，限速2MB/s，使用轮询策略，实时显示状态
./traffic_consumer --cron "0 9-18 * * 1-5" --traffic-limit 100 -l 2 -t 8 --url-strategy round_robin --config "workday_hourly" --save-config
```

#### 多URL负载均衡方案

```bash
# 使用多个CDN源，随机策略确保负载均衡
./traffic_consumer -u "https://speed.cloudflare.com/__down?bytes=100000000" \
                      "https://proof.ovh.net/files/100Mb.dat" \
                      "https://download.thinkbroadband.com/100MB.zip" \
                   --url-strategy random -t 12 --traffic-limit 500 --config "multi_cdn" --save-config

# 使用轮询策略确保每个URL都被均匀使用
./traffic_consumer -u "https://mirror1.example.com/testfile" \
                      "https://mirror2.example.com/testfile" \
                      "https://mirror3.example.com/testfile" \
                   --url-strategy round_robin -t 9 -c 100 --config "mirror_test" --save-config
```

#### 网络负载测试方案

```bash
# 每天不同时段使用不同配置
# 早上6点：低负载测试
./traffic_consumer --cron "0 6 * * *" --traffic-limit 50 -l 1 -t 4 --config "morning_test" --save-config

# 中午12点：中等负载测试
./traffic_consumer --cron "0 12 * * *" --traffic-limit 200 -l 5 -t 8 --config "noon_test" --save-config

# 晚上8点：高负载测试
./traffic_consumer --cron "0 20 * * *" --traffic-limit 500 -l 0 -t 16 --config "evening_test" --save-config
```

#### 间歇性网络压力测试

```bash
# 每30分钟高强度消耗50MB流量，使用16线程不限速
./traffic_consumer --interval 30 --traffic-limit 50 -t 16 -l 0 --config "burst_test" --save-config
```

#### 全天候网络监控方案

```bash
# 白天：每15分钟消耗10MB流量，限速1MB/s
./traffic_consumer --cron "*/15 8-20 * * *" --traffic-limit 10 -l 1 --config "daytime_monitor" --save-config

# 夜间：每小时消耗5MB流量，限速0.5MB/s
./traffic_consumer --cron "0 21-7 * * *" --traffic-limit 5 -l 0.5 --config "nighttime_monitor" --save-config
```

#### 组合所有参数的超级示例

```bash
# 工作日：每30分钟消耗100MB流量，限速2MB/s，使用12线程
# 周末：每小时消耗200MB流量，不限速，使用16线程
# 所有配置保存为"weekly_plan"

# 工作日配置 - 使用轮询策略确保URL均匀分布
./traffic_consumer --cron "*/30 9-18 * * 1-5" --traffic-limit 100 -l 2 -t 12 \
                   -u "https://cdn1.example.com/test" "https://cdn2.example.com/test" \
                   --url-strategy round_robin --config "workday_config" --save-config

# 周末配置 - 使用随机策略和更多URL源
./traffic_consumer --cron "0 10-22 * * 0,6" --traffic-limit 200 -l 0 -t 16 \
                   -u "https://cdn1.example.com/test" "https://cdn2.example.com/test" "https://cdn3.example.com/test" \
                   --url-strategy random --config "weekend_config" --save-config
```

#### 大流量消耗示例

```bash
# 每天0点开始消耗10TB流量（10,240,000MB）
# 警告：这将消耗极大量的网络流量，请确保您有足够的流量配额和网络带宽
# 建议：使用32个线程，不限速，以最快速度完成任务

./traffic_consumer --cron "0 0 * * *" --traffic-limit 10240000 -t 32 -l 0 --config "daily_10tb" --save-config

# 如果需要限制速度，可以设置一个较高的限速值，例如50MB/s
./traffic_consumer --cron "0 0 * * *" --traffic-limit 10240000 -t 32 -l 50 --config "daily_10tb_limited" --save-config

# 如果需要分批次完成，可以设置每小时消耗1TB
./traffic_consumer --cron "0 0-9 * * *" --traffic-limit 1024000 -t 32 -l 0 --config "hourly_1tb" --save-config
```

---

## 注意事项

1. 该工具会消耗大量网络流量，请确保您有足够的流量配额
2. 长时间运行可能会导致设备发热，请注意设备温度
3. 请合理使用，避免对网络造成不必要的负担
4. 定时任务会在后台运行，可以使用Ctrl+C随时停止
5. 流量限制达到后，程序会自动停止当前下载并等待下一次执行
6. Linux版本的可执行文件已针对性能进行了优化，可能比源代码版本运行更高效
7. 配置文件和统计数据保存在用户主目录的`.traffic_consumer`文件夹中

## Linux系统下的高级用法

### 后台运行

使用nohup命令可以让程序在后台运行，即使关闭终端也不会停止：

```bash
nohup ./traffic_consumer --traffic-limit 1000 &
```

查看nohup输出：

```bash
cat nohup.out
```

### 设置为系统服务

1. 创建服务文件：

```bash
sudo nano /etc/systemd/system/traffic-consumer.service
```

2. 添加以下内容：

```
[Unit]
Description=Traffic Consumer Service
After=network.target

[Service]
Type=simple
User=your_username
ExecStart=/path/to/traffic_consumer --config "your_config" --load-config //替换为具体目录
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. 启用并启动服务：

```bash
sudo systemctl enable traffic-consumer.service
sudo systemctl start traffic-consumer.service
```

4. 查看服务状态：

```bash
sudo systemctl status traffic-consumer.service
```

## 许可证

MIT