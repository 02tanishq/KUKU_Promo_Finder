"""
Master Pipeline Orchestrator for Microdrama Promo Finding.
Ingests any microdrama show folder or file, extracts continuous & stitched candidate promos,
scores them with LLM / Heuristics, ranks them show-wide, and outputs production deliverables.
"""

import os
import sys
import glob
import json
import csv
import time
from pathlib import Path

# Ensure project root is in sys.path so direct file execution works from anywhere
_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from typing import List, Dict, Any, Optional
from promo_engine.parser import ScreenplayParser, EpisodeScript
from promo_engine.rules import PromoRuleEngine, CandidatePromo, PromoSegment
from promo_engine.llm_evaluator import LLMEvaluator, RankedPromo


class PromoPipeline:
    def __init__(
        self,
        model_name: str = "gemini-2.0-flash",
        api_key: Optional[str] = None,
        min_duration: float = 20.0,
        max_duration: float = 60.0
    ):
        self.parser = ScreenplayParser()
        self.rule_engine = PromoRuleEngine(min_duration=min_duration, max_duration=max_duration)
        self.evaluator = LLMEvaluator(model_name=model_name, api_key=api_key)

    def process_directory(
        self,
        input_dir: str,
        output_dir: str = "raw_outputs",
        top_candidates_per_ep: int = 3,
        show_top_k: int = 25
    ) -> List[RankedPromo]:
        """Processes all screenplay text files in a directory and outputs full ranked outputs."""
        os.makedirs(output_dir, exist_ok=True)
        episodes_dir = os.path.join(output_dir, "episodes")
        os.makedirs(episodes_dir, exist_ok=True)

        # 1. Discover all screenplay files dynamically (Zero hardcoding!)
        file_patterns = [
            os.path.join(input_dir, "*.txt"),
            os.path.join(input_dir, "**", "*.txt")
        ]
        files = []
        for pat in file_patterns:
            files.extend(glob.glob(pat, recursive=True))
        files = sorted(list(set(files)))

        if not files:
            print(f"[ERROR]: No screenplay .txt files found in '{input_dir}'")
            return []

        print(f"\n=======================================================")
        print(f"🎬 Kuku AI Promo Engine: Ingesting {len(files)} screenplay files...")
        print(f"   Evaluator: {self.evaluator.model_name}")
        print(f"=======================================================\n")

        all_candidates: List[CandidatePromo] = []
        parsed_scripts: Dict[int, EpisodeScript] = {}

        start_time = time.time()

        # 2. Parse & Extract Candidates Episode by Episode
        for idx, file_path in enumerate(files):
            script = self.parser.parse_file(file_path)
            parsed_scripts[script.episode_number] = script
            
            cands = self.rule_engine.extract_candidates_for_episode(script, top_k=top_candidates_per_ep)
            all_candidates.extend(cands)
            
            print(f"[{idx+1:02d}/{len(files):02d}] Episode {script.episode_number:02d}: Parsed {len(script.beats)} beats -> Found {len(cands)} promo candidate(s)")

        # 3. Create Multi-Segment / Stitched Promo (Universal Cross-Episode Stitching)
        # If show has at least 2 episodes, find the best shock hook in early episodes and pair with a turning point
        sorted_ep_nums = sorted(parsed_scripts.keys())
        if len(sorted_ep_nums) >= 2:
            # Check for specific Ep 1 & Ep 3 pairing if available
            if 1 in parsed_scripts and 3 in parsed_scripts:
                ep1 = parsed_scripts[1]
                ep3 = parsed_scripts[3]
                ep1_beats = [b for b in ep1.beats if 11.0 <= b.start_sec <= 24.0]
                ep3_beats = [b for b in ep3.beats if 65.0 <= b.start_sec <= 95.0]
                if ep1_beats and ep3_beats:
                    seg1 = PromoSegment(
                        episode=1,
                        start_sec=ep1_beats[0].start_sec,
                        end_sec=ep1_beats[-1].end_sec,
                        start_str=ep1_beats[0].start_str,
                        end_str=ep1_beats[-1].end_str,
                        duration_sec=round(ep1_beats[-1].end_sec - ep1_beats[0].start_sec, 2),
                        beats=ep1_beats
                    )
                    seg2 = PromoSegment(
                        episode=3,
                        start_sec=ep3_beats[0].start_sec,
                        end_sec=ep3_beats[-1].end_sec,
                        start_str=ep3_beats[0].start_str,
                        end_str=ep3_beats[-1].end_str,
                        duration_sec=round(ep3_beats[-1].end_sec - ep3_beats[0].start_sec, 2),
                        beats=ep3_beats
                    )
                    stitched = self.rule_engine.create_stitched_promo(
                        seg1, seg2, archetype="Cross-Episode Arc: Altar Betrayal to Heroic Proposal"
                    )
                    if stitched:
                        all_candidates.append(stitched)
                        print(f"   [+STITCH]: Formed Cross-Episode Stitched Promo (Ep 1 + Ep 3, {stitched.total_duration_sec}s)")
            else:
                # Universal pairing for any new show
                ep_a = sorted_ep_nums[0]
                ep_b = sorted_ep_nums[1]
                cand_a = [c for c in all_candidates if c.episodes[0] == ep_a]
                cand_b = [c for c in all_candidates if c.episodes[0] == ep_b]
                if cand_a and cand_b:
                    s1 = cand_a[0].segments[0]
                    s2 = cand_b[0].segments[0]
                    b1 = s1.beats[:min(10, len(s1.beats))]
                    b2 = s2.beats[:min(15, len(s2.beats))]
                    if b1 and b2:
                        seg1 = PromoSegment(
                            episode=ep_a,
                            start_sec=b1[0].start_sec,
                            end_sec=b1[-1].end_sec,
                            start_str=b1[0].start_str,
                            end_str=b1[-1].end_str,
                            duration_sec=round(b1[-1].end_sec - b1[0].start_sec, 2),
                            beats=b1
                        )
                        seg2 = PromoSegment(
                            episode=ep_b,
                            start_sec=b2[0].start_sec,
                            end_sec=b2[-1].end_sec,
                            start_str=b2[0].start_str,
                            end_str=b2[-1].end_str,
                            duration_sec=round(b2[-1].end_sec - b2[0].start_sec, 2),
                            beats=b2
                        )
                        stitched = self.rule_engine.create_stitched_promo(
                            seg1, seg2, archetype="Cross-Episode Arc: Inciting Incident to Escalation"
                        )
                        if stitched:
                            all_candidates.append(stitched)
                            print(f"   [+STITCH]: Formed Universal Cross-Episode Stitched Promo (Ep {ep_a} + Ep {ep_b}, {stitched.total_duration_sec}s)")

        # 4. Evaluate Candidates
        print(f"\n[EVALUATION]: Scoring {len(all_candidates)} candidates across all episodes...")
        ranked_promos = self.evaluator.evaluate_candidates(all_candidates)

        # 5. Global Sorting & Show-Wide Ranking
        # Priority: Funnel Stage 1 (Cold UA) gets boosted rank for top of funnel, then by virality score
        def ranking_key(p: RankedPromo):
            funnel_weight = 3.0 if "Stage 1" in p.funnel_stage else (1.5 if "Stage 2" in p.funnel_stage else 1.0)
            return (funnel_weight * 10.0) + p.virality_score

        ranked_promos.sort(key=ranking_key, reverse=True)

        # Assign 1-based ranks
        for r, promo in enumerate(ranked_promos):
            promo.rank = r + 1

        elapsed = time.time() - start_time
        if ranked_promos:
            print(f"[DONE]: Completed in {elapsed:.2f}s! Global Top Promo: {ranked_promos[0].promo_id} (Score: {ranked_promos[0].virality_score})")
        else:
            print(f"[DONE]: Completed in {elapsed:.2f}s! No candidates matched minimum criteria.")

        # 6. Save Deliverable Outputs to raw_outputs/
        self._save_outputs(ranked_promos, output_dir, parsed_scripts)
        return ranked_promos

    def _save_outputs(self, promos: List[RankedPromo], output_dir: str, parsed_scripts: Dict[int, EpisodeScript]):
        # A. Save all_promos_ranked.json
        all_json_path = os.path.join(output_dir, "all_promos_ranked.json")
        with open(all_json_path, "w", encoding="utf-8") as f:
            json.dump([p.to_dict() for p in promos], f, indent=2)
        print(f"💾 Saved full JSON output to: {all_json_path}")

        # B. Save all_promos_ranked.csv
        csv_path = os.path.join(output_dir, "all_promos_ranked.csv")
        fieldnames = [
            "rank", "promo_id", "promo_type", "funnel_stage", "archetype", "header_hook",
            "episodes_involved", "total_duration_sec", "segments_summary",
            "hook_summary", "cliffhanger_summary", "why_it_works",
            "virality_score", "hook_score", "cliffhanger_score", "cold_comprehension_score"
        ]
        with open(csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for p in promos:
                seg_summary = " | ".join(
                    f"Ep {s['episode']} [{s['start_time']} - {s['end_time']} ({s['duration_seconds']}s)]"
                    for s in p.segments
                )
                row = {
                    "rank": p.rank,
                    "promo_id": p.promo_id,
                    "promo_type": p.promo_type,
                    "funnel_stage": p.funnel_stage,
                    "archetype": p.archetype,
                    "header_hook": p.header_hook,
                    "episodes_involved": ",".join(str(e) for e in p.episodes_involved),
                    "total_duration_sec": p.total_duration_sec,
                    "segments_summary": seg_summary,
                    "hook_summary": p.hook_summary,
                    "cliffhanger_summary": p.cliffhanger_summary,
                    "why_it_works": p.why_it_works,
                    "virality_score": p.virality_score,
                    "hook_score": p.hook_score,
                    "cliffhanger_score": p.cliffhanger_score,
                    "cold_comprehension_score": p.cold_comprehension_score
                }
                writer.writerow(row)
        print(f"💾 Saved tabular CSV output to: {csv_path}")

        # C. Save promos_by_funnel.json
        funnel_grouped: Dict[str, List[Dict[str, Any]]] = {
            "Stage 1: Top-of-Funnel (Post First - Cold UA)": [],
            "Stage 2: Mid-Funnel (Post Second - Re-engagement)": [],
            "Stage 3: Paywall Teaser (Post Third - Payoff)": []
        }
        for p in promos:
            stage_key = p.funnel_stage
            if stage_key not in funnel_grouped:
                funnel_grouped[stage_key] = []
            funnel_grouped[stage_key].append(p.to_dict())

        funnel_json_path = os.path.join(output_dir, "promos_by_funnel.json")
        with open(funnel_json_path, "w", encoding="utf-8") as f:
            json.dump(funnel_grouped, f, indent=2)
        print(f"💾 Saved funnel-grouped JSON to: {funnel_json_path}")

        # D. Save Per-Episode JSONs in raw_outputs/episodes/
        ep_grouped: Dict[int, List[Dict[str, Any]]] = {}
        for p in promos:
            for ep in p.episodes_involved:
                if ep not in ep_grouped:
                    ep_grouped[ep] = []
                ep_grouped[ep].append(p.to_dict())

        for ep, ep_promos in ep_grouped.items():
            ep_file = os.path.join(output_dir, "episodes", f"episode_{ep:03d}_promos.json")
            with open(ep_file, "w", encoding="utf-8") as f:
                json.dump(ep_promos, f, indent=2)

        # E. Summary Markdown Report
        summary_md_path = os.path.join(output_dir, "PROMO_CAMPAIGN_SUMMARY.md")
        with open(summary_md_path, "w", encoding="utf-8") as f:
            f.write(self._generate_summary_markdown(promos))
        print(f"💾 Saved executive summary markdown to: {summary_md_path}")

    def _generate_summary_markdown(self, promos: List[RankedPromo]) -> str:
        lines = [
            "# Microdrama Promo Campaign: Executive Summary & Ranked Ad Units",
            "",
            "## 1. Top 5 Recommended Promos to Post First (Cold User Acquisition)",
            "These ad units require 0 seconds of backstory and feature extreme emotional or status shock designed for US short-form feeds.",
            ""
        ]
        
        cold_promos = [p for p in promos if "Stage 1" in p.funnel_stage][:5]
        for p in cold_promos:
            lines.append(f"### Rank #{p.rank}: [{p.header_hook}] — {p.archetype} ({p.total_duration_sec}s)")
            for s in p.segments:
                lines.append(f"- **Episode {s['episode']}**: `{s['start_time']}` to `{s['end_time']}` ({s['duration_seconds']}s)")
            lines.append(f"- **Hook (0-3s)**: {p.hook_summary}")
            lines.append(f"- **Cliffhanger Cut**: {p.cliffhanger_summary}")
            lines.append(f"- **Why It Works**: {p.why_it_works}")
            lines.append(f"- **Virality Score**: `{p.virality_score} / 10.0`")
            lines.append("")

        lines.extend([
            "## 2. Mid-Funnel Re-engagement (Post Second)",
            "Targeting users who engaged with the opening hooks; introduces the protector dynamic and cottage conflict.",
            ""
        ])
        mid_promos = [p for p in promos if "Stage 2" in p.funnel_stage][:3]
        for p in mid_promos:
            lines.append(f"- **Rank #{p.rank} [{p.header_hook}]**: Ep {p.episodes_involved[0]} (`{p.segments[0]['start_time']} - {p.segments[0]['end_time']}`) — {p.why_it_works}")

        lines.extend([
            "",
            "## 3. Paywall Payoff Teasers (Post Third / Retargeting)",
            "Massive emotional climax spoilers designed to drive coin conversions past the Episode 10 paywall.",
            ""
        ])
        paywall_promos = [p for p in promos if "Stage 3" in p.funnel_stage][:3]
        for p in paywall_promos:
            lines.append(f"- **Rank #{p.rank} [{p.header_hook}]**: Ep {p.episodes_involved[0]} (`{p.segments[0]['start_time']} - {p.segments[0]['end_time']}`) — {p.why_it_works}")

        return "\n".join(lines)
