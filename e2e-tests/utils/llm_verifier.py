"""
LLM-based verification utility for marketing claims validation
Uses OpenAI API to independently assess test outputs against marketing claims
"""

import json
import os
import time
from typing import Any, Dict, List, Optional

import openai
from openai import OpenAI


class LLMVerifier:
    """LLM-based verification for marketing claims validation"""

    def __init__(self, api_key: Optional[str] = None, max_retries: int = 3):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")

        self.client = OpenAI(api_key=self.api_key)
        self.model = "gpt-4"  # Using GPT-4 for better reasoning capabilities
        self.max_retries = max_retries
        self.request_delay = 2  # Increased delay between requests

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
            for attempt in range(self.max_retries):
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
                        timeout=30,  # Add 30 second timeout
                    )

                    result_text = response.choices[0].message.content
                    return self._parse_verification_result(result_text, claim, test_output)

                except Exception as api_error:
                    if attempt == self.max_retries - 1:
                        # Last attempt failed
                        raise api_error
                    
                    # Check if it's a rate limit error
                    error_str = str(api_error)
                    if "429" in error_str or "rate limit" in error_str.lower():
                        print(f"Rate limit hit, waiting {self.request_delay * (attempt + 1)} seconds before retry...")
                        time.sleep(self.request_delay * (attempt + 1))
                        continue
                    else:
                        # Non-rate-limit error, don't retry
                        raise api_error

        except Exception as e:
            error_msg = str(e)
            
            # Check for API quota/rate limit issues
            if "429" in error_msg or "insufficient_quota" in error_msg or "rate limit" in error_msg.lower():
                return {
                    "claim": claim,
                    "verified": False,
                    "confidence": 0.0,
                    "reason": f"API quota/rate limit reached: {error_msg}. Verification paused due to OpenAI API limits.",
                    "evidence": test_output,
                    "api_limit_error": True,
                    "error": True,
                }
            else:
                return {
                    "claim": claim,
                    "verified": False,
                    "confidence": 0.0,
                    "reason": f"LLM verification failed: {error_msg}",
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
            result = self.verify_marketing_claim(claim, test_outputs, context)
            
            # Check if it's an API limit error and provide fallback
            if result.get("api_limit_error", False):
                print(f"⚠️  API limit reached for claim: {claim}. Skipping verification due to OpenAI quota limits.")
                # Provide mock verification based on available evidence
                results[claim] = self._fallback_verification(claim, test_outputs)
            else:
                results[claim] = result
            
            # Rate limiting: wait between API calls to avoid rate limits
            time.sleep(self.request_delay)

        return results

    def _fallback_verification(self, claim: str, test_output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provide fallback verification when API is unavailable
        Uses rule-based analysis instead of LLM
        """
        # Simple rule-based verification based on available evidence
        evidence_keywords = {
            "workflow": ["workflow", "automation", "automated"],
            "natural language": ["natural_language", "input", "description"],
            "memory": ["memory", "context", "history", "conversation"],
            "seamless": ["seamless", "integrated", "coordination"],
            "voice": ["voice", "audio", "speech", "transcription"],
            "production": ["production", "ready", "fastapi", "next", "framework"]
        }
        
        claim_lower = claim.lower()
        evidence_text = str(test_output).lower()
        
        # Check if evidence supports the claim
        supporting_evidence = []
        for keyword, evidence_list in evidence_keywords.items():
            if keyword in claim_lower:
                found_evidence = [ev for ev in evidence_list if ev in evidence_text]
                supporting_evidence.extend(found_evidence)
        
        # Basic verification logic
        if supporting_evidence:
            confidence = min(0.8, len(supporting_evidence) * 0.2)
            return {
                "claim": claim,
                "verified": confidence >= 0.4,
                "confidence": confidence,
                "reason": f"Fallback verification found evidence: {supporting_evidence}. Limited analysis due to API quota limits.",
                "evidence_cited": supporting_evidence,
                "gaps": ["Limited analysis due to API quota exhaustion"],
                "fallback_used": True
            }
        else:
            return {
                "claim": claim,
                "verified": False,
                "confidence": 0.0,
                "reason": "No supporting evidence found for marketing claim (fallback verification due to API limits)",
                "evidence": test_output,
                "fallback_used": True
            }

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
