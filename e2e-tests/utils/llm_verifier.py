"""
LLM-based verification utility for marketing claims validation
Uses OpenAI API to independently assess test outputs against marketing claims
"""

import json
import os
from typing import Any, Dict, List, Optional

import openai
from openai import OpenAI


class LLMVerifier:
    """LLM-based verification for marketing claims validation"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4"  # Using GPT-4 for better reasoning capabilities

    def verify_marketing_claim(
        self, claim: str, test_output: Dict[str, Any], context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Verify if test output supports the marketing claim

        Args:
            claim: Marketing claim to verify
            test_output: Test results and outputs
            context: Additional context about the test

        Returns:
            Verification results with confidence score
        """
        prompt = self._build_verification_prompt(claim, test_output, context)

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": """You are a quality assurance expert that verifies marketing claims against actual test results.
                        Be objective, thorough, and evidence-based in your assessment.
                        Focus on whether the test results demonstrate the claimed capability.""",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1000,
            )

            result_text = response.choices[0].message.content
            return self._parse_verification_result(result_text, claim, test_output)

        except Exception as e:
            return {
                "claim": claim,
                "verified": False,
                "confidence": 0.0,
                "reason": f"LLM verification failed: {str(e)}",
                "evidence": test_output,
                "error": True,
            }

    def _build_verification_prompt(
        self, claim: str, test_output: Dict[str, Any], context: Optional[str]
    ) -> str:
        """Build the verification prompt for the LLM"""

        prompt_parts = [
            "MARKETING CLAIM TO VERIFY:",
            f"'{claim}'",
            "",
            "TEST OUTPUT DATA:",
            json.dumps(test_output, indent=2, default=str),
            "",
        ]

        if context:
            prompt_parts.extend(["ADDITIONAL CONTEXT:", context, ""])

        prompt_parts.extend(
            [
                "VERIFICATION INSTRUCTIONS:",
                "1. Analyze whether the test output demonstrates the claimed capability",
                "2. Provide a confidence score (0.0 to 1.0) based on evidence",
                "3. Explain your reasoning with specific references to the test data",
                "4. Identify any gaps or limitations in the evidence",
                "5. Format your response as JSON with these fields:",
                "   - verified: boolean",
                "   - confidence: float (0.0-1.0)",
                "   - reasoning: string (detailed explanation)",
                "   - evidence_cited: list of specific evidence points",
                "   - gaps: list of missing evidence or limitations",
                "",
                "RESPONSE:",
            ]
        )

        return "\n".join(prompt_parts)

    def _parse_verification_result(
        self, result_text: str, claim: str, test_output: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Parse the LLM response into structured verification results"""

        try:
            # Try to extract JSON from the response
            if "```json" in result_text:
                json_str = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                json_str = result_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = result_text

            result_data = json.loads(json_str)

            return {
                "claim": claim,
                "verified": result_data.get("verified", False),
                "confidence": float(result_data.get("confidence", 0.0)),
                "reason": result_data.get("reasoning", "No reasoning provided"),
                "evidence_cited": result_data.get("evidence_cited", []),
                "gaps": result_data.get("gaps", []),
                "evidence": test_output,
            }

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            # Fallback parsing if JSON parsing fails
            return {
                "claim": claim,
                "verified": False,
                "confidence": 0.0,
                "reason": f"Failed to parse LLM response: {str(e)}. Raw response: {result_text}",
                "evidence_cited": [],
                "gaps": ["LLM response parsing failed"],
                "evidence": test_output,
                "error": True,
            }

    def batch_verify_claims(
        self,
        claims: List[str],
        test_outputs: Dict[str, Any],
        context: Optional[str] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """
        Verify multiple marketing claims against the same test output

        Args:
            claims: List of marketing claims to verify
            test_outputs: Test results and outputs
            context: Additional context about the test

        Returns:
            Dictionary mapping claims to verification results
        """
        results = {}

        for claim in claims:
            print(f"Verifying claim: {claim}")
            results[claim] = self.verify_marketing_claim(claim, test_outputs, context)

        return results

    def generate_test_scenario(
        self, feature: str, marketing_claims: List[str]
    ) -> Dict[str, Any]:
        """
        Generate test scenarios based on marketing claims

        Args:
            feature: Feature being tested
            marketing_claims: List of marketing claims for the feature

        Returns:
            Generated test scenario with steps and expected outcomes
        """
        prompt = f"""
        Generate a comprehensive end-to-end test scenario for the feature: {feature}

        Marketing Claims:
        {chr(10).join(f"- {claim}" for claim in marketing_claims)}

        Create a test scenario that would validate these claims through actual usage.
        Include:
        1. Test scenario description
        2. Step-by-step test steps
        3. Expected outcomes that would support the marketing claims
        4. Key metrics to measure
        5. Success criteria

        Format as JSON with these fields:
        - scenario_description
        - test_steps (list of objects with step_number, action, expected_result)
        - expected_outcomes
        - metrics_to_measure
        - success_criteria
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a senior QA engineer creating realistic test scenarios.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=1500,
            )

            result_text = response.choices[0].message.content
            return self._parse_test_scenario(result_text)

        except Exception as e:
            return {
                "error": f"Failed to generate test scenario: {str(e)}",
                "scenario_description": f"Basic test for {feature}",
                "test_steps": [],
                "expected_outcomes": [],
                "metrics_to_measure": [],
                "success_criteria": [],
            }

    def _parse_test_scenario(self, result_text: str) -> Dict[str, Any]:
        """Parse the generated test scenario"""
        try:
            if "```json" in result_text:
                json_str = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                json_str = result_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = result_text

            return json.loads(json_str)

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            return {
                "error": f"Failed to parse test scenario: {str(e)}",
                "raw_response": result_text,
            }


# Utility functions for common verification patterns
def calculate_overall_confidence(
    verification_results: Dict[str, Dict[str, Any]],
) -> float:
    """Calculate overall confidence score from multiple verification results"""
    if not verification_results:
        return 0.0

    total_confidence = 0.0
    count = 0

    for result in verification_results.values():
        if not result.get("error", False):
            total_confidence += result.get("confidence", 0.0)
            count += 1

    return total_confidence / count if count > 0 else 0.0


def get_verification_summary(
    verification_results: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """Generate summary statistics from verification results"""
    total_claims = len(verification_results)
    verified_claims = sum(
        1
        for result in verification_results.values()
        if result.get("verified", False) and not result.get("error", False)
    )
    average_confidence = calculate_overall_confidence(verification_results)

    return {
        "total_claims": total_claims,
        "verified_claims": verified_claims,
        "verification_rate": verified_claims / total_claims
        if total_claims > 0
        else 0.0,
        "average_confidence": average_confidence,
        "claims_with_errors": sum(
            1 for result in verification_results.values() if result.get("error", False)
        ),
    }
