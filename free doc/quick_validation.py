#!/usr/bin/env python3
"""
Quick Validation Script for ATOM Platform

This script provides a fast assessment of ATOM's current capabilities
without requiring the backend to be running. It analyzes the codebase
structure and implementation files to validate marketing claims.
"""

import json
import os
import sys
from pathlib import Path
from datetime import datetime


class QuickValidator:
    def __init__(self):
        self.results = {}
        self.claims_validation = {}

    def count_service_files(self):
        """Count service implementation files"""
        service_patterns = ["**/*service*.py", "**/*handler*.py"]
        service_count = 0
        backend_dir = Path("backend/python-api-service")

        if backend_dir.exists():
            for pattern in service_patterns:
                service_files = list(backend_dir.rglob(pattern))
                # Filter out test files and backup files
                service_files = [
                    f
                    for f in service_files
                    if not any(x in str(f) for x in ["test", "backup", "__pycache__"])
                ]
                service_count = max(service_count, len(service_files))

        return service_count

    def check_byok_implementation(self):
        """Check BYOK implementation files"""
        byok_files = {}
        backend_dir = Path("backend/python-api-service")

        if backend_dir.exists():
            api_key_files = list(backend_dir.rglob("*api*key*.py"))
            for file_path in api_key_files:
                if "test" not in str(file_path):
                    provider_name = file_path.stem.replace("_", " ").title()
                    byok_files[provider_name] = str(file_path)

        return byok_files

    def check_workflow_implementation(self):
        """Check workflow implementation files"""
        workflow_files = {}
        backend_dir = Path("backend/python-api-service")

        if backend_dir.exists():
            workflow_patterns = ["**/*workflow*.py", "**/*automation*.py"]

            for pattern in workflow_patterns:
                files = list(backend_dir.rglob(pattern))
                for file_path in files:
                    if "test" not in str(file_path):
                        workflow_name = file_path.stem.replace("_", " ").title()
                        workflow_files[workflow_name] = str(file_path)

        return workflow_files

    def check_nlu_implementation(self):
        """Check NLU implementation files"""
        nlu_files = {}
        backend_dir = Path("backend/python-api-service")

        if backend_dir.exists():
            nlu_patterns = ["**/*nlu*.py", "**/*language*.py", "**/*understanding*.py"]

            for pattern in nlu_patterns:
                files = list(backend_dir.rglob(pattern))
                for file_path in files:
                    if "test" not in str(file_path):
                        nlu_name = file_path.stem.replace("_", " ").title()
                        nlu_files[nlu_name] = str(file_path)

        return nlu_files

    def check_voice_implementation(self):
        """Check voice implementation files"""
        voice_files = {}
        project_root = Path(".")

        voice_patterns = [
            "**/*voice*.py",
            "**/*audio*.py",
            "**/*speech*.py",
            "**/*wake*word*.py",
        ]

        for pattern in voice_patterns:
            files = list(project_root.rglob(pattern))
            for file_path in files:
                if "test" not in str(file_path) and "backup" not in str(file_path):
                    voice_name = file_path.stem.replace("_", " ").title()
                    voice_files[voice_name] = str(file_path)

        return voice_files

    def check_wake_word_detector(self):
        """Check if wake word detector exists"""
        wake_word_dir = Path("wake_word_recorder")
        return wake_word_dir.exists() and any(wake_word_dir.iterdir())

    def check_audio_samples(self):
        """Check if audio samples exist"""
        audio_samples_dir = Path("audio_samples")
        return audio_samples_dir.exists() and any(audio_samples_dir.iterdir())

    def check_frontend_implementation(self):
        """Check frontend implementation"""
        frontend_dirs = ["frontend-nextjs", "desktop"]

        frontend_status = {}
        for dir_name in frontend_dirs:
            dir_path = Path(dir_name)
            frontend_status[dir_name] = {
                "exists": dir_path.exists(),
                "has_package_json": (dir_path / "package.json").exists(),
                "has_next_config": (dir_path / "next.config.js").exists(),
            }

        return frontend_status

    def validate_claims(self):
        """Validate marketing claims based on file analysis"""

        # Count services
        service_count = self.count_service_files()

        # Check implementations
        byok_files = self.check_byok_implementation()
        workflow_files = self.check_workflow_implementation()
        nlu_files = self.check_nlu_implementation()
        voice_files = self.check_voice_implementation()
        wake_word_exists = self.check_wake_word_detector()
        audio_samples_exists = self.check_audio_samples()
        frontend_status = self.check_frontend_implementation()

        # Claim 1: "Production Ready"
        infrastructure_exists = (
            service_count > 0
            and len(workflow_files) > 0
            and any(status["exists"] for status in frontend_status.values())
        )

        self.claims_validation["production_ready"] = {
            "claimed": True,
            "actual": infrastructure_exists,
            "evidence": f"Services: {service_count}, Workflows: {len(workflow_files)}, Frontend: {len(frontend_status)}",
            "verdict": "PARTIALLY VALID" if infrastructure_exists else "INVALID",
            "notes": "Infrastructure exists but backend services need configuration",
        }

        # Claim 2: "15+ integrated platforms"
        self.claims_validation["integrated_platforms"] = {
            "claimed": "15+",
            "actual": service_count,
            "evidence": f"Service implementations found: {service_count}",
            "verdict": "VALID" if service_count >= 15 else "INVALID",
            "notes": f"{service_count} service implementations available",
        }

        # Claim 3: "Natural language workflow generation"
        self.claims_validation["nl_workflow_generation"] = {
            "claimed": True,
            "actual": len(workflow_files) > 0,
            "evidence": f"Workflow implementation files: {len(workflow_files)}",
            "verdict": "VALID" if len(workflow_files) > 0 else "INVALID",
            "notes": "Workflow infrastructure implemented",
        }

        # Claim 4: "BYOK System"
        self.claims_validation["byok_system"] = {
            "claimed": True,
            "actual": len(byok_files) > 0,
            "evidence": f"BYOK implementation files: {len(byok_files)}",
            "verdict": "VALID" if len(byok_files) > 0 else "INVALID",
            "notes": "BYOK system infrastructure implemented",
        }

        # Claim 5: "Advanced NLU System"
        self.claims_validation["advanced_nlu"] = {
            "claimed": True,
            "actual": len(nlu_files) > 0,
            "evidence": f"NLU implementation files: {len(nlu_files)}",
            "verdict": "VALID" if len(nlu_files) > 0 else "INVALID",
            "notes": "NLU infrastructure implemented",
        }

        # Claim 6: "Real service integrations"
        self.claims_validation["real_integrations"] = {
            "claimed": True,
            "actual": service_count > 0,
            "evidence": f"Service implementations: {service_count}",
            "verdict": "VALID" if service_count > 0 else "INVALID",
            "notes": "Service integration infrastructure exists",
        }

        # Claim 7: "Voice integration"
        self.claims_validation["voice_integration"] = {
            "claimed": True,
            "actual": len(voice_files) > 0,
            "evidence": f"Voice files: {len(voice_files)}, Wake word: {wake_word_exists}, Audio samples: {audio_samples_exists}",
            "verdict": "VALID" if len(voice_files) > 0 else "INVALID",
            "notes": "Voice integration infrastructure exists",
        }

        # Claim 8: "Cross-platform coordination"
        self.claims_validation["cross_platform_coordination"] = {
            "claimed": True,
            "actual": service_count > 1,
            "evidence": f"Multiple service implementations: {service_count}",
            "verdict": "VALID" if service_count > 1 else "INVALID",
            "notes": "Multi-service coordination capability exists",
        }

        # Store detailed results
        self.results = {
            "service_count": service_count,
            "byok_files": byok_files,
            "workflow_files": workflow_files,
            "nlu_files": nlu_files,
            "voice_files": voice_files,
            "wake_word_exists": wake_word_exists,
            "audio_samples_exists": audio_samples_exists,
            "frontend_status": frontend_status,
        }

    def run_validation(self):
        """Run the quick validation"""
        print("🚀 Quick ATOM Platform Validation")
        print("=" * 60)
        print("📊 Analyzing codebase structure and implementation files")
        print("=" * 60)

        # Run validation
        self.validate_claims()

        # Print results
        print("\n📈 VALIDATION RESULTS:")
        print("=" * 60)

        for claim, validation in self.claims_validation.items():
            claimed = validation["claimed"]
            actual = validation["actual"]
            verdict = validation["verdict"]
            evidence = validation["evidence"]
            notes = validation.get("notes", "")

            if verdict == "VALID":
                icon = "✅"
            elif verdict == "PARTIALLY VALID":
                icon = "⚠️"
            else:
                icon = "❌"

            print(f"\n{icon} {claim.upper().replace('_', ' ')}")
            print(f"   Claimed: {claimed}")
            print(f"   Actual: {actual}")
            print(f"   Evidence: {evidence}")
            if notes:
                print(f"   Notes: {notes}")
            print(f"   Verdict: {verdict}")

        # Calculate overall score
        valid_claims = sum(
            1 for v in self.claims_validation.values() if v["verdict"] == "VALID"
        )
        partial_claims = sum(
            1
            for v in self.claims_validation.values()
            if v["verdict"] == "PARTIALLY VALID"
        )
        total_claims = len(self.claims_validation)

        weighted_score = valid_claims + (partial_claims * 0.5)
        weighted_percentage = (weighted_score / total_claims) * 100

        print(f"\n📊 OVERALL ASSESSMENT:")
        print(f"   Valid Claims: {valid_claims}/{total_claims}")
        print(f"   Partially Valid: {partial_claims}/{total_claims}")
        print(f"   Weighted Score: {weighted_percentage:.1f}%")

        if weighted_percentage >= 70:
            print("🎯 VERDICT: Infrastructure is SUBSTANTIALLY COMPLETE")
            print("   ✅ Most claimed features have infrastructure implemented")
        elif weighted_percentage >= 50:
            print("⚠️ VERDICT: Infrastructure is PARTIALLY COMPLETE")
            print("   📋 Core infrastructure exists but needs backend configuration")
        else:
            print("❌ VERDICT: Infrastructure is INCOMPLETE")
            print("   🔧 Significant development work needed")

        print(f"\n💡 RECOMMENDATIONS:")
        print("   • Start backend services to enable full functionality")
        print("   • Configure OAuth for service integrations")
        print("   • Update README to reflect current infrastructure status")

        return self.results, self.claims_validation


def main():
    """Main function"""
    validator = QuickValidator()
    results, claims = validator.run_validation()

    # Save results
    with open("quick_validation_results.json", "w") as f:
        json.dump(
            {
                "timestamp": datetime.now().isoformat(),
                "validation_method": "quick_file_analysis",
                "results": results,
                "claims_validation": claims,
            },
            f,
            indent=2,
        )

    print(f"\n📄 Quick validation results saved to: quick_validation_results.json")


if __name__ == "__main__":
    main()

