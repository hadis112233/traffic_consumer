AOS.init({ once: true });

document.addEventListener('DOMContentLoaded', (event) => {
    const socket = io.connect(location.protocol + '//' + document.domain + ':' + location.port);

    // --- 元素获取 ---
    const startBtn = document.getElementById('start-btn');
    const stopBtn = document.getElementById('stop-btn');
    const stopSchedulerBtn = document.getElementById('stop-scheduler-btn');
    const saveConfigBtn = document.getElementById('save-config-btn');
    const configSelect = document.getElementById('config-select');
    const runningStatus = document.getElementById('running-status');
    const configInputs = {
        name: document.getElementById('config-name'),
        urls: document.getElementById('urls'),
        threads: document.getElementById('threads'),
        limit_speed: document.getElementById('limit-speed'),
        traffic_limit: document.getElementById('traffic-limit'),
        duration: document.getElementById('duration'),
        count: document.getElementById('count'),
        cron_expr: document.getElementById('cron-expr'),
        interval: document.getElementById('interval')
    };
    const jobDetailsEl = document.getElementById('job-details');
    const nextRunTimeEl = document.getElementById('next-run-time');
    const countdownEl = document.getElementById('countdown');
    const historyTableBody = document.getElementById('history-table-body');
    const cronPreviewEl = document.getElementById('cron-preview');
    const logSwitch = document.getElementById('log-switch');
    const logContainer = document.getElementById('log-container');
    const clearLogBtn = document.getElementById('clear-log-btn');

    function ansiToHtml(text) {
        const ansiToCss = {
            '30': 'black',
            '31': 'red',
            '32': 'green',
            '33': 'yellow',
            '34': 'blue',
            '35': 'magenta',
            '36': 'cyan',
            '37': 'white',
            '90': 'grey'
        };
        return text.replace(/\u001b\[(\d+)m/g, (match, code) => {
            if (code === '0') {
                return '</span>';
            }
            const color = ansiToCss[code];
            return color ? `<span style="color:${color}">` : '';
        }).replace(/\u001b\[0m/g, '</span>');
    }

    // --- Chart.js 初始化 ---
    const speedChartCtx = document.getElementById('speed-chart').getContext('2d');
    const speedChart = new Chart(speedChartCtx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: '速度 (MB/s)',
                data: [],
                borderColor: 'rgba(255, 105, 180, 0.8)',
                backgroundColor: 'rgba(255, 105, 180, 0.2)',
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: { display: false },
                y: {
                    beginAtZero: true,
                    ticks: { color: '#FF69B4' }
                }
            },
            plugins: {
                legend: { display: false }
            }
        }
    });


    function addDataToChart(label, data) {
        speedChart.data.labels.push(label);
        speedChart.data.datasets.forEach((dataset) => {
            dataset.data.push(data);
        });
        if (speedChart.data.labels.length > 30) {
            speedChart.data.labels.shift();
            speedChart.data.datasets[0].data.shift();
        }
        speedChart.update('none'); // 'none' for no animation
    }

    // --- Socket.IO 事件处理 ---
    socket.on('connect', () => {
        console.log('已连接到服务器');
        socket.emit('get_configs');
    });

    socket.on('configs_list', (data) => {
        configSelect.innerHTML = '';
        data.configs.forEach(config => {
            const option = document.createElement('option');
            option.value = config;
            option.textContent = config;
            configSelect.appendChild(option);
        });
        if (data.configs.length > 0) {
            configSelect.dispatchEvent(new Event('change'));
        }
    });

    socket.on('config_details', (data) => {
        configInputs.name.value = data.name;
        configInputs.urls.value = data.config.urls ? data.config.urls.join('\n') : '';
        configInputs.threads.value = data.config.threads || '';
        configInputs.limit_speed.value = data.config.limit_speed !== null ? data.config.limit_speed : '';
        configInputs.traffic_limit.value = data.config.traffic_limit || '';
        configInputs.duration.value = data.config.duration || '';
        configInputs.count.value = data.config.count || '';
        configInputs.cron_expr.value = data.config.cron_expr || '';
        configInputs.interval.value = data.config.interval || '';
    });

    socket.on('status_update', (data) => {
        if (data.running) {
            runningStatus.textContent = '运行中';
            runningStatus.className = 'badge bg-success';
        } else {
            runningStatus.textContent = '已停止';
            runningStatus.className = 'badge bg-secondary';
        }
        document.getElementById('speed-text').textContent = data.speed || '0 B/s';
        document.getElementById('total-bytes').textContent = data.total_bytes || '0 B';
        document.getElementById('download-count').textContent = data.download_count || '0';
        document.getElementById('current-config').textContent = data.config || 'N/A';

        const speedValue = data.speed ? data.speed.match(/(\d+\.\d+)\s*MB\/s/i) : null;
        const speedMB = speedValue ? parseFloat(speedValue[1]) : 0;
        addDataToChart(new Date().toLocaleTimeString(), speedMB);

        startBtn.disabled = data.running;
        stopBtn.disabled = !data.running;
    });

    socket.on('history_update', (record) => {
        const row = historyTableBody.insertRow(0);
        row.innerHTML = `<td>${new Date(record.timestamp).toLocaleString()}</td><td>${record.result}</td><td>${record.bytes_consumed}</td><td>${record.download_count || 'N/A'}</td>`;
        const noHistoryRow = historyTableBody.querySelector('.no-history');
        if (noHistoryRow) noHistoryRow.remove();
        while (historyTableBody.rows.length > 50) {
            historyTableBody.deleteRow(historyTableBody.rows.length - 1);
        }
    });

    socket.on('log_message', (data) => {
        if (!logSwitch.checked) return;
        const initialMessage = logContainer.querySelector('.text-muted');
        if (initialMessage) {
            initialMessage.remove();
        }
        const logEntry = document.createElement('p');
        logEntry.className = 'mb-1';
        const timestamp = `[${new Date().toLocaleTimeString()}] `;
        logEntry.innerHTML = timestamp + ansiToHtml(data.message);
        logContainer.append(logEntry); // Append to show latest at the bottom
        
        // Auto-scroll to the bottom
        logContainer.scrollTop = logContainer.scrollHeight;

        while (logContainer.children.length > 200) {
            logContainer.removeChild(logContainer.firstChild);
        }
    });

    let countdownInterval;
    socket.on('scheduler_status_update', (data) => {
        jobDetailsEl.textContent = data.job_details || '无';
        stopSchedulerBtn.disabled = !data.job_details;

        if (data.next_run_time) {
            const nextRunDate = new Date(data.next_run_time);
            nextRunTimeEl.textContent = nextRunDate.toLocaleString();
            if (countdownInterval) clearInterval(countdownInterval);
            countdownInterval = setInterval(() => {
                const diff = nextRunDate - new Date();
                if (diff <= 0) {
                    countdownEl.textContent = '运行中...';
                    clearInterval(countdownInterval);
                    return;
                }
                const h = Math.floor(diff / 3600000).toString().padStart(2, '0');
                const m = Math.floor((diff % 3600000) / 60000).toString().padStart(2, '0');
                const s = Math.floor((diff % 60000) / 1000).toString().padStart(2, '0');
                countdownEl.textContent = `${h}:${m}:${s}`;
            }, 1000);
        } else {
            nextRunTimeEl.textContent = '无';
            countdownEl.textContent = '无';
            if (countdownInterval) clearInterval(countdownInterval);
        }

        historyTableBody.innerHTML = '';
        if (data.history && data.history.length > 0) {
            data.history.forEach(item => {
                const row = historyTableBody.insertRow();
                row.innerHTML = `<td>${new Date(item.timestamp).toLocaleString()}</td><td>${item.result}</td><td>${item.bytes_consumed}</td><td>${item.download_count || 'N/A'}</td>`;
            });
        } else {
            historyTableBody.innerHTML = '<tr class="no-history text-center"><td colspan="4">暂无历史记录</td></tr>';
        }
    });
    
    // --- 事件监听 ---
    function getConfigFromForm() {
        const data = {};
        for (const key in configInputs) {
            data[key] = configInputs[key].value || null;
        }
        data.urls = data.urls ? data.urls.split(/\r?\n/).filter(url => url.trim() !== '') : [];
        ['threads', 'limit_speed', 'traffic_limit', 'duration', 'count', 'interval'].forEach(key => {
            data[key] = data[key] ? parseInt(data[key], 10) : null;
        });
        return data;
    }

    startBtn.addEventListener('click', () => {
        socket.emit('start_consumer', getConfigFromForm());
    });

    stopBtn.addEventListener('click', () => {
        socket.emit('stop_consumer');
    });

    stopSchedulerBtn.addEventListener('click', () => socket.emit('stop_scheduler'));

    saveConfigBtn.addEventListener('click', () => {
        const config = getConfigFromForm();
        socket.emit('save_config', { name: config.name, data: config });
    });

    configSelect.addEventListener('change', () => {
        socket.emit('get_config_details', { name: configSelect.value });
    });

    logSwitch.addEventListener('change', () => {
        socket.emit('toggle_logs', { enabled: logSwitch.checked });
        if(logSwitch.checked) {
            const initialMessage = logContainer.querySelector('.text-muted');
            if (initialMessage) {
               initialMessage.textContent = '正在等待日志...';
            }
        }
    });

    clearLogBtn.addEventListener('click', () => {
        logContainer.innerHTML = '<p class="text-muted">日志已清空。</p>';
    });

    // --- Cron 表达式预览 ---
    let debounceTimer;
    configInputs.cron_expr.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => {
            const cronExpr = configInputs.cron_expr.value;
            if (cronExpr) {
                fetch('/api/preview_cron', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ cron_expr: cronExpr })
                })
                .then(response => response.json())
                .then(data => {
                    if (data.error) {
                        cronPreviewEl.innerHTML = `<span class="text-danger">错误: ${data.error}</span>`;
                    } else {
                        let html = '<strong>接下来5次运行时间:</strong><ul>';
                        data.forEach(ts => {
                            html += `<li>${new Date(ts).toLocaleString()}</li>`;
                        });
                        html += '</ul>';
                        cronPreviewEl.innerHTML = html;
                    }
                })
                .catch(err => {
                    cronPreviewEl.innerHTML = `<span class="text-danger">请求预览失败</span>`;
                });
            } else {
                cronPreviewEl.innerHTML = '';
            }
        }, 500);
    });

    document.querySelectorAll('.cron-preset').forEach(button => {
        button.addEventListener('click', (e) => {
            e.preventDefault();
            configInputs.cron_expr.value = e.target.dataset.cron;
            // 触发input事件来更新预览
            configInputs.cron_expr.dispatchEvent(new Event('input'));
        });
    });

    // --- 初始加载 ---
});