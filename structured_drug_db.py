# --- Efficient and Structured Drug Database for NER System ---

from collections import namedtuple
from fuzzywuzzy import process

# Define structured data types for both drugs and equipment
Drug = namedtuple('Drug', ['name', 'generic', 'contents'])
Equipment = namedtuple('Equipment', ['name', 'type', 'contents'])

# List of all drugs and brands (single source of truth)
DRUGS = [
    Drug(name='paracetamol', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='panadol', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='paracetamol extra', generic='Paracetamol', contents='Acetaminophen, Caffeine'),
    Drug(name='panadol extra', generic='Paracetamol', contents='Acetaminophen, Caffeine'),
    Drug(name='acetaminophen', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='Sanmol', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='Cetamol', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='NEO KAOLANA', generic='Attapulgite, Pectin', contents='Attapulgite, Pectin, Kaolin'),
    Drug(name='KAOLANA', generic='Attapulgite, Pectin', contents=['Attapulgite', 'Pectin', 'Kaolin']),
    Drug(name='bodrex', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='ponstan', generic='Mefenamic Acid', contents='Mefenamic Acid'),
    Drug(name='aspirin', generic='Acetylsalicylic Acid', contents='Acetylsalicylic Acid'),
    Drug(name='ibuprofen', generic='Ibuprofen', contents='Ibuprofen'),
    Drug(name='promag', generic='Hydrotalcite, Magnesium Hydroxide, Simethicone', contents='Hydrotalcite, Magnesium Hydroxide, Simethicone'),
    Drug(name='amoxicillin', generic='Amoxicillin', contents='Amoxicillin'),
    Drug(name='cefixime', generic='Cefixime', contents='Cefixime'),
    Drug(name='azithromycin', generic='Azithromycin', contents='Azithromycin'),
    Drug(name='ciprofloxacin', generic='Ciprofloxacin', contents='Ciprofloxacin'),
    Drug(name='metronidazole', generic='Metronidazole', contents='Metronidazole'),
    Drug(name='clavic', generic='Amoxicillin Trihydrate, Potassium Clavulanate', contents='Amoxicillin Trihydrate, Potassium Clavulanate'),
    Drug(name='decadryl', generic='Diphenhydramine Hydrochloride, Ammonium Chloride', contents='Diphenhydramine Hydrochloride, Ammonium Chloride'),
    Drug(name='bisolvon', generic='Bromhexine Hydrochloride', contents='Bromhexine Hydrochloride'),
    Drug(name='actifed', generic='Pseudoephedrine Hydrochloride, Triprolidine Hydrochloride', contents='Pseudoephedrine Hydrochloride, Triprolidine Hydrochloride'),
    Drug(name='obh combi', generic='Succus Liquiritiae, Ammonium Chloride, Paracetamol', contents='Succus Liquiritiae, Ammonium Chloride, Paracetamol'),
    Drug(name='paratusin', generic='Paracetamol, Noscapine, Chlorpheniramine Maleate', contents='Paracetamol, Noscapine, Chlorpheniramine Maleate'),
    Drug(name='cetirizine', generic='Cetirizine', contents='Cetirizine'),
    Drug(name='loratadine', generic='Loratadine', contents='Loratadine'),
    Drug(name='incidal', generic='Cetirizine Dihydrochloride', contents='Cetirizine Dihydrochloride'),
    Drug(name='interhistin', generic='Mebhydrolin Napadisylate', contents='Mebhydrolin Napadisylate'),
    Drug(name='ctm', generic='Chlorphenamine Maleate', contents='Chlorphenamine Maleate'),
    Drug(name='omeprazole', generic='Omeprazole', contents='Omeprazole'),
    Drug(name='ranitidine', generic='Ranitidine', contents='Ranitidine'),
    Drug(name='gastran', generic='Cimetidine', contents='Cimetidine'),
    Drug(name='mylanta', generic='Aluminium Hydroxide, Magnesium Hydroxide, Simethicone', contents='Aluminium Hydroxide, Magnesium Hydroxide, Simethicone'),
    Drug(name='lansoprazole', generic='Lansoprazole', contents='Lansoprazole'),
    Drug(name='captopril', generic='Captopril', contents='Captopril'),
    Drug(name='amlodipine', generic='Amlodipine', contents='Amlodipine'),
    Drug(name='valsartan', generic='Valsartan', contents='Valsartan'),
    Drug(name='bisoprolol', generic='Bisoprolol Fumarate', contents='Bisoprolol Fumarate'),
    Drug(name='simvastatin', generic='Simvastatin', contents='Simvastatin'),
    Drug(name='atorvastatin', generic='Atorvastatin', contents='Atorvastatin'),
    Drug(name='lupin', generic='Lisinopril', contents='Lisinopril'),
    Drug(name='metformin', generic='Metformin', contents='Metformin'),
    Drug(name='glimepiride', generic='Glimepiride', contents='Glimepiride'),
    Drug(name='glyburide', generic='glyburide', contents='glyburide'),
    Drug(name='insulin', generic='Insulin', contents='Insulin'),
    Drug(name='vitamin c', generic='Ascorbic Acid', contents='Ascorbic Acid'),
    Drug(name='vitamin b12', generic='Cyanocobalamin', contents='Cyanocobalamin'),
    Drug(name='becom-c', generic='Vitamin B Complex, Vitamin C', contents='Vitamin B Complex, Vitamin C'),
    Drug(name='folic acid', generic='Folic Acid', contents='Folic Acid'),
    Drug(name='oscal', generic='Calcium Carbonate', contents='Calcium Carbonate'),
    Drug(name='domperidone', generic='Domperidone', contents='Domperidone'),
    Drug(name='betadine', generic='Povidone-Iodine', contents='Povidone-Iodine'),
    Drug(name='dexteem', generic='Dexamethasone, Dexchlorpheniramine Maleate', contents='Dexamethasone, Dexchlorpheniramine Maleate'),
    Drug(name='kalpanax', generic='Miconazole Nitrate', contents='Miconazole Nitrate'),
    Drug(name='oralit', generic='Glucose, Sodium Chloride, Potassium Chloride', contents='Glucose, Sodium Chloride, Potassium Chloride'),
    Drug(name='vicks vaporub', generic='Camphor, Menthol, Eucalyptus Oil', contents='Camphor, Menthol, Eucalyptus Oil'),
    Drug(name='salbutamol', generic='Salbutamol', contents='Salbutamol'),
    Drug(name='cetaphil', generic='Cetaphil', contents='Cetaphil'),
    Drug(name='dumin', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='cataflam', generic='Diclofenac Potassium', contents='Diclofenac Potassium'),
    Drug(name='neurontin', generic='Gabapentin', contents='Gabapentin'),
    Drug(name='biogesic', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='antimo', generic='Dimenhydrinate', contents='Dimenhydrinate'),
    Drug(name='diapet', generic='Atapulgite, Pectin', contents='Atapulgite, Pectin'),
    Drug(name='enervon c', generic='Vitamin B Complex, Vitamin C, Zinc', contents='Vitamin B Complex, Vitamin C, Zinc'),
    Drug(name='proris', generic='Ibuprofen', contents='Ibuprofen'),
    Drug(name='promethazine', generic='Promethazine', contents='Promethazine'),
    Drug(name='amaryl', generic='Glimepiride', contents='Glimepiride'),
    Drug(name='novalgin', generic='Metamizole Sodium', contents='Metamizole Sodium'),
    Drug(name='combantrin', generic='Pyrantel Pamoate', contents='Pyrantel Pamoate'),
    Drug(name='neo rheumacyl', generic='Ibuprofen, Paracetamol', contents='Ibuprofen, Acetaminophen'),
    Drug(name='tolak angin', generic='Herbal Extracts', contents='Herbal Extracts'),
    Drug(name='larutan penyegar', generic='Gypsum Fibrosum, Calcitum', contents='Gypsum Fibrosum, Calcitum'),
    Drug(name='mixagrip', generic='Paracetamol, Phenylephrine Hydrochloride, Chlorpheniramine Maleate', contents='Acetaminophen, Phenylephrine Hydrochloride, Chlorpheniramine Maleate'),
    Drug(name='bodrexin', generic='Acetylsalicylic Acid', contents='Acetylsalicylic Acid'),
    Drug(name='antangin', generic='Herbal Extracts', contents='Herbal Extracts'),
    Drug(name='entrostop', generic='Attapulgite, Pectin', contents='Attapulgite, Pectin'),
    Drug(name='neo napacin', generic='Paracetamol, Chlorpheniramine Maleate, Phenylpropanolamine Hydrochloride', contents='Acetaminophen, Chlorpheniramine Maleate, Phenylpropanolamine Hydrochloride'),
    Drug(name='konidin', generic='Guaifenesin, Dextromethorphan hydrobromide, Chlorpheniramine Maleate', contents='Guaifenesin, Dextromethorphan hydrobromide, Chlorpheniramine Maleate'),
    Drug(name='silex', generic='Thyme extract, Primrose extract', contents='Thyme extract, Primrose extract'),
    Drug(name='alpara', generic='Paracetamol, Phenylpropanolamine Hydrochloride, Chlorpheniramine Maleate, Dextromethorphan hydrobromide', contents='Acetaminophen, Phenylpropanolamine Hydrochloride, Chlorpheniramine Maleate, Dextromethorphan hydrobromide'),
    Drug(name='rhinos sr', generic='Pseudoephedrine Hydrochloride, Loratadine', contents='Pseudoephedrine Hydrochloride, Loratadine'),
    Drug(name='rhinofed', generic='Pseudoephedrine Hydrochloride, Terfenadine', contents='Pseudoephedrine Hydrochloride, Terfenadine'),
    Drug(name='histapan', generic='Mebhydrolin Napadisylate', contents='Mebhydrolin Napadisylate'),
    Drug(name='cetal', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='pracetam', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='fasidol', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='sanmol', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='neozep', generic='Paracetamol, Phenylephrine Hydrochloride, Chlorpheniramine Maleate', contents='Acetaminophen, Phenylephrine Hydrochloride, Chlorpheniramine Maleate'),
    Drug(name='bodrex flu dan batuk', generic='Paracetamol, Pseudoephedrine Hydrochloride, Dextromethorphan hydrobromide', contents='Acetaminophen, Pseudoephedrine Hydrochloride, Dextromethorphan hydrobromide'),
    Drug(name='feverin', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='tempra', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='demacolin', generic='Paracetamol, Pseudoephedrine Hydrochloride, Chlorpheniramine Maleate', contents='Acetaminophen, Pseudoephedrine Hydrochloride, Chlorpheniramine Maleate'),
    Drug(name='nalgestan', generic='Phenylpropanolamine Hydrochloride, Chlorpheniramine Maleate', contents='Phenylpropanolamine Hydrochloride, Chlorpheniramine Maleate'),
    Drug(name='rhinos', generic='Pseudoephedrine Hydrochloride', contents='Pseudoephedrine Hydrochloride'),
    Drug(name='nasacort', generic='Triamcinolone Acetonide', contents='Triamcinolone Acetonide'),
    Drug(name='bodrex flu', generic='Paracetamol, Pseudoephedrine Hydrochloride, Chlorpheniramine Maleate', contents='Acetaminophen, Pseudoephedrine Hydrochloride, Chlorpheniramine Maleate'),
    Drug(name='rhinos junior', generic='Pseudoephedrine Hydrochloride', contents='Pseudoephedrine Hydrochloride'),
    Drug(name='fluimucil', generic='Acetylcysteine', contents='Acetylcysteine'),
    Drug(name='lasix', generic='Furosemide', contents='Furosemide'),
    Drug(name='imodium', generic='Loperamide', contents='Loperamide'),
    Drug(name='zoralin', generic='Ketoconazole', contents='Ketoconazole'),
    Drug(name='myco-z', generic='Nystatin', contents='Nystatin'),
    Drug(name='dexa-m', generic='Dexamethasone', contents='Dexamethasone'),
    Drug(name='flutamol', generic='Paracetamol, Phenylephrine Hydrochloride, Chlorpheniramine Maleate', contents='Acetaminophen, Phenylephrine Hydrochloride, Chlorpheniramine Maleate'),
    Drug(name='obh kaca', generic='Succus Liquiritiae', contents=['Succus Liquiritiae', 'Ammonium Chloride', 'Acetaminophen', 'Ephedrine Hydrochloride', 'Chlorphenamine Maleate']),
    Drug(name='erysanbe chewibel', generic='Erythromycin', contents='Erythromycin'),
    Drug(name='tremenza', generic='Pseudoephedrine Hydrochloride, Triprolidine Hydrochloride', contents='Pseudoephedrine Hydrochloride, Triprolidine Hydrochloride'),
    Drug(name='mucohexin', generic='Bromhexine Hydrochloride', contents='Bromhexine Hydrochloride'),
    Drug(name='tiriz', generic='Cetirizine', contents='Cetirizine'),
    Drug(name='sirplus', generic='Sirup pemanis', contents='sucralose '),
    Drug(name='Bufect', generic='Sirup Bufect', contents='ibuprofen'),
    Drug(name='Mixagrip Flu & Batuk', generic='Paracetamol, Phenylephrine Hydrochloride, Chlorpheniramine Maleate, Dextromethorphan hydrobromide', contents='Acetaminophen, Phenylephrine Hydrochloride, Chlorpheniramine Maleate, Dextromethorphan hydrobromide'),
    Drug(name='OBH Combi Batuk Berdahak', generic='Succus Liquiritiae, Ammonium Chloride, Paracetamol, Ephedrine Hydrochloride, Chlorphenamine Maleate', contents='Succus Liquiritiae, Ammonium Chloride, Acetaminophen, Ephedrine Hydrochloride, Chlorphenamine Maleate'),
    Drug(name='OBH Combi Batuk Kering', generic='Succus Liquiritiae, Ammonium Chloride, Paracetamol, Ephedrine Hydrochloride, Dextromethorphan hydrobromide', contents='Succus Liquiritiae, Ammonium Chloride, Acetaminophen, Ephedrine Hydrochloride, Dextromethorphan hydrobromide'),
    Drug(name='Paracetamol Extra', generic='Paracetamol, Caffeine', contents='Acetaminophen, Caffeine'),
    Drug(name='Panadol Extra', generic='Paracetamol, Caffeine', contents='Acetaminophen, Caffeine'),
    Drug(name='Bodrexin Extra', generic='Paracetamol, Caffeine', contents='Acetaminophen, Caffeine'),
    Drug(name='Amoxan', generic='Amoxicillin', contents='Amoxicillin'),
    Drug(name='Amoxan 500', generic='Amoxicillin', contents='Amoxicillin'),
    Drug(name='Amoxan 625', generic='Amoxicillin', contents='Amoxicillin'),
    Drug(name='Amlodipine Hexpharm', generic='Amlodipine Besylate', contents='Amlodipine Besylate'),
    Drug(name='Amlodipine Besylate', generic='Amlodipine Besylate', contents='Amlodipine Besylate'),
    Drug(name='Piracetam', generic='Piracetam', contents='Piracetam'),
    Drug(name='Nootropil', generic='Piracetam', contents='Piracetam'),
    Drug(name='Nootropil 800', generic='Piracetam', contents='Piracetam'),
    Drug(name='Nootropil 1200', generic='Piracetam', contents='Piracetam'),
    Drug(name='Dinagen', generic='Piracetam', contents='Piracetam'),
    Drug(name='Dinagen 800', generic='Piracetam', contents='Piracetam'),
    Drug(name='Qropil', generic='Piracetam', contents='Piracetam'),
    Drug(name='Qropil 800', generic='Piracetam', contents='Piracetam'),
    Drug(name='Qropil 1200', generic='Piracetam', contents='Piracetam'),
    Drug(name='Cefixime Hexpharm', generic='Cefixime', contents='Cefixime'),
    Drug(name='Cefixime Hexpharm 200', generic='Cefixime', contents='Cefixime'),
    Drug(name='Cefixime Hexpharm 400', generic='Cefixime', contents='Cefixime'),
    Drug(name='Cefixime Hexpharm 600', generic='Cefixime', contents='Cefixime'),
    Drug(name='Aptor', generic='aspirin', contents='Acetylsalicylic Acid'),
    Drug(name='asetosal', generic='aspirin', contents='Acetylsalicylic Acid'),
    Drug(name='Cefspan', generic='Cefixime', contents='Cefixime'),
    Drug(name='Cefspan 200', generic='Cefixime', contents='Cefixime'),
    Drug(name='Cefspan 400', generic='Cefixime', contents='Cefixime'),
    Drug(name='Cefspan 600', generic='Cefixime', contents='Cefixime'),
    Drug(name='Azithromycin Hexpharm', generic='Azithromycin', contents='Azithromycin'),
    Drug(name='Ciproxin', generic='Ciprofloxacin', contents='Ciprofloxacin'),
    Drug(name='Ciproxin 250', generic='Ciprofloxacin', contents='Ciprofloxacin'),
    Drug(name='Ciproxin 500', generic='Ciprofloxacin', contents='Ciprofloxacin'),
    Drug(name='Ciproxin 750', generic='Ciprofloxacin', contents='Ciprofloxacin'),
    Drug(name='Flagyl', generic='Metronidazole', contents='Metronidazole'),
    Drug(name='Flagyl 250', generic='Metronidazole', contents='Metronidazole'),
    Drug(name='Flagyl 500', generic='Metronidazole', contents='Metronidazole'),
    Drug(name='Flagyl 750', generic='Metronidazole', contents='Metronidazole'),
    Drug(name='Clavimox', generic='Amoxicillin Trihydrate, Potassium Clavulanate', contents='Amoxicillin Trihydrate, Potassium Clavulanate'),
    Drug(name='Clavimox 625', generic='Amoxicillin Trihydrate, Potassium Clavulanate', contents='Amoxicillin Trihydrate, Potassium Clavulanate'),
    Drug(name='Clavimox 875', generic='Amoxicillin Trihydrate, Potassium Clavulanate', contents='Amoxicillin Trihydrate, Potassium Clavulanate'),
    Drug(name='Decadryl Forte', generic='Diphenhydramine Hydrochloride, Ammonium Chloride', contents='Diphenhydramine Hydrochloride, Ammonium Chloride'),
    Drug(name='Bisolvon Forte', generic='Bromhexine Hydrochloride', contents='Bromhexine Hydrochloride'),
    Drug(name='Actifed Cold & Allergy', generic='Pseudoephedrine Hydrochloride, Triprolidine Hydrochloride', contents='Pseudoephedrine Hydrochloride, Triprolidine Hydrochloride'),
    Drug(name='OBH Combi Botol Kaca', generic='Succus Liquiritiae, Ammonium Chloride, Paracetamol, Ephedrine Hydrochloride, Chlorphenamine Maleate', contents='Succus Liquiritiae, Ammonium Chloride, Acetaminophen, Ephedrine Hydrochloride, Chlorphenamine Maleate'),
    Drug(name='Amlodipine', generic='Amlodipine Besylate', contents='Amlodipine Besylate'),
    Drug(name='Piracetam 800', generic='Piracetam', contents='Piracetam'),
    Drug(name='ACRAN', generic='ranitidine', contents='ranitidine'),
    Drug(name='RANITIDINE HEXPHARM', generic='ranitidine', contents='ranitidine'),
    Drug(name='ANALSIK', generic='Metamizole, Diazepam', contents='Diazepam, Metamizole'),
    Drug(name='ASAM TRANEKSAMAT', generic='TRANEXAMIC ACID', contents='TRANEXAMIC ACID'),
    Drug(name='TRANEXAMIC ACID', generic='TRANEXAMIC ACID', contents='TRANEXAMIC ACID'),
    Drug(name='TRANEXAMIC', generic='TRANEXAMIC ACID', contents='TRANEXAMIC ACID'),
    Drug(name='TRANEXAMIC HEXPHARM', generic='TRANEXAMIC ACID', contents='TRANEXAMIC ACID'),
    Drug(name='TRANEXAMIC ACID HEXPHARM', generic='TRANEXAMIC ACID', contents='TRANEXAMIC ACID'),
    Drug(name='BETAHISTIN MESYLATE', generic='Betahistin Mesylate', contents='Betahistin Mesylate'),
    Drug(name='BETAHISTINE MESYLATE', generic='Betahistin Mesylate', contents='Betahistin Mesylate'),
    Drug(name='BETAHISTINE', generic='Betahistin Mesylate', contents='Betahistin Mesylate'),
    Drug(name='CANDESARTAN', generic='Candesartan Cilexetil', contents='Candesartan Cilexetil'),
    Drug(name='CANDESARTAN CILEXETIL', generic='Candesartan Cilexetil', contents='Candesartan Cilexetil'),
    Drug(name='CEFADROXYL', generic='Cefadroxil', contents='Cefadroxil'),
    Drug(name='CEFADROXIL', generic='Cefadroxil', contents='Cefadroxil'),
    Drug(name='DOMPERIDONE', generic='Domperidone', contents='Domperidone'),
    Drug(name='DOMPERIDON', generic='Domperidone', contents='Domperidone'),
    Drug(name='ERMUNON', generic='Erythromycin', contents='Erythromycin'),
    Drug(name='ERYTHROMYCIN', generic='Erythromycin', contents='Erythromycin'),
    Drug(name='ERYTHROMYCIN ETHYLSUCCINATE', generic='Erythromycin', contents='Erythromycin'),
    Drug(name='ERYTHROMYCIN STEARATE', generic='Erythromycin', contents='Erythromycin'),
    Drug(name='FLUCONAZOLE', generic='Fluconazole', contents='Fluconazole'),
    Drug(name='FLUCONAZOL', generic='Fluconazole', contents='Fluconazole'),
    Drug(name='GLIQUIDONE', generic='Glimepiride', contents='Glimepiride'),
    Drug(name='KETOROLAC', generic='Ketorolac Tromethamine', contents='Ketorolac Tromethamine'),
    Drug(name='KETOROLAC TROMETHAMINE', generic='Ketorolac Tromethamine', contents='Ketorolac Tromethamine'),
    Drug(name='KETOROLAC TRIMETHAMINE', generic='Ketorolac Tromethamine', contents='Ketorolac Tromethamine'),
    Drug(name='LORATADINE', generic='Loratadine', contents='Loratadine'),
    Drug(name='LORATADIN', generic='Loratadine', contents='Loratadine'),
    Drug(name='METFORMIN', generic='Metformin', contents='Metformin'),
    Drug(name='METFORMIN Hydrochloride', generic='Metformin', contents='Metformin'),
    Drug(name='METFORMIN HYDROCHLORIDE', generic='Metformin', contents='Metformin'),
    Drug(name='ONDANSETRON', generic='Ondansetron', contents='Ondansetron'),
    Drug(name='ONDANSETRON HYDROCHLORIDE', generic='Ondansetron', contents='Ondansetron'),
    Drug(name='ONDANSETRON HYDROCHLORIDE DIHYDRATE', generic='Ondansetron', contents='Ondansetron'),
    Drug(name='ONDANSETRON Hydrochloride', generic='Ondansetron', contents='Ondansetron'),
    Drug(name='RANITIDIN', generic='Ranitidine', contents='Ranitidine'),
    Drug(name='SANTAGESIK', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='SANTAGESIC', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='SUCRALFATE', generic='Sucralfate', contents='Sucralfate'),
    Drug(name='SUCRALFAT', generic='Sucralfate', contents='Sucralfate'),
    Drug(name='SULFAZALAZINE', generic='Sulfasalazine', contents='Sulfasalazine'),
    Drug(name='ZINC SULFATE', generic='Zinc Sulfate', contents='Zinc Sulfate'),
    Drug(name='ZINC SULPHATE', generic='Zinc Sulfate', contents='Zinc Sulfate'),
    Drug(name='ZINC', generic='Zinc Sulfate', contents='Zinc Sulfate'),
    Drug(name='ZINC PICOLINATE', generic='Zinc Picolinate', contents='Zinc Picolinate'),
    Drug(name='ZINC GLUCONATE', generic='Zinc Gluconate', contents='Zinc Gluconate'),
    Drug(name='ZINC OXIDE', generic='Zinc Oxide', contents='Zinc Oxide'),
    Drug(name='ZINC CHLORIDE', generic='Zinc Chloride', contents='Zinc Chloride'),
    Drug(name='ZINC CITRATE', generic='Zinc Citrate', contents='Zinc Citrate'),
    Drug(name='ZINC SULFIDE', generic='Zinc Sulfide', contents='Zinc Sulfide'),
    Drug(name='ZINC SULPHIDE', generic='Zinc Sulfide', contents='Zinc Sulfide'),
    Drug(name='ZINC ACETATE', generic='Zinc Acetate', contents='Zinc Acetate'),
    Drug(name='ZINC ASPARTATE', generic='Zinc Aspartate', contents='Zinc Aspartate'),
    Drug(name='ZINC METHIONINE', generic='Zinc Methionine', contents='Zinc Methionine'),
    Drug(name='ZINC ORTHOPHOSPHATE', generic='Zinc Orthophosphate', contents='Zinc Orthophosphate'),
    Drug(name='APIALYS', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='APO-ALYS', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='APOALYS', generic='Paracetamol', contents='Acetaminophen'),
    Drug(name='BAQUINOR FORTE', generic='Norfloxacin, Tinidazole', contents='Norfloxacin, Tinidazole, ciprofloxacin'),
    Drug(name='BAQUINOR', generic='Norfloxacin, Tinidazole', contents='Norfloxacin, Tinidazole, ciprofloxacin'),
    Drug(name='BACTOPRIM', generic='cotrimoxazole', contents='Trimethoprim, Sulfamethoxazole'),
    Drug(name='BACTRIM', generic='cotrimoxazole', contents='Trimethoprim, Sulfamethoxazole'),
    Drug(name='BECOM C', generic='Vitamin B Complex, Vitamin C', contents='Vitamin B Complex, Vitamin C'),
    Drug(name='BECOM-C', generic='Vitamin B Complex, Vitamin C', contents='Vitamin B Complex, Vitamin C'),
    Drug(name='BECOMC', generic='Vitamin B Complex, Vitamin C', contents='Vitamin B Complex, Vitamin C'),
    Drug(name='CATAFLAM', generic='Diclofenac Potassium', contents='Diclofenac Potassium'),
    Drug(name='BIOTHICOL', generic='Chloramphenicol', contents='Chloramphenicol'),
    Drug(name='CHLORAMPHENICOL', generic='Chloramphenicol', contents='Chloramphenicol'),
    Drug(name='BRAXIDINE', generic='chlordiazepoxide, clidinium bromide', contents='chlordiazepoxide, clidinium bromide'),
    Drug(name='BRAXIDIN', generic='chlordiazepoxide, clidinium bromide', contents='chlordiazepoxide, clidinium bromide'),
    Drug(name='BUSCOPAN', generic='Hyoscine Butylbromide', contents='Hyoscine Butylbromide'),
    Drug(name='BUSCOPAN COMPOSITUM', generic='Hyoscine Butylbromide, Paracetamol', contents='Hyoscine Butylbromide, Acetaminophen'),
    Drug(name='BUSCOPAN PLUS', generic='Hyoscine Butylbromide, Paracetamol', contents='Hyoscine Butylbromide, Acetaminophen'),
    Drug(name='caco3', generic='Calcium Carbonate', contents='Calcium Carbonate'),
    Drug(name='calcium carbonate', generic='Calcium Carbonate', contents='Calcium Carbonate'),
    Drug(name='CEFAT', generic='Cefadroxil', contents='Cefadroxil'),
    Drug(name='CIPROFLOXACIN', generic='Ciprofloxacin', contents='Ciprofloxacin'),
    Drug(name='cobaziml', generic='Cobamamide', contents='Cobamamide'),
    Drug(name='COBAZIML', generic='Cobamamide', contents='Cobamamide'),
    Drug(name='COTRIMOXAZOLE', generic='cotrimoxazole', contents='Trimethoprim, Sulfamethoxazole'),
    Drug(name='CLOPIDOGREL', generic='Clopidogrel Bisulfate', contents='Clopidogrel Bisulfate'),
    Drug(name='kotrimoksazol', generic='cotrimoxazole', contents='Trimethoprim, Sulfamethoxazole'),
    Drug(name='CURCUMA', generic='Curcuma', contents='kurkumin, curcumin'),
    Drug(name='DIAGIT', generic='glyburide', contents='glyburide, Atapulgite, Pectin'),
    Drug(name='DIAPET', generic='Atapulgite, Pectin', contents='Atapulgite, Pectin'),
    Drug(name='DICLOFENAC', generic='Diclofenac Sodium', contents='Diclofenac Sodium'),
    Drug(name='ELKANA', generic='Vitamin A, Vitamin D, Vitamin B1, Vitamin B2, Vitamin B6, Vitamin B12, Vitamin  C, Niacinamide, Inositol, Kalsium, Kolin, Natrium , L-lisin Hydrochloride', contents='Vitamin A, Vitamin D, Vitamin B1, Vitamin B2, Vitamin B6, Vitamin B12, Vitamin  C, Niacinamide, Inositol, Kalsium, Kolin, Natrium , L-lisin Hydrochloride'),
    Drug(name='ELKANA SYRUP', generic='Vitamin A, Vitamin D, Vitamin B1, Vitamin B2, Vitamin B6, Vitamin B12, Vitamin  C, Niacinamide, Inositol, Kalsium, Kolin, Natrium , L-lisin Hydrochloride', contents='Vitamin A, Vitamin D, Vitamin B1, Vitamin B2, Vitamin B6, Vitamin B12, Vitamin  C, Niacinamide, Inositol, Kalsium, Kolin, Natrium , L-lisin Hydrochloride'),
    Drug(name='ERYTHROMYCIN', generic='Erythromycin', contents='Erythromycin'),
    Drug(name='FLUCONAZOLE', generic='Fluconazole', contents='Fluconazole'),
    Drug(name='H C T', generic='hydrochlorothiazide', contents='Hydrochlorothiazide'),
    Drug(name='HCT', generic='hydrochlorothiazide', contents='Hydrochlorothiazide'),
    Drug(name='HYDROCHLOROTHIAZIDE', generic='hydrochlorothiazide', contents='Hydrochlorothiazide'),
    Drug(name='IMODIUM', generic='Loperamide', contents='Loperamide'),
    Drug(name='LORAZEPAM', generic='Lorazepam', contents='Lorazepam'),
    Drug(name='INTERZINC', generic='Zinc Sulfate', contents='Zinc Sulfate'),
    Drug(name='INTUNAL FORTE', generic='Acetaminophen, Fenilpropanolamin Hydrochloride, Dekstrometorfan hydrobromide, guaifenesin, dexchlorpheniramine maleate', contents='Acetaminophen, Fenilpropanolamin Hydrochloride, Dekstrometorfan hydrobromide, guaifenesin, dexchlorpheniramine maleate'),
    Drug(name='INTUNAL', generic='Acetaminophen, Fenilpropanolamin Hydrochloride, Dekstrometorfan hydrobromide, guaifenesin, dexchlorpheniramine maleate', contents='Acetaminophen, Fenilpropanolamin Hydrochloride, Dekstrometorfan hydrobromide, guaifenesin, dexchlorpheniramine maleate'),
    Drug(name='KETOROLAC', generic='Ketorolac Tromethamine', contents='Ketorolac Tromethamine'),
    Drug(name='L-ZINC SYRUP', generic='Zinc Sulfate', contents='Zinc Sulfate'),
    Drug(name='L-ZINC', generic='Zinc Sulfate', contents='Zinc Sulfate'),
    Drug(name='LAGESIL', generic='Magnesium Hydroxide, Aluminum Hydroxide, Simethicone', contents='Magnesium Hydroxide, Aluminum Hydroxide, Simethicone'),
    Drug(name='LANZOPRAZOL', generic='Lansoprazole', contents='Lansoprazole'),
    Drug(name='LAPIFED', generic='Triprolidine Hydrochloride , Pseudoephedrine Hydrochloride', contents='Triprolidine Hydrochloride, Pseudoephedrine Hydrochloride'),
    Drug(name='LAPIFED DM', generic='Triprolidine Hydrochloride , Pseudoephedrine Hydrochloride, Dextromethorphan hydrobromide', contents='Triprolidine Hydrochloride , Pseudoephedrine Hydrochloride, Dextromethorphan hydrobromide'),
    Drug(name='LAPIFED Ekspektoran', generic='Triprolidine Hydrochloride , Pseudoephedrine Hydrochloride, Glyceryl guaiacolate', contents='Triprolidine Hydrochloride , Pseudoephedrine Hydrochloride, Glyceryl guaiacolate'),
    Drug(name='LAPIFED PLUS', generic='Triprolidine Hydrochloride , Pseudoephedrine Hydrochloride, Paracetamol', contents='Triprolidine Hydrochloride , Pseudoephedrine Hydrochloride, Acetaminophen'),
    Drug(name='LAPRAZ', generic='Lansoprazole', contents='Lansoprazole'),
    Drug(name='Lasal', generic='salbutamol', contents='albuterol'),
    Drug(name='Lasal Expectorant', generic='salbutamol, guaifenesin', contents='albuterol, guaifenesin'),
    Drug(name='LASIX', generic='Furosemide', contents='Furosemide'),
    Drug(name='LASGAN', generic='lansoprazole', contents='lansoprazole'),
    Drug(name='L-BIO', generic='Lactobacillus acidophilus', contents='Lactobcillus acidophilus'),
    Drug(name='LEVOCIN', generic='Levofloxacin', contents='Levofloxacin'),
    Drug(name='LEVOFLOXACIN', generic='Levofloxacin', contents='Levofloxacin'),
    Drug(name='LODIAN', generic='loperamide', contents='loperamide hydrochloride'),
    Drug(name='LOPAMID', generic='Loperamide', contents='loperamide hydrochloride'),
    Drug(name='LOPERAMIDE', generic='Loperamide', contents='loperamide hydrochloride'),
    Drug(name='MELOXICAM', generic='Meloxicam', contents='Meloxicam'),
    Drug(name='MELATONIN', generic='Melatonin', contents='Melatonin'),
    Drug(name='METRONIDAZOL', generic='Metronidazole', contents='metronidazole'),
    Drug(name='NEO KAOLANA', generic='Kaolin, Pectin', contents='Kaolin, Pectin'),
    Drug(name='NEW DIATAB', generic='attapulgite', contents='activated attapulgite'),
    Drug(name='ORALIT SACHET', generic='Glucose, Sodium Chloride, Potassium Chloride, Trisodium Citrate Dihydrate', contents='Glucose, Sodium Chloride, Potassium Chloride, Trisodium Citrate Dihydrate'),
    Drug(name='OSTELOX', generic='meloxicam', contents='meloxicam'),
    Drug(name='PROBIOKID', generic='probiotic, prebiotic', contents='Lactobacillus helveticus, Bifidobacterium infantis, Bifidobacterium bifidum, Frukto-oligosakarida'),
    Drug(name='PROBIOSTIM', generic='probiotic, prebiotic', contents='Lactobacillus helveticus, Bifidobacterium infantis, Bifidobacterium bifidum, Frukto-oligosakarida'),
    Drug(name='PROMUBA', generic='antibiotic, antiprotozoa', contents='metronidazole'),
    Drug(name='RATIVOL', generic='Ranitidine', contents='ketorolac tromethamine'),
    Drug(name='SANLIN', generic='tetracycline', contents='tetracycline'),
    Drug(name='SANMAG', generic='Mylanta, Maalox, Rulox', contents='Magnesium Trisilicate, Aluminum Hydroxide, Papaverine Hydrochloride, Chlordiazepoxide Hydrochloride, Calcium Pantothenate, Vitamin B'),
    Drug(name='SANPRIMA', generic='cotrimoxazole', contents='cotrimoxazole, sulfamethoxazole, trimethoprim'),
    Drug(name='SCOPAMIN', generic='Hyoscine Butylbromide', contents='Hyoscine Butylbromide, acetaminophen'),
    Drug(name='SPASMAL', generic='Hyoscine Butylbromide', contents='Methampyrone , papaverine hydrochloride, Belladonna extract'),
    Drug(name='SPORETIK', generic='sefalosporin', contents='cefexime'),
    Drug(name='TETRACYCLIN', generic='tetracycline', contents='tetracycline hydrochloride'),
    Drug(name='TRICHODAZOL', generic='Metronidazole', contents='Metronidazole'),
    Drug(name='Trilac', generic='triamcinolone acetonide', contents='triamcinolone acetonide'),
    Drug(name='TROVENSIS', generic='ondansetron', contents='ondansetron'),
    Drug(name='TROVAFLOXACIN', generic='ondansetron', contents='ondansetron'),
    Drug(name='VENOSMIL', generic='Diosmin, Hesperidin', contents='Diosmin, Hesperidin, hidrosmin'),
    Drug(name='VOSEDON', generic='antiemetik', contents='domperidone'),
    Drug(name='ZETOR', generic='Zinc Sulfate', contents='Zinc Sulfate'),
    Drug(name='ZETOR PLUS', generic='Zinc Sulfate, Vitamin C', contents='Zinc Sulfate, Vitamin C'),
    Drug(name='XEPAZYM', generic='Pancreatin, Simethicone', contents='Pancreatin, Simethicone'),
    Drug(name='glibenclamide', generic='glyburide', contents='glyburide'),
    Drug(name='chlorphenamine', generic='chlorphenamine', contents='chlorphenamine'),
    Drug(name='hyoscine butylbromide', generic='scopolamine', contents='scopolamine'),
    Drug(name='attapulgite', generic='attapulgite', contents='attapulgite'),
    Drug(name='silymarin', generic='silymarin', contents='silymarin'),
    Drug(name='pseudoephedrine-triprolidine', generic='pseudoephedrine', contents='pseudoephedrine'),
    Drug(name='salbutamol', generic='albuterol', contents='albuterol'),
    Drug(name='triamcinolone', generic='triamcinolone', contents='triamcinolone'),
    Drug(name='ranitidine', generic='ranitidine', contents='ranitidine'),
    Drug(name='hyoscine-paracetamol', generic='scopolamine, acetaminophen', contents='scopolamine, acetaminophen'),
    Drug(name='triprolidine-pseudoephedrine', generic='triprolidine, pseudoephedrine', contents='triprolidine, pseudoephedrine'),
    Drug(name='magnesium trisilicate', generic='magnesium trisilicate', contents='magnesium trisilicate'),

]

