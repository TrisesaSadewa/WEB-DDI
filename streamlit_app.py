import streamlit as st
import pandas as pd
import requests
import re
import time
import altair as alt
from itertools import combinations

# --- SAFELY IMPORT OPTIONAL MODULES ---
try:
    from fuzzywuzzy import process
    FUZZY_AVAILABLE = True
except ImportError:
    FUZZY_AVAILABLE = False

try:
    from structured_drug_db import get_drug_by_name
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    def get_drug_by_name(name): return None

# --- CONFIGURATION ---
st.set_page_config(page_title="DDI Analysis Tool", layout="wide", page_icon="💊")

# --- 1. ROBUST TRANSLATION MAP (The "Rosetta Stone") ---
# Maps specific variations found in your datasets to the EXACT keys used in KNOWN_INTERACTIONS
ID_TO_EN_MAP = {
    # Aspirin Variants
    'ACETYLSALICYLIC ACID': 'ASPIRIN', 'ACETYL SALICYLIC ACID': 'ASPIRIN',
    'ASAM ASETILSALISILAT': 'ASPIRIN', 'ASETOSAL': 'ASPIRIN',
    'MINIASPI': 'ASPIRIN', 'NOSPIRINAL': 'ASPIRIN', 'ASPILET': 'ASPIRIN',
    'THROMBO': 'ASPIRIN', 'THROMBO ASPILOTS': 'ASPIRIN',
    
    # Amlodipine Variants
    'AMLODIPIN': 'AMLODIPINE', 'AMLODIPINE BESILATE': 'AMLODIPINE',
    
    # Folic Acid Variants
    'ASAM FOLAT': 'FOLIC ACID', 'FOLIC ACID': 'FOLIC ACID',
    
    # Tranexamic Acid
    'ASAM TRANEKSAMAT': 'TRANEXAMIC ACID', 'TRANEXAMIC': 'TRANEXAMIC ACID',
    
    # Acetaminophen
    'PARASETAMOL': 'ACETAMINOPHEN', 'PARACETAMOL': 'ACETAMINOPHEN',
    
    # Others
    'GLIBENKLAMID': 'GLYBURIDE', 'GLIBENCLAMIDE': 'GLYBURIDE',
    'KLOPIDOGREL': 'CLOPIDOGREL', 'CLOPIDOGREL BISULFATE': 'CLOPIDOGREL',
    'KANDESARTAN': 'CANDESARTAN', 'CANDESARTAN CILEXETIL': 'CANDESARTAN',
    'BISOPROLOL': 'BISOPROLOL', 'BISOPROLOL FUMARATE': 'BISOPROLOL',
    'FUROSEMID': 'FUROSEMIDE', 'LASIX': 'FUROSEMIDE',
    'SPIRONOLAKTON': 'SPIRONOLACTONE', 'SPIRONOLACTON': 'SPIRONOLACTONE',
    'SIMVASTATIN': 'SIMVASTATIN', 
    'FENITOIN': 'PHENYTOIN', 'PHENYTOIN SODIUM': 'PHENYTOIN', 'KUTOIN': 'PHENYTOIN',
    'V-BLOC': 'CARVEDILOL', 'CARVEDILOL': 'CARVEDILOL',
    'NITROKAF': 'NITROGLYCERIN', 'GLISERIL TRINITRAT': 'NITROGLYCERIN',
    'SUCRALFATE': 'SUCRALFATE', 
    'IBUPROFEN': 'IBUPROFEN', 
    'OMEPRAZOLE': 'OMEPRAZOLE', 'OMEPRAZOL': 'OMEPRAZOLE',
    'VALSARTAN': 'VALSARTAN', 
    'MELOXICAM': 'MELOXICAM', 
    'CAPTOPRIL': 'CAPTOPRIL', 
    'METFORMIN': 'METFORMIN', 'METFORMIN HCL': 'METFORMIN',
    'GABAPENTIN': 'GABAPENTIN', 
    'FENOFIBRATE': 'FENOFIBRATE', 
    'NIFEDIPINE': 'NIFEDIPINE', 
    'DIGOXIN': 'DIGOXIN', 
    'METHYL PREDNISOLON': 'METHYLPREDNISOLONE', 'METHYLPREDNISOLONE': 'METHYLPREDNISOLONE',
    'NOTISIL': 'DIAZEPAM', 
    'WARFARIN': 'WARFARIN', 'SIMARC': 'WARFARIN'
}

