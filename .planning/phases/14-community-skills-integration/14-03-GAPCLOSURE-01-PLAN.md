---
phase: 14-community-skills-integration
plan: GAPCLOSURE-01
type: execute
wave: 3
depends_on:
  - "01"
  - "02"
  - "03"
gap_closure: true
files_modified:
  - backend/core/skill_registry_service.py
  - backend/core/episode_segmentation_service.py
  - backend/core/agent_graduation_service.py
  - backend/api/skill_routes.py
  - backend/tests/test_skill_episodic_integration.py
autonomous: true

must_haves:
  truths:
    - "Skill executions create EpisodeSegments with skill metadata and context"
    - "AgentGraduationService tracks skill usage in graduation readiness scores"
    - "Skills with successful executions increase agent learning metrics"
    - "Failed skill executions create episodes with error patterns for learning"
    - "Integration tests verify episodic memory captures skill context"
  artifacts:
    - path: "backend/core/skill_registry_service.py"
      provides: "Enhanced skill registry with episodic memory integration"
      min_lines: 250
      contains: "_create_execution_episode", "episode_integration", "skill_context"
    - path: "backend/core/episode_segmentation_service.py"
      provides: "Episode segmentation service with skill-aware segmentation"
      min_lines: 50
      contains: "create_skill_episode", "skill_metadata_extraction"
    - path: "backend/core/agent_graduation_service.py"
      provides: "Graduation service with skill usage tracking"
     _min_lines: 100
      contains: "skill_usage_metrics", "update_skill_metrics"
    - path: "backend/api/skill_routes.py"
      provides: "Enhanced skill routes with episodic context"
      min_lines: 250
      contains: "get_skill_episodes", "skill_learning_progress"
    - path: "backend/tests/test_skill_episodic_integration.py"
      provides: "Integration tests for episodic memory and graduation"
      min_lines: 200

