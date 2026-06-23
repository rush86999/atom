from core.base_routes import BaseAPIRouter
from core.auth import get_current_user, User

router = BaseAPIRouter(prefix="/api/reports", tags=["Reports"])

@router.get("/")
async def reports_root():
    return router.success_response(
        data={"message": "Reports API"},
        message="Reports API root endpoint"
    )
