from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def reports_root():
    return {"message": "Reports API"}
