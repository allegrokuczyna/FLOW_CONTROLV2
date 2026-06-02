from fastapi import APIRouter

from app.api.routers import auth, sync, works, plan, analystics, ai, test_d365
from app.services.gate_sync import poll_gates_and_update
from app.core.auth import get_d365_access_token

router = APIRouter()



# ╔════════════════════════════════════════════════════════════════════════╗
#  Wszystkie endpointy                                                     ║
# ╚════════════════════════════════════════════════════════════════════════╝

router.include_router(auth.router)
router.include_router(sync.router)
router.include_router(works.router)
router.include_router(plan.router)
router.include_router(analystics.router)
router.include_router(ai.router)
router.include_router(test_d365.router)