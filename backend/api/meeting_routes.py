"""
Meeting Attendance API Routes
Handles meeting attendance tracking and status
"""
from datetime import datetime
from typing import List, Optional
from core.base_routes import BaseAPIRouter
from fastapi import Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.models import MeetingAttendanceStatus, User

router = BaseAPIRouter(prefix="/api/meetings", tags=["Meetings"])


# Request/Response Models
class MeetingAttendanceResponse(BaseModel):
    """Meeting attendance status for a task"""
    task_id: str
    user_id: str
    platform: Optional[str]
    meeting_identifier: Optional[str]
    status_timestamp: datetime
    current_status_message: Optional[str]
    final_notion_page_url: Optional[str]
    error_details: Optional[str]

    class Config:
        from_attributes = True


class CreateMeetingAttendanceRequest(BaseModel):
    """Request to create meeting attendance record"""
    task_id: str = Field(..., description="Unique task identifier")
    platform: Optional[str] = Field(None, description="Meeting platform (zoom, teams, etc.)")
    meeting_identifier: Optional[str] = Field(None, description="Meeting ID or URL")
    current_status_message: Optional[str] = Field(None, description="Current status description")


class UpdateMeetingAttendanceRequest(BaseModel):
    """Request to update meeting attendance record"""
    platform: Optional[str] = Field(None, description="Meeting platform")
    meeting_identifier: Optional[str] = Field(None, description="Meeting ID or URL")
    current_status_message: Optional[str] = Field(None, description="Current status description")
    final_notion_page_url: Optional[str] = Field(None, description="Generated Notion page URL")
    error_details: Optional[str] = Field(None, description="Error details if failed")


class DeleteMeetingAttendanceResponse(BaseModel):
    """Response after deleting attendance record"""
    message: str


# Endpoints
@router.get("/attendance/{task_id}", response_model=MeetingAttendanceResponse)
async def get_meeting_attendance(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get meeting attendance status for a task

    Returns attendance tracking information for automated meeting monitoring.
    Includes platform details, status messages, and generated Notion pages.
    """
    attendance = db.query(MeetingAttendanceStatus).filter(
        MeetingAttendanceStatus.task_id == task_id,
        MeetingAttendanceStatus.user_id == current_user.id
    ).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting attendance not found"
        )

    return MeetingAttendanceResponse(
        task_id=attendance.task_id,
        user_id=attendance.user_id,
        platform=attendance.platform,
        meeting_identifier=attendance.meeting_identifier,
        status_timestamp=attendance.status_timestamp,
        current_status_message=attendance.current_status_message,
        final_notion_page_url=attendance.final_notion_page_url,
        error_details=attendance.error_details
    )


@router.get("/attendance", response_model=List[MeetingAttendanceResponse])
async def list_meeting_attendance(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all meeting attendance records for current user

    Returns all attendance tracking records ordered by most recent status.
    """
    attendances = db.query(MeetingAttendanceStatus).filter(
        MeetingAttendanceStatus.user_id == current_user.id
    ).order_by(MeetingAttendanceStatus.status_timestamp.desc()).all()

    return [
        MeetingAttendanceResponse(
            task_id=att.task_id,
            user_id=att.user_id,
            platform=att.platform,
            meeting_identifier=att.meeting_identifier,
            status_timestamp=att.status_timestamp,
            current_status_message=att.current_status_message,
            final_notion_page_url=att.final_notion_page_url,
            error_details=att.error_details
        )
        for att in attendances
    ]


@router.post("/attendance", response_model=MeetingAttendanceResponse, status_code=status.HTTP_201_CREATED)
async def create_meeting_attendance(
    request: CreateMeetingAttendanceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create a new meeting attendance record

    Creates a new attendance tracking record for automated meeting monitoring.
    """
    # Check if attendance record already exists for this task
    existing = db.query(MeetingAttendanceStatus).filter(
        MeetingAttendanceStatus.task_id == request.task_id,
        MeetingAttendanceStatus.user_id == current_user.id
    ).first()

    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Attendance record for this task already exists"
        )

    attendance = MeetingAttendanceStatus(
        task_id=request.task_id,
        user_id=current_user.id,
        platform=request.platform,
        meeting_identifier=request.meeting_identifier,
        status_timestamp=datetime.utcnow(),
        current_status_message=request.current_status_message
    )

    db.add(attendance)
    db.commit()
    db.refresh(attendance)

    return MeetingAttendanceResponse(
        task_id=attendance.task_id,
        user_id=attendance.user_id,
        platform=attendance.platform,
        meeting_identifier=attendance.meeting_identifier,
        status_timestamp=attendance.status_timestamp,
        current_status_message=attendance.current_status_message,
        final_notion_page_url=attendance.final_notion_page_url,
        error_details=attendance.error_details
    )


@router.patch("/attendance/{task_id}", response_model=MeetingAttendanceResponse)
async def update_meeting_attendance(
    task_id: str,
    request: UpdateMeetingAttendanceRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update meeting attendance record

    Updates attendance tracking information. Only provided fields are updated.
    Requires ownership of the record.
    """
    attendance = db.query(MeetingAttendanceStatus).filter(
        MeetingAttendanceStatus.task_id == task_id,
        MeetingAttendanceStatus.user_id == current_user.id
    ).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting attendance not found"
        )

    # Update only provided fields
    if request.platform is not None:
        attendance.platform = request.platform
    if request.meeting_identifier is not None:
        attendance.meeting_identifier = request.meeting_identifier
    if request.current_status_message is not None:
        attendance.current_status_message = request.current_status_message
    if request.final_notion_page_url is not None:
        attendance.final_notion_page_url = request.final_notion_page_url
    if request.error_details is not None:
        attendance.error_details = request.error_details

    attendance.status_timestamp = datetime.utcnow()

    db.commit()
    db.refresh(attendance)

    return MeetingAttendanceResponse(
        task_id=attendance.task_id,
        user_id=attendance.user_id,
        platform=attendance.platform,
        meeting_identifier=attendance.meeting_identifier,
        status_timestamp=attendance.status_timestamp,
        current_status_message=attendance.current_status_message,
        final_notion_page_url=attendance.final_notion_page_url,
        error_details=attendance.error_details
    )


@router.delete("/attendance/{task_id}", response_model=DeleteMeetingAttendanceResponse)
async def delete_meeting_attendance(
    task_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete meeting attendance record

    Permanently deletes an attendance tracking record.
    Requires ownership of the record.
    """
    attendance = db.query(MeetingAttendanceStatus).filter(
        MeetingAttendanceStatus.task_id == task_id,
        MeetingAttendanceStatus.user_id == current_user.id
    ).first()

    if not attendance:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting attendance not found"
        )

    db.delete(attendance)
    db.commit()

    return DeleteMeetingAttendanceResponse(message="Meeting attendance deleted successfully")
