#!/usr/bin/env python
# -*- coding: utf-8 -*-

import warnings
warnings.filterwarnings("ignore", category=UserWarning, module='apscheduler')

"""
流量消耗器 - 用于测试网络带宽和流量消耗

使用示例:
1. 基本使用 - 使用默认多个URL消耗无限流量:
   python traffic_consumer.py

2. 指定多个URL:
   python traffic_consumer.py -u "https://example1.com/file" "https://example2.com/file"

3. 设置URL选择策略:
   python traffic_consumer.py --url-strategy random  # 随机选择URL
   python traffic_consumer.py --url-strategy round_robin  # 轮询选择URL

4. 限制下载次数:
   python traffic_consumer.py -c 100  # 下载100次后停止

5. 限制流量:
   python traffic_consumer.py --traffic-limit 100  # 消耗100MB流量后停止

6. 限制速度:
   python traffic_consumer.py -l 1  # 限制速度为1MB/s

7. 定时执行 - 使用cron表达式:
   python traffic_consumer.py --cron "*/30 * * * *"  # 每30分钟执行一次

8. 定时执行 - 使用间隔时间:
   python traffic_consumer.py --interval 60  # 每60分钟执行一次

9. 组合使用:
   python traffic_consumer.py --traffic-limit 50 --interval 30 --url-strategy round_robin

10. 保存配置:
    python traffic_consumer.py --traffic-limit 100 -l 2 --config "daily_task" --save-config

11. 加载配置:
    python traffic_consumer.py --config "daily_task" --load-config

12. 查看所有配置:
    python traffic_consumer.py --list-configs

13. 查看历史统计:
    python traffic_consumer.py --show-stats
"""

import requests
import threading
import time
import argparse
import sys
import os
import json
import signal
import random
from tqdm import tqdm
from colorama import Fore, Style, init
from datetime import datetime, timedelta, timezone
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
import http.client  # 添加导入http.client模块
from requests.exceptions import ChunkedEncodingError, RequestException, Timeout

# 初始化colorama
init(autoreset=True)

# 默认URL列表
DEFAULT_URLS = [
    "https://img.mcloud.139.com/material_prod/material_media/20221128/1669626861087.png",
    # "https://yun.mcloud.139.com/mCloudPc/v832/mCloud_Setup-001.exe",
    "https://wxhls.mcloud.139.com/hls/M068756c0040acdfc2749d3e70b04f183d/single/video/0/1080/ts/000000.ts"
]

# 配置文件路径
CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".traffic_consumer")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
STATS_FILE = os.path.join(CONFIG_DIR, "stats.json")

DEFAULT_CHUNK_SIZE = 256 * 1024  # 256KB 默认分块大小


class RateLimiter:
    """简单的线程安全令牌桶限速器"""

    def __init__(self, rate_bytes_per_sec):
        self.rate = max(0, rate_bytes_per_sec)
        self.tokens = float(self.rate)
        self.last_refill = time.perf_counter()
        self.lock = threading.Lock()

    def acquire(self, num_bytes):
        if self.rate <= 0:
            return

        request_bytes = min(num_bytes, self.rate)

        while True:
            with self.lock:
                self._refill_tokens()

                if self.tokens >= request_bytes:
                    self.tokens -= request_bytes
                    return

                deficit = request_bytes - self.tokens

            sleep_time = deficit / self.rate
            time.sleep(min(sleep_time, 0.5))

    def _refill_tokens(self):
        now = time.perf_counter()
        elapsed = now - self.last_refill
        if elapsed <= 0:
            return

        refill = elapsed * self.rate
        self.tokens = min(self.rate, self.tokens + refill)
        self.last_refill = now

