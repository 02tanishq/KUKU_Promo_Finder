"""
Swappable LLM Evaluator & Ranking Pipeline for Microdrama Promos.
Supports:
- Groq Cloud (LPU: llama-3.3-70b-versatile, llama-3.1-8b-instant) [keys starting with gsk_]
- xAI Grok (grok-2-latest, grok-beta) [keys starting with xai-]
- Google Gemini (gemini-2.0-flash, gemini-1.5-pro)
- OpenAI (gpt-4o, gpt-4o-mini)
- Local / Rule-Based Heuristic Fallback (Runs without API keys, zero cost)

Robust Error Handling:
- Intercepts rate limits, 429s, quota errors cleanly without raw tracebacks.
- Outputs graceful notice: "LLM rate limit / quota exceeded. Please retry after [wait_time] or contact candidate. Falling back to Rule-Based Heuristic Evaluation."
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path so direct file execution works from anywhere
_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

import json
import re
import urllib.request
import urllib.error
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, asdict
from promo_engine.rules import CandidatePromo, seconds_to_timestamp


@dataclass
class RankedPromo:
    rank: int
    promo_id: str
    promo_type: str
    funnel_stage: str
    archetype: str
    header_hook: str
    episodes_involved: List[int]
    segments: List[Dict[str, Any]]
    total_duration_sec: float
    hook_summary: str
    cliffhanger_summary: str
    why_it_works: str
    virality_score: float
    hook_score: float
    cliffhanger_score: float
    cold_comprehension_score: float
    evaluator_source: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def load_env_file():
    """Reads .env file from project root if it exists and loads into os.environ."""
    env_paths = [
        os.path.join(_root_dir, ".env"),
        ".env"
    ]
    for env_path in env_paths:
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            key, val = line.split("=", 1)
                            key = key.strip()
                            val = val.strip().strip('"').strip("'")
                            if key and val and not val.startswith("xai-your-api-key"):
                                os.environ[key] = val
            except Exception:
                pass


load_env_file()


class LLMEvaluator:
    """Evaluates candidate promos using Groq, xAI Grok, Gemini, OpenAI, or robust heuristic fallback."""

    def __init__(self, model_name: str = "default", api_key: Optional[str] = None):
        load_env_file()

        # Find API key from parameter or environment
        self.api_key = (
            api_key
            or os.environ.get("GROQ_API_KEY")
            or os.environ.get("GROK_API_KEY")
            or os.environ.get("XAI_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
        )

        # Smart Provider Detection based on Key Prefix and Model Name
        if self.api_key and self.api_key.startswith("gsk_"):
            # Groq Cloud API Key
            self.provider = "groq"
            self.model_name = "auto" if model_name in ("default", "heuristic", "grok-2-latest", "llama-3.3-70b-versatile") else model_name
        elif self.api_key and self.api_key.startswith("xai-"):
            # xAI Grok API Key
            self.provider = "xai"
            self.model_name = "grok-2-latest" if model_name in ("default", "heuristic") else model_name
        elif self.api_key and self.api_key.startswith("AIza"):
            # Google Gemini Key
            self.provider = "gemini"
            self.model_name = "gemini-2.0-flash" if model_name in ("default", "heuristic") else model_name
        elif self.api_key and self.api_key.startswith("sk-"):
            # OpenAI Key
            self.provider = "openai"
            self.model_name = "gpt-4o" if model_name in ("default", "heuristic") else model_name
        else:
            self.provider = "heuristic"
            self.model_name = model_name

        self.contact_info = os.environ.get("CANDIDATE_CONTACT", "Tanishqg503@gmail.com / +91-7878675557")

    def _get_groq_model(self) -> str:
        """Dynamically picks the best available high-performance LLM on the Groq account."""
        if self.model_name not in ("auto", "default", "heuristic", "llama-3.3-70b-versatile"):
            return self.model_name
        try:
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {self.api_key}", "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ids = [m["id"] for m in data.get("data", [])]
                for preferred in ["openai/gpt-oss-120b", "llama-3.3-70b-versatile", "qwen/qwen3.8-27b", "openai/gpt-oss-20b", "llama-3.1-8b-instant"]:
                    if preferred in ids:
                        return preferred
        except Exception:
            pass
        return "openai/gpt-oss-120b"

    def evaluate_candidates(self, candidates: List[CandidatePromo], episode_logline: str = "", max_llm_eval: int = 10) -> List[RankedPromo]:
        """Evaluates a batch of candidate promos for an episode or whole show."""
        if not candidates:
            return []

        # If no API key or explicitly heuristic mode, run fast heuristic evaluator
        if not self.api_key or self.model_name.lower() in ("heuristic", "rule-based", "none"):
            return self._heuristic_evaluation(candidates, episode_logline)

        # Token-safe Two-Stage Funnel:
        # If candidates are few (<= max_llm_eval, e.g. single episode or small batch), evaluate all with LLM.
        # If candidates are many (e.g. 142 from 50 episodes), evaluate top max_llm_eval with LLM to prevent
        # burning through free API rate limits / token quotas, and score remainder via fast heuristic engine.
        if len(candidates) <= max_llm_eval:
            llm_candidates = candidates
            heuristic_candidates = []
        else:
            # Stitched promos always get LLM evaluation priority
            stitched = [c for c in candidates if c.promo_type == "stitched_multi_segment"]
            continuous = [c for c in candidates if c.promo_type != "stitched_multi_segment"]
            continuous.sort(key=lambda c: c.composite_heuristic_score, reverse=True)
            
            slots_for_continuous = max(0, max_llm_eval - len(stitched))
            llm_candidates = stitched + continuous[:slots_for_continuous]
            heuristic_candidates = continuous[slots_for_continuous:]

        results: List[RankedPromo] = []
        batch_size = 5
        for i in range(0, len(llm_candidates), batch_size):
            chunk = llm_candidates[i:i + batch_size]
            try:
                chunk_results = self._evaluate_batch_with_llm(chunk, episode_logline)
                results.extend(chunk_results)
            except urllib.error.HTTPError as e:
                if e.code in (429, 403, 503):
                    print(f"\n[NOTICE]: LLM rate limit or quota exceeded ({e.code}). Please retry after a brief wait or contact candidate at [{self.contact_info}].")
                    print("[NOTICE]: Gracefully falling back to Rule-Based Heuristic Evaluation to complete execution without failure.\n")
                else:
                    print(f"\n[NOTICE]: LLM service returned status {e.code}. Falling back to Rule-Based Heuristic Evaluation.")
                results.extend(self._heuristic_evaluation(chunk, episode_logline))
            except Exception as e:
                print(f"\n[NOTICE]: External LLM connection paused: {type(e).__name__}. Falling back to Rule-Based Heuristic Evaluation.")
                results.extend(self._heuristic_evaluation(chunk, episode_logline))

        if heuristic_candidates:
            results.extend(self._heuristic_evaluation(heuristic_candidates, episode_logline))

        return results

    def _evaluate_batch_with_llm(self, candidates: List[CandidatePromo], episode_logline: str) -> List[RankedPromo]:
        """Routes a single chunk to the active provider API."""
        if self.provider == "groq" or (self.api_key and self.api_key.startswith("gsk_")):
            return self._call_groq_cloud_api(candidates, episode_logline)
        elif self.provider == "xai" or "grok" in self.model_name.lower():
            return self._call_xai_grok_api(candidates, episode_logline)
        elif self.provider == "gemini" or "gemini" in self.model_name.lower():
            return self._call_gemini_api(candidates, episode_logline)
        elif self.provider == "openai" or "gpt" in self.model_name.lower():
            return self._call_openai_api(candidates, episode_logline)
        else:
            return self._heuristic_evaluation(candidates, episode_logline)

    def _call_groq_cloud_api(self, candidates: List[CandidatePromo], logline: str) -> List[RankedPromo]:
        """Calls Groq Cloud API (https://api.groq.com/openai/v1/chat/completions) using ultra-fast LPU inference."""
        prompt = self._build_prompt(candidates, logline)
        url = "https://api.groq.com/openai/v1/chat/completions"
        
        model = self._get_groq_model()
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are the Lead Creative Director for ReelShort and DramaBox US Marketing. Return strictly valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_text = data["choices"][0]["message"]["content"]
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            parsed_json = json.loads(cleaned)
            return self._parse_llm_json_response(parsed_json, candidates, f"llm_groq_{model}")

    def _call_xai_grok_api(self, candidates: List[CandidatePromo], logline: str) -> List[RankedPromo]:
        """Calls xAI Grok REST API (https://api.x.ai/v1/chat/completions)."""
        prompt = self._build_prompt(candidates, logline)
        url = "https://api.x.ai/v1/chat/completions"
        model = self.model_name if "grok" in self.model_name.lower() else "grok-2-latest"
        
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are the Lead Creative Director for ReelShort and DramaBox US Marketing. Return strictly valid JSON."
                },
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )
        
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_text = data["choices"][0]["message"]["content"]
            cleaned = re.sub(r"^```(?:json)?\s*", "", raw_text.strip(), flags=re.IGNORECASE)
            cleaned = re.sub(r"\s*```$", "", cleaned)
            parsed_json = json.loads(cleaned)
            return self._parse_llm_json_response(parsed_json, candidates, f"llm_xai_{model}")

    def _call_gemini_api(self, candidates: List[CandidatePromo], logline: str) -> List[RankedPromo]:
        prompt = self._build_prompt(candidates, logline)
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:generateContent?key={self.api_key}"
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature": 0.2,
                "responseMimeType": "application/json"
            }
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed_json = json.loads(raw_text)
            return self._parse_llm_json_response(parsed_json, candidates, "llm_gemini")

    def _call_openai_api(self, candidates: List[CandidatePromo], logline: str) -> List[RankedPromo]:
        prompt = self._build_prompt(candidates, logline)
        url = "https://api.openai.com/v1/chat/completions"
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": "You are an expert US microdrama marketing editor for ReelShort and DramaBox."},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2,
            "response_format": {"type": "json_object"}
        }
        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
            }
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            raw_text = data["choices"][0]["message"]["content"]
            parsed_json = json.loads(raw_text)
            return self._parse_llm_json_response(parsed_json, candidates, "llm_openai")

    def _build_prompt(self, candidates: List[CandidatePromo], logline: str) -> str:
        cand_summaries = []
        for i, c in enumerate(candidates):
            transcript_snippet = c.segments[0].transcript_text[:600]
            cand_summaries.append(f"""
Candidate #{i+1} [ID: {c.candidate_id}]:
Duration: {c.total_duration_sec}s ({c.segments[0].start_str} - {c.segments[0].end_str})
Suggested Archetype: {c.suggested_archetype}
Transcript:
{transcript_snippet}
""")

        return f"""
You are the Lead Creative Director for ReelShort / DramaBox US Marketing.
Evaluate these candidate promo clips from Episode logline: "{logline}".

For each candidate, analyze:
1. Hook (first 3s): Does it immediately stop a scrolling finger with shock, outrage, or taboo conflict?
2. Cliffhanger (last 3s): Does it cut at the exact unresolved tension peak?
3. Cold Comprehensibility: Does it make 100% sense to someone who has never heard of this show?
4. Generate a 2-3 word bold uppercase On-Screen Text Header (e.g. 'WHO DID THIS?', 'STOP THE WEDDING', 'YOUR GRACE', 'NEVER MY DUCHESS').
5. Assign Funnel Stage:
   - 'Stage 1: Top-of-Funnel (Post First)' for opening inciting incidents requiring 0 backstory
   - 'Stage 2: Mid-Funnel (Post Second)' for relationship dynamic & protector conflict
   - 'Stage 3: Paywall Teaser (Post Third)' for major identity reveals & climax rescues
6. One-line "Why It Works" explaining why this converts US TikTok/Reels scrollers.
7. Virality score between 1.0 and 10.0.

Return JSON in this exact structure:
{{
  "promos": [
    {{
      "candidate_id": "string",
      "header_hook": "2-3 WORDS UPPERCASE",
      "funnel_stage": "Stage 1: Top-of-Funnel (Post First) | Stage 2: Mid-Funnel (Post Second) | Stage 3: Paywall Teaser (Post Third)",
      "archetype": "string",
      "hook_summary": "1-2 sentences on the opening 3-second hook",
      "cliffhanger_summary": "1-2 sentences on the cut point",
      "why_it_works": "Single punchy sentence",
      "hook_score": 8.5,
      "cliffhanger_score": 9.0,
      "cold_comprehension_score": 9.2,
      "virality_score": 9.0
    }}
  ]
}}
Candidates to evaluate:
{"".join(cand_summaries)}
"""

    def _parse_llm_json_response(self, parsed_json: Dict[str, Any], candidates: List[CandidatePromo], source: str) -> List[RankedPromo]:
        cand_map = {c.candidate_id: c for c in candidates}
        results = []
        
        items = parsed_json.get("promos", [])
        if isinstance(parsed_json, list):
            items = parsed_json
            
        for item in items:
            cid = item.get("candidate_id")
            cand = cand_map.get(cid)
            if not cand:
                continue

            seg_dicts = [
                {
                    "episode": s.episode,
                    "start_time": s.start_str,
                    "end_time": s.end_str,
                    "duration_seconds": s.duration_sec
                }
                for s in cand.segments
            ]

            results.append(RankedPromo(
                rank=0,
                promo_id=cand.candidate_id,
                promo_type=cand.promo_type,
                funnel_stage=item.get("funnel_stage", self._infer_funnel_stage(cand.episodes[0])),
                archetype=item.get("archetype", cand.suggested_archetype),
                header_hook=item.get("header_hook", self._generate_header_hook(cand.suggested_archetype)),
                episodes_involved=cand.episodes,
                segments=seg_dicts,
                total_duration_sec=cand.total_duration_sec,
                hook_summary=item.get("hook_summary", cand.hook_text),
                cliffhanger_summary=item.get("cliffhanger_summary", cand.cliffhanger_text),
                why_it_works=item.get("why_it_works", "High emotional contrast and unresolved tension designed for US short-form feeds."),
                virality_score=float(item.get("virality_score", cand.composite_heuristic_score)),
                hook_score=float(item.get("hook_score", cand.hook_score)),
                cliffhanger_score=float(item.get("cliffhanger_score", cand.cliffhanger_score)),
                cold_comprehension_score=float(item.get("cold_comprehension_score", 8.0)),
                evaluator_source=source
            ))

        return results if results else self._heuristic_evaluation(candidates, "")

    def _heuristic_evaluation(self, candidates: List[CandidatePromo], logline: str) -> List[RankedPromo]:
        """Instant, 100% deterministic heuristic evaluator based on ReelShort empirical data."""
        results = []
        for cand in candidates:
            ep = cand.episodes[0]
            funnel = self._infer_funnel_stage(ep)
            header = self._generate_header_hook(cand.suggested_archetype)
            
            if ep <= 4:
                cold_score = 9.5
            elif ep <= 15:
                cold_score = 8.5
            elif ep <= 35:
                cold_score = 7.0
            else:
                cold_score = 7.8

            virality = round(min(9.8, max(6.0, cand.composite_heuristic_score + (1.2 if ep <= 3 else 0.5))), 1)
            why = self._generate_why_it_works(cand.suggested_archetype, ep)

            seg_dicts = [
                {
                    "episode": s.episode,
                    "start_time": s.start_str,
                    "end_time": s.end_str,
                    "duration_seconds": s.duration_sec
                }
                for s in cand.segments
            ]

            results.append(RankedPromo(
                rank=0,
                promo_id=cand.candidate_id,
                promo_type=cand.promo_type,
                funnel_stage=funnel,
                archetype=cand.suggested_archetype,
                header_hook=header,
                episodes_involved=cand.episodes,
                segments=seg_dicts,
                total_duration_sec=cand.total_duration_sec,
                hook_summary=f"Opens on instant high emotion: {cand.hook_text[:120]}",
                cliffhanger_summary=f"Snaps at peak unresolved tension: {cand.cliffhanger_text[:120]}",
                why_it_works=why,
                virality_score=virality,
                hook_score=cand.hook_score,
                cliffhanger_score=cand.cliffhanger_score,
                cold_comprehension_score=cold_score,
                evaluator_source="heuristic_engine"
            ))

        return results

    def _infer_funnel_stage(self, episode_num: int) -> str:
        if episode_num <= 4:
            return "Stage 1: Top-of-Funnel (Post First - Cold UA)"
        elif episode_num <= 20:
            return "Stage 2: Mid-Funnel (Post Second - Re-engagement)"
        else:
            return "Stage 3: Paywall Teaser (Post Third - Payoff)"

    def _generate_header_hook(self, archetype: str) -> str:
        arch_lower = archetype.lower()
        if "altar" in arch_lower or "betrayal" in arch_lower:
            return "HER OWN SISTER?"
        elif "proposal" in arch_lower or "claim" in arch_lower:
            return "A STRANGER PROPOSED"
        elif "retribution" in arch_lower or "wounds" in arch_lower:
            return "WHO DID THIS?"
        elif "inversion" in arch_lower or "duke" in arch_lower:
            return "YOUR GRACE"
        elif "scaffold" in arch_lower or "execution" in arch_lower or "witch" in arch_lower:
            return "ENDS HERE!"
        return "NO MORE HIDING"

    def _generate_why_it_works(self, archetype: str, episode_num: int) -> str:
        if episode_num <= 4:
            return "Primal rage-bait and public wedding humiliation that requires 0 seconds of backstory for cold US viewers."
        elif "retribution" in archetype.lower():
            return "Protective alpha male rage taps directly into the highly popular protector romance trope on TikTok."
        elif "inversion" in archetype.lower():
            return "Pure status-inversion dopamine payoff: the arrogant bullies realize the man they mocked is the Duke."
        elif "scaffold" in archetype.lower() or "climax" in archetype.lower():
            return "Extreme life-or-death urgency cut right before the execution block drops, forcing viewers to click to find out."
        return "Monotonically escalating conflict with rapid dialogue pacing that prevents scrolling drop-off."


if __name__ == "__main__":
    print("\n--- LLMEvaluator Self-Test ---")
    evaluator = LLMEvaluator()
    print(f"Active Provider: {evaluator.provider.upper()}")
    print(f"Active Model: {evaluator.model_name}")
    print(f"API Key Found: {'Yes (' + evaluator.api_key[:8] + '...)' if evaluator.api_key else 'No (Running in Heuristic Fallback mode)'}")
    print(f"Candidate Contact: {evaluator.contact_info}")
    print("Initialization verified successfully!\n")
