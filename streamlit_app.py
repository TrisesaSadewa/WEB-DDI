import streamlit as st
import pandas as pd
import requests
import re
import time
import altair as alt

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

# --- DATABASE LOADING ---
try:
    from structured_drug_db import get_drug_by_name
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    def get_drug_by_name(name): return None

# --- STATIC KNOWLEDGE BASE (CRITICAL FALLBACK) ---
# Maps FROZEN SETS of canonical English names to (Severity, Description)
KNOWN_INTERACTIONS = {
    # MAJOR
    frozenset(['AMLODIPINE', 'PHENYTOIN']): ('Major', 'Phenytoin decreases levels of Amlodipine by increasing metabolism.'),
    frozenset(['ASPIRIN', 'IBUPROFEN']): ('Major', 'Ibuprofen may interfere with the anti-platelet effect of low-dose Aspirin.'),
    frozenset(['FENOFIBRATE', 'SIMVASTATIN']): ('Major', 'Increased risk of myopathy/rhabdomyolysis.'),
    frozenset(['CLOPIDOGREL', 'WARFARIN']): ('Major', 'Increased risk of bleeding.'),
    frozenset(['WARFARIN', 'MELOXICAM']): ('Major', 'NSAIDs increase bleeding risk with Anticoagulants.'),
    
    # MODERATE
    frozenset(['CARVEDILOL', 'IBUPROFEN']): ('Moderate', 'NSAIDs may diminish the antihypertensive effect of Beta-blockers.'),
    frozenset(['PHENYTOIN', 'FOLIC ACID']): ('Moderate', 'Phenytoin may decrease serum Folic Acid; Folic Acid may decrease Phenytoin levels.'),
    frozenset(['MELOXICAM', 'CAPTOPRIL']): ('Moderate', 'NSAIDs may diminish the antihypertensive effect of ACE Inhibitors.'),
    frozenset(['MELOXICAM', 'METFORMIN']): ('Moderate', 'Use with caution (renal function monitoring).'),
    frozenset(['MELOXICAM', 'GLYBURIDE']): ('Moderate', 'NSAIDs may increase the effect of sulfonylureas (hypoglycemia risk).'),
    frozenset(['MELOXICAM', 'FENOFIBRATE']): ('Moderate', 'Potential risk of renal toxicity.'),
    frozenset(['MELOXICAM', 'NIFEDIPINE']): ('Moderate', 'NSAIDs may diminish the antihypertensive effect of Calcium Channel Blockers.'),
    frozenset(['CAPTOPRIL', 'METFORMIN']): ('Moderate', 'ACE inhibitors may enhance the hypoglycemic effect of Metformin.'),
    frozenset(['CAPTOPRIL', 'GLYBURIDE']): ('Moderate', 'ACE inhibitors may enhance the hypoglycemic effect of Sulfonylureas.'),
    
    # MINOR / OTHER
    frozenset(['SPIRONOLACTONE', 'DIGOXIN']): ('Minor', 'Spironolactone may increase Digoxin levels.'),
}

# --- HELPER FUNCTIONS ---

def clean_drug_name(raw_text):
    """
    Cleans raw text and uses structured_drug_db to find the canonical English generic name.
    """
    if not isinstance(raw_text, str): return ""
    text = raw_text.upper().strip()
    
    # 1. Clean Noise & Prefixes (Specific to this dataset)
    text = re.sub(r'\b(ANS|KIE)\b', '', text).strip()
    
    # 2. Handle Alternate Style "Drug#Qty" or "Drug:Usage"
    text = re.split(r'[#:]', text)[0].strip()
    
    # 3. Handle Multiline (Racikan)
    if '\n' in text: text = text.split('\n')[0].strip()
        
    # 4. Remove Forms/Dosages to isolate the Name
    # E.g. "AMLODIPIN 10 MG TABLET" -> "AMLODIPIN"
    text = re.sub(r'\b(TAB|CAP|SYR|DROP|TABLET|KAPSUL|INJEKSI|MG|ML|G|PRN)\b', '', text)
    text = re.sub(r'\b\d+([.,]\d+)?\b', '', text) # Remove loose numbers
    text = re.sub(r'\s+', ' ', text).strip()

    # 5. Database Lookup (Indonesian -> English Canonical)
    if DB_AVAILABLE:
        drug_obj = get_drug_by_name(text)
        if drug_obj and hasattr(drug_obj, 'name'):
            return drug_obj.name.upper()
            
    return text # Fallback if DB lookup fails

