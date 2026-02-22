"""
LLM Scoring stage using local model (vLLM or llama.cpp).
"""
import os
import json
import shutil
from datetime import datetime
from typing import Tuple, Dict, Any

from celery.exceptions import SoftTimeLimitExceeded
from workers.celery_app import celery_app
from core.config import get_settings
from core.database import get_db_context
from models import ProcessingJob, EvaluationResult, ScoringTemplate, Call

settings = get_settings()

# Global LLM (loaded once per worker)
_llm = None

def _use_cpu_llm() -> bool:
    return os.environ.get("USE_CPU_LLM", "").lower() in ("1", "true", "yes")

def get_llm():
    """Get or load LLM. Uses llama_cpp for .gguf (vLLM does not support GGUF)."""
    global _llm
    if _llm is None:
        model_path = settings.LLM_MODEL_PATH
        use_cpu = _use_cpu_llm()
        use_gguf = model_path.lower().endswith(".gguf")
        try:
            if use_gguf:
                print("[scoring] Loading llama.cpp model (GGUF)...")
                from llama_cpp import Llama
                _llm = Llama(
                    model_path=model_path,
                    n_ctx=settings.VLLM_MAX_MODEL_LEN,
                    n_gpu_layers=0 if use_cpu else -1,
                )
                _llm._backend = "llama_cpp"
            else:
                try:
                    from vllm import LLM, SamplingParams
                    _llm = LLM(
                        model=model_path,
                        tensor_parallel_size=settings.VLLM_TENSOR_PARALLEL_SIZE,
                        gpu_memory_utilization=settings.VLLM_GPU_MEMORY_UTILIZATION,
                        max_model_len=settings.VLLM_MAX_MODEL_LEN
                    )
                    _llm._backend = "vllm"
                except ImportError:
                    from llama_cpp import Llama
                    _llm = Llama(
                        model_path=model_path,
                        n_ctx=settings.VLLM_MAX_MODEL_LEN,
                        n_gpu_layers=0 if use_cpu else -1,
                    )
                    _llm._backend = "llama_cpp"
        except Exception as e:
            print(f"Failed to load LLM: {e}")
            raise
    return _llm


def score_to_vertical_score(vertical: str, result: Dict[str, Any]) -> Tuple[float, Dict[str, float]]:
    """
    Calculate vertical-specific score from LLM output.
    """
    pillar_scores = {}
    
    def to_float(val: Any) -> float:
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, dict):
            # If it's a dict, maybe the score is inside?
            for k in ["score", "rating", "value"]:
                if k in val: return to_float(val[k])
            # Or count 'Yes' vs 'No' if it contains those
            yes_count = sum(1 for v in val.values() if str(v).lower() in ("yes", "good", "passed"))
            no_count = sum(1 for v in val.values() if str(v).lower() in ("no", "bad", "failed"))
            if yes_count + no_count > 0:
                return (yes_count / (yes_count + no_count)) * 100
            return 0.0
        if isinstance(val, str):
            val_clean = val.lower().strip()
            if val_clean in ("yes", "good", "passed", "true"): return 100.0
            if val_clean in ("no", "bad", "failed", "false", "n/a"): return 0.0
            # Try to extract first number
            import re
            match = re.search(r'(\d+(?:\.\d+)?)', val)
            if match: return float(match.group(1))
        return 0.0

    if vertical == "Sales":
        pillar_scores = {
            "CQS": to_float(result.get("cqs_score", result.get("conversation_quality", 0))),
            "ECS": to_float(result.get("ecs_score", result.get("execution_cadence", 0))),
            "PHS": to_float(result.get("phs_score", result.get("pipeline_health", 0))),
            "DIS": to_float(result.get("dis_score", result.get("deal_intelligence", 0))),
            "ROS": to_float(result.get("ros_score", result.get("revenue_outcome", 0)))
        }
        weights = {"CQS": 0.25, "ECS": 0.25, "PHS": 0.20, "DIS": 0.15, "ROS": 0.15}
        
    elif vertical == "Support":
        pillar_scores = {
            "FCR": to_float(result.get("fcr_score", result.get("first_contact_resolution", 0))),
            "EMP": to_float(result.get("emp_score", result.get("empathy", 0))),
            "EFF": to_float(result.get("eff_score", result.get("efficiency", 0))),
            "SAT": to_float(result.get("sat_score", result.get("satisfaction", 0))),
            "PRK": to_float(result.get("prk_score", result.get("product_knowledge", 0)))
        }
        weights = {"FCR": 0.30, "EMP": 0.25, "EFF": 0.20, "SAT": 0.15, "PRK": 0.10}
        
    elif vertical == "Collections":
        pillar_scores = {
            "CMP": to_float(result.get("cmp_score", result.get("compliance", 0))),
            "NEG": to_float(result.get("neg_score", result.get("negotiation", result.get("negotiation_skill", 0)))),
            "PTP": to_float(result.get("ptp_score", result.get("promise_to_pay", result.get("promise_quality", 0)))),
            "AMT": to_float(result.get("amt_score", result.get("amount_recovered", 0)))
        }
        weights = {"CMP": 0.40, "NEG": 0.25, "PTP": 0.20, "AMT": 0.15}
    else:
        weights = {}
    
    # Calculate weighted score
    overall = sum(pillar_scores.get(k, 0) * weights.get(k, 0) for k in weights.keys())
    
    # Final fallback if overall is 0 but result has an overall_score field
    if overall == 0 and "overall_score" in result:
        overall = to_float(result["overall_score"])
    
    # Ensure 0-100 range
    overall = max(0, min(100, overall))
    pillar_scores = {k: max(0, min(100, v)) for k, v in pillar_scores.items()}
    
    return overall, pillar_scores


