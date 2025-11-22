
import sys
import os
from pathlib import Path

# Add current directory to path
sys.path.append(os.getcwd())
sys.path.append(os.path.join(os.getcwd(), "backend"))

from backend.independent_ai_validator.core.claims_generator import ClaimsGenerator

def main():
    generator = ClaimsGenerator()
    
    # Generate all pending claims
    pending_claims = generator.generate_claims_from_specifications(status_filter="pending")
    
    # Already added: Salesforce, HubSpot, Slack, Zendesk, Stripe
    already_added = ["Salesforce", "HubSpot", "Slack", "Zendesk", "Stripe"]
    
    # Filter for remaining pending integrations
    target_claims = [
        claim for claim in pending_claims 
        if not any(added in claim.claim for added in already_added)
    ]
    
    print("# Remaining Integration Claims")
    print(generator.export_to_validator_format(target_claims))

if __name__ == "__main__":
    main()
