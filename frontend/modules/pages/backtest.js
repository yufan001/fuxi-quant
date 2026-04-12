import { buildFactorRunPayload, isFactorStrategy } from './backtest/factor-utils.js?v=3';
import { createStrategy, deleteStrategy, getStrategies, startBacktest, startFactorBacktest, updateStrategy } from '../api/client.js?v=3';

let currentTab = 'strategy-lib';
let verifyStrategies = [];

export async function render(container) {
    container.innerHTML = `
        <div style="display:flex;flex-direction:column;height:100%;">
            <div class="backtest-tabs">
                <div class="tab active" data-tab="strategy-lib">策略库<span class="tab-sub">管理所有策略</span></div>
                <div class="tab" data-tab="strategy-verify">策略验证<span class="tab-sub">回测分析</span></div>
            </div>
            <div id="tabContent" style="flex:1;overflow:auto;"></div>
        </div>
    `;

    container.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => {
            container.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            currentTab = tab.dataset.tab;
            renderTab(document.getElementById('tabContent'));
        });
    });

    renderTab(document.getElementById('tabContent'));
}

async function renderTab(container) {
    if (currentTab === 'strategy-lib') {
        await renderStrategyLib(container);
    } else {
        await renderStrategyVerify(container);
    }
}

// ===== Strategy Library =====
async function renderStrategyLib(container) {
    container.innerHTML = '<div style="padding:20px;color:var(--text-muted)">加载中...</div>';
    try {
        const data = await getStrategies();
        const strategies = data.data || [];

        container.innerHTML = `
            <div style="padding:8px 0;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                    <div style="font-size:13px;color:var(--text-secondary);">共 ${strategies.length} 个策略</div>
                    <button class="btn btn-primary" id="btnAddStrategy">+ 新建策略</button>
                </div>
                <div class="strategy-grid" id="strategyGrid">
                    ${strategies.map(s => renderStrategyCard(s)).join('')}
                </div>
            </div>
            <div id="strategyModal" style="display:none;"></div>
        `;

        document.getElementById('btnAddStrategy').addEventListener('click', () => showStrategyModal());

        container.querySelectorAll('.strategy-card').forEach(card => {
            card.querySelector('.btn-edit')?.addEventListener('click', (e) => {
                e.stopPropagation();
                const sid = card.dataset.id;
                const s = strategies.find(x => x.id === sid);
                if (s) showStrategyModal(s);
            });
            card.querySelector('.btn-delete')?.addEventListener('click', async (e) => {
                e.stopPropagation();
                const sid = card.dataset.id;
                if (confirm('确定删除此策略？')) {
                    await deleteStrategy(sid);
                    await renderStrategyLib(container);
                }
            });
            card.querySelector('.btn-verify')?.addEventListener('click', (e) => {
                e.stopPropagation();
                const sid = card.dataset.id;
                // Switch to verify tab with this strategy pre-selected
                document.querySelector('.tab[data-tab="strategy-verify"]').click();
                setTimeout(() => {
                    const sel = document.getElementById('pipelineStrategy');
                    if (sel) {
                        sel.value = sid;
                        sel.dispatchEvent(new Event('change'));
                    }
                }, 100);
            });
        });
    } catch (e) {
        container.innerHTML = `<div class="badge badge-error">加载失败: ${e.message}</div>`;
    }
}

function renderStrategyCard(s) {
    const typeLabels = { tech: '技术指标', pattern: '形态识别', ml: 'AI/ML', factor: '因子选股', custom: '自定义' };
    const typeColors = { tech: '#3b82f6', pattern: '#a855f7', ml: '#f59e0b', factor: '#06b6d4', custom: '#22c55e' };
    const color = typeColors[s.type] || '#64748b';
    const label = typeLabels[s.type] || s.type;

    return `
        <div class="strategy-card card" data-id="${s.id}">
            <div style="display:flex;justify-content:space-between;align-items:flex-start;">
                <div>
                    <span style="display:inline-block;padding:2px 6px;border-radius:3px;font-size:10px;background:${color}20;color:${color};margin-bottom:6px;">${label}</span>
                    ${s.builtin ? '<span style="display:inline-block;padding:2px 6px;border-radius:3px;font-size:10px;background:rgba(100,116,139,0.2);color:#94a3b8;margin-left:4px;">内置</span>' : ''}
                    <div style="font-size:15px;font-weight:600;margin-top:4px;">${s.name}</div>
                </div>
            </div>
            <div style="font-size:12px;color:var(--text-muted);margin:8px 0;min-height:32px;">${s.description || '暂无描述'}</div>
            <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">
                参数: ${Object.entries(s.params || {}).map(([k, v]) => `${k}=${v}`).join(', ') || '无'}
            </div>
            <div style="display:flex;gap:6px;">
                <button class="btn btn-verify" style="flex:1;">验证</button>
                ${!s.builtin ? '<button class="btn btn-edit">编辑</button><button class="btn btn-delete" style="color:var(--red);">删除</button>' : ''}
            </div>
        </div>
    `;
}

