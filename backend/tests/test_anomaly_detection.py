# import pytest
from datetime import datetime
from ai.data_intelligence import DataIntelligenceEngine, PlatformType, EntityType, UnifiedEntity

def test_deal_risk_detection():
    engine = DataIntelligenceEngine()
    
    # 1. Create a high-value deal
    deal = UnifiedEntity(
        entity_id="deal_1",
        entity_type=EntityType.DEAL,
        canonical_name="Enterprise Deal",
        platform_mappings={PlatformType.SALESFORCE: "sf_deal_1"},
        attributes={"amount": 50000, "status": "active"},
        relationships={},
        created_at=datetime.now(),
        updated_at=datetime.now(),
        confidence_score=1.0,
        source_platforms={PlatformType.SALESFORCE}
    )
    
    # 2. Create a blocked task
    task = UnifiedEntity(
        entity_id="task_1",
        entity_type=EntityType.TASK,
        canonical_name="Blocked Integration Task",
        platform_mappings={PlatformType.JIRA: "jira_task_1"},
        attributes={"status": "blocked", "priority": "high"},
        relationships={},
        created_at=datetime.now(),
        updated_at=datetime.now(),
        confidence_score=1.0,
        source_platforms={PlatformType.JIRA}
    )
    
    engine.entity_registry["deal_1"] = deal
    engine.entity_registry["task_1"] = task
    
    # 3. Link them
    engine._create_relationship("deal_1", "task_1", "depends_on", 1.0)
    
    # 4. Detect anomalies
    anomalies = engine.detect_anomalies()
    
    # 5. Verify
    deal_risks = [a for a in anomalies if a.severity == "critical" and "Deal" in a.title]
    assert len(deal_risks) > 0
    assert "Enterprise Deal" in deal_risks[0].description
    assert "task_1" in deal_risks[0].affected_entities

def test_sla_breach_detection():
    engine = DataIntelligenceEngine()
    
    # Create a high priority active task
    task = UnifiedEntity(
        entity_id="task_2",
        entity_type=EntityType.TASK,
        canonical_name="Urgent Customer Bug",
        platform_mappings={PlatformType.ZENDESK: "zd_ticket_1"},
        attributes={"status": "active", "priority": "high"},
        relationships={},
        created_at=datetime.now(),
        updated_at=datetime.now(),
        confidence_score=1.0,
        source_platforms={PlatformType.ZENDESK}
    )
    
    engine.entity_registry["task_2"] = task
    
    anomalies = engine.detect_anomalies()
    
    breaches = [a for a in anomalies if "SLA" in a.title]
    assert len(breaches) > 0
    assert "Urgent Customer Bug" in breaches[0].description

if __name__ == "__main__":
    test_deal_risk_detection()
    test_sla_breach_detection()
    print("All anomaly detection tests passed!")
