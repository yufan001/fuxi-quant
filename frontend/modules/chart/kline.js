const CHART_THEMES = {
    dark: {
        background: '#111827',
        text: '#94a3b8',
        grid: '#1e2a3a',
        border: '#1e2a3a',
        crosshair: '#3b82f6',
    },
    light: {
        background: '#ffffff',
        text: '#475569',
        grid: '#e2e8f0',
        border: '#d8e0ea',
        crosshair: '#2563eb',
    },
};

const DEFAULT_PRICE_SCALE_MARGINS = { top: 0.08, bottom: 0.12 };
const MIN_PRICE_MARGIN = 0.02;
const MAX_PRICE_MARGIN_SUM = 0.86;
const VERTICAL_DRAG_MARGIN_SPEED = 0.95;

function normalizeTheme(theme) {
    return theme === 'light' ? 'light' : 'dark';
}

function clamp(value, min, max) {
    return Math.max(min, Math.min(max, value));
}

function normalizePriceScaleMargins(margins) {
    let top = clamp(Number(margins.top), MIN_PRICE_MARGIN, MAX_PRICE_MARGIN_SUM - MIN_PRICE_MARGIN);
    let bottom = clamp(Number(margins.bottom), MIN_PRICE_MARGIN, MAX_PRICE_MARGIN_SUM - MIN_PRICE_MARGIN);
    const sum = top + bottom;
    if (sum > MAX_PRICE_MARGIN_SUM) {
        const overflow = sum - MAX_PRICE_MARGIN_SUM;
        if (bottom > top) {
            bottom = Math.max(MIN_PRICE_MARGIN, bottom - overflow);
        } else {
            top = Math.max(MIN_PRICE_MARGIN, top - overflow);
        }
    }
    return { top, bottom };
}

function chartThemeOptions(theme) {
    const palette = CHART_THEMES[normalizeTheme(theme)];
    return {
        layout: {
            background: { color: palette.background },
            textColor: palette.text,
            fontSize: 12,
        },
        grid: {
            vertLines: { color: palette.grid },
            horzLines: { color: palette.grid },
        },
        crosshair: {
            mode: 0,
            vertLine: { color: palette.crosshair, width: 1, style: 2 },
            horzLine: { color: palette.crosshair, width: 1, style: 2 },
        },
        rightPriceScale: {
            borderColor: palette.border,
        },
        timeScale: {
            borderColor: palette.border,
        },
    };
}

export class KlineChart {
    constructor(container) {
        this.container = container;
        this.chart = null;
        this.candleSeries = null;
        this.volumeSeries = null;
        this.maSeries = {};
        this.profileZones = [];
        this.profileVisible = true;
        this.profileOverlay = null;
        this.trendSeries = [];
        this.supportResistanceLines = [];
        this.volatilitySeries = [];
        this.resizeObserver = null;
        this.theme = 'dark';
        this.priceScaleMargins = { ...DEFAULT_PRICE_SCALE_MARGINS };
        this.dragState = null;
        this.dragHandlers = null;
    }

    async init() {
        const { createChart } = await import('https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.mjs');

        const themeOptions = chartThemeOptions(this.theme);
        this.chart = createChart(this.container, {
            ...themeOptions,
            rightPriceScale: {
                ...themeOptions.rightPriceScale,
                scaleMargins: this.priceScaleMargins,
            },
            timeScale: {
                ...themeOptions.timeScale,
                timeVisible: false,
            },
            handleScroll: {
                mouseWheel: true,
                pressedMouseMove: false,
                horzTouchDrag: true,
                vertTouchDrag: true,
            },
            handleScale: true,
        });

        this.candleSeries = this.chart.addCandlestickSeries({
            upColor: '#ef4444',
            downColor: '#22c55e',
            borderUpColor: '#ef4444',
            borderDownColor: '#22c55e',
            wickUpColor: '#ef4444',
            wickDownColor: '#22c55e',
        });

        this.volumeSeries = this.chart.addHistogramSeries({
            priceFormat: { type: 'volume' },
            priceScaleId: 'volume',
        });

        this.chart.priceScale('volume').applyOptions({
            scaleMargins: { top: 0.85, bottom: 0 },
        });
        this._applyPriceScaleMargins(this.priceScaleMargins);

        this.profileOverlay = document.createElement('div');
        this.profileOverlay.className = 'chart-profile-overlay';
        this.container.style.position = this.container.style.position || 'relative';
        this.container.appendChild(this.profileOverlay);

        this.chart.timeScale().subscribeVisibleLogicalRangeChange(() => this.renderProfileOverlay());
        this._handleResize();
        this._installDragPan();
    }

