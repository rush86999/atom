from core.database import engine, Base
from core.models import Workspace
from sales.models import Deal, CommissionEntry
from accounting.models import Entity
from ecommerce.models import EcommerceCustomer, EcommerceOrder, EcommerceOrderItem, Subscription, SubscriptionAudit
from service_delivery.models import Contract, Project, Milestone
from saas.models import SaaSTier, UsageEvent
from intelligence.models import ClientHealthScore, ResourceRole, CapacityPlan, BusinessScenario

def migrate():
    print("Updating database schema for Phase 18...")
    Base.metadata.create_all(bind=engine, tables=[
        Entity.__table__,
        Deal.__table__,
        CommissionEntry.__table__,
        EcommerceCustomer.__table__,
        EcommerceOrder.__table__,
        EcommerceOrderItem.__table__,
        Subscription.__table__,
        SubscriptionAudit.__table__,
        Contract.__table__,
        Project.__table__,
        Milestone.__table__,
        SaaSTier.__table__,
        UsageEvent.__table__,
        ClientHealthScore.__table__,
        ResourceRole.__table__,
        CapacityPlan.__table__,
        BusinessScenario.__table__
    ])
    print("Migration complete!")

if __name__ == "__main__":
    migrate()
