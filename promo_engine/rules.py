"""
Heuristic Signal Extractor & Sliding Window Rules Engine for Microdrama Promos.
Implements ReelShort & DramaBox empirical research rules:
- 0-3s Hook detection (high-stakes violations, physical action, emotion polarity)
- 15-35s Escalation density & pacing
- Peak tension cliffhanger cutoffs (unresolved ultimatums/questions, holds)
- Strict 20s-60s windowing bounds with sentence-boundary snapping (never cuts mid-dialogue)
"""

import os
import sys
from pathlib import Path

# Ensure project root is in sys.path so direct file execution works from anywhere
_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

import re
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass, field
from promo_engine.parser import Beat, EpisodeScript, seconds_to_timestamp


# High-stakes lexicon derived from top ReelShort & DramaBox viral promos
HIGH_STAKES_WORDS = {
    # Relationship & Betrayal
    "marry", "marriage", "wedding", "altar", "groom", "bride", "fiancé", "fiance",
    "divorce", "sister", "betray", "betrayal", "cheating", "mistress", "wife", "husband",
    "gown", "dress", "ring", "veil",
    # Power & Inversion
    "duke", "duchess", "grace", "your grace", "lord", "lady", "beggar", "peasant",
    "nobody", "billionaire", "heir", "heiress", "disown", "disowned", "inherit", "inheritance",
    "money", "fortune", "debt", "house", "birthright", "title",
    # Physical Danger & Conflict
    "kill", "die", "death", "dead", "execution", "gallows", "block", "scaffold", "witch",
    "witchcraft", "poison", "arsenic", "blade", "sword", "blood", "wound", "bruise",
    "strike", "slap", "choke", "chains", "cell", "dungeon", "arrest", "hang", "hangs"
}

PHYSICAL_ACTION_VERBS = {
    "slap", "slaps", "strike", "strikes", "struck", "grab", "grabs", "grabbed",
    "seize", "seizes", "seized", "shove", "shoves", "tear", "tears", "ripped",
    "throw", "throws", "kneel", "kneels", "draws", "draw", "bleed", "bleeding",
    "collapse", "collapses", "weep", "weeps", "shaking", "trembling", "crying",
    "clutches", "intercepts", "blocks"
}

HIGH_VOLTAGE_TONES = {
    "cruel", "cold", "sneering", "callous", "furious", "outraged", "heartbroken",
    "desperate", "shocked", "terrified", "smug", "derisive", "arrogant", "merciless",
    "commanding", "whispering", "pleading", "unforgiving", "defiant", "steely"
}


@dataclass
class PromoSegment:
    episode: int
    start_sec: float
    end_sec: float
    start_str: str
    end_str: str
    duration_sec: float
    beats: List[Beat] = field(default_factory=list)

    @property
    def transcript_text(self) -> str:
        lines = []
        for b in self.beats:
            if b.beat_type == "dialogue":
                lines.append(f"{b.speaker} ({b.tone}): \"{b.text}\"")
            elif b.beat_type == "action":
                lines.append(f"[ACTION: {b.text}]")
        return "\n".join(lines)


@dataclass
class CandidatePromo:
    candidate_id: str
    promo_type: str  # 'single_segment' or 'stitched_segment'
    episodes: List[int]
    segments: List[PromoSegment]
    total_duration_sec: float
    hook_score: float
    escalation_score: float
    cliffhanger_score: float
    composite_heuristic_score: float
    hook_beat: Optional[Beat] = None
    cliffhanger_beat: Optional[Beat] = None
    hook_text: str = ""
    cliffhanger_text: str = ""
    suggested_archetype: str = "General Drama"


