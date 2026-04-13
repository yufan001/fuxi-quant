import { getStocks, getKline } from '../api/client.js';
import { KlineChart, calcMA } from '../chart/kline.js';

let chart = null;
let currentCode = 'sh.600000';
let currentName = '浦发银行';
let currentData = [];
let currentPeriod = 'd';

const MA_CONFIG = [
    { period: 5, color: '#f59e0b', label: 'MA5' },
    { period: 10, color: '#3b82f6', label: 'MA10' },
    { period: 20, color: '#a855f7', label: 'MA20' },
    { period: 60, color: '#22c55e', label: 'MA60' },
];

// localStorage keys
const FAVORITES_KEY = 'lianghua_favorites';
const HISTORY_KEY = 'lianghua_search_history';

function getFavorites() {
    try { return JSON.parse(localStorage.getItem(FAVORITES_KEY) || '[]'); } catch { return []; }
}
function saveFavorites(list) { localStorage.setItem(FAVORITES_KEY, JSON.stringify(list)); }
function getSearchHistory() {
    try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); } catch { return []; }
}
function addSearchHistory(code, name) {
    let history = getSearchHistory();
    history = history.filter(h => h.code !== code);
    history.unshift({ code, name });
    if (history.length > 20) history = history.slice(0, 20);
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
}

export async function render(container) {
    container.innerHTML = `
        <div style="display:grid;grid-template-columns:1fr 220px;gap:12px;height:100%;">
            <div class="platform-layout">
                <div class="search-bar">
                    <div class="search-wrapper">
                        <input type="text" class="search-input" id="stockSearch"
                               placeholder="输入代码或名称搜索..." autocomplete="off">
                        <div class="search-dropdown" id="searchDropdown"></div>
                    </div>
                    <button class="btn" id="btnFavorite" title="加入自选">&#9734;</button>
                    <span class="stock-name" id="stockName">${currentName}</span>
                    <span class="stock-code" id="stockCode">${currentCode}</span>
                    <div class="period-switch" id="periodSwitch" style="display:flex;gap:4px;">
                        <button class="btn btn-period active" data-period="d">日</button>
                        <button class="btn btn-period" data-period="w">周</button>
                        <button class="btn btn-period" data-period="m">月</button>
                    </div>
                    <span class="stock-price" id="stockPrice">--</span>
                    <span class="stock-change" id="stockChange"></span>
                    <div style="margin-left:auto;display:flex;gap:4px;" id="maLegend">
                        ${MA_CONFIG.map(m => `<span class="ma-legend" style="color:${m.color};">${m.label}</span>`).join('')}
                    </div>
                </div>
                <div class="chart-container" id="chartContainer"></div>
                <div class="info-bar" id="infoBar"></div>
            </div>
            <div class="watchlist-panel" id="watchlistPanel">
                <div class="watchlist-header">
                    <span style="font-weight:600;font-size:13px;">自选股</span>
                    <button class="btn" id="btnAddCurrent" title="添加当前" style="padding:2px 6px;font-size:11px;">+ 添加</button>
                </div>
                <div class="watchlist-list" id="watchlistList"></div>
            </div>
        </div>
    `;

    setupSearch();
    setupFavoriteButton();
    setupPeriodSwitch();
    document.getElementById('btnAddCurrent').addEventListener('click', () => {
        addFavorite(currentCode, currentName);
    });
    renderWatchlist();
    await initChart();
    await loadStock(currentCode);
}

function setupSearch() {
    const input = document.getElementById('stockSearch');
    const dropdown = document.getElementById('searchDropdown');
    let debounceTimer;

    input.addEventListener('focus', () => {
        const q = input.value.trim();
        if (!q) showSearchHistory(dropdown);
    });

    input.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        const q = input.value.trim();
        if (!q) {
            showSearchHistory(dropdown);
            return;
        }
        debounceTimer = setTimeout(async () => {
            try {
                const resp = await getStocks(q);
                const stocks = resp.data || [];
                if (stocks.length === 0) { dropdown.classList.remove('show'); return; }
                dropdown.innerHTML = stocks.map(s => `
                    <div class="search-item" data-code="${s.code}" data-name="${s.name || ''}">
                        <span class="code">${s.code}</span>
                        <span class="name">${s.name || ''}</span>
                    </div>
                `).join('');
                dropdown.classList.add('show');
                bindDropdownClicks(dropdown, input);
            } catch (e) { console.error('Search error:', e); }
        }, 300);
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-wrapper')) dropdown.classList.remove('show');
    });
}

