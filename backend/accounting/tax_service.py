from enum import Enum
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from accounting.models import Entity, Invoice, InvoiceStatus, TaxNexus
from sqlalchemy import func
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class NexusType(str, Enum):
    """Type of tax nexus"""
    ECONOMIC = "economic"  # Sales-based nexus
    PHYSICAL = "physical"  # Presence-based nexus


class TaxService:
    """
    Automated service for tax compliance and nexus detection.

    Enhanced features:
    - Proper address parsing using regex
    - State-specific nexus thresholds
    - Economic vs physical nexus distinction
    - Region name normalization
    """

    # State-specific nexus thresholds (as of 2024)
    # Economic nexus thresholds vary significantly by state
    STATE_THRESHOLDS = {
        # $500,000 threshold
        "California": 500000,
        "Texas": 500000,
        "Florida": 500000,

        # $100,000 threshold
        "New York": 100000,
        "Illinois": 100000,
        "Pennsylvania": 100000,
        "Ohio": 100000,
        "Georgia": 100000,
        "North Carolina": 100000,
        "Michigan": 100000,

        # Lower thresholds
        "Washington": 25000,  # Very low threshold
        "Colorado": 100000,
        "Arizona": 100000,

        # Default threshold for states not listed
        "default": 100000
    }

    # State abbreviations to full names mapping
    STATE_ABBREVIATIONS = {
        "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
        "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
        "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
        "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
        "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
        "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
        "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
        "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
        "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
        "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
        "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
        "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
        "WI": "Wisconsin", "WY": "Wyoming", "DC": "District of Columbia"
    }

    def __init__(self, db: Session):
        self.db = db

    def _parse_address(self, address: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Parse address to extract state and country.

        Uses improved regex pattern to identify:
        - State abbreviations (2 letters)
        - Full state names
        - Country names

        Args:
            address: Address string

        Returns:
            Tuple of (state, country) or (None, None) if not found
        """
        if not address:
            return None, None

        address_upper = address.upper()

        # Try to find state abbreviation first (2 letters at end of line or before zip)
        # Pattern: "ST 12345" or "State Name, ST 12345"
        state_abbr_match = re.search(
            r'\b([A-Z]{2})\s*\d{5}(?:-\d{4})?\b',
            address_upper
        )
        if state_abbr_match:
            abbr = state_abbr_match.group(1)
            if abbr in self.STATE_ABBREVIATIONS:
                return self.STATE_ABBREVIATIONS[abbr], "United States"

        # Try to find full state name
        for state_name in self.STATE_ABBREVIATIONS.values():
            if state_name.upper() in address_upper:
                return state_name, "United States"

        # Check for country indicators
        if "CANADA" in address_upper or any(prov in address_upper for prov in ["ONTARIO", "QUEBEC", "BRITISH COLUMBIA", "ALBERTA"]):
            return None, "Canada"

        if "UNITED KINGDOM" in address_upper or "UK" in address_upper or "U.K." in address_upper:
            return None, "United Kingdom"

        if "AUSTRALIA" in address_upper:
            return None, "Australia"

        # Fallback: try to extract last part as region
        parts = [p.strip() for p in address.split(",") if p.strip()]
        if parts:
            region = parts[-1]
            # Check if it's a state abbreviation
            if len(region) == 2 and region.upper() in self.STATE_ABBREVIATIONS:
                return self.STATE_ABBREVIATIONS[region.upper()], "United States"
            return region, None

        return None, None

    def _normalize_region_name(self, region: str) -> str:
        """
        Normalize region name for consistency.

        Args:
            region: Region name (state, province, etc.)

        Returns:
            Normalized region name
        """
        if not region:
            return "Unknown"

        # If it's an abbreviation, convert to full name
        if region.upper() in self.STATE_ABBREVIATIONS:
            return self.STATE_ABBREVIATIONS[region.upper()]

        # Capitalize properly
        return region.strip().title()

    def _get_nexus_threshold(self, state: str) -> float:
        """
        Get nexus threshold for a specific state.

        Args:
            state: State name

        Returns:
            Sales threshold in dollars
        """
        return self.STATE_THRESHOLDS.get(state, self.STATE_THRESHOLDS["default"])

    async def detect_nexus(self, workspace_id: str) -> List[Dict[str, Any]]:
        """
        Identify jurisdictions where the business may have a tax nexus
        based on customer locations and sales volume.

        Enhanced features:
        - Proper address parsing
        - State-specific thresholds
        - Economic vs physical nexus tracking
        - Region normalization

        Args:
            workspace_id: Workspace ID

        Returns:
            List of dictionaries with nexus details
        """
        # Get all invoices with customer addresses
        invoices = self.db.query(Invoice).join(Entity, Invoice.customer_id == Entity.id).filter(
            Invoice.workspace_id == workspace_id,
            Invoice.status != InvoiceStatus.VOID
        ).all()

        region_sales = {}
        region_customers = {}  # Track unique customers per region

        for inv in invoices:
            # Parse address properly
            state, country = self._parse_address(inv.customer.address)

            # Determine region
            if state:
                region = state
            elif country:
                region = country
            else:
                region = "Unknown"

            # Normalize region name
            region = self._normalize_region_name(region)

            # Accumulate sales
            region_sales[region] = region_sales.get(region, 0) + inv.amount

            # Track unique customers
            if region not in region_customers:
                region_customers[region] = set()
            if inv.customer_id:
                region_customers[region].add(inv.customer_id)

        new_nexuses = []
        for region, total_sales in region_sales.items():
            if region == "Unknown":
                continue

            # Get threshold for this region (state-specific for US)
            threshold = self._get_nexus_threshold(region)

            # Check if threshold met
            if total_sales >= threshold:
                # Check if nexus already exists
                existing = self.db.query(TaxNexus).filter(
                    TaxNexus.workspace_id == workspace_id,
                    TaxNexus.region == region
                ).first()

                if not existing:
                    # Determine nexus type
                    nexus_type = NexusType.ECONOMIC  # Sales-based

                    logger.info(
                        f"New Tax Nexus detected in {region} "
                        f"(Sales: ${total_sales:,.2f}, Threshold: ${threshold:,.2f}, "
                        f"Customers: {len(region_customers[region])})"
                    )

                    nexus = TaxNexus(
                        workspace_id=workspace_id,
                        region=region,
                        tax_type="Sales Tax",
                        is_active=True
                    )
                    self.db.add(nexus)
                    self.db.commit()
                    self.db.refresh(nexus)

                    new_nexuses.append({
                        "region": region,
                        "nexus_type": nexus_type.value,
                        "sales_amount": total_sales,
                        "threshold": threshold,
                        "customer_count": len(region_customers[region]),
                        "nexus_id": nexus.id
                    })

        return new_nexuses

    def estimate_tax_liability(self, workspace_id: str, period: str = None) -> Dict[str, Any]:
        """
        Estimate outstanding sales tax liability.
        """
        # For MVP, we'll assume a flat 7% tax for regions where nexus exists
        # and sales haven't explicitly recorded tax yet.
        nexuses = self.db.query(TaxNexus).filter(
            TaxNexus.workspace_id == workspace_id,
            TaxNexus.is_active == True
        ).all()
        
        nexus_regions = [n.region for n in nexuses]
        
        invoices = self.db.query(Invoice).join(Entity, Invoice.customer_id == Entity.id).filter(
            Invoice.workspace_id == workspace_id,
            Invoice.status != InvoiceStatus.VOID
        ).all()

        total_liability = 0.0
        breakdown = {}

        for inv in invoices:
            address = inv.customer.address or ""
            parts = [p.strip() for p in address.split(",") if p.strip()]
            region = parts[-1] if parts else "Unknown"
            
            if region in nexus_regions:
                # Mock calculation: 7% of invoice amount
                tax = inv.amount * 0.07 
                total_liability += tax
                breakdown[region] = breakdown.get(region, 0) + tax

        return {
            "total_estimated_liability": total_liability,
            "currency": "USD",
            "breakdown": breakdown
        }
