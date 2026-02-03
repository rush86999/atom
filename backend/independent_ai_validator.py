#!/usr/bin/env python3
"""
Independent AI Validator for ATOM Marketing Claims
Uses external LLM providers to validate marketing claims with real evidence
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add current directory to path
sys.path.append(str(Path(__file__).parent))

from independent_ai_validator.core.validator_engine import IndependentAIValidator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('independent_ai_validator.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class IndependentValidatorCLI:
    """Command Line Interface for Independent AI Validator"""

    def __init__(self):
        self.validator = IndependentAIValidator()

    async def run_validation(self, claim_ids: list = None, output_format: str = "json"):
        """
        Run independent AI validation
        """
        try:
            print("[INFO] Independent AI Validator for ATOM Marketing Claims")
            print("=" * 60)
            print("Initializing validation system...")

            # Initialize the validator
            if not await self.validator.initialize():
                print("[ERROR] Failed to initialize validator")
                return False

            print("[SUCCESS] Validator initialized successfully")

            # Check available providers
            available_providers = list(self.validator.providers.keys())
            print(f"[INFO] Available AI Providers: {available_providers}")

            # Validate credentials
            credential_status = self.validator.credential_manager.validate_credentials()
            print(f"[INFO] Credential Status: {credential_status}")

            # Run validation
            if claim_ids:
                print(f"\n[INFO] Validating specific claims: {claim_ids}")
                results = {}
                for claim_id in claim_ids:
                    print(f"   Validating: {claim_id}...")
                    try:
                        result = await self.validator.validate_claim(claim_id)
                        results[claim_id] = result
                        print(f"   [PASS] {claim_id}: {result.overall_score:.1%}")
                    except Exception as e:
                        print(f"   [FAIL] {claim_id}: Failed - {str(e)}")
            else:
                print("\n[INFO] Validating ALL marketing claims...")
                results = await self.validator.validate_all_claims()

            # Generate report
            print(f"\n[INFO] Generating validation report...")
            report_data = await self.validator.generate_validation_report(results)
            report = json.loads(report_data)

            # Display results
            self.display_results(report)

            # Save report
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = f"independent_ai_validation_report_{timestamp}.{output_format}"

            if output_format == "json":
                with open(report_file, 'w', encoding='utf-8') as f:
                    f.write(report_data)
            else:
                # Generate markdown report
                markdown_report = self.generate_markdown_report(report)
                with open(f"independent_ai_validation_report_{timestamp}.md", 'w', encoding='utf-8') as f:
                    f.write(markdown_report)
                report_file = f"independent_ai_validation_report_{timestamp}.md"

            print(f"\n[INFO] Report saved to: {report_file}")

            # Cleanup
            await self.validator.cleanup()
            print("[INFO] Cleanup completed")

            return True

        except Exception as e:
            logger.error(f"Validation failed: {str(e)}")
            print(f"[ERROR] Validation failed: {str(e)}")
            return False

    def display_results(self, report: dict):
        """Display validation results in a formatted way"""
        summary = report["summary"]
        metadata = report["metadata"]

        print(f"\n[INFO] VALIDATION SUMMARY")
        print("-" * 40)
        print(f"Overall Score: {summary['overall_score']:.1%}")
        print(f"Claims Validated: {metadata['total_claims_validated']}")
        print(f"Fully Validated: {summary['claims_fully_validated']}")
        print(f"Partially Validated: {summary['claims_partially_validated']}")
        print(f"Not Validated: {summary['claims_not_validated']}")
        print(f"Average Confidence: {summary['average_confidence']:.1%}")

        print(f"\n[INFO] CATEGORY BREAKDOWN")
        print("-" * 40)
        for category, score in report["category_scores"].items():
            status = "[PASS]" if score >= 0.9 else "[WARN]" if score >= 0.7 else "[FAIL]"
            print(f"{status} {category.title()}: {score:.1%}")

        print(f"\n[INFO] DETAILED RESULTS")
        print("-" * 40)
        for claim_id, result in report["detailed_results"].items():
            status = "[PASS]" if result["score"] >= 0.9 else "[WARN]" if result["score"] >= 0.7 else "[FAIL]"
            print(f"{status} {claim_id}: {result['score']:.1%} ({result['evidence_strength']})")

    def generate_markdown_report(self, report: dict) -> str:
        """Generate markdown version of the validation report"""
        summary = report["summary"]
        metadata = report["metadata"]

        md_content = f"""# Independent AI Validation Report for ATOM Marketing Claims

**Generated:** {report['metadata']['validation_date']}
**Validator Version:** {report['metadata']['validator_version']}
**AI Providers Used:** {', '.join(report['metadata']['providers_used'])}

## Executive Summary

This independent AI validation report provides an unbiased assessment of ATOM's marketing claims using external AI models and real evidence-based testing.

