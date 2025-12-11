# --- HELPER FUNCTIONS ---

def clean_drug_name(raw_text):
    """
    Robust cleaning for 'Racikan', alternate styles, and messy inputs.
    Example: 
      "ANS AMLODIPIN 10 MG TABLET#30..." -> "AMLODIPIN"
      "Diagit 1/4 tablet..." -> "DIAGIT"
    """
    text = str(raw_text).upper().strip()
    
    # 1. Remove common noise prefixes like 'ANS' (from alternate style)
    text = re.sub(r'\bANS\b', '', text).strip()
    
    # 2. Handle multiline racikan (take top line)
    if '\n' in text:
        text = text.split('\n')[0]

    # 3. Handle alternate style separator '#' (DrugName#Quantity)
    if '#' in text:
        text = text.split('#')[0]
        
    # 4. Stop at common delimiters
    separators = [':', 'TAB', 'CAP', 'SYR', 'BTL', 'FLS', 'M.F.', 'PULV', 'DTD', 'NO.']
    for sep in separators:
        text = text.split(sep)[0]
        
    # 5. Remove non-alpha characters (keep spaces)
    text = re.sub(r'[^A-Z\s]', '', text) 
    return text.strip()

def parse_time_slots(prescription_str):
    s = prescription_str.lower()
    slots = set()
    
    # --- 1. Check for Alternate Style "1-0-0" Pattern (Morning-Noon-Night) ---
    # Matches patterns like "1-0-0", "0-1/2-0", "1-0-1"
    xyz_match = re.search(r'\b(\d+(?:/\d+)?)\s*-\s*(\d+(?:/\d+)?)\s*-\s*(\d+(?:/\d+)?)\b', s)
    if xyz_match:
        try:
            # Helper to parse values like "1" or "1/2"
            def is_positive(val_str):
                if '/' in val_str:
                    n, d = val_str.split('/')
                    return (float(n)/float(d)) > 0
                return float(val_str) > 0

            m_val, n_val, ni_val = xyz_match.groups()
            
            if is_positive(m_val): slots.add('Morning')
            if is_positive(n_val): slots.add('Noon')
            if is_positive(ni_val): slots.add('Night')
            
            # If we found this specific pattern, return immediately
            if slots: return list(slots)
        except ValueError:
            pass 

    # --- 2. Standard Text/Frequency Parsing ---
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
    
    # --- 1. Normalize Separators for Alternate Style ---
    # Convert '|||', newlines, and carriage returns into a standard semicolon delimiter
    normalized_row = row_str.replace('|||', ';').replace('\n', ';').replace('\r', ';')
    items = normalized_row.split(';')
    
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
                    # Parse time from the raw item string (which might contain "1-0-0" or "3 dd")
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