function bindScriptUpload(inputId, textareaId) {
    const fileInput = document.getElementById(inputId);
    const textarea = document.getElementById(textareaId);
    if (!fileInput || !textarea) return;
    fileInput.onchange = async (event) => {
        const file = event.target.files?.[0];
        if (!file) return;
        textarea.value = await file.text();
    };
}

function toggleStrategyCodeEditor() {
    const type = document.getElementById('modalType')?.value;
    const codeGroup = document.getElementById('modalCodeGroup');
    if (!codeGroup) return;
    codeGroup.style.display = (type === 'factor' || type === 'custom') ? 'block' : 'none';
}

function showStrategyModal(existing = null) {
    const modal = document.getElementById('strategyModal');
    const isEdit = !!existing;
    modal.style.display = 'block';
    modal.innerHTML = `
        <div style="position:fixed;inset:0;background:rgba(0,0,0,0.6);z-index:200;display:flex;align-items:center;justify-content:center;">
            <div class="card" style="width:480px;max-height:80vh;overflow:auto;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
                    <div class="card-title" style="margin:0;">${isEdit ? '编辑策略' : '新建策略'}</div>
                    <button class="btn" id="btnCloseModal" style="padding:2px 8px;">&times;</button>
                </div>
                <div class="form-group">
                    <label class="form-label">策略名称</label>
                    <input class="form-input" id="modalName" value="${existing?.name || ''}">
                </div>
                <div class="form-group">
                    <label class="form-label">类型</label>
                    <select class="form-select" id="modalType">
                        <option value="tech" ${existing?.type === 'tech' ? 'selected' : ''}>技术指标</option>
                        <option value="pattern" ${existing?.type === 'pattern' ? 'selected' : ''}>形态识别</option>
                        <option value="ml" ${existing?.type === 'ml' ? 'selected' : ''}>AI/ML</option>
                        <option value="factor" ${existing?.type === 'factor' ? 'selected' : ''}>因子选股</option>
                        <option value="custom" ${!existing || existing?.type === 'custom' ? 'selected' : ''}>自定义</option>
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">描述</label>
                    <input class="form-input" id="modalDesc" value="${existing?.description || ''}">
                </div>
                <div class="form-group">
                    <label class="form-label">参数 (JSON)</label>
                    <textarea class="form-input" id="modalParams" rows="3" style="font-family:var(--font-mono);font-size:12px;">${JSON.stringify(existing?.params || {}, null, 2)}</textarea>
                </div>
                <div class="form-group" id="modalCodeGroup" style="display:none;">
                    <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;">
                        <label class="form-label" style="margin:0;">Python 脚本</label>
                        <input type="file" id="modalScriptFile" accept=".py" style="font-size:11px;color:var(--text-muted);max-width:190px;">
                    </div>
                    <div style="font-size:11px;color:var(--text-muted);margin:6px 0 8px;">支持 score_stocks(histories, context) 或 select_portfolio(histories, context)</div>
                    <textarea class="form-input" id="modalCode" rows="10" style="font-family:var(--font-mono);font-size:12px;white-space:pre;">${existing?.code || ''}</textarea>
                </div>
                <div style="display:flex;gap:8px;justify-content:flex-end;margin-top:16px;">
                    <button class="btn" id="btnCancelModal">取消</button>
                    <button class="btn btn-primary" id="btnSaveModal">${isEdit ? '保存' : '创建'}</button>
                </div>
            </div>
        </div>
    `;

    document.getElementById('btnCloseModal').addEventListener('click', () => modal.style.display = 'none');
    document.getElementById('btnCancelModal').addEventListener('click', () => modal.style.display = 'none');
    document.getElementById('modalType').addEventListener('change', toggleStrategyCodeEditor);
    toggleStrategyCodeEditor();
    bindScriptUpload('modalScriptFile', 'modalCode');
    document.getElementById('btnSaveModal').addEventListener('click', async () => {
        const body = {
            name: document.getElementById('modalName').value,
            type: document.getElementById('modalType').value,
            description: document.getElementById('modalDesc').value,
            params: JSON.parse(document.getElementById('modalParams').value || '{}'),
            code: document.getElementById('modalCode')?.value || '',
        };
        if (isEdit) {
            await updateStrategy(existing.id, body);
        } else {
            await createStrategy(body);
        }
        modal.style.display = 'none';
        await renderStrategyLib(document.getElementById('tabContent'));
    });
}