SCORE_SOFT_TIME_LIMIT = 15 * 60
SCORE_TIME_LIMIT = 20 * 60

@celery_app.task(bind=True, max_retries=3, soft_time_limit=SCORE_SOFT_TIME_LIMIT, time_limit=SCORE_TIME_LIMIT)
def run_llm_scoring_task(self, previous_result: Tuple[int, str, str], call_id: int, work_dir: str, template_id: int):
    """
    Score transcript using local LLM.
    
    Args:
        previous_result: Tuple of (call_id, transcript_text, _) from transcription
    """
    _, transcript_text, _ = previous_result
    job_id = None
    start_time = datetime.utcnow()
    print(f"[scoring] call_id={call_id} starting LLM scoring (transcript len={len(transcript_text)})")
    try:
        with get_db_context() as db:
            job = ProcessingJob(
                call_id=call_id,
                stage="scoring",
                status="in_progress",
                celery_task_id=self.request.id,
                started_at=start_time
            )
            db.add(job)
            db.commit()
            job_id = job.job_id
            
            template = db.query(ScoringTemplate).filter(
                ScoringTemplate.template_id == template_id
            ).first()
            if not template:
                raise ValueError(f"Template {template_id} not found")
            system_prompt = template.system_prompt
            user_prompt_template = template.user_prompt_template
            template_vertical = template.vertical
            template_version = template.version

        max_chars = getattr(settings, "TRANSCRIPT_MAX_CHARS", 12000)
        if len(transcript_text) > max_chars:
            transcript_text = transcript_text[:max_chars] + "\n\n[Transcript truncated for length.]"
        user_prompt = user_prompt_template.replace("{transcript}", transcript_text)
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        max_tokens = (
            getattr(settings, "LLM_MAX_TOKENS_CPU", 768)
            if _use_cpu_llm()
            else settings.LLM_MAX_TOKENS
        )
        max_tokens = min(max_tokens, settings.LLM_MAX_TOKENS)
        print(f"[scoring] call_id={call_id} loading LLM (max_tokens={max_tokens})...")
        llm = get_llm()
        print(f"[scoring] call_id={call_id} LLM ready, generating...")
        if llm._backend == "vllm":
            from vllm import SamplingParams
            sampling_params = SamplingParams(
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=max_tokens,
                top_p=settings.LLM_TOP_P
            )
            outputs = llm.generate(
                prompt=messages,
                sampling_params=sampling_params
            )
            response_text = outputs[0].outputs[0].text
        else:
            response = llm.create_chat_completion(
                messages=messages,
                temperature=settings.LLM_TEMPERATURE,
                max_tokens=max_tokens,
                top_p=settings.LLM_TOP_P
            )
            response_text = response["choices"][0]["message"]["content"]
        print(f"[scoring] call_id={call_id} LLM response received ({len(response_text)} chars)")
        # Clean response text from markdown blocks if present
        cleaned_response = response_text.strip()
        if cleaned_response.startswith("```"):
            # Remove ```json or ``` at beginning
            import re
            cleaned_response = re.sub(r'^```(?:json)?\s*', '', cleaned_response)
            # Remove ``` at end
            cleaned_response = re.sub(r'\s*```$', '', cleaned_response)
        
        try:
            result = json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            # Try more aggressive regex extraction and bracket closing
            import re
            
            # Step 1: Extract JSON portion - handle leading text
            first_brace = cleaned_response.find('{')
            if first_brace != -1:
                json_str = cleaned_response[first_brace:]
                # Check for trailing junk after the last brace
                last_brace = json_str.rfind('}')
                if last_brace != -1:
                    json_str = json_str[:last_brace+1]
            else:
                json_str = cleaned_response
            
            # Step 2: Auto-close truncated JSON
            open_braces = json_str.count('{')
            close_braces = json_str.count('}')
            
            if open_braces > close_braces:
                # Truncate to the last successful comma, brace, or bracket to be safer
                last_safe = max(json_str.rfind(','), json_str.rfind('{'), json_str.rfind('['))
                if last_safe != -1:
                    if json_str[last_safe] == ',':
                        json_str = json_str[:last_safe]
                    else:
                        json_str = json_str[:last_safe+1]
                
                # Re-count and close
                open_braces = json_str.count('{')
                close_braces = json_str.count('}')
                json_str += '}' * (open_braces - close_braces)
            
            # Step 3: Cleanup common LLM artifacts within the JSON
            # Remove trailing commas
            json_str = re.sub(r',\s*([\]\}])', r'\1', json_str)
            # Remove inline commentary like "Value" (comment)
            json_str = re.sub(r':\s*("[^"]*")\s*\([^)]*\)', r': \1', json_str)
            json_str = re.sub(r':\s*([^,"\s}]+)\s*\([^)]*\)', r': \1', json_str)
            # Fix unquoted values like N/A
            json_str = re.sub(r':\s*N/A\b', r': "N/A"', json_str)
            
            try:
                result = json.loads(json_str)
            except json.JSONDecodeError:
                # Step 4: Final partial recovery via direct regex extraction
                print(f"[scoring] call_id={call_id} WARNING: JSON still malformed, attempting partial recovery.")
                result = {}
                # Extract some common fields if they exist
                for field in ["overall_score", "summary", "sentiment_score", "agent_summary"]:
                    match = re.search(f'"{field}"\\s*:\\s*([^,\\s}}]+)', json_str)
                    if match:
                        val = match.group(1).strip('"').split("(")[0].strip()
                        try:
                            result[field] = float(val) if "score" in field else val
                        except: result[field] = val
                
                if not result:
                    print(f"[scoring] call_id={call_id} ERROR: Malformed JSON after all recovery attempts: {json_str}")
                    print(f"[scoring] call_id={call_id} ERROR: Full response: {response_text}")
                    raise
        
        overall_score, pillar_scores = score_to_vertical_score(template_vertical, result)
        compliance_flags = result.get("compliance_flags", {})
        fatal_flaw = result.get("compliance_violation", False) or result.get("fatal_flaw", False)
        fatal_flaw_type = result.get("fatal_flaw_type") if fatal_flaw else None
        if template_vertical == "Collections" and fatal_flaw:
            overall_score = 0
        
        # Calculate processing duration
        duration = (datetime.utcnow() - start_time).total_seconds()
        
        # Save to database
        with get_db_context() as db:
            # Create evaluation result
            evaluation = EvaluationResult(
                call_id=call_id,
                overall_score=overall_score,
                ses_score=result.get("ses_score") if template_vertical == "Sales" else None,
                sqs_score=result.get("sqs_score") if template_vertical == "Support" else None,
                res_score=result.get("res_score") if template_vertical == "Collections" else None,
                pillar_scores=pillar_scores,
                compliance_flags=compliance_flags,
                fatal_flaw_detected=fatal_flaw,
                fatal_flaw_type=fatal_flaw_type,
                summary=result.get("summary", result.get("agent_summary", "")),
                recommendations=result.get("recommendations", []),
                sentiment_score=result.get("sentiment_score"),
                full_json_output=result,
                prompt_version=template_version,
                model_used=settings.LLM_MODEL_NAME,
                processing_duration_seconds=int(duration)
            )
            db.add(evaluation)
            
            # Update call status
            call = db.query(Call).filter(Call.call_id == call_id).first()
            if call:
                call.status = "completed"
                call.processing_completed_at = datetime.utcnow()
            
            # Update job status
            job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
            if job:
                job.status = "completed"
                job.finished_at = datetime.utcnow()
                job.extra_metadata = {
                    "overall_score": overall_score,
                    "processing_duration_seconds": duration
                }
            
            db.commit()
        
        # Cleanup work directory
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        
        return {
            "call_id": call_id,
            "status": "completed",
            "overall_score": overall_score,
            "processing_duration_seconds": duration
        }
        
    except SoftTimeLimitExceeded:
        error_msg = "Scoring timed out (15 min limit). Try shorter audio or faster hardware."
        give_up = self.request.retries >= self.max_retries
        with get_db_context() as db:
            job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
            if job:
                job.status = "failed"
                job.finished_at = datetime.utcnow()
                job.error_message = error_msg
            if give_up:
                call = db.query(Call).filter(Call.call_id == call_id).first()
                if call:
                    call.status = "failed"
                    call.error_message = error_msg
            db.commit()
        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        if give_up:
            raise
        raise self.retry(countdown=60)
    except Exception as exc:
        error_msg = str(exc)
        give_up = self.request.retries >= self.max_retries

        with get_db_context() as db:
            job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
            if job:
                job.status = "failed"
                job.finished_at = datetime.utcnow()
                job.error_message = error_msg
            if give_up:
                call = db.query(Call).filter(Call.call_id == call_id).first()
                if call:
                    call.status = "failed"
                    call.error_message = error_msg
            db.commit()

        if os.path.exists(work_dir):
            shutil.rmtree(work_dir)
        if give_up:
            raise
        raise (self.retry(exc=exc, countdown=30) if exc else self.retry(countdown=30))
