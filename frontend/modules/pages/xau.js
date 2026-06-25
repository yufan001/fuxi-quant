import { getXauChart } from '../api/client.js';
import { KlineChart, calcMA } from '../chart/kline.js';

let chart = null;
let refreshTimer = null;
let currentInterval = '1m';
let showProfile = true;
let showTrend = false;
let showSupportResistance = true;
let showVolatility = false;
let latestSnapshot = null;
let latestVolatility = null;
let loadRequestId = 0;
let lastRenderedInterval = null;
let currentTheme = 'dark';

const THEME_STORAGE_KEY = 'fuxi_xau_theme';
const AUTO_REFRESH_MS = 15_000;
const MA_CONFIG = [
    { period: 20, color: '#f59e0b', label: 'MA20', note: '20根' },
    { period: 60, color: '#06b6d4', label: 'MA60', note: '60根' },
];
const VOLATILITY_CONFIG = {
    color: '#64748b',
    label: 'GVZ',
};
const DEFAULT_VISIBLE_BARS = {
    '1m': 180,
    '5m': 96,
};

export async function render(container) {
    currentTheme = readThemePreference();
    container.innerHTML = `
        <div class="xau-page">
            <div class="xau-toolbar">
                <div class="xau-identity">
                    <div class="xau-title">XAUUSD</div>
                    <div class="xau-subtitle">GC volume profile mapped to spot</div>
                </div>
                <div class="xau-price-block">
                    <span class="stock-price" id="xauPrice">--</span>
                    <span class="stock-change" id="xauChange"></span>
                </div>
                <div class="xau-controls">
                    <div class="xau-control-group period-switch" id="xauIntervalSwitch">
                        <button class="btn btn-period active" data-interval="1m">1m</button>
                        <button class="btn btn-period" data-interval="5m">5m</button>
                    </div>
                    <div class="xau-control-group xau-layer-group">
                        <button class="btn btn-sm xau-toggle active" id="toggleProfile" aria-pressed="true">GC VP</button>
                        <button class="btn btn-sm xau-toggle${showTrend ? ' active' : ''}" id="toggleTrend" aria-pressed="${showTrend}">120m 趋势</button>
                        <button class="btn btn-sm xau-toggle active" id="toggleSupportResistance" aria-pressed="true">支撑/压力</button>
                        <button class="btn btn-sm xau-toggle${showVolatility ? ' active' : ''}" id="toggleVolatility" aria-pressed="${showVolatility}">波动率</button>
                    </div>
                    <div class="xau-control-group xau-action-group">
                        <button class="btn btn-sm xau-theme-toggle" id="toggleTheme" aria-pressed="${currentTheme === 'light'}">${currentTheme === 'light' ? '亮色' : '暗色'}</button>
                        <button class="btn btn-sm" id="btnRefreshXau">刷新</button>
                    </div>
                </div>
                <div class="xau-status" id="xauStatus">加载中...</div>
            </div>
            <div class="xau-main">
                <div class="xau-chart-shell">
                    <div class="chart-container xau-chart-container" id="xauChartContainer">
                        <div class="xau-info-bar" id="xauInfoBar"></div>
                    </div>
                </div>
                <aside class="xau-side">
                    <div class="xau-panel">
                        <div class="xau-panel-title">GC VP 密集区</div>
                        <div id="xauProfilePanel" class="xau-panel-body">--</div>
                    </div>
                    <div class="xau-panel">
                        <div class="xau-panel-title">120m 趋势带</div>
                        <div id="xauTrendPanel" class="xau-panel-body">--</div>
                    </div>
                    <div class="xau-panel">
                        <div class="xau-panel-title">数据窗口</div>
                        <div id="xauSourcePanel" class="xau-panel-body">--</div>
                    </div>
                </aside>
            </div>
        </div>
    `;

    setTheme(currentTheme, false);
    await initChart();
    bindControls();
    await loadXauChart();
    refreshTimer = setInterval(loadXauChart, AUTO_REFRESH_MS);
}