tasks:
  - title: "Integrate skill executions with episodic memory"
    files:
      - path: "backend/core/skill_registry_service.py"
        action: |
        Add episode integration to SkillRegistryService:

        1. Import episode services:
           ```python
           from core.episode_segmentation_service import EpisodeSegmentationService
           from core.episode_retrieval_service import EpisodeRetrievalService
           ```

        2. Create episode after skill execution:
           ```python
           async def _create_execution_episode(
               self,
               skill_name: str,
               agent_id: str,
               inputs: dict,
               result: Any,
               error: Optional[Exception],
               execution_time: float
           ) -> str:
               """Create an episode segment for skill execution."""
               segment_type = "skill_success" if error is None else "skill_failure"

               # Extract skill metadata
               skill_context = {
                   "skill_name": skill_name,
                   "skill_source": "community",
                   "execution_time": execution_time,
                   "input_summary": self._summarize_inputs(inputs),
                   "result_summary": str(result)[:200] if result else None,
                   "error_type": type(error).__name__ if error else None,
                   "error_message": str(error)[:200] if error else None
               }

               # Create episode segment
               segment = await self.segmentation_service.create_segment(
                   agent_id=agent_id,
                   segment_type=segment_type,
                   context_data=skill_context,
                   metadata={"skill_execution": True}
               )

               return segment.id
           ```

        3. Store episode_id in SkillExecution record
        4. Return episode_id to caller for tracking

        Verify: EpisodeSegment created with skill metadata, episode_id stored in SkillExecution
        Done: Episode creation tested with mock episode services

  - title: "Add skill-aware episode segmentation"
    files:
      - path: "backend/core/episode_segmentation_service.py"
        action: |
        Extend EpisodeSegmentationService for skill context:

        1. Add skill metadata extraction helper:
           ```python
           def extract_skill_metadata(self, context_data: dict) -> dict:
               """Extract relevant metadata from skill execution context."""
               return {
                   "skill_name": context_data.get("skill_name"),
                   "skill_source": context_data.get("skill_source", "community"),
                   "execution_successful": context_data.get("error_type") is None,
                   "execution_time": context_data.get("execution_time", 0),
                   "input_hash": hashlib.sha256(
                       str(context_data.get("input_summary", "")).encode()
                   ).hexdigest()[:8]
               }
           ```

        2. Create skill-specific segmentation logic:
           ```python
           async def create_skill_episode(
               self,
               agent_id: str,
               skill_name: str,
               inputs: dict,
               result: Any,
               error: Optional[Exception],
               execution_time: float
           ) -> str:
               """Create episode with skill-specific segmentation."""
               context_data = {
                   "skill_name": skill_name,
                   "skill_source": "community",
                   "execution_time": execution_time,
                   "input_summary": self._summarize_inputs(inputs),
                   "result_summary": str(result)[:200] if result else None,
                   "error_type": type(error).__name__ if error else None,
                   "error_message": str(error)[:200] if error else None
               }

               segment = EpisodeSegment(
                   agent_id=agent_id,
                   segment_type="skill_execution",
                   context_data=context_data,
                   start_time=datetime.utcnow(),
                   end_time=datetime.utcnow(),
                   metadata=self.extract_skill_metadata(context_data)
               )

               self.db.add(segment)
               await self.db.commit()
               return segment.id
           ```

        Verify: Skill episodes created with proper metadata extraction
        Done: Helper methods tested with sample skill executions

  - title: "Track skill usage in agent graduation"
    files:
      - path: "backend/core/agent_graduation_service.py"
        action: |
        Extend AgentGraduationService to track skill usage:

        1. Import skill execution model:
           ```python
           from core.models import SkillExecution, EpisodeSegment
           ```

        2. Add skill usage metrics calculation:
           ```python
           async def calculate_skill_usage_metrics(
               self,
               agent_id: str,
               days_back: int = 30
           ) -> dict:
               """Calculate skill usage metrics for graduation readiness."""
               from sqlalchemy import func

               # Get recent skill executions
               start_date = datetime.utcnow() - timedelta(days=days_back)

               skill_executions = await self.db.execute(
                   select(SkillExecution)
                   .where(SkillExecution.agent_id == agent_id)
                   .where(SkillExecution.executed_at >= start_date)
                   .where(SkillExecution.skill_source == "community")
               )
               skills = skill_executions.scalars().all()

               # Calculate metrics
               total_executions = len(skills)
               successful_executions = len([s for s in skills if s.status == "success"])
               unique_skills_used = len(set(s.skill_name for s in skills))

               # Get skill episodes
               skill_episodes = await self.db.execute(
                   select(EpisodeSegment)
                   .where(EpisodeSegment.agent_id == agent_id)
                   .where(EpisodeSegment.segment_type.in_(["skill_success", "skill_failure"]))
                   .where(EpisodeSegment.start_time >= start_date)
               )
               episodes = skill_episodes.scalars().all()

               return {
                   "total_skill_executions": total_executions,
                   "successful_executions": successful_executions,
                   "success_rate": successful_executions / total_executions if total_executions > 0 else 0,
                   "unique_skills_used": unique_skills_used,
                   "skill_episodes_count": len(episodes),
                   "skill_learning_velocity": self._calculate_learning_velocity(episodes)
               }
           ```

        3. Integrate into readiness score calculation:
           ```python
           async def calculate_readiness_score(
               self,
               agent_id: str
           ) -> dict:
               """Calculate graduation readiness score with skill metrics."""
               # Get existing metrics
               episode_metrics = await self._calculate_episode_metrics(agent_id)
               intervention_metrics = await self._calculate_intervention_metrics(agent_id)

               # Add skill usage metrics
               skill_metrics = await self.calculate_skill_usage_metrics(agent_id)

               # Weighted score (existing: 40% episodes, 30% intervention, 30% constitutional)
               # New: Add skill usage as bonus factor
               base_score = (
                   episode_metrics["episode_score"] * 0.40 +
                   intervention_metrics["intervention_score"] * 0.30 +
                   episode_metrics["constitutional_score"] * 0.30
               )

               # Skill bonus: up to +5% for diverse skill usage
               skill_diversity_bonus = min(skill_metrics["unique_skills_used"] * 0.01, 0.05)

               final_score = min(base_score + skill_diversity_bonus, 1.0)

               return {
                   "readiness_score": final_score,
                   "episode_metrics": episode_metrics,
                   "intervention_metrics": intervention_metrics,
                   "skill_metrics": skill_metrics,
                   "skill_diversity_bonus": skill_diversity_bonus
               }
           ```

        Verify: Skill usage metrics calculated correctly, integrated into readiness score
        Done: Graduation service tests updated with skill metrics

  - title: "Add episodic context API endpoints"
    files:
      - path: "backend/api/skill_routes.py"
        action: |
        Add episodic memory integration endpoints:

        1. Get skill episodes endpoint:
           ```python
           @router.get("/api/skills/{skill_id}/episodes")
           async def get_skill_execution_episodes(
               skill_id: str,
               agent_id: str,
               limit: int = 50,
               db: Session = Depends(get_db)
           ):
               """Get episodic memories for skill executions."""
               # Query EpisodeSegment for skill executions
               episodes = db.query(EpisodeSegment).filter(
                   EpisodeSegment.context_data["skill_name"].astext == skill_id,
                   EpisodeSegment.agent_id == agent_id,
                   EpisodeSegment.segment_type.in_(["skill_success", "skill_failure"])
               ).order_by(EpisodeSegment.start_time.desc()).limit(limit).all()

               return {
                   "success": True,
                   "episodes": [
                       {
                           "episode_id": e.id,
                           "segment_type": e.segment_type,
                           "context": e.context_data,
                           "start_time": e.start_time.isoformat(),
                           "metadata": e.metadata
                       }
                       for e in episodes
                   ]
               }
           ```

        2. Get skill learning progress endpoint:
           ```python
           @router.get("/api/skills/{skill_id}/learning-progress")
           async def get_skill_learning_progress(
               skill_id: str,
               agent_id: str,
               db: Session = Depends(get_db)
           ):
               """Get learning progress for a specific skill."""
               # Get all skill executions
               executions = db.query(SkillExecution).filter(
                   SkillExecution.skill_name == skill_id,
                   SkillExecution.agent_id == agent_id
               ).all()

               # Calculate learning curve
               total = len(executions)
               successful = len([e for e in executions if e.status == "success"])
               failed = total - successful

               # Get trend over time
               execution_dates = [e.executed_at for e in executions]
               if len(execution_dates) > 1:
                   # Calculate improvement rate
                   recent_success_rate = successful / total
                   return {
                       "skill_id": skill_id,
                       "total_executions": total,
                       "successful_executions": successful,
                       "failed_executions": failed,
                       "success_rate": recent_success_rate,
                       "learning_trend": "improving" if recent_success_rate > 0.7 else "learning",
                       "last_execution": execution_dates[-1].isoformat()
                   }
               else:
                   return {"skill_id": skill_id, "message": "Not enough data"}
           ```

        Verify: Endpoints return episodic context and learning progress
        Done: API tests verify episode retrieval and learning metrics

  - title: "Create integration tests for episodic memory"
    files:
      - path: "backend/tests/test_skill_episodic_integration.py"
        action: |
        Create comprehensive integration tests:

        ```python
        import pytest
        from unittest.mock import AsyncMock, Mock
        from core.skill_registry_service import SkillRegistryService
        from core.episode_segmentation_service import EpisodeSegmentationService
        from core.agent_graduation_service import AgentGraduationService

        class TestSkillEpisodicIntegration:
            """Test episodic memory integration with community skills."""

            @pytest.mark.asyncio
            async def test_skill_execution_creates_episode(self):
                """Verify successful skill execution creates episode segment."""
                # Test episode creation on skill success

            @pytest.mark.asyncio
            async def test_skill_failure_creates_error_episode(self):
                """Verify failed skill execution creates error episode."""

            @pytest.mark.asyncio
            async def test_skill_metadata_extracted_correctly(self):
                """Verify skill metadata (name, source, execution time) is captured."""

            @pytest.mark.asyncio
            async def test_graduation_service_tracks_skill_usage(self):
                """Verify graduation service calculates skill usage metrics."""

            @pytest.mark.asyncio
            async def test_skill_diversity_bonus_in_readiness_score(self):
                """Verify unique skill usage contributes to graduation readiness."""

            @pytest.mark.asyncio
            async def test_get_skill_episodes_endpoint(self):
                """Verify API endpoint returns skill execution episodes."""

            @pytest.mark.asyncio
            async def test_learning_progress_endpoint(self):
                """Verify API endpoint returns learning trends over time."""
        ```

        Verify: All integration tests pass, episodic memory captures skill context
        Done: 8 integration tests verifying episode creation, graduation tracking, API endpoints

verification_criteria:
  - SkillRegistryService creates EpisodeSegment after each execution
  - EpisodeSegment contains skill metadata (name, source, inputs, result, error)
  - AgentGraduationService tracks skill usage in readiness score calculation
  - Skill diversity bonus applied correctly (up to +5%)
  - API endpoints /episodes and /learning-proportion return correct data
  - Integration tests verify end-to-end episodic memory flow
