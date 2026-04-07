from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.core.config import DAILY_UPDATE_HOUR, DAILY_UPDATE_MINUTE

scheduler = BackgroundScheduler()


def daily_data_update():
    from app.data.downloader import DataDownloader
    downloader = DataDownloader()
    try:
        downloader.incremental_update()
    finally:
        downloader.provider.logout()


def init_scheduler():
    scheduler.add_job(
        daily_data_update,
        CronTrigger(hour=DAILY_UPDATE_HOUR, minute=DAILY_UPDATE_MINUTE),
        id="daily_data_update",
        name="每日数据增量更新",
        replace_existing=True,
    )
    scheduler.start()


def get_scheduler_status():
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": str(job.next_run_time) if job.next_run_time else None,
        })
    return {"running": scheduler.running, "jobs": jobs}
