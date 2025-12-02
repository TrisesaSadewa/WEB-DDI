import streamlit as st
import pandas as pd
import requests
import re
import time
import numpy as np
from fuzzywuzzy import process as fw_process

# --- CONFIGURATION ---
st.set_page_config(
    page_title="DDI Analysis Tool", 
    layout="wide",
    page_icon="💊"
)

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    .main {
        background-color: #f8f9fa;
    }
    .stMetric {
        background-color: #ffffff;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    div[data-testid="stExpander"] {
        background-color: white;
        border-radius: 10px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

# --- DATABASE LOADING LOGIC ---
def load_db_logic():
    """Attempts to load external DB, falls back to Mock DB."""
    try:
        # Tries to import from the file you uploaded to the folder
        import structured_drug_db
        from structured_drug_db import get_drug_by_name
        return True, get_drug_by_name
    except ImportError:
        # --- MOCK DB (Fallback if file is missing) ---
        class MockDrug:
            def __init__(self, name, contents):
                self.name = name
                self.contents = contents # Matches your file structure

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
            'SPIRONOLACTONE': ['SPIRONOLACTONE'],
            'IBUPROFEN': ['IBUPROFEN'],
            'DEXAMETHASONE': ['DEXAMETHASONE'],
            'KETOROLAC': ['KETOROLAC'],
            'ONDANSETRON': ['ONDANSETRON']
        }

        def mock_get_drug_by_name(query):
            query_upper = query.upper()
            # 1. Exact match
            if query_upper in MOCK_DRUG_DB:
                return MockDrug(query_upper, MOCK_DRUG_DB[query_upper])
            # 2. Fuzzy match
            match, score = fw_process.extractOne(query_upper, MOCK_DRUG_DB.keys())
            if score > 85:
                return MockDrug(match, MOCK_DRUG_DB[match])
            return None

        return False, mock_get_drug_by_name

# Initialize DB
is_external_db, get_drug_func = load_db_logic()

# --- HELPER FUNCTIONS ---

def clean_drug_name(raw_text):
    """Extracts the likely brand name from the raw string."""
    text = str(raw_text).upper()
    # Remove common prescription noise
    text = text.split(':')[0] 
    text = text.split('TAB')[0]
    text = text.split('CAP')[0]
    text = text.split('SYR')[0]
    text = text.split('BTL')[0]
    text = text.split('FLS')[0]
    # Keep only letters and spaces
    text = re.sub(r'[^A-Z\s]', '', text) 
    return text.strip()

def parse_time_slots(prescription_str):
    """Parses dosage instructions to assign time slots."""
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

@st.cache_data(ttl=3600) 
def check_fda_interaction(drug_a, drug_b):
    """Queries OpenFDA to check if Drug A's label mentions Drug B in warnings."""
    base_url = "https://api.fda.gov/drug/label.json"
    
    # Query for Drug A's label looking for B
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
                
    except Exception:
        return False, None
        
    return False, None

def analyze_row(row_str, row_id):
    """Process a single prescription row."""
    if not isinstance(row_str, str):
        return []

    items = row_str.split(';')
    
    # 1. Bucketize drugs by time
    time_buckets = {'Morning': [], 'Noon': [], 'Night': []}
    
    for item in items:
        if not item.strip(): continue
        clean_name = clean_drug_name(item)
        
        try:
            drug_obj = get_drug_func(clean_name)
            
            if drug_obj:
                # --- FIX FOR ATTRIBUTE ERROR ---
                # Your file uses 'contents', not 'active_ingredients'
                # We also need to handle if contents is a String or a List
                
                raw_contents = getattr(drug_obj, 'contents', [])
                
                ingredients_list = []
                if isinstance(raw_contents, str):
                    # Handle "Acetaminophen, Caffeine" string format
                    ingredients_list = [x.strip() for x in raw_contents.split(',')]
                elif isinstance(raw_contents, list):
                    # Handle ["Attapulgite", "Pectin"] list format
                    ingredients_list = raw_contents
                else:
                    # Fallback
                    ingredients_list = getattr(drug_obj, 'active_ingredients', [])

                if ingredients_list:
                    slots = parse_time_slots(item)
                    for slot in slots:
                        for ingredient in ingredients_list:
                            # Clean ingredient name just in case
                            time_buckets[slot].append(ingredient.strip())
                            
        except Exception as e:
            # Silently skip bad drug entries to prevent full crash
            continue

    # 2. Check interactions within buckets
    alerts = []
    
    for slot, ingredients in time_buckets.items():
        if len(ingredients) < 2: continue
        
        unique_ingredients = list(set(ingredients))
        for i in range(len(unique_ingredients)):
            for j in range(i + 1, len(unique_ingredients)):
                ing_a = unique_ingredients[i]
                ing_b = unique_ingredients[j]
                
                # Check FDA
                has_interaction, desc = check_fda_interaction(ing_a, ing_b)
                
                if has_interaction:
                    alerts.append({
                        'Prescription ID': row_id,
                        'Time Slot': slot,
                        'Drug Pair': f"{ing_a} + {ing_b}",
                        'Warning': desc,
                        'Severity': 'Review Required'
                    })
    return alerts