class PromoRuleEngine:
    """Evaluates screenplay beats and extracts 20-60s candidate promos."""

    def __init__(self, min_duration: float = 20.0, max_duration: float = 60.0):
        self.min_duration = min_duration
        self.max_duration = max_duration

    def score_hook(self, beat: Beat) -> Tuple[float, str]:
        """Scores how effectively a beat stops the scroll within seconds 0-3."""
        score = 0.0
        reasons = []

        text_lower = beat.text.lower()
        tone_lower = beat.tone.lower()
        speaker_lower = beat.speaker.lower()

        # 1. High-voltage emotional tone
        for tone_word in HIGH_VOLTAGE_TONES:
            if tone_word in tone_lower:
                score += 2.5
                reasons.append(f"High-voltage emotion ({tone_word})")
                break

        # 2. Physical action / violation
        for act in PHYSICAL_ACTION_VERBS:
            if re.search(r"\b" + act + r"\b", text_lower):
                score += 3.0
                reasons.append(f"Physical action ({act})")
                break

        # 3. High-stakes keywords
        found_stakes = [w for w in HIGH_STAKES_WORDS if re.search(r"\b" + re.escape(w) + r"\b", text_lower)]
        if found_stakes:
            score += min(3.5, len(found_stakes) * 1.5)
            reasons.append(f"High-stakes theme ({', '.join(found_stakes[:2])})")

        # 4. Immediate dialogue question or provocative statement
        if beat.beat_type == "dialogue":
            score += 1.0
            if "?" in beat.text or "!" in beat.text:
                score += 1.0

        score = min(10.0, max(0.0, score))
        return score, "; ".join(reasons)

    def score_cliffhanger(self, beat: Beat) -> Tuple[float, str]:
        """Scores whether a beat ends on an unresolved, high-tension cliffhanger."""
        score = 0.0
        reasons = []

        text_lower = beat.text.lower()
        tone_lower = beat.tone.lower()

        # 1. Unanswered question
        if beat.beat_type == "dialogue" and beat.text.strip().endswith("?"):
            score += 3.5
            reasons.append("Unanswered question")

        # 2. Ultimatums / Declarations / Threats
        ultimatum_triggers = ["marry", "never", "not anymore", "changed my mind", "ends here", "my wife", "your grace", "hang", "kill", "who did this", "taking back"]
        for trig in ultimatum_triggers:
            if trig in text_lower:
                score += 3.0
                reasons.append(f"Ultimatum trigger ({trig})")
                break

        # 3. Dramatic holds / shock actions
        if beat.beat_type in ("action", "camera"):
            if any(k in text_lower for k in ["kneel", "stunned", "silence", "tears", "furious", "draws", "stares", "frozen"]):
                score += 2.5
                reasons.append("Dramatic reaction hold")

        # 4. Punctuation indicators of unfinished action (...)
        if beat.text.strip().endswith("..."):
            score += 1.5
            reasons.append("Suspended dialogue (...)")

        score = min(10.0, max(0.0, score))
        return score, "; ".join(reasons)

    def classify_archetype(self, beats: List[Beat]) -> str:
        """Determines the universal ReelShort archetype for a sequence of beats."""
        full_text = " ".join(b.text.lower() for b in beats)
        
        if any(w in full_text for w in ["altar", "wedding", "groom", "marrying me", "gown", "fiancé", "changed my mind"]):
            return "Altar Betrayal & Public Humiliation"
        elif any(w in full_text for w in ["propose", "proposal", "ring", "knee", "marry me", "solemn vow"]):
            return "The Impromptu Proposal / Heroic Claim"
        elif any(w in full_text for w in ["who did this", "wounds", "bruise", "struck", "never be hurt", "defend"]):
            return "Protector Retribution (\"Who Did This?\")"
        elif any(w in full_text for w in ["your grace", "duke", "dead duke", "beggar", "my house", "birthright"]):
            return "Status Inversion & Duke Reveal"
        elif any(w in full_text for w in ["execution", "block", "scaffold", "witch", "gallows", "poison", "arsenic"]):
            return "Life-or-Death Scaffold Climax"
        return "Underdog Defiance / High-Stakes Clash"

    def extract_candidates_for_episode(self, script: EpisodeScript, top_k: int = 5) -> List[CandidatePromo]:
        """Generates top continuous 20-60s candidate promos from an episode script."""
        beats = script.beats
        if not beats:
            return []

        candidates: List[CandidatePromo] = []
        n = len(beats)

        # Sliding window over potential start beats
        for i in range(n):
            start_beat = beats[i]
            hook_score, hook_reason = self.score_hook(start_beat)
            
            # Only consider starting beats that have at least some hook potential (>= 3.0)
            if hook_score < 2.5:
                continue

            # Slide end beat forward to find valid 20s - 60s windows
            for j in range(i + 1, n):
                end_beat = beats[j]
                duration = end_beat.end_sec - start_beat.start_sec
                
                if duration < self.min_duration:
                    continue
                if duration > self.max_duration:
                    break  # Exceeded max duration, stop expanding this window

                cliff_score, cliff_reason = self.score_cliffhanger(end_beat)
                
                # Must end on a beat with some cliffhanger tension
                if cliff_score < 2.5:
                    continue

                window_beats = beats[i:j+1]
                
                # Calculate dialogue density / escalation
                dialogue_beats = [b for b in window_beats if b.beat_type == "dialogue"]
                turns = len(dialogue_beats)
                dialogue_rate = (turns / (duration / 60.0)) if duration > 0 else 0
                escalation_score = min(10.0, max(2.0, (dialogue_rate / 8.0) * 10.0))

                # Composite score
                # 35% Hook + 35% Cliffhanger + 30% Escalation
                composite = (0.35 * hook_score) + (0.35 * cliff_score) + (0.30 * escalation_score)
                
                # Bonus if duration is in the sweet spot (32s - 50s)
                if 32.0 <= duration <= 50.0:
                    composite += 0.5
                
                archetype = self.classify_archetype(window_beats)

                # Format hook and cliffhanger descriptions
                h_text = f"{start_beat.speaker}: \"{start_beat.text}\"" if start_beat.beat_type == "dialogue" else start_beat.text
                c_text = f"{end_beat.speaker}: \"{end_beat.text}\"" if end_beat.beat_type == "dialogue" else end_beat.text

                segment = PromoSegment(
                    episode=script.episode_number,
                    start_sec=start_beat.start_sec,
                    end_sec=end_beat.end_sec,
                    start_str=seconds_to_timestamp(start_beat.start_sec),
                    end_str=seconds_to_timestamp(end_beat.end_sec),
                    duration_sec=round(duration, 2),
                    beats=window_beats
                )

                cand = CandidatePromo(
                    candidate_id=f"EP{script.episode_number:02d}_{start_beat.start_str.replace(':', '')}_{end_beat.end_str.replace(':', '')}",
                    promo_type="single_segment",
                    episodes=[script.episode_number],
                    segments=[segment],
                    total_duration_sec=round(duration, 2),
                    hook_score=round(hook_score, 2),
                    escalation_score=round(escalation_score, 2),
                    cliffhanger_score=round(cliff_score, 2),
                    composite_heuristic_score=round(composite, 2),
                    hook_beat=start_beat,
                    cliffhanger_beat=end_beat,
                    hook_text=h_text,
                    cliffhanger_text=c_text,
                    suggested_archetype=archetype
                )
                candidates.append(cand)

        # Deduplicate overlapping candidates (keep highest scoring within overlapping start windows)
        candidates.sort(key=lambda c: c.composite_heuristic_score, reverse=True)
        filtered: List[CandidatePromo] = []
        
        for cand in candidates:
            c_start = cand.segments[0].start_sec
            c_end = cand.segments[0].end_sec
            
            # Check overlap with already selected candidates
            overlap = False
            for existing in filtered:
                e_start = existing.segments[0].start_sec
                e_end = existing.segments[0].end_sec
                # Overlap condition: start times within 10 seconds of each other
                if abs(c_start - e_start) < 10.0:
                    overlap = True
                    break
            
            if not overlap:
                filtered.append(cand)
            if len(filtered) >= top_k:
                break

        return filtered

    def create_stitched_promo(
        self,
        hook_segment: PromoSegment,
        payoff_segment: PromoSegment,
        archetype: str = "Connected Arc: Betrayal to Rescue"
    ) -> Optional[CandidatePromo]:
        """Creates a high-performing 2-segment stitch promo (e.g. 12s Ep 1 Betrayal + 30s Ep 3 Proposal)."""
        tot_dur = hook_segment.duration_sec + payoff_segment.duration_sec
        if tot_dur < self.min_duration or tot_dur > self.max_duration:
            return None

        hook_beat = hook_segment.beats[0] if hook_segment.beats else None
        cliff_beat = payoff_segment.beats[-1] if payoff_segment.beats else None

        h_score, _ = self.score_hook(hook_beat) if hook_beat else (5.0, "")
        c_score, _ = self.score_cliffhanger(cliff_beat) if cliff_beat else (5.0, "")
        comp = (0.40 * h_score) + (0.40 * c_score) + 2.0  # High bonus for curated mini-story stitch

        return CandidatePromo(
            candidate_id=f"STITCH_EP{hook_segment.episode:02d}_EP{payoff_segment.episode:02d}",
            promo_type="stitched_segment",
            episodes=sorted(list(set([hook_segment.episode, payoff_segment.episode]))),
            segments=[hook_segment, payoff_segment],
            total_duration_sec=round(tot_dur, 2),
            hook_score=round(h_score, 2),
            escalation_score=9.0,
            cliffhanger_score=round(c_score, 2),
            composite_heuristic_score=round(comp, 2),
            hook_beat=hook_beat,
            cliffhanger_beat=cliff_beat,
            hook_text=f"Ep {hook_segment.episode}: {hook_beat.text if hook_beat else ''}",
            cliffhanger_text=f"Ep {payoff_segment.episode}: {cliff_beat.text if cliff_beat else ''}",
            suggested_archetype=archetype
        )
