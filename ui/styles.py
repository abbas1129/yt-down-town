"""
=============================================================================
ui/styles.py
=============================================================================
Custom CSS injected into Streamlit's HTML for a premium dark-mode look.
=============================================================================
"""

import streamlit as st


def inject_vercel_analytics() -> None:
    """Inject Vercel Web Analytics script into the Streamlit page."""
    st.markdown(
        """
        <script defer src="https://cdn.vercel-insights.com/v1/script.js"></script>
        """,
        unsafe_allow_html=True,
    )


def inject_custom_css() -> None:
    """Inject the full custom CSS stylesheet into the Streamlit page."""
    st.markdown(
        """
        <style>
        /* ── Google Font ───────────────────────────────────────────────── */
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

        /* ── Global resets ─────────────────────────────────────────────── */
        html, body, [class*="css"] {
            font-family: 'Inter', sans-serif !important;
        }

        /* ── App background ─────────────────────────────────────────────── */
        .stApp {
            background: linear-gradient(135deg, #0d0d1a 0%, #111827 50%, #0a0f1e 100%);
            min-height: 100vh;
        }

        /* ── Header ─────────────────────────────────────────────────────── */
        .header-container {
            display: flex;
            align-items: center;
            gap: 1.2rem;
            padding: 1.5rem 0 0.5rem;
            border-bottom: 1px solid rgba(99,102,241,0.3);
            margin-bottom: 1.5rem;
        }
        .header-icon {
            font-size: 3rem;
            line-height: 1;
            filter: drop-shadow(0 0 12px rgba(99,102,241,0.7));
        }
        .header-text h1 {
            margin: 0;
            font-size: 2rem;
            font-weight: 700;
            background: linear-gradient(90deg, #818cf8, #c084fc, #f472b6);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        .header-text p {
            margin: 0.2rem 0 0;
            color: #94a3b8;
            font-size: 0.9rem;
            letter-spacing: 0.04em;
        }

        /* ── Sidebar ─────────────────────────────────────────────────────── */
        section[data-testid="stSidebar"] {
            background: rgba(17, 24, 39, 0.95) !important;
            border-right: 1px solid rgba(99,102,241,0.25) !important;
        }
        section[data-testid="stSidebar"] .stMarkdown h2 {
            color: #c084fc;
            font-size: 1.1rem;
            font-weight: 600;
        }

        /* ── Metric cards ────────────────────────────────────────────────── */
        .metric-card {
            background: rgba(30, 41, 59, 0.8);
            border: 1px solid rgba(99,102,241,0.3);
            border-radius: 12px;
            padding: 1rem 1.2rem;
            text-align: center;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .metric-card:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 24px rgba(99,102,241,0.2);
        }
        .metric-card .value {
            font-size: 2rem;
            font-weight: 700;
            color: #818cf8;
        }
        .metric-card .label {
            font-size: 0.8rem;
            color: #94a3b8;
            margin-top: 0.2rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        /* ── Video result cards ──────────────────────────────────────────── */
        .video-card {
            background: rgba(17, 24, 39, 0.9);
            border: 1px solid rgba(99,102,241,0.2);
            border-radius: 14px;
            padding: 1rem 1.2rem;
            margin-bottom: 0.75rem;
            transition: border-color 0.2s, box-shadow 0.2s;
        }
        .video-card:hover {
            border-color: rgba(99,102,241,0.5);
            box-shadow: 0 4px 20px rgba(99,102,241,0.15);
        }
        .video-card.success  { border-left: 4px solid #34d399; }
        .video-card.partial  { border-left: 4px solid #fbbf24; }
        .video-card.failed   { border-left: 4px solid #f87171; }
        .video-card .vc-title {
            font-weight: 600;
            font-size: 0.95rem;
            color: #e2e8f0;
            margin-bottom: 0.4rem;
        }
        .video-card .vc-meta {
            font-size: 0.78rem;
            color: #64748b;
        }
        .video-card .vc-badge {
            display: inline-block;
            padding: 0.15rem 0.55rem;
            border-radius: 999px;
            font-size: 0.7rem;
            font-weight: 600;
            margin-right: 0.4rem;
        }
        .badge-video   { background: rgba(52,211,153,0.15); color: #34d399; border: 1px solid #34d399; }
        .badge-txt     { background: rgba(96,165,250,0.15); color: #60a5fa; border: 1px solid #60a5fa; }
        .badge-missing { background: rgba(248,113,113,0.15); color: #f87171; border: 1px solid #f87171; }

        /* ── Log console ─────────────────────────────────────────────────── */
        .log-console {
            background: #080c14;
            border: 1px solid rgba(99,102,241,0.25);
            border-radius: 10px;
            padding: 1rem;
            max-height: 320px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 0.78rem;
            color: #94a3b8;
            line-height: 1.6;
        }
        .log-console .log-line { margin: 0; }
        .log-console .log-success { color: #34d399; }
        .log-console .log-error   { color: #f87171; }
        .log-console .log-warn    { color: #fbbf24; }
        .log-console .log-info    { color: #818cf8; }

        /* ── Progress bar override ───────────────────────────────────────── */
        .stProgress > div > div > div > div {
            background: linear-gradient(90deg, #6366f1, #c084fc) !important;
            border-radius: 999px !important;
        }

        /* ── Buttons ─────────────────────────────────────────────────────── */
        .stButton > button {
            background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
            letter-spacing: 0.03em !important;
            padding: 0.55rem 1.5rem !important;
            transition: opacity 0.2s, transform 0.2s !important;
        }
        .stButton > button:hover {
            opacity: 0.88 !important;
            transform: translateY(-1px) !important;
        }
        .stDownloadButton > button {
            background: linear-gradient(135deg, #0f766e, #0d9488) !important;
            color: white !important;
            border: none !important;
            border-radius: 10px !important;
            font-weight: 600 !important;
        }

        /* ── Text inputs / number inputs ──────────────────────────────────── */
        .stTextInput > div > div > input,
        .stNumberInput > div > div > input {
            background: rgba(30, 41, 59, 0.9) !important;
            border: 1px solid rgba(99,102,241,0.35) !important;
            border-radius: 8px !important;
            color: #e2e8f0 !important;
        }
        .stTextInput > div > div > input:focus,
        .stNumberInput > div > div > input:focus {
            border-color: #818cf8 !important;
            box-shadow: 0 0 0 2px rgba(99,102,241,0.25) !important;
        }

        /* ── Expander ─────────────────────────────────────────────────────── */
        .streamlit-expanderHeader {
            background: rgba(30,41,59,0.6) !important;
            border-radius: 8px !important;
            color: #c084fc !important;
            font-weight: 600 !important;
        }

        /* ── Divider ─────────────────────────────────────────────────────── */
        hr { border-color: rgba(99,102,241,0.2) !important; }

        /* ── Section headers ──────────────────────────────────────────────── */
        .section-header {
            font-size: 1.1rem;
            font-weight: 600;
            color: #c084fc;
            letter-spacing: 0.03em;
            margin: 1.2rem 0 0.6rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        /* ── Tooltip / info boxes ────────────────────────────────────────── */
        .info-box {
            background: rgba(99,102,241,0.1);
            border: 1px solid rgba(99,102,241,0.3);
            border-radius: 8px;
            padding: 0.7rem 1rem;
            font-size: 0.82rem;
            color: #94a3b8;
            margin: 0.5rem 0;
        }

        /* ── Scrollbar styling ──────────────────────────────────────────── */
        ::-webkit-scrollbar { width: 6px; height: 6px; }
        ::-webkit-scrollbar-track { background: rgba(17,24,39,0.5); }
        ::-webkit-scrollbar-thumb { background: rgba(99,102,241,0.4); border-radius: 999px; }
        ::-webkit-scrollbar-thumb:hover { background: rgba(99,102,241,0.7); }
        </style>
        """,
        unsafe_allow_html=True,
    )