async function initChart() {
    const container = document.getElementById('xauChartContainer');
    if (chart) chart.destroy();
    lastRenderedInterval = null;
    chart = new KlineChart(container);
    await chart.init();
    chart.applyTheme(currentTheme);
    chart.setVolumeVisible(false);
    for (const m of MA_CONFIG) {
        chart.addMA(m.period, m.color);
    }
}

function bindControls() {
    document.querySelectorAll('#xauIntervalSwitch .btn-period').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.interval === currentInterval);
        btn.addEventListener('click', async () => {
            const next = btn.dataset.interval;
            if (next === currentInterval) return;
            currentInterval = next;
            document.querySelectorAll('#xauIntervalSwitch .btn-period').forEach(node => {
                node.classList.toggle('active', node.dataset.interval === currentInterval);
            });
            await loadXauChart();
        });
    });

    document.getElementById('toggleProfile').addEventListener('click', () => {
        showProfile = !showProfile;
        const btn = document.getElementById('toggleProfile');
        btn.classList.toggle('active', showProfile);
        btn.setAttribute('aria-pressed', String(showProfile));
        chart?.setProfileVisible(showProfile);
    });

    document.getElementById('toggleTrend').addEventListener('click', () => {
        showTrend = !showTrend;
        const btn = document.getElementById('toggleTrend');
        btn.classList.toggle('active', showTrend);
        btn.setAttribute('aria-pressed', String(showTrend));
        chart?.setTrendOverlay(latestSnapshot?.trend_120m, showTrend);
    });

    document.getElementById('toggleSupportResistance').addEventListener('click', () => {
        showSupportResistance = !showSupportResistance;
        const btn = document.getElementById('toggleSupportResistance');
        btn.classList.toggle('active', showSupportResistance);
        btn.setAttribute('aria-pressed', String(showSupportResistance));
        chart?.setSupportResistanceOverlay(latestSnapshot?.trend_120m, showSupportResistance);
    });

    document.getElementById('toggleVolatility').addEventListener('click', () => {
        showVolatility = !showVolatility;
        const btn = document.getElementById('toggleVolatility');
        btn.classList.toggle('active', showVolatility);
        btn.setAttribute('aria-pressed', String(showVolatility));
        chart?.setVolatilityOverlay(latestVolatility, showVolatility);
        if (latestSnapshot) applySnapshot(latestSnapshot);
    });

    document.getElementById('toggleTheme').addEventListener('click', () => {
        setTheme(currentTheme === 'light' ? 'dark' : 'light');
    });

    document.getElementById('btnRefreshXau').addEventListener('click', () => loadXauChart({ forceRefresh: true }));
}

function readThemePreference() {
    try {
        return localStorage.getItem(THEME_STORAGE_KEY) === 'light' ? 'light' : 'dark';
    } catch (e) {
        return 'dark';
    }
}

function setTheme(theme, persist = true) {
    currentTheme = theme === 'light' ? 'light' : 'dark';
    document.body.classList.toggle('theme-light', currentTheme === 'light');
    if (persist) {
        try {
            localStorage.setItem(THEME_STORAGE_KEY, currentTheme);
        } catch (e) {
            console.warn('Unable to persist theme preference:', e);
        }
    }
    updateThemeButton();
    chart?.applyTheme(currentTheme);
}

function updateThemeButton() {
    const btn = document.getElementById('toggleTheme');
    if (!btn) return;
    const isLight = currentTheme === 'light';
    btn.classList.toggle('active', isLight);
    btn.textContent = isLight ? '亮色' : '暗色';
    btn.setAttribute('aria-pressed', String(isLight));
    btn.title = isLight ? '切换到暗色模式' : '切换到亮色模式';
}