# --- 2. KNOWLEDGE BASE (Strict English Keys) ---
KNOWN_INTERACTIONS = {
    # Major
    frozenset(['AMLODIPINE', 'PHENYTOIN']): ('Major', 'Phenytoin decreases levels of Amlodipine by increasing metabolism.'),
    frozenset(['ASPIRIN', 'IBUPROFEN']): ('Major', 'Ibuprofen may interfere with the anti-platelet effect of low-dose Aspirin.'),
    frozenset(['FENOFIBRATE', 'SIMVASTATIN']): ('Major', 'Increased risk of myopathy/rhabdomyolysis.'),
    frozenset(['CLOPIDOGREL', 'WARFARIN']): ('Major', 'Increased risk of bleeding.'),
    frozenset(['WARFARIN', 'MELOXICAM']): ('Major', 'NSAIDs increase bleeding risk with Anticoagulants.'),
    
    # Moderate
    frozenset(['CARVEDILOL', 'IBUPROFEN']): ('Moderate', 'NSAIDs may diminish the antihypertensive effect of Beta-blockers.'),
    frozenset(['PHENYTOIN', 'FOLIC ACID']): ('Moderate', 'Phenytoin may decrease serum Folic Acid; Folic Acid may decrease Phenytoin levels.'),
    frozenset(['MELOXICAM', 'CAPTOPRIL']): ('Moderate', 'NSAIDs may diminish the antihypertensive effect of ACE Inhibitors.'),
    frozenset(['MELOXICAM', 'METFORMIN']): ('Moderate', 'Use with caution (renal function monitoring).'),
    frozenset(['MELOXICAM', 'GLYBURIDE']): ('Moderate', 'NSAIDs may increase the effect of sulfonylureas (hypoglycemia risk).'),
    frozenset(['MELOXICAM', 'FENOFIBRATE']): ('Moderate', 'Potential risk of renal toxicity.'),
    frozenset(['MELOXICAM', 'NIFEDIPINE']): ('Moderate', 'NSAIDs may diminish the antihypertensive effect of Calcium Channel Blockers.'),
    frozenset(['CAPTOPRIL', 'METFORMIN']): ('Moderate', 'ACE inhibitors may enhance the hypoglycemic effect of Metformin.'),
    
    # Minor
    frozenset(['SPIRONOLACTONE', 'DIGOXIN']): ('Minor', 'Spironolactone may increase Digoxin levels.'),
}

# --- HELPER FUNCTIONS ---

def clean_drug_name(raw_text):
    if not isinstance(raw_text, str): return ""
    text = raw_text.upper().strip()
    
    # 1. Aggressive Cleaning (R/, prefixes, parens)
    text = re.sub(r'\b(ANS|KIE|RESEP|R/|OBAT)\b', '', text).strip() # Added R/
    text = re.sub(r'\([^)]*\)', '', text).strip() # Remove (generic name) or (brand) in parens
    text = re.split(r'[#:]', text)[0].strip()
    
    if '\n' in text: text = text.split('\n')[0].strip()
    
    # Remove dosage forms/units
    text = re.sub(r'\b(TAB|CAP|SYR|DROP|TABLET|KAPSUL|INJEKSI|MG|ML|G|PRN|RETARD|BESILATE|HCL)\b', '', text)
    text = re.sub(r'\b\d+([.,]\d+)?\b', '', text)
    text = re.sub(r'\s+', ' ', text).strip()
    
    if not text: return ""

    # 2. Check Map (Exact or Substring)
    if text in ID_TO_EN_MAP: return ID_TO_EN_MAP[text]
    
    # Substring check: e.g. "AMLODIPIN 10" -> matches key "AMLODIPIN"
    for k, v in ID_TO_EN_MAP.items():
        if k in text: return v
            
    return text

def safe_parse_fraction(val_str):
    try:
        if '/' in val_str:
            n, d = val_str.split('/')
            return float(n) / float(d)
        return float(val_str)
    except:
        return 0.0

def parse_time_slots(prescription_str):
    s = prescription_str.lower()
    slots = set()
    
    xyz_match = re.search(r'\b(\d+(?:/\d+)?)\s*-\s*(\d+(?:/\d+)?)\s*-\s*(\d+(?:/\d+)?)\b', s)
    if xyz_match:
        m, n, ni = xyz_match.groups()
        if safe_parse_fraction(m) > 0: slots.add('Morning')
        if safe_parse_fraction(n) > 0: slots.add('Noon')
        if safe_parse_fraction(ni) > 0: slots.add('Night')

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
    
    # Normalize
    normalized_row = row_str.replace('|||', ';').replace('\n', ';').replace('\r', ';')
    items = [x for x in normalized_row.split(';') if x.strip()]
    
    time_buckets = {'Morning': [], 'Noon': [], 'Night': [], 'Entire Prescription': []}
    parsed_log = []
    
    for item in items:
        canonical = clean_drug_name(item)
        if not canonical or len(canonical) < 3: continue
        
        # Log exact translation
        parsed_log.append(f"Raw: {item[:15]}... -> Cln: {canonical}")
        
        slots = parse_time_slots(item)
        for slot in slots:
            time_buckets[slot].append(canonical)
        time_buckets['Entire Prescription'].append(canonical)

    alerts = []
    
    # Analyze
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
    debug_mode = st.checkbox("🐞 Show Parsed Data", value=False)

st.markdown("""
<div style="background-color:white;padding:1.5rem;border-radius:12px;margin-bottom:2rem;display:flex;align-items:center;gap:1rem;">
    <div style="font-size: 2.5rem;">💊</div>
    <div>
        <h1 style="margin:0; font-size: 1.8rem; color:#1e293b;">DDI Analyzer Pro</h1>
        <p style="margin:0; color:#64748b;">Universal Parser V2.2</p>
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
    resep_col = next((df.columns[i] for i, c in enumerate(cols) if 'resep' in c or 'obat' in c or 'presc' in c), None)
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
                with st.expander("🐞 Debug Log (Check Translations)"):
                    st.write(pd.DataFrame(debug_logs))

            if all_alerts:
                res_df = pd.DataFrame(all_alerts)
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
                            ).properties(height=300)
                        )
                    with c2:
                        st.markdown("##### Top Pairs")
                        top = res_df['Drug Pair'].value_counts().head(10).reset_index()
                        top.columns = ['Pair', 'Count']
                        st.altair_chart(
                            alt.Chart(top).mark_bar().encode(
                                x='Count', y=alt.Y('Pair', sort='-x'), color=alt.value('#10b981')
                            ).properties(height=300)
                        )

                with tab2:
                    st.dataframe(res_df, hide_index=True)
            else:
                st.warning("No interactions found. Check the Debug Log to ensure 'Raw' names map to 'Clean' English names.")