# --- MAIN UI ---

# Sidebar for Setup
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/3063/3063167.png", width=60)
    st.header("1. Upload Data")
    uploaded_file = st.file_uploader("Upload .xlsx or .csv", type=['xlsx', 'csv'])
    
    st.divider()
    
    st.header("System Status")
    if is_external_db:
        st.success("✅ External DB Loaded")
        st.caption("Using `structured_drug_db.py`")
    else:
        st.warning("⚠️ Using Mock Database")
        st.caption("`structured_drug_db.py` not detected. Using internal dictionary.")
    
    st.info("ℹ️ **Data Privacy:** Processed locally. OpenFDA API used for label text.")

# Main Page
st.title("💊 DDI Analyzer Pro")
st.markdown("Automated detection of **drug-drug interactions** with **time-segmentation** (Morning/Noon/Night).")

if uploaded_file:
    # Load Data
    with st.spinner('Reading file...'):
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
            
    # Column Discovery
    cols = df.columns.str.lower()
    resep_col = None
    possible_cols = [c for c in cols if 'resep' in c]
    if possible_cols:
        target_col_name = df.columns[list(cols).index(possible_cols[0])]
        resep_col = target_col_name
    
    if not resep_col:
        st.error("❌ Column 'resep' not found. Please ensure your file contains the prescription column.")
        st.dataframe(df.head())
    else:
        # Show Data Preview
        with st.expander("📄 Click to view Uploaded Data Preview", expanded=False):
            st.dataframe(df.head(), use_container_width=True)

        if st.button("🚀 Run Analysis", type="primary", use_container_width=True):
            all_alerts = []
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            rows_to_process = df
            total_rows = len(rows_to_process)
            
            for index, row in rows_to_process.iterrows():
                row_str = str(row[resep_col])
                
                # Identify ID column (optional)
                row_id = row.get('No', row.get('ID', index + 1))
                
                # Analyze
                try:
                    alerts = analyze_row(row_str, row_id)
                    all_alerts.extend(alerts)
                except Exception as e:
                    print(f"Row {index} failed: {e}")
                
                # Update UI
                pct = (index + 1) / total_rows
                progress_bar.progress(min(pct, 1.0))
                status_text.text(f"Processing row {index + 1}/{total_rows}...")
                
                # Rate limit politeness
                time.sleep(0.05)
                
            progress_bar.empty()
            status_text.empty()
            st.divider()
            
            # --- RESULTS DASHBOARD ---
            if all_alerts:
                results_df = pd.DataFrame(all_alerts)
                
                # 1. Metrics Row
                m1, m2, m3 = st.columns(3)
                m1.metric("Total Interactions", len(results_df), delta_color="inverse")
                m2.metric("Affected Prescriptions", results_df['Prescription ID'].nunique(), delta_color="inverse")
                m3.metric("Unique Drug Pairs", results_df['Drug Pair'].nunique())
                
                st.divider()

                # 2. Tabs for different views
                tab1, tab2, tab3 = st.tabs(["📊 Charts", "📋 Detailed Log", "📥 Export"])
                
                with tab1:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.subheader("Interactions by Time Slot")
                        st.bar_chart(results_df['Time Slot'].value_counts(), color="#FF4B4B")
                    with c2:
                        st.subheader("Most Frequent Pairs")
                        st.bar_chart(results_df['Drug Pair'].value_counts().head(10))

                with tab2:
                    st.subheader("Interaction Details")
                    # Search box
                    search_term = st.text_input("🔍 Search drug name, ID, or warning text", "")
                    
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
                            "Warning": st.column_config.TextColumn("FDA Warning Text", width="large"),
                        }
                    )

                with tab3:
                    csv = results_df.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Full Report (CSV)",
                        data=csv,
                        file_name="ddi_analysis_report.csv",
                        mime="text/csv",
                        type="primary"
                    )
            else:
                st.success("✅ No major interactions detected in the analyzed sample.")
                st.balloons()
else:
    st.info("👈 Please upload a file to begin.")
