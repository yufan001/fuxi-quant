import { getStocks, getKline } from '../api/client.js';
import { KlineChart, calcMA } from '../chart/kline.js';

let chart = null;
let currentCode = 'sh.600000';
let currentName = '浦发银行';
let currentData = [];

export async function render(container) {
    container.innerHTML = `
        <div class="platform-layout">
            <div class="search-bar">
                <div class="search-wrapper">
                    <input type="text" class="search-input" id="stockSearch"
                           placeholder="输入代码或名称搜索..." autocomplete="off">
                    <div class="search-dropdown" id="searchDropdown"></div>
                </div>
                <span class="stock-name" id="stockName">${currentName}</span>
                <span class="stock-code" id="stockCode">${currentCode}</span>
                <span class="stock-price" id="stockPrice">--</span>
                <span class="stock-change" id="stockChange"></span>
            </div>
            <div class="chart-container" id="chartContainer"></div>
            <div class="info-bar" id="infoBar"></div>
        </div>
    `;

    setupSearch();
    await initChart();
    await loadStock(currentCode);
}

function setupSearch() {
    const input = document.getElementById('stockSearch');
    const dropdown = document.getElementById('searchDropdown');
    let debounceTimer;

    input.addEventListener('input', () => {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(async () => {
            const q = input.value.trim();
            if (!q) {
                dropdown.classList.remove('show');
                return;
            }
            try {
                const resp = await getStocks(q);
                const stocks = resp.data || [];
                if (stocks.length === 0) {
                    dropdown.classList.remove('show');
                    return;
                }
                dropdown.innerHTML = stocks.map(s => `
                    <div class="search-item" data-code="${s.code}" data-name="${s.name || ''}">
                        <span class="code">${s.code}</span>
                        <span class="name">${s.name || ''}</span>
                    </div>
                `).join('');
                dropdown.classList.add('show');

                dropdown.querySelectorAll('.search-item').forEach(item => {
                    item.addEventListener('click', () => {
                        const code = item.dataset.code;
                        const name = item.dataset.name;
                        input.value = '';
                        dropdown.classList.remove('show');
                        currentCode = code;
                        currentName = name;
                        document.getElementById('stockName').textContent = name;
                        document.getElementById('stockCode').textContent = code;
                        loadStock(code);
                    });
                });
            } catch (e) {
                console.error('Search error:', e);
            }
        }, 300);
    });

    document.addEventListener('click', (e) => {
        if (!e.target.closest('.search-wrapper')) {
            dropdown.classList.remove('show');
        }
    });
}

async function initChart() {
    const container = document.getElementById('chartContainer');
    if (chart) chart.destroy();
    chart = new KlineChart(container);
    await chart.init();

    chart.addMA(5, '#f59e0b');
    chart.addMA(10, '#3b82f6');
    chart.addMA(20, '#a855f7');
    chart.addMA(60, '#22c55e');
}

async function loadStock(code) {
    try {
        const resp = await getKline(code);
        const data = resp.data || [];
        currentData = data;

        if (data.length > 0) {
            chart.setData(data);

            const ma5 = calcMA(data, 5);
            const ma10 = calcMA(data, 10);
            const ma20 = calcMA(data, 20);
            const ma60 = calcMA(data, 60);
            chart.setMAData(5, ma5);
            chart.setMAData(10, ma10);
            chart.setMAData(20, ma20);
            chart.setMAData(60, ma60);

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
    const bar = document.getElementById('infoBar');
    bar.innerHTML = `
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
    if (chart) {
        chart.destroy();
        chart = null;
    }
}