// ===== Strategy Verification Pipeline =====
async function renderStrategyVerify(container) {
    const strategies = (await getStrategies()).data || [];
    verifyStrategies = strategies;

    container.innerHTML = `
        <div class="pipeline-layout">
            <div class="pipeline-sidebar">
                <div class="card" style="margin-bottom:12px;">
                    <div class="card-title">基础配置</div>
                    <div class="form-group">
                        <label class="form-label">模式</label>
                        <div style="display:flex;gap:4px;">
                            <button class="btn btn-primary btn-sm mode-btn active" data-mode="single">单策略</button>
                            <button class="btn btn-sm mode-btn" data-mode="batch">批量</button>
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">策略</label>
                        <select class="form-select" id="pipelineStrategy">
                            ${strategies.map(s => `<option value="${s.id}">${s.name}</option>`).join('')}
                        </select>
                    </div>
                    <div class="form-group" id="singleCodeGroup">
                        <label class="form-label">股票代码</label>
                        <input class="form-input" id="pCode" value="sh.600000">
                    </div>
                    <div class="form-group">
                        <label class="form-label">回测区间</label>
                        <div style="display:flex;gap:6px;">
                            <input class="form-input" type="date" id="pStart" value="2023-01-01" style="flex:1;">
                            <input class="form-input" type="date" id="pEnd" value="2024-12-31" style="flex:1;">
                        </div>
                    </div>
                    <div class="form-group">
                        <label class="form-label">初始资金</label>
                        <input class="form-input" id="pCapital" value="100000">
                    </div>
                    <div class="card" id="factorConfigGroup" style="display:none;background:linear-gradient(180deg, rgba(6,182,212,0.10), rgba(15,23,42,0.65));border:1px solid rgba(6,182,212,0.25);margin-top:12px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:8px;">
                            <div>
                                <div style="font-size:12px;color:#67e8f9;letter-spacing:0.08em;text-transform:uppercase;">Factor Lab</div>
                                <div style="font-size:16px;font-weight:700;">截面选股配置</div>
                            </div>
                            <div id="factorPresetChips" style="display:flex;flex-wrap:wrap;gap:6px;"></div>
                        </div>
                        <div class="form-group">
                            <label class="form-label">TopN</label>
                            <input class="form-input" id="factorTopN" value="10">
                        </div>
                        <div class="form-group">
                            <label class="form-label">调仓频率</label>
                            <select class="form-select" id="factorRebalance">
                                <option value="monthly">月度</option>
                                <option value="weekly">每周</option>
                            </select>
                        </div>
                        <div class="form-group" style="margin-bottom:0;">
                            <label class="form-label">股票池代码（可选）</label>
                            <textarea class="form-input" id="factorPoolCodes" rows="4" placeholder="留空默认使用全部已下载股票；也可输入 sh.600000, sz.000001"></textarea>
                        </div>
                    </div>
                    <div class="card" id="factorScriptGroup" style="display:none;background:linear-gradient(180deg, rgba(59,130,246,0.10), rgba(15,23,42,0.65));border:1px solid rgba(59,130,246,0.25);margin-top:12px;">
                        <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;margin-bottom:10px;">
                            <div>
                                <div style="font-size:12px;color:#93c5fd;letter-spacing:0.08em;text-transform:uppercase;">Python Strategy</div>
                                <div style="font-size:16px;font-weight:700;">脚本编辑器</div>
                            </div>
                            <input type="file" id="factorScriptFile" accept=".py" style="font-size:11px;color:var(--text-muted);max-width:190px;">
                        </div>
                        <div style="font-size:11px;color:var(--text-muted);margin-bottom:8px;">支持 score_stocks(histories, context) 或 select_portfolio(histories, context)</div>
                        <textarea class="form-input" id="factorScriptEditor" rows="12" style="font-family:var(--font-mono);font-size:12px;white-space:pre;"></textarea>
                    </div>
                </div>

                <div class="pipeline-steps">
                    <div class="pipeline-step" data-step="1" id="step1">
                        <div class="step-header">
                            <span class="step-num">1</span>
                            <span class="step-title">回测分析</span>
                            <span class="step-status" id="step1Status"></span>
                        </div>
                        <button class="btn btn-primary" id="btnRunBacktest" style="width:100%;margin-top:8px;">运行</button>
                    </div>

                    <div class="pipeline-step" data-step="2" id="step2">
                        <div class="step-header">
                            <span class="step-num">2</span>
                            <span class="step-title">参数敏感性</span>
                            <span class="step-status" id="step2Status"></span>
                        </div>
                        <div class="form-group" style="margin-top:6px;">
                            <label class="form-label">扫描窗口</label>
                            <div style="display:flex;gap:4px;">
                                <button class="btn btn-sm scan-btn active" data-range="narrow">窄</button>
                                <button class="btn btn-sm scan-btn" data-range="medium">中</button>
                                <button class="btn btn-sm scan-btn" data-range="wide">宽</button>
                            </div>
                        </div>
                        <button class="btn btn-primary" id="btnRunSensitivity" style="width:100%;margin-top:6px;">运行</button>
                    </div>

                    <div class="pipeline-step" data-step="3" id="step3">
                        <div class="step-header">
                            <span class="step-num">3</span>
                            <span class="step-title">Walk-Forward</span>
                            <span class="step-status" id="step3Status"></span>
                        </div>
                        <div class="form-group" style="margin-top:6px;">
                            <label class="form-label">折数</label>
                            <input class="form-input" id="pFolds" value="5" style="width:60px;">
                        </div>
                        <button class="btn btn-primary" id="btnRunWalkForward" style="width:100%;margin-top:6px;">运行</button>
                    </div>

                    <div class="pipeline-step" data-step="4" id="step4">
                        <div class="step-header">
                            <span class="step-num">4</span>
                            <span class="step-title">总结</span>
                            <span class="step-status" id="step4Status"></span>
                        </div>
                    </div>
                </div>
            </div>

            <div class="pipeline-results" id="pipelineResults">
                <div class="card" style="text-align:center;color:var(--text-muted);padding:60px;">
                    选择策略并运行回测分析流水线
                </div>
            </div>
        </div>
    `;

    // Mode buttons
    container.querySelectorAll('.mode-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            container.querySelectorAll('.mode-btn').forEach(b => { b.classList.remove('active'); b.classList.remove('btn-primary'); b.classList.add('btn'); });
            btn.classList.add('active', 'btn-primary');
        });
    });

    // Scan range buttons
    container.querySelectorAll('.scan-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            container.querySelectorAll('.scan-btn').forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
        });
    });

    // Step 1: Backtest
    document.getElementById('btnRunBacktest').addEventListener('click', () => runPipelineBacktest());
    // Step 2: Sensitivity
    document.getElementById('btnRunSensitivity').addEventListener('click', () => runSensitivityAnalysis());
    // Step 3: Walk-Forward
    document.getElementById('btnRunWalkForward').addEventListener('click', () => runWalkForward());

    document.getElementById('pipelineStrategy').addEventListener('change', updatePipelineMode);
    updatePipelineMode();
}

