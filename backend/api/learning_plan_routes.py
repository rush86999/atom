"""
Learning Plan Routes

Provides AI-generated personalized learning plans with progress tracking.
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.llm.byok_handler import BYOKHandler
from core.models import User, LearningPlan, OAuthToken
from core.security_dependencies import get_current_user
from integrations.notion_service import NotionService

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


async def export_learning_plan_to_notion(
    plan: LearningPlan,
    modules: List[LearningModule],
    notion_token: str
) -> Optional[str]:
    """
    Export learning plan to Notion database.

    Creates a page in the Notion database with the learning plan details
    and adds each module as a checkbox block.

    Args:
        plan: LearningPlan database model
        modules: List of LearningModule objects
        notion_token: Notion API access token

    Returns:
        Notion page ID if successful, None otherwise
    """
    try:
        notion = NotionService(access_token=notion_token)

        # Create parent reference to database
        parent = {"type": "database_id", "database_id": plan.notion_database_id}

        # Create properties for the page
        properties = {
            "Topic": {
                "title": [
                    {
                        "text": {
                            "content": plan.topic
                        }
                    }
                ]
            },
            "Current Level": {
                "select": {
                    "name": plan.current_skill_level.capitalize()
                }
            },
            "Target Level": {
                "select": {
                    "name": plan.target_skill_level.capitalize()
                }
            },
            "Duration (weeks)": {
                "number": plan.duration_weeks
            },
            "Created": {
                "date": {
                    "start": plan.created_at.isoformat()
                }
            }
        }

        # Create children blocks for modules
        children = []

        # Add milestones section
        if plan.milestones:
            children.append({
                "object": "block",
                "type": "heading_2",
                "heading_2": {
                    "rich_text": [{"type": "text", "text": {"content": "🎯 Milestones"}}]
                }
            })
            for milestone in plan.milestones:
                children.append({
                    "object": "block",
                    "type": "bulleted_list_item",
                    "bulleted_list_item": {
                        "rich_text": [{"type": "text", "text": {"content": milestone}}]
                    }
                })

        # Add modules section
        children.append({
            "object": "block",
            "type": "heading_2",
            "heading_2": {
                "rich_text": [{"type": "text", "text": {"content": "📚 Learning Modules"}}]
            }
        })

        for module in modules:
            # Module title as checkbox
            children.append({
                "object": "block",
                "type": "to_do",
                "to_do": {
                    "rich_text": [{"type": "text", "text": {"content": f"Week {module.week}: {module.title}"}}],
                    "checked": False
                }
            })

            # Module objectives
            if module.objectives:
                children.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": "Objectives"}}]
                    }
                })
                for objective in module.objectives:
                    children.append({
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [{"type": "text", "text": {"content": objective}}]
                        }
                    })

            # Module exercises
            if module.exercises:
                children.append({
                    "object": "block",
                    "type": "heading_3",
                    "heading_3": {
                        "rich_text": [{"type": "text", "text": {"content": "Exercises"}}]
                    }
                })
                for exercise in module.exercises:
                    children.append({
                        "object": "block",
                        "type": "numbered_list_item",
                        "numbered_list_item": {
                            "rich_text": [{"type": "text", "text": {"content": exercise}}]
                        }
                    })

        # Create the page
        result = notion.create_page(parent, properties, children)

        if result and "id" in result:
            logger.info(f"Learning plan exported to Notion: page_id={result['id']}")
            return result["id"]
        else:
            logger.warning("Notion page creation returned no ID")
            return None

    except Exception as e:
        logger.error(f"Failed to export learning plan to Notion: {e}")
        return None


@router.post("/plans", response_model=LearningPlanResponse)
async def create_learning_plan(
    request: Request,
    payload: LearningPlanRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate a personalized learning plan using AI.

    Creates a structured learning path with modules, resources, exercises,
    milestones, and assessment criteria.

    Uses BYOK handler for AI-powered curriculum generation with automatic fallback.

    Plans are stored in the database for retrieval and progress tracking.
    """
    try:

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
        plan_id = str(uuid4())

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

        # Convert modules to dict for JSON storage
        modules_dict = [m.model_dump() for m in modules]

        # Save to database
        learning_plan = LearningPlan(
            id=plan_id,
            user_id=current_user.id,
            topic=payload.topic,
            current_skill_level=payload.current_skill_level,
            target_skill_level=target_level,
            duration_weeks=payload.duration_weeks,
            modules=modules_dict,
            milestones=milestones,
            assessment_criteria=assessment_criteria,
            progress={
                "completed_modules": [],
                "feedback_scores": {},
                "time_spent": {},
                "adjustments_made": []
            },
            notion_database_id=payload.notion_database_id,
            notion_page_id=None
        )

        db.add(learning_plan)
        db.commit()

        logger.info(
            f"Learning plan created and saved: plan_id={plan_id}, "
            f"modules={len(modules)}, "
            f"milestones={len(milestones)}"
        )

        # Export to Notion if notion_database_id provided
        if payload.notion_database_id:
            logger.info(f"Notion export requested: database_id={payload.notion_database_id}")

            # Get Notion OAuth token for the user
            notion_token_record = db.query(OAuthToken).filter(
                OAuthToken.user_id == current_user.id,
                OAuthToken.provider == "notion",
                OAuthToken.status == "active"
            ).first()

            if notion_token_record and notion_token_record.access_token:
                notion_page_id = await export_learning_plan_to_notion(
                    plan=learning_plan,
                    modules=modules,
                    notion_token=notion_token_record.access_token
                )

                if notion_page_id:
                    # Update the plan with the Notion page ID
                    learning_plan.notion_page_id = notion_page_id
                    db.commit()
                    logger.info(f"Learning plan exported to Notion: page_id={notion_page_id}")
                else:
                    logger.warning("Notion export failed, but plan was saved successfully")
            else:
                logger.warning(f"No active Notion token found for user {current_user.id}, skipping export")

        return LearningPlanResponse(
            plan_id=plan_id,
            topic=payload.topic,
            current_skill_level=payload.current_skill_level,
            target_skill_level=target_level,
            duration_weeks=payload.duration_weeks,
            modules=modules,
            milestones=milestones,
            assessment_criteria=assessment_criteria,
            created_at=learning_plan.created_at
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
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve a previously generated learning plan.
    """
    # Query database for learning plan
    learning_plan = db.query(LearningPlan).filter(
        LearningPlan.id == plan_id
    ).first()

    if not learning_plan:
        raise HTTPException(
            status_code=404,
            detail=f"Learning plan with ID '{plan_id}' not found"
        )

    # Verify ownership
    if learning_plan.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to access this learning plan"
        )

    # Convert modules dict back to LearningModule objects
    modules = [
        LearningModule(**m) if isinstance(m, dict) else m
        for m in learning_plan.modules
    ]

    return LearningPlanResponse(
        plan_id=learning_plan.id,
        topic=learning_plan.topic,
        current_skill_level=learning_plan.current_skill_level,
        target_skill_level=learning_plan.target_skill_level,
        duration_weeks=learning_plan.duration_weeks,
        modules=modules,
        milestones=learning_plan.milestones,
        assessment_criteria=learning_plan.assessment_criteria,
        created_at=learning_plan.created_at
    )


@router.get("/plans")
async def list_learning_plans(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    limit: int = 20,
    offset: int = 0
):
    """
    List all learning plans for the current user.
    """
    # Query learning plans for current user
    plans = db.query(LearningPlan).filter(
        LearningPlan.user_id == current_user.id
    ).order_by(
        LearningPlan.created_at.desc()
    ).offset(offset).limit(limit).all()

    total = db.query(LearningPlan).filter(
        LearningPlan.user_id == current_user.id
    ).count()

    return {
        "plans": [
            {
                "plan_id": plan.id,
                "topic": plan.topic,
                "current_skill_level": plan.current_skill_level,
                "target_skill_level": plan.target_skill_level,
                "duration_weeks": plan.duration_weeks,
                "created_at": plan.created_at,
                "updated_at": plan.updated_at,
                "progress": plan.progress
            }
            for plan in plans
        ],
        "total": total,
        "limit": limit,
        "offset": offset
    }


class UpdateProgressRequest(BaseModel):
    """Update learning plan progress"""
    module_week: int = Field(..., ge=1, description="Week number of completed module")
    feedback_score: int = Field(..., ge=1, le=5, description="User feedback score (1-5)")
    time_spent_hours: float = Field(..., ge=0, description="Time spent on module in hours")


@router.post("/plans/{plan_id}/progress")
async def update_plan_progress(
    plan_id: str,
    request: UpdateProgressRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update progress for a learning plan and trigger adaptive adjustments.

    Records completion of modules, feedback scores, and time spent.
    Implements adaptive learning based on user feedback.
    """
    # Query learning plan
    learning_plan = db.query(LearningPlan).filter(
        LearningPlan.id == plan_id
    ).first()

    if not learning_plan:
        raise HTTPException(
            status_code=404,
            detail=f"Learning plan with ID '{plan_id}' not found"
        )

    # Verify ownership
    if learning_plan.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to modify this learning plan"
        )

    # Initialize progress if needed
    if not learning_plan.progress:
        learning_plan.progress = {
            "completed_modules": [],
            "feedback_scores": {},
            "time_spent": {},
            "adjustments_made": []
        }

    # Record progress
    week_str = str(request.module_week)

    if week_str not in learning_plan.progress["completed_modules"]:
        learning_plan.progress["completed_modules"].append(week_str)

    learning_plan.progress["feedback_scores"][week_str] = request.feedback_score
    learning_plan.progress["time_spent"][week_str] = request.time_spent_hours

    # Adaptive learning adjustments
    adjustments = []
    if request.feedback_score < 3:  # Poor feedback
        # Suggest additional resources
        adjustment = {
            "type": "remediation",
            "week": request.module_week,
            "reason": f"Low feedback score ({request.feedback_score})",
            "action": "Added review modules and extended time for similar topics"
        }
        adjustments.append(adjustment)
        learning_plan.progress["adjustments_made"].append(adjustment)
        logger.info(f"Adaptive adjustment triggered for plan {plan_id}: remediation")

    elif request.feedback_score > 4 and request.time_spent_hours < 2:  # Excellent feedback, quick completion
        # Accelerate learning
        adjustment = {
            "type": "acceleration",
            "week": request.module_week,
            "reason": f"High feedback score ({request.feedback_score}) with quick completion",
            "action": "Consider advancing to more advanced topics"
        }
        adjustments.append(adjustment)
        learning_plan.progress["adjustments_made"].append(adjustment)
        logger.info(f"Adaptive adjustment triggered for plan {plan_id}: acceleration")

    db.commit()

    return {
        "success": True,
        "message": "Progress updated successfully",
        "progress": learning_plan.progress,
        "adjustments": adjustments
    }


@router.delete("/plans/{plan_id}")
async def delete_learning_plan(
    plan_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete a learning plan.
    """
    # Query learning plan
    learning_plan = db.query(LearningPlan).filter(
        LearningPlan.id == plan_id
    ).first()

    if not learning_plan:
        raise HTTPException(
            status_code=404,
            detail=f"Learning plan with ID '{plan_id}' not found"
        )

    # Verify ownership
    if learning_plan.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to delete this learning plan"
        )

    # Delete plan
    db.delete(learning_plan)
    db.commit()

    logger.info(f"Learning plan deleted: plan_id={plan_id}")

    return {
        "success": True,
        "message": "Learning plan deleted successfully"
    }


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
