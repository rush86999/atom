"""
Business Outcome Validator for ATOM Platform
Focuses on tangible business value instead of technical features
"""

import json
import os
import time
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

import openai
from openai import OpenAI


class BusinessOutcomeValidator:
    """Business-focused validator that measures real-world value"""

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, model: str = "gpt-4"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = base_url
        self.model = model

        # Try to initialize LLM client, but don't fail if API key not available
        self.client = None
        if self.api_key:
            try:
                if self.base_url:
                    self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                else:
                    self.client = OpenAI(api_key=self.api_key)
                self.llm_available = True
            except Exception as e:
                print(f"LLM client initialization failed: {e}")
                self.llm_available = False
        else:
            print("LLM client not available - using rule-based business validation")
            self.llm_available = False

    def validate_business_value(
        self,
        feature_name: str,
        test_output: Dict[str, Any],
        business_metrics: Optional[Dict[str, Any]] = None,
        user_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate business value delivered by a feature

        Args:
            feature_name: Name of the feature being validated
            test_output: Technical test results
            business_metrics: Measured business metrics (time saved, costs, etc.)
            user_context: User scenario and business context

        Returns:
            Business value assessment with ROI calculations
        """

        # Extract business-relevant data from test output
        business_data = self._extract_business_signals(test_output)

        # Build business-focused validation prompt
        prompt = self._build_business_validation_prompt(
            feature_name, business_data, business_metrics, user_context
        )

        if self.llm_available and self.client:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {
                            "role": "system",
                            "content": """You are a Chief Financial Officer evaluating automation investments.
                            Your ONLY focus is on tangible business outcomes and ROI.
                            Be skeptical and demand concrete evidence of business value.
                            Rate everything in terms of money saved, time recovered, and revenue impact."""
                        },
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=1500,
                )

                result_text = response.choices[0].message.content
                return self._parse_business_validation(result_text, feature_name, business_data)

            except Exception as e:
                print(f"LLM validation failed, using fallback: {e}")
                return self._fallback_business_validation(feature_name, business_data, business_metrics, user_context)
        else:
            # Use rule-based validation when LLM not available
            return self._fallback_business_validation(feature_name, business_data, business_metrics, user_context)

    def calculate_automation_roi(
        self,
        workflow_name: str,
        time_saved_minutes: float,
        hourly_rate: float,
        implementation_cost: float = 0,
        monthly_frequency: int = 20
    ) -> Dict[str, Any]:
        """
        Calculate concrete ROI for automated workflows

        Args:
            workflow_name: Name of the automated workflow
            time_saved_minutes: Minutes saved per automation run
            hourly_rate: User's hourly cost (for time value calculation)
            implementation_cost: One-time setup cost
            monthly_frequency: How many times per month this runs

        Returns:
            Detailed ROI calculation with payback period
        """

        # Calculate time value
        hours_saved_per_run = time_saved_minutes / 60
        dollar_value_per_run = hours_saved_per_run * hourly_rate

        # Monthly and annual projections
        monthly_value = dollar_value_per_run * monthly_frequency
        annual_value = monthly_value * 12

        # ROI calculations
        monthly_roi = ((monthly_value - implementation_cost) / implementation_cost * 100) if implementation_cost > 0 else 1000
        annual_roi = ((annual_value - implementation_cost) / implementation_cost * 100) if implementation_cost > 0 else 12000

        # Payback period
        payback_months = implementation_cost / monthly_value if monthly_value > 0 else float('inf')

        return {
            "workflow_name": workflow_name,
            "time_metrics": {
                "minutes_saved_per_run": time_saved_minutes,
                "hours_saved_per_run": hours_saved_per_run,
                "monthly_frequency": monthly_frequency,
                "total_hours_saved_monthly": hours_saved_per_run * monthly_frequency,
                "total_hours_saved_annually": hours_saved_per_run * monthly_frequency * 12
            },
            "financial_metrics": {
                "hourly_rate": hourly_rate,
                "value_per_run": dollar_value_per_run,
                "monthly_value": monthly_value,
                "annual_value": annual_value,
                "implementation_cost": implementation_cost
            },
            "roi_metrics": {
                "monthly_roi_percent": monthly_roi,
                "annual_roi_percent": annual_roi,
                "payback_period_months": payback_months,
                "profit_first_year": annual_value - implementation_cost
            },
            "business_value_score": min(10.0, 5.0 + (annual_roi / 100)),  # Base 5 + 1 point per 100% ROI
            "recommendation": self._generate_roi_recommendation(annual_roi, payback_months)
        }

    def validate_user_productivity_gains(
        self,
        user_scenario: str,
        before_metrics: Dict[str, Any],
        after_metrics: Dict[str, Any],
        time_period_days: int = 30
    ) -> Dict[str, Any]:
        """
        Validate actual productivity improvements from user usage

        Args:
            user_scenario: Description of user's workflow
            before_metrics: Metrics before automation
            after_metrics: Metrics after automation
            time_period_days: Measurement period

        Returns:
            Productivity gain analysis with business impact
        """

        # Calculate improvements
        tasks_completed_before = before_metrics.get("tasks_completed", 0)
        tasks_completed_after = after_metrics.get("tasks_completed", 0)

        time_spent_before = before_metrics.get("hours_spent", 0)
        time_spent_after = after_metrics.get("hours_spent", 0)

        errors_before = before_metrics.get("errors", 0)
        errors_after = after_metrics.get("errors", 0)

        # Calculate percentages
        task_increase_pct = ((tasks_completed_after - tasks_completed_before) / tasks_completed_before * 100) if tasks_completed_before > 0 else 0
        time_reduction_pct = ((time_spent_before - time_spent_after) / time_spent_before * 100) if time_spent_before > 0 else 0
        error_reduction_pct = ((errors_before - errors_after) / errors_before * 100) if errors_before > 0 else 0

        # Business impact
        efficiency_score = (task_increase_pct + time_reduction_pct + error_reduction_pct) / 3

        prompt = f"""
        USER SCENARIO: {user_scenario}

        PRODUCTIVITY METRICS ({time_period_days} days):
        - Tasks completed: {tasks_completed_before} → {tasks_completed_after} ({task_increase_pct:+.1f}%)
        - Time spent: {time_spent_before}h → {time_spent_after}h ({time_reduction_pct:+.1f}%)
        - Errors: {errors_before} → {errors_after} ({error_reduction_pct:+.1f}%)

        EFFICIENCY SCORE: {efficiency_score:.1f}/100

        As a business operations manager, evaluate:
        1. Is this productivity gain meaningful for business operations?
        2. What's the estimated dollar value of these improvements?
        3. Should this automation be scaled across the organization?

        Rate the business value (0.0-10.0) where:
        - 0-3: Minimal business impact
        - 4-6: Moderate value worth considering
        - 7-8: Significant value, should deploy
        - 9-10: Transformative value, immediate deployment

        Respond in JSON with:
        - business_value_score: float (0.0-10.0)
        - monthly_value_estimate: string
        - scalability_recommendation: string
        - key_business_benefits: list of strings
        - deployment_priority: string (Low/Medium/High/Critical)
        """

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a business operations expert focused on productivity and ROI."
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.1,
                max_tokens=1000,
            )

            result_text = response.choices[0].message.content
            result = self._parse_productivity_validation(result_text)

            # Add raw metrics
            result.update({
                "user_scenario": user_scenario,
                "time_period_days": time_period_days,
                "productivity_metrics": {
                    "task_completion_increase_pct": task_increase_pct,
                    "time_reduction_pct": time_reduction_pct,
                    "error_reduction_pct": error_reduction_pct,
                    "efficiency_score": efficiency_score
                }
            })

            return result

        except Exception as e:
            return {
                "business_value_score": efficiency_score / 10,  # Fallback based on efficiency
                "error": f"LLM validation failed: {str(e)}",
                "fallback_used": True
            }

    def _extract_business_signals(self, test_output: Dict[str, Any]) -> Dict[str, Any]:
        """Extract business-relevant signals from technical test output"""

        signals = {
            "workflow_automation_detected": False,
            "cross_platform_coordination": False,
            "time_saving_features": False,
            "error_reduction_features": False,
            "productivity_gains": False,
            "scalability_indicators": False
        }

        output_text = str(test_output).lower()

        # Check for business value indicators
        if any(word in output_text for word in ["workflow", "automation", "automated"]):
            signals["workflow_automation_detected"] = True

        if any(word in output_text for word in ["coordination", "integration", "multiple services"]):
            signals["cross_platform_coordination"] = True

        if any(word in output_text for word in ["time", "schedule", "reminder", "routine"]):
            signals["time_saving_features"] = True

        if any(word in output_text for word in ["error", "check", "validate", "verify"]):
            signals["error_reduction_features"] = True

        if any(word in output_text for word in ["productivity", "efficient", "optimize"]):
            signals["productivity_gains"] = True

        if any(word in output_text for word in ["scale", "multiple", "enterprise", "organization"]):
            signals["scalability_indicators"] = True

        return signals

    def _build_business_validation_prompt(
        self, feature_name: str, business_data: Dict[str, Any],
        business_metrics: Optional[Dict[str, Any]], user_context: Optional[str]
    ) -> str:
        """Build business-focused validation prompt"""

        prompt = f"""
        FEATURE: {feature_name}

        BUSINESS SIGNALS DETECTED:
        {json.dumps(business_data, indent=2)}

        USER BUSINESS CONTEXT:
        {user_context or "No specific business context provided"}

        MEASURED BUSINESS METRICS:
        {json.dumps(business_metrics or {}, indent=2)}

        INSTRUCTIONS - CFO PERSPECTIVE:
        Evaluate this feature's business value as if you're deciding whether to invest $100K in it.

        1. What tangible business problems does this solve?
        2. How much money/time will this save annually?
        3. What's the competitive advantage?
        4. Is this a "must-have" or "nice-to-have"?
        5. Would you recommend this to other businesses?

        Rate the business value (0.0-10.0) where:
        - 0-2: No clear business value
        - 3-5: Limited value, niche use cases
        - 6-7: Good value, solid ROI
        - 8-9: Excellent value, competitive advantage
        - 10: Transformative value, must-have

        Return JSON with:
        - business_value_score: float (0.0-10.0)
        - annual_cost_savings: string
        - revenue_impact: string
        - competitive_advantage: string
        - investment_recommendation: string (Skip/Consider/Invest/Priority)
        - target_market_size: string
        - key_business_benefits: list of strings
        - roi_months_estimate: string
        """

        return prompt

    def _parse_business_validation(self, result_text: str, feature_name: str, business_data: Dict[str, Any]) -> Dict[str, Any]:
        """Parse business validation results"""

        try:
            if "```json" in result_text:
                json_str = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                json_str = result_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = result_text

            result = json.loads(json_str)
            result["feature_name"] = feature_name
            result["business_signals"] = business_data
            result["validation_timestamp"] = datetime.now().isoformat()
            return result

        except Exception as e:
            # Fallback parsing
            return {
                "feature_name": feature_name,
                "business_value_score": 5.0,  # Neutral score
                "error": f"Parse error: {str(e)}",
                "raw_response": result_text,
                "business_signals": business_data
            }

    def _parse_productivity_validation(self, result_text: str) -> Dict[str, Any]:
        """Parse productivity validation results"""

        try:
            if "```json" in result_text:
                json_str = result_text.split("```json")[1].split("```")[0].strip()
            elif "```" in result_text:
                json_str = result_text.split("```")[1].split("```")[0].strip()
            else:
                json_str = result_text

            return json.loads(json_str)

        except Exception as e:
            return {
                "business_value_score": 5.0,
                "error": f"Parse error: {str(e)}",
                "raw_response": result_text
            }

    def _generate_roi_recommendation(self, annual_roi: float, payback_months: float) -> str:
        """Generate ROI-based recommendation"""

        if annual_roi < 50:
            return "Poor ROI - reconsider implementation"
        elif annual_roi < 100:
            return "Marginal ROI - evaluate alternatives"
        elif annual_roi < 200:
            return "Good ROI - recommended implementation"
        elif annual_roi < 500:
            return "Excellent ROI - prioritize deployment"
        else:
            return "Exceptional ROI - immediate implementation"

    def _fallback_business_validation(
        self,
        feature_name: str,
        business_data: Dict[str, Any],
        business_metrics: Optional[Dict[str, Any]],
        user_context: Optional[str]
    ) -> Dict[str, Any]:
        """Rule-based business validation when LLM not available"""

        # Calculate business value score based on available metrics
        score = 0.0
        reasoning = []
        annual_savings = 0

        # Check business metrics for value indicators
        if business_metrics:
            monthly_savings = business_metrics.get("monthly_cost_savings", 0)
            annual_val = business_metrics.get("annual_value", 0)
            
            # Use annual value to derive monthly if needed
            if monthly_savings == 0 and annual_val > 0:
                monthly_savings = annual_val / 12

            if monthly_savings > 10000:
                score += 3.0
                reasoning.append("Significant monthly cost savings")
                annual_savings = monthly_savings * 12
            elif monthly_savings > 2000:  # Lowered threshold
                score += 2.0
                reasoning.append("Moderate monthly cost savings")
                annual_savings = monthly_savings * 12

            if business_metrics.get("productivity_increase_pct", 0) > 50:
                score += 2.5
                reasoning.append("High productivity increase")
            elif business_metrics.get("productivity_increase_pct", 0) > 25:
                score += 1.5
                reasoning.append("Moderate productivity increase")

            if business_metrics.get("error_reduction_pct", 0) > 75:
                score += 2.0
                reasoning.append("Excellent error reduction")
            elif business_metrics.get("error_reduction_pct", 0) > 50:
                score += 1.0
                reasoning.append("Good error reduction")

        # Check business signals
        if business_data.get("workflow_automation_detected"):
            score += 1.5
            reasoning.append("Workflow automation capability")

        if business_data.get("cross_platform_coordination"):
            score += 1.5
            reasoning.append("Cross-platform coordination")

        if business_data.get("scalability_indicators"):
            score += 1.0
            reasoning.append("Enterprise scalability")

        # Determine investment recommendation
        if score >= 8.0:
            recommendation = "Priority"
        elif score >= 6.0:
            recommendation = "Invest"
        elif score >= 4.0:
            recommendation = "Consider"
        else:
            recommendation = "Skip"

        return {
            "feature_name": feature_name,
            "business_value_score": min(10.0, score),
            "annual_cost_savings": f"${annual_savings:,.2f}",
            "revenue_impact": f"${annual_savings * 1.5:,.2f}" if annual_savings > 0 else "Minimal",
            "competitive_advantage": "Strong" if score >= 7.0 else "Moderate" if score >= 5.0 else "Limited",
            "investment_recommendation": recommendation,
            "target_market_size": "Enterprise" if business_data.get("scalability_indicators") else "SMB",
            "key_business_benefits": reasoning,
            "roi_months_estimate": "< 6 months" if annual_savings > 50000 else "6-12 months" if annual_savings > 20000 else "> 12 months",
            "validation_method": "Rule-based analysis",
            "business_signals": business_data
        }


# Utility functions for business outcome validation
def calculate_business_impact_score(validation_results: List[Dict[str, Any]]) -> float:
    """Calculate overall business impact score from multiple validations"""

    if not validation_results:
        return 0.0

    total_score = 0.0
    count = 0

    for result in validation_results:
        score = result.get("business_value_score", 0.0)
        if not result.get("error"):
            total_score += score
            count += 1

    return total_score / count if count > 0 else 0.0


def generate_business_summary(validation_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Generate executive summary of business validation results"""

    total_validations = len(validation_results)
    high_value_features = sum(1 for r in validation_results if r.get("business_value_score", 0) >= 8.0)
    medium_value_features = sum(1 for r in validation_results if 5.0 <= r.get("business_value_score", 0) < 8.0)
    low_value_features = total_validations - high_value_features - medium_value_features

    avg_business_score = calculate_business_impact_score(validation_results)

    return {
        "total_features_validated": total_validations,
        "high_value_features": high_value_features,
        "medium_value_features": medium_value_features,
        "low_value_features": low_value_features,
        "average_business_score": avg_business_score,
        "business_readiness": "Ready" if avg_business_score >= 7.0 else "Needs Improvement",
        "executive_recommendation": _generate_executive_recommendation(avg_business_score, high_value_features, total_validations)
    }


def _generate_executive_recommendation(avg_score: float, high_value_count: int, total_count: int) -> str:
    """Generate executive-level recommendation"""

    if avg_score >= 8.0 and high_value_count / total_count >= 0.7:
        return "STRONG BUY: Excellent business value across multiple features"
    elif avg_score >= 7.0:
        return "BUY: Good business value with solid ROI potential"
    elif avg_score >= 5.0:
        return "CONSIDER: Moderate business value, evaluate specific use cases"
    else:
        return "HOLD: Limited business value, requires repositioning"