class TrafficConsumer:
    def __init__(self, urls=None, threads=1, limit_speed=0,
                 duration=None, count=None, cron_expr=None,
                 traffic_limit=None, interval=None,
                 config_name="default", url_strategy="random", logger=None, history_callback=None,
                 invalid_url_callback=None):
        self.urls = urls if urls else DEFAULT_URLS
        self.threads = threads if threads is not None else 1
        self.limit_speed = limit_speed if limit_speed is not None else 0  # 限速，单位MB/s，0表示不限速
        self.duration = duration  # 持续时间，单位秒
        self.count = count  # 下载次数
        self.cron_expr = cron_expr  # Cron表达式
        self.traffic_limit = traffic_limit  # 流量限制，单位MB
        self.interval = interval  # 间隔时间，单位分钟
        self.config_name = config_name if config_name else "default"
        self.url_strategy = url_strategy if url_strategy else "random"  # URL选择策略: "random" 或 "round_robin"
        self.logger = logger if logger else self._default_logger
        self.history_callback = history_callback
        self.invalid_url_callback = invalid_url_callback

        # 网络与控制参数
        self.connect_timeout = 10
        self.read_timeout = 30
        self.max_retries = 5
        self.retry_backoff = 1.5
        self.chunk_size = DEFAULT_CHUNK_SIZE
        self.rate_limiter = RateLimiter(int(self.limit_speed * 1024 * 1024)) if self.limit_speed > 0 else None
        self._traffic_limit_triggered = False
        self._count_limit_triggered = False
        self.invalid_urls = set()

        # 统计数据
        self.lock = threading.Lock()
        self.total_bytes = 0
        self.start_time = None
        self.active = False
        self.download_count = 0

        # 进度条
        self.progress_bar = None

        # 调度器
        self.scheduler = None

        # 历史统计数据
        self.history = []
        self.MAX_HISTORY_ENTRIES = 50  # 限制历史记录最大条数

        # 状态
        self.status = "初始化"
        self.next_run_time = None

        # URL轮询计数器
        self.url_counter = 0
        self.url_counter_lock = threading.Lock()

        # URL使用统计
        self.url_usage = {url: 0 for url in self.urls}

        # 线程当前使用的URL
        self.thread_current_urls = {}

        # 加权随机选择器 - 确保URL分布更均匀
        self.url_weights = [1.0] * len(self.urls)  # 初始权重相等
        self.weight_lock = threading.Lock()

        # 线程URL分配记录（避免重复打印）
        self.thread_url_assignments = {}

    def _default_logger(self, message, color=None):
        if color:
            print(f"{color}{message}{Style.RESET_ALL}")
        else:
            print(message)
        
    def get_url_for_thread(self, thread_id):
        """为线程获取URL"""
        available_urls = self._get_available_urls()
        if not available_urls:
            return None

        if self.url_strategy == "random":
            return self.weighted_random_choice(available_urls)
        elif self.url_strategy == "round_robin":
            with self.url_counter_lock:
                for _ in range(len(self.urls)):
                    url = self.urls[self.url_counter % len(self.urls)]
                    self.url_counter += 1
                    if url in self.invalid_urls:
                        continue
                    return url
            # 如果轮询未命中有效URL，则回退到随机策略
            return self.weighted_random_choice(available_urls)
        else:
            return available_urls[0]  # 默认返回第一个有效URL

    def _get_available_urls(self):
        """获取仍然有效的URL列表"""
        with self.lock:
            return [url for url in self.urls if url not in self.invalid_urls]

    def weighted_random_choice(self, candidates):
        """加权随机选择URL，确保分布更均匀"""
        with self.weight_lock:
            # 计算当前使用次数
            total_usage = sum(self.url_usage.values())

            if total_usage == 0:
                # 如果还没有使用记录，完全随机选择
                return random.choice(candidates)

            # 计算期望的平均使用次数
            expected_avg = total_usage / len(self.urls) if self.urls else 0

            # 更新权重：使用次数越少的URL权重越高
            for i, url in enumerate(self.urls):
                current_usage = self.url_usage.get(url, 0)
                if url in self.invalid_urls:
                    self.url_weights[i] = 0.0
                    continue
                if expected_avg == 0:
                    self.url_weights[i] = 1.0
                    continue
                # 权重与使用次数成反比，使用次数少的URL权重更高
                if current_usage < expected_avg:
                    self.url_weights[i] = expected_avg - current_usage + 1
                else:
                    self.url_weights[i] = 1.0 / (current_usage - expected_avg + 1)

            weights = []
            for url in candidates:
                try:
                    idx = self.urls.index(url)
                    weights.append(self.url_weights[idx])
                except ValueError:
                    weights.append(1.0)

            # 根据权重进行随机选择
            return self.weighted_choice(candidates, weights)

    def weighted_choice(self, choices, weights):
        """根据权重进行随机选择"""
        total_weight = sum(weights)
        if total_weight == 0:
            return random.choice(choices)

        # 生成随机数
        r = random.uniform(0, total_weight)

        # 找到对应的选择
        cumulative_weight = 0
        for choice, weight in zip(choices, weights):
            cumulative_weight += weight
            if r <= cumulative_weight:
                return choice

        # 如果由于浮点数精度问题没有找到，返回最后一个
        return choices[-1]

    def download_file(self, thread_id):
        """单个线程的下载函数"""
        session = self._create_session()

        while self.active:
            if self.count is not None:
                with self.lock:
                    if self.download_count >= self.count:
                        self._stop_due_to_count()
                        break

            current_url = self.get_url_for_thread(thread_id)

            if current_url is None:
                self.logger("未找到可用的下载链接，任务将停止。", Fore.RED)
                with self.lock:
                    self.thread_current_urls[thread_id] = "无可用链接"
                self.active = False
                break

            with self.lock:
                self.thread_current_urls[thread_id] = current_url
                if current_url not in self.url_usage:
                    self.url_usage[current_url] = 0

            completed = self._download_with_retries(session, current_url, thread_id)

            if not self.active:
                break

            if completed:
                reached_count_limit = False
                with self.lock:
                    self.url_usage[current_url] += 1
                    self.download_count += 1
                    if self.count is not None and self.download_count >= self.count:
                        reached_count_limit = True

                if reached_count_limit:
                    self._stop_due_to_count()
                    break
            else:
                # 未完成意味着已触发限流或重试耗尽，循环将重新选择URL继续
                continue

        session.close()

    def _create_session(self):
        """创建针对下载场景优化的 Session"""
        session = requests.Session()
        session.headers.update({
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        })
        return session

    def _download_with_retries(self, session, url, thread_id):
        """带指数退避的重试下载"""
        attempt = 1
        backoff = self.retry_backoff

        while attempt <= self.max_retries and self.active:
            try:
                return self._stream_download(session, url)
            except (RequestException, Timeout, http.client.IncompleteRead, ChunkedEncodingError) as exc:
                if not self.active:
                    return False

                self.logger(
                    f"线程 {thread_id} 下载出错 (第{attempt}次尝试/{self.max_retries}): {exc}",
                    Fore.RED
                )

                if attempt >= self.max_retries:
                    self._mark_url_invalid(url, exc)
                    return False

                time.sleep(backoff)
                backoff = min(backoff * 2, 8.0)
                attempt += 1

        return False

    def _mark_url_invalid(self, url, error):
        """在重试耗尽后标记URL为无效并通知外部回调"""
        notify_callback = None
        payload = None

        with self.lock:
            if url in self.invalid_urls:
                return
            self.invalid_urls.add(url)
            for thread_id, assigned_url in list(self.thread_current_urls.items()):
                if assigned_url == url:
                    self.thread_current_urls[thread_id] = f"{url} (已失效)"
            all_invalid = len(self.invalid_urls) == len(self.urls)

        with self.weight_lock:
            if url in self.urls:
                try:
                    idx = self.urls.index(url)
                    self.url_weights[idx] = 0.0
                except ValueError:
                    pass

        summary = f"链接 {url} 连续失败超过 {self.max_retries} 次，已标记为无效。"
        if error:
            summary += f" 错误信息: {error}"
        self.logger(summary, Fore.RED)

        if self.invalid_url_callback:
            payload = {
                "url": url,
                "message": f"链接已连续失败 {self.max_retries} 次，已停止重试。",
                "retries": self.max_retries
            }
            if error:
                payload["error"] = str(error)
            notify_callback = self.invalid_url_callback

        if all_invalid:
            self.logger("所有下载链接均已失效，任务即将停止。", Fore.RED)
            self.active = False

        if notify_callback and payload:
            try:
                notify_callback(payload)
            except Exception as callback_exc:
                self.logger(f"通知前端无效链接时出错: {callback_exc}", Fore.YELLOW)

    def _stream_download(self, session, url):
        """执行一次流式下载，返回是否完整结束"""
        completed = True

        with session.get(
            url,
            stream=True,
            timeout=(self.connect_timeout, self.read_timeout)
        ) as response:
            response.raise_for_status()

            for chunk in response.iter_content(chunk_size=self.chunk_size):
                if not self.active:
                    completed = False
                    break

                if not chunk:
                    continue

                if self.rate_limiter:
                    self.rate_limiter.acquire(len(chunk))

                with self.lock:
                    self.total_bytes += len(chunk)

                if self._check_traffic_limit():
                    completed = False
                    break

        return completed

    def _check_traffic_limit(self):
        """检查是否达到流量限制"""
        if self.traffic_limit is None:
            return False

        limit_bytes = self.traffic_limit * 1024 * 1024

        with self.lock:
            if self._traffic_limit_triggered:
                return False

            if self.total_bytes < limit_bytes:
                return False

            self._traffic_limit_triggered = True

        self.logger(f"\n已达到流量限制 {self.traffic_limit} MB", Fore.YELLOW)

        if self.interval or self.cron_expr:
            self.status = "等待下次执行"
            self.logger("等待下次执行...", Fore.CYAN)
        else:
            self.logger("停止下载", Fore.YELLOW)

        self.active = False
        return True

    def _stop_due_to_count(self):
        """达到次数限制时的统一处理"""
        if self.count is None or self._count_limit_triggered:
            return

        self._count_limit_triggered = True
        self.logger(f"\n已达到下载次数限制 {self.count}", Fore.YELLOW)

        if self.interval or self.cron_expr:
            self.status = "等待下次执行"
            self.logger("等待下次执行...", Fore.CYAN)
        else:
            self.logger("停止下载", Fore.YELLOW)

        self.active = False
    
    def display_stats(self):
        """显示流量消耗统计信息"""
        last_bytes = 0

        # 清屏并显示初始界面
        self.clear_and_display_interface()

        while self.active:
            current_bytes = self.total_bytes
            elapsed_time = time.time() - self.start_time

            # 计算速度
            bytes_diff = current_bytes - last_bytes
            speed = bytes_diff / 1.0  # 1秒内的字节数

            # 转换单位
            total_str = self.format_bytes(current_bytes)
            speed_str = self.format_bytes(speed) + "/s"

            # 显示流量限制进度
            traffic_limit_str = ""
            if self.traffic_limit is not None:
                progress = min(100, self.total_bytes / (self.traffic_limit * 1024 * 1024) * 100)
                traffic_limit_str = f" | 流量限制: {progress:.1f}% ({total_str}/{self.format_bytes(self.traffic_limit * 1024 * 1024)})"

            # 更新固定显示界面
            self.update_display_interface(total_str, speed_str, traffic_limit_str, elapsed_time)

            # 记录历史数据点（每10秒记录一次）
            if int(elapsed_time) % 10 == 0 and int(elapsed_time) > 0:
                self.history.append({
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "bytes": current_bytes,
                    "speed": speed,
                    "elapsed_seconds": int(elapsed_time),
                    "download_count": self.download_count
                })

            last_bytes = current_bytes
            time.sleep(1)
        
        # 最终统计
        self.add_history_record("completed", self.total_bytes)
        self.save_stats()
        
        elapsed_time = time.time() - self.start_time
        avg_speed = self.total_bytes / elapsed_time if elapsed_time > 0 else 0
        
        avg_speed_str = self.format_bytes(avg_speed) + "/s"
            
        self.logger("\n\n=== 流量消耗统计 ===", Fore.CYAN)
        self.logger(f"总消耗流量: {self.format_bytes(self.total_bytes)}", Fore.CYAN)
        self.logger(f"平均速度: {avg_speed_str}", Fore.CYAN)
        self.logger(f"总运行时间: {timedelta(seconds=int(elapsed_time))}", Fore.CYAN)
        self.logger(f"总下载次数: {self.download_count}", Fore.CYAN)

        # 显示URL使用统计
        self.logger("\n=== URL使用统计 ===", Fore.CYAN)
        self.logger(f"URL选择策略: {self.url_strategy}", Fore.CYAN)
        for url, count in self.url_usage.items():
            percentage = (count / self.download_count * 100) if self.download_count > 0 else 0
            self.logger(f"  {url}: {count}次 ({percentage:.1f}%)", Fore.CYAN)

        self.logger(f"\n统计数据已保存到: {STATS_FILE}", Fore.CYAN)
        
        # 如果有下一次执行时间，显示它
        if self.next_run_time:
            next_run = self.next_run_time.strftime("%Y-%m-%d %H:%M:%S")
            self.logger(f"下一次执行时间: {next_run}", Fore.CYAN)

    def add_history_record(self, result, bytes_consumed):
        """添加一条历史记录"""
        record = {
            "timestamp": datetime.now().isoformat(),
            "result": result,
            "bytes_consumed": self.format_bytes(bytes_consumed),
            "download_count": self.download_count
        }
        self.history.insert(0, record) # 插入到开头
        # 限制历史记录的大小
        if len(self.history) > self.MAX_HISTORY_ENTRIES:
            self.history.pop()
        
        # 如果有回调，则调用它
        if self.history_callback:
            self.history_callback(record)

    def clear_and_display_interface(self):
        """清屏并显示固定界面"""
        # 清屏
        os.system('cls' if os.name == 'nt' else 'clear')

        # 显示标题和配置信息
        print(f"{Fore.CYAN}流量消耗器启动{Style.RESET_ALL}")
        print(f"{Fore.CYAN}URLs ({len(self.urls)}个): {Style.RESET_ALL}")
        for i, url in enumerate(self.urls, 1):
            print(f"{Fore.CYAN}  {i}. {url}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}URL选择策略: {self.url_strategy}{Style.RESET_ALL}")
        print(f"{Fore.CYAN}线程数: {self.threads}{Style.RESET_ALL}")

        if self.limit_speed > 0:
            print(f"{Fore.CYAN}限速: {self.limit_speed} MB/s{Style.RESET_ALL}")
        else:
            print(f"{Fore.CYAN}限速: 无限制{Style.RESET_ALL}")

        if self.duration:
            print(f"{Fore.CYAN}持续时间: {timedelta(seconds=self.duration)}{Style.RESET_ALL}")
        elif self.count:
            print(f"{Fore.CYAN}下载次数: {self.count}{Style.RESET_ALL}")
        elif self.traffic_limit:
            print(f"{Fore.CYAN}流量限制: {self.traffic_limit} MB{Style.RESET_ALL}")
        else:
            print(f"{Fore.CYAN}持续时间: 无限制 (按Ctrl+C停止){Style.RESET_ALL}")

    def update_display_interface(self, total_str, speed_str, traffic_limit_str, elapsed_time):
        """更新固定显示界面"""
        # 移动光标到线程状态显示区域
        self.logger(f"\n线程状态:", Fore.BLUE)

        # 显示每个线程当前使用的URL
        with self.lock:
            for thread_id in range(1, self.threads + 1):
                current_url = self.thread_current_urls.get(thread_id, "等待中...")
                self.logger(f"线程 {thread_id} 当前使用URL: {current_url}", Fore.BLUE)

        # 显示分隔线
        self.logger(f"\n{'=' * 50}", Fore.CYAN)

        # 显示统计信息
        self.logger(f"已消耗: {total_str} | 速度: {speed_str}{traffic_limit_str} | "
              f"运行时间: {timedelta(seconds=int(elapsed_time))} | "
              f"下载次数: {self.download_count}", Fore.GREEN)

        # 移动光标回到开始位置准备下次更新
        # 计算需要向上移动的行数（线程数 + 4行固定内容）
        lines_to_move_up = self.threads + 4
        # print(f"\033[{lines_to_move_up}A", end="")  # 向上移动光标

    def format_bytes(self, bytes_value):
        """格式化字节数为可读字符串"""
        if bytes_value < 1024:
            return f"{bytes_value:.2f} B"
        elif bytes_value < 1024 * 1024:
            return f"{bytes_value/1024:.2f} KB"
        elif bytes_value < 1024 * 1024 * 1024:
            return f"{bytes_value/(1024*1024):.2f} MB"
        else:
            return f"{bytes_value/(1024*1024*1024):.2f} GB"
    
    def save_stats(self):
        """保存统计数据到文件"""
        # 确保目录存在
        os.makedirs(os.path.dirname(STATS_FILE), exist_ok=True)
        
        # 读取现有数据
        stats_data = {}
        if os.path.exists(STATS_FILE):
            try:
                with open(STATS_FILE, 'r') as f:
                    stats_data = json.load(f)
            except:
                stats_data = {}
        
        # 添加新的统计数据
        run_id = datetime.now().strftime("%Y%m%d%H%M%S")
        stats_data[run_id] = {
            "config_name": self.config_name,
            "urls": self.urls,
            "url_strategy": self.url_strategy,
            "url_usage": self.url_usage,
            "threads": self.threads,
            "limit_speed": self.limit_speed,
            "start_time": datetime.fromtimestamp(self.start_time).strftime("%Y-%m-%d %H:%M:%S") if self.start_time else None,
            "end_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_bytes": self.total_bytes,
            "download_count": self.download_count,
            "elapsed_seconds": int(time.time() - self.start_time) if self.start_time else 0,
            "history": self.history
        }
        
        # 保存数据
        with open(STATS_FILE, 'w') as f:
            json.dump(stats_data, f, indent=2)
    
    def save_config(self):
        """保存当前配置到文件"""
        # 确保目录存在
        os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
        
        # 读取现有配置
        config_data = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    config_data = json.load(f)
            except:
                config_data = {}
        
        # 添加或更新配置
        config_data[self.config_name] = {
            "urls": self.urls,
            "url_strategy": self.url_strategy,
            "threads": self.threads,
            "limit_speed": self.limit_speed,
            "duration": self.duration,
            "count": self.count,
            "cron_expr": self.cron_expr,
            "traffic_limit": self.traffic_limit,
            "interval": self.interval
        }
        
        # 保存配置
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        print(f"{Fore.CYAN}配置 '{self.config_name}' 已保存{Style.RESET_ALL}")
    
    @staticmethod
    def load_config(config_name):
        """从文件加载配置"""
        if not os.path.exists(CONFIG_FILE):
            # print(f"{Fore.YELLOW}配置文件不存在，将使用默认配置{Style.RESET_ALL}")
            return None
        
        try:
            with open(CONFIG_FILE, 'r') as f:
                config_data = json.load(f)

            if config_name == '_all_':
                return config_data
            
            if config_name in config_data:
                config = config_data[config_name]
                # print(f"{Fore.CYAN}已加载配置 '{config_name}'{Style.RESET_ALL}")
                return config
            else:
                # print(f"{Fore.YELLOW}配置 '{config_name}' 不存在，将使用默认配置{Style.RESET_ALL}")
                return None
        except Exception as e:
            # print(f"{Fore.RED}加载配置出错: {e}{Style.RESET_ALL}")
            return None
    
    @staticmethod
    def list_configs():
        """列出所有保存的配置"""
        if not os.path.exists(CONFIG_FILE):
            print(f"{Fore.YELLOW}没有保存的配置{Style.RESET_ALL}")
            return
        
        try:
            with open(CONFIG_FILE, 'r') as f:
                config_data = json.load(f)
            
            if not config_data:
                print(f"{Fore.YELLOW}没有保存的配置{Style.RESET_ALL}")
                return
            
            print(f"{Fore.CYAN}=== 保存的配置 ==={Style.RESET_ALL}")
            for name, config in config_data.items():
                print(f"\n{Fore.GREEN}配置名称: {name}{Style.RESET_ALL}")
                # 兼容旧配置格式
                if 'urls' in config:
                    print(f"  URLs: {config['urls']}")
                    print(f"  URL策略: {config.get('url_strategy', 'random')}")
                elif 'url' in config:
                    print(f"  URL: {config['url']}")
                print(f"  线程数: {config['threads']}")
                print(f"  限速: {config['limit_speed']} MB/s (0表示不限速)")
                
                if config['duration']:
                    print(f"  持续时间: {timedelta(seconds=config['duration'])}")
                else:
                    print(f"  持续时间: 无限制")
                    
                if config['count']:
                    print(f"  下载次数: {config['count']}")
                else:
                    print(f"  下载次数: 无限制")
                    
                if config['cron_expr']:
                    print(f"  Cron表达式: {config['cron_expr']}")
        except Exception as e:
            print(f"{Fore.RED}列出配置出错: {e}{Style.RESET_ALL}")
    
    @staticmethod
    def delete_config(config_name):
        """删除指定的配置"""
        if not os.path.exists(CONFIG_FILE):
            print(f"{Fore.YELLOW}配置文件不存在{Style.RESET_ALL}")
            return False
        
        try:
            with open(CONFIG_FILE, 'r') as f:
                config_data = json.load(f)
            
            if config_name in config_data:
                del config_data[config_name]
                
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(config_data, f, indent=2)
                
                print(f"{Fore.CYAN}配置 '{config_name}' 已删除{Style.RESET_ALL}")
                return True
            else:
                print(f"{Fore.YELLOW}配置 '{config_name}' 不存在{Style.RESET_ALL}")
                return False
        except Exception as e:
            print(f"{Fore.RED}删除配置出错: {e}{Style.RESET_ALL}")
            return False
    
    @staticmethod
    def show_stats(limit=5):
        """显示历史统计数据"""
        if not os.path.exists(STATS_FILE):
            print(f"{Fore.YELLOW}没有历史统计数据{Style.RESET_ALL}")
            return
        
        try:
            with open(STATS_FILE, 'r') as f:
                stats_data = json.load(f)
            
            if not stats_data:
                print(f"{Fore.YELLOW}没有历史统计数据{Style.RESET_ALL}")
                return
            
            # 按时间排序，最新的在前
            sorted_runs = sorted(stats_data.items(), key=lambda x: x[1]['end_time'], reverse=True)
            
            print(f"{Fore.CYAN}=== 流量消耗历史记录 (最近 {min(limit, len(sorted_runs))} 条) ==={Style.RESET_ALL}")
            
            for i, (run_id, stats) in enumerate(sorted_runs[:limit]):
                print(f"\n{Fore.GREEN}运行ID: {run_id}{Style.RESET_ALL}")
                print(f"  配置名称: {stats.get('config_name', '默认')}")
                print(f"  开始时间: {stats.get('start_time', 'N/A')}")
                print(f"  结束时间: {stats.get('end_time', 'N/A')}")
                print(f"  总消耗流量: {TrafficConsumer().format_bytes(stats.get('total_bytes', 0))}")
                print(f"  下载次数: {stats.get('download_count', 0)}")
                print(f"  运行时间: {timedelta(seconds=stats.get('elapsed_seconds', 0))}")
                
                if i < len(sorted_runs) - 1:
                    print(f"{Fore.CYAN}------------------------{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}显示统计数据出错: {e}{Style.RESET_ALL}")
    
    def setup_scheduler(self):
        """设置调度器 (cron 或 interval)"""
        if not self.cron_expr and not self.interval:
            return

        self.scheduler = BackgroundScheduler(timezone="Asia/Shanghai")
        job = None
        
        try:
            if self.cron_expr:
                trigger = CronTrigger.from_crontab(self.cron_expr)
                job = self.scheduler.add_job(self.scheduled_run, trigger, id='traffic_consumer_job')
                self.logger(f"{Fore.CYAN}已设置Cron调度: {self.cron_expr}{Style.RESET_ALL}")
            elif self.interval:
                job = self.scheduler.add_job(self.scheduled_run, 'interval', minutes=self.interval, id='traffic_consumer_job')
                self.logger(f"{Fore.CYAN}已设置间隔调度: 每{self.interval}分钟执行一次{Style.RESET_ALL}")

            self.scheduler.start()
            
            if job:
                # 重新从调度器获取作业以确保状态是最新的
                job_instance = self.scheduler.get_job(job.id)
                if job_instance and job_instance.next_run_time:
                    self.next_run_time = job_instance.next_run_time
                    self.logger(f"{Fore.CYAN}下一次执行时间: {self.next_run_time.strftime('%Y-%m-%d %H:%M:%S')}{Style.RESET_ALL}")
            self.logger(f"{Fore.CYAN}调度器已启动。按Ctrl+C停止。{Style.RESET_ALL}")
            
            self.status = "等待执行"
            
            # 在CLI模式下，保持主线程活动以显示倒计时
            is_cli_mode = self.logger == self._default_logger
            if is_cli_mode:
                signal.signal(signal.SIGINT, self.handle_signal)
                signal.signal(signal.SIGTERM, self.handle_signal)
                while self.scheduler.running:
                    if self.next_run_time:
                        remaining = self.next_run_time - datetime.now(self.next_run_time.tzinfo)
                        if remaining.total_seconds() < 0:
                            # 等待任务触发后更新时间
                            time.sleep(1)
                            if self.scheduler.get_jobs():
                                self.next_run_time = self.scheduler.get_jobs()[0].next_run_time
                            continue

                        remaining_str = str(remaining).split('.')[0]
                        status_msg = f"\r{Fore.CYAN}状态: {self.status} | 距离下次执行还有: {remaining_str}{Style.RESET_ALL}"
                        sys.stdout.write(status_msg)
                        sys.stdout.flush()
                    time.sleep(1)

        except ValueError as e:
            self.logger(f"{Fore.RED}无效的调度配置: {e}{Style.RESET_ALL}")
        except Exception as e:
            self.logger(f"{Fore.RED}启动调度器时出错: {e}{Style.RESET_ALL}")

    def handle_signal(self, signum, frame):
        """处理信号"""
        self.logger(f"\n{Fore.YELLOW}接收到信号 {signum}，正在停止...{Style.RESET_ALL}")
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown()
        self.active = False
        sys.exit(0)

    def scheduled_run(self):
        """由调度器执行的任务"""
        self.logger(f"\n{Fore.CYAN}[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 开始执行计划任务...{Style.RESET_ALL}")
        
        # 重置统计数据以进行新的运行
        with self.lock:
            self.total_bytes = 0
            self.start_time = time.time()
            self.download_count = 0
            self.thread_current_urls = {}
            self.url_usage = {url: 0 for url in self.urls}

        # 记录任务开始
        start_bytes = self.total_bytes
        try:
            self._run_task()
            end_bytes = self.total_bytes
            # 记录任务完成
            self.add_history_record("成功", end_bytes - start_bytes)
        except Exception as e:
            self.logger(f"{Fore.RED}计划任务执行失败: {e}{Style.RESET_ALL}", Fore.RED)
            self.add_history_record("failed", 0) # 记录失败

        # 从调度器获取下一次运行时间
        if self.scheduler and self.scheduler.running and self.scheduler.get_jobs():
            self.next_run_time = self.scheduler.get_jobs()[0].next_run_time
        
        self.status = "等待下次执行"
        self.logger(f"{Fore.CYAN}计划任务执行完毕。{Style.RESET_ALL}")
        if self.next_run_time:
            self.logger(f"{Fore.CYAN}下一次执行时间: {self.next_run_time.strftime('%Y-%m-%d %H:%M:%S')}{Style.RESET_ALL}")

    def _run_task(self):
        """执行一次完整的下载任务"""
        self.active = True
        self.start_time = time.time()
        self.status = "正在执行"
        
        download_threads = []
        for i in range(self.threads):
            thread = threading.Thread(target=self.download_file, args=(i+1,))
            thread.daemon = True
            thread.start()
            download_threads.append(thread)
        
        stats_thread = None
        # 仅在CLI模式下启动独立的统计显示线程
        if self.logger == self._default_logger:
            stats_thread = threading.Thread(target=self.display_stats)
            stats_thread.daemon = True
            stats_thread.start()
        
        try:
            # 限制条件（如时长、流量、次数）将在download_file方法内部检查
            # 并将self.active设置为False
            if self.duration:
                time.sleep(self.duration)
                self.active = False
            else:
                while self.active:
                    time.sleep(0.1)
        except KeyboardInterrupt:
            self.logger(f"\n{Fore.YELLOW}接收到中断信号，正在停止...{Style.RESET_ALL}")
            self.active = False
        
        for thread in download_threads:
            thread.join(timeout=1.0)
        if stats_thread:
            stats_thread.join(timeout=1.0)
        
        self.save_stats()
        self.logger(f"{Fore.CYAN}任务已停止。{Style.RESET_ALL}")

    def start(self):
        """启动流量消耗器"""
        if self.cron_expr or self.interval:
            self.setup_scheduler()
        else:
            self._run_task()


