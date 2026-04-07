const BASE_URL = '';

async function fetchJSON(url, options = {}) {
    const resp = await fetch(`${BASE_URL}${url}`, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    return resp.json();
}

export async function getStocks(q = '') {
    const params = q ? `?q=${encodeURIComponent(q)}` : '';
    return fetchJSON(`/api/market/stocks${params}`);
}

export async function getKline(code, startDate, endDate) {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    const qs = params.toString();
    return fetchJSON(`/api/market/kline/${encodeURIComponent(code)}${qs ? '?' + qs : ''}`);
}

export async function getDataStatus() {
    return fetchJSON('/api/market/status');
}

export async function startBacktest(config) {
    return fetchJSON('/api/backtest/run', {
        method: 'POST',
        body: JSON.stringify(config),
    });
}

export async function getBacktestResult(taskId) {
    return fetchJSON(`/api/backtest/result/${taskId}`);
}

export async function getStrategies() {
    return fetchJSON('/api/strategy/list');
}

export async function getSystemStatus() {
    return fetchJSON('/api/monitor/status');
}

export async function triggerDataUpdate() {
    return fetchJSON('/api/market/update', { method: 'POST' });
}
