export async function render(container) {
    container.innerHTML = `
        <div class="backtest-layout">
            <div class="backtest-sidebar">
                <div class="card">
                    <div class="card-title">策略配置</div>
                    <div class="form-group">
                        <label class="form-label">策略</label>
                        <select class="form-select" id="strategySelect">
                            <option value="ma_cross">均线交叉</option>
                            <option value="macd">MACD</option>
                            <option value="rsi">RSI</option>
                            <option value="bollinger">布林带突破</option>
                            <option value="platform_breakout">强势平台启动</option>
                        </select>
                    </div>
                    <div class="form-group">
                        <label class="form-label">股票代码</label>
                        <input class="form-input" id="btCode" value="sh.600000">
                    </div>
                    <div class="form-group">
                        <label class="form-label">开始日期</label>
                        <input class="form-input" type="date" id="btStart" value="2023-01-01">
                    </div>
                    <div class="form-group">
                        <label class="form-label">结束日期</label>
                        <input class="form-input" type="date" id="btEnd" value="2024-12-31">
                    </div>
                    <div class="form-group">
                        <label class="form-label">初始资金</label>
                        <input class="form-input" id="btCapital" value="100000">
                    </div>
                    <div id="strategyParams"></div>
                    <button class="btn btn-primary" id="btnRunBacktest" style="width: 100%; margin-top: 8px;">
                        运行回测
                    </button>
                    <div id="btProgress" style="margin-top: 8px;"></div>
                </div>
            </div>
            <div class="backtest-results" id="btResults">
                <div class="card" style="text-align: center; color: var(--text-muted); padding: 60px;">
                    选择策略并运行回测查看结果
                </div>
            </div>
        </div>
    `;

    setupStrategyParams();
    document.getElementById('strategySelect').addEventListener('change', setupStrategyParams);
    document.getElementById('btnRunBacktest').addEventListener('click', runBacktest);
}

function setupStrategyParams() {
    const strategy = document.getElementById('strategySelect').value;
    const container = document.getElementById('strategyParams');

    const params = {
        ma_cross: `
            <div class="form-group"><label class="form-label">短期均线</label>
            <input class="form-input" id="param_short" value="5"></div>
            <div class="form-group"><label class="form-label">长期均线</label>
            <input class="form-input" id="param_long" value="20"></div>`,
        macd: `
            <div class="form-group"><label class="form-label">快线</label>
            <input class="form-input" id="param_fast" value="12"></div>
            <div class="form-group"><label class="form-label">慢线</label>
            <input class="form-input" id="param_slow" value="26"></div>
            <div class="form-group"><label class="form-label">信号线</label>
            <input class="form-input" id="param_signal" value="9"></div>`,
        rsi: `
            <div class="form-group"><label class="form-label">RSI周期</label>
            <input class="form-input" id="param_period" value="14"></div>
            <div class="form-group"><label class="form-label">超买线</label>
            <input class="form-input" id="param_overbought" value="70"></div>
            <div class="form-group"><label class="form-label">超卖线</label>
            <input class="form-input" id="param_oversold" value="30"></div>`,
        bollinger: `
            <div class="form-group"><label class="form-label">周期</label>
            <input class="form-input" id="param_period" value="20"></div>
            <div class="form-group"><label class="form-label">标准差倍数</label>
            <input class="form-input" id="param_std" value="2"></div>`,
        platform_breakout: `
            <div class="form-group"><label class="form-label">整理天数</label>
            <input class="form-input" id="param_days" value="20"></div>
            <div class="form-group"><label class="form-label">振幅阈值(%)</label>
            <input class="form-input" id="param_amplitude" value="10"></div>`,
    };

    container.innerHTML = params[strategy] || '';
}

async function runBacktest() {
    const results = document.getElementById('btResults');
    const progress = document.getElementById('btProgress');

    progress.innerHTML = `
        <div class="progress-bar"><div class="progress-fill" style="width: 0%"></div></div>
        <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">回测运行中...</div>
    `;

    // Simulate progress for now (will be replaced with WebSocket)
    let pct = 0;
    const interval = setInterval(() => {
        pct = Math.min(pct + Math.random() * 15, 95);
        progress.querySelector('.progress-fill').style.width = pct + '%';
    }, 200);

    try {
        const config = {
            strategy: document.getElementById('strategySelect').value,
            code: document.getElementById('btCode').value,
            start_date: document.getElementById('btStart').value,
            end_date: document.getElementById('btEnd').value,
            capital: parseFloat(document.getElementById('btCapital').value),
        };

        const resp = await fetch('/api/backtest/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config),
        });

        clearInterval(interval);

        if (!resp.ok) throw new Error('回测请求失败');

        const data = await resp.json();
        progress.innerHTML = '<span class="badge badge-success">回测完成</span>';
        displayResults(data.data, results);
    } catch (e) {
        clearInterval(interval);
        progress.innerHTML = `<span class="badge badge-error">回测失败: ${e.message}</span>`;
    }
}

