"""
Kuku AI Promo Finding Engine Package
"""

import sys
from pathlib import Path

# Automatically ensure project root is always in sys.path
_root = str(Path(__file__).resolve().parent.parent)
if _root not in sys.path:
    sys.path.insert(0, _root)

from promo_engine.parser import ScreenplayParser, EpisodeScript, Beat
from promo_engine.rules import PromoRuleEngine, CandidatePromo, PromoSegment
from promo_engine.llm_evaluator import LLMEvaluator, RankedPromo
from promo_engine.pipeline import PromoPipeline

__all__ = [
    "ScreenplayParser",
    "EpisodeScript",
    "Beat",
    "PromoRuleEngine",
    "CandidatePromo",
    "PromoSegment",
    "LLMEvaluator",
    "RankedPromo",
    "PromoPipeline",
]