async function loadXauChart(options = {}) {
    const requestId = ++loadRequestId;
    const interval = currentInterval;
    const forceRefresh = Boolean(options.forceRefresh);
    const status = document.getElementById('xauStatus');
    if (status) status.textContent = forceRefresh ? '强制刷新中...' : '同步中...';
    try {
        const days = interval === '1m' ? 2 : 7;
        const lookbackBars = interval === '1m' ? 720 : 240;
        const resp = await getXauChart({
            interval,
            days,
            trendDays: 60,
            lookbackBars,
            priceStep: 0.5,
            valueAreaPct: 0.7,
            forceRefresh,
        });
        if (requestId !== loadRequestId || interval !== currentInterval) return;
        latestSnapshot = resp.data;
        applySnapshot(latestSnapshot);
        updateRefreshStatus(latestSnapshot);
    } catch (e) {
        if (requestId !== loadRequestId) return;
        console.error('Load XAU chart error:', e);
        if (status) status.innerHTML = `<span class="badge badge-error">加载失败</span>`;
    }
}

function applySnapshot(snapshot) {
    const candles = snapshot?.candles || [];
    if (!candles.length || !chart) return;

    const preserveVisibleRange = lastRenderedInterval === snapshot.interval;
    chart.setData(candles, {
        timeVisible: true,
        preserveVisibleRange,
        focusVisibleBars: DEFAULT_VISIBLE_BARS[snapshot.interval] || 120,
        focusRightOffset: 8,
    });
    lastRenderedInterval = snapshot.interval;
    const maReadings = MA_CONFIG.map(m => {
        const data = calcMA(candles, m.period);
        chart.setMAData(m.period, data);
        return {
            ...m,
            value: data.length ? data[data.length - 1].value : null,
        };
    });
    chart.setProfileZones(snapshot.zones || [], showProfile);
    chart.setTrendOverlay(snapshot.trend_120m, showTrend);
    chart.setSupportResistanceOverlay(snapshot.trend_120m, showSupportResistance);
    latestVolatility = snapshot.panic_volatility || null;
    chart.setVolatilityOverlay(latestVolatility, showVolatility);

    const last = candles[candles.length - 1];
    const prev = candles.length > 1 ? candles[candles.length - 2] : last;
    updatePriceDisplay(last, prev);
    updateInfoBar(last, snapshot, maReadings, latestVolatility);
    renderProfilePanel(snapshot);
    renderTrendPanel(snapshot.trend_120m);
    renderSourcePanel(snapshot);
}

function updatePriceDisplay(last, prev) {
    const priceEl = document.getElementById('xauPrice');
    const changeEl = document.getElementById('xauChange');
    const change = Number(last.close) - Number(prev.close);
    const changePct = Number(prev.close) ? change / Number(prev.close) * 100 : 0;
    const sign = change >= 0 ? '+' : '';
    const cls = change >= 0 ? 'price-up' : 'price-down';
    priceEl.textContent = Number(last.close).toFixed(2);
    priceEl.className = `stock-price ${cls}`;
    changeEl.className = `stock-change ${cls}`;
    changeEl.textContent = `${sign}${change.toFixed(2)} (${sign}${changePct.toFixed(2)}%)`;
}

function updateInfoBar(last, snapshot, maReadings = [], volatility = null) {
    const profile = snapshot.profile || {};
    const sr = snapshot.trend_120m?.support_resistance || {};
    document.getElementById('xauInfoBar').innerHTML = `
        <div class="info-item">开 <span>${fmt(last.open)}</span></div>
        <div class="info-item">高 <span>${fmt(last.high)}</span></div>
        <div class="info-item">低 <span>${fmt(last.low)}</span></div>
        <div class="info-item">收 <span>${fmt(last.close)}</span></div>
        ${renderMaLegend(maReadings)}
        ${renderVolatilityLegend(volatility)}
        <div class="info-item">GC POC <span>${fmt(profile.poc)}</span></div>
        <div class="info-item">120m方向 <span>${directionLabel(sr)}</span></div>
        <div class="info-item">周期 <span>${snapshot.interval}</span></div>
    `;
}