EQUIPMENT = [
    Equipment(name='Spuit DISP. 3 CC', type='Suntik', contents='Needle/Syringe'),
    Equipment(name='Spuit DISP. 5 CC', type='Suntik', contents='Needle/Syringe'),
    Equipment(name='Spuit DISP. 10 CC', type='Suntik', contents='Needle/Syringe'),
    Equipment(name='Spuit DISP. 20 CC', type='Suntik', contents='Needle/Syringe'),
    Equipment(name='Spuit DISP. 50 CC', type='Suntik', contents='Needle/Syringe'),
    Equipment(name='jarum', type='Suntik', contents='Needle/Syringe'),
    Equipment(name='JARUM DISP NO 25', type='Suntik', contents='Needle/Syringe'),
    Equipment(name='infus set', type='Infus Set', contents='IV tubing set'),
    Equipment(name='kanula', type='Kanula', contents='IV cannula'),
    Equipment(name='tensi meter', type='Tensimeter', contents='Blood Pressure Monitor'),
    Equipment(name='stetoskop', type='Stetoskop', contents='Stethoscope'),
    Equipment(name='thermometer', type='Termometer', contents='Thermometer'),
    Equipment(name='oximeter', type='Oximeter', contents='Pulse Oximeter'),
    Equipment(name='saline bottle', type='Cairan Infus', contents='0.9% NaCl solution'),
    Equipment(name='Holter monitor', type='Monitor Jantung', contents='24-hour ambulatory ECG device'),
]