def parse_time_slots(prescription_str):
    """
    Determines if drug is taken Morning, Noon, or Night based on string patterns.
    """
    s = prescription_str.lower()
    slots = set()
    
    # Pattern 1: "1-0-0" or "0-1/2-0" (Morning-Noon-Night)
    xyz_match = re.search(r'\b(\d+(?:/\d+)?)\s*-\s*(\d+(?:/\d+)?)\s*-\s*(\d+(?:/\d+)?)\b', s)
    if xyz_match:
        m, n, ni = xyz_match.groups()
        try:
            if eval(str(m)) > 0: slots.add('Morning')
            if eval(str(n)) > 0: slots.add('Noon')
            if eval(str(ni)) > 0: slots.add('Night')
        except: pass
        if slots: return list(slots)

    # Pattern 2: "3 dd 1", "3x1", "2x"
    freq = 0
    match = re.search(r'(\d+)\s*(?:dd|x)', s)
    if match: freq = int(match.group(1))
    
    # Pattern 3: Explicit words
    if 'malam' in s or 'night' in s: slots.add('Night')
    if 'pagi' in s or 'morning' in s: slots.add('Morning')
    if 'siang' in s or 'noon' in s: slots.add('Noon')
    
    # Fallback based on frequency
    if not slots:
        if freq >= 1: slots.add('Morning')
        if freq >= 2: slots.add('Night')
        if freq >= 3: slots.add('Noon')
    
    # Ultimate Fallback
    if not slots: slots.add('Morning')
            
    return list(slots)

