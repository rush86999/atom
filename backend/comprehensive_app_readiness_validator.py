#!/usr/bin/env python3
"""
Comprehensive App Readiness Validation using Independent AI Validator
Validates features, detects gaps, and provides readiness assessment
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from independent_ai_validator.core.validator_engine import IndependentAIValidator, MarketingClaim

# Marketing claims to validate
READINESS_CLAIMS = [
    MarketingClaim(
        id="claim_1",
        claim="ATOM provides unified task and project management across multiple platforms (Asana, Notion, Trello, Jira)",
        claim_type="feature_completeness",
        category="project_management",
        description="Backend API endpoints and frontend integration for task/project management",
        validation_criteria=[
            "Unified task endpoint exists and is functional",
            "Unified project endpoint exists and is functional",
            "Frontend TaskManagement.tsx is properly integrated",
            "CRUD operations work for tasks and projects",
            "Mock data properly structured"
        ],
        priority="high"
    ),
    MarketingClaim(
        id="claim_2",
        claim="ATOM provides unified calendar management with conflict detection and multi-platform support (Google, Outlook)",
        claim_type="feature_completeness",
        category="calendar",
        description="Backend API endpoints and frontend integration for calendar events",
        validation_criteria=[
            "Unified calendar endpoint exists and is functional",
            "Frontend CalendarManagement.tsx is properly integrated",
            "CRUD operations work for calendar events",
            "Conflict detection is implemented",
            "Mock data properly structured"
        ],
        priority="high"
    ),
    MarketingClaim(
        id="claim_3",
        claim="ATOM provides advanced hybrid search combining semantic and keyword search across documents, meetings, and notes",
        claim_type="feature_completeness",
        category="search",
        description="Backend search endpoints with hybrid search capabilities",
        validation_criteria=[
            "Hybrid search endpoint exists and is functional",
            "Suggestions endpoint exists and is functional",
            "Search results are properly scored",
            "Filters work correctly",
            "Frontend search.tsx is properly integrated"
        ],
        priority="high"
    ),
    MarketingClaim(
        id="claim_4",
        claim="ATOM provides AI-powered workflow automation with natural language processing",
        claim_type="feature_completeness",
        category="workflows",
        description="Backend workflow endpoints and AI processing capabilities",
        validation_criteria=[
            "Workflow agent endpoint exists",
            "AI NLU processing is functional",
            "DeepSeek integration is working",
            "Workflow execution is implemented",
            "Frontend WorkflowChat.tsx is integrated"
        ],
        priority="high"
    ),
    MarketingClaim(
        id="claim_5",
        claim="ATOM is ready for real-world usage with all core features implemented",
        claim_type="readiness_assessment",
        category="overall_readiness",
        description="Overall application readiness for production use",
        validation_criteria=[
            "All critical API endpoints are functional",
            "Frontend components are properly integrated",
            "No critical bugs exist",
            "Core user flows are functional",
            "TypeScript conversion is complete"
        ],
        priority="critical"
    ),
    MarketingClaim(
        id="claim_6_gaps",
        claim="Identify any missing features, incomplete integrations, or critical bugs in ATOM application",
        claim_type="gap_analysis",
        category="gaps_and_bugs",
        description="Comprehensive analysis to find missing features and bugs",
        validation_criteria=[
            "Check for incomplete API implementations",
            "Identify missing frontend integrations",
            "Detect type errors or TypeScript issues",
            "Find broken user flows",
            "Identify security vulnerabilities"
        ],
        priority="critical"
    )
]

async def run_comprehensive_validation():
    """Run comprehensive validation of app readiness"""
    print("=" * 80)
    print("ATOM Application Readiness Validation")
    print("=" * 80)
    print()
    
    # Initialize validator
    validator = IndependentAIValidator(
        credentials_file="notes/credentials.md",
        backend_url="http://localhost:5059"
    )
    
    try:
        print("Initializing AI Validator...")
        if not await validator.initialize():
            print("ERROR: Failed to initialize validator")
            return 1
        
        print(f"✓ Validator initialized successfully")
        print(f"✓ Using DeepSeek for AI processing")
        print()
        
        # Register claims in the database
        print("Registering claims in database...")
        for claim in READINESS_CLAIMS:
            validator.claims_database[claim.id] = claim
        print(f"✓ {len(READINESS_CLAIMS)} claims registered")
        print()
        
        # Validate each claim
        results = []
        for i, claim in enumerate(READINESS_CLAIMS, 1):
            print(f"[{i}/{len(READINESS_CLAIMS)}] Validating: {claim.claim[:70]}...")
            print(f"    Category: {claim.category}")
            print(f"    Priority: {claim.priority}")
            
            result = await validator.validate_claim(claim.id)
            results.append(result)
            
            # Display key findings
            print(f"    ✓ Overall Score: {result.overall_score:.2f}/1.0")
            print(f"    ✓ Evidence Strength: {result.evidence_strength}")
            print()
            
            # Show critical recommendations
            if result.recommendations:
                print(f"    Key Recommendations:")
                for rec in result.recommendations[:3]:
                    print(f"      • {rec}")
                print()
        
        # Generate comprehensive report
        print("=" * 80)
        print("VALIDATION SUMMARY")
        print("=" * 80)
        print()
        
        # Calculate aggregate scores
        avg_score = sum(r.overall_score for r in results) / len(results)
        critical_results = [r for r in results if any(c.priority == "critical" for c in READINESS_CLAIMS if c.id == r.claim.split()[0])]
        
        print(f"Overall Readiness Score: {avg_score:.2%}")
        print()
        
        # Categorize results
        excellent = [r for r in results if r.overall_score >= 0.8]
        good = [r for r in results if 0.6 <= r.overall_score < 0.8]
        needs_work = [r for r in results if r.overall_score < 0.6]
        
        print(f"✓ Excellent ({len(excellent)}): {[r.claim[:40] + '...' for r in excellent]}")
        print(f"⚠ Good ({len(good)}): {[r.claim[:40] + '...' for r in good]}")
        print(f"✗ Needs Work ({len(needs_work)}): {[r.claim[:40] + '...' for r in needs_work]}")
        print()
        
        # Save detailed report
        report_path = Path(f"/Users/rushiparikh/projects/atom/atom/backend/app_readiness_validation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        detailed_report = {
            "validation_date": datetime.now().isoformat(),
            "overall_score": avg_score,
            "total_claims_validated": len(results),
            "results_by_category": {
                "excellent": len(excellent),
                "good": len(good),
                "needs_work": len(needs_work)
            },
            "detailed_results": [
                {
                    "claim": r.claim,
                    "score": r.overall_score,
                    "evidence_strength": r.evidence_strength,
                    "recommendations": r.recommendations[:5],
                    "provider_consensus": r.consensus_score
                }
                for r in results
            ],
            "critical_findings": [
                {
                    "claim": r.claim,
                    "score": r.overall_score,
                    "recommendations": r.recommendations
                }
                for r in results if r.overall_score < 0.6 or "gap" in r.claim.lower()
            ]
        }
        
        with open(report_path, 'w') as f:
            json.dump(detailed_report, f, indent=2)
        
        print(f"✓ Detailed report saved to: {report_path}")
        print()
        
        # Final assessment
        print("=" * 80)
        print("READINESS ASSESSMENT")
        print("=" * 80)
        print()
        
        if avg_score >= 0.8:
            print("✓ APPLICATION IS READY FOR PRODUCTION")
            print("  All features are implemented and functional.")
            return 0
        elif avg_score >= 0.6:
            print("⚠ APPLICATION IS MOSTLY READY")
            print("  Minor improvements recommended before production.")
            return 0
        else:
            print("✗ APPLICATION NEEDS WORK")
            print("  Critical features missing or not functional.")
            return 1
    
    except Exception as e:
        print(f"ERROR: Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    exit_code = asyncio.run(run_comprehensive_validation())
    sys.exit(exit_code)
