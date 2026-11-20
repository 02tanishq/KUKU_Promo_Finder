"""
Interactive Production Web Dashboard for Kuku AI Promo Engine.
Built using Python standard library http.server (Zero external pip dependencies).
Provides:
- Real-time ingestion of screenplay folders OR direct browser file upload for ANY show.
- Continuous Single-Segment vs Stitched Multi-Segment filtering.
- Top-N filtering (Top 3, Top 5, Top 10, Top 25, All).
- Funnel Stage & Archetype filtering.
- Duration range filtering & live dialogue keyword search.
- 1-click EDL / CapCut / Premiere video editor cutlist copy.
- 1-click CSV & JSON production exports.
"""

import http.server
import socketserver
import json
import os
import sys
import glob
import urllib.parse
from pathlib import Path

_root_dir = str(Path(__file__).resolve().parent.parent)
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

from promo_engine.pipeline import PromoPipeline

PORT = 8080
RAW_OUTPUTS_DIR = os.path.join(_root_dir, "raw_outputs")
RAW_OUTPUTS_JSON = os.path.join(RAW_OUTPUTS_DIR, "all_promos_ranked.json")
RAW_OUTPUTS_CSV = os.path.join(RAW_OUTPUTS_DIR, "all_promos_ranked.csv")
UPLOADS_DIR = os.path.join(_root_dir, "uploads")
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(RAW_OUTPUTS_DIR, exist_ok=True)

HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Kuku AI — Microdrama Promo Studio (Production Prototype)</title>
  <style>
    :root {
      --bg: #090d16;
      --card-bg: #121824;
      --panel-bg: #182234;
      --border: #26354a;
      --border-focus: #3b82f6;
      --text: #cbd5e1;
      --text-bright: #f8fafc;
      --text-muted: #8492a6;
      --accent-red: #ef4444;
      --accent-gold: #f59e0b;
      --accent-blue: #3b82f6;
      --accent-purple: #8b5cf6;
      --accent-green: #10b981;
    }
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; }
    body { background: var(--bg); color: var(--text); padding: 24px; line-height: 1.5; }
    
    /* Header */
    header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid var(--border); padding-bottom: 20px; margin-bottom: 24px; flex-wrap: wrap; gap: 16px; }
    .logo-container { display: flex; align-items: center; gap: 12px; }
    .brand-pill { background: linear-gradient(135deg, #ef4444, #b91c1c); color: white; padding: 3px 10px; border-radius: 6px; font-weight: 800; font-size: 13px; letter-spacing: 0.5px; }
    .brand-title { font-size: 22px; font-weight: 800; color: var(--text-bright); }
    .current-show-badge { background: #1e293b; border: 1px solid var(--border); padding: 6px 14px; border-radius: 20px; font-size: 13px; color: #94a3b8; }
    .current-show-badge strong { color: var(--text-bright); }

    /* Ingest & Run Panel */
    .ingest-card { background: var(--panel-bg); border: 1px solid var(--border); border-radius: 12px; padding: 20px; margin-bottom: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); }
    .ingest-header { display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
    .ingest-header h3 { font-size: 16px; color: var(--text-bright); display: flex; align-items: center; gap: 8px; }
    .toggle-icon { font-size: 14px; color: var(--accent-blue); }
    
    .ingest-body { margin-top: 18px; display: grid; grid-template-columns: 1fr 1fr; gap: 20px; border-top: 1px solid var(--border); padding-top: 18px; }
    .ingest-column { display: flex; flex-direction: column; gap: 14px; }
    .form-group label { display: block; font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-bottom: 6px; }
    .form-control { width: 100%; background: #0d131f; border: 1px solid var(--border); color: var(--text-bright); padding: 10px 14px; border-radius: 8px; font-size: 14px; outline: none; }
    .form-control:focus { border-color: var(--border-focus); }
    
    .dropzone { border: 2px dashed var(--border); border-radius: 8px; padding: 24px; text-align: center; background: #0d131f; cursor: pointer; transition: border-color 0.2s; }
    .dropzone:hover { border-color: var(--accent-blue); }
    .dropzone-text { font-size: 13px; color: var(--text-muted); }
    .dropzone-highlight { color: var(--accent-blue); font-weight: 600; }

    .run-btn-row { grid-column: span 2; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 16px; margin-top: 8px; }
    .btn { display: inline-flex; align-items: center; gap: 8px; padding: 10px 18px; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; border: none; transition: all 0.15s ease; }
    .btn-primary { background: linear-gradient(135deg, #ef4444, #dc2626); color: white; }
    .btn-primary:hover { opacity: 0.92; transform: translateY(-1px); }
    .btn-secondary { background: #1e293b; color: var(--text-bright); border: 1px solid var(--border); }
    .btn-secondary:hover { background: #283548; }

    /* Stats Overview */
    .stats-bar { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; margin-bottom: 24px; }
    .stat-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 10px; padding: 16px; position: relative; overflow: hidden; }
    .stat-label { font-size: 11px; text-transform: uppercase; font-weight: 700; color: var(--text-muted); letter-spacing: 0.5px; }
    .stat-val { font-size: 24px; font-weight: 800; color: var(--text-bright); margin-top: 4px; }

    /* Interactive Filters Bar */
    .controls-panel { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 18px; margin-bottom: 24px; display: flex; flex-direction: column; gap: 16px; }
    .filter-row { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; }
    
    .pill-group { display: inline-flex; background: #0d131f; border: 1px solid var(--border); border-radius: 8px; padding: 3px; gap: 4px; }
    .pill-btn { background: transparent; border: none; color: var(--text-muted); padding: 6px 14px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.15s ease; }
    .pill-btn.active { background: var(--accent-blue); color: white; }
    .pill-btn.active-purple { background: var(--accent-purple); color: white; }

    .search-box { flex: 1; min-width: 240px; position: relative; }
    .search-input { width: 100%; background: #0d131f; border: 1px solid var(--border); color: var(--text-bright); padding: 9px 14px 9px 36px; border-radius: 8px; font-size: 13px; outline: none; }
    .search-input:focus { border-color: var(--accent-blue); }
    .search-icon { position: absolute; left: 12px; top: 10px; font-size: 14px; color: var(--text-muted); }

    /* Promo Cards List */
    .promo-grid { display: flex; flex-direction: column; gap: 18px; }
    .promo-card { background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 22px; transition: border-color 0.15s ease; }
    .promo-card:hover { border-color: #3b82f6; }
    
    .card-top { display: flex; justify-content: space-between; align-items: flex-start; margin-bottom: 14px; flex-wrap: wrap; gap: 10px; }
    .rank-tag { background: #ef4444; color: white; padding: 4px 10px; border-radius: 6px; font-weight: 800; font-size: 14px; display: inline-flex; align-items: center; gap: 4px; }
    .format-tag { padding: 4px 10px; border-radius: 6px; font-weight: 700; font-size: 12px; text-transform: uppercase; letter-spacing: 0.5px; }
    .format-single { background: rgba(59, 130, 246, 0.15); color: #60a5fa; border: 1px solid rgba(59, 130, 246, 0.35); }
    .format-stitch { background: rgba(139, 92, 246, 0.2); color: #c084fc; border: 1px solid rgba(139, 92, 246, 0.45); }
    
    .header-hook-text { font-size: 19px; font-weight: 800; color: var(--accent-gold); letter-spacing: 0.5px; margin-left: 8px; }
    .archetype-text { font-size: 13px; color: var(--text-muted); margin-left: 8px; }
    
    .score-badge { font-weight: 800; font-size: 16px; color: var(--accent-gold); display: inline-flex; align-items: center; gap: 4px; background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); padding: 4px 10px; border-radius: 6px; }

    /* Segment Visualizer */
    .segment-strip { background: #0a0e17; border: 1px solid var(--border); border-radius: 8px; padding: 12px 16px; margin: 14px 0; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; font-family: monospace; font-size: 13px; }
    .seg-badge { background: #1e293b; color: #93c5fd; padding: 4px 10px; border-radius: 4px; }
    .stitch-indicator { color: var(--accent-purple); font-weight: bold; }

    /* 3-Beat Timeline */
    .beat-timeline { display: flex; height: 10px; width: 100%; border-radius: 5px; overflow: hidden; margin: 12px 0 16px 0; background: #1e293b; }
    .beat-hook { background: #ef4444; width: 15%; title: "0-3s Shock Hook"; }
    .beat-escalation { background: #3b82f6; width: 70%; title: "15-35s Escalation"; }
    .beat-cliff { background: #f59e0b; width: 15%; title: "Peak Cliffhanger Cut"; }

    /* Details Grid */
    .details-row { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-top: 14px; }
    .detail-cell { background: #0d131f; border: 1px solid var(--border); border-radius: 8px; padding: 14px; }
    .cell-title { font-size: 11px; text-transform: uppercase; font-weight: 700; color: var(--text-muted); margin-bottom: 6px; display: flex; align-items: center; gap: 6px; }
    .cell-content { font-size: 13px; color: var(--text-bright); }
    
    .why-it-works-box { grid-column: span 2; background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.25); border-radius: 8px; padding: 12px 16px; color: #34d399; font-size: 13px; display: flex; align-items: center; gap: 8px; margin-top: 6px; }

    /* Card Actions */
    .card-footer { display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--border); padding-top: 14px; margin-top: 16px; }
    .source-label { font-size: 12px; color: var(--text-muted); font-family: monospace; }
    .card-btn-group { display: flex; gap: 8px; }
    .mini-btn { background: #1e293b; border: 1px solid var(--border); color: var(--text-bright); padding: 5px 12px; border-radius: 6px; font-size: 12px; font-weight: 600; cursor: pointer; transition: all 0.15s ease; }
    .mini-btn:hover { background: #2d3b4f; }

    /* Notification / Toast */
    #toast { position: fixed; bottom: 24px; right: 24px; background: #10b981; color: white; padding: 12px 20px; border-radius: 8px; font-size: 14px; font-weight: 600; box-shadow: 0 4px 14px rgba(0,0,0,0.4); display: none; z-index: 1000; }
    
    /* Loading Spinner */
    .spinner { display: inline-block; width: 16px; height: 16px; border: 2px solid rgba(255,255,255,0.3); border-radius: 50%; border-top-color: white; animation: spin 0.8s linear infinite; }
    @keyframes spin { to { transform: rotate(360deg); } }
  </style>
</head>
<body>

  <!-- Top Header -->
  <header>
    <div class="logo-container">
      <div class="brand-pill">KUKU AI</div>
      <div class="brand-title">Microdrama Video Promo Studio</div>
    </div>
    <div style="display: flex; align-items: center; gap: 12px;">
      <div class="current-show-badge" id="showBadge">
        Active Show: <strong>I Married a Broken Soldier. He was a Duke</strong> (50 Episodes)
      </div>
      <button class="btn btn-secondary" onclick="toggleIngestPanel()">
        📁 Ingest New Show
      </button>
    </div>
  </header>

  <!-- Ingest & Production Run Panel -->
  <div class="ingest-card" id="ingestPanel" style="display: none;">
    <div class="ingest-header" onclick="toggleIngestPanel()">
      <h3>⚡ Ingest Screenplays for ANY Show (Dynamic Production Pipeline)</h3>
      <span class="toggle-icon">✕ Close Panel</span>
    </div>
    
    <div class="ingest-body">
      <!-- Option A: File Upload -->
      <div class="ingest-column">
        <div class="form-group">
          <label>Option 1: Upload Screenplay Files (.txt)</label>
          <div class="dropzone" onclick="document.getElementById('fileInput').click()">
            <div style="font-size: 28px; margin-bottom: 8px;">📤</div>
            <div class="dropzone-text">Click to browse or drop <span class="dropzone-highlight">.txt screenplay files</span> here</div>
            <div style="font-size: 11px; color: #64748b; margin-top: 4px;">Supports single or multi-episode screenplay batches</div>
          </div>
          <input type="file" id="fileInput" multiple accept=".txt" style="display: none;" onchange="handleFileSelection(this)">
          <div id="fileSelectionInfo" style="font-size: 12px; color: #34d399; margin-top: 6px;"></div>
        </div>

        <div class="form-group">
          <label>Show Name / Title</label>
          <input type="text" id="showNameInput" class="form-control" placeholder="e.g. The Alpha's Silent Bride" value="I Married a Broken Soldier. He was a Duke">
        </div>
      </div>

      <!-- Option B: Local Directory Path & Settings -->
      <div class="ingest-column">
        <div class="form-group">
          <label>Option 2: Or Path to Screenplay Directory on Server</label>
          <input type="text" id="dirInput" class="form-control" value="I Married a Broken Soldier. He was a Duke" placeholder="Folder containing episode .txt files">
        </div>

        <div class="form-group">
          <label>Evaluator Model</label>
          <select id="modelSelect" class="form-control">
            <option value="auto">Groq LPU (openai/gpt-oss-120b - High Speed / Reasoning)</option>
            <option value="heuristic">ReelShort Empirical Heuristic Engine (Zero Cost / Instant)</option>
            <option value="grok-2-latest">xAI Grok-2 (grok-2-latest)</option>
            <option value="gemini-2.0-flash">Google Gemini 2.0 Flash</option>
            <option value="gpt-4o">OpenAI GPT-4o</option>
          </select>
        </div>

        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
          <div class="form-group">
            <label>Min Duration (sec)</label>
            <input type="number" id="minDurInput" class="form-control" value="20" min="15" max="40">
          </div>
          <div class="form-group">
            <label>Max Duration (sec)</label>
            <input type="number" id="maxDurInput" class="form-control" value="60" min="40" max="90">
          </div>
        </div>
      </div>

      <div class="run-btn-row">
        <div style="font-size: 13px; color: var(--text-muted);" id="runStatusText">
          Ready to extract 20–60s hooks & cliffhangers from microdrama scripts.
        </div>
        <button class="btn btn-primary" id="runPipelineBtn" onclick="runExtractionPipeline()">
          <span>🚀 Run Promo Extraction Pipeline</span>
        </button>
      </div>
    </div>
  </div>

  <!-- Stats Overview Bar -->
  <div class="stats-bar">
    <div class="stat-card">
      <div class="stat-label">Total Promos Found</div>
      <div class="stat-val" id="totalPromosVal">142</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Continuous Clips</div>
      <div class="stat-val" id="continuousCountVal" style="color: #60a5fa;">141</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Stitched Multi-Segment</div>
      <div class="stat-val" id="stitchedCountVal" style="color: #c084fc;">1</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Stage 1: Cold UA</div>
      <div class="stat-val" id="stage1CountVal" style="color: #f87171;">Top Priority</div>
    </div>
    <div class="stat-card">
      <div class="stat-label">Average Duration</div>
      <div class="stat-val" id="avgDurationVal" style="color: var(--accent-gold);">40.8s</div>
    </div>
  </div>

  <!-- Interactive Controls & Filters Panel -->
  <div class="controls-panel">
    <!-- Filter Row 1: Clip Format & Top N Selection -->
    <div class="filter-row">
      <div>
        <span style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-right: 8px;">Clip Format:</span>
        <div class="pill-group" id="formatPills">
          <button class="pill-btn active" onclick="setClipFormat('all', this)">All Formats</button>
          <button class="pill-btn" onclick="setClipFormat('single_segment', this)">🎬 Continuous Clips Only</button>
          <button class="pill-btn" onclick="setClipFormat('stitched_segment', this)">🔗 Multi-Segment Stitches</button>
        </div>
      </div>

      <div>
        <span style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: var(--text-muted); margin-right: 8px;">Show Top:</span>
        <div class="pill-group" id="topNPills">
          <button class="pill-btn" onclick="setTopN(3, this)">Top 3</button>
          <button class="pill-btn active" onclick="setTopN(5, this)">Top 5 (Priority)</button>
          <button class="pill-btn" onclick="setTopN(10, this)">Top 10</button>
          <button class="pill-btn" onclick="setTopN(25, this)">Top 25</button>
          <button class="pill-btn" onclick="setTopN('all', this)">All (142)</button>
        </div>
      </div>

      <div class="search-box">
        <span class="search-icon">🔍</span>
        <input type="text" id="searchInput" class="search-input" placeholder="Search by dialogue, character, or promo ID..." oninput="applyFilters()">
      </div>
    </div>

    <!-- Filter Row 2: Funnel Stage, Archetype & Duration -->
    <div class="filter-row" style="border-top: 1px solid var(--border); padding-top: 12px;">
      <label style="font-size: 13px; color: var(--text-muted); display: flex; align-items: center; gap: 6px;">
        Funnel Stage:
        <select id="stageFilter" class="form-control" style="width: auto; padding: 6px 10px;" onchange="applyFilters()">
          <option value="all">All Funnel Stages</option>
          <option value="Stage 1">Stage 1: Top-of-Funnel (Post First - Cold UA)</option>
          <option value="Stage 2">Stage 2: Mid-Funnel (Post Second - Protector Conflict)</option>
          <option value="Stage 3">Stage 3: Paywall Teaser (Post Third - Duke Reveal / Execution)</option>
        </select>
      </label>

      <label style="font-size: 13px; color: var(--text-muted); display: flex; align-items: center; gap: 6px;">
        Archetype:
        <select id="archetypeFilter" class="form-control" style="width: auto; padding: 6px 10px;" onchange="applyFilters()">
          <option value="all">All Archetypes</option>
          <option value="Proposal">Heroic Proposal / Impromptu Claim</option>
          <option value="Altar Betrayal">Altar Betrayal & Public Humiliation</option>
          <option value="Retribution">Protector Retribution ("Who Did This?")</option>
          <option value="Status Inversion">Status Inversion & Duke Reveal</option>
          <option value="Scaffold">Life-or-Death Scaffold Climax</option>
        </select>
      </label>

      <label style="font-size: 13px; color: var(--text-muted); display: flex; align-items: center; gap: 6px;">
        Duration:
        <select id="durationRangeFilter" class="form-control" style="width: auto; padding: 6px 10px;" onchange="applyFilters()">
          <option value="all">All Durations (20–60s)</option>
          <option value="short">⚡ Snappy Short (&lt; 35s)</option>
          <option value="medium">🎯 Sweetspot (35s – 48s)</option>
          <option value="long">📖 Full Narrative (48s – 60s)</option>
        </select>
      </label>

      <label style="font-size: 13px; color: var(--text-muted); display: flex; align-items: center; gap: 6px;">
        Sort Order:
        <select id="sortOrderSelect" class="form-control" style="width: auto; padding: 6px 10px;" onchange="applyFilters()">
          <option value="funnel">🚀 Campaign Release Order (Post First)</option>
          <option value="virality">★ Pure Virality Score (Highest First)</option>
        </select>
      </label>

      <!-- Production Export Buttons -->
      <div style="margin-left: auto; display: flex; gap: 8px;">
        <button class="btn btn-secondary" onclick="exportData('csv')">
          📥 Export CSV
        </button>
        <button class="btn btn-secondary" onclick="exportData('json')">
          📥 Export JSON
        </button>
        <button class="btn btn-secondary" onclick="copyFullCampaignCutlist()">
          📋 Copy All Cutlists
        </button>
      </div>
    </div>
  </div>

  <!-- Promos Grid Container -->
  <div class="promo-grid" id="promoContainer">
    <!-- Populated by JavaScript -->
  </div>

  <!-- Toast Notification -->
  <div id="toast">Cutlist copied to clipboard!</div>

  <script>
    let allPromos = [];
    let currentClipFormat = 'all';
    let currentTopN = 5;
    let uploadedFilesCache = [];

    async function initDashboard() {
      await loadPromos();
    }

    async function loadPromos() {
      try {
        const resp = await fetch('/api/promos');
        allPromos = await resp.json();
        updateStats(allPromos);
        applyFilters();
      } catch (err) {
        console.error('Failed to load promos:', err);
      }
    }

    function updateStats(promos) {
      document.getElementById('totalPromosVal').innerText = promos.length;
      
      const continuous = promos.filter(p => !p.promo_type.includes('stitched'));
      const stitched = promos.filter(p => p.promo_type.includes('stitched'));
      
      document.getElementById('continuousCountVal').innerText = continuous.length;
      document.getElementById('stitchedCountVal').innerText = stitched.length;
      
      if (promos.length > 0) {
        const avgDur = (promos.reduce((acc, p) => acc + p.total_duration_sec, 0) / promos.length).toFixed(1);
        document.getElementById('avgDurationVal').innerText = avgDur + 's';
      }
    }

    function setClipFormat(format, btnElem) {
      currentClipFormat = format;
      const pills = document.querySelectorAll('#formatPills .pill-btn');
      pills.forEach(p => p.classList.remove('active', 'active-purple'));
      if (format === 'stitched_segment') {
        btnElem.classList.add('active-purple');
      } else {
        btnElem.classList.add('active');
      }
      applyFilters();
    }

    function setTopN(n, btnElem) {
      currentTopN = n;
      const pills = document.querySelectorAll('#topNPills .pill-btn');
      pills.forEach(p => p.classList.remove('active'));
      btnElem.classList.add('active');
      applyFilters();
    }

    function applyFilters() {
      const stage = document.getElementById('stageFilter').value;
      const arch = document.getElementById('archetypeFilter').value;
      const durRange = document.getElementById('durationRangeFilter').value;
      const search = document.getElementById('searchInput').value.toLowerCase().trim();

      let filtered = allPromos.filter(p => {
        // Format filter
        if (currentClipFormat === 'single_segment' && p.promo_type.includes('stitched')) return false;
        if (currentClipFormat === 'stitched_segment' && !p.promo_type.includes('stitched')) return false;

        // Funnel Stage filter
        if (stage !== 'all' && !p.funnel_stage.includes(stage)) return false;

        // Archetype filter
        if (arch !== 'all' && !p.archetype.toLowerCase().includes(arch.toLowerCase())) return false;

        // Duration filter
        if (durRange === 'short' && p.total_duration_sec >= 35) return false;
        if (durRange === 'medium' && (p.total_duration_sec < 35 || p.total_duration_sec > 48)) return false;
        if (durRange === 'long' && p.total_duration_sec <= 48) return false;

        // Search text
        if (search) {
          const haystack = (
            p.promo_id + ' ' +
            p.header_hook + ' ' +
            p.archetype + ' ' +
            p.hook_summary + ' ' +
            p.cliffhanger_summary + ' ' +
            p.why_it_works
          ).toLowerCase();
          if (!haystack.includes(search)) return false;
        }

        return true;
      });

      // Sort order
      const sortOrder = document.getElementById('sortOrderSelect') ? document.getElementById('sortOrderSelect').value : 'funnel';
      if (sortOrder === 'virality') {
        filtered.sort((a, b) => b.virality_score - a.virality_score);
      } else {
        filtered.sort((a, b) => a.rank - b.rank);
      }

      // Slice Top N if selected
      if (currentTopN !== 'all' && typeof currentTopN === 'number') {
        filtered = filtered.slice(0, currentTopN);
      }

      renderPromos(filtered);
    }

    function renderPromos(promos) {
      const container = document.getElementById('promoContainer');
      container.innerHTML = '';

      if (promos.length === 0) {
        container.innerHTML = `
          <div style="background: var(--card-bg); border: 1px solid var(--border); border-radius: 12px; padding: 60px 20px; text-align: center; color: var(--text-muted);">
            <div style="font-size: 32px; margin-bottom: 12px;">🔍</div>
            <div style="font-size: 16px; font-weight: 600; color: var(--text-bright);">No Promos Match Selected Filters</div>
            <div style="font-size: 13px; margin-top: 6px;">Try expanding your filter options or searching for different keywords.</div>
          </div>
        `;
        return;
      }

      promos.forEach(p => {
        const isStitch = p.promo_type.includes('stitched');
        const formatBadgeClass = isStitch ? 'format-stitch' : 'format-single';
        const formatBadgeText = isStitch ? '🔗 MULTI-SEGMENT STITCH' : '🎬 CONTINUOUS CLIP';

        let funnelPillColor = '#ef4444';
        if (p.funnel_stage.includes('Stage 2')) funnelPillColor = '#3b82f6';
        if (p.funnel_stage.includes('Stage 3')) funnelPillColor = '#f59e0b';

        // Segment representation
        let segHtml = '';
        p.segments.forEach((s, idx) => {
          if (idx > 0) {
            segHtml += `<span class="stitch-indicator"> ➔ [Stitch Cut] ➔ </span>`;
          }
          segHtml += `
            <span class="seg-badge">
              <strong>Ep ${s.episode}</strong>: ${s.start_time} - ${s.end_time} (${s.duration_seconds}s)
            </span>
          `;
        });

        const card = document.createElement('div');
        card.className = 'promo-card';
        card.innerHTML = `
          <div class="card-top">
            <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px;">
              <span class="rank-tag">Rank #${p.rank}</span>
              <span class="format-tag ${formatBadgeClass}">${formatBadgeText}</span>
              <span class="header-hook-text">${p.header_hook}</span>
              <span class="archetype-text">• ${p.archetype}</span>
            </div>
            <div style="display: flex; align-items: center; gap: 12px;">
              <span style="font-size: 12px; font-weight: 700; color: ${funnelPillColor}; background: rgba(255,255,255,0.06); padding: 4px 10px; border-radius: 4px;">
                ${p.funnel_stage.split('(')[0]}
              </span>
              <span class="score-badge">★ ${p.virality_score} <span style="font-size: 12px; color: var(--text-muted);">/10</span></span>
            </div>
          </div>

          <!-- Video Editor Timeline Strip -->
          <div class="segment-strip">
            <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 8px;">
              <span style="color: var(--text-muted); font-size: 11px; text-transform: uppercase; font-weight: 700;">Cut Sequence:</span>
              ${segHtml}
            </div>
            <div>
              <strong style="color: var(--text-bright);">${p.total_duration_sec}s Total Duration</strong>
            </div>
          </div>

          <!-- 3-Beat Visual Progression -->
          <div class="beat-timeline" title="3-Beat ReelShort Timeline: 0-3s Shock Hook | 15-35s Escalation | Cliffhanger Cut">
            <div class="beat-hook"></div>
            <div class="beat-escalation"></div>
            <div class="beat-cliff"></div>
          </div>

          <!-- Details Grid -->
          <div class="details-row">
            <div class="detail-cell">
              <div class="cell-title">
                <span style="color: #ef4444;">●</span> 0–3s Opening Shock Hook (Thumb-Stopper)
              </div>
              <div class="cell-content">${p.hook_summary}</div>
            </div>
            <div class="detail-cell">
              <div class="cell-title">
                <span style="color: #f59e0b;">●</span> Cliffhanger Snapping Point (Unexploded Bomb)
              </div>
              <div class="cell-content">${p.cliffhanger_summary}</div>
            </div>
            
            <div class="why-it-works-box">
              <span style="font-size: 16px;">💡</span>
              <div>
                <strong>Why This Converts US Scrollers:</strong> ${p.why_it_works}
              </div>
            </div>
          </div>

          <!-- Card Actions -->
          <div class="card-footer">
            <div class="source-label">
              Engine: <span style="color: #94a3b8;">${p.evaluator_source}</span> | ID: <code>${p.promo_id}</code>
            </div>
            <div class="card-btn-group">
              <button class="mini-btn" onclick="copyPromoCutlist('${p.promo_id}')">
                📋 Copy Cutlist
              </button>
              <button class="mini-btn" onclick="copyHookText('${p.header_hook}')">
                🏷️ Copy On-Screen Title
              </button>
            </div>
          </div>
        `;

        container.appendChild(card);
      });
    }

    function toggleIngestPanel() {
      const panel = document.getElementById('ingestPanel');
      panel.style.display = (panel.style.display === 'none' || panel.style.display === '') ? 'block' : 'none';
    }

    function handleFileSelection(input) {
      const files = Array.from(input.files);
      if (files.length === 0) return;
      uploadedFilesCache = files;
      document.getElementById('fileSelectionInfo').innerText = `✓ Selected ${files.length} screenplay file(s): ` + files.slice(0, 3).map(f => f.name).join(', ') + (files.length > 3 ? ` + ${files.length - 3} more` : '');
    }

    async function runExtractionPipeline() {
      const btn = document.getElementById('runPipelineBtn');
      const statusText = document.getElementById('runStatusText');
      
      const showName = document.getElementById('showNameInput').value.trim() || 'Uploaded Show';
      const dirInput = document.getElementById('dirInput').value.trim();
      const model = document.getElementById('modelSelect').value;
      const minDur = parseFloat(document.getElementById('minDurInput').value) || 20.0;
      const maxDur = parseFloat(document.getElementById('maxDurInput').value) || 60.0;

      btn.disabled = true;
      btn.innerHTML = `<span class="spinner"></span> <span>Analyzing Screenplays...</span>`;
      statusText.innerText = 'Extracting 0-3s hooks, evaluating pacing, and ranking promos...';

      try {
        let resp;
        if (uploadedFilesCache.length > 0) {
          // Send files content as JSON payload
          statusText.innerText = `Reading ${uploadedFilesCache.length} screenplay file(s)...`;
          const filePayloads = [];
          for (const file of uploadedFilesCache) {
            const content = await file.text();
            filePayloads.push({ filename: file.name, content: content });
          }

          resp = await fetch('/api/upload_and_run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: jsonStringifySafe({
              show_name: showName,
              files: filePayloads,
              model: model,
              min_duration: minDur,
              max_duration: maxDur
            })
          });
        } else {
          // Run on server directory
          resp = await fetch('/api/run', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              input_dir: dirInput,
              model: model,
              min_duration: minDur,
              max_duration: maxDur
            })
          });
        }

        const data = await resp.json();
        if (data.status === 'success') {
          allPromos = data.promos;
          document.getElementById('showBadge').innerHTML = `Active Show: <strong>${showName}</strong> (${data.episode_count || 'Multi'} Episodes)`;
          updateStats(allPromos);
          applyFilters();
          statusText.innerText = `🎉 Success! Found and ranked ${allPromos.length} promos in ${data.runtime_seconds || 1.2}s!`;
          showToast(`Successfully extracted ${allPromos.length} promos!`);
          toggleIngestPanel();
        } else {
          statusText.innerText = '⚠️ Processing notice: ' + (data.message || 'Check terminal logs');
          alert('Error: ' + data.message);
        }
      } catch (err) {
        statusText.innerText = 'Error connecting to pipeline: ' + err.message;
        alert('Pipeline execution error: ' + err.message);
      } finally {
        btn.disabled = false;
        btn.innerHTML = `<span>🚀 Run Promo Extraction Pipeline</span>`;
      }
    }

    function jsonStringifySafe(obj) {
      return JSON.stringify(obj);
    }

    function copyPromoCutlist(promoId) {
      const p = allPromos.find(x => x.promo_id === promoId);
      if (!p) return;

      let cutlistText = `=== PROMO CUTLIST: ${p.header_hook} [${p.promo_id}] ===\n`;
      cutlistText += `Format: ${p.promo_type} | Duration: ${p.total_duration_sec}s | Score: ${p.virality_score}/10\n`;
      cutlistText += `Funnel Stage: ${p.funnel_stage}\n`;
      cutlistText += `Archetype: ${p.archetype}\n\n`;
      cutlistText += `TIMESTAMPS FOR PREMIERE / CAPCUT:\n`;
      p.segments.forEach((s, idx) => {
        cutlistText += `  Segment #${idx + 1}: Episode ${s.episode} | IN: ${s.start_time} ➔ OUT: ${s.end_time} (${s.duration_seconds}s)\n`;
      });
      cutlistText += `\n0-3s HOOK: ${p.hook_summary}\n`;
      cutlistText += `CLIFFHANGER CUT: ${p.cliffhanger_summary}\n`;
      cutlistText += `WHY IT WORKS: ${p.why_it_works}\n`;

      navigator.clipboard.writeText(cutlistText).then(() => {
        showToast(`Copied cutlist for "${p.header_hook}"!`);
      });
    }

    function copyHookText(hookText) {
      navigator.clipboard.writeText(hookText).then(() => {
        showToast(`Copied On-Screen Title "${hookText}"!`);
      });
    }

    function copyFullCampaignCutlist() {
      if (allPromos.length === 0) return;
      let text = `=== KUKU AI MASTER PROMO CAMPAIGN CUTLIST ===\n`;
      text += `Total Promos: ${allPromos.length} | Generated for US Marketing\n\n`;
      allPromos.slice(0, 10).forEach(p => {
        text += `[Rank #${p.rank}] ${p.header_hook} (${p.total_duration_sec}s, ${p.funnel_stage.split('(')[0].trim()})\n`;
        p.segments.forEach(s => {
          text += `   Ep ${s.episode} [${s.start_time} - ${s.end_time}]\n`;
        });
        text += `\n`;
      });
      navigator.clipboard.writeText(text).then(() => {
        showToast('Copied Master Campaign Cutlist to clipboard!');
      });
    }

    function exportData(format) {
      if (format === 'csv') {
        window.location.href = '/api/export_csv';
      } else {
        window.location.href = '/api/export_json';
      }
    }

    function showToast(msg) {
      const t = document.getElementById('toast');
      t.innerText = msg;
      t.style.display = 'block';
      setTimeout(() => { t.style.display = 'none'; }, 3000);
    }

    window.onload = initDashboard;
  </script>
</body>
</html>
"""


class PromoDashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        
        if parsed.path in ("/", "/index.html"):
            content = HTML_TEMPLATE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        elif parsed.path == "/api/promos":
            if os.path.exists(RAW_OUTPUTS_JSON):
                with open(RAW_OUTPUTS_JSON, "rb") as f:
                    content = f.read()
            else:
                content = b"[]"
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        elif parsed.path == "/api/export_csv":
            if os.path.exists(RAW_OUTPUTS_CSV):
                with open(RAW_OUTPUTS_CSV, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "text/csv; charset=utf-8")
                self.send_header("Content-Disposition", "attachment; filename=kuku_promos_ranked.csv")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "CSV file not found")

        elif parsed.path == "/api/export_json":
            if os.path.exists(RAW_OUTPUTS_JSON):
                with open(RAW_OUTPUTS_JSON, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Content-Disposition", "attachment; filename=kuku_promos_ranked.json")
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "JSON file not found")

        else:
            super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        post_data = self.rfile.read(content_length)

        try:
            req_json = json.loads(post_data.decode("utf-8"))
        except Exception as e:
            self._send_json_response({"status": "error", "message": f"Invalid JSON payload: {e}"}, status_code=400)
            return

        if parsed.path == "/api/run":
            # Run pipeline on server directory
            input_dir = req_json.get("input_dir", "I Married a Broken Soldier. He was a Duke")
            model = req_json.get("model", "auto")
            min_dur = float(req_json.get("min_duration", 20.0))
            max_dur = float(req_json.get("max_duration", 60.0))

            if not os.path.isabs(input_dir):
                input_dir = os.path.join(_root_dir, input_dir)

            if not os.path.exists(input_dir):
                self._send_json_response({"status": "error", "message": f"Directory not found: {input_dir}"}, status_code=404)
                return

            try:
                pipeline = PromoPipeline(model_name=model, min_duration=min_dur, max_duration=max_dur)
                promos = pipeline.process_directory(input_dir, output_dir=RAW_OUTPUTS_DIR)
                
                # Count episodes
                txt_files = glob.glob(os.path.join(input_dir, "*.txt"))
                
                self._send_json_response({
                    "status": "success",
                    "episode_count": len(txt_files),
                    "promos": [p.to_dict() for p in promos]
                })
            except Exception as e:
                self._send_json_response({"status": "error", "message": str(e)}, status_code=500)

        elif parsed.path == "/api/upload_and_run":
            # User uploaded raw files via the browser
            show_name = req_json.get("show_name", "Uploaded Show").strip()
            # Clean folder name
            clean_show_name = "".join(c for c in show_name if c.isalnum() or c in (" ", "_", "-")).strip() or "Uploaded_Show"
            target_show_dir = os.path.join(UPLOADS_DIR, clean_show_name)
            os.makedirs(target_show_dir, exist_ok=True)

            files = req_json.get("files", [])
            if not files:
                self._send_json_response({"status": "error", "message": "No files provided in upload"}, status_code=400)
                return

            # Save uploaded screenplay text files
            for file_info in files:
                fname = os.path.basename(file_info.get("filename", "episode.txt"))
                content = file_info.get("content", "")
                fpath = os.path.join(target_show_dir, fname)
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(content)

            model = req_json.get("model", "auto")
            min_dur = float(req_json.get("min_duration", 20.0))
            max_dur = float(req_json.get("max_duration", 60.0))

            try:
                pipeline = PromoPipeline(model_name=model, min_duration=min_dur, max_duration=max_dur)
                promos = pipeline.process_directory(target_show_dir, output_dir=RAW_OUTPUTS_DIR)
                
                self._send_json_response({
                    "status": "success",
                    "episode_count": len(files),
                    "promos": [p.to_dict() for p in promos]
                })
            except Exception as e:
                self._send_json_response({"status": "error", "message": str(e)}, status_code=500)
        else:
            self.send_error(404, "Endpoint not found")

    def _send_json_response(self, data: dict, status_code: int = 200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def run_server(port=PORT):
    import socket
    server = None
    active_port = port
    for p in [port, 8081, 8082, 8501]:
        try:
            test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_sock.bind(("", p))
            test_sock.close()
            server = http.server.ThreadingHTTPServer(("", p), PromoDashboardHandler)
            active_port = p
            break
        except OSError:
            continue

    if server is None:
        print(f"[!] Could not bind to port {port} or fallback ports.", flush=True)
        return

    with server:
        print(f"\n=======================================================", flush=True)
        print(f"🚀 Kuku AI Promo Dashboard running on: http://localhost:{active_port}", flush=True)
        print(f"   Open in your browser to inspect & run promo extraction interactively!", flush=True)
        print(f"=======================================================\n", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down dashboard server.", flush=True)


if __name__ == "__main__":
    run_server()
