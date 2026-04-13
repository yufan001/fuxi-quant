import threading
from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import FRONTEND_DIR, HOST, PORT
from app.models.db import init_market_db, init_biz_db
from app.api.market import router as market_router
from app.api.backtest import router as backtest_router
from app.api.monitor import router as monitor_router
from app.api.strategy import router as strategy_router
from app.api.trading import router as trading_router
from app.api.auth import router as auth_router
from app.api.jobs import router as jobs_router


def create_app() -> FastAPI:
    app = FastAPI(title="量化交易系统", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    app.include_router(market_router, prefix="/api/market", tags=["market"])
    app.include_router(backtest_router, prefix="/api/backtest", tags=["backtest"])
    app.include_router(monitor_router, prefix="/api/monitor", tags=["monitor"])
    app.include_router(strategy_router, prefix="/api/strategy", tags=["strategy"])
    app.include_router(trading_router, prefix="/api/trading", tags=["trading"])
    app.include_router(jobs_router, prefix="/api/jobs", tags=["jobs"])

    @app.post("/api/market/update")
    def trigger_update(background_tasks: BackgroundTasks):
        def do_update():
            from app.data.downloader import DataDownloader
            d = DataDownloader()
            try:
                d.incremental_update()
            finally:
                d.provider.logout()
        background_tasks.add_task(do_update)
        return {"message": "更新任务已启动"}

    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")

    @app.on_event("startup")
    def startup():
        init_market_db()
        init_biz_db()
        from app.core.scheduler import init_scheduler
        from app.core.job_handlers import register_job_handlers
        from app.core.jobs import get_job_manager

        register_job_handlers(get_job_manager())
        init_scheduler()

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=HOST, port=PORT, reload=True)
