"""
CLI Runner for Kuku AI Promo Finding Engine.
Can be executed on any show folder or screenplay file.

Usage:
  python.cmd run_batch.py --input_dir "I Married a Broken Soldier. He was a Duke" --output_dir "raw_outputs"
  python.cmd run_batch.py --model gemini-2.0-flash --api_key YOUR_KEY
"""

import argparse
import sys
from pathlib import Path

# Ensure project root is in sys.path
_root_dir = str(Path(__file__).resolve().parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from promo_engine.pipeline import PromoPipeline


def main():
    parser = argparse.ArgumentParser(description="Find & Rank Best Video Promos from Microdrama Screenplays")
    parser.add_argument(
        "--input_dir",
        type=str,
        default="I Married a Broken Soldier. He was a Duke",
        help="Path to folder containing screenplay .txt files (or a single file)"
    )
    parser.add_argument(
        "--output_dir",
        type=str,
        default="raw_outputs",
        help="Directory to save raw unedited promo outputs (JSON, CSV, MD)"
    )
    parser.add_argument(
        "--model",
        type=str,
        default="grok-2-latest",
        help="Model to use: 'grok-2-latest' (xAI), 'grok-beta', 'gemini-2.0-flash', 'gpt-4o', or 'heuristic' (zero-cost)"
    )
    parser.add_argument(
        "--api_key",
        type=str,
        default=None,
        help="Optional API key for LLM provider (or set GROK_API_KEY / XAI_API_KEY in .env or environment)"
    )
    parser.add_argument(
        "--min_duration",
        type=float,
        default=20.0,
        help="Minimum promo duration in seconds (default: 20.0s)"
    )
    parser.add_argument(
        "--max_duration",
        type=float,
        default=60.0,
        help="Maximum promo duration in seconds (default: 60.0s)"
    )

    args = parser.parse_args()

    pipeline = PromoPipeline(
        model_name=args.model,
        api_key=args.api_key,
        min_duration=args.min_duration,
        max_duration=args.max_duration
    )

    promos = pipeline.process_directory(
        input_dir=args.input_dir,
        output_dir=args.output_dir
    )

    if not promos:
        print("[!] No promos generated. Please check input directory path.")
        sys.exit(1)

    print("\n=======================================================")
    print(f"🎉 SUCCESS: Extracted & Ranked {len(promos)} Promos!")
    print(f"📁 Raw Outputs saved in '{args.output_dir}/'")
    print(f"   • {args.output_dir}/all_promos_ranked.json")
    print(f"   • {args.output_dir}/all_promos_ranked.csv")
    print(f"   • {args.output_dir}/promos_by_funnel.json")
    print(f"   • {args.output_dir}/PROMO_CAMPAIGN_SUMMARY.md")
    print("=======================================================\n")


if __name__ == "__main__":
    main()