def parse_args():
    parser = argparse.ArgumentParser(description="流量消耗器 - 用于测试网络带宽和流量消耗")
    
    # 主要参数
    parser.add_argument("-u", "--urls", nargs='+', default=None,
                      help=f"要下载的URL列表，可以指定多个URL (默认: 使用内置的{len(DEFAULT_URLS)}个测试URL)")
    parser.add_argument("--url-strategy", choices=['random', 'round_robin'], default='random',
                      help="URL选择策略: random(随机选择) 或 round_robin(轮询选择) (默认: random)")
    parser.add_argument("-t", "--threads", type=int, default=8,
                      help="下载线程数 (默认: 8)")
    parser.add_argument("-l", "--limit", type=int, default=0,
                      help="下载速度限制，单位MB/s，0表示不限速 (默认: 0)")
    parser.add_argument("-d", "--duration", type=int, default=None,
                      help="持续时间，单位秒 (默认: 无限制)")
    parser.add_argument("-c", "--count", type=int, default=None,
                      help="下载次数 (默认: 无限制)")
    parser.add_argument("--cron", default=None,
                      help="Cron表达式，格式: '分 时 日 月 周'，例如: '0 * * * *' 表示每小时执行一次")
    parser.add_argument("--traffic-limit", type=int, default=None,
                      help="流量限制，单位MB (默认: 无限制)")
    parser.add_argument("--interval", type=int, default=None,
                      help="间隔执行时间，单位分钟，例如: 60 表示每60分钟执行一次 (默认: 无限制)")
    
    # 配置管理
    parser.add_argument("--config", default="default",
                      help="配置名称 (默认: default)")
    parser.add_argument("--save-config", action="store_true",
                      help="保存当前配置")
    parser.add_argument("--load-config", action="store_true",
                      help="加载指定配置")
    parser.add_argument("--list-configs", action="store_true",
                      help="列出所有保存的配置")
    parser.add_argument("--delete-config", action="store_true",
                      help="删除指定配置")
    
    # 统计数据
    parser.add_argument("--show-stats", action="store_true",
                      help="显示历史统计数据")
    parser.add_argument("--stats-limit", type=int, default=5,
                      help="显示的历史统计数据条数 (默认: 5)")

    # UI
    parser.add_argument("--no-gui", action="store_true",
                      help="不启动Web UI，仅使用命令行")
    
    return parser.parse_args()


