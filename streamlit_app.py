import streamlit as st
import pandas as pd
import requests
import re
import time
import altair as alt
from itertools import combinations
from fuzzywuzzy import process # Standard library for fuzzy matching

# --- CONFIGURATION ---
st.set_page_config(
    page_title="DDI Analysis Tool", 
    layout="wide",
    page_icon="💊",
    initial_sidebar_state="expanded"
)

# --- DATABASE & KNOWLEDGE BASE ---
try:
    from structured_drug_db import get_drug_by_name
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    def get_drug_by_name(name): return None

# 1. CANONICAL DRUG LIST (The "Target" list for fuzzy matching)
# These are the correct English names we want to map TO.
CANONICAL_DRUGS = [
    'AMLODIPINE', 'ASPIRIN', 'ACETAMINOPHEN', 'BISOPROLOL', 'CANDESARTAN', 
    'CAPTOPRIL', 'CARVEDILOL', 'CLOPIDOGREL', 'DIGOXIN', 'FENOFIBRATE', 
    'FOLIC ACID', 'FUROSEMIDE', 'GABAPENTIN', 'GLYBURIDE', 'IBUPROFEN', 
    'INSULIN', 'MELOXICAM', 'METFORMIN', 'METHYLPREDNISOLONE', 'NIFEDIPINE', 
    'NITROGLYCERIN', 'OMEPRAZOLE', 'PHENYTOIN', 'SIMVASTATIN', 
    'SODIUM BICARBONATE', 'SPIRONOLACTONE', 'SUCRALFATE', 'TRANEXAMIC ACID', 
    'VALSARTAN', 'WARFARIN'
]

# 2. KNOWN INTERACTIONS (Knowledge Base)
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
    
    # MINOR
    frozenset(['SPIRONOLACTONE', 'DIGOXIN']): ('Minor', 'Spironolactone may increase Digoxin levels.'),
}

# --- HELPER FUNCTIONS ---

def clean_drug_name(raw_text):
    """
    1. Clean Noise
    2. Try Exact Match
    3. Try Fuzzy Match (The new layer!)
    """
    if not isinstance(raw_text, str): return ""
    text = raw_text.upper().strip()
    
    # 1. Clean Noise
    text = re.sub(r'\b(ANS|KIE|RESEP)\b', '', text).strip()
    text = re.split(r'[#:]', text)[0].strip()
    if '\n' in text: text = text.split('\n')[0].strip()
    text = re.sub(r'\b(TAB|CAP|SYR|DROP|TABLET|KAPSUL|INJEKSI|MG|ML|G|PRN|RETARD)\b', '', text)
    text = re.sub(r'\b\d+([.,]\d+)?\b', '', text)
    text = re.sub(r'\s+', ' ', text).strip()

    if not text: return ""

    # 2. Exact Match Check (Fastest)
    if text in CANONICAL_DRUGS:
        return text

    # 3. Fuzzy Match (Robust Fallback)
    # This will find "AMLODIPIN" -> "AMLODIPINE" (Score > 90)
    best_match, score = process.extractOne(text, CANONICAL_DRUGS)
    if score >= 88: # High threshold to avoid "Tramadol" vs "Toradol" errors
        return best_match
            
    return text # Return raw if no good match found

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

def analyze_row(row_str, row_id):
    if not isinstance(row_str, str): return [], []
    
    normalized_row = row_str.replace('|||', ';').replace('\n', ';').replace('\r', ';')
    items = [x for x in normalized_row.split(';') if x.strip()]
    
    time_buckets = {'Morning': [], 'Noon': [], 'Night': [], 'Entire Prescription': []}
    parsed_log = []
    
    for item in items:
        canonical = clean_drug_name(item)
        if not canonical or len(canonical) < 3: continue
        
        # Log the mapping for debugging
        parsed_log.append(f"{item[:15]}... -> {canonical}")
        
        slots = parse_time_slots(item)
        for slot in slots:
            time_buckets[slot].append(canonical)
        time_buckets['Entire Prescription'].append(canonical)

    alerts = []
    
    # Check interactions in all buckets
    for slot, drugs in time_buckets.items():
        if len(drugs) < 2: continue
        unique = sorted(list(set(drugs)))
        
        for d1, d2 in combinations(unique, 2):
            pair_key = frozenset([d1, d2])
            
            if pair_key in KNOWN_INTERACTIONS:
                sev, desc = KNOWN_INTERACTIONS[pair_key]
                alerts.append({
                    'Prescription ID': row_id,
                    'Context': slot,
                    'Drug Pair': f"{d1} + {d2}",
                    'Warning': desc,
                    'Severity': sev
                })
    
    return alerts, parsed_log

