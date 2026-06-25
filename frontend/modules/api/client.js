const BASE_URL = '';

function getToken() {
    return localStorage.getItem('lianghua_token') || '';
}

export function setToken(token) {
    localStorage.setItem('lianghua_token', token);
}

export function clearToken() {
    localStorage.removeItem('lianghua_token');
}

export function isLoggedIn() {
    return !!getToken();
}

async function fetchJSON(url, options = {}) {
    const token = getToken();
    const headers = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const resp = await fetch(`${BASE_URL}${url}`, { headers, ...options });
    if (resp.status === 401) {
        clearToken();
        throw new Error('请求未授权');
    }
    if (!resp.ok) throw new Error(`API error: ${resp.status}`);
    return resp.json();
}

export async function login(username, password) {
    const resp = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password }),
    });
    return resp.json();
}

export async function getStocks(q = '') {
    const params = q ? `?q=${encodeURIComponent(q)}` : '';
    return fetchJSON(`/api/market/stocks${params}`);
}

export async function getKline(code, startDate, endDate, period = 'd') {
    const params = new URLSearchParams();
    if (startDate) params.set('start_date', startDate);
    if (endDate) params.set('end_date', endDate);
    params.set('period', period);
    const qs = params.toString();
    return fetchJSON(`/api/market/kline/${encodeURIComponent(code)}${qs ? '?' + qs : ''}`);
}

export async function getXauChart(options = {}) {
    const params = new URLSearchParams();
    if (options.interval) params.set('interval', options.interval);
    if (options.days) params.set('days', String(options.days));
    if (options.trendDays) params.set('trend_days', String(options.trendDays));
    if (options.lookbackBars) params.set('lookback_bars', String(options.lookbackBars));
    if (options.priceStep) params.set('price_step', String(options.priceStep));
    if (options.valueAreaPct) params.set('value_area_pct', String(options.valueAreaPct));
    if (options.forceRefresh) params.set('force_refresh', 'true');
    const qs = params.toString();
    return fetchJSON(`/api/market/xau/chart${qs ? '?' + qs : ''}`);
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

export async function startFactorBacktest(config) {
    return fetchJSON('/api/backtest/factor/run', {
        method: 'POST',
        body: JSON.stringify(config),
    });
}

export async function getFactorBacktestResult(runId) {
    return fetchJSON(`/api/backtest/factor/${runId}`);
}

export async function getStrategies() {
    return fetchJSON('/api/strategy/list');
}

export async function createStrategy(config) {
    return fetchJSON('/api/strategy/create', {
        method: 'POST',
        body: JSON.stringify(config),
    });
}

export async function updateStrategy(id, config) {
    return fetchJSON(`/api/strategy/${id}`, {
        method: 'PUT',
        body: JSON.stringify(config),
    });
}

export async function deleteStrategy(id) {
    return fetchJSON(`/api/strategy/${id}`, { method: 'DELETE' });
}

export async function getSystemStatus() {
    return fetchJSON('/api/monitor/status');
}

export async function triggerDataUpdate() {
    return fetchJSON('/api/market/update', { method: 'POST' });
}
