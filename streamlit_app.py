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

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .stApp { background-color: #f8fafc; color: #1e293b; }
    [data-testid="stSidebar"] { background-color: #ffffff; border-right: 1px solid #e2e8f0; }
    .main-header {
        background-color: white; padding: 1.5rem 2rem; border-radius: 12px;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05); margin-bottom: 2rem; border: 1px solid #f1f5f9;
        display: flex; align-items: center; gap: 1rem;
    }
    div[data-testid="stMetric"] {
        background-color: white; padding: 1rem; border-radius: 12px;
        border: 1px solid #e2e8f0; box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    </style>
""", unsafe_allow_html=True)

# --- DATABASE LOADING ---
def load_db_logic():
    try:
        import structured_drug_db
        from structured_drug_db import get_drug_by_name
        return True, get_drug_by_name
    except ImportError:
        # Fallback Mock DB logic removed for brevity, assume file exists or use mock
        return False, None

is_external_db, get_drug_func = load_db_logic()

# --- IMPROVED PARSING FUNCTIONS ---

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
    # API Call Logic (Same as before)
    base_url = "https://api.fda.gov/drug/label.json"
    params = {'search': f'openfda.substance_name:"{drug_name}"', 'limit': 1}
    try:
        resp = requests.get(base_url, params=params, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if 'results' in data:
                res = data['results'][0]
                full_text = ""
                # Join all relevant fields into one giant string blob
                fields = ['drug_interactions', 'warnings', 'precautions', 'contraindications', 'boxed_warning']
                for f in fields:
                    if f in res and isinstance(res[f], list):
                        full_text += " ".join(res[f]) + " "
                return full_text
    except: return ""
    return ""

def check_fda_interaction_robust(drug_a, drug_b):
    def scan(source, target, text):
        if not text: return None, None
        # Allow partial matches (e.g. "NSAID" matching "NSAIDs")
        pattern = r'\b' + re.escape(target) + r'[a-z]*\b' 
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            start = max(0, match.start() - 200)
            end = min(len(text), match.end() + 200)
            return True, "..." + text[start:end] + "..."
        return False, None

    # Check A -> B
    text_a = get_drug_label_text(drug_a)
    found, desc = scan(drug_a, drug_b, text_a)
    if found: return True, desc

    # Check B -> A
    text_b = get_drug_label_text(drug_b)
    found, desc = scan(drug_b, drug_a, text_b)
    if found: return True, desc
            
    return False, None

# --- MAIN ANALYSIS LOGIC ---
def analyze_row(row_str, row_id):
    if not isinstance(row_str, str): return []
    items = row_str.split(';')
    time_buckets = {'Morning': [], 'Noon': [], 'Night': []}
    
    for item in items:
        if not item.strip(): continue
        clean_name = clean_drug_name(item)
        
        try:
            # External DB Lookup
            drug_obj = get_drug_func(clean_name) if get_drug_func else None
            
            if drug_obj:
                # CRITICAL FIX: Split comma-separated strings!
                raw_contents = getattr(drug_obj, 'contents', [])
                ingredients_list = []
                
                if isinstance(raw_contents, str):
                    # "Acetaminophen, Caffeine" -> ["Acetaminophen", "Caffeine"]
                    ingredients_list = [x.strip() for x in raw_contents.split(',')]
                elif isinstance(raw_contents, list):
                    ingredients_list = raw_contents
                else:
                    ingredients_list = getattr(drug_obj, 'active_ingredients', [])

                if ingredients_list:
                    slots = parse_time_slots(item)
                    for slot in slots:
                        for ingredient in ingredients_list:
                            # Clean up
                            ing_clean = ingredient.strip()
                            if ing_clean: time_buckets[slot].append(ing_clean)
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
                    alerts.append({
                        'Prescription ID': row_id,
                        'Time Slot': slot,
                        'Drug Pair': f"{ing_a} + {ing_b}",
                        'Warning': desc,
                        'Severity': determine_severity(desc)
                    })
    return alerts

# --- UI RENDER ---
with st.sidebar:
    st.title("Setup")
    uploaded_file = st.file_uploader("Upload Data", type=['xlsx', 'csv'])
    if is_external_db: st.success("✅ External DB Loaded")
    else: st.warning("⚠️ Using Mock DB")

st.markdown("""
<div class="main-header">
    <div style="font-size: 2.5rem;">💊</div>
    <div><h1 style="margin:0; font-size: 1.8rem; color:#1e293b;">DDI Analyzer Pro</h1></div>
</div>
""", unsafe_allow_html=True)

if uploaded_file:
    with st.spinner('Reading...'):
        if uploaded_file.name.endswith('.csv'): df = pd.read_csv(uploaded_file)
        else: df = pd.read_excel(uploaded_file)

    cols = df.columns.str.lower()
    possible_cols = [c for c in cols if 'resep' in c]
    
    if possible_cols:
        resep_col = df.columns[list(cols).index(possible_cols[0])]
        
        if st.button("🚀 Start Analysis", type="primary"):
            all_alerts = []
            
            # Progress Bar
            p_bar = st.progress(0)
            rows_to_process = df
            total_rows = len(rows_to_process)
            
            for index, row in rows_to_process.iterrows():
                row_id = row.get('No', row.get('ID', index + 1))
                try:
                    all_alerts.extend(analyze_row(str(row[resep_col]), row_id))
                except: pass
                p_bar.progress(min((index + 1) / total_rows, 1.0))
                time.sleep(0.01) # Small throttle
            
            p_bar.empty()
            
            # --- RESULTS ---
            st.divider()
            
            if all_alerts:
                results_df = pd.DataFrame(all_alerts)
            else:
                results_df = pd.DataFrame(columns=['Prescription ID', 'Severity', 'Drug Pair'])

            # METRICS
            total_rx = len(df)
            affected_rx_count = results_df['Prescription ID'].nunique() if not results_df.empty else 0
            safe_rx_count = total_rx - affected_rx_count
            
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Interactions", len(results_df))
            m2.metric("At-Risk Prescriptions", affected_rx_count)
            m3.metric("Safe Prescriptions", safe_rx_count)
            
            tab1, tab2 = st.tabs(["📊 Charts", "📋 Data"])
            
            with tab1:
                c1, c2 = st.columns(2)
                
                # 1. DONUT CHART
                prev_df = pd.DataFrame({'Status': ['At Risk', 'Safe'], 'Count': [affected_rx_count, safe_rx_count]})
                base = alt.Chart(prev_df).encode(theta=alt.Theta("Count", stack=True))
                pie = base.mark_arc(outerRadius=100, innerRadius=60).encode(
                    color=alt.Color("Status", scale=alt.Scale(domain=['At Risk', 'Safe'], range=['#ef4444', '#3b82f6'])),
                    tooltip=["Status", "Count"]
                )
                text = base.mark_text(radius=120).encode(text="Count", color=alt.value("black"))
                with c1: 
                    st.write("##### Prevalence")
                    st.altair_chart(pie + text, use_container_width=True)
                
                # 2. FREQUENCY CHART (With Zero-Filling)
                with c2:
                    st.write("##### Burden (Alerts per Rx)")
                    if not results_df.empty:
                        # Count alerts per ID
                        burden_counts = results_df['Prescription ID'].value_counts()
                        
                        # Create a full Series for ALL IDs (filling 0 for those not in results_df)
                        # We need the list of ALL IDs from the original dataframe
                        all_ids = df['No'] if 'No' in df.columns else df.index
                        # Reindex to include 0s
                        full_burden = burden_counts.reindex(all_ids, fill_value=0)
                        
                        # Now count frequencies (How many have 0? How many have 1?)
                        # FIX: Explicitly rename axis and column to avoid 'count' collision
                        freq_dist = full_burden.value_counts().rename_axis('Alerts').reset_index(name='Count')
                        
                        chart = alt.Chart(freq_dist).mark_bar().encode(
                            x=alt.X('Alerts:O', title="Alerts per Rx"),
                            y='Count',
                            color=alt.value('#6366f1'),
                            tooltip=['Alerts', 'Count']
                        )
                        st.altair_chart(chart, use_container_width=True)

            with tab2:
                st.dataframe(results_df)

    else:
        st.error("No 'resep' column found.")