function renderMaLegend(maReadings) {
    return maReadings.map(ma => `
        <div class="info-item xau-ma-item" title="${ma.label} · ${ma.note}">
            <i class="xau-ma-dot" style="background:${ma.color};"></i>
            ${ma.label}<span>${fmt(ma.value)}</span>
        </div>
    `).join('');
}

function renderVolatilityLegend(volatility) {
    if (!showVolatility || !volatility?.visible || !Number.isFinite(Number(volatility.latest))) return '';
    const source = volatility.source || 'Yahoo Finance / Cboe GVZ';
    const definition = volatility.definition || '30-day implied volatility estimate';
    return `
        <div class="info-item xau-vol-item ${volatilityStateClass(volatility.state)}" title="${source} · ${definition}">
            <i class="xau-vol-dot" style="background:${VOLATILITY_CONFIG.color};"></i>
            ${VOLATILITY_CONFIG.label}<span>${fmt(volatility.latest)} ${signed(volatility.change)} · ${panicStateLabel(volatility.state)} · ${fmtPercentile(volatility.percentile_1y)}</span>
        </div>
    `;
}

function renderProfilePanel(snapshot) {
    const zones = snapshot.zones || [];
    if (!zones.length) {
        document.getElementById('xauProfilePanel').innerHTML = '<div class="xau-empty">暂无密集区</div>';
        return;
    }
    document.getElementById('xauProfilePanel').innerHTML = `
        <div class="xau-profile-summary">
            <div><span>POC</span><strong>${fmt(snapshot.profile?.poc)}</strong></div>
            <div><span>GC量</span><strong>${compact(snapshot.profile?.total_volume)}</strong></div>
        </div>
        <div class="xau-zone-list">
            ${zones.map(zone => `
                <div class="xau-zone-row">
                    <div class="xau-zone-rank">#${zone.rank}</div>
                    <div class="xau-zone-main">
                        <div>${fmt(zone.lower)} - ${fmt(zone.upper)}</div>
                        <span>POC ${fmt(zone.poc)} · ${(Number(zone.volume_pct) * 100).toFixed(1)}%</span>
                    </div>
                    <div class="xau-zone-distance">${signed(zone.distance_to_price)}</div>
                </div>
            `).join('')}
        </div>
    `;
}

function renderTrendPanel(trend) {
    const el = document.getElementById('xauTrendPanel');
    if (!trend?.visible) {
        el.innerHTML = '<div class="xau-empty">暂无有效趋势带</div>';
        return;
    }
    const direction = trend.direction === 'up' ? '上升支撑带' : '下降压力带';
    const state = trend.state === 'intact' ? '未破' : '破位';
    const status = trend.status === 'valid' ? '有效' : '暂定';
    const sr = trend.support_resistance || {};
    el.innerHTML = `
        ${renderSupportResistanceBlock(sr)}
        <div class="xau-trend-head ${trend.direction === 'up' ? 'up' : 'down'}">
            <strong>${direction}</strong>
            <span>${status} · ${state}</span>
        </div>
        <div class="xau-trend-range">${fmt(trend.latest_lower)} - ${fmt(trend.latest_upper)}</div>
        <div class="xau-metric-grid">
            <div><span>触碰</span><strong>${trend.touches}</strong></div>
            <div><span>破坏</span><strong>${trend.violations}</strong></div>
            <div><span>跨度</span><strong>${Number(trend.duration_days).toFixed(0)}d</strong></div>
            <div><span>ATR</span><strong>${fmt(trend.atr)}</strong></div>
        </div>
    `;
}

function renderSupportResistanceBlock(sr) {
    if (!sr?.visible || !sr.support || !sr.resistance) {
        return '<div class="xau-empty" style="padding-top:0;">暂无120m支撑/压力</div>';
    }
    const positionPct = Number.isFinite(Number(sr.range_position))
        ? `${Math.max(0, Math.min(100, Number(sr.range_position) * 100)).toFixed(0)}%`
        : '--';
    return `
        <div class="xau-sr-block">
            <div class="xau-sr-head">
                <strong>120m 支撑 / 压力</strong>
                <span>${directionLabel(sr)}</span>
            </div>
            <div class="xau-sr-levels">
                <div class="support"><span>支撑</span><strong>${fmt(sr.support.center)}</strong></div>
                <div class="resistance"><span>压力</span><strong>${fmt(sr.resistance.center)}</strong></div>
            </div>
            <div class="xau-range-track">
                <div class="xau-range-fill" style="width:${positionPct};"></div>
            </div>
            <div class="xau-sr-note">${srHint(sr)}</div>
        </div>
    `;
}

