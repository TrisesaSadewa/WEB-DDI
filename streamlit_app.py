import streamlit as st
import pandas as pd
import requests
import re
import time
import numpy as np
from fuzzywuzzy import process as fw_process

# --- CONFIGURATION ---
st.set_page_config(page_title="DDI Analysis Tool", layout="wide")
st.title("💊 Prescription Drug-Drug Interaction Analyzer")
st.markdown("""
This tool analyzes prescriptions for potential interactions.
It attempts to load your local `structured_drug_db` logic. If not found, it uses a simplified internal database.
""")

# --- DATABASE LOADING LOGIC ---
# This block handles the "External File" request.
# It tries to import your file relative to this script's location (not C: drive)
try:
    # This expects structured_drug_db.py to be in the SAME directory as this file
    import structured_drug_db
    from structured_drug_db import get_drug_by_name, Drug
    
    USING_EXTERNAL_DB = True
    st.success("✅ Successfully loaded external `structured_drug_db.py` module.")
    
except ImportError:
    USING_EXTERNAL_DB = False
    st.warning("⚠️ `structured_drug_db.py` not found in the directory. Using simplified Mock Database instead.")

    # --- MOCK DB (Fallback) ---
    class Drug:
        def __init__(self, name, active_ingredients):
            self.name = name
            self.active_ingredients = active_ingredients

    # Simplified mapping (Fallback)
    MOCK_DRUG_DB = {
        'ACRAN': ['RANITIDINE'],
        'VOSEDON': ['DOMPERIDONE'],
        'LODIA': ['LOPERAMIDE'],
        'SPASMINAL': ['METAMIZOLE', 'HYOSCINE'],
        'NEW DIATAB': ['ATTAPULGITE'],
        'BRAXIDIN': ['CHLORDIAZEPOXIDE', 'CLIDINIUM'],
        'SANMOL': ['PARACETAMOL'],
        'COTRIMOXAZOL': ['SULFAMETHOXAZOLE', 'TRIMETHOPRIM'],
        'ZINC': ['ZINC'],
        'AMOXSAN': ['AMOXICILLIN'],
        'TREMENZA': ['PSEUDOEPHEDRINE', 'TRIPROLIDINE'],
        'INTERHISTIN': ['MEBHYDROLIN'],
        'CEFIXIME': ['CEFIXIME'],
        'METHYLPREDNISOLONE': ['METHYLPREDNISOLONE'],
        'SALBUTAMOL': ['SALBUTAMOL'],
        'AMBROXOL': ['AMBROXOL'],
        'CETIRIZINE': ['CETIRIZINE'],
        'CANDESARTAN': ['CANDESARTAN'],
        'AMLODIPINE': ['AMLODIPINE'],
        'SIMVASTATIN': ['SIMVASTATIN'],
        'ASPILET': ['ASPIRIN'],
        'CPG': ['CLOPIDOGREL'],
        'GLIMEPIRIDE': ['GLIMEPIRIDE'],
        'METFORMIN': ['METFORMIN'],
        'LANSOPRAZOLE': ['LANSOPRAZOLE'],
        'BISOPROLOL': ['BISOPROLOL'],
        'FUROSEMIDE': ['FUROSEMIDE'],
        'DIGOXIN': ['DIGOXIN'],
        'SPIRONOLACTONE': ['SPIRONOLACTONE']
    }

    def get_drug_by_name(query):
        # 1. Exact match
        query_upper = query.upper()
        if query_upper in MOCK_DRUG_DB:
            return Drug(query_upper, MOCK_DRUG_DB[query_upper])
        
        # 2. Fuzzy match
        match, score = fw_process.extractOne(query_upper, MOCK_DRUG_DB.keys())
        if score > 85:
            return Drug(match, MOCK_DRUG_DB[match])
        return None

# --- HELPER FUNCTIONS ---

def clean_drug_name(raw_text):
    """Extracts the likely brand name from the raw string."""
    text = str(raw_text).upper()
    # Simple heuristic cleaning
    text = text.split(':')[0] 
    text = text.split('TAB')[0]
    text = text.split('CAP')[0]
    text = re.sub(r'[^A-Z\s]', '', text) 
    return text.strip()

def parse_time_slots(prescription_str):
    """
    Parses dosage instructions to assign time slots.
    """
    s = prescription_str.lower()
    slots = set()
    
    # Frequency detection logic
    freq = 1
    if '2 dd' in s or '2x' in s: freq = 2
    elif '3 dd' in s or '3x' in s: freq = 3
    elif '4 dd' in s or '4x' in s: freq = 4
    elif '1 dd' in s or '1x' in s: freq = 1
    
    # Specific time keywords
    if 'malam' in s or 'night' in s: slots.add('Night')
    if 'pagi' in s or 'morning' in s: slots.add('Morning')
    if 'siang' in s or 'noon' in s: slots.add('Noon')
    if 'sore' in s: slots.add('Night') 

    # Default filling
    if not slots:
        if freq >= 1: slots.add('Morning')
        if freq >= 2: slots.add('Night')
        if freq >= 3: slots.add('Noon')
            
    return list(slots)