function getSelectedStrategy() {
    const selectedId = document.getElementById('pipelineStrategy')?.value;
    return verifyStrategies.find(s => s.id === selectedId) || null;
}

function renderFactorChips(strategy) {
    const container = document.getElementById('factorPresetChips');
    if (!container) return;
    const factors = strategy?.params?.factor_configs || [];
    container.innerHTML = factors.map(item => `
        <span style="padding:4px 8px;border-radius:999px;background:rgba(6,182,212,0.16);color:#67e8f9;font-size:11px;font-family:var(--font-mono);">
            ${item.key} × ${item.weight}
        </span>
    `).join('');
}

function updatePipelineMode() {
    const strategy = getSelectedStrategy();
    const factorMode = isFactorStrategy(strategy);
    const singleCodeGroup = document.getElementById('singleCodeGroup');
    const factorConfigGroup = document.getElementById('factorConfigGroup');
    const factorScriptGroup = document.getElementById('factorScriptGroup');
    const factorScriptEditor = document.getElementById('factorScriptEditor');
    const sensitivityBtn = document.getElementById('btnRunSensitivity');
    const walkForwardBtn = document.getElementById('btnRunWalkForward');
    const step2Status = document.getElementById('step2Status');
    const step3Status = document.getElementById('step3Status');

    if (singleCodeGroup) singleCodeGroup.style.display = factorMode ? 'none' : 'block';
    if (factorConfigGroup) factorConfigGroup.style.display = factorMode ? 'block' : 'none';
    if (factorScriptGroup) factorScriptGroup.style.display = factorMode && strategy?.code ? 'block' : 'none';
    if (factorMode) {
        renderFactorChips(strategy);
        document.getElementById('factorTopN').value = strategy?.params?.top_n || 10;
        document.getElementById('factorRebalance').value = strategy?.params?.rebalance || 'monthly';
        if (factorScriptEditor) factorScriptEditor.value = strategy?.code || '';
        bindScriptUpload('factorScriptFile', 'factorScriptEditor');
        sensitivityBtn.disabled = true;
        walkForwardBtn.disabled = true;
        sensitivityBtn.style.opacity = '0.5';
        walkForwardBtn.style.opacity = '0.5';
        step2Status.innerHTML = '<span class="badge badge-warning">后续</span>';
        step3Status.innerHTML = '<span class="badge badge-warning">后续</span>';
    } else {
        sensitivityBtn.disabled = false;
        walkForwardBtn.disabled = false;
        sensitivityBtn.style.opacity = '1';
        walkForwardBtn.style.opacity = '1';
        step2Status.innerHTML = '';
        step3Status.innerHTML = '';
    }
}

