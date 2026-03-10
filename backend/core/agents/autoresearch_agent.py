import logging
import json
import os
import subprocess
import asyncio
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from core.llm_router import LLMRouter

logger = logging.getLogger(__name__)

class AutoresearchAgent:
    """
    The Autoresearch Agent automates machine learning experimentation.
    It reads instructions, modifies a target script, runs it, and evaluates
    metrics to decide whether to keep or rollback changes.
    """

    def __init__(self, db: Session, llm_router: LLMRouter):
        self.db = db
        self.llm = llm_router

    async def run_experiment_loop(self, 
                                  program_md_path: str, 
                                  target_script_path: str, 
                                  iterations: int = 5,
                                  tenant_id: str = "default") -> Dict[str, Any]:
        """
        Run the autoresearch loop for a specified number of iterations.
        """
        logger.info(f"Autoresearch: Starting {iterations} iterations on {target_script_path}")
        
        try:
            with open(program_md_path, 'r') as f:
                instructions = f.read()
        except Exception as e:
            logger.error(f"Failed to read instructions from {program_md_path}: {e}")
            return {"status": "error", "message": "Failed to read instructions"}

        best_metric = float('inf')  # Assuming lower is better (e.g., validation loss)
        history = []

        for i in range(iterations):
            logger.info(f"Autoresearch: Iteration {i+1}/{iterations}")
            
            try:
                with open(target_script_path, 'r') as f:
                    current_code = f.read()
            except Exception as e:
                logger.error(f"Failed to read target script {target_script_path}: {e}")
                return {"status": "error", "message": "Failed to read target script"}

            # Generate new code
            prompt = f"""You are the Autoresearch Agent, an expert machine learning researcher.
            
            Instructions guidelines:
            {instructions}
            
            Here is the current code for the training script:
            ```python
            {current_code}
            ```
            
            Propose a single meaningful change (e.g., adjust hyperparameters, change architecture, modify optimizer).
            Return ONLY the full updated python code, without markdown blocks, ready to be executed.
            Do not include any explanations, just the raw code. Make sure it prints a final metric in the format 'FINAL_METRIC: <value>' for evaluation.
            """

            try:
                response = await self.llm.call(
                    tenant_id=tenant_id,
                    messages=[
                        {"role": "system", "content": "You are a senior ML researcher. Output only valid Python code designed to improve the metric."},
                        {"role": "user", "content": prompt}
                    ]
                )
                
                new_code = response.get("content", "").strip()
                if new_code.startswith("```python"):
                    new_code = new_code[9:]
                if new_code.endswith("```"):
                    new_code = new_code[:-3]
                new_code = new_code.strip()
                
            except Exception as e:
                logger.error(f"Autoresearch: LLM generation failed: {e}")
                continue

            # Write proposed code to temporary file
            temp_script_path = f"{target_script_path}.tmp"
            with open(temp_script_path, 'w') as f:
                f.write(new_code)

            # Evaluate
            metric = await self._evaluate_script(temp_script_path)
            
            result = {
                "iteration": i + 1,
                "metric": metric,
                "kept": False
            }

            if metric is not None and metric < best_metric:
                # Accept change
                best_metric = metric
                result["kept"] = True
                # Replace original file with new code
                os.replace(temp_script_path, target_script_path)
                logger.info(f"Iteration {i+1}: Change accepted! New best metric: {best_metric}")
            else:
                # Rollback (discard temp file)
                if os.path.exists(temp_script_path):
                    os.remove(temp_script_path)
                logger.info(f"Iteration {i+1}: Change rejected. Metric: {metric}, Best: {best_metric}")

            history.append(result)

        return {
            "status": "success",
            "best_metric": best_metric if best_metric != float('inf') else None,
            "history": history
        }

    async def _evaluate_script(self, script_path: str) -> Optional[float]:
        """
        Executes the script and parses standard output for evaluating performance.
        Looks for 'FINAL_METRIC: <value>'
        """
        try:
            # Using asyncio to run subprocess without blocking
            process = await asyncio.create_subprocess_exec(
                "python", script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                logger.warning(f"Script evaluation failed with return code {process.returncode}: {stderr.decode()}")
                return None

            output = stdout.decode()
            for line in output.split('\n'):
                if "FINAL_METRIC:" in line:
                    try:
                        metric_val = float(line.split("FINAL_METRIC:")[1].strip())
                        return metric_val
                    except ValueError:
                        pass
                        
            logger.warning("FINAL_METRIC not found in script output.")
            return None
            
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            return None