@st.cache_data(ttl=7200)
def get_drug_label_text(drug_name):
    """Fetches FDA label text via API as a fallback."""
    if not drug_name or len(drug_name) < 3: return ""
    base_url = "https://api.fda.gov/drug/label.json"
    try:
        query = f'openfda.brand_name:"{drug_name}"+OR+openfda.generic_name:"{drug_name}"'
        resp = requests.get(base_url, params={'search': query, 'limit': 1}, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            if 'results' in data:
                res = data['results'][0]
                fields = ['drug_interactions', 'warnings', 'precautions', 'contraindications', 'boxed_warning']
                full_text = " ".join([" ".join(res.get(f, [])) for f in fields])
                return full_text
    except: pass
    return ""

def analyze_row(row_str, row_id):
    """
    Main Logic:
    1. Splits row by delimiters (||| or \n).
    2. Cleans drug names (Indo -> Eng).
    3. Buckets into Time Slots.
    4. Checks pairs against KB and FDA API.
    """
    if not isinstance(row_str, str): return []
    
    # Normalize delimiters: ||| -> ; and \n -> ;
    normalized_row = row_str.replace('|||', ';').replace('\n', ';').replace('\r', ';')
    items = [x for x in normalized_row.split(';') if x.strip()]
    
    time_buckets = {'Morning': [], 'Noon': [], 'Night': []}
    
    # 1. Parse Drugs into Time Slots
    for item in items:
        canonical_name = clean_drug_name(item)
        if not canonical_name: continue
        
        slots = parse_time_slots(item)
        for slot in slots:
            time_buckets[slot].append(canonical_name)

    alerts = []
    
    # 2. Analyze Pairs per Time Slot
    for slot, drugs in time_buckets.items():
        if len(drugs) < 2: continue
        unique_drugs = sorted(list(set(drugs)))
        
        for i in range(len(unique_drugs)):
            for j in range(i + 1, len(unique_drugs)):
                d1, d2 = unique_drugs[i], unique_drugs[j]
                
                # Create Key for KB Lookup
                pair_key = frozenset([d1, d2])
                
                # A. CHECK STATIC KNOWLEDGE BASE (Primary & Fastest)
                if pair_key in KNOWN_INTERACTIONS:
                    sev, desc = KNOWN_INTERACTIONS[pair_key]
                    alerts.append({
                        'Prescription ID': row_id,
                        'Time Slot': slot,
                        'Drug Pair': f"{d1} + {d2}",
                        'Warning': f"[KB] {desc}",
                        'Severity': sev
                    })
                    continue 

                # B. CHECK FDA API (Fallback)
                # Only if not found in KB. Checks if D2 is mentioned in D1's label.
                label_text = get_drug_label_text(d1)
                if label_text and d2 in label_text.upper():
                    alerts.append({
                        'Prescription ID': row_id,
                        'Time Slot': slot,
                        'Drug Pair': f"{d1} + {d2}",
                        'Warning': f"Potential interaction mentioned in {d1} FDA label regarding {d2}.",
                        'Severity': 'Moderate'
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
    if DB_AVAILABLE:
        st.success("✅ **External DB Active**")
        st.caption("Running with `structured_drug_db`.")
    else:
        st.warning("⚠️ **Mock DB Active**")
        st.caption("File `structured_drug_db.py` not found.")
    
    st.divider()
    st.info("ℹ️ **Privacy Note:**\nAll processing happens in-memory. No data is stored.")

# Main Header
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
    # Flexible column search
    possible_cols = [c for c in cols if 'resep' in c or 'obat' in c or 'presc' in c]
    
    if possible_cols:
        target_col_name = df.columns[list(cols).index(possible_cols[0])]
        resep_col = target_col_name
    elif len(df.columns) > 1:
        # Fallback to 2nd column if not found
        resep_col = df.columns[1] 
    
    if not resep_col:
        st.error("❌ Could not identify a Prescription column. Please ensure your file has a column named 'resep', 'obat', or similar.")
        st.write("Available columns:", df.columns.tolist())
    else:
        # Action Bar
        col_preview, col_action = st.columns([2, 1])
        with col_preview:
            with st.expander(f"📄 Data Preview (Using column: '{resep_col}')", expanded=False):
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
                # Try to find an ID column, otherwise use Index
                row_id = row.get('No', row.get('ID', row.get('EMR', index + 1)))
                
                try:
                    alerts = analyze_row(row_str, row_id)
                    all_alerts.extend(alerts)
                except Exception as e:
                    print(f"Row {index} failed: {e}")
                
                # Update Progress
                if index % 5 == 0 or index == total_rows - 1:
                    pct = (index + 1) / total_rows
                    p_bar.progress(min(pct, 1.0))
                    status_text.markdown(f"<span style='color:#64748b'>Processing prescription <b>{index + 1}</b> of <b>{total_rows}</b>...</span>", unsafe_allow_html=True)
                    time.sleep(0.001) 
                
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
                
                # 1. Metrics Cards
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
                        prev_data = pd.DataFrame({
                            'Status': ['At Risk', 'Safe'],
                            'Count': [affected_rx_count, safe_rx_count]
                        })
                        base = alt.Chart(prev_data).encode(theta=alt.Theta("Count", stack=True))
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
                        sev_counts = results_df['Severity'].value_counts().reset_index()
                        sev_counts.columns = ['Severity', 'Count']
                        sev_chart = alt.Chart(sev_counts).mark_bar().encode(
                            x=alt.X('Severity', sort=['High', 'Moderate', 'Low', 'Minor']),
                            y='Count',
                            color=alt.Color('Severity', scale=alt.Scale(
                                domain=['High', 'Moderate', 'Low', 'Minor'],
                                range=['#b91c1c', '#f59e0b', '#3b82f6', '#94a3b8']
                            )),
                            tooltip=['Severity', 'Count']
                        )
                        st.altair_chart(sev_chart, use_container_width=True)

                    st.divider()

                    # Row 2
                    c3, c4 = st.columns(2)
                    
                    with c3:
                        st.markdown("##### 📉 DDIs per Prescription (Burden)")
                        burden_counts = results_df['Prescription ID'].value_counts()
                        # Align with full dataset
                        all_ids = df['No'] if 'No' in df.columns else (df['EMR'] if 'EMR' in df.columns else df.index)
                        full_burden = burden_counts.reindex(all_ids, fill_value=0)
                        
                        avg_ddi = full_burden.mean()
                        dist_data = full_burden.value_counts().rename_axis('Alerts').reset_index(name='Count')
                        
                        bars = alt.Chart(dist_data).mark_bar().encode(
                            x=alt.X('Alerts:Q', title="Alerts per Rx"),
                            y=alt.Y('Count:Q', title="Number of Prescriptions"),
                            color=alt.value("#6366f1"),
                            tooltip=['Alerts', 'Count']
                        )
                        rule = alt.Chart(pd.DataFrame({'mean': [avg_ddi]})).mark_rule(color='red', strokeDash=[5,5]).encode(x='mean')
                        st.altair_chart(bars + rule, use_container_width=True)

                    with c4:
                        st.markdown("##### 💊 Top 20 Frequent Pairs")
                        top_pairs = results_df['Drug Pair'].value_counts().head(20).reset_index()
                        top_pairs.columns = ['Pair', 'Count']
                        
                        pair_chart = alt.Chart(top_pairs).mark_bar().encode(
                            x=alt.X('Count', title='Occurrences'),
                            y=alt.Y('Pair', sort='-x', title='Drug Pair'),
                            color=alt.value("#10b981"),
                            tooltip=['Pair', 'Count']
                        ).properties(height=500)
                        st.altair_chart(pair_chart, use_container_width=True)

                with tab_data:
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
                            "Warning": st.column_config.TextColumn("Details", width="large"),
                            "Drug Pair": st.column_config.TextColumn("Pair", width="medium"),
                            "Severity": st.column_config.TextColumn("Severity", width="small"),
                        },
                        hide_index=True
                    )

                with tab_export:
                    st.markdown("##### Download Results")
                    csv = results_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download CSV Report",
                        data=csv,
                        file_name="ddi_analysis_report.csv",
                        mime="text/csv",
                        type="primary"
                    )
            else:
                st.success("✅ **Analysis Complete:** No significant interactions detected in this dataset.")
                st.balloons()
else:
    # Empty State
    st.markdown("""
    <div style="text-align: center; padding: 4rem 2rem; border: 2px dashed #cbd5e1; border-radius: 12px; background-color: white;">
        <div style="font-size: 3rem; margin-bottom: 1rem; color: #94a3b8;">📂</div>
        <h3 style="color: #475569;">No Data Uploaded</h3>
        <p style="color: #64748b;">Upload a prescription file (.xlsx or .csv) from the sidebar to begin analysis.</p>
    </div>
    """, unsafe_allow_html=True)