async function runPipelineBacktest() {
    const status = document.getElementById('step1Status');
    status.innerHTML = '<span class="badge badge-warning">运行中</span>';

    const strategy = getSelectedStrategy();
    const factorMode = isFactorStrategy(strategy);

    try {
        const data = factorMode
            ? await startFactorBacktest(buildFactorRunPayload(strategy, {
                start_date: document.getElementById('pStart').value,
                end_date: document.getElementById('pEnd').value,
                capital: document.getElementById('pCapital').value,
                top_n: document.getElementById('factorTopN').value,
                rebalance: document.getElementById('factorRebalance').value,
                pool_codes: document.getElementById('factorPoolCodes').value,
                script: document.getElementById('factorScriptEditor')?.value || '',
            }))
            : await startBacktest({
                strategy: document.getElementById('pipelineStrategy').value,
                code: document.getElementById('pCode').value,
                start_date: document.getElementById('pStart').value,
                end_date: document.getElementById('pEnd').value,
                capital: parseFloat(document.getElementById('pCapital').value),
            });
        if (data.error) throw new Error(data.error);

        status.innerHTML = '<span class="badge badge-success">完成</span>';
        factorMode ? displayFactorResults(data.data) : displayPipelineResults(data.data);
    } catch (e) {
        status.innerHTML = `<span class="badge badge-error">失败</span>`;
    }
}

