import streamlit as st
import pandas as pd
import requests
import re
import time
import numpy as np
import altair as alt
from fuzzywuzzy import process as fw_process

# --- CONFIGURATION ---
st.set_page_config(
    page_title="DDI Analysis Tool", 
    layout="wide",
    page_icon="💊",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS (HTML5 LOOK & FEEL) ---
st.markdown("""
    <style>
    /* Main Background - Slate 50 */
    .stApp {
        background-color: #f8fafc;
        color: #1e293b;
    }
    
    /* Sidebar Background - White */
    [data-testid="stSidebar"] {
        background-color: #ffffff;
        border-right: 1px solid #e2e8f0;
    }

    /* Navbar-like Header */
    .main-header {
        background-color: white;
        padding: 1.5rem 2rem;
        border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05), 0 2px 4px -1px rgba(0, 0, 0, 0.03);
        margin-bottom: 2rem;
        border: 1px solid #f1f5f9;
        display: flex;
        align-items: center;
        gap: 1rem;
    }
    
    /* Metric Cards Styling */
    div[data-testid="stMetric"] {
        background-color: white;
        padding: 1.25rem;
        border-radius: 12px;
        border: 1px solid #e2e8f0;
        box-shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px -1px rgba(0, 0, 0, 0.1);
        transition: all 0.2s ease;
    }
    div[data-testid="stMetric"]:hover {
        border-color: #3b82f6;
        transform: translateY(-2px);
    }
    
    /* Tabs Styling */
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        border-bottom: 1px solid #e2e8f0;
    }
    .stTabs [data-baseweb="tab"] {
        height: 3rem;
        white-space: pre-wrap;
        background-color: transparent;
        border-radius: 4px 4px 0 0;
        color: #64748b;
        font-weight: 600;
    }
    .stTabs [aria-selected="true"] {
        color: #2563eb; /* Blue 600 */
        border-bottom-color: #2563eb;
    }
    </style>
""", unsafe_allow_html=True)

# --- DATABASE LOADING LOGIC ---
def load_db_logic():
    """Attempts to load external DB, falls back to Mock DB."""
    try:
        import structured_drug_db
        from structured_drug_db import get_drug_by_name
        return True, get_drug_by_name
    except ImportError:
        # Simplified Fallback
        return False, None

is_external_db, get_drug_func = load_db_logic()

# --- HELPER FUNCTIONS ---

def clean_drug_name(raw_text):
    """
    Robust cleaning for 'Racikan' and messy inputs.
    Example: "Diagit 1/4 tablet\nm.f.pulv..." -> "DIAGIT"
    """
    text = str(raw_text).upper()
    
    # 1. Handle multiline racikan (take top line)
    if '\n' in text:
        text = text.split('\n')[0]
        
    # 2. Stop at common delimiters
    separators = [':', 'TAB', 'CAP', 'SYR', 'BTL', 'FLS', 'M.F.', 'PULV', 'DTD', 'NO.']
    for sep in separators:
        text = text.split(sep)[0]
        
    # 3. Remove non-alpha characters (keep spaces)
    text = re.sub(r'[^A-Z\s]', '', text) 
    return text.strip()

def parse_time_slots(prescription_str):
    s = prescription_str.lower()
    slots = set()
    freq = 1
    
    # Regex for "3 dd" or "3x"
    if re.search(r'3\s*(dd|x)', s): freq = 3
    elif re.search(r'2\s*(dd|x)', s): freq = 2
    elif re.search(r'4\s*(dd|x)', s): freq = 4
    elif re.search(r'1\s*(dd|x)', s): freq = 1
    
    if 'malam' in s or 'night' in s: slots.add('Night')
    if 'pagi' in s or 'morning' in s: slots.add('Morning')
    if 'siang' in s or 'noon' in s: slots.add('Noon')
    if 'sore' in s: slots.add('Night') 

    if not slots:
        if freq >= 1: slots.add('Morning')
        if freq >= 2: slots.add('Night')
        if freq >= 3: slots.add('Noon')
            
    return list(slots)

def determine_severity(text):
    """Parses FDA warning text to determine severity level."""
    t = text.lower()
    high_keywords = [
        'contraindicated', 'avoid', 'fatal', 'life-threatening', 'severe', 'serious', 
        'do not use', 'unsafe', 'anaphylaxis', 'hypoglycemia', 'hospitalization', 'death',
        'toxicity', 'major interaction'
    ]
    if any(x in t for x in high_keywords):
        return 'High'
        
    moderate_keywords = [
        'monitor', 'caution', 'risk', 'adjust', 'potential', 'care', 'consider',
        'may increase', 'may decrease', 'alter', 'effect'
    ]
    if any(x in t for x in moderate_keywords):
        return 'Moderate'
    return 'Low'

# --- ROBUST FDA CHECKER ---
@st.cache_data(ttl=7200)
def get_drug_label_text(drug_name):
    """Fetches full label text (Warnings, Interactions, Contraindications, Boxed Warning) for a drug."""
    base_url = "https://api.fda.gov/drug/label.json"
    params = {'search': f'openfda.substance_name:"{drug_name}"', 'limit': 1}
    
    try:
        resp = requests.get(base_url, params=params, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if 'results' in data:
                res = data['results'][0]
                full_text = ""
                fields = [
                    'drug_interactions', 'warnings', 'precautions', 
                    'contraindications', 'boxed_warning', 'warnings_and_cautions'
                ]
                for f in fields:
                    if f in res and isinstance(res[f], list):
                        full_text += " ".join(res[f]) + " "
                return full_text
    except Exception:
        return ""
    return ""

def check_fda_interaction_robust(drug_a, drug_b):
    """Checks interaction by scanning full label text of A for B, and B for A."""
    def scan(source, target, text):
        if not text: return None, None
        # Allow partial matches (e.g. "NSAID" matching "NSAIDs")
        pattern = r'\b' + re.escape(target) + r'[a-z]*\b' 
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start = max(0, match.start() - 200)
            end = min(len(text), match.end() + 200)
            snippet = "..." + text[start:end] + "..."
            return True, snippet
        return False, None

    # Check A -> B
    text_a = get_drug_label_text(drug_a)
    found, desc = scan(drug_a, drug_b, text_a)
    if found: return True, desc

    # Check B -> A (Reverse)
    text_b = get_drug_label_text(drug_b)
    found, desc = scan(drug_b, drug_a, text_b)
    if found: return True, desc
            
    return False, None

def analyze_row(row_str, row_id):
    if not isinstance(row_str, str): return []
    items = row_str.split(';')
    time_buckets = {'Morning': [], 'Noon': [], 'Night': []}
    
    for item in items:
        if not item.strip(): continue
        clean_name = clean_drug_name(item)
        try:
            drug_obj = get_drug_func(clean_name) if get_drug_func else None
            if drug_obj:
                raw_contents = getattr(drug_obj, 'contents', [])
                ingredients_list = []
                if isinstance(raw_contents, str):
                    ingredients_list = [x.strip() for x in raw_contents.split(',')]
                elif isinstance(raw_contents, list):
                    ingredients_list = raw_contents
                else:
                    ingredients_list = getattr(drug_obj, 'active_ingredients', [])

                if ingredients_list:
                    slots = parse_time_slots(item)
                    for slot in slots:
                        for ingredient in ingredients_list:
                            clean_ing = ingredient.strip()
                            if clean_ing: time_buckets[slot].append(clean_ing)
        except Exception: continue

    alerts = []
    for slot, ingredients in time_buckets.items():
        if len(ingredients) < 2: continue
        unique_ingredients = list(set(ingredients))
        for i in range(len(unique_ingredients)):
            for j in range(i + 1, len(unique_ingredients)):
                ing_a = unique_ingredients[i]
                ing_b = unique_ingredients[j]
                has_interaction, desc = check_fda_interaction_robust(ing_a, ing_b)
                if has_interaction:
                    severity = determine_severity(desc)
                    alerts.append({
                        'Prescription ID': row_id,
                        'Time Slot': slot,
                        'Drug Pair': f"{ing_a} + {ing_b}",
                        'Warning': desc,
                        'Severity': severity
                    })
    return alerts

# --- MAIN UI ---

# Sidebar
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3063/3063167.png", width=60)
    st.title("Setup")
    
    st.markdown("### 1. Upload Data")
    uploaded_file = st.file_uploader("Choose .xlsx or .csv", type=['xlsx', 'csv'], label_visibility="collapsed")
    
    st.divider()
    
    st.markdown("### System Status")
    if is_external_db:
        st.success("✅ **External DB Active**")
        st.caption("Running with full `structured_drug_db`.")
    else:
        st.warning("⚠️ **Mock DB Active**")
        st.caption("Using internal dictionary.")
    
    st.divider()
    st.info("ℹ️ **Privacy Note:**\nAll processing happens in-memory. No data is stored.")

# Main Layout with Custom Header
st.markdown("""
<div class="main-header">
    <div style="font-size: 2.5rem;">💊</div>
    <div>
        <h1 style="margin:0; font-size: 1.8rem; color:#1e293b;">DDI Analyzer Pro</h1>
        <p style="margin:0; color:#64748b;">Automated Prescription Interaction Scanner</p>
    </div>
</div>
""", unsafe_allow_html=True)

if uploaded_file:
    # Load Data
    with st.spinner('Parsing file structure...'):
        try:
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Error reading file: {e}")
            st.stop()
            
    # Column Discovery
    cols = df.columns.str.lower()
    resep_col = None
    possible_cols = [c for c in cols if 'resep' in c]
    if possible_cols:
        target_col_name = df.columns[list(cols).index(possible_cols[0])]
        resep_col = target_col_name
    
    if not resep_col:
        st.error("❌ Column 'resep' not found. Please ensure your file contains the prescription column.")
        with st.expander("Available Columns"):
            st.write(df.columns.tolist())
    else:
        # Action Bar
        col_preview, col_action = st.columns([2, 1])
        with col_preview:
            with st.expander("📄 Data Preview (First 5 rows)", expanded=False):
                st.dataframe(df.head(), use_container_width=True)
        
        with col_action:
            st.write("") # Spacing
            start_btn = st.button("🚀 Start Analysis", type="primary", use_container_width=True)

        if start_btn:
            all_alerts = []
            
            # Progress UI
            progress_container = st.container()
            with progress_container:
                st.write("---")
                p_bar = st.progress(0)
                status_text = st.empty()
            
            rows_to_process = df
            total_rows = len(rows_to_process)
            
            # Processing Loop
            for index, row in rows_to_process.iterrows():
                row_str = str(row[resep_col])
                row_id = row.get('No', row.get('ID', index + 1))
                
                try:
                    alerts = analyze_row(row_str, row_id)
                    all_alerts.extend(alerts)
                except Exception as e:
                    print(f"Row {index} failed: {e}")
                
                # Update Progress
                pct = (index + 1) / total_rows
                p_bar.progress(min(pct, 1.0))
                status_text.markdown(f"<span style='color:#64748b'>Processing prescription <b>{index + 1}</b> of <b>{total_rows}</b>...</span>", unsafe_allow_html=True)
                time.sleep(0.01) 
                
            # Cleanup Progress
            p_bar.empty()
            status_text.empty()
            
            # --- RESULTS DASHBOARD ---
            st.markdown("### Analysis Report")
            
            if all_alerts:
                results_df = pd.DataFrame(all_alerts)
                
                # Metrics Prep
                total_rx = len(df)
                affected_rx_count = results_df['Prescription ID'].nunique()
                safe_rx_count = total_rx - affected_rx_count
                
                # 1. Metrics Cards (HTML5 Style)
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Interactions", len(results_df), delta="Detected", delta_color="inverse")
                m2.metric("At-Risk Prescriptions", affected_rx_count, delta=f"{affected_rx_count/total_rx*100:.1f}%", delta_color="inverse")
                m3.metric("Unique Drug Pairs", results_df['Drug Pair'].nunique(), delta="Combinations", delta_color="off")
                
                st.write("") # Spacing

                # 2. Tabs
                tab_viz, tab_data, tab_export = st.tabs(["📊 Visualizations", "📋 Interaction Log", "📥 Exports"])
                
                with tab_viz:
                    c1, c2 = st.columns(2)
                    
                    with c1:
                        st.markdown("##### 🍩 DDI Prevalence")
                        # PREVALENCE DONUT CHART
                        prev_data = pd.DataFrame({
                            'Status': ['At Risk', 'Safe'],
                            'Count': [affected_rx_count, safe_rx_count]
                        })
                        
                        base = alt.Chart(prev_data).encode(
                            theta=alt.Theta("Count", stack=True)
                        )
                        
                        pie = base.mark_arc(outerRadius=120, innerRadius=80).encode(
                            color=alt.Color("Status", scale=alt.Scale(domain=['At Risk', 'Safe'], range=['#ef4444', '#3b82f6'])),
                            tooltip=["Status", "Count"]
                        )
                        text = base.mark_text(radius=140).encode(
                            text=alt.Text("Count", format="d"),
                            order=alt.Order("Status", sort="descending"),
                            color=alt.value("black") 
                        )
                        st.altair_chart(pie + text, use_container_width=True)
                        
                    with c2:
                        st.markdown("##### ⚠️ Severity Distribution")
                        # SEVERITY DISTRIBUTION CHART
                        sev_counts = results_df['Severity'].value_counts().reset_index()
                        sev_counts.columns = ['Severity', 'Count']
                        
                        sev_chart = alt.Chart(sev_counts).mark_bar().encode(
                            x=alt.X('Severity', sort=['High', 'Moderate', 'Low']),
                            y='Count',
                            color=alt.Color('Severity', scale=alt.Scale(
                                domain=['High', 'Moderate', 'Low'],
                                range=['#b91c1c', '#f59e0b', '#3b82f6']
                            )),
                            tooltip=['Severity', 'Count']
                        )
                        st.altair_chart(sev_chart, use_container_width=True)

                    st.divider()

                    # Row 2: Burden & Pairs
                    c3, c4 = st.columns(2)
                    
                    with c3:
                        st.markdown("##### 📉 DDIs per Prescription (Burden)")
                        # BURDEN DISTRIBUTION
                        burden_counts = results_df['Prescription ID'].value_counts()
                        # Get all IDs including zeros
                        all_ids = df['No'] if 'No' in df.columns else df.index
                        full_burden = burden_counts.reindex(all_ids, fill_value=0)
                        
                        # STATISTICS CALCULATIONS
                        avg_ddi = full_burden.mean()
                        max_ddi = full_burden.max()
                        med_ddi = full_burden.median()
                        
                        # Display Stats Legend
                        st.caption(f"**Statistics:** Avg: **{avg_ddi:.2f}** | Median: **{med_ddi}** | Max: **{max_ddi}**")

                        # FIX: Explicit Rename to avoid collision
                        dist_data = full_burden.value_counts().rename_axis('Alerts').reset_index(name='Count')
                        
                        # Base Bars
                        bars = alt.Chart(dist_data).mark_bar().encode(
                            x=alt.X('Alerts:Q', title="Alerts per Rx", axis=alt.Axis(tickMinStep=1)),
                            y=alt.Y('Count:Q', title="Number of Prescriptions"),
                            color=alt.value("#6366f1"),
                            tooltip=['Alerts', 'Count']
                        )
                        
                        # Mean Rule (Red Line)
                        rule = alt.Chart(pd.DataFrame({'mean': [avg_ddi]})).mark_rule(color='red', strokeDash=[5,5]).encode(x='mean')
                        
                        # Mean Label
                        text = alt.Chart(pd.DataFrame({'mean': [avg_ddi], 'label': [f'Avg: {avg_ddi:.1f}']})).mark_text(
                            align='left', dx=5, color='red', dy=-5
                        ).encode(
                            x='mean', y=alt.value(0), text='label'
                        )

                        st.altair_chart((bars + rule + text), use_container_width=True)

                    with c4:
                        st.markdown("##### 💊 Top 20 Frequent Pairs")
                        # TOP PAIRS CHART (Changed to Top 20)
                        top_pairs = results_df['Drug Pair'].value_counts().head(20).reset_index()
                        top_pairs.columns = ['Pair', 'Count']
                        
                        pair_chart = alt.Chart(top_pairs).mark_bar().encode(
                            x=alt.X('Count', title='Occurrences'),
                            y=alt.Y('Pair', sort='-x', title='Drug Pair'),
                            color=alt.value("#10b981"),
                            tooltip=['Pair', 'Count']
                        ).properties(height=600)  # Increased height to fit 20 bars comfortably
                        st.altair_chart(pair_chart, use_container_width=True)

                with tab_data:
                    # Search
                    search_term = st.text_input("🔍 Filter by Drug, ID or Keyword", "", placeholder="Type 'Aspirin' or '123'...")
                    
                    if search_term:
                        filtered_df = results_df[
                            results_df.apply(lambda row: row.astype(str).str.contains(search_term, case=False).any(), axis=1)
                        ]
                    else:
                        filtered_df = results_df
                        
                    st.dataframe(
                        filtered_df, 
                        use_container_width=True,
                        column_config={
                            "Warning": st.column_config.TextColumn("FDA Warning Text", width="large", help="Text extracted from FDA Label"),
                            "Drug Pair": st.column_config.TextColumn("Pair", width="medium"),
                            "Severity": st.column_config.TextColumn("Severity", width="small"),
                        },
                        hide_index=True
                    )

                with tab_export:
                    st.markdown("##### Download Results")
                    csv = results_df.to_csv(index=False).encode('utf-8')
                    c_down, _ = st.columns([1,3])
                    with c_down:
                        st.download_button(
                            label="📥 Download CSV Report",
                            data=csv,
                            file_name="ddi_analysis_report.csv",
                            mime="text/csv",
                            type="primary",
                            use_container_width=True
                        )
            else:
                st.success("✅ **Analysis Complete:** No significant interactions detected in this dataset.")
                st.balloons()
else:
    # Empty State (HTML5 Style)
    st.markdown("""
    <div style="text-align: center; padding: 4rem 2rem; border: 2px dashed #cbd5e1; border-radius: 12px; background-color: white;">
        <div style="font-size: 3rem; margin-bottom: 1rem; color: #94a3b8;">📂</div>
        <h3 style="color: #475569;">No Data Uploaded</h3>
        <p style="color: #64748b;">Upload a prescription file (.xlsx or .csv) from the sidebar to begin analysis.</p>
    </div>
    """, unsafe_allow_html=True)
