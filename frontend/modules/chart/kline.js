export class KlineChart {
    constructor(container) {
        this.container = container;
        this.chart = null;
        this.candleSeries = null;
        this.volumeSeries = null;
        this.maSeries = {};
    }

    async init() {
        const { createChart } = await import('https://unpkg.com/lightweight-charts@4.2.0/dist/lightweight-charts.standalone.production.mjs');

        this.chart = createChart(this.container, {
            layout: {
                background: { color: '#111827' },
                textColor: '#94a3b8',
                fontSize: 12,
            },
            grid: {
                vertLines: { color: '#1e2a3a' },
                horzLines: { color: '#1e2a3a' },
            },
            crosshair: {
                mode: 0,
                vertLine: { color: '#3b82f6', width: 1, style: 2 },
                horzLine: { color: '#3b82f6', width: 1, style: 2 },
            },
            rightPriceScale: {
                borderColor: '#1e2a3a',
            },
            timeScale: {
                borderColor: '#1e2a3a',
                timeVisible: false,
            },
            handleScroll: true,
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

        this._handleResize();
    }

    _handleResize() {
        const observer = new ResizeObserver(() => {
            if (this.chart) {
                this.chart.applyOptions({
                    width: this.container.clientWidth,
                    height: this.container.clientHeight,
                });
            }
        });
        observer.observe(this.container);
    }

    setData(data) {
        if (!data || data.length === 0) return;

        const candles = data.map(d => ({
            time: d.date,
            open: d.open,
            high: d.high,
            low: d.low,
            close: d.close,
        }));

        const volumes = data.map(d => ({
            time: d.date,
            value: d.volume,
            color: d.close >= d.open ? 'rgba(239, 68, 68, 0.4)' : 'rgba(34, 197, 94, 0.4)',
        }));

        this.candleSeries.setData(candles);
        this.volumeSeries.setData(volumes);
        this.chart.timeScale().fitContent();
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

    destroy() {
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
        result.push({ time: data[i].date, value: sum / period });
    }
    return result;
}
