import time
import psutil
import os
from fastapi import APIRouter

router = APIRouter()

_start_time = time.time()


@router.get("/status")
def get_status():
    uptime_secs = int(time.time() - _start_time)
    hours, remainder = divmod(uptime_secs, 3600)
    mins, secs = divmod(remainder, 60)

    process = psutil.Process(os.getpid())
    mem_mb = process.memory_info().rss / 1024 / 1024
    cpu_pct = process.cpu_percent(interval=0.1)

    from app.core.scheduler import get_scheduler_status
    sched = get_scheduler_status()

    return {
        "data": {
            "uptime": f"{hours}h {mins}m {secs}s",
            "memory": f"{mem_mb:.1f} MB",
            "cpu": f"{cpu_pct:.1f}%",
            "scheduler": sched,
        }
    }
