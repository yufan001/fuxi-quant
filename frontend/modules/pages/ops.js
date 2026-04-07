export async function render(container) {
    container.innerHTML = `
        <div class="data-grid">
            <div class="card">
                <div class="card-title">系统状态</div>
                <div id="sysStatus">加载中...</div>
            </div>
            <div class="card">
                <div class="card-title">调度任务</div>
                <div id="schedulerTasks">
                    <table>
                        <thead><tr><th>任务</th><th>触发时间</th><th>状态</th></tr></thead>
                        <tbody>
                            <tr><td>增量数据更新</td><td>每日 15:30</td><td><span class="badge badge-success">运行中</span></td></tr>
                            <tr><td>策略执行</td><td>每日 15:00</td><td><span class="badge badge-warning">未配置</span></td></tr>
                            <tr><td>委托下单</td><td>每日 09:25</td><td><span class="badge badge-warning">未配置</span></td></tr>
                            <tr><td>数据完整性检查</td><td>每周末</td><td><span class="badge badge-success">运行中</span></td></tr>
                        </tbody>
                    </table>
                </div>
            </div>
            <div class="card" style="grid-column: 1 / -1;">
                <div class="card-title">系统日志</div>
                <div class="log-viewer" id="logViewer">
                    等待日志...
                </div>
            </div>
        </div>
    `;

    loadStatus();
}

async function loadStatus() {
    try {
        const resp = await fetch('/api/monitor/status');
        if (resp.ok) {
            const data = await resp.json();
            document.getElementById('sysStatus').innerHTML = `
                <div class="info-item">运行时间: <span>${data.data?.uptime || '--'}</span></div>
                <div class="info-item">内存使用: <span>${data.data?.memory || '--'}</span></div>
                <div class="info-item">CPU使用: <span>${data.data?.cpu || '--'}</span></div>
            `;
        }
    } catch {
        document.getElementById('sysStatus').innerHTML = `
            <div class="info-item">系统运行中</div>
        `;
    }
}

export function destroy() {}
