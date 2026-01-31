import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional
from ..core.models import Finding, Severity

logger = logging.getLogger(__name__)

class LLMAnalyzer:
    """
    Open-source LLM analyzer for security scanning.
    Supports:
    - BYOK (Bring Your Own Key) for OpenAI and Anthropic.
    - Local CPU inference for privacy and offline use.
    """

    def __init__(
        self, 
        mode: str = "local", 
        model: Optional[str] = None, 
        api_key: Optional[str] = None,
        provider: Optional[str] = None
    ):
        """
        Initialize the LLM Analyzer.
        
        Args:
            mode: "local" or "byok"
            model: Model name (e.g., "gpt-4o", "claude-3-5-sonnet", or local model path)
            api_key: API key for the provider
            provider: "openai" or "anthropic" (for byok mode)
        """
        self.mode = mode
        self.model = model or ("Qwen/Qwen2.5-1.5B-Instruct" if mode == "local" else "gpt-4o")
        self.api_key = api_key or os.getenv("ATOM_SECURITY_LLM_API_KEY")
        self.provider = provider or os.getenv("ATOM_SECURITY_LLM_PROVIDER", "openai")
        self.pipeline = None
        self.client = None

        if self.mode == "local":
            self._init_local()
        else:
            self._init_byok()

    def _init_local(self):
        """Initialize local transformers pipeline."""
        try:
            from transformers import pipeline, AutoTokenizer, AutoModelForCausalLM
            import torch
            
            logger.info(f"Loading local model: {self.model}...")
            self.tokenizer = AutoTokenizer.from_pretrained(self.model, trust_remote_code=True)
            self.model_obj = AutoModelForCausalLM.from_pretrained(
                self.model, 
                device_map="cpu", 
                torch_dtype=torch.float32,
                trust_remote_code=True
            )
            self.pipeline = pipeline(
                "text-generation",
                model=self.model_obj,
                tokenizer=self.tokenizer,
                max_new_tokens=512,
                temperature=0.1
            )
        except Exception as e:
            logger.error(f"Failed to load local model: {e}")
            raise

    def _init_byok(self):
        """Initialize cloud provider client."""
        if self.provider == "openai":
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key)
        elif self.provider == "anthropic":
            from anthropic import Anthropic
            self.client = Anthropic(api_key=self.api_key)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def analyze(self, skill_name: str, content: str) -> List[Finding]:
        """Run analysis on skill content."""
        system_prompt = (
            "You are a security expert. Analyze the AI agent skill for:\n"
            "1. Prompt Injection\n2. Code Injection\n3. Data Exfiltration\n\n"
            "Return JSON: {\"findings\": [{\"category\": \"...\", \"severity\": \"...\", \"description\": \"...\"}]}"
        )
        
        user_prompt = f"Skill: {skill_name}\n\nContent:\n{content[:4000]}"

        if self.mode == "local":
            return await self._analyze_local(system_prompt, user_prompt)
        else:
            return await self._analyze_byok(system_prompt, user_prompt)

    async def _analyze_local(self, system_prompt: str, user_prompt: str) -> List[Finding]:
        """Local inference."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        outputs = await asyncio.to_thread(self.pipeline, prompt)
        text = outputs[0]["generated_text"].replace(prompt, "")
        return self._parse_json(text)

    async def _analyze_byok(self, system_prompt: str, user_prompt: str) -> List[Finding]:
        """BYOK API call."""
        if self.provider == "openai":
            response = await asyncio.to_thread(
                self.client.chat.completions.create,
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                response_format={"type": "json_object"}
            )
            text = response.choices[0].message.content
        elif self.provider == "anthropic":
            response = await asyncio.to_thread(
                self.client.messages.create,
                model=self.model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}]
            )
            text = response.content[0].text
            
        return self._parse_json(text)

    def _parse_json(self, text: str) -> List[Finding]:
        """Parse findings from LLM output."""
        try:
            # Simple cleanup for markdown
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0]
            elif "```" in text:
                text = text.split("```")[1].split("```")[0]
            
            data = json.loads(text)
            findings = []
            for f in data.get("findings", []):
                findings.append(Finding(
                    rule_id=f.get("category", "LLM_DETECTED"),
                    category=f.get("category", "OTHER"),
                    severity=Severity(f.get("severity", "MEDIUM").upper()),
                    title=f.get("category", "Security issue"),
                    description=f.get("description", ""),
                    analyzer="llm"
                ))
            return findings
        except Exception as e:
            logger.warning(f"Failed to parse LLM response: {e}")
            return []