# Efficient lookup dictionaries
DRUG_BY_NAME = {drug.name.lower(): drug for drug in DRUGS}
DRUG_BY_GENERIC = {}
for drug in DRUGS:
    for gen in drug.generic.lower().split(','):
        gen = gen.strip()
        if gen:
            DRUG_BY_GENERIC.setdefault(gen, []).append(drug)

EQUIPMENT_BY_NAME = {eq.name.lower(): eq for eq in EQUIPMENT}

# Query functions

def get_drug_by_name(name):
    """Return the Drug object for a given name, or None if not found."""
    # First try exact match (for specific entries like 'Amoxan 500')
    exact_match = DRUG_BY_NAME.get(name.lower())
    if exact_match:
        return exact_match
    
    # Use fuzzy match for slightly misformatted names
    from fuzzywuzzy import process
    best_match_key = _fuzzy_match_name(name, DRUG_BY_NAME)
    if best_match_key:
        return DRUG_BY_NAME[best_match_key]
    return None

def get_equipment_by_name(name):
    """Return the Equipment object for a given name, or None if not found."""
    # First try exact match
    exact_match = EQUIPMENT_BY_NAME.get(name.lower())
    if exact_match:
        return exact_match
    
    # Use fuzzy match
    from fuzzywuzzy import process
    best_match_key = _fuzzy_match_name(name, EQUIPMENT_BY_NAME)
    if best_match_key:
        return EQUIPMENT_BY_NAME[best_match_key]
    return None

def _fuzzy_match_name(name, db_dict, threshold=80):
    """
    Helper function to find the best fuzzy match key in a dictionary.
    Assumes fuzzywuzzy is imported.
    """
    if not name or not db_dict:
        return None
    
    # Process the name against all keys in the dictionary
    best_match = process.extractOne(name, db_dict.keys())
    
    if best_match and best_match[1] >= threshold:
        return best_match[0]
    return None

def get_drugs_by_generic(generic):
    """Return a list of Drug objects for a given generic name (case-insensitive substring match)."""
    g = generic.lower()
    return [drug for key, drugs in DRUG_BY_GENERIC.items() if g in key for drug in drugs]

def search_drugs(query):
    """Return a list of Drug objects whose name or generic matches the query (case-insensitive substring)."""
    q = query.lower()
    return [drug for drug in DRUGS if q in drug.name.lower() or q in drug.generic.lower()]

def get_brand_contents(name):
    """Return the contents list for a given brand name, or None if not found or not a combination drug."""
    drug = get_drug_by_name(name)
    return drug.contents if drug else None