import streamlit as st
import pandas as pd
import requests
import re
import time
import altair as alt
from itertools import combinations

# --- CONFIGURATION ---
st.set_page_config(
    page_title="DDI Analysis Tool", 
    layout="wide",
    page_icon="💊",
    initial_sidebar_state="expanded"
)

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #1e293b; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e2e8f0; }
    .main-header {
        background-color: white; padding: 1.5rem 2rem; border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05); margin-bottom: 2rem;
        border: 1px solid #f1f5f9; display: flex; align-items: center; gap: 1rem;
    }
    div[data-testid="stMetric"] {
        background-color: white; padding: 1.25rem; border-radius: 12px;
        border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

# --- 1. ROBUST TRANSLATION MAP (The Fix for "No Interactions") ---
# Maps Indonesian/Trade names to the English Generic names the API/KB expects.
ID_TO_EN_MAP = {
    'AMLODIPIN': 'AMLODIPINE', 'ASAM FOLAT': 'FOLIC ACID', 
    'ASAM TRANEKSAMAT': 'TRANEXAMIC ACID', 'PARASETAMOL': 'ACETAMINOPHEN', 
    'GLIBENKLAMID': 'GLYBURIDE', 'KLOPIDOGREL': 'CLOPIDOGREL', 
    'KANDESARTAN': 'CANDESARTAN', 'BISOPROLOL': 'BISOPROLOL', 
    'FUROSEMID': 'FUROSEMIDE', 'SPIRONOLAKTON': 'SPIRONOLACTONE', 
    'SIMVASTATIN': 'SIMVASTATIN', 'FENITOIN': 'PHENYTOIN', 
    'ASAM ASETILSALISILAT': 'ASPIRIN', 'ASETOSAL': 'ASPIRIN', 
    'MINIASPI': 'ASPIRIN', 'NOSPIRINAL': 'ASPIRIN', 'V-BLOC': 'CARVEDILOL', 
    'NITROKAF': 'NITROGLYCERIN', 'SUCRALFATE': 'SUCRALFATE', 
    'IBUPROFEN': 'IBUPROFEN', 'OMEPRAZOLE': 'OMEPRAZOLE', 
    'VALSARTAN': 'VALSARTAN', 'MELOXICAM': 'MELOXICAM', 
    'CAPTOPRIL': 'CAPTOPRIL', 'METFORMIN': 'METFORMIN', 
    'GABAPENTIN': 'GABAPENTIN', 'FENOFIBRATE': 'FENOFIBRATE', 
    'NIFEDIPINE': 'NIFEDIPINE', 'DIGOXIN': 'DIGOXIN', 
    'METHYL PREDNISOLON': 'METHYLPREDNISOLONE', 'NOTISIL': 'DIAZEPAM',
    'WARFARIN': 'WARFARIN', 'SIMARC': 'WARFARIN', 'THROMBO': 'ASPIRIN'
}

# --- 2. KNOWLEDGE BASE (Guaranteed Detection) ---
KNOWN_INTERACTIONS = {
    frozenset(['AMLODIPINE', 'PHENYTOIN']): ('Major', 'Phenytoin decreases levels of Amlodipine by increasing metabolism.'),
    frozenset(['ASPIRIN', 'IBUPROFEN']): ('Major', 'Ibuprofen may interfere with the anti-platelet effect of low-dose Aspirin.'),
    frozenset(['FENOFIBRATE', 'SIMVASTATIN']): ('Major', 'Increased risk of myopathy/rhabdomyolysis.'),
    frozenset(['CLOPIDOGREL', 'WARFARIN']): ('Major', 'Increased risk of bleeding.'),
    frozenset(['WARFARIN', 'MELOXICAM']): ('Major', 'NSAIDs increase bleeding risk with Anticoagulants.'),
    frozenset(['CARVEDILOL', 'IBUPROFEN']): ('Moderate', 'NSAIDs may diminish the antihypertensive effect of Beta-blockers.'),
    frozenset(['PHENYTOIN', 'FOLIC ACID']): ('Moderate', 'Phenytoin may decrease serum Folic Acid; Folic Acid may decrease Phenytoin levels.'),
    frozenset(['MELOXICAM', 'CAPTOPRIL']): ('Moderate', 'NSAIDs may diminish the antihypertensive effect of ACE Inhibitors.'),
    frozenset(['MELOXICAM', 'METFORMIN']): ('Moderate', 'Use with caution (renal function monitoring).'),
    frozenset(['MELOXICAM', 'GLYBURIDE']): ('Moderate', 'NSAIDs may increase the effect of sulfonylureas (hypoglycemia risk).'),
    frozenset(['CAPTOPRIL', 'METFORMIN']): ('Moderate', 'ACE inhibitors may enhance the hypoglycemic effect of Metformin.'),
    frozenset(['SPIRONOLACTONE', 'DIGOXIN']): ('Minor', 'Spironolactone may increase Digoxin levels.'),
}

# --- HELPER FUNCTIONS ---

def clean_drug_name(raw_text):
    """Parses and translates drug names."""
    if not isinstance(raw_text, str): return ""
    text = raw_text.upper().strip()
    
    # 1. Clean Noise (Prefixes, R/, etc)
    text = re.sub(r'\b(ANS|KIE|RESEP|R/|OBAT)\b', '', text).strip()
    
    # 2. Handle Separators (# or :)
    text = re.split(r'[#:]', text)[0].strip()
    
    # 3. Handle Multiline
    if '\n' in text: text = text.split('\n')[0].strip()
    
    # 4. Remove Forms/Dosages
    text = re.sub(r'\b(TAB|CAP|SYR|DROP|TABLET|KAPSUL|INJEKSI|MG|ML|G|PRN|RETARD)\b', '', text)
    text = re.sub(r'\b\d+([.,]\d+)?\b', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    # 5. TRANSLATE (Crucial Step)
    if text in ID_TO_EN_MAP: return ID_TO_EN_MAP[text]
    
    # Substring match (e.g. "ANS AMLODIPIN" -> "AMLODIPINE")
    for k, v in ID_TO_EN_MAP.items():
        if k in text: return v
            
    return text

def parse_time_slots(prescription_str):
    s = prescription_str.lower()
    slots = set()
    
    # Check "1-0-0" Pattern
    xyz_match = re.search(r'\b(\d+(?:/\d+)?)\s*-\s*(\d+(?:/\d+)?)\s*-\s*(\d+(?:/\d+)?)\b', s)
    if xyz_match:
        m, n, ni = xyz_match.groups()
        try:
            if eval(str(m)) > 0: slots.add('Morning')
            if eval(str(n)) > 0: slots.add('Noon')
            if eval(str(ni)) > 0: slots.add('Night')
        except: pass

    # Check Frequency
    freq = 0
    match = re.search(r'(\d+)\s*(?:dd|x)', s)
    if match: freq = int(match.group(1))
    
    if 'malam' in s or 'night' in s: slots.add('Night')
    if 'pagi' in s or 'morning' in s: slots.add('Morning')
    if 'siang' in s or 'noon' in s: slots.add('Noon')
    
    if not slots:
        if freq >= 1: slots.add('Morning')
        if freq >= 2: slots.add('Night')
        if freq >= 3: slots.add('Noon')
            
    return list(slots) if slots else ['Morning']

def determine_severity(text):
    t = text.lower()
    if any(x in t for x in ['contraindicated', 'fatal', 'life-threatening', 'severe', 'major']): return 'High'
    if any(x in t for x in ['monitor', 'caution', 'risk', 'adjust']): return 'Moderate'
    return 'Low'

@st.cache_data(ttl=7200)
def get_drug_label_text(drug_name):
    """Fetches FDA label text."""
    base_url = "https://api.fda.gov/drug/label.json"
    try:
        query = f'openfda.brand_name:"{drug_name}"+OR+openfda.generic_name:"{drug_name}"'
        resp = requests.get(base_url, params={'search': query, 'limit': 1}, timeout=3)
        if resp.status_code == 200:
            data = resp.json()
            if 'results' in data:
                res = data['results'][0]
                fields = ['drug_interactions', 'warnings', 'precautions', 'contraindications']
                return " ".join([" ".join(res.get(f, [])) for f in fields])
    except: pass
    return ""

def check_fda_interaction_robust(drug_a, drug_b):
    """Checks FDA API as fallback."""
    text_a = get_drug_label_text(drug_a)
    if text_a and drug_b in text_a.upper():
        return True, f"Potential interaction mentioned in {drug_a} FDA label."
    return False, None

def analyze_row(row_str, row_id):
    if not isinstance(row_str, str): return []
    
    # Normalize Delimiters (The fix for Old vs New data)
    normalized_row = row_str.replace('|||', ';').replace('\n', ';').replace('\r', ';')
    items = [x for x in normalized_row.split(';') if x.strip()]
    
    time_buckets = {'Morning': [], 'Noon': [], 'Night': [], 'Global': []}
    
    for item in items:
        canonical = clean_drug_name(item)
        if not canonical or len(canonical) < 3: continue
        
        slots = parse_time_slots(item)
        for slot in slots:
            time_buckets[slot].append(canonical)
        time_buckets['Global'].append(canonical)

    alerts = []
    
    # Check interactions in all buckets
    for slot, drugs in time_buckets.items():
        if len(drugs) < 2: continue
        unique = sorted(list(set(drugs)))
        
        for d1, d2 in combinations(unique, 2):
            pair_key = frozenset([d1, d2])
            
            # 1. CHECK KB (Fast & Accurate)
            if pair_key in KNOWN_INTERACTIONS:
                sev, desc = KNOWN_INTERACTIONS[pair_key]
                alerts.append({
                    'Prescription ID': row_id,
                    'Time Slot': slot,
                    'Drug Pair': f"{d1} + {d2}",
                    'Warning': f"[KB] {desc}",
                    'Severity': sev
                })
            # 2. CHECK API (Fallback)
            elif slot != 'Global': # Only check API for specific time slots to save requests
                found, desc = check_fda_interaction_robust(d1, d2)
                if found:
                    alerts.append({
                        'Prescription ID': row_id,
                        'Time Slot': slot,
                        'Drug Pair': f"{d1} + {d2}",
                        'Warning': f"[API] {desc}",
                        'Severity': determine_severity(desc)
                    })
    
    return alerts

# --- MAIN UI ---

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3063/3063167.png", width=60)
    st.title("Setup")
    uploaded_file = st.file_uploader("Choose .xlsx or .csv", type=['xlsx', 'csv'], label_visibility="collapsed")
    st.divider()
    st.info("ℹ️ **Privacy Note:**\nAll processing happens in-memory.")

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
    with st.spinner('Parsing file structure...'):
        try:
            if uploaded_file.name.endswith('.csv'): df = pd.read_csv(uploaded_file)
            else: df = pd.read_excel(uploaded_file)
        except Exception as e:
            st.error(f"Error reading file: {e}")
            st.stop()
            
    cols = df.columns.str.lower()
    resep_col = next((df.columns[i] for i, c in enumerate(cols) if 'resep' in c or 'obat' in c or 'presc' in c), None)
    if not resep_col and len(df.columns) > 1: resep_col = df.columns[1]
    
    if resep_col:
        col_preview, col_action = st.columns([2, 1])
        with col_preview:
            with st.expander("📄 Data Preview"):
                st.dataframe(df.head(), use_container_width=True)
        
        with col_action:
            st.write("") 
            start_btn = st.button("🚀 Start Analysis", type="primary", use_container_width=True)

        if start_btn:
            all_alerts = []
            progress_container = st.container()
            
            with progress_container:
                st.write("---")
                p_bar = st.progress(0)
                status_text = st.empty()
            
            rows = df.to_dict('records')
            total = len(rows)
            
            for i, row in enumerate(rows):
                rid = row.get('No', row.get('ID', i + 1))
                rstr = str(row.get(resep_col, ''))
                all_alerts.extend(analyze_row(rstr, rid))
                
                if i % 5 == 0 or i == total - 1:
                    p_bar.progress((i + 1) / total)
                    status_text.text(f"Processing {i + 1}/{total}...")
            
            p_bar.empty()
            status_text.empty()
            
            # --- RESULTS ---
            st.markdown("### Analysis Report")
            
            if all_alerts:
                results_df = pd.DataFrame(all_alerts)
                # Deduplicate logic: If caught in Morning, don't show again in Global
                results_df = results_df.sort_values('Time Slot').drop_duplicates(subset=['Prescription ID', 'Drug Pair'])
                
                # Metrics
                total_rx = len(df)
                affected = results_df['Prescription ID'].nunique()
                
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Interactions", len(results_df))
                m2.metric("At-Risk Prescriptions", affected, delta=f"{affected/total_rx*100:.1f}%", delta_color="inverse")
                m3.metric("Unique Drug Pairs", results_df['Drug Pair'].nunique())
                
                tab_viz, tab_data, tab_export = st.tabs(["📊 Visualizations", "📋 Interaction Log", "📥 Exports"])
                
                with tab_viz:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("##### Severity")
                        sev_c = results_df['Severity'].value_counts().reset_index()
                        sev_c.columns = ['Severity', 'Count']
                        st.altair_chart(
                            alt.Chart(sev_c).mark_bar().encode(
                                x='Severity', y='Count', color='Severity'
                            ).properties(width='container'), 
                            use_container_width=True
                        )
                    with c2:
                        st.markdown("##### Top Pairs")
                        top = results_df['Drug Pair'].value_counts().head(10).reset_index()
                        top.columns = ['Pair', 'Count']
                        st.altair_chart(
                            alt.Chart(top).mark_bar().encode(
                                x='Count', y=alt.Y('Pair', sort='-x'), color=alt.value('#10b981')
                            ).properties(width='container'),
                            use_container_width=True
                        )

                with tab_data:
                    st.dataframe(results_df, use_container_width=True, hide_index=True)

                with tab_export:
                    csv = results_df.to_csv(index=False).encode('utf-8')
                    st.download_button("📥 Download CSV", csv, "ddi_report.csv", "text/csv", type="primary")
            else:
                st.success("✅ No significant interactions detected.")
                st.balloons()
    else:
        st.error("❌ Column 'resep' not found.")
else:
    st.markdown("""
    <div style="text-align: center; padding: 4rem 2rem; border: 2px dashed #cbd5e1; border-radius: 12px; background-color: white;">
        <h3 style="color: #475569;">No Data Uploaded</h3>
        <p style="color: #64748b;">Upload a prescription file (.xlsx or .csv) to begin.</p>
    </div>
    """, unsafe_allow_html=True)
