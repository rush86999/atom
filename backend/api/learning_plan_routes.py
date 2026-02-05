"""
Learning Plan Routes

Provides AI-generated personalized learning plans with progress tracking.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.llm.byok_handler import BYOKHandler
from core.models import User

router = BaseAPIRouter(prefix="/api/v1/learning", tags=["learning-plans"])
logger = logging.getLogger(__name__)

# Initialize BYOK handler for LLM integration
byok_handler = BYOKHandler()


# Request/Response Models
class LearningPlanRequest(BaseModel):
    """Learning plan generation request"""
    topic: str = Field(..., min_length=1, description="Topic to learn about")
    current_skill_level: str = Field("beginner", description="beginner, intermediate, advanced")
    learning_goals: List[str] = Field(default=[], description="Specific learning objectives")
    time_commitment: str = Field("medium", description="low, medium, high (hours per week)")
    duration_weeks: int = Field(4, ge=1, le=52, description="Plan duration in weeks")
    preferred_format: List[str] = Field(
        default=["articles", "videos", "exercises"],
        description="Preferred learning formats"
    )
    notion_database_id: Optional[str] = Field(None, description="Notion database ID for export")

    model_config = ConfigDict(extra="allow")


class LearningModule(BaseModel):
    """Individual learning module"""
    week: int
    title: str
    objectives: List[str]
    resources: List[dict]
    exercises: List[str]
    estimated_hours: float


class LearningPlanModules(BaseModel):
    """Container for learning modules"""
    modules: List[LearningModule]


class LearningPlanResponse(BaseModel):
    """Learning plan response"""
    plan_id: str
    topic: str
    current_skill_level: str
    target_skill_level: str
    duration_weeks: int
    modules: List[LearningModule]
    milestones: List[str]
    assessment_criteria: List[str]
    created_at: datetime


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Get current user from session or JWT."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            from core.enterprise_auth_service import EnterpriseAuthService
            auth_service = EnterpriseAuthService()
            token = auth_header.split(" ")[1]
            claims = auth_service.verify_token(token)
            if claims:
                user_id = claims.get('user_id')
                user = db.query(User).filter(User.id == user_id).first()
                if user:
                    return user
        except Exception as e:
            logger.debug(f"JWT auth failed: {e}")

    user_id = request.headers.get("X-User-ID")
    if user_id:
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            return user

    user_email = request.headers.get("X-User-Email")
    if user_email:
        user = db.query(User).filter(User.email == user_email).first()
        if user:
            return user

    if os.getenv("ENVIRONMENT", "development") == "development":
        temp_id = request.headers.get("X-User-ID") or "dev_user"
        user = db.query(User).filter(User.id == temp_id).first()
        if not user:
            user = User(
                id=temp_id,
                email=f"dev_{temp_id}@example.com",
                first_name="Dev",
                last_name="User"
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        return user

    raise HTTPException(
        status_code=401,
        detail="Unauthorized: Valid authentication required"
    )


async def generate_learning_modules(
    topic: str,
    current_level: str,
    duration_weeks: int,
    preferred_formats: List[str],
    learning_goals: List[str] = []
) -> List[LearningModule]:
    """
    Generate learning modules using AI.

    Uses BYOK handler for personalized, AI-generated curriculum.
    Falls back to template-based modules if LLM fails.
    """
    # Calculate skill progression
    levels = ["beginner", "intermediate", "advanced", "expert"]
    start_idx = levels.index(current_level) if current_level in levels else 0
    target_level = levels[min(start_idx + 1, len(levels) - 1)]

    # Prepare comprehensive prompt
    goals_str = ', '.join(learning_goals) if learning_goals else "general proficiency"
    formats_str = ', '.join(preferred_formats)

    prompt = f"""
    Create a personalized learning plan for mastering: {topic}

    Current Level: {current_level}
    Target Level: {target_level}
    Duration: {duration_weeks} weeks
    Learning Goals: {goals_str}
    Preferred Formats: {formats_str}

    Generate {duration_weeks} weekly learning modules. Each module should include:
    1. Clear title indicating the week's focus
    2. Specific learning objectives (3-5 objectives)
    3. Curated resources matching preferred formats (articles, videos, exercises)
    4. Practical hands-on exercises
    5. Realistic time estimates (hours)

    Structure the plan to progress from {current_level} to {target_level}:
    - Early weeks: Foundation and core concepts
    - Middle weeks: Practical application and projects
    - Final weeks: Advanced techniques and mastery

    Make content specific to {topic}, not generic templates.
    """

    system_instruction = f"""You are an expert curriculum designer and educational consultant.
    You create personalized, structured learning paths that adapt to the learner's current level.
    Your plans are practical, progressive, and focused on real-world application.
    You break down complex topics into manageable weekly modules."""

    try:
        # Use structured output with BYOK handler
        result = await byok_handler.generate_structured_response(
            prompt=prompt,
            system_instruction=system_instruction,
            response_model=LearningPlanModules,
            temperature=0.4,  # Moderate temp for creativity
            task_type="analysis",  # Content generation
            agent_id=None
        )

        if result and result.modules:
            logger.info(f"Generated {len(result.modules)} AI learning modules for: {topic}")
            return result.modules
        else:
            logger.warning(f"LLM returned None for learning plan, using fallback")

    except Exception as e:
        logger.error(f"LLM learning plan generation failed for {topic}: {e}")

    # Fallback to template-based generation
    logger.info(f"Using fallback learning modules for: {topic}")
    return _generate_template_modules(
        topic=topic,
        current_level=current_level,
        target_level=target_level,
        duration_weeks=duration_weeks,
        preferred_formats=preferred_formats
    )


def _generate_template_modules(
    topic: str,
    current_level: str,
    target_level: str,
    duration_weeks: int,
    preferred_formats: List[str]
) -> List[LearningModule]:
    """Generate template-based learning modules when LLM is unavailable."""
    modules = []

    for week in range(1, duration_weeks + 1):
        # Determine focus area
        if week <= duration_weeks / 3:
            focus = "Foundation"
            objectives = [
                f"Understand core {topic} concepts",
                f"Learn {topic} terminology and basics",
                f"Practice fundamental {topic} skills"
            ]
        elif week <= 2 * duration_weeks / 3:
            focus = "Application"
            objectives = [
                f"Apply {topic} concepts to real problems",
                f"Build practical {topic} projects",
                f"Develop intermediate {topic} techniques"
            ]
        else:
            focus = "Mastery"
            objectives = [
                f"Master advanced {topic} techniques",
                f"Optimize {topic} workflows",
                f"Contribute to {topic} community"
            ]

        # Generate resources
        resources = []
        if "articles" in preferred_formats:
            resources.append({
                "type": "article",
                "title": f"{topic} {focus} Guide - Week {week}",
                "url": f"https://example.com/{topic.lower()}/week{week}",
                "estimated_minutes": 30
            })

        if "videos" in preferred_formats:
            resources.append({
                "type": "video",
                "title": f"{topic} {focus} Tutorial",
                "url": f"https://example.com/videos/{topic.lower()}/week{week}",
                "estimated_minutes": 45
            })

        if "exercises" in preferred_formats:
            resources.append({
                "type": "exercise",
                "title": f"{topic} Practice Problems",
                "url": f"https://example.com/exercises/{topic.lower()}/week{week}",
                "estimated_minutes": 60
            })

        exercises = [
            f"Complete {focus.lower()} tutorial for {topic}",
            f"Build a small {topic} project focusing on {focus.lower()}",
            f"Write a summary of key {focus.lower()} concepts"
        ]

        module = LearningModule(
            week=week,
            title=f"{topic} {focus} - Week {week}",
            objectives=objectives,
            resources=resources,
            exercises=exercises,
            estimated_hours=5.0
        )

        modules.append(module)

    return modules


def generate_milestones(topic: str, duration_weeks: int) -> List[str]:
    """Generate key learning milestones."""
    milestones = []

    if duration_weeks >= 4:
        milestones.append(f"Week 4: Complete {topic} foundation course")
    if duration_weeks >= 8:
        milestones.append(f"Week 8: Build first {topic} portfolio project")
    if duration_weeks >= 12:
        milestones.append(f"Week 12: Pass {topic} intermediate assessment")
    if duration_weeks >= 16:
        milestones.append(f"Week 16: Contribute to {topic} open-source project")

    return milestones


def generate_assessment_criteria(topic: str) -> List[str]:
    """Generate criteria for assessing learning progress."""
    return [
        f"Complete all {topic} learning modules",
        f"Pass {topic} knowledge quiz with >80% score",
        f"Submit {topic} practical project for review",
        f"Demonstrate {topic} skills in code review or presentation"
    ]


@router.post("/plans", response_model=LearningPlanResponse)
async def create_learning_plan(
    request: Request,
    payload: LearningPlanRequest,
    db: Session = Depends(get_db)
):
    """
    Generate a personalized learning plan using AI.

    Creates a structured learning path with modules, resources, exercises,
    milestones, and assessment criteria.

    Uses BYOK handler for AI-powered curriculum generation with automatic fallback.

    TODO: Store plans in database for tracking progress
    TODO: Export to Notion when notion_database_id is provided
    TODO: Implement adaptive learning based on user feedback
    """
    try:
        # Get current user
        current_user = get_current_user(request, db)

        # Validate inputs
        if not payload.topic or len(payload.topic.strip()) == 0:
            raise HTTPException(
                status_code=400,
                detail="Topic is required"
            )

        valid_levels = ["beginner", "intermediate", "advanced"]
        if payload.current_skill_level not in valid_levels:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid skill level. Must be one of: {', '.join(valid_levels)}"
            )

        valid_commitments = ["low", "medium", "high"]
        if payload.time_commitment not in valid_commitments:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid time commitment. Must be one of: {', '.join(valid_commitments)}"
            )

        # Generate plan ID
        plan_id = str(uuid.uuid4())

        logger.info(
            f"Creating learning plan: user={current_user.id}, "
            f"plan_id={plan_id}, "
            f"topic={payload.topic}, "
            f"duration={payload.duration_weeks} weeks"
        )

        # Generate learning modules
        modules = await generate_learning_modules(
            topic=payload.topic,
            current_level=payload.current_skill_level,
            duration_weeks=payload.duration_weeks,
            preferred_formats=payload.preferred_format,
            learning_goals=payload.learning_goals
        )

        # Generate milestones
        milestones = generate_milestones(payload.topic, payload.duration_weeks)

        # Generate assessment criteria
        assessment_criteria = generate_assessment_criteria(payload.topic)

        # Determine target skill level
        levels = ["beginner", "intermediate", "advanced", "expert"]
        start_idx = levels.index(payload.current_skill_level)
        target_level = levels[min(start_idx + 1, len(levels) - 1)]

        logger.info(
            f"Learning plan created: plan_id={plan_id}, "
            f"modules={len(modules)}, "
            f"milestones={len(milestones)}"
        )

        # TODO: Export to Notion if notion_database_id provided
        if payload.notion_database_id:
            logger.info(f"Notion export requested: database_id={payload.notion_database_id}")

        return LearningPlanResponse(
            plan_id=plan_id,
            topic=payload.topic,
            current_skill_level=payload.current_skill_level,
            target_skill_level=target_level,
            duration_weeks=payload.duration_weeks,
            modules=modules,
            milestones=milestones,
            assessment_criteria=assessment_criteria,
            created_at=datetime.utcnow()
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Learning plan creation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create learning plan: {str(e)}"
        )


@router.get("/plans/{plan_id}")
async def get_learning_plan(
    plan_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Retrieve a previously generated learning plan.

    TODO: Implement storage and retrieval of plans
    """
    # TODO: Retrieve from database
    raise HTTPException(
        status_code=501,
        detail="Plan retrieval not yet implemented - plans are returned immediately"
    )


@router.get("/topics/suggested")
async def suggest_learning_topics():
    """
    Suggest popular learning topics.

    Returns a curated list of topics for which learning plans
    can be generated.
    """
    topics = {
        "programming": [
            "Python", "JavaScript", "TypeScript", "Go", "Rust",
            "Web Development", "Mobile Development", "DevOps"
        ],
        "data": [
            "Machine Learning", "Data Science", "Data Engineering",
            "SQL", "Data Visualization"
        ],
        "design": [
            "UI/UX Design", "Graphic Design", "Product Design",
            "Figma", "Design Systems"
        ],
        "business": [
            "Project Management", "Marketing", "Sales",
            "Entrepreneurship", "Business Strategy"
        ]
    }

    return {
        "categories": topics,
        "total_topics": sum(len(v) for v in topics.values())
    }
