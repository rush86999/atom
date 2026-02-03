#!/usr/bin/env python3
"""
Claims Generator - Automatically generate marketing claims from integration specifications
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class MarketingClaim:
    """Marketing claim data structure"""
    id: str
    claim: str
    claim_type: str
    category: str
    description: str
    validation_criteria: List[str]
    priority: str
    metadata: Optional[Dict[str, Any]] = None


class ClaimsGenerator:
    """
    Automatically generate marketing claims from integration specifications
    """
    
    def __init__(self, specifications_file: Optional[Path] = None):
        """
        Initialize claims generator
        
        Args:
            specifications_file: Path to integration specifications JSON
        """
        if specifications_file is None:
            specifications_file = Path(__file__).parent.parent / "data" / "integration_specifications.json"
        
        self.specifications_file = specifications_file
        self.specifications = self._load_specifications()
    
    def _load_specifications(self) -> Dict[str, Any]:
        """Load integration specifications from JSON file"""
        try:
            if self.specifications_file.exists():
                with open(self.specifications_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                logger.warning(f"Specifications file not found: {self.specifications_file}")
                return {"validated_integrations": {}, "pending_integrations": {}}
        except Exception as e:
            logger.error(f"Error loading specifications: {e}")
            return {"validated_integrations": {}, "pending_integrations": {}}
    
    def generate_integration_claim(
        self,
        integration_name: str,
        category: str,
        annual_value: Optional[float] = None,
        features: Optional[List[str]] = None,
        status: str = "validated"
    ) -> MarketingClaim:
        """
        Generate a marketing claim for an integration
        
        Args:
            integration_name: Name of the integration (e.g., "Asana", "Slack")
            category: Category (e.g., "project_management", "communication")
            annual_value: Annual business value in dollars
            features: List of key features
            status: "validated" or "pending"
        
        Returns:
            MarketingClaim object
        """
        # Generate claim text
        claim_text = f"{integration_name} Integration: "
        
        if annual_value:
            claim_text += f"Automate workflows delivering ${annual_value:,.0f}/year value"
        else:
            claim_text += f"Seamless integration with {integration_name}"
        
        # Determine priority based on value
        if annual_value:
            if annual_value >= 50000:
                priority = "high"
            elif annual_value >= 30000:
                priority = "medium"
            else:
                priority = "low"
        else:
            priority = "medium"
        
        # Create description
        description = f"{integration_name} integration"
        if features:
            description += f" - {', '.join(features[:3])}"
        
        return MarketingClaim(
            id=f"integration_{integration_name.lower().replace(' ', '_').replace('.', '')}",
            claim=claim_text,
            claim_type="integration",
            category=category,
            description=description,
            validation_criteria=["Real API", "Functionality", "Business Value"],
            priority=priority,
            metadata={
                "integration_name": integration_name,
                "annual_value": annual_value,
                "features": features or [],
                "status": status
            }
        )
    
    def generate_claims_from_specifications(
        self,
        status_filter: Optional[str] = None
    ) -> List[MarketingClaim]:
        """
        Generate claims from all integrations in specifications
        
        Args:
            status_filter: Filter by "validated" or "pending", or None for all
        
        Returns:
            List of MarketingClaim objects
        """
        claims = []
        
        # Process validated integrations
        if status_filter in [None, "validated"]:
            for integration_name, spec in self.specifications.get("validated_integrations", {}).items():
                try:
                    claim = self.generate_integration_claim(
                        integration_name=integration_name,
                        category=spec.get("category", "general"),
                        annual_value=spec.get("annual_value"),
                        features=spec.get("features", []),
                        status="validated"
                    )
                    claims.append(claim)
                    logger.debug(f"Generated claim for validated integration: {integration_name}")
                except Exception as e:
                    logger.error(f"Error generating claim for {integration_name}: {e}")
        
        # Process pending integrations
        if status_filter in [None, "pending"]:
            for integration_name, spec in self.specifications.get("pending_integrations", {}).items():
                try:
                    claim = self.generate_integration_claim(
                        integration_name=integration_name,
                        category=spec.get("category", "general"),
                        annual_value=spec.get("estimated_value"),
                        features=spec.get("features", []),
                        status="pending"
                    )
                    claims.append(claim)
                    logger.debug(f"Generated claim for pending integration: {integration_name}")
                except Exception as e:
                    logger.error(f"Error generating claim for {integration_name}: {e}")
        
        logger.info(f"Generated {len(claims)} claims from specifications")
        return claims
    
    def generate_claims_from_backend(self, backend_integrations_dir: Path) -> List[MarketingClaim]:
        """
        Scan backend/integrations directory and auto-generate claims
        
        Args:
            backend_integrations_dir: Path to backend/integrations directory
        
        Returns:
            List of MarketingClaim objects
        """
        claims = []
        
        if not backend_integrations_dir.exists():
            logger.error(f"Backend integrations directory not found: {backend_integrations_dir}")
            return claims
        
        # Find all route files
        route_files = list(backend_integrations_dir.glob("*_routes.py"))
        
        for route_file in route_files:
            try:
                # Extract integration name from filename
                # e.g., "slack_routes.py" -> "Slack"
                integration_name = route_file.stem.replace("_routes", "").replace("_", " ").title()
                
                # Check if already in specifications
                if integration_name.lower() in [k.lower() for k in self.specifications.get("validated_integrations", {}).keys()]:
                    continue
                if integration_name.lower() in [k.lower() for k in self.specifications.get("pending_integrations", {}).keys()]:
                    continue
                
                # Generate a basic claim
                claim = self.generate_integration_claim(
                    integration_name=integration_name,
                    category="general",
                    annual_value=None,
                    status="pending"
                )
                claims.append(claim)
                logger.debug(f"Generated claim from backend file: {integration_name}")
                
            except Exception as e:
                logger.error(f"Error processing {route_file}: {e}")
        
        logger.info(f"Generated {len(claims)} claims from backend scanning")
        return claims
    
    def export_to_validator_format(self, claims: List[MarketingClaim]) -> str:
        """
        Export claims to Python code format for validator
        
        Args:
            claims: List of MarketingClaim objects
        
        Returns:
            Python code string
        """
        code_lines = []
        
        for claim in claims:
            code_lines.append("MarketingClaim(")
            code_lines.append(f'    id="{claim.id}",')
            code_lines.append(f'    claim="{claim.claim}",')
            code_lines.append(f'    claim_type="{claim.claim_type}",')
            code_lines.append(f'    category="{claim.category}",')
            code_lines.append(f'    description="{claim.description}",')
            code_lines.append(f'    validation_criteria={claim.validation_criteria},')
            code_lines.append(f'    priority="{claim.priority}"')
            code_lines.append("),")
        
        return "\n".join(code_lines)


def main():
    """CLI for testing claims generator"""
    import sys
    
    generator = ClaimsGenerator()
    
    if len(sys.argv) > 1 and sys.argv[1] == "--scan-backend":
        # Scan backend directory
        backend_dir = Path(__file__).parent.parent.parent / "integrations"
        claims = generator.generate_claims_from_backend(backend_dir)
        print(f"\nGenerated {len(claims)} claims from backend:\n")
        for claim in claims[:10]:  # Show first 10
            print(f"  • {claim.claim}")
    else:
        # Generate from specifications
        claims = generator.generate_claims_from_specifications()
        print(f"\nGenerated {len(claims)} claims from specifications:\n")
        for claim in claims:
            print(f"  • {claim.claim}")


if __name__ == "__main__":
    main()
