# -*- coding: utf-8 -*-
"""
Regression tests for SQLAlchemy relationship fixes (Phase 70-01)

Tests verify that relationship attributes can be accessed without AttributeError.
Ensures back_populates is correctly configured on both sides of relationships.
"""
import pytest
from sqlalchemy import inspect
from core.models import User, FFmpegJob, HueBridge, HomeAssistantConnection
from core.database import get_db_session


class TestFFmpegJobRelationships:
    """Test FFmpegJob relationship configuration"""
    
    def test_ffmpeg_job_user_relationship_config(self):
        """Verify FFmpegJob.user uses back_populates"""
        insp = inspect(FFmpegJob)
        user_rel = insp.relationships['user']
        assert user_rel.back_populates == 'ffmpeg_jobs', \
            "FFmpegJob.user should use back_populates='ffmpeg_jobs'"
    
    def test_user_ffmpeg_jobs_relationship_config(self):
        """Verify User.ffmpeg_jobs uses back_populates"""
        insp = inspect(User)
        # Check that the relationship exists
        assert hasattr(User, 'ffmpeg_jobs'), "User should have ffmpeg_jobs relationship"
        
        # Check it uses back_populates
        ffmpeg_jobs_rel = insp.relationships['ffmpeg_jobs']
        assert ffmpeg_jobs_rel.back_populates == 'user', \
            "User.ffmpeg_jobs should use back_populates='user'"
    
    def test_ffmpeg_job_user_relationship_access(self, db_session):
        """Test that FFmpegJob.user can be accessed without AttributeError"""
        # Create test user
        user = User(
            id="test-ffmpeg-user",
            email="ffmpeg-test@example.com",
            role="member"
        )
        db_session.add(user)
        db_session.commit()
        
        # Create FFmpegJob
        job = FFmpegJob(
            id="test-ffmpeg-job",
            user_id="test-ffmpeg-user",
            operation="trim_video",
            status="pending"
        )
        db_session.add(job)
        db_session.commit()
        
        # Test forward relationship access (job.user)
        loaded_job = db_session.query(FFmpegJob).filter_by(id="test-ffmpeg-job").first()
        assert loaded_job is not None, "FFmpegJob should be loaded"
        assert loaded_job.user is not None, "FFmpegJob.user should not be None"
        assert loaded_job.user.id == "test-ffmpeg-user", "Should load correct user"
        
        # Test reverse relationship access (user.ffmpeg_jobs)
        loaded_user = db_session.query(User).filter_by(id="test-ffmpeg-user").first()
        assert loaded_user is not None, "User should be loaded"
        assert hasattr(loaded_user, 'ffmpeg_jobs'), "User should have ffmpeg_jobs attribute"
        assert len(loaded_user.ffmpeg_jobs) == 1, "User should have 1 ffmpeg_job"
        assert loaded_user.ffmpeg_jobs[0].id == "test-ffmpeg-job", "Should load correct job"
        
        # Cleanup
        db_session.delete(job)
        db_session.delete(user)
        db_session.commit()


class TestHueBridgeRelationships:
    """Test HueBridge relationship configuration"""
    
    def test_hue_bridge_user_relationship_config(self):
        """Verify HueBridge.user uses back_populates"""
        insp = inspect(HueBridge)
        user_rel = insp.relationships['user']
        assert user_rel.back_populates == 'hue_bridges', \
            "HueBridge.user should use back_populates='hue_bridges'"
    
    def test_user_hue_bridges_relationship_config(self):
        """Verify User.hue_bridges uses back_populates"""
        insp = inspect(User)
        # Check that the relationship exists
        assert hasattr(User, 'hue_bridges'), "User should have hue_bridges relationship"
        
        # Check it uses back_populates
        hue_bridges_rel = insp.relationships['hue_bridges']
        assert hue_bridges_rel.back_populates == 'user', \
            "User.hue_bridges should use back_populates='user'"
    
    def test_hue_bridge_user_relationship_access(self, db_session):
        """Test that HueBridge.user can be accessed without AttributeError"""
        # Create test user
        user = User(
            id="test-hue-user",
            email="hue-test@example.com",
            role="member"
        )
        db_session.add(user)
        db_session.commit()
        
        # Create HueBridge
        bridge = HueBridge(
            user_id="test-hue-user",
            bridge_ip="192.168.1.100",
            api_key="encrypted_key_here"
        )
        db_session.add(bridge)
        db_session.commit()
        
        # Test forward relationship access (bridge.user)
        loaded_bridge = db_session.query(HueBridge).filter_by(id=bridge.id).first()
        assert loaded_bridge is not None, "HueBridge should be loaded"
        assert loaded_bridge.user is not None, "HueBridge.user should not be None"
        assert loaded_bridge.user.id == "test-hue-user", "Should load correct user"
        
        # Test reverse relationship access (user.hue_bridges)
        loaded_user = db_session.query(User).filter_by(id="test-hue-user").first()
        assert loaded_user is not None, "User should be loaded"
        assert hasattr(loaded_user, 'hue_bridges'), "User should have hue_bridges attribute"
        assert len(loaded_user.hue_bridges) == 1, "User should have 1 hue_bridge"
        assert loaded_user.hue_bridges[0].id == bridge.id, "Should load correct bridge"
        
        # Cleanup
        db_session.delete(bridge)
        db_session.delete(user)
        db_session.commit()


