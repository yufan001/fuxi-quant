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
        window.location.hash = '#/login';
        throw new Error('未授权，请先登录');
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
