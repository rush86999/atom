from core.base_routes import BaseAPIRouter

router = BaseAPIRouter(prefix="/api/reports", tags=["Reports"])

@router.get("/")
async def reports_root():
    return router.success_response(
        data={"message": "Reports API"},
        message="Reports API root endpoint"
    )
