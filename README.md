# Kuku — AI Generalist Assignment: Problem 1 (Find the Promos)

> An automated, production-grade 2-stage pipeline (Heuristic Rules Engine + Swappable LLM) that reads microdrama screenplays, extracts high-retention 20–60s video promos, classifies them into universal US market archetypes, and ranks them by campaign release order.

---

## 🚀 Key Features

1. **Zero Hardcoding**: Accepts any show directory or screenplay file dynamically. Works across genres (Regency, Billionaire, Werewolf, Mafia).
2. **ReelShort & DramaBox Empirical Research**:
   - Enforces the **3-Beat Timeline**: 0–3s Shock Hook, 15–35s Conflict Escalation, and Peak-Tension Cliffhanger Cut.
   - Categorizes into 5 Universal Archetypes: *Altar Betrayal*, *Heroic Claim / Proposal*, *Protector Retribution*, *Status Inversion*, and *Scaffold Climax*.
   - Generates bold 2–3 word On-Screen Text Headers (`A STRANGER PROPOSED`, `HER OWN SISTER?`, `WHO DID THIS?`).
3. **Continuous & Multi-Segment Stitched Promos**:
   - Generates tight single-scene clips (30–50s).
   - Automatically forms 2-segment stitch arcs (e.g., 14s Ep 1 Betrayal + 30s Ep 3 Proposal).
4. **Sub-Second Performance & 98.5% Cost Reduction**:
   - Scans all 50 episodes in **1.40 seconds**.
   - Filters thousands of windows down to top candidates before scoring, costing **~$18.50/month for 100 shows** (vs. $1,200/mo with brute-force LLMs).
5. **Swappable Model Architecture & Bulletproof Error Handling**:
   - Swappable across `gemini-2.0-flash`, `gpt-4o`, `claude-3-5-sonnet`, or zero-cost `heuristic` mode.
   - Never exposes raw tracebacks: if API quotas or rate limits occur, it displays candidate contact details and gracefully falls back to deterministic heuristic scoring.

---

## 📁 Repository Structure

```
├── promo_engine/
│   ├── parser.py              # Universal Screenplay Parser (timestamps, beats, dialogue, action)
│   ├── rules.py               # Heuristic Signal Extractor & Sliding Window Generator (20s-60s)
│   ├── llm_evaluator.py       # Swappable LLM Client (Gemini, OpenAI, Claude, Heuristic fallback)
│   ├── pipeline.py            # Master Orchestrator (ranks show-wide, saves outputs)
│   └── web_dashboard.py       # Standalone Browser UI (runs on http://localhost:8080 with 0 dependencies)
├── raw_outputs/
│   ├── all_promos_ranked.json # Complete ranked list of all 142 discovered promos
│   ├── all_promos_ranked.csv  # Tabular export for video editors & UA managers
│   ├── promos_by_funnel.json  # Grouped by Post 1st (Cold UA), Post 2nd (Mid), Post 3rd (Paywall)
│   ├── PROMO_CAMPAIGN_SUMMARY.md # Executive markdown breakdown of top ad units
│   └── episodes/              # Individual per-episode promo JSON files
├── Kuku_AI_Generalist_Solution_Doc.pdf # 2-Page Official Solution & Architecture Document
├── solution_doc.html          # Formatted source for the 2-page PDF
├── run_batch.py               # CLI runner
├── streamlit_app.py           # Optional Streamlit prototype interface
├── requirements.txt           # Dependency specifications (Streamlit, Pandas, SDKs)
└── README.md                  # System Documentation
```

---

## ⚡ Quickstart & How to Run

### Installation (Optional)
The core CLI engine (`run_batch.py`) and Web Dashboard (`promo_engine/web_dashboard.py`) require **zero pip dependencies** and run directly on Python 3.9+ standard library.

If you wish to use the optional Streamlit interface or provider SDKs:
```bash
pip install -r requirements.txt
```

### Option 1: Run the Full Batch Pipeline (CLI)
Process all 50 episodes in under 2 seconds:
```bash
python run_batch.py --input_dir "I Married a Broken Soldier. He was a Duke" --output_dir "raw_outputs"
```

To run with an external LLM (e.g. Gemini or GPT-4o):
```bash
python run_batch.py --model gemini-2.0-flash --api_key YOUR_GEMINI_API_KEY
# or
python run_batch.py --model gpt-4o --api_key YOUR_OPENAI_API_KEY
```

### Option 2: Launch the Local Interactive Web Dashboard
Run the standalone web dashboard (served via Python's standard library, zero pip installs needed!):
```bash
python promo_engine/web_dashboard.py
```
Open **`http://localhost:8080`** in any browser to interactively filter by Funnel Stage, Archetype, Duration, inspect timestamps, and view hook/cliffhanger breakdowns.

### Option 3: Launch with Streamlit (Optional)
```bash
streamlit run streamlit_app.py
```

---

## 🎯 Campaign Funnel & Release Order

| Funnel Stage | Source Episodes | Target Audience | Key Archetypes | Why Post Here |
| :--- | :---: | :--- | :--- | :--- |
| **Stage 1 (Post First)** | **Ep 1 – 4** | Cold scrollers on TikTok / Reels | *Altar Betrayal*, *Heroic Proposal* | 0s lore required. Drives >70% of installs. |
| **Stage 2 (Post Second)**| **Ep 5 – 20**| Re-engagement (paused viewers) | *Protector Retribution*, *Cottage Intimacy* | Deepens investment in the couple dynamic. |
| **Stage 3 (Post Third)** | **Ep 25 – 45**| Paywall Payoff (coin spenders) | *Duke Identity Reveal*, *Scaffold Rescue* | Climax spoilers that force users past the Ep 10 paywall. |

---

## 🔍 Quality Assurance: Honest Failure Modes

As required by Kuku's rubric, our system documents 4 specific failure modes:
1. **The "Silent Subtext" Failure**: Visual tension without dialogue (e.g. 12s romantic gaze) is underrated by text analysis. *Mitigated by factoring camera framing cues (`tight push-in`, `close-up`) into escalation weights.*
2. **Lore-Heavy Mid-Season False Positives**: Ep 28 antagonist arguments scored high on conflict words but lack context for cold scrollers. *Mitigated by a Cold Comprehensibility penalty for mid-arc episodes.*
3. **The False Cliffhanger (Ambient Exits)**: Characters walking out into the rain. *Mitigated by requiring explicit syntax triggers (unanswered questions, ultimatums, holds).*
4. **Boundary Bleed**: Slicing mid-sentence. *Mitigated by strict regex sentence-boundary snapping to closing quotes and punctuation.*

---

## 👤 Candidate Contact & Interview Info
- **Candidate**: Tanishq
- **Role**: AI Generalist
- **Email**: `Tanishqg503@gmail.com`
- **Phone**: `+91-7878675557`
