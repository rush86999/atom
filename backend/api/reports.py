from core.base_routes import BaseAPIRouter

router = BaseAPIRouter()

@router.get("/")
async def reports_root():
    return router.success_response(
        data={"message": "Reports API"},
        message="Reports API root endpoint"
    )