function showSearchHistory(dropdown) {
    const history = getSearchHistory();
    if (history.length === 0) { dropdown.classList.remove('show'); return; }
    dropdown.innerHTML = `
        <div style="padding:6px 12px;font-size:11px;color:var(--text-muted);border-bottom:1px solid var(--border);">搜索历史</div>
        ${history.map(h => `
            <div class="search-item" data-code="${h.code}" data-name="${h.name || ''}">
                <span class="code">${h.code}</span>
                <span class="name">${h.name || ''}</span>
            </div>
        `).join('')}
    `;
    dropdown.classList.add('show');
    bindDropdownClicks(dropdown, document.getElementById('stockSearch'));
}

function bindDropdownClicks(dropdown, input) {
    dropdown.querySelectorAll('.search-item').forEach(item => {
        item.addEventListener('click', () => {
            const code = item.dataset.code;
            const name = item.dataset.name;
            input.value = '';
            dropdown.classList.remove('show');
            switchStock(code, name);
        });
    });
}

function setupPeriodSwitch() {
    document.querySelectorAll('.btn-period').forEach(btn => {
        btn.addEventListener('click', async () => {
            const nextPeriod = btn.dataset.period;
            if (nextPeriod === currentPeriod) return;
            currentPeriod = nextPeriod;
            document.querySelectorAll('.btn-period').forEach(node => {
                node.classList.toggle('active', node.dataset.period === currentPeriod);
            });
            await loadStock(currentCode);
        });
    });
}

function switchStock(code, name) {
    currentCode = code;
    currentName = name;
    document.getElementById('stockName').textContent = name;
    document.getElementById('stockCode').textContent = code;
    addSearchHistory(code, name);
    updateFavoriteButton();
    loadStock(code);
}

function setupFavoriteButton() {
    document.getElementById('btnFavorite').addEventListener('click', () => {
        let favs = getFavorites();
        const exists = favs.find(f => f.code === currentCode);
        if (exists) {
            favs = favs.filter(f => f.code !== currentCode);
        } else {
            favs.push({ code: currentCode, name: currentName });
        }
        saveFavorites(favs);
        updateFavoriteButton();
        renderFavoritesPanel();
    });
    updateFavoriteButton();
}

function updateFavoriteButton() {
    const btn = document.getElementById('btnFavorite');
    const favs = getFavorites();
    const isFav = favs.some(f => f.code === currentCode);
    btn.innerHTML = isFav ? '&#9733;' : '&#9734;';
    btn.style.color = isFav ? '#f59e0b' : 'var(--text-muted)';
}

function addFavorite(code, name) {
    let favs = getFavorites();
    if (!favs.find(f => f.code === code)) {
        favs.push({ code, name });
        saveFavorites(favs);
        updateFavoriteButton();
        renderWatchlist();
    }
}

function renderWatchlist() {
    const list = document.getElementById('watchlistList');
    const favs = getFavorites();
    if (favs.length === 0) {
        list.innerHTML = '<div style="text-align:center;padding:40px 0;color:var(--text-muted);font-size:12px;">暂无自选股<br>搜索并添加股票</div>';
        return;
    }
    list.innerHTML = favs.map(f => `
        <div class="watchlist-item ${f.code === currentCode ? 'active' : ''}" data-code="${f.code}" data-name="${f.name}">
            <div class="watchlist-item-main">
                <div class="watchlist-name">${f.name || f.code}</div>
                <div class="watchlist-code">${f.code}</div>
            </div>
            <div class="watchlist-item-price" id="wp_${f.code.replace('.', '_')}">
                <div class="watchlist-price">--</div>
                <div class="watchlist-change">--</div>
            </div>
            <button class="watchlist-remove" data-code="${f.code}" title="移除">&times;</button>
        </div>
    `).join('');

    list.querySelectorAll('.watchlist-item').forEach(item => {
        item.addEventListener('click', (e) => {
            if (e.target.classList.contains('watchlist-remove')) return;
            switchStock(item.dataset.code, item.dataset.name);
            renderWatchlist();
        });
    });

    list.querySelectorAll('.watchlist-remove').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            let favs = getFavorites();
            favs = favs.filter(f => f.code !== btn.dataset.code);
            saveFavorites(favs);
            updateFavoriteButton();
            renderWatchlist();
        });
    });

    // Load prices for watchlist items
    loadWatchlistPrices(favs);
}