    applyTheme(theme) {
        this.theme = normalizeTheme(theme);
        if (!this.chart) return;
        this.chart.applyOptions(chartThemeOptions(this.theme));
        this._applyPriceScaleMargins(this.priceScaleMargins);
        requestAnimationFrame(() => this.renderProfileOverlay());
    }

    _handleResize() {
        this.resizeObserver = new ResizeObserver(() => {
            if (this.chart) {
                this.chart.applyOptions({
                    width: this.container.clientWidth,
                    height: this.container.clientHeight,
                });
                this.renderProfileOverlay();
            }
        });
        this.resizeObserver.observe(this.container);
    }

    _installDragPan() {
        const onPointerDown = event => {
            if (event.button !== 0 || event.ctrlKey || event.metaKey || event.altKey) return;
            if (event.target instanceof Element && event.target.closest('a, button, input, select, textarea')) return;
            const visibleRange = this.chart?.timeScale().getVisibleLogicalRange();
            const width = this.container.clientWidth || 0;
            if (!visibleRange || width <= 0) return;

            this.dragState = {
                pointerId: event.pointerId,
                startX: event.clientX,
                startY: event.clientY,
                startRange: { from: visibleRange.from, to: visibleRange.to },
                startMargins: { ...this.priceScaleMargins },
                logicalPerPixel: (visibleRange.to - visibleRange.from) / width,
                marginPerPixel: VERTICAL_DRAG_MARGIN_SPEED / Math.max(1, this.container.clientHeight || 0),
            };
            this.container.classList.add('is-grabbing-chart');
            document.body.classList.add('chart-is-grabbing');
            try {
                this.container.setPointerCapture?.(event.pointerId);
            } catch (e) {
                // Synthetic pointer events and some browser edge cases may not allow capture.
            }
            event.preventDefault();
        };

        const onPointerMove = event => {
            if (!this.dragState || event.pointerId !== this.dragState.pointerId) return;
            const deltaX = event.clientX - this.dragState.startX;
            const deltaY = event.clientY - this.dragState.startY;
            const offset = deltaX * this.dragState.logicalPerPixel;
            this.chart.timeScale().setVisibleLogicalRange({
                from: this.dragState.startRange.from - offset,
                to: this.dragState.startRange.to - offset,
            });
            this._applyVerticalDrag(deltaY);
            this.renderProfileOverlay();
            event.preventDefault();
        };

        const finishDrag = event => {
            if (!this.dragState) return;
            if (event?.pointerId != null && event.pointerId !== this.dragState.pointerId) return;
            try {
                this.container.releasePointerCapture?.(this.dragState.pointerId);
            } catch (e) {
                // Pointer capture may already be released by the browser.
            }
            this.dragState = null;
            this.container.classList.remove('is-grabbing-chart');
            document.body.classList.remove('chart-is-grabbing');
        };

        this.dragHandlers = { onPointerDown, onPointerMove, finishDrag };
        this.container.classList.add('can-grab-chart');
        this.container.addEventListener('pointerdown', onPointerDown);
        this.container.addEventListener('pointermove', onPointerMove);
        this.container.addEventListener('pointerup', finishDrag);
        this.container.addEventListener('pointercancel', finishDrag);
        this.container.addEventListener('pointerleave', finishDrag);
    }

    _removeDragPan() {
        if (!this.dragHandlers) return;
        this.container.removeEventListener('pointerdown', this.dragHandlers.onPointerDown);
        this.container.removeEventListener('pointermove', this.dragHandlers.onPointerMove);
        this.container.removeEventListener('pointerup', this.dragHandlers.finishDrag);
        this.container.removeEventListener('pointercancel', this.dragHandlers.finishDrag);
        this.container.removeEventListener('pointerleave', this.dragHandlers.finishDrag);
        this.container.classList.remove('can-grab-chart', 'is-grabbing-chart');
        document.body.classList.remove('chart-is-grabbing');
        this.dragHandlers = null;
        this.dragState = null;
    }