class TestHomeAssistantConnectionRelationships:
    """Test HomeAssistantConnection relationship configuration"""
    
    def test_ha_connection_user_relationship_config(self):
        """Verify HomeAssistantConnection.user uses back_populates"""
        insp = inspect(HomeAssistantConnection)
        user_rel = insp.relationships['user']
        assert user_rel.back_populates == 'ha_connections', \
            "HomeAssistantConnection.user should use back_populates='ha_connections'"
    
    def test_user_ha_connections_relationship_config(self):
        """Verify User.ha_connections uses back_populates"""
        insp = inspect(User)
        # Check that the relationship exists
        assert hasattr(User, 'ha_connections'), "User should have ha_connections relationship"
        
        # Check it uses back_populates
        ha_conn_rel = insp.relationships['ha_connections']
        assert ha_conn_rel.back_populates == 'user', \
            "User.ha_connections should use back_populates='user'"
    
    def test_ha_connection_user_relationship_access(self, db_session):
        """Test that HomeAssistantConnection.user can be accessed without AttributeError"""
        # Create test user
        user = User(
            id="test-ha-user",
            email="ha-test@example.com",
            role="member"
        )
        db_session.add(user)
        db_session.commit()
        
        # Create HomeAssistantConnection
        conn = HomeAssistantConnection(
            user_id="test-ha-user",
            url="http://homeassistant.local:8123",
            token="encrypted_token_here"
        )
        db_session.add(conn)
        db_session.commit()
        
        # Test forward relationship access (conn.user)
        loaded_conn = db_session.query(HomeAssistantConnection).filter_by(id=conn.id).first()
        assert loaded_conn is not None, "HomeAssistantConnection should be loaded"
        assert loaded_conn.user is not None, "HomeAssistantConnection.user should not be None"
        assert loaded_conn.user.id == "test-ha-user", "Should load correct user"
        
        # Test reverse relationship access (user.ha_connections)
        loaded_user = db_session.query(User).filter_by(id="test-ha-user").first()
        assert loaded_user is not None, "User should be loaded"
        assert hasattr(loaded_user, 'ha_connections'), "User should have ha_connections attribute"
        assert len(loaded_user.ha_connections) == 1, "User should have 1 ha_connection"
        assert loaded_user.ha_connections[0].id == conn.id, "Should load correct connection"
        
        # Cleanup
        db_session.delete(conn)
        db_session.delete(user)
        db_session.commit()


class TestNoBackrefInCriticalModels:
    """Verify no backref remains in critical models"""
    
    def test_ffmpeg_job_no_backref(self):
        """FFmpegJob should not use backref"""
        insp = inspect(FFmpegJob)
        user_rel = insp.relationships['user']
        # Check that back_populates is used (not backref)
        assert user_rel.back_populates is not None, "Should use back_populates"
        assert user_rel.backref is None, "Should not use backref"
    
    def test_hue_bridge_no_backref(self):
        """HueBridge should not use backref"""
        insp = inspect(HueBridge)
        user_rel = insp.relationships['user']
        assert user_rel.back_populates is not None, "Should use back_populates"
        assert user_rel.backref is None, "Should not use backref"
    
    def test_ha_connection_no_backref(self):
        """HomeAssistantConnection should not use backref"""
        insp = inspect(HomeAssistantConnection)
        user_rel = insp.relationships['user']
        assert user_rel.back_populates is not None, "Should use back_populates"
        assert user_rel.backref is None, "Should not use backref"
