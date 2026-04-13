import shutil
from pathlib import Path
from types import SimpleNamespace

from app.core.config import MARKET_DB_PATH
from app.core.factor_runner import run_factor_job
from app.data.downloader import DataDownloader
from app.data.storage import MarketStorage


def factor_backtest_job(context):
    context.log('loading market storage')
    context.set_progress(10, 'factor_backtest_loading_data')
    context.raise_if_cancelled()
    storage = MarketStorage()
    request = SimpleNamespace(**context.payload)
    result = run_factor_job(
        storage,
        request,
        progress_callback=context.set_progress,
        log_callback=context.log,
        assert_not_cancelled=context.raise_if_cancelled,
    )
    context.raise_if_cancelled()
    summary = {
        'final_equity': result.get('metrics', {}).get('final_equity'),
        'total_return': result.get('metrics', {}).get('total_return'),
        'rebalance_count': result.get('metrics', {}).get('rebalance_count'),
        'pool_size': result.get('pool_size'),
    }
    context.set_summary(summary)
    context.write_json_artifact('summary.json', summary)
    context.write_json_artifact('result.json', result)
    context.write_json_artifact('equity_curve.json', result.get('equity_curve', []))
    context.write_json_artifact('rebalances.json', result.get('rebalances', []))
    context.log('factor backtest completed')
    context.write_text_artifact('logs.txt', '\n'.join(context.logs))
    context.set_progress(100, 'factor_backtest_complete')
    return result


def data_import_db_job(context):
    source_path = Path(context.payload['source_path'])
    replace_existing = bool(context.payload.get('replace_existing', True))
    if not source_path.exists():
        raise FileNotFoundError(f'数据库文件不存在: {source_path}')

    context.set_progress(10, 'import_db_preparing')
    context.raise_if_cancelled()
    MARKET_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if MARKET_DB_PATH.exists() and not replace_existing:
        raise FileExistsError(f'目标数据库已存在: {MARKET_DB_PATH}')

    shutil.copy2(source_path, MARKET_DB_PATH)
    storage = MarketStorage()
    codes = storage.get_all_stock_codes()
    if codes:
        storage.sync_parquet_tables(codes, periods=['d', 'w', 'm'])
    report = {
        'source_path': str(source_path),
        'target_path': str(MARKET_DB_PATH),
        'size_bytes': source_path.stat().st_size,
        'parquet_sync_codes': len(codes),
    }
    context.log(f'imported database from {source_path}')
    context.set_summary(report)
    context.write_json_artifact('import_report.json', report)
    context.write_text_artifact('logs.txt', '\n'.join(context.logs))
    context.set_progress(100, 'import_db_complete')
    return report


def data_update_job(context):
    mode = context.payload.get('mode', 'incremental')
    downloader = DataDownloader()
    stock_count = 0
    calendar_count = 0
    codes = []
    context.set_progress(5, 'data_update_started')
    context.log(f'data update mode={mode}')
    try:
        context.raise_if_cancelled()
        context.log('downloading stock list')
        stock_count = downloader.download_stock_list()
        context.set_progress(25, 'data_update_stock_list_complete')

        context.raise_if_cancelled()
        context.log('downloading trade calendar')
        calendar_count = downloader.download_trade_calendar()
        context.set_progress(45, 'data_update_calendar_complete')

        context.raise_if_cancelled()
        context.log('downloading daily data')
        codes = downloader.storage.get_all_stock_codes()
        if mode == 'full':
            downloader.download_daily_data(codes=codes)
        else:
            downloader.download_daily_data(codes=codes)
        context.set_progress(90, 'data_update_daily_complete')
    finally:
        downloader.provider.logout()
    report = {
        'mode': mode,
        'status': 'completed',
        'stock_count': stock_count,
        'calendar_count': calendar_count,
        'code_count': len(codes),
    }
    context.set_summary(report)
    context.write_json_artifact('update_report.json', report)
    context.write_text_artifact('logs.txt', '\n'.join(context.logs))
    context.set_progress(100, 'data_update_complete')
    return report


def register_job_handlers(manager):
    manager.register('factor_backtest', factor_backtest_job)
    manager.register('data_import_db', data_import_db_job)
    manager.register('data_update', data_update_job)