async function displayFactorResults(data) {
    const container = document.getElementById('pipelineResults');
    const m = data.metrics || {};
    const curve = data.equity_curve || [];
    const rebalances = data.rebalances || [];
    const upDown = (v, suffix = '%') => {
        const cls = v >= 0 ? 'price-up' : 'price-down';
        const sign = v >= 0 ? '+' : '';
        return `<span class="${cls}">${sign}${Number(v || 0).toFixed(2)}${suffix}</span>`;
    };

    container.innerHTML = `
        <div class="pipeline-section">
            <div class="section-header">
                <span class="step-num">1</span>
                <span>因子组合回测</span>
                <span style="margin-left:auto;font-size:11px;color:#67e8f9;letter-spacing:0.08em;text-transform:uppercase;">Factor Lab</span>
            </div>

            <div class="metrics-grid">
                <div class="metric-card">
                    <div class="metric-value">${upDown(m.total_return || 0)}</div>
                    <div class="metric-label">总收益率</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value" style="font-size:16px;">${(m.final_equity || 0).toLocaleString()}</div>
                    <div class="metric-label">最终权益</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${m.rebalance_count || 0}</div>
                    <div class="metric-label">调仓次数</div>
                </div>
                <div class="metric-card">
                    <div class="metric-value">${data.pool_size || 0}</div>
                    <div class="metric-label">股票池数量</div>
                </div>
            </div>

            <div class="card" style="margin-bottom:12px;background:linear-gradient(180deg, rgba(6,182,212,0.10), rgba(15,23,42,0.65));border:1px solid rgba(6,182,212,0.18);">
                <div class="card-title">权益曲线</div>
                <div id="factorEquityCurve" style="height:280px;"></div>
            </div>

            <div class="card">
                <div class="card-title">调仓快照 (${rebalances.length} 次)</div>
                <div style="display:flex;flex-direction:column;gap:12px;">
                    ${rebalances.map(item => `
                        <div style="border:1px solid rgba(6,182,212,0.18);border-radius:10px;padding:14px;background:rgba(15,23,42,0.65);">
                            <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px;gap:8px;">
                                <div style="font-weight:700;">${item.date}</div>
                                <div style="font-size:11px;color:var(--text-muted);">现金 ${Number(item.cash || 0).toLocaleString()}</div>
                            </div>
                            <div style="display:flex;flex-wrap:wrap;gap:8px;">
                                ${(item.selected || []).map(stock => `
                                    <div style="min-width:200px;flex:1;background:rgba(6,182,212,0.08);border:1px solid rgba(6,182,212,0.16);border-radius:8px;padding:10px;">
                                        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                                            <strong>${stock.code}</strong>
                                            <span class="price-up" style="font-family:var(--font-mono);">${Number(stock.score || 0).toFixed(2)}</span>
                                        </div>
                                        <div style="font-size:11px;color:var(--text-muted);display:flex;flex-wrap:wrap;gap:6px;">
                                            ${Object.entries(stock.factor_values || {}).map(([key, value]) => `<span>${key}: ${Number(value).toFixed(3)}</span>`).join('') || '<span>无因子明细</span>'}
                                        </div>
                                    </div>
                                `).join('') || '<div style="color:var(--text-muted);font-size:12px;">无有效入选股票</div>'}
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        </div>

        <div class="pipeline-section" id="sensitivitySection" style="display:none;"></div>
        <div class="pipeline-section" id="walkForwardSection" style="display:none;"></div>
        <div class="pipeline-section" id="summarySection" style="display:none;"></div>
    `;

    if (curve.length > 0) {
        const { createChart } = await import('https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.mjs');
        const chartContainer = document.getElementById('factorEquityCurve');
        const chart = createChart(chartContainer, {
            layout: { background: { color: '#151d2b' }, textColor: '#94a3b8', fontSize: 11 },
            grid: { vertLines: { color: '#1e2a3a' }, horzLines: { color: '#1e2a3a' } },
            rightPriceScale: { borderColor: '#1e2a3a' },
            timeScale: { borderColor: '#1e2a3a', timeVisible: false },
            handleScroll: true, handleScale: true,
        });
        chart.addLineSeries({ color: '#06b6d4', lineWidth: 2, title: '因子组合', priceLineVisible: false })
            .setData(curve.map(p => ({ time: p.date, value: p.equity })));
        chart.timeScale().fitContent();
        new ResizeObserver(() => chart.applyOptions({ width: chartContainer.clientWidth, height: chartContainer.clientHeight })).observe(chartContainer);
    }
}

async function displayPipelineResults(data) {
    const container = document.getElementById('pipelineResults');
    const m = data.metrics || {};
    const trades = data.trades || [];
    const curve = data.equity_curve || [];

    const upDown = (v, suffix = '%') => {
        const cls = v >= 0 ? 'price-up' : 'price-down';
        const sign = v >= 0 ? '+' : '';
        return `<span class="${cls}">${sign}${v.toFixed(2)}${suffix}</span>`;
    };

    container.innerHTML = `
        <div class="pipeline-section">
            <div class="section-header">
                <span class="step-num">1</span>
                <span>回测分析</span>
            </div>

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
                <div class="metric-card">
                    <div class="metric-value" style="font-size:16px;">${(m.final_equity || 0).toLocaleString()}</div>
                    <div class="metric-label">最终权益</div>
                </div>
            </div>

            <div class="card" style="margin-bottom:12px;">
                <div class="card-title">收益曲线</div>
                <div id="pEquityCurve" style="height:280px;"></div>
            </div>

            <div class="card" style="margin-bottom:12px;">
                <div class="card-title">月度收益</div>
                <div id="pMonthlyReturns"></div>
            </div>

            <div class="card">
                <div class="card-title">交易记录 (${trades.length}笔)</div>
                <div style="max-height:400px;overflow-y:auto;">
                    <table>
                        <thead><tr><th>日期</th><th>操作</th><th>代码</th><th>价格</th><th>数量</th><th>盈亏</th><th>原因</th></tr></thead>
                        <tbody>
                            ${trades.map(t => `
                                <tr>
                                    <td>${t.date}</td>
                                    <td><span class="${t.action === 'buy' ? 'price-up' : 'price-down'}">${t.action === 'buy' ? '买入' : '卖出'}</span></td>
                                    <td>${t.code}</td>
                                    <td>${t.price?.toFixed(2)}</td>
                                    <td>${t.amount}</td>
                                    <td>${t.pnl != null ? upDown(t.pnl, '') : '--'}</td>
                                    <td style="font-size:11px;color:var(--text-muted);">${t.reason || ''}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>

        <div class="pipeline-section" id="sensitivitySection" style="display:none;"></div>
        <div class="pipeline-section" id="walkForwardSection" style="display:none;"></div>
        <div class="pipeline-section" id="summarySection" style="display:none;"></div>
    `;

    // Render equity curve
    if (curve.length > 0) {
        const { createChart } = await import('https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.mjs');
        const chartContainer = document.getElementById('pEquityCurve');
        const chart = createChart(chartContainer, {
            layout: { background: { color: '#151d2b' }, textColor: '#94a3b8', fontSize: 11 },
            grid: { vertLines: { color: '#1e2a3a' }, horzLines: { color: '#1e2a3a' } },
            rightPriceScale: { borderColor: '#1e2a3a' },
            timeScale: { borderColor: '#1e2a3a', timeVisible: false },
            handleScroll: true, handleScale: true,
        });
        chart.addLineSeries({ color: '#3b82f6', lineWidth: 2, title: '策略', priceLineVisible: false })
            .setData(curve.map(p => ({ time: p.date, value: p.equity })));
        chart.addLineSeries({ color: '#64748b', lineWidth: 1, lineStyle: 2, title: '基准', priceLineVisible: false })
            .setData(curve.map(p => ({ time: p.date, value: p.benchmark })));
        chart.timeScale().fitContent();
        new ResizeObserver(() => chart.applyOptions({ width: chartContainer.clientWidth, height: chartContainer.clientHeight })).observe(chartContainer);
    }

    // Monthly returns
    renderMonthlyReturns(curve);
}

function renderMonthlyReturns(curve) {
    const container = document.getElementById('pMonthlyReturns');
    if (!curve || curve.length === 0) { container.innerHTML = '无数据'; return; }

    const monthly = {};
    let prevEquity = curve[0].equity;
    for (const p of curve) {
        const ym = p.date.substring(0, 7);
        if (!monthly[ym]) monthly[ym] = { start: prevEquity, end: p.equity };
        monthly[ym].end = p.equity;
    }

    const rows = Object.entries(monthly).map(([ym, v]) => {
        const ret = ((v.end - v.start) / v.start * 100);
        const cls = ret >= 0 ? 'price-up' : 'price-down';
        const bg = ret >= 0 ? 'rgba(239,68,68,0.12)' : 'rgba(34,197,94,0.12)';
        return `<div style="display:inline-block;padding:4px 8px;margin:2px;border-radius:4px;background:${bg};font-size:11px;">
            <span style="color:var(--text-muted)">${ym}</span>
            <span class="${cls}" style="font-family:var(--font-mono);margin-left:4px;">${ret >= 0 ? '+' : ''}${ret.toFixed(1)}%</span>
        </div>`;
    });

    container.innerHTML = `<div style="display:flex;flex-wrap:wrap;gap:2px;">${rows.join('')}</div>`;
}

async function runSensitivityAnalysis() {
    if (isFactorStrategy(getSelectedStrategy())) return;
    const status = document.getElementById('step2Status');
    status.innerHTML = '<span class="badge badge-warning">运行中</span>';

    const strategy = document.getElementById('pipelineStrategy').value;
    const code = document.getElementById('pCode').value;
    const start = document.getElementById('pStart').value;
    const end = document.getElementById('pEnd').value;
    const capital = parseFloat(document.getElementById('pCapital').value);
    const range = document.querySelector('.scan-btn.active')?.dataset.range || 'narrow';

    // Generate parameter variations
    const paramRanges = {
        ma_cross: {
            narrow: [{ short: 3, long: 15 }, { short: 5, long: 20 }, { short: 5, long: 30 }, { short: 10, long: 20 }, { short: 10, long: 30 }],
            medium: [{ short: 3, long: 10 }, { short: 3, long: 20 }, { short: 5, long: 15 }, { short: 5, long: 20 }, { short: 5, long: 30 }, { short: 10, long: 20 }, { short: 10, long: 30 }, { short: 10, long: 60 }],
            wide: [{ short: 3, long: 10 }, { short: 3, long: 20 }, { short: 3, long: 30 }, { short: 5, long: 10 }, { short: 5, long: 15 }, { short: 5, long: 20 }, { short: 5, long: 30 }, { short: 5, long: 60 }, { short: 10, long: 20 }, { short: 10, long: 30 }, { short: 10, long: 60 }, { short: 20, long: 60 }],
        },
    };

    const variations = paramRanges[strategy]?.[range] || [{}];
    const results = [];

    for (const params of variations) {
        try {
            const data = await startBacktest({ strategy, code, start_date: start, end_date: end, capital, params });
            results.push({ params, metrics: data.data?.metrics || {} });
        } catch { results.push({ params, metrics: {} }); }
    }

    status.innerHTML = '<span class="badge badge-success">完成</span>';

    const section = document.getElementById('sensitivitySection');
    section.style.display = 'block';
    section.innerHTML = `
        <div class="section-header">
            <span class="step-num">2</span>
            <span>参数敏感性分析</span>
            <span style="font-size:11px;color:var(--text-muted);margin-left:auto;">${results.length} 组参数</span>
        </div>
        <div class="card">
            <table>
                <thead><tr><th>参数</th><th>收益率</th><th>年化</th><th>最大回撤</th><th>夏普</th><th>胜率</th><th>交易数</th></tr></thead>
                <tbody>
                    ${results.map(r => {
                        const m = r.metrics;
                        const cls = (m.total_return || 0) >= 0 ? 'price-up' : 'price-down';
                        return `<tr>
                            <td style="font-size:11px;">${JSON.stringify(r.params)}</td>
                            <td class="${cls}">${(m.total_return || 0).toFixed(2)}%</td>
                            <td>${(m.annual_return || 0).toFixed(2)}%</td>
                            <td class="price-down">${(m.max_drawdown || 0).toFixed(2)}%</td>
                            <td>${(m.sharpe_ratio || 0).toFixed(2)}</td>
                            <td>${(m.win_rate || 0).toFixed(1)}%</td>
                            <td>${m.total_trades || 0}</td>
                        </tr>`;
                    }).join('')}
                </tbody>
            </table>
        </div>
    `;

    section.scrollIntoView({ behavior: 'smooth' });
}

async function runWalkForward() {
    if (isFactorStrategy(getSelectedStrategy())) return;
    const status = document.getElementById('step3Status');
    status.innerHTML = '<span class="badge badge-warning">运行中</span>';

    const strategy = document.getElementById('pipelineStrategy').value;
    const code = document.getElementById('pCode').value;
    const start = document.getElementById('pStart').value;
    const end = document.getElementById('pEnd').value;
    const capital = parseFloat(document.getElementById('pCapital').value);
    const folds = parseInt(document.getElementById('pFolds').value) || 5;

    // Split date range into folds
    const startDate = new Date(start);
    const endDate = new Date(end);
    const totalDays = (endDate - startDate) / (1000 * 60 * 60 * 24);
    const foldDays = Math.floor(totalDays / folds);

    const results = [];
    for (let i = 0; i < folds; i++) {
        const foldStart = new Date(startDate.getTime() + i * foldDays * 86400000);
        const foldEnd = new Date(foldStart.getTime() + foldDays * 86400000);
        const fs = foldStart.toISOString().split('T')[0];
        const fe = foldEnd.toISOString().split('T')[0];

        try {
            const data = await startBacktest({ strategy, code, start_date: fs, end_date: fe, capital });
            results.push({ fold: i + 1, start: fs, end: fe, metrics: data.data?.metrics || {} });
        } catch { results.push({ fold: i + 1, start: fs, end: fe, metrics: {} }); }
    }

    status.innerHTML = '<span class="badge badge-success">完成</span>';
    document.getElementById('step4Status').innerHTML = '<span class="badge badge-success">完成</span>';

    const section = document.getElementById('walkForwardSection');
    section.style.display = 'block';

    const avgReturn = results.reduce((s, r) => s + (r.metrics.total_return || 0), 0) / results.length;
    const avgSharpe = results.reduce((s, r) => s + (r.metrics.sharpe_ratio || 0), 0) / results.length;
    const positiveFolds = results.filter(r => (r.metrics.total_return || 0) > 0).length;

    section.innerHTML = `
        <div class="section-header">
            <span class="step-num">3</span>
            <span>Walk-Forward 分析</span>
        </div>
        <div class="card" style="margin-bottom:12px;">
            <table>
                <thead><tr><th>折</th><th>区间</th><th>收益率</th><th>最大回撤</th><th>夏普</th><th>交易数</th></tr></thead>
                <tbody>
                    ${results.map(r => {
                        const m = r.metrics;
                        const cls = (m.total_return || 0) >= 0 ? 'price-up' : 'price-down';
                        return `<tr>
                            <td>${r.fold}</td>
                            <td style="font-size:11px;">${r.start} ~ ${r.end}</td>
                            <td class="${cls}">${(m.total_return || 0).toFixed(2)}%</td>
                            <td class="price-down">${(m.max_drawdown || 0).toFixed(2)}%</td>
                            <td>${(m.sharpe_ratio || 0).toFixed(2)}</td>
                            <td>${m.total_trades || 0}</td>
                        </tr>`;
                    }).join('')}
                </tbody>
            </table>
        </div>
    `;

    // Summary section
    const summary = document.getElementById('summarySection');
    summary.style.display = 'block';
    const score = (avgReturn > 0 ? 40 : 0) + (avgSharpe > 0.5 ? 30 : avgSharpe > 0 ? 15 : 0) + (positiveFolds / folds > 0.6 ? 30 : positiveFolds / folds > 0.4 ? 15 : 0);
    const grade = score >= 70 ? 'A' : score >= 50 ? 'B' : score >= 30 ? 'C' : 'D';
    const gradeColor = { A: 'var(--green)', B: '#3b82f6', C: 'var(--yellow)', D: 'var(--red)' }[grade];

    summary.innerHTML = `
        <div class="section-header">
            <span class="step-num">4</span>
            <span>总结</span>
        </div>
        <div class="card">
            <div style="display:flex;align-items:center;gap:24px;">
                <div style="text-align:center;">
                    <div style="font-size:48px;font-weight:800;color:${gradeColor};font-family:var(--font-mono);">${grade}</div>
                    <div style="font-size:12px;color:var(--text-muted);">综合评分 ${score}/100</div>
                </div>
                <div style="flex:1;">
                    <div style="margin-bottom:8px;">
                        <span class="info-item">平均收益: <span class="${avgReturn >= 0 ? 'price-up' : 'price-down'}">${avgReturn.toFixed(2)}%</span></span>
                    </div>
                    <div style="margin-bottom:8px;">
                        <span class="info-item">平均夏普: <span>${avgSharpe.toFixed(2)}</span></span>
                    </div>
                    <div>
                        <span class="info-item">盈利折数: <span>${positiveFolds}/${folds}</span></span>
                    </div>
                </div>
            </div>
        </div>
    `;

    summary.scrollIntoView({ behavior: 'smooth' });
}

export function destroy() {}