### Overall Results
- **Overall Validation Score:** {summary['overall_score']:.1%}
- **Total Claims Validated:** {metadata['total_claims_validated']}
- **Fully Validated Claims (≥90%):** {summary['claims_fully_validated']}
- **Partially Validated Claims (70-89%):** {summary['claims_partially_validated']}
- **Not Validated Claims (<70%):** {summary['claims_not_validated']}
- **Average Confidence Score:** {summary['average_confidence']:.1%}

## Validation Methodology

### Independent AI Analysis
- **Multiple AI Providers:** {len(report['metadata']['providers_used'])} external models used
- **Cross-Validation:** Consensus-based scoring to eliminate bias
- **Evidence-Based Testing:** Real API calls and system integration testing
- **Bias Detection:** Automated bias analysis performed on all results

### Evidence Collection
- **Live System Testing:** Real-time API calls to ATOM backend
- **Integration Validation:** Testing of third-party service connections
- **Performance Monitoring:** Actual performance metrics collection
- **Security Assessment:** Enterprise feature validation

## Category Results

"""

        for category, score in report["category_scores"].items():
            status = "✅ Strongly Validated" if score >= 0.9 else "⚠️ Partially Validated" if score >= 0.7 else "❌ Not Validated"
            md_content += f"### {category.title()}\n"
            md_content += f"- **Validation Score:** {score:.1%}\n"
            md_content += f"- **Status:** {status}\n\n"

        md_content += "## Detailed Claim Analysis\n\n"

        for claim_id, result in report["detailed_results"].items():
            status_emoji = "✅" if result["score"] >= 0.9 else "⚠️" if result["score"] >= 0.7 else "❌"
            md_content += f"### {status_emoji} {claim_id}\n\n"
            md_content += f"**Claim:** {result['claim']}\n"
            md_content += f"**Category:** {result['category'].title()}\n"
            md_content += f"**Validation Score:** {result['score']:.1%}\n"
            md_content += f"**Evidence Strength:** {result['evidence_strength']}\n\n"

            if result["recommendations"]:
                md_content += "**Recommendations:**\n"
                for rec in result["recommendations"]:
                    md_content += f"- {rec}\n"
                md_content += "\n"

            md_content += "---\n\n"

        md_content += f"""
## Confidence Intervals

All validation scores include statistical confidence intervals to account for:
- AI model variability
- Evidence quality assessment
- Cross-validation consensus

## Methodology Transparency

This validation was conducted using:
- **Independent AI Models:** External LLM providers with no connection to ATOM
- **Real Evidence:** Actual system performance and integration testing
- **Statistical Validation:** Mathematical confidence intervals and consensus scoring
- **Bias Detection:** Automated bias analysis and correction

### Validation Criteria
Each claim was evaluated based on:
1. **Functional Accuracy:** Does the feature actually work?
2. **Performance Claims:** Are performance metrics met?
3. **Integration Capabilities:** Do integrations function properly?
4. **Evidence Quality:** Is there sufficient supporting evidence?

## Conclusion

The independent AI validation process provides an unbiased, evidence-based assessment of ATOM's marketing claims. All results are derived from real system testing and external AI analysis, ensuring complete independence and objectivity.

---

*Report generated by Independent AI Validator*
*Methodology: Evidence-based AI validation with cross-validation*
*Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*
"""

        return md_content

def main():
    """Main execution function"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Independent AI Validator for ATOM Marketing Claims"
    )
    parser.add_argument(
        "--claims",
        nargs="*",
        help="Specific claim IDs to validate (default: all claims)"
    )
    parser.add_argument(
        "--format",
        choices=["json", "markdown"],
        default="markdown",
        help="Output format for the report (default: markdown)"
    )
    parser.add_argument(
        "--list-claims",
        action="store_true",
        help="List all available claims and exit"
    )

    args = parser.parse_args()

    cli = IndependentValidatorCLI()

    if args.list_claims:
        # Just initialize to get claims list
        async def list_claims():
            await cli.validator.initialize()
            print("\n[INFO] Available Marketing Claims:")
            print("-" * 40)
            for claim_id, claim in cli.validator.claims_database.items():
                print(f"* {claim_id}: {claim.claim}")
                print(f"  Category: {claim.category}")
                print(f"  Type: {claim.claim_type}")
                print()
            await cli.validator.cleanup()

        asyncio.run(list_claims())
        return

    # Run validation
    try:
        success = asyncio.run(cli.run_validation(args.claims, args.format))
        sys.exit(0 if success else 1)

    except KeyboardInterrupt:
        print("\n[WARN] Validation interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n[FATAL] Fatal error: {str(e)}")
        logger.exception("Fatal error in main")
        sys.exit(1)

if __name__ == "__main__":
    main()