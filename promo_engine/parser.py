"""
Universal Screenplay Parser for Microdrama Series.
Parses formatted screenplays containing scenes, timestamps, character dialogue,
tone modifiers, actions, and camera directions into structured beat timelines.
Zero hardcoding: works on any screenplay following standard production formats.
"""

import re
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Dict, Any


def timestamp_to_seconds(ts_str: str) -> float:
    """Converts (MM:SS.ss) or MM:SS.ss or HH:MM:SS to float seconds."""
    clean = re.sub(r"[^\d:.]", "", ts_str.strip())
    if not clean:
        return 0.0
    parts = clean.split(":")
    if len(parts) == 3:
        h, m, s = parts
        return float(h) * 3600 + float(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return float(m) * 60 + float(s)
    elif len(parts) == 1:
        return float(parts[0])
    return 0.0


def seconds_to_timestamp(seconds: float) -> str:
    """Converts float seconds back to standard MM:SS.ss string format."""
    mins = int(seconds // 60)
    secs = seconds % 60
    return f"{mins:02d}:{secs:05.2f}"


@dataclass
class Beat:
    beat_type: str  # 'dialogue', 'action', 'camera'
    start_sec: float
    end_sec: float
    speaker: str = ""
    tone: str = ""
    text: str = ""
    scene_number: int = 1
    episode_number: int = 1

    @property
    def duration(self) -> float:
        return max(0.0, self.end_sec - self.start_sec)

    @property
    def start_str(self) -> str:
        return seconds_to_timestamp(self.start_sec)

    @property
    def end_str(self) -> str:
        return seconds_to_timestamp(self.end_sec)


@dataclass
class Scene:
    scene_number: int
    heading: str
    start_sec: float
    end_sec: float
    beats: List[Beat] = field(default_factory=list)


@dataclass
class EpisodeScript:
    episode_number: int
    logline: str
    continuity_notes: str
    scenes: List[Scene] = field(default_factory=list)
    beats: List[Beat] = field(default_factory=list)
    raw_path: str = ""

    @property
    def total_duration(self) -> float:
        if not self.beats:
            return 0.0
        return max(b.end_sec for b in self.beats)


class ScreenplayParser:
    """Robust parser for microdrama screenplay text files."""

    def parse_text(self, text: str, episode_num_hint: Optional[int] = None) -> EpisodeScript:
        lines = text.splitlines()
        
        # 1. Extract Header Metadata
        episode_num = episode_num_hint or 1
        logline = ""
        continuity = ""
        
        for line in lines[:20]:
            ep_match = re.search(r"EPISODE\s+NUMBER:\s*(?:Episode\s*)?(\d+)", line, re.IGNORECASE)
            if ep_match:
                episode_num = int(ep_match.group(1))
            log_match = re.search(r"EPISODE\s+LOGLINE:\s*(.+)", line, re.IGNORECASE)
            if log_match:
                logline = log_match.group(1).strip()
            cont_match = re.search(r"CONTINUITY\s+NOTES:\s*(.+)", line, re.IGNORECASE)
            if cont_match:
                continuity = cont_match.group(1).strip()

        # 2. Parse Scenes and Beats
        scenes: List[Scene] = []
        all_beats: List[Beat] = []
        
        current_scene_num = 1
        current_scene_heading = "GENERAL"
        current_scene_start = 0.0
        current_scene_end = 0.0
        current_scene_beats: List[Beat] = []

        i = 0
        n = len(lines)
        
        # Regex helpers
        time_pat = re.compile(r"Start:\s*\(?([0-9:.]+)\)?\s*\|\s*End:\s*\(?([0-9:.]+)\)?", re.IGNORECASE)
        scene_heading_pat = re.compile(r"^(?:SCENE\s+(\d+)|Scene\s+heading:\s*(.+)|Scene\s+start:\s*([0-9:.]+)|Scene\s+end:\s*([0-9:.]+))", re.IGNORECASE)

        while i < n:
            line = lines[i].strip()
            if not line:
                i += 1
                continue

            # Scene headers
            if line.upper().startswith("SCENE ") and not line.startswith("**"):
                # Close previous scene
                if current_scene_beats:
                    scenes.append(Scene(
                        scene_number=current_scene_num,
                        heading=current_scene_heading,
                        start_sec=current_scene_start,
                        end_sec=current_scene_end or (current_scene_beats[-1].end_sec if current_scene_beats else 0.0),
                        beats=current_scene_beats
                    ))
                    current_scene_beats = []
                
                num_match = re.search(r"SCENE\s+(\d+)", line, re.IGNORECASE)
                if num_match:
                    current_scene_num = int(num_match.group(1))
                i += 1
                continue

            if line.lower().startswith("scene heading:"):
                current_scene_heading = line.split(":", 1)[1].strip()
                i += 1
                continue

            if line.lower().startswith("scene start:"):
                current_scene_start = timestamp_to_seconds(line.split(":", 1)[1])
                i += 1
                continue

            if line.lower().startswith("scene end:"):
                current_scene_end = timestamp_to_seconds(line.split(":", 1)[1])
                i += 1
                continue

            # Check for Camera Block
            if line.startswith("**CAMERA:**") or line == "**CAMERA**":
                i += 1
                start_sec, end_sec = 0.0, 0.0
                if i < n:
                    tm = time_pat.search(lines[i])
                    if tm:
                        start_sec = timestamp_to_seconds(tm.group(1))
                        end_sec = timestamp_to_seconds(tm.group(2))
                        i += 1
                # Read description
                desc_lines = []
                while i < n and lines[i].strip() and not lines[i].strip().startswith("**"):
                    desc_lines.append(lines[i].strip())
                    i += 1
                desc = " ".join(desc_lines)
                beat = Beat(
                    beat_type="camera",
                    start_sec=start_sec,
                    end_sec=end_sec,
                    text=desc,
                    scene_number=current_scene_num,
                    episode_number=episode_num
                )
                current_scene_beats.append(beat)
                all_beats.append(beat)
                continue

            # Check for Action Block
            if line.startswith("**ACTION:**") or line == "**ACTION**":
                i += 1
                start_sec, end_sec = 0.0, 0.0
                if i < n:
                    tm = time_pat.search(lines[i])
                    if tm:
                        start_sec = timestamp_to_seconds(tm.group(1))
                        end_sec = timestamp_to_seconds(tm.group(2))
                        i += 1
                desc_lines = []
                while i < n and lines[i].strip() and not lines[i].strip().startswith("**"):
                    desc_lines.append(lines[i].strip())
                    i += 1
                desc = " ".join(desc_lines)
                beat = Beat(
                    beat_type="action",
                    start_sec=start_sec,
                    end_sec=end_sec,
                    text=desc,
                    scene_number=current_scene_num,
                    episode_number=episode_num
                )
                current_scene_beats.append(beat)
                all_beats.append(beat)
                continue

            # Check for Character Dialogue Block: **NAME (TONE):**
            char_match = re.match(r"^\*\*([A-Z0-9\s._'-]+?)(?:\s*\(([^)]+)\))?\s*:\*\*", line)
            if char_match:
                speaker = char_match.group(1).strip()
                tone = char_match.group(2).strip() if char_match.group(2) else ""
                i += 1
                start_sec, end_sec = 0.0, 0.0
                if i < n:
                    tm = time_pat.search(lines[i])
                    if tm:
                        start_sec = timestamp_to_seconds(tm.group(1))
                        end_sec = timestamp_to_seconds(tm.group(2))
                        i += 1
                dialogue_lines = []
                while i < n and lines[i].strip() and not lines[i].strip().startswith("**"):
                    clean_d = lines[i].strip().strip('"')
                    dialogue_lines.append(clean_d)
                    i += 1
                dialogue_text = " ".join(dialogue_lines)
                beat = Beat(
                    beat_type="dialogue",
                    start_sec=start_sec,
                    end_sec=end_sec,
                    speaker=speaker,
                    tone=tone,
                    text=dialogue_text,
                    scene_number=current_scene_num,
                    episode_number=episode_num
                )
                current_scene_beats.append(beat)
                all_beats.append(beat)
                continue

            i += 1

        # Append last scene
        if current_scene_beats:
            scenes.append(Scene(
                scene_number=current_scene_num,
                heading=current_scene_heading,
                start_sec=current_scene_start,
                end_sec=current_scene_end or (current_scene_beats[-1].end_sec if current_scene_beats else 0.0),
                beats=current_scene_beats
            ))

        # 3. Universal Fallback: If 0 beats were found with strict **BLOCK** format,
        # parse generic screenplay format (e.g. NAME: dialogue, or timestamped dialogue)
        if not all_beats:
            all_beats = self._parse_generic_script(lines, episode_num)
            if all_beats:
                scenes = [Scene(
                    scene_number=1,
                    heading="SCENE 1",
                    start_sec=all_beats[0].start_sec,
                    end_sec=all_beats[-1].end_sec,
                    beats=all_beats
                )]

        return EpisodeScript(
            episode_number=episode_num,
            logline=logline,
            continuity_notes=continuity,
            scenes=scenes,
            beats=all_beats
        )

    def _parse_generic_script(self, lines: List[str], episode_num: int) -> List[Beat]:
        """Flexible fallback parser for arbitrary screenplay scripts."""
        beats = []
        cur_time = 0.0
        ts_pattern = re.compile(r"\(?(\d{1,2}:\d{2}(?:\.\d{1,2})?)\)?")
        dialogue_pattern = re.compile(r"^([A-Z0-9\s._'-]{2,25}?)(?:\s*\(([^)]+)\))?\s*:\s*(.+)$")

        for line in lines:
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue

            # Check if line contains a timestamp
            ts_match = ts_pattern.search(line_str)
            if ts_match:
                cur_time = timestamp_to_seconds(ts_match.group(1))

            # Check dialogue
            d_match = dialogue_pattern.match(line_str)
            if d_match:
                spk = d_match.group(1).strip()
                tone = d_match.group(2).strip() if d_match.group(2) else ""
                txt = d_match.group(3).strip()
                
                # Estimate duration if not explicitly advanced
                est_dur = max(2.5, min(12.0, len(txt.split()) * 0.45))
                end_time = cur_time + est_dur

                beats.append(Beat(
                    beat_type="dialogue",
                    start_sec=cur_time,
                    end_sec=end_time,
                    speaker=spk,
                    tone=tone,
                    text=txt,
                    scene_number=1,
                    episode_number=episode_num
                ))
                cur_time = end_time
            elif len(line_str.split()) > 3 and not line_str.startswith("["):
                # Action line
                est_dur = max(2.0, min(8.0, len(line_str.split()) * 0.4))
                end_time = cur_time + est_dur
                beats.append(Beat(
                    beat_type="action",
                    start_sec=cur_time,
                    end_sec=end_time,
                    text=line_str,
                    scene_number=1,
                    episode_number=episode_num
                ))
                cur_time = end_time

        return beats

    def parse_file(self, file_path: str) -> EpisodeScript:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        
        # Try to infer episode number from filename if possible
        fn_match = re.search(r"episode-?(\d+)", file_path, re.IGNORECASE)
        ep_hint = int(fn_match.group(1)) if fn_match else None
        
        script = self.parse_text(content, episode_num_hint=ep_hint)
        script.raw_path = file_path
        return script