function displayResults(data, container) {
    if (!data) {
        container.innerHTML = '<div class="card"><span class="badge badge-error">无回测结果</span></div>';
        return;
    }

    const m = data.metrics || {};
    const trades = data.trades || [];

    const upDown = (v, suffix = '%') => {
        const cls = v >= 0 ? 'price-up' : 'price-down';
        const sign = v >= 0 ? '+' : '';
        return `<span class="${cls}">${sign}${v.toFixed(2)}${suffix}</span>`;
    };

    container.innerHTML = `
        <div class="metrics-grid">
            <div class="metric-card">
                <div class="metric-value">${upDown(m.total_return || 0)}</div>
                <div class="metric-label">总收益率</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${upDown(m.annual_return || 0)}</div>
                <div class="metric-label">年化收益</div>
            </div>
            <div class="metric-card">
                <div class="metric-value price-down">${(m.max_drawdown || 0).toFixed(2)}%</div>
                <div class="metric-label">最大回撤</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${(m.sharpe_ratio || 0).toFixed(2)}</div>
                <div class="metric-label">夏普比率</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${(m.win_rate || 0).toFixed(1)}%</div>
                <div class="metric-label">胜率</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${(m.profit_loss_ratio || 0).toFixed(2)}</div>
                <div class="metric-label">盈亏比</div>
            </div>
            <div class="metric-card">
                <div class="metric-value">${m.total_trades || 0}</div>
                <div class="metric-label">交易次数</div>
            </div>
        </div>
        <div class="card" style="margin-bottom: 16px;">
            <div class="card-title">收益曲线</div>
            <div id="equityCurveChart" style="height: 300px;"></div>
        </div>
        <div class="card">
            <div class="card-title">交易记录</div>
            <table>
                <thead>
                    <tr><th>日期</th><th>操作</th><th>代码</th><th>价格</th><th>数量</th><th>盈亏</th></tr>
                </thead>
                <tbody>
                    ${trades.slice(0, 50).map(t => `
                        <tr>
                            <td>${t.date}</td>
                            <td><span class="${t.action === 'buy' ? 'price-up' : 'price-down'}">${t.action === 'buy' ? '买入' : '卖出'}</span></td>
                            <td>${t.code}</td>
                            <td>${t.price?.toFixed(2)}</td>
                            <td>${t.amount}</td>
                            <td>${t.pnl != null ? upDown(t.pnl, '') : '--'}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </div>
    `;

    // Render equity curve chart
    const equityCurve = data.equity_curve || [];
    if (equityCurve.length > 0) {
        renderEquityCurve(equityCurve);
    }
}

async function renderEquityCurve(equityCurve) {
    const { createChart } = await import('https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.mjs');
    const container = document.getElementById('equityCurveChart');
    if (!container) return;

    const chart = createChart(container, {
        layout: { background: { color: '#151d2b' }, textColor: '#94a3b8', fontSize: 11 },
        grid: { vertLines: { color: '#1e2a3a' }, horzLines: { color: '#1e2a3a' } },
        rightPriceScale: { borderColor: '#1e2a3a' },
        timeScale: { borderColor: '#1e2a3a', timeVisible: false },
        handleScroll: true,
        handleScale: true,
    });

    const equitySeries = chart.addLineSeries({
        color: '#3b82f6',
        lineWidth: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: '策略收益',
    });

    const benchmarkSeries = chart.addLineSeries({
        color: '#64748b',
        lineWidth: 1,
        lineStyle: 2,
        priceLineVisible: false,
        lastValueVisible: true,
        title: '基准',
    });

    equitySeries.setData(equityCurve.map(p => ({ time: p.date, value: p.equity })));
    benchmarkSeries.setData(equityCurve.map(p => ({ time: p.date, value: p.benchmark })));
    chart.timeScale().fitContent();

    const observer = new ResizeObserver(() => {
        chart.applyOptions({ width: container.clientWidth, height: container.clientHeight });
    });
    observer.observe(container);
}

export function destroy() {}
