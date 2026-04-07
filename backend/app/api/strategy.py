from fastapi import APIRouter

router = APIRouter()

# Placeholder - will be expanded in Phase 5
@router.get("/list")
def list_strategies():
    from app.api.backtest import list_strategies
    return list_strategies()
