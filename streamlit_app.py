"""
Streamlit Web Prototype for Kuku AI Promo Finding Engine.
Run with:
  streamlit run streamlit_app.py
"""

import streamlit as st
import json
import os
import sys
import glob
from pathlib import Path

# Ensure project root is in sys.path
_root_dir = str(Path(__file__).resolve().parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

import pandas as pd
from promo_engine.pipeline import PromoPipeline

st.set_page_config(page_title="Kuku AI — Microdrama Promo Studio", layout="wide", page_icon="🎬")

st.title("🎬 Kuku AI — Microdrama Video Promo Studio")
st.markdown("Automated 2-Stage Pipeline (Heuristic Rule Engine + Swappable LLM) engineered for US TikTok, Reels & Shorts Ad Creatives.")

# Sidebar Controls: Show Ingestion & Model Setup
st.sidebar.header("📁 Ingest Show Screenplays")
ingest_mode = st.sidebar.radio("Ingestion Source", ["Local Directory on Server", "Upload .txt Screenplay Files"])

uploads_dir = os.path.join(_root_dir, "uploads")
os.makedirs(uploads_dir, exist_ok=True)

target_folder = "I Married a Broken Soldier. He was a Duke"
show_name_display = "I Married a Broken Soldier. He was a Duke"

if ingest_mode == "Upload .txt Screenplay Files":
    custom_show_name = st.sidebar.text_input("Show Title", value="My Custom Drama")
    uploaded_files = st.sidebar.file_uploader(
        "Upload episode .txt files",
        type=["txt"],
        accept_multiple_files=True
    )
    if uploaded_files:
        clean_name = "".join(c for c in custom_show_name if c.isalnum() or c in (" ", "_", "-")).strip() or "Custom_Show"
        target_folder = os.path.join(uploads_dir, clean_name)
        os.makedirs(target_folder, exist_ok=True)
        for uf in uploaded_files:
            fpath = os.path.join(target_folder, uf.name)
            with open(fpath, "wb") as f:
                f.write(uf.getbuffer())
        show_name_display = custom_show_name
        st.sidebar.success(f"Uploaded {len(uploaded_files)} episodes into `{target_folder}`")
else:
    target_folder = st.sidebar.text_input("Screenplay Directory Path", value="I Married a Broken Soldier. He was a Duke")
    show_name_display = os.path.basename(target_folder)

st.sidebar.markdown("---")
st.sidebar.header("⚙️ Model & Extraction Settings")
model_choice = st.sidebar.selectbox(
    "Evaluation Model",
    ["auto (Groq LPU: openai/gpt-oss-120b)", "heuristic (Zero Cost / Instant)", "grok-2-latest (xAI Grok)", "gemini-2.0-flash", "gpt-4o"]
)
min_dur, max_dur = st.sidebar.slider("Promo Duration Range (seconds)", 15, 75, (20, 60))

if st.sidebar.button("🚀 Run Promo Extraction Pipeline", use_container_width=True):
    with st.spinner(f"Analyzing screenplays in '{target_folder}' and extracting 20–60s hooks & cliffhangers..."):
        model_key = model_choice.split()[0]
        pipeline = PromoPipeline(
            model_name=model_key,
            min_duration=float(min_dur),
            max_duration=float(max_dur)
        )
        pipeline.process_directory(target_folder, output_dir="raw_outputs")
        st.sidebar.success("🎉 Extraction completed! Dashboard updated below.")

# Load Ranked Promos
raw_json_path = os.path.join("raw_outputs", "all_promos_ranked.json")
raw_csv_path = os.path.join("raw_outputs", "all_promos_ranked.csv")

if not os.path.exists(raw_json_path):
    st.info("No promos loaded yet. Use the sidebar to run promo extraction on any show folder.")
    st.stop()

with open(raw_json_path, "r", encoding="utf-8") as f:
    promos = json.load(f)

# KPI Metric Header
st.markdown(f"### Current Show: **{show_name_display}**")
kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
continuous_promos = [p for p in promos if not "stitched" in p["promo_type"]]
stitched_promos = [p for p in promos if "stitched" in p["promo_type"]]
stage1_promos = [p for p in promos if "Stage 1" in p["funnel_stage"]]
avg_duration = sum(p["total_duration_sec"] for p in promos) / len(promos) if promos else 0.0

kpi1.metric("Total Promos Found", len(promos))
kpi2.metric("Continuous Clips", len(continuous_promos))
kpi3.metric("Stitched Multi-Segment", len(stitched_promos))
kpi4.metric("Stage 1 (Cold UA)", len(stage1_promos))
kpi5.metric("Avg Duration", f"{avg_duration:.1f}s")

st.markdown("---")

# Interactive Filter Controls
f_row1_col1, f_row1_col2, f_row1_col3 = st.columns([1.5, 1.5, 2])
with f_row1_col1:
    clip_format_filter = st.radio(
        "Clip Format",
        ["All Formats", "Continuous Clips Only", "Multi-Segment Stitches Only"],
        horizontal=True
    )

with f_row1_col2:
    top_n_filter = st.selectbox(
        "Show Top N Promos",
        ["All Ranked Promos", "Top 5 (Priority Ad Units)", "Top 3", "Top 10", "Top 25", "Top 50"],
        index=0
    )

with f_row1_col3:
    search_query = st.text_input("🔍 Search Dialogue, Keywords, or Promo ID", placeholder="e.g. altar, poison, Juliana, EP01...")

f_row2_col1, f_row2_col2, f_row2_col3, f_row2_col4 = st.columns(4)
with f_row2_col1:
    stage_filter = st.selectbox(
        "Funnel Stage",
        ["All Funnel Stages", "Stage 1: Top-of-Funnel (Post First)", "Stage 2: Mid-Funnel (Post Second)", "Stage 3: Paywall Teaser (Post Third)"]
    )

with f_row2_col2:
    archetype_filter = st.selectbox(
        "Archetype",
        ["All Archetypes", "Proposal", "Altar Betrayal", "Retribution", "Status Inversion", "Scaffold"]
    )

with f_row2_col3:
    dur_range = st.selectbox(
        "Duration Window",
        ["All Durations (20–60s)", "< 35s (Snappy)", "35s - 48s (Sweetspot)", "48s - 60s (Narrative)"],
        index=0
    )

with f_row2_col4:
    sort_order = st.selectbox(
        "Sort Order",
        ["Campaign Release Order (Post First)", "Pure Virality Score (Highest ★ First)"],
        index=0
    )

# Filter Logic
filtered = []
for p in promos:
    # Format
    if clip_format_filter == "Continuous Clips Only" and "stitched" in p["promo_type"]:
        continue
    if clip_format_filter == "Multi-Segment Stitches Only" and not "stitched" in p["promo_type"]:
        continue

    # Funnel
    if stage_filter != "All Funnel Stages" and stage_filter.split(":")[0] not in p["funnel_stage"]:
        continue

    # Archetype
    if archetype_filter != "All Archetypes" and archetype_filter.lower() not in p["archetype"].lower():
        continue

    # Duration
    dur = p["total_duration_sec"]
    if dur_range == "< 35s (Snappy)" and dur >= 35.0:
        continue
    if dur_range == "35s - 48s (Sweetspot)" and (dur < 35.0 or dur > 48.0):
        continue
    if dur_range == "48s - 60s (Narrative)" and dur <= 48.0:
        continue

    # Search
    if search_query.strip():
        q = search_query.lower().strip()
        haystack = f"{p['promo_id']} {p['header_hook']} {p['archetype']} {p['hook_summary']} {p['cliffhanger_summary']} {p['why_it_works']}".lower()
        if q not in haystack:
            continue

    filtered.append(p)

# Apply Sort Order
if "Pure Virality" in sort_order:
    filtered.sort(key=lambda x: x["virality_score"], reverse=True)
else:
    filtered.sort(key=lambda x: x["rank"])

# Apply Top N slicing
if "Top 3" in top_n_filter:
    display_promos = filtered[:3]
elif "Top 5" in top_n_filter:
    display_promos = filtered[:5]
elif "Top 10" in top_n_filter:
    display_promos = filtered[:10]
elif "Top 25" in top_n_filter:
    display_promos = filtered[:25]
elif "Top 50" in top_n_filter:
    display_promos = filtered[:50]
else:
    display_promos = filtered

# Export Toolbar
exp_c1, exp_c2, exp_c3 = st.columns([1, 1, 3])
with exp_c1:
    if os.path.exists(raw_csv_path):
        with open(raw_csv_path, "rb") as f:
            st.download_button("📥 Download Production CSV", f, file_name="kuku_promos_ranked.csv", mime="text/csv", use_container_width=True)
with exp_c2:
    if os.path.exists(raw_json_path):
        with open(raw_json_path, "rb") as f:
            st.download_button("📥 Download JSON Deliverable", f, file_name="kuku_promos_ranked.json", mime="application/json", use_container_width=True)

st.subheader(f"Ranked Video Promos ({len(display_promos)} displayed / {len(filtered)} matching)")

for p in display_promos:
    is_stitch = "stitched" in p["promo_type"]
    tag_prefix = "🔗 [MULTI-SEGMENT STITCH]" if is_stitch else "🎬 [CONTINUOUS CLIP]"
    expander_title = f"Rank #{p['rank']}: {tag_prefix} {p['header_hook']} — {p['archetype']} ({p['total_duration_sec']}s) ★ {p['virality_score']}/10"
    
    with st.expander(expander_title, expanded=(p["rank"] <= 3)):
        col_main, col_side = st.columns([2.5, 1])
        
        with col_main:
            st.markdown(f"**Funnel Target**: `{p['funnel_stage']}`")
            st.markdown(f"**0–3s Shock Hook**: {p['hook_summary']}")
            st.markdown(f"**Cliffhanger Cut Point**: {p['cliffhanger_summary']}")
            st.info(f"💡 **Why This Converts US Scrollers**: {p['why_it_works']}")
            
            # Segments timeline
            seg_texts = []
            for idx, s in enumerate(p["segments"]):
                seg_texts.append(f"**Segment #{idx+1}**: Ep {s['episode']} `[{s['start_time']} ➔ {s['end_time']}]` ({s['duration_seconds']}s)")
            st.markdown(" • " + "  ➔  ".join(seg_texts))

        with col_side:
            st.metric("Virality Score", f"★ {p['virality_score']}/10")
            st.markdown(f"- Hook Score: **{p['hook_score']}**")
            st.markdown(f"- Cliffhanger: **{p['cliffhanger_score']}**")
            st.markdown(f"- Cold Comprehension: **{p['cold_comprehension_score']}**")
            st.caption(f"Evaluator: `{p['evaluator_source']}`")
            st.caption(f"Promo ID: `{p['promo_id']}`")