# Caching FDA calls to prevent rate limiting
@st.cache_data(ttl=3600) 
def check_fda_interaction(drug_a, drug_b):
    """
    Queries OpenFDA to check if Drug A's label mentions Drug B in warnings.
    """
    base_url = "https://api.fda.gov/drug/label.json"
    
    # Query for Drug A's label
    search_query = f'openfda.substance_name:"{drug_a}"+AND+(drug_interactions:"{drug_b}"+OR+warnings:"{drug_b}")'
    params = {'search': search_query, 'limit': 1}
    
    try:
        # Check A -> B
        resp = requests.get(base_url, params=params, timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            if 'results' in data:
                text = data['results'][0].get('drug_interactions', [''])[0]
                if not text: text = data['results'][0].get('warnings', [''])[0]
                return True, text[:300] + "..."
        
        # Check B -> A (Reverse lookup)
        search_query_rev = f'openfda.substance_name:"{drug_b}"+AND+(drug_interactions:"{drug_a}"+OR+warnings:"{drug_a}")'
        params_rev = {'search': search_query_rev, 'limit': 1}
        resp_rev = requests.get(base_url, params=params_rev, timeout=5)
        if resp_rev.status_code == 200:
            data = resp_rev.json()
            if 'results' in data:
                text = data['results'][0].get('drug_interactions', [''])[0]
                return True, text[:300] + "..."
                
    except Exception as e:
        return False, None
        
    return False, None

def analyze_row(row_str, row_id):
    """Process a single prescription row."""
    items = row_str.split(';')
    
    # 1. Bucketize drugs by time
    time_buckets = {'Morning': [], 'Noon': [], 'Night': []}
    
    for item in items:
        if not item.strip(): continue
        clean_name = clean_drug_name(item)
        
        # Use whatever DB is available (External or Mock)
        drug_obj = get_drug_by_name(clean_name)
        
        if drug_obj:
            slots = parse_time_slots(item)
            for slot in slots:
                # Add all active ingredients
                for ingredient in drug_obj.active_ingredients:
                    time_buckets[slot].append(ingredient)

    # 2. Check interactions within buckets
    alerts = []
    
    for slot, ingredients in time_buckets.items():
        if len(ingredients) < 2: continue
        
        # Check pairs
        unique_ingredients = list(set(ingredients))
        for i in range(len(unique_ingredients)):
            for j in range(i + 1, len(unique_ingredients)):
                ing_a = unique_ingredients[i]
                ing_b = unique_ingredients[j]
                
                # Call FDA API (Cached)
                has_interaction, desc = check_fda_interaction(ing_a, ing_b)
                
                if has_interaction:
                    alerts.append({
                        'ID': row_id,
                        'Time': slot,
                        'Pair': f"{ing_a} + {ing_b}",
                        'Description': desc,
                        'Severity': 'Check Label'
                    })
    return alerts

# --- MAIN UI ---

uploaded_file = st.file_uploader("Upload Excel or CSV", type=['xlsx', 'csv'])

if uploaded_file:
    with st.spinner('Loading data...'):
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
    st.success(f"Loaded {len(df)} rows.")
    
    # Find column
    cols = df.columns.str.lower()
    resep_col = None
    # Flexible column finder
    possible_cols = [c for c in cols if 'resep' in c]
    if possible_cols:
        resep_col = df.columns[list(cols).index(possible_cols[0])]
    
    if not resep_col:
        st.error("Could not find a column named 'resep'. Please rename your column.")
        st.write("Available columns:", df.columns.tolist())
    else:
        if st.button("Run Analysis"):
            all_alerts = []
            progress_bar = st.progress(0)
            
            # Limit for demo purposes - REMOVE [:20] for full run
            rows_to_process = df # Processing all rows now
            total_rows = len(rows_to_process)
            
            for index, row in rows_to_process.iterrows():
                row_str = str(row[resep_col])
                alerts = analyze_row(row_str, index)
                all_alerts.extend(alerts)
                
                # Update progress bar
                progress_bar.progress(min((index + 1) / total_rows, 1.0))
                
                # Add a tiny sleep to be nice to the FDA API free tier
                time.sleep(0.1)
                
            st.divider()
            
            if all_alerts:
                results_df = pd.DataFrame(all_alerts)
                
                # Metrics
                col1, col2 = st.columns(2)
                col1.metric("Total Interactions Found", len(results_df))
                col2.metric("Affected Prescriptions", results_df['ID'].nunique())
                
                # Chart
                st.subheader("Interactions by Time Slot")
                st.bar_chart(results_df['Time'].value_counts())
                
                # Table
                st.subheader("Detailed Interaction Log")
                st.dataframe(results_df, use_container_width=True)
                
                # Download
                csv = results_df.to_csv(index=False).encode('utf-8')
                st.download_button("Download Report", csv, "ddi_report.csv", "text/csv")
            else:
                st.info("No interactions detected in the processed sample.")