async function loadWatchlistPrices(favs) {
    for (const f of favs) {
        try {
            const resp = await getKline(f.code, undefined, undefined, 'd');
            const data = resp.data || [];
            if (data.length >= 2) {
                const last = data[data.length - 1];
                const prev = data[data.length - 2];
                const change = last.close - prev.close;
                const changePct = prev.close ? (change / prev.close * 100) : 0;
                const cls = change >= 0 ? 'price-up' : 'price-down';
                const sign = change >= 0 ? '+' : '';
                const el = document.getElementById(`wp_${f.code.replace('.', '_')}`);
                if (el) {
                    el.innerHTML = `
                        <div class="watchlist-price ${cls}">${last.close.toFixed(2)}</div>
                        <div class="watchlist-change ${cls}">${sign}${changePct.toFixed(2)}%</div>
                    `;
                }
            }
        } catch {}
    }
}

async function initChart() {
    const container = document.getElementById('chartContainer');
    if (chart) chart.destroy();
    chart = new KlineChart(container);
    await chart.init();
    for (const m of MA_CONFIG) {
        chart.addMA(m.period, m.color);
    }
}

async function loadStock(code) {
    try {
        const resp = await getKline(code, undefined, undefined, currentPeriod);
        const data = resp.data || [];
        currentData = data;

        if (data.length > 0) {
            chart.setData(data);
            for (const m of MA_CONFIG) {
                chart.setMAData(m.period, calcMA(data, m.period));
            }
            const last = data[data.length - 1];
            const prev = data.length > 1 ? data[data.length - 2] : last;
            updatePriceDisplay(last, prev);
            updateInfoBar(last);
        }
    } catch (e) {
        console.error('Load stock error:', e);
    }
}

function updatePriceDisplay(last, prev) {
    const priceEl = document.getElementById('stockPrice');
    const changeEl = document.getElementById('stockChange');
    priceEl.textContent = last.close.toFixed(2);
    const change = last.close - prev.close;
    const changePct = prev.close ? (change / prev.close * 100) : 0;
    const sign = change >= 0 ? '+' : '';
    const cls = change >= 0 ? 'price-up' : 'price-down';
    priceEl.className = `stock-price ${cls}`;
    changeEl.className = `stock-change ${cls}`;
    changeEl.textContent = `${sign}${change.toFixed(2)} (${sign}${changePct.toFixed(2)}%)`;
}

function updateInfoBar(d) {
    document.getElementById('infoBar').innerHTML = `
        <div class="info-item">开: <span>${d.open?.toFixed(2) ?? '--'}</span></div>
        <div class="info-item">高: <span>${d.high?.toFixed(2) ?? '--'}</span></div>
        <div class="info-item">低: <span>${d.low?.toFixed(2) ?? '--'}</span></div>
        <div class="info-item">收: <span>${d.close?.toFixed(2) ?? '--'}</span></div>
        <div class="info-item">量: <span>${d.volume ? (d.volume / 10000).toFixed(0) + '万' : '--'}</span></div>
        <div class="info-item">额: <span>${d.amount ? (d.amount / 100000000).toFixed(2) + '亿' : '--'}</span></div>
        <div class="info-item">换手: <span>${d.turn ? d.turn.toFixed(2) + '%' : '--'}</span></div>
    `;
}

export function destroy() {
    if (chart) { chart.destroy(); chart = null; }
}