# --- MAIN UI ---

with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3063/3063167.png", width=60)
    st.title("Setup")
    uploaded_file = st.file_uploader("Upload Data", type=['xlsx', 'csv'], label_visibility="collapsed")
    st.divider()
    debug_mode = st.checkbox("🐞 Show Parsed Data", value=False, help="See fuzzy match results.")

st.markdown("""
<div style="background-color:white;padding:1.5rem;border-radius:12px;box-shadow:0 4px 6px -1px rgba(0,0,0,0.05);margin-bottom:2rem;display:flex;align-items:center;gap:1rem;">
    <div style="font-size: 2.5rem;">💊</div>
    <div>
        <h1 style="margin:0; font-size: 1.8rem; color:#1e293b;">DDI Analyzer Pro</h1>
        <p style="margin:0; color:#64748b;">With Fuzzy Matching Engine</p>
    </div>
</div>
""", unsafe_allow_html=True)

if uploaded_file:
    try:
        if uploaded_file.name.endswith('.csv'): df = pd.read_csv(uploaded_file)
        else: df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"Error: {e}")
        st.stop()
        
    cols = df.columns.str.lower()
    resep_col = next((df.columns[i] for i, c in enumerate(cols) if 'resep' in c or 'obat' in c), None)
    if not resep_col and len(df.columns) > 1: resep_col = df.columns[1]
    
    if resep_col:
        st.success(f"✅ Scanning column: **{resep_col}**")
        if st.button("🚀 Start Analysis", type="primary"):
            all_alerts = []
            debug_logs = []
            
            bar = st.progress(0)
            for i, row in df.iterrows():
                rid = row.get('No', row.get('ID', i+1))
                rstr = str(row[resep_col])
                
                alerts, logs = analyze_row(rstr, rid)
                all_alerts.extend(alerts)
                if debug_mode and logs:
                    debug_logs.append({'ID': rid, 'Parsed': logs})
                
                bar.progress((i+1)/len(df))
            bar.empty()
            
            if debug_mode:
                with st.expander("🐞 Debug Log (Fuzzy Match Results)"):
                    st.write(pd.DataFrame(debug_logs))

            if all_alerts:
                res_df = pd.DataFrame(all_alerts)
                # Deduplicate same interaction appearing in 'Entire Prescription' AND 'Morning'
                res_df = res_df.drop_duplicates(subset=['Prescription ID', 'Drug Pair'])
                
                tab1, tab2 = st.tabs(["📊 Dashboard", "📋 Details"])
                
                with tab1:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("##### Severity")
                        sev_c = res_df['Severity'].value_counts().reset_index()
                        sev_c.columns = ['Severity', 'Count']
                        st.altair_chart(
                            alt.Chart(sev_c).mark_bar().encode(
                                x='Severity', y='Count', color='Severity'
                            ).properties(height=300),
                            use_container_width=True
                        )
                    with c2:
                        st.markdown("##### Top Pairs")
                        top = res_df['Drug Pair'].value_counts().head(10).reset_index()
                        top.columns = ['Pair', 'Count']
                        st.altair_chart(
                            alt.Chart(top).mark_bar().encode(
                                x='Count', y=alt.Y('Pair', sort='-x'), color=alt.value('#10b981')
                            ).properties(height=300),
                            use_container_width=True
                        )

                with tab2:
                    st.markdown("### Interaction Log")
                    st.dataframe(res_df, use_container_width=True, hide_index=True)
            else:
                st.warning("No interactions found. Check the Debug Log to see if fuzzy matching is working.")
