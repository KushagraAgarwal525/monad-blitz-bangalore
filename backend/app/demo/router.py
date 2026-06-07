from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.demo.flow import STEP_RUNNERS, get_demo_state

router = APIRouter(prefix="/demo", tags=["demo"])


def _ensure_enabled() -> None:
    if not settings.enable_demo_flow:
        raise HTTPException(status_code=404, detail="Demo flow is disabled")


@router.get("/flow/state")
async def demo_flow_state():
    _ensure_enabled()
    state = get_demo_state()
    return {
        "parent_id": str(state.parent_id) if state.parent_id else None,
        "child_id": str(state.child_id) if state.child_id else None,
        "last_step": state.last_step,
        "total_steps": len(STEP_RUNNERS),
    }


@router.post("/flow/step/{step}")
async def demo_flow_step(step: int, db: AsyncSession = Depends(get_db)):
    _ensure_enabled()
    runner = STEP_RUNNERS.get(step)
    if not runner:
        raise HTTPException(status_code=400, detail=f"Invalid step {step}. Use 1–7.")
    try:
        result = await runner(db)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