function directionLabel(sr) {
    if (!sr?.visible) return '--';
    if (sr.directional_context === 'near_support') return '靠近支撑';
    if (sr.directional_context === 'near_resistance') return '靠近压力';
    if (sr.directional_context === 'middle_range') return '区间中部';
    return '--';
}

function srHint(sr) {
    if (!sr?.visible) return '';
    if (sr.bias === 'long_reclaim_5m_lower') return '观察从支撑向上后，是否重新突破5m密集区下限。';
    if (sr.bias === 'short_break_5m_upper') return '观察从压力向下后，是否击穿5m密集区上限。';
    return '中部不追，等靠近大级别边界或5m区间给出方向。';
}

function renderSourcePanel(snapshot) {
    const window = snapshot.window || {};
    const cache = snapshot.cache || {};
    document.getElementById('xauSourcePanel').innerHTML = `
        <div class="xau-source-row"><span>XAU</span><strong>${snapshot.source?.spot || '--'}</strong></div>
        <div class="xau-source-row"><span>GC</span><strong>${snapshot.source?.volume_owner || '--'}</strong></div>
        <div class="xau-source-row"><span>窗口</span><strong>${shortDate(window.start)} - ${shortDate(window.end)}</strong></div>
        <div class="xau-source-row"><span>对齐</span><strong>${window.aligned_rows || 0} bars</strong></div>
        <div class="xau-source-row"><span>Basis</span><strong>${fmt(window.median_basis)}</strong></div>
        <div class="xau-source-row"><span>状态</span><strong>${cache.refreshing ? '后台刷新中' : '实时轮询'}</strong></div>
    `;
}

function updateRefreshStatus(snapshot) {
    const status = document.getElementById('xauStatus');
    if (!status) return;
    const cache = snapshot?.cache || {};
    const age = Number(cache.age_seconds || 0);
    if (cache.refreshing) {
        status.textContent = `后台刷新中 · ${age.toFixed(0)}s`;
        setTimeout(() => {
            if (latestSnapshot?.interval === currentInterval) loadXauChart();
        }, 3000);
        return;
    }
    status.textContent = `${cache.hit ? '缓存快照' : '实时'} · ${formatClock(new Date())}`;
}

function fmt(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n.toFixed(2) : '--';
}

function fmtPercentile(value) {
    const n = Number(value);
    return Number.isFinite(n) ? `${(n * 100).toFixed(0)}%分位` : '--';
}

function signed(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return '--';
    return `${n >= 0 ? '+' : ''}${n.toFixed(1)}`;
}

function panicStateLabel(state) {
    if (state === 'panic') return '恐慌';
    if (state === 'elevated') return '偏高';
    if (state === 'calm') return '平静';
    return '常态';
}

function volatilityStateClass(state) {
    if (state === 'panic') return 'is-panic';
    if (state === 'elevated') return 'is-elevated';
    if (state === 'calm') return 'is-calm';
    return '';
}

function compact(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return '--';
    if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
    if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`;
    return n.toFixed(0);
}

function shortDate(value) {
    if (!value) return '--';
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return '--';
    return `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}`;
}

function formatClock(date) {
    return `${String(date.getHours()).padStart(2, '0')}:${String(date.getMinutes()).padStart(2, '0')}:${String(date.getSeconds()).padStart(2, '0')}`;
}

export function destroy() {
    if (refreshTimer) {
        clearInterval(refreshTimer);
        refreshTimer = null;
    }
    if (chart) {
        chart.destroy();
        chart = null;
    }
}
