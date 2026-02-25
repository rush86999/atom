"""
Agent CRUD operations database integration tests (Phase 3, Plan 1, Task 2.2).

Tests cover:
- Agent CRUD operations with database
- Agent filtering and sorting
- Agent pagination
- Agent relationship queries (executions, feedback)

Coverage target: All query patterns tested with actual database
"""

import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, desc

from core.models import (
    AgentRegistry, AgentExecution, AgentFeedback, AgentStatus,
    User
)


class TestAgentCRUDOperations:
    """Integration tests for agent CRUD operations."""

    def test_create_agent(self, db_session: Session):
        """Test creating an agent in database."""
        agent = AgentRegistry(
            name="CRUDAgent",
            category="test",
            module_path="test.module",
            class_name="CRUDAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
            description="A CRUD test agent"
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        assert agent.id is not None
        assert agent.name == "CRUDAgent"
        assert agent.category == "test"
        assert agent.status == AgentStatus.INTERN.value

    def test_read_agent_by_id(self, db_session: Session):
        """Test reading an agent by ID."""
        agent = AgentRegistry(
            name="ReadAgent",
            category="test",
            module_path="test.module",
            class_name="ReadAgent",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        retrieved = db_session.query(AgentRegistry).filter_by(id=agent.id).first()
        assert retrieved is not None
        assert retrieved.id == agent.id
        assert retrieved.name == "ReadAgent"

    def test_update_agent(self, db_session: Session):
        """Test updating an agent."""
        agent = AgentRegistry(
            name="UpdateAgent",
            category="test",
            module_path="test.module",
            class_name="UpdateAgent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Update agent
        agent.name = "UpdatedAgent"
        agent.confidence_score = 0.75
        agent.status = AgentStatus.SUPERVISED.value
        db_session.commit()
        db_session.refresh(agent)

        assert agent.name == "UpdatedAgent"
        assert agent.confidence_score == 0.75
        assert agent.status == AgentStatus.SUPERVISED.value

    def test_delete_agent(self, db_session: Session):
        """Test deleting an agent."""
        agent = AgentRegistry(
            name="DeleteAgent",
            category="test",
            module_path="test.module",
            class_name="DeleteAgent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        agent_id = agent.id

        db_session.delete(agent)
        db_session.commit()

        deleted = db_session.query(AgentRegistry).filter_by(id=agent_id).first()
        assert deleted is None

    def test_bulk_agent_creation(self, db_session: Session):
        """Test creating multiple agents."""
        agents = []
        for i in range(5):
            agent = AgentRegistry(
                name=f"BulkAgent{i}",
                category="test",
                module_path="test.module",
                class_name=f"BulkAgent{i}",
                status=AgentStatus.INTERN.value,
                confidence_score=0.5 + (i * 0.1)
            )
            agents.append(agent)
            db_session.add(agent)

        db_session.commit()

        count = db_session.query(AgentRegistry).filter(
            AgentRegistry.name.like("BulkAgent%")
        ).count()
        assert count == 5


class TestAgentFiltering:
    """Integration tests for agent filtering."""

    def test_filter_by_status(self, db_session: Session):
        """Test filtering agents by status."""
        # Create agents with different statuses
        for status in [AgentStatus.STUDENT, AgentStatus.INTERN, AgentStatus.SUPERVISED]:
            agent = AgentRegistry(
                name=f"FilterAgent{status.value}",
                category="test",
                module_path="test.module",
                class_name="FilterAgent",
                status=status.value,
                confidence_score=0.5
            )
            db_session.add(agent)
        db_session.commit()

        interns = db_session.query(AgentRegistry).filter_by(
            status=AgentStatus.INTERN.value
        ).all()

        assert len(interns) == 1
        assert interns[0].status == AgentStatus.INTERN.value

    def test_filter_by_category(self, db_session: Session):
        """Test filtering agents by category."""
        categories = ["sales", "support", "finance"]
        for cat in categories:
            agent = AgentRegistry(
                name=f"{cat.capitalize()}Agent",
                category=cat,
                module_path="test.module",
                class_name="CategoryAgent",
                status=AgentStatus.INTERN.value,
                confidence_score=0.6
            )
            db_session.add(agent)
        db_session.commit()

        sales_agents = db_session.query(AgentRegistry).filter_by(
            category="sales"
        ).all()

        assert len(sales_agents) == 1
        assert sales_agents[0].category == "sales"

    def test_filter_by_confidence_range(self, db_session: Session):
        """Test filtering agents by confidence score range."""
        # Create agents with different confidence scores
        for score in [0.3, 0.5, 0.7, 0.9]:
            agent = AgentRegistry(
                name=f"ConfidenceAgent{int(score*10)}",
                category="test",
                module_path="test.module",
                class_name="ConfidenceAgent",
                status=AgentStatus.INTERN.value,
                confidence_score=score
            )
            db_session.add(agent)
        db_session.commit()

        high_confidence = db_session.query(AgentRegistry).filter(
            AgentRegistry.confidence_score >= 0.7
        ).all()

        assert len(high_confidence) == 2

    def test_filter_by_multiple_conditions(self, db_session: Session):
        """Test filtering agents with multiple conditions."""
        agent1 = AgentRegistry(
            name="MultiFilter1",
            category="sales",
            module_path="test.module",
            class_name="MultiAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        agent2 = AgentRegistry(
            name="MultiFilter2",
            category="sales",
            module_path="test.module",
            class_name="MultiAgent",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8
        )
        db_session.add(agent1)
        db_session.add(agent2)
        db_session.commit()

        results = db_session.query(AgentRegistry).filter(
            and_(
                AgentRegistry.category == "sales",
                AgentRegistry.confidence_score >= 0.7
            )
        ).all()

        assert len(results) == 1
        assert results[0].name == "MultiFilter2"

    def test_filter_with_or_condition(self, db_session: Session):
        """Test filtering agents with OR condition."""
        agent1 = AgentRegistry(
            name="OrFilter1",
            category="sales",
            module_path="test.module",
            class_name="OrAgent",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.3
        )
        agent2 = AgentRegistry(
            name="OrFilter2",
            category="support",
            module_path="test.module",
            class_name="OrAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        agent3 = AgentRegistry(
            name="OrFilter3",
            category="finance",
            module_path="test.module",
            class_name="OrAgent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        db_session.add(agent1)
        db_session.add(agent2)
        db_session.add(agent3)
        db_session.commit()

        results = db_session.query(AgentRegistry).filter(
            or_(
                AgentRegistry.category == "sales",
                AgentRegistry.category == "support"
            )
        ).all()

        assert len(results) == 2


class TestAgentSorting:
    """Integration tests for agent sorting."""

    def test_sort_by_name(self, db_session: Session):
        """Test sorting agents by name."""
        names = ["Zebra", "Alpha", "Charlie"]
        for name in names:
            agent = AgentRegistry(
                name=name,
                category="test",
                module_path="test.module",
                class_name="SortAgent",
                status=AgentStatus.INTERN.value,
                confidence_score=0.6
            )
            db_session.add(agent)
        db_session.commit()

        agents = db_session.query(AgentRegistry).order_by(
            AgentRegistry.name
        ).all()

        assert agents[0].name == "Alpha"
        assert agents[1].name == "Charlie"
        assert agents[2].name == "Zebra"

    def test_sort_by_confidence_desc(self, db_session: Session):
        """Test sorting agents by confidence descending."""
        for score in [0.3, 0.9, 0.6]:
            agent = AgentRegistry(
                name=f"SortScore{int(score*10)}",
                category="test",
                module_path="test.module",
                class_name="SortScoreAgent",
                status=AgentStatus.INTERN.value,
                confidence_score=score
            )
            db_session.add(agent)
        db_session.commit()

        agents = db_session.query(AgentRegistry).order_by(
            desc(AgentRegistry.confidence_score)
        ).all()

        assert agents[0].confidence_score == 0.9
        assert agents[1].confidence_score == 0.6
        assert agents[2].confidence_score == 0.3

    def test_sort_by_created_at(self, db_session: Session):
        """Test sorting agents by creation time."""
        agent1 = AgentRegistry(
            name="FirstAgent",
            category="test",
            module_path="test.module",
            class_name="TimeAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
            created_at=datetime.utcnow() - timedelta(hours=2)
        )
        agent2 = AgentRegistry(
            name="SecondAgent",
            category="test",
            module_path="test.module",
            class_name="TimeAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6,
            created_at=datetime.utcnow() - timedelta(hours=1)
        )
        db_session.add(agent1)
        db_session.add(agent2)
        db_session.commit()

        agents = db_session.query(AgentRegistry).order_by(
            AgentRegistry.created_at
        ).all()

        assert agents[0].name == "FirstAgent"
        assert agents[1].name == "SecondAgent"


class TestAgentPagination:
    """Integration tests for agent pagination."""

    def test_paginate_agents(self, db_session: Session):
        """Test paginating agent list."""
        # Create 15 agents
        for i in range(15):
            agent = AgentRegistry(
                name=f"PageAgent{i}",
                category="test",
                module_path="test.module",
                class_name="PageAgent",
                status=AgentStatus.INTERN.value,
                confidence_score=0.6
            )
            db_session.add(agent)
        db_session.commit()

        # Get first page (limit 5)
        page1 = db_session.query(AgentRegistry).filter(
            AgentRegistry.name.like("PageAgent%")
        ).limit(5).all()

        assert len(page1) == 5

        # Get second page (offset 5, limit 5)
        page2 = db_session.query(AgentRegistry).filter(
            AgentRegistry.name.like("PageAgent%")
        ).offset(5).limit(5).all()

        assert len(page2) == 5
        # Verify different agents
        assert page1[0].name != page2[0].name

    def test_paginate_with_ordering(self, db_session: Session):
        """Test paginating with ordering."""
        # Create agents
        names = ["AgentZ", "AgentA", "AgentM", "AgentB", "AgentY"]
        for name in names:
            agent = AgentRegistry(
                name=name,
                category="test",
                module_path="test.module",
                class_name="OrderedAgent",
                status=AgentStatus.INTERN.value,
                confidence_score=0.6
            )
            db_session.add(agent)
        db_session.commit()

        # Get first page ordered by name
        page1 = db_session.query(AgentRegistry).filter(
            AgentRegistry.name.like("Agent%")
        ).order_by(AgentRegistry.name).limit(2).all()

        assert len(page1) == 2
        assert page1[0].name == "AgentA"
        assert page1[1].name == "AgentB"

        # Get second page
        page2 = db_session.query(AgentRegistry).filter(
            AgentRegistry.name.like("Agent%")
        ).order_by(AgentRegistry.name).offset(2).limit(2).all()

        assert len(page2) == 2
        assert page2[0].name == "AgentM"
        assert page2[1].name == "AgentY"


class TestAgentRelationshipQueries:
    """Integration tests for agent relationship queries."""

    def test_agent_with_executions(self, db_session: Session):
        """Test querying agent executions relationship."""
        agent = AgentRegistry(
            name="RelAgent",
            category="test",
            module_path="test.module",
            class_name="RelAgent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        db_session.add(agent)
        db_session.commit()

        # Create executions
        for i in range(3):
            execution = AgentExecution(
                agent_id=agent.id,
                workspace_id="default",
                status="completed",
                input_data={"execution": i}
            )
            db_session.add(execution)
        db_session.commit()

        # Query executions
        executions = db_session.query(AgentExecution).filter_by(
            agent_id=agent.id
        ).all()

        assert len(executions) == 3
        for exec in executions:
            assert exec.agent_id == agent.id

    def test_agent_with_feedback(self, db_session: Session):
        """Test querying agent feedback relationship."""
        agent = AgentRegistry(
            name="FeedbackAgent",
            category="test",
            module_path="test.module",
            class_name="FeedbackAgent",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8
        )
        db_session.add(agent)
        db_session.commit()

        # Create execution
        execution = AgentExecution(
            agent_id=agent.id,
            workspace_id="default",
            status="completed",
            input_data={}
        )
        db_session.add(execution)
        db_session.commit()

        # Create feedback
        feedback = AgentFeedback(
            agent_id=agent.id,
            execution_id=execution.id,
            rating=5,
            feedback="Excellent work!"
        )
        db_session.add(feedback)
        db_session.commit()

        # Query feedback
        feedbacks = db_session.query(AgentFeedback).filter_by(
            agent_id=agent.id
        ).all()

        assert len(feedbacks) == 1
        assert feedbacks[0].rating == 5

    def test_join_agent_with_executions(self, db_session: Session):
        """Test joining agents with executions."""
        agent1 = AgentRegistry(
            name="JoinAgent1",
            category="test",
            module_path="test.module",
            class_name="JoinAgent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        agent2 = AgentRegistry(
            name="JoinAgent2",
            category="test",
            module_path="test.module",
            class_name="JoinAgent",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent1)
        db_session.add(agent2)
        db_session.commit()

        # Create execution only for agent1
        execution = AgentExecution(
            agent_id=agent1.id,
            workspace_id="default",
            status="completed",
            input_data={}
        )
        db_session.add(execution)
        db_session.commit()

        # Join query
        results = db_session.query(AgentRegistry).join(
            AgentExecution,
            AgentRegistry.id == AgentExecution.agent_id
        ).all()

        # Should only return agent1 which has executions
        assert len(results) == 1
        assert results[0].name == "JoinAgent1"

    def test_count_executions_per_agent(self, db_session: Session):
        """Test counting executions per agent."""
        agent1 = AgentRegistry(
            name="CountAgent1",
            category="test",
            module_path="test.module",
            class_name="CountAgent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        agent2 = AgentRegistry(
            name="CountAgent2",
            category="test",
            module_path="test.module",
            class_name="CountAgent",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        db_session.add(agent1)
        db_session.add(agent2)
        db_session.commit()

        # Create different number of executions
        for i in range(5):
            execution = AgentExecution(
                agent_id=agent1.id,
                workspace_id="default",
                status="completed",
                input_data={}
            )
            db_session.add(execution)

        for i in range(2):
            execution = AgentExecution(
                agent_id=agent2.id,
                workspace_id="default",
                status="completed",
                input_data={}
            )
            db_session.add(execution)
        db_session.commit()

        # Count executions
        agent1_count = db_session.query(AgentExecution).filter_by(
            agent_id=agent1.id
        ).count()
        agent2_count = db_session.query(AgentExecution).filter_by(
            agent_id=agent2.id
        ).count()

        assert agent1_count == 5
        assert agent2_count == 2

    def test_average_feedback_per_agent(self, db_session: Session):
        """Test calculating average feedback rating per agent."""
        agent = AgentRegistry(
            name="AvgAgent",
            category="test",
            module_path="test.module",
            class_name="AvgAgent",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.8
        )
        db_session.add(agent)
        db_session.commit()

        # Create execution
        execution = AgentExecution(
            agent_id=agent.id,
            workspace_id="default",
            status="completed",
            input_data={}
        )
        db_session.add(execution)
        db_session.commit()

        # Create feedback with different ratings
        ratings = [5, 4, 5, 3, 4]
        for rating in ratings:
            feedback = AgentFeedback(
                agent_id=agent.id,
                execution_id=execution.id,
                rating=rating,
                feedback=f"Rating {rating}"
            )
            db_session.add(feedback)
        db_session.commit()

        # Calculate average
        from sqlalchemy import func
        avg_rating = db_session.query(func.avg(AgentFeedback.rating)).filter_by(
            agent_id=agent.id
        ).scalar()

        expected_avg = sum(ratings) / len(ratings)
        assert avg_rating == expected_avg