def main():
    args = parse_args()

    # 如果是命令行模式或指定了no-gui
    is_cli_mode = any(arg in sys.argv for arg in ['--list-configs', '--delete-config', '--show-stats', '--save-config', '--no-gui'])

    if is_cli_mode:
        # 处理配置管理命令
        if args.list_configs:
            TrafficConsumer.list_configs()
            return
        
        if args.delete_config:
            TrafficConsumer.delete_config(args.config)
            return
        
        if args.show_stats:
            TrafficConsumer.show_stats(args.stats_limit)
            return
        
        # 加载配置
        config = None
        if args.load_config:
            config = TrafficConsumer.load_config(args.config)
        
        # 处理URLs参数
        urls = None
        if config:
            # 兼容旧配置格式
            if "urls" in config:
                urls = config["urls"]
            elif "url" in config:
                urls = [config["url"]]  # 将单个URL转换为列表

        if not urls:
            urls = args.urls if args.urls else DEFAULT_URLS

        # 创建流量消耗器实例
        consumer = TrafficConsumer(
            urls=urls,
            url_strategy=config.get("url_strategy", args.url_strategy) if config else args.url_strategy,
            threads=config["threads"] if config and "threads" in config else args.threads,
            limit_speed=config["limit_speed"] if config and "limit_speed" in config else args.limit,
            duration=config["duration"] if config and "duration" in config else args.duration,
            count=config["count"] if config and "count" in config else args.count,
            cron_expr=config["cron_expr"] if config and "cron_expr" in config else args.cron,
            traffic_limit=config["traffic_limit"] if config and "traffic_limit" in config else args.traffic_limit,
            interval=config["interval"] if config and "interval" in config else args.interval,
            config_name=args.config
        )
        
        # 如果只是保存配置
        if args.save_config:
            consumer.save_config()
            return
        
        # 启动流量消耗器
        consumer.start()
    else:
        # 启动Web UI
        try:
            from web_ui import app, socketio
            print("启动 Web UI, 访问 http://127.0.0.1:5001")
            socketio.run(app, host='0.0.0.0', port=5001, allow_unsafe_werkzeug=True)
        except ImportError:
            print("错误: 无法导入web_ui。请确保Flask和Flask-SocketIO已安装。")
            print("运行 'pip install Flask Flask-SocketIO' 来安装。")


if __name__ == "__main__":
    main()
