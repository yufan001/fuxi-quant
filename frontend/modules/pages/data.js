import { getDataStatus, triggerDataUpdate } from '../api/client.js';

export async function render(container) {
    container.innerHTML = `
        <div class="data-grid">
            <div class="card">
                <div class="card-title">数据概览</div>
                <div id="dataOverview">加载中...</div>
            </div>
            <div class="card">
                <div class="card-title">数据操作</div>
                <div style="display: flex; flex-direction: column; gap: 8px;">
                    <button class="btn btn-primary" id="btnUpdate">增量更新数据</button>
                    <button class="btn" id="btnFullDownload">全量下载</button>
                    <div id="updateStatus"></div>
                </div>
            </div>
        </div>
    `;

    await loadStatus();

    document.getElementById('btnUpdate').addEventListener('click', async () => {
        const statusEl = document.getElementById('updateStatus');
        statusEl.innerHTML = '<span class="badge badge-warning">更新中...</span>';
        try {
            await triggerDataUpdate();
            statusEl.innerHTML = '<span class="badge badge-success">更新完成</span>';
            await loadStatus();
        } catch (e) {
            statusEl.innerHTML = `<span class="badge badge-error">更新失败: ${e.message}</span>`;
        }
    });
}

async function loadStatus() {
    try {
        const resp = await getDataStatus();
        const s = resp.data;
        document.getElementById('dataOverview').innerHTML = `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                <div>
                    <div class="stat-value">${s.total_stocks.toLocaleString()}</div>
                    <div class="stat-label">股票数量</div>
                </div>
                <div>
                    <div class="stat-value">${s.total_records.toLocaleString()}</div>
                    <div class="stat-label">数据条数</div>
                </div>
            </div>
            <div style="margin-top: 12px;" class="info-item">
                最后更新: <span>${s.last_update_date || '暂无数据'}</span>
            </div>
        `;
    } catch (e) {
        document.getElementById('dataOverview').innerHTML = `<span class="badge badge-error">加载失败</span>`;
    }
}

export function destroy() {}
