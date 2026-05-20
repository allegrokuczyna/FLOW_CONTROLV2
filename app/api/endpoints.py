from fastapi import APIRouter

from app.api.routers import auth, sync, works, plan, analystics, ai
from app.services.gate_sync import poll_gates_and_update


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