    _applyVerticalDrag(deltaY) {
        if (!this.dragState) return;
        const shift = -deltaY * this.dragState.marginPerPixel;
        const margins = normalizePriceScaleMargins({
            top: this.dragState.startMargins.top - shift,
            bottom: this.dragState.startMargins.bottom + shift,
        });
        this._applyPriceScaleMargins(margins);
    }

    _applyPriceScaleMargins(margins) {
        this.priceScaleMargins = normalizePriceScaleMargins(margins);
        if (!this.chart) return;
        this.chart.priceScale('right').applyOptions({
            autoScale: true,
            scaleMargins: this.priceScaleMargins,
        });
        this.container.dataset.priceMarginTop = this.priceScaleMargins.top.toFixed(4);
        this.container.dataset.priceMarginBottom = this.priceScaleMargins.bottom.toFixed(4);
    }

    setData(data, options = {}) {
        if (!data || data.length === 0) return;
        const timeVisible = options.timeVisible ?? Boolean(data[0]?.time);
        const preserveVisibleRange = Boolean(options.preserveVisibleRange);
        const focusVisibleBars = Math.max(0, Number(options.focusVisibleBars || 0));
        const focusRightOffset = Math.max(0, Number(options.focusRightOffset ?? 8));
        const visibleRange = preserveVisibleRange
            ? this.chart.timeScale().getVisibleLogicalRange()
            : null;
        this.chart.applyOptions({ timeScale: { timeVisible } });

        const candles = data.map(d => ({
            time: d.time ?? d.date,
            open: d.open,
            high: d.high,
            low: d.low,
            close: d.close,
        }));

        const volumes = data.map(d => ({
            time: d.time ?? d.date,
            value: d.volume,
            color: d.close >= d.open ? 'rgba(239, 68, 68, 0.4)' : 'rgba(34, 197, 94, 0.4)',
        }));

        this.candleSeries.setData(candles);
        this.volumeSeries.setData(volumes);
        if (visibleRange) {
            this.chart.timeScale().setVisibleLogicalRange(visibleRange);
        } else if (focusVisibleBars > 0) {
            const lastIndex = data.length - 1;
            const from = Math.max(0, data.length - focusVisibleBars);
            this.chart.timeScale().setVisibleLogicalRange({
                from,
                to: lastIndex + focusRightOffset,
            });
        } else {
            this.chart.timeScale().fitContent();
        }
        requestAnimationFrame(() => this.renderProfileOverlay());
    }

    addMA(period, color) {
        if (this.maSeries[period]) {
            this.chart.removeSeries(this.maSeries[period]);
        }
        this.maSeries[period] = this.chart.addLineSeries({
            color,
            lineWidth: 1,
            priceLineVisible: false,
            lastValueVisible: false,
        });
    }

    setMAData(period, data) {
        if (!this.maSeries[period]) return;
        this.maSeries[period].setData(data);
    }

    setVolumeVisible(visible) {
        this.volumeSeries?.applyOptions({ visible: Boolean(visible) });
    }

    setProfileZones(zones, visible = true) {
        this.profileZones = Array.isArray(zones) ? zones : [];
        this.profileVisible = Boolean(visible);
        this.renderProfileOverlay();
    }

    setProfileVisible(visible) {
        this.profileVisible = Boolean(visible);
        this.renderProfileOverlay();
    }

    renderProfileOverlay() {
        if (!this.profileOverlay || !this.candleSeries) return;
        if (!this.profileVisible || this.profileZones.length === 0) {
            this.profileOverlay.innerHTML = '';
            return;
        }
        const width = this.container.clientWidth || 0;
        const html = this.profileZones
            .map(zone => {
                const topCoord = this.candleSeries.priceToCoordinate(Number(zone.upper));
                const bottomCoord = this.candleSeries.priceToCoordinate(Number(zone.lower));
                if (topCoord == null || bottomCoord == null) return '';
                const top = Math.min(topCoord, bottomCoord);
                const height = Math.max(Math.abs(bottomCoord - topCoord), 3);
                const strength = Math.max(0.12, Math.min(0.36, Number(zone.volume_pct || 0) * 1.2));
                const labelTop = Math.max(2, top + 2);
                const title = `VP${zone.rank || ''} ${Number(zone.lower).toFixed(1)}-${Number(zone.upper).toFixed(1)}`;
                return `
                    <div class="vp-zone-band" style="top:${top}px;height:${height}px;background:rgba(245,158,11,${strength});"></div>
                    <div class="vp-zone-label" style="top:${labelTop}px;right:${Math.max(12, width * 0.02)}px;">${title}</div>
                `;
            })
            .join('');
        this.profileOverlay.innerHTML = html;
    }

    clearTrendOverlay() {
        for (const series of this.trendSeries) {
            this.chart.removeSeries(series);
        }
        this.trendSeries = [];
    }

    setTrendOverlay(trend, visible = true) {
        this.clearTrendOverlay();
        if (!visible || !trend || !trend.visible || !trend.lower_line || !trend.upper_line) return;

        const isUp = trend.direction === 'up';
        const lower = this.chart.addLineSeries({
            color: isUp ? 'rgba(34,197,94,0.95)' : 'rgba(239,68,68,0.85)',
            lineWidth: 2,
            lineStyle: 0,
            priceLineVisible: false,
            lastValueVisible: false,
        });
        const upper = this.chart.addLineSeries({
            color: isUp ? 'rgba(132,204,22,0.85)' : 'rgba(248,113,113,0.95)',
            lineWidth: 2,
            lineStyle: 2,
            priceLineVisible: false,
            lastValueVisible: false,
        });
        lower.setData(trend.lower_line.map(point => ({ time: point.time, value: point.value })));
        upper.setData(trend.upper_line.map(point => ({ time: point.time, value: point.value })));
        this.trendSeries = [lower, upper];
    }

    clearSupportResistanceOverlay() {
        for (const line of this.supportResistanceLines) {
            this.candleSeries?.removePriceLine(line);
        }
        this.supportResistanceLines = [];
    }

    setSupportResistanceOverlay(levels, visible = true) {
        this.clearSupportResistanceOverlay();
        const sr = levels?.support_resistance || levels;
        if (!visible || !sr?.visible || !sr.support || !sr.resistance || !this.candleSeries) return;

        const support = this.candleSeries.createPriceLine({
            price: Number(sr.support.center),
            color: 'rgba(34,197,94,0.95)',
            lineWidth: 2,
            lineStyle: 2,
            axisLabelVisible: true,
            title: `120m 支撑 ${Number(sr.support.center).toFixed(1)}`,
        });
        const resistance = this.candleSeries.createPriceLine({
            price: Number(sr.resistance.center),
            color: 'rgba(239,68,68,0.95)',
            lineWidth: 2,
            lineStyle: 2,
            axisLabelVisible: true,
            title: `120m 压力 ${Number(sr.resistance.center).toFixed(1)}`,
        });
        this.supportResistanceLines = [support, resistance];
    }

    clearVolatilityOverlay() {
        for (const series of this.volatilitySeries) {
            this.chart.removeSeries(series);
        }
        this.volatilitySeries = [];
    }

    setVolatilityOverlay(volatility, visible = true) {
        this.clearVolatilityOverlay();
        const points = Array.isArray(volatility?.points)
            ? volatility.points
                .map(point => ({ time: point.time, value: Number(point.value) }))
                .filter(point => point.time && Number.isFinite(point.value))
            : [];
        if (!visible || !volatility?.visible || !points.length) return;

        const panicVolatility = this.chart.addLineSeries({
            priceScaleId: 'panic-volatility',
            color: 'rgba(100,116,139,0.9)',
            lineWidth: 2,
            lineStyle: 0,
            priceLineVisible: false,
            lastValueVisible: false,
            crosshairMarkerVisible: false,
        });
        this.chart.priceScale('panic-volatility').applyOptions({
            visible: false,
            scaleMargins: { top: 0.78, bottom: 0.06 },
        });
        panicVolatility.setData(points);
        this.volatilitySeries = [panicVolatility];
    }

    destroy() {
        this._removeDragPan();
        if (this.resizeObserver) {
            this.resizeObserver.disconnect();
            this.resizeObserver = null;
        }
        this.clearTrendOverlay();
        this.clearSupportResistanceOverlay();
        this.clearVolatilityOverlay();
        if (this.chart) {
            this.chart.remove();
            this.chart = null;
        }
    }
}

export function calcMA(data, period) {
    const result = [];
    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) continue;
        let sum = 0;
        for (let j = 0; j < period; j++) {
            sum += data[i - j].close;
        }
        result.push({ time: data[i].time ?? data[i].date, value: sum / period });
    }
    return result;
}
