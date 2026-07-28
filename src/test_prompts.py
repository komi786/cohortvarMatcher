"""
Test prompts for evaluating revised system prompts in the Anthropic playground.

Usage:
1. Paste SYSTEM_PROMPT_NE or SYSTEM_PROMPT_EV into the System Prompt box
2. Paste the corresponding test prompt into the User Message box
3. Compare output against expected verdict

Every test has both NE and EV versions.
"""

"""# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622.0, population=heart failure, inclusion criteria=an nt-bnp level higher than twice the upper limit of normal. specifically, this meant ≥400 pg/ml for patients aged 60 to 74 years and ≥800 pg/ml for patients aged ≥75 years; a history of  congestive heart failure hospitalization within the last year; clinical signs or symptoms of  congestive heart failure (dyspnea nyha ≥ ii on current therapy); <35 kg/m²; <= 84.5 and >= 69.3 years old; male and female
Target: gissi-hf, design=randomized_controlled_trial, N=6.975, population=heart failure, inclusion criteria=heart failure; <= 78 and >= 56 years old; male and female
Target : viennahf-register, design= observational_design, N== 1085, population = heart_failure, age= > 18 years old
Target: aachen-hf, observational_design, number of participants= 250, population = heart_failure, age= <= 77.5 and >= 51.5 years old

Both cohorts share study-level condition(s): heart failure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.


## INPUT
Source: description: cause of heart failure, concepts: heart failure | etiology, unit: , categories: [dcm||cad||other||vhd||hhd]
Target: description: presence of heart failure, concepts: heart failure, unit: , categories: [yes||no]
"""

# ============================================================
# COMPLETE — equivalent units / same representation
# ============================================================

test_01 = {
"expected": "COMPLETE",
"rationale": "ug/L = ng/mL mathematically. Same entity, same granularity, equivalent units.",
"ne": """## INPUT
Source: description: NT-proBNP, unit: ucum:ng/mL, categories: []
Target: description: pro-brain natriuretic peptide, unit: ucum:ug/L, categories: []""",
"ev": """# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622, population=heart failure, age=>=60 years
Target: viennahf-register, design=observational_study_design, N=2068, population=heart failure, age=>=18 years
Both cohorts require: heart failure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.
## INPUT
Source: description: NT-proBNP, concepts: natriuretic peptide.b prohormone n-terminal [mass/volume] in serum or plasma, unit: ucum:ng/mL, categories: []
Target: description: pro-brain natriuretic peptide, concepts: natriuretic peptide.b prohormone n-terminal [mass/volume] in serum or plasma, unit: ucum:ug/L, categories: []""",
}

test_02 = {
"expected": "COMPLETE",
"rationale": "{counts}/min = /min for heart rate. Same entity, equivalent notation.",
"ne": """# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622, population=heart failure, age=>=60 years
Target : gissi-hf, design= randomized_controlled_trial, 6975= 6975, population = heart_failure, age =  <= 78 and >= 56 years old
Both cohorts require: heart failure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.
## INPUT
Source: description: heart rate recumbent position, unit: ucum:{counts}/min, categories: []
Target: description: resting heart rate, unit: ucum:/min, categories: []""",
"ev": """# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622, population=heart failure, age=>=60 years
Target : gissi-hf, design= randomized_controlled_trial, 6975= 6975, population = heart_failure, age =  <= 78 and >= 56 years old
Both cohorts share study-level condition(s): heartfailure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.
## INPUT
Source: description: heart rate recumbent position, concepts: heart rate --supine, unit: ucum:{counts}/min, categories: []
Target: description: resting heart rate, concepts: heart rate, unit: ucum:/min, categories: []""",
}

# ============================================================
# COMPATIBLE — same entity, different encoding/units
# ============================================================

test_03 = {
"expected": "COMPATIBLE",
"rationale": "Same entity (LVH), same granularity (binary yes/no), different encoding. ECG is measurement context, not a different entity.",
"ne": """## INPUT
Source: description: lvh criterium reached on ecg, unit: , categories: [no||yes]
Target: description: left ventricular hypertrophy, unit: , categories: [yes||no]""",
"ev": """# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622, population=heart failure, age=>=60 years
Target: viennahf-register, design=observational_study_design, N=2068, population=heart failure, age=>=18 years
Both cohorts require: heart failure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.
## INPUT
Source: description: lvh criterium reached on ecg, concepts: left ventricular hypertrophy | electrocardiogram finding, unit: , categories: [no||yes]
Target: description: left ventricular hypertrophy, concepts: left ventricular hypertrophy, unit: , categories: [yes||no]""",
}

test_04 = {
"expected": "COMPATIBLE",
"rationale": "Same entity, different units requiring conversion factor (umol/L * 0.0113 = mg/dL).",
"ne": """## INPUT
Source: description: serum creatinine, unit: ucum:umol/L, categories: []
Target: description: creatinine, unit: ucum:mg/dL, categories: []""",
"ev": """# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622, population=heart failure, age=>=60 years
Target: aachen-hf, observational_design, number of participants= 250, population = heart_failure, age= <= 77.5 and >= 51.5 years old
Both cohorts require: heart failure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.
## INPUT
Source: description: serum creatinine, concepts: creatinine [mass/volume] in serum or plasma, unit: ucum:umol/L, categories: []
Target: description: creatinine, concepts: creatinine measurement, unit: ucum:mg/dL, categories: []""",
}

test_05 = {
"expected": "COMPATIBLE",
"rationale": "Same entity, deterministic lossless recode.",
"ne": """## INPUT
Source: description: patient sex, unit: , categories: [Female||Male]
Target: description: gender, unit: , categories: [m||f]""",
"ev": """# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622, population=heart failure, age=>=60 years
Target: viennahf-register, design=observational_study_design, N=2068, population=heart failure, age=>=18 years
Both cohorts require: heart failure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity. 
## INPUT
Source: description: patient sex, concepts: gender, unit: , categories: [Female||Male]
Target: description: gender, concepts: gender, unit: , categories: [m||f]""",
}

# ============================================================
# PARTIAL(a) — granularity reduction
# ============================================================

test_06 = {
"expected": "PARTIAL",
"rationale": "Collapse never/former to no, current to yes. Information loss but valid.",
"ne": """## INPUT
Source: description: smoking status, unit: , categories: [never||former||current]
Target: description: current smoker yes/no, unit: , categories: [yes||no]""",
"ev": """# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622, population=heart failure, age=>=60 years
Target: viennahf-register, design=observational_study_design, N=2068, population=heart failure, age=>=18 years
Both cohorts share study-level condition(s): heartfailure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.
## INPUT
Source: description: smoking status, concepts: tobacco smoking behavior | type, unit: , categories: [never||former||current]
Target: description: current smoker yes/no, concepts: tobacco user, unit: , categories: [yes||no]""",
}

test_07 = {
"expected": "PARTIAL",
"rationale": "Collapse: heart disease/MI/sudden cardiac death to yes, all others to no. Both sides fully populate.",
"ne": """## INPUT
Source: description: cause of death, unit: , categories: [alive||heart disease||myocardial infarction||stroke||renal failure||other||unknown]
Target: description: cardiac death yes/no, unit: , categories: [yes||no]""",
"ev": """#STUDY CONTEXTSource: time-chf, design=randomized_controlled_trial, N=622, population=heart failure, age=>=60 years
Target : gissi-hf, design= randomized_controlled_trial, 6975= 6975, population = heart_failure, age =  <= 78 and >= 56 years old
Both cohorts share study-level condition(s): heartfailure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.
## INPUT
Source: description: cause of death, concepts: cause of death | type, unit: , categories: [alive||heart disease||myocardial infarction||stroke||renal failure||other||unknown]
Target: description: cardiac death yes/no, concepts: cause of death | cardiac, unit: , categories: [yes||no]""",
}

# ============================================================
# PARTIAL(b) — external-reference alignment (dose conversions)
# ============================================================

test_08 = {
"expected": "PARTIAL",
"rationale": "Same drug, different dose scale. Convertible via target-dose reference table.",
"ne": """## INPUT
Source: description: furosemide dose, unit: ucum:mg, categories: []
Target: description: furosemide dose as percentage of target dose, unit: ucum:%, categories: []""",
"ev": """# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622.0, population=heart failure, inclusion criteria=an nt-bnp level higher than twice the upper limit of normal. specifically, this meant ≥400 pg/ml for patients aged 60 to 74 years and ≥800 pg/ml for patients aged ≥75 years; a history of  congestive heart failure hospitalization within the last year; clinical signs or symptoms of  congestive heart failure (dyspnea nyha ≥ ii on current therapy); <35 kg/m²; <= 84.5 and >= 69.3 years old; male and female

Target: gissi-hf, design=randomized_controlled_trial, N=6.975, population=heart failure, inclusion criteria=heart failure; <= 78 and >= 56 years old; male and female
Both cohorts share study-level condition(s): heart failure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.

# INPUT
Source: description: furosemide dose, concepts: furosemide | dosage, unit: ucum:mg, categories: []
Target: description: furosemide dose as percentage of target dose, concepts: furosemide | percentage target dose, unit: ucum:%, categories: []""",
}

test_09 = {
"expected": "PARTIAL",
"rationale": "Member drug mg vs class % target. Two-layer conversion: drug equivalence + target-dose table. Both carry dose info.",
"ne": """## INPUT
Source: description: metoprolol dose, unit: ucum:mg, categories: []
Target: description: beta-blocker dose as percentage of target dose, unit: ucum:%, categories: []""",
"ev": """# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622.0, population=heart failure, inclusion criteria=an nt-bnp level higher than twice the upper limit of normal. specifically, this meant ≥400 pg/ml for patients aged 60 to 74 years and ≥800 pg/ml for patients aged ≥75 years; a history of  congestive heart failure hospitalization within the last year; clinical signs or symptoms of  congestive heart failure (dyspnea nyha ≥ ii on current therapy); <35 kg/m²; <= 84.5 and >= 69.3 years old; male and female

Target: gissi-hf, design=randomized_controlled_trial, N=6.975, population=heart failure, inclusion criteria=heart failure; <= 78 and >= 56 years old; male and female
Both cohorts share study-level condition(s): heart failure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.

# INPUT
Source: description: metoprolol dose, concepts: metoprolol | dosage, unit: ucum:mg, categories: []
Target: description: beta-blocker dose as percentage of target dose, concepts: beta blocking agents | percentage target dose, unit: ucum:%, categories: []""",
}

test_10 = {
"expected": "PARTIAL",
"rationale": "Furosemide mg vs loop diuretic % target. Member + scale conversion, both quantitative.",
"ne": """## INPUT
Source: description: dose furosemide, unit: ucum:mg, categories: []
Target: description: normalisation of loop diuretics, unit: ucum:%, categories: []""",
"ev": """## STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622.0, population=heart failure, inclusion criteria=an nt-bnp level higher than twice the upper limit of normal. specifically, this meant ≥400 pg/ml for patients aged 60 to 74 years and ≥800 pg/ml for patients aged ≥75 years; a history of  congestive heart failure hospitalization within the last year; clinical signs or symptoms of  congestive heart failure (dyspnea nyha ≥ ii on current therapy); <35 kg/m²; <= 84.5 and >= 69.3 years old; male and female
Target: gissi-hf, design=randomized_controlled_trial, N=6.975, population=heart failure, inclusion criteria=heart failure; <= 78 and >= 56 years old; male and female
Both cohorts share study-level condition(s): heart failure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.
# INPUT
Source: description: dose furosemide, concepts: furosemide | dosage, unit: ucum:mg, categories: []
Target: description: normalisation of loop diuretics, concepts: sulfonamides plain | percentage target dose, unit: ucum:%, categories: []""",
}

# ============================================================
# PARTIAL(c) — asymmetric member/class
# ============================================================

test_11 = {
"expected": "PARTIAL",
"rationale": "Harmonized: loop_diuretic_use_yes_no. Dose > 0 -> yes (full). Furosemide yes -> yes, no -> missing.",
"ne": """## INPUT
Source: description: furosemide indicated, unit: , categories: [yes||no]
Target: description: loop diuretic daily dose, unit: ucum:mg, categories: []""",
"ev": """## STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622.0, population=heart failure, inclusion criteria=an nt-bnp level higher than twice the upper limit of normal. specifically, this meant ≥400 pg/ml for patients aged 60 to 74 years and ≥800 pg/ml for patients aged ≥75 years; a history of  congestive heart failure hospitalization within the last year; clinical signs or symptoms of  congestive heart failure (dyspnea nyha ≥ ii on current therapy); <35 kg/m²; <= 84.5 and >= 69.3 years old; male and female
Target: gissi-hf, design=randomized_controlled_trial, N=6.975, population=heart failure, inclusion criteria=heart failure; <= 78 and >= 56 years old; male and female
Both cohorts share study-level condition(s): heart failure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.
## INPUT
Source: description: furosemide indicated, concepts: furosemide, unit: , categories: [yes||no]
Target: description: loop diuretic daily dose, concepts: high-ceiling diuretics | dosage, unit: ucum:mg, categories: []""",
}

test_12 = {
"expected": "PARTIAL",
"rationale": "Aspirin is a member of the broader antithrombotic agents class. The specific drug measurement is a subset of the class-level measurement. can create antithrombotic_agent_use",
"ne": """## INPUT
Source: description: aspirin taken, unit: , categories: [yes||no]
Target: description: antithrombotic agent use, unit: , categories: [yes||no]""",
"ev": """## STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622.0, population=heart failure, inclusion criteria=an nt-bnp level higher than twice the upper limit of normal. specifically, this meant ≥400 pg/ml for patients aged 60 to 74 years and ≥800 pg/ml for patients aged ≥75 years; a history of  congestive heart failure hospitalization within the last year; clinical signs or symptoms of  congestive heart failure (dyspnea nyha ≥ ii on current therapy); <35 kg/m²; <= 84.5 and >= 69.3 years old; male and female
Target: gissi-hf, design=randomized_controlled_trial, N=6.975, population=heart failure, inclusion criteria=heart failure; <= 78 and >= 56 years old; male and female
Both cohorts share study-level condition(s): heart failure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.
## INPUT
Source: description: aspirin taken, concepts: aspirin, unit: , categories: [yes||no]
Target: description: antithrombotic agent use, concepts: antithrombotic agents, unit: , categories: [yes||no]""",
}

# ============================================================
# PARTIAL — temporal/contextual (same categories, different qualifier)
# ============================================================

test_21 = {
"expected": "PARTIAL",
"rationale": "Same entity, identical categories, but 'maximal over interval' vs point-in-time. Preserve full category granularity, not binary.",
"ne": """## INPUT
Source: description: max amount of edema between baseline and visit month 1, unit: , categories: [no||ankle edema||edema of knee||edema of thigh]
Target: description: peripheral edema severity at 1 month follow-up, unit: , categories: [no||ankle edema||edema of knee||edema of thigh]""",
"ev": """## STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622.0, population=heart failure, inclusion criteria=an nt-bnp level higher than twice the upper limit of normal. specifically, this meant ≥400 pg/ml for patients aged 60 to 74 years and ≥800 pg/ml for patients aged ≥75 years; a history of  congestive heart failure hospitalization within the last year; clinical signs or symptoms of  congestive heart failure (dyspnea nyha ≥ ii on current therapy); <35 kg/m²; <= 84.5 and >= 69.3 years old; male and female
Target: gissi-hf, design=randomized_controlled_trial, N=6.975, population=heart failure, inclusion criteria=heart failure; <= 78 and >= 56 years old; male and female
Both cohorts share study-level condition(s): heart failure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.
## INPUT
Source: description: max amount of edema between baseline and visit month 1, concepts: edema of lower extremity | maximal, unit: , categories: [no||ankle edema||edema of knee||edema of thigh]
Target: description: peripheral edema severity at 1 month follow-up, concepts: edema of lower extremity, unit: , categories: [no||ankle edema||edema of knee||edema of thigh]""",
}
test_21_1 = {
"expected": "PARTIAL",
"rationale": "source doesnot specify left or right limb.",
"ne": """## INPUT
Source: description: max amount of edema between baseline and visit month 1, unit: , categories: [no||ankle edema||edema of knee||edema of thigh]
Target: description: peripheral edema of left leg severity at 1 month follow-up, unit: , categories: [no||ankle edema||edema of knee||edema of thigh]""",
"ev": """## STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622.0, population=heart failure, inclusion criteria=an nt-bnp level higher than twice the upper limit of normal. specifically, this meant ≥400 pg/ml for patients aged 60 to 74 years and ≥800 pg/ml for patients aged ≥75 years; a history of  congestive heart failure hospitalization within the last year; clinical signs or symptoms of  congestive heart failure (dyspnea nyha ≥ ii on current therapy); <35 kg/m²; <= 84.5 and >= 69.3 years old; male and female
Target: gissi-hf, design=randomized_controlled_trial, N=6.975, population=heart failure, inclusion criteria=heart failure; <= 78 and >= 56 years old; male and female
Both cohorts share study-level condition(s): heart failure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.
## INPUT
Source: description: max amount of edema between baseline and visit month 1, concepts: edema of lower extremity | maximal, unit: , categories: [no||ankle edema||edema of knee||edema of thigh]
Target: description: peripheral edema of left leg severity at 1 month follow-up, concepts: Edema of left lower limb, unit: , categories: [no||ankle edema||edema of knee||edema of thigh]""",
}
# ============================================================
# IMPOSSIBLE — fabrication (binary -> continuous)
# ============================================================

test_13 = {
"expected": "PARTIAL",
"rationale": "Torasemide is a loop diuretic. Both variables can be harmonized into a broader binary loop diuretic use indicator.",
"ne": """## INPUT
Source: description: torasemide indicated, unit: , categories: [yes||no]
Target: description: loop diuretic percentage of target dose, unit: ucum:%, categories: []""",
"ev": """## INPUT
Source: description: torasemide indicated, concepts: torsemide, unit: , categories: [yes||no]
Target: description: loop diuretic percentage of target dose, concepts: sulfonamides plain | percentage target dose, unit: ucum:%, categories: []""",
}

# ============================================================
# IMPOSSIBLE — inferential fabrication (cause vs procedure)
# ============================================================

test_14 = {
"expected": "IMPOSSIBLE",
"rationale": "Source records general cause of death categories, while target specifically tracks procedure-associated outcomes. The source lacks sufficient granularity to isolate CABG-related deaths.",
"ne": """## INPUT
Source: description: cause of death, unit: , categories: [alive||heart disease||myocardial infarction||stroke||renal failure||other||unknown||sudden cardiac death]
Target: description: decease followed after CABG, unit: , categories: [yes||no]""",
"ev": """## INPUT
Source: description: cause of death, concepts: cause of death | type, unit: , categories: [alive||heart disease||myocardial infarction||stroke||renal failure||other||unknown||sudden cardiac death]
Target: description: decease followed after CABG, concepts: cause of death | coronary artery bypass graft, unit: , categories: [yes||no]""",
}

# ============================================================
# IMPOSSIBLE — different clinical dimensions
# ============================================================

test_15 = {
"expected": "IMPOSSIBLE",
"rationale": "The variables measure different dimensions of the same entity: one is a quantitative measurement value and the other is the method used for measurement.",
"ne": """## INPUT
Source: description: left ventricular ejection fraction, unit: ucum:%, categories: []
Target: description: method of LVEF measurement, unit: , categories: [echocardiography||nuclear imaging||ventriculography]""",
"ev": """## INPUT
Source: description: left ventricular ejection fraction, concepts: left ventricular ejection fraction, unit: ucum:%, categories: []
Target: description: method of LVEF measurement, concepts: left ventricular ejection fraction | measurement method, unit: , categories: [echocardiography||nuclear imaging||ventriculography]""",
}

test_16 = {
"expected": "IMPOSSIBLE",
"rationale": "Disease presence/severity vs intervention occurrence. Having severe PAOD doesn't mean intervention was performed.",
"ne": """## INPUT
Source: description: peripheral arterial disease severity, unit: , categories: [asymptomatic||mild||moderate||severe||no]
Target: description: intervention for PAOD performed, unit: , categories: [yes||no]""",
"ev": """## INPUT
Source: description: peripheral arterial disease severity, concepts: peripheral arterial disease, unit: , categories: [asymptomatic||mild||moderate||severe||no]
Target: description: intervention for PAOD performed, concepts: peripheral arterial disease | intervention, unit: , categories: [yes||no]""",
}

# ============================================================
# IMPOSSIBLE — sibling concepts
# ============================================================

test_17 = {
"expected": "IMPOSSIBLE",
"rationale": "Sibling drug classes, not member/class. No valid common variable.",
"ne": """## INPUT
Source: description: ACE inhibitor use, unit: , categories: [yes||no]
Target: description: ARB use, unit: , categories: [yes||no]""",
"ev": """## INPUT
Source: description: ACE inhibitor use, concepts: ace inhibitors plain, unit: , categories: [yes||no]
Target: description: ARB use, concepts: angiotensin ii receptor blockers, unit: , categories: [yes||no]""",
}

# ============================================================
# IMPOSSIBLE — trial-arm indicator vs lab value
# ============================================================

test_18 = {
"expected": "IMPOSSIBLE",
"rationale": "Binary trial-arm indicator vs continuous lab value. Different dimensions. yes/no is context-dependent (trial arm + threshold).",
"ne": """## INPUT
Source: description: BNP target in BNP-guided arm reached at 3 months, unit: , categories: [yes||no]
Target: description: NT-proBNP at 3 month follow-up, unit: ucum:pg/mL, categories: []""",
"ev": """## INPUT
Source: description: BNP target in BNP-guided arm reached at 3 months, concepts: natriuretic peptide.b prohormone n-terminal [mass/volume] in serum or plasma | target parameter | clinical trial arm, unit: , categories: [yes||no]
Target: description: NT-proBNP at 3 month follow-up, concepts: natriuretic peptide.b prohormone n-terminal [mass/volume] in serum or plasma, unit: ucum:pg/mL, categories: []""",
}

# ============================================================
# IMPOSSIBLE — causal relationship (device vs rhythm)
# ============================================================

test_22 = {
"expected": "IMPOSSIBLE",
"rationale": "Device presence vs physiological finding. Pacemaker present does not mean rhythm is paced. Different entities.",
"ne": """## INPUT
Source: description: having a pacemaker, unit: , categories: [yes||no]
Target: description: rhythm from pacemaker, unit: , categories: [yes||no]""",
"ev": """## INPUT
Source: description: having a pacemaker, concepts: cardiac pacemaker, unit: , categories: [yes||no]
Target: description: rhythm from pacemaker, concepts: rhythm from artificial pacing, unit: , categories: [yes||no]
graph_evidence: [cardiac pacemaker -> has_finding -> rhythm from artificial pacing (distance: 1)]""",
}

# ============================================================
# IMPOSSIBLE — drug type identification vs dose quantity
# ============================================================

test_20 = {
"expected": "PARTIAL",
"rationale": "Both variables inform beta-blocker treatment status. While specific drug type and dose intensity are different dimensions, they collapse to a common binary 'yes/no' use indicator",
"ne": """## INPUT
Source: description: which beta blocker, unit: , categories: [metoprolol||bisoprolol||carvedilol||atenolol||no||other]
Target: description: beta-blocker dose as percentage of target dose, unit: ucum:%, categories: []""",
"ev": """## INPUT
Source: description: which beta blocker, concepts: beta blocking agents | type, unit: , categories: [metoprolol||bisoprolol||carvedilol||atenolol||no||other]
Target: description: beta-blocker dose as percentage of target dose, concepts: beta blocking agents | percentage target dose, unit: ucum:%, categories: []""",
}

# ============================================================
# EDGE CASES
# ============================================================

test_19 = {
"expected": "COMPATIBLE",
"rationale": "Both variables represent a binary diagnosis of atrial fibrillation. Contextual differences (during echo vs general) do not preclude merging these clinical indicators.",
"ne": """## INPUT
Source: description: atrial fibrillation during echocardiography, unit: , categories: [no||yes]
Target: description: atrial fibrillation yes/no, unit: , categories: [yes||no]""",
"ev": """## INPUT
Source: description: atrial fibrillation during echocardiography, concepts: atrial fibrillation | echocardiography, unit: , categories: [no||yes]
Target: description: atrial fibrillation yes/no, concepts: atrial fibrillation, unit: , categories: [yes||no]""",
}

test_23_edge_ast = {
"expected": "COMPLETE",
"rationale": "Same lab test (AST), same units (U/L). One concept is LOINC-specific, other is SNOMED-generic. Should not downgrade for concept granularity difference.",
"ne": """## INPUT
Source: description: aspartate aminotransferase (AST), unit: ucum:[u]/l, categories: []
Target: description: aspartaat aminotransferase (ASAT), unit: ucum:[u]/l, categories: []""",
"ev": """## INPUT
Source: description: aspartate aminotransferase (AST), concepts: aspartate aminotransferase [enzymatic activity/volume] in serum or plasma, unit: ucum:[u]/l, categories: []
Target: description: aspartaat aminotransferase (ASAT), concepts: aspartate aminotransferase measurement, unit: ucum:[u]/l, categories: []""",
}

test_24_edge_allergies = {
"expected": "PARTIAL",
"rationale": "Both variables measure the same clinical entity of having allergies, but one is defined with explicit yes/no categories while the other is open",
"ne": """## INPUT
Source: description: history of allergies y/n, unit: , categories: [no||yes]
Target: description: any allergies, unit: , categories: []""",
"ev": """## INPUT
Source: description: history of allergies y/n, concepts: h/o: multiple allergies, unit: , categories: [no||yes]
Target: description: any allergies, concepts: h/o: multiple allergies, unit: , categories: []""",
}

test_25 = {
"expected": "COMPLETE",
"rationale": "Exact match for lab analyte (Erythrocytes).",
"ne": """## INPUT
Source: description: erythrocytes, unit: ucum:10*6/ml, categories: []
Target: description: erythrocytes, unit: ucum:10*12/l, categories: []""",
"ev": """## INPUT
Source: description: erythrocytes, concepts: erythrocytes [#/volume] in blood, unit: ucum:10*6/ml, categories: []
Target: description: erythrocytes, concepts: erythrocytes [#/volume] in blood, unit: ucum:10*12/l, categories: []""",
}
test_26 = {
"expected": "COMPATIBLE",
"rationale": "Same clinical condition (AV block) in different diagnostic contexts (echo vs ecg).",
"ne": """## INPUT
Source: description: av-block during echocardiography y/n, unit: , categories: [no||yes]
Target: description: presence of av block in ecg (yes/no), unit: , categories: [yes||no]""",
"ev": """## INPUT
Source: description: av-block during echocardiography y/n, concepts: atrioventricular block, unit: , categories: [no||yes]
Target: description: presence of av block in ecg (yes/no), concepts: atrioventricular block, unit: , categories: [yes||no]""",
}

test_27 = {
"expected": "PARTIAL",
"rationale": "Granularity conversion: Categorical CCS class to continuous/ordinal scale.",
"ne": """## INPUT
Source: description: ccs (classification of chest pain) classification, unit: , categories: [no||class i||class ii||class i/ii]
Target: description: angina ccs class, unit: , categories: []""",
"ev": """## INPUT
Source: description: ccs (classification of chest pain) classification, concepts: canadian cardiovascular society classification of angina, unit: , categories: [no||class i||class ii||class i/ii]
Target: description: angina ccs class, concepts: canadian cardiovascular society grading of angina pectoris grade, unit: , categories: []""",
}

test_28 = {
"expected": "IMPOSSIBLE",
"rationale": "Different dimensions: disease severity state cannot be converted to a specific date of intervention.",
"ne": """## INPUT
Source: description: history of peripheral arterial occlusive disease, unit: , categories: [asymptomatic||mild||moderate||severe||no]
Target: description: date of intervention, unit: , categories: []""",
"ev": """## INPUT
Source: description: history of peripheral arterial occlusive disease, concepts: peripheral arterial disease, unit: , categories: [asymptomatic||mild||moderate||severe||no]
Target: description: date of intervention, concepts: peripheral arterial disease | date of procedure, unit: , categories: []""",
}

# test_29: RAS Inhibitors (PARTIAL - Broadening/Grouping)
test_29 = {
"expected": "PARTIAL",
"rationale": "Mapping individual drug classes (ACEi/ARB) to a consolidated 'RAS inhibitor' group.",
"ne": """## INPUT
Source: description: ace-inhibitor or atii-antagonist use, unit: , categories: [yes||no]
Target: description: agents acting on the renin-angiotensin system, unit: , categories: [losartan||candesartan||telmisartan||valsartan]""",
"ev": """## INPUT
Source: description: ace-inhibitor or atii-antagonist use, concepts: angiotensin ii receptor blockers, unit: , categories: [yes||no]
Target: description: agents acting on the renin-angiotensin system, concepts: agents acting on the renin-angiotensin system, unit: , categories: [losartan||candesartan||telmisartan||valsartan]""",
}
# test_30: DCM Year vs Cardiomegaly (IMPOSSIBLE - Different Clinical Entities)
test_30 = {
"expected": "IMPOSSIBLE",
"rationale": "Date of diagnosis for a specific disease (DCM) is not equivalent to the presence of a finding (cardiomegaly).",
"ne": """## INPUT
Source: description: dilated cardiomyopathy year diagnosis, unit: ucum:a, categories: []
Target: description: cardiomegaly, unit: , categories: [yes||no]""",
"ev": """## INPUT
Source: description: dilated cardiomyopathy year diagnosis, concepts: dilated cardiomyopathy, unit: ucum:a, categories: []
Target: description: cardiomegaly, concepts: cardiomegaly, unit: , categories: [yes||no]""",
}

# test_31: Hypertension Year (COMPLETE - Same entity, temporal point)
test_31 = {
"expected": "COMPLETE",
"rationale": "Same clinical entity (hypertension) and temporal dimension (year of diagnosis).",
"ne": """## INPUT
Source: description: hypertension diagnosis year, unit: ucum:a, categories: []
Target: description: first presentation of hypertension, unit: ucum:a, categories: []""",
"ev": """## INPUT
Source: description: hypertension diagnosis year, concepts: hypertensive disorder, unit: ucum:a, categories: []
Target: description: first presentation of hypertension, concepts: hypertensive disorder, unit: ucum:a, categories: []""",
}

# test_32: Heart Rate / Frequency (COMPLETE - Semantic synonyms)
test_32 = {
"expected": "COMPLETE",
"rationale": "Frequency and heart rate are semantically identical in this cardiovascular context.",
"ne": """## INPUT
Source: description: frequency, unit: ucum:{counts}/min, categories: []
Target: description: resting heart rate, unit: ucum:/min, categories: []""",
"ev": """## INPUT
Source: description: frequency, concepts: heart rate, unit: ucum:{counts}/min, categories: []
Target: description: resting heart rate, concepts: heart rate, unit: ucum:/min, categories: []""",
}
# test_33: Cerebrovascular Disease (PARTIAL - Granularity/Definition)
test_33 = {
"expected": "PARTIAL",
"rationale": "Mapping a subset (mild disease) to a broader category (occlusive disease).",
"ne": """## INPUT
Source: description: history of mild cerebrovascular disease (0 vs 1-2-3) y/n, unit: , categories: [yes||no]
Target: description: cerebral artery occlusive disease (caod), unit: , categories: [no||yes]""",
"ev": """## INPUT
Source: description: history of mild cerebrovascular disease (0 vs 1-2-3) y/n, concepts: cerebrovascular disease, unit: , categories: [yes||no]
Target: description: cerebral artery occlusive disease (caod), concepts: cerebral artery occlusion, unit: , categories: [no||yes]""",
}

# test_36: Beta-Blocker (PARTIAL - Specifics to binary)
test_34 = {
"expected": "PARTIAL",
"rationale": "Converting specific beta-blocker substance to a binary use indicator.",
"ne": """## INPUT
Source: description: betablocker use, unit: , categories: [yes||no]
Target: description: betablocker substance, unit: , categories: []""",
"ev": """## INPUT
Source: description: betablocker use, concepts: beta blocking agents, unit: , categories: [yes||no]
Target: description: betablocker substance, concepts: beta blocking agents, unit: , categories: []""",
}

# test_35: Valvular Disease (PARTIAL - General to specific)
test_35 = {
"expected": "PARTIAL",
"rationale": "Mapping general valvular heart disease to a specific pulmonary valve disorder.",
"ne": """## INPUT
Source: description: history of valvular heart disease y/n, unit: , categories: [no||yes]
Target: description: pulmonary valve regurgitation / stenosis, unit: , categories: []""",
"ev": """## INPUT
Source: description: history of valvular heart disease y/n, concepts: heart valve disorder, unit: , categories: [no||yes]
Target: description: pulmonary valve regurgitation / stenosis, concepts: pulmonary valve disorder, unit: , categories: []""",
}

# test_36: Ectopic Beats (PARTIAL - Count to Binary)
test_36 = {
"expected": "PARTIAL",
"rationale": "Converting a count of supraventricular extrasystoles (a measurement) into a boolean presence/absence of ectopic beats.",
"ne": """## INPUT
Source: description: number of supraventricular extrasystoles (sves), unit: , categories: []
Target: description: presence of ectopic beats either supraventricular or ventricular, unit: , categories: [no||yes]""",
"ev": """## INPUT
Source: description: number of supraventricular extrasystoles (sves), concepts: supraventricular premature beats, unit: , categories: []
Target: description: presence of ectopic beats either supraventricular or ventricular, concepts: premature beats, unit: , categories: [no||yes]""",
}

# test_37: Cause of Heart Failure (PARTIAL - Categorical harmonization)


test_37 = {
"expected": "PARTIAL",
"rationale": "Same entity (cause of HF), but different category sets requiring semantic harmonization (e.g., 'disorder of coronary artery' vs 'ischemic').",
"ne": """## INPUT
Source: description: cause of heart failure, unit: , categories: [dilated cardiomyopathy||disorder of coronary artery||other||heart valve disorder||hypertensive heart disease]
Target: description: main cause of heart failure, unit: , categories: [dilated cardiomyopathy||cannot be determined||alcohol||hypertension||hypertensive disorder||other||ischemic||unknown]""",
"ev": """## INPUT
Source: description: cause of heart failure, concepts: heart failure | etiology, unit: , categories: [dilated cardiomyopathy||disorder of coronary artery||other||heart valve disorder||hypertensive heart disease]
Target: description: main cause of heart failure, concepts: heart failure | etiology, unit: , categories: [dilated cardiomyopathy||cannot be determined||alcohol||hypertension||hypertensive disorder||other||ischemic||unknown]""",
}

# test_38: Time to Endpoint (PARTIAL - Semantic scope of endpoint)
test_38 = {
"expected": "PARTIAL",
"rationale": "Both variables measure time to a clinical study endpoint in days. Partial because the composite endpoint definitions vary slightly (inclusion of death vs focus on hospital admission).",
"ne": """## INPUT
Source: description: time to first heart failure hospitalisation or death, unit: ucum:d, categories: []
Target: description: number of days to endpoint, unit: ucum:d, categories: []""",
"ev": """## INPUT
Source: description: time to first heart failure hospitalisation or death, concepts: study endpoint | time to first event | death | emergency hospital admission for heart failure, unit: ucum:d, categories: []
Target: description: number of days to endpoint, concepts: study endpoint | time | emergency hospital admission for heart failure, unit: ucum:d, categories: []""",
}

test_39 = {
"expected": "PARTIAL",
"rationale": "Both measure cause of death. Source captures broad malignancy, while target identifies specific lung malignancy. Harmonized variable is death_due_to_malignant_neoplasm.",
"ne": """## INPUT
Source: description: cause of death, unit: , categories: [unknown||alive||renal failure||heart failure||stroke||heart disease||other||myocardial infarction||infectious disease||sudden cardiac death||malignant neoplastic disease||hepatic failure]
Target: description: pulmonary neoplasia (if decease reason neoplasia), unit: , categories: [no||yes]""",
"ev": """## INPUT
Source: description: cause of death, concepts: cause of death | type, unit: , categories: [unknown||alive||renal failure||heart failure||stroke||heart disease||other||myocardial infarction||infectious disease||sudden cardiac death||malignant neoplastic disease||hepatic failure]
Target: description: pulmonary neoplasia (if decease reason neoplasia), concepts: cause of death | malignant tumor of lung, unit: , categories: [no||yes]""",
}
test_40 = {
"expected": "COMPLETE",
"rationale": "Same clinical entity, same concept (edema of lower extremity), and identical category set. No information loss or transformation required.",
"ne": """## INPUT
Source: description: amount of peripheral edema severity in history, unit: , categories: [no||ankle edema||edema of knee||edema of thigh]
Target: description: peripheral edema severity, unit: , categories: [no||ankle edema||edema of knee||edema of thigh]""",
"ev": """## INPUT
Source: description: amount of peripheral edema severity in history, concepts: edema of lower extremity | maximal, unit: , categories: [no||ankle edema||edema of knee||edema of thigh]
Target: description: peripheral edema severity, concepts: edema of lower extremity, unit: , categories: [no||ankle edema||edema of knee||edema of thigh]""",
}

# test_41: Valvular Heart Disease (PARTIAL - Generic vs Specific Granularity)
test_41 = {
"expected": "IMPOSSIBLE",
"rationale": "Variable 1 captures broad valvular disease history, while Variable 2 is specific to the pulmonary valve. Pulmonary valve disease is a specific subset that cannot be inferred from a generic 'yes' in the broader category.",
"ne": """## INPUT
Source: description: history of valvular heart disease y/n, unit: , categories: [no||yes]
Target: description: pulmonary valve regurgitation / stenosis / prothesis degeneration, unit: , categories: []""",
"ev": """## INPUT
Source: description: history of valvular heart disease y/n, concepts: heart valve disorder, unit: , categories: [no||yes]
Target: description: pulmonary valve regurgitation / stenosis / prothesis degeneration, concepts: pulmonary valve disorder, unit: , categories: []""",
}

test_42 = {
"expected": "COMPATIBLE",
"rationale": "Both measure AF presence, but measurement contexts differ (one specifically during echo, one general history). A common binary flag for AF presence is feasible.",
"ne": """## INPUT
Source: description: atrial fibrillation during echocardiography y/n, unit: , categories: [no||yes]
Target: description: history of atrial fibrillation, unit: , categories: [0|1]""",
"ev": """## INPUT
Source: description: atrial fibrillation during echocardiography y/n, concepts: atrial fibrillation|echocardiography, unit: , categories: [no||yes]
Target: description: history of atrial fibrillation, concepts: atrial fibrillation|medical history, unit: , categories: [0|1]""",
}


test_42 = {
"expected": "PARTIAL MATCH",
"rationale": "Both measure atrial fibrillation but differ in specificity (AF vs AF/Flutter) and measurement context (echo vs baseline), requiring information loss to align",
"ne": """## INPUT
Source: description:atrial fibrillation during echocardiography y/n, unit: , categories: [no||yes]
Target: description: Atrial fibrillation / Flutter, unit: , categories: [0|1]""",
"ev": """## INPUT
Source: description: atrial fibrillation during echocardiography y/n, concepts: atrial fibrillation|echocardiography, unit: , categories: [no||yes]
Target: description: Atrial fibrillation / Flutter, concepts: atrial fibrillation, unit: , categories: [0|1]""",
}

test_43 = {
"expected": "PARTIAL",
"rationale": "Paroxysmal AF is a subtype of AF. Mapping specific subtype 'yes' to class 'yes' is valid, but 'no' for subtype does not imply 'no' for class.",
"ne": """## INPUT
Source: description:atrial fibrillation during echocardiography y/n, unit: , categories: [no||yes]
Target: description: paroxysmal atrial fibrillation, unit: , categories: [no||yes]""",
"ev": """# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622, population=heart failure, age=>=60 years
Target: aachen-hf, observational_design, number of participants= 250, population = heart_failure, age= <= 77.5 and >= 51.5 years old
Both cohorts share study-level condition(s): heartfailure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.
## INPUT
Source: description: atrial fibrillation during echocardiography y/n, concepts: atrial fibrillation|echocardiography, unit: , categories: [no||yes]
Target: description: paroxysmal atrial fibrillation, concepts: paroxysmal atrial fibrillation, unit: , categories: [no||yes]""",
}

test_44 = {
"expected": "PARTIAL",
"rationale": "",
"ne": """## INPUT
Source: description:furosemide indicated, unit: , categories: [no||yes]
Target: description: diuretics, unit: , categories: [torasemide||furosemide]""",
"ev": """# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622, population=heart failure, age=>=60 years
Target: aachen-hf, observational_design, number of participants= 250, population = heart_failure, age= <= 77.5 and >= 51.5 years old
Both cohorts share study-level condition(s): heartfailure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.
## INPUT
Source: description: furosemide indicated, concepts: furosemide, unit: , categories: [no||yes]
Target: description: diuretics, concepts: sulfonamides, plain, unit: , categories: [torasemide||furosemide]""",
}

test_45 = {
"expected": "COMPATIBLE",
"rationale": "Both variables represent the same clinical entity (elevated central venous pressure) as a binary interpreted state.",
"ne": """## INPUT
Source: description:jugular vein elevated , unit: , categories: [no||yes]
Target: description: central venous pressure > 6 cm h20, unit: , categories: [no||yes]""",
"ev": """# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622, population=heart failure, age=>=60 years
Target : gissi-hf, design= randomized_controlled_trial, 6975= 6975, population = heart_failure, age =  <= 78 and >= 56 years old
Both cohorts share study-level condition(s): heartfailure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.

## INPUT
Source: description: jugular vein elevated , concepts: central venous pressure, unit: , categories: [no||yes]
Target: description: central venous pressure > 6 cm h20, concepts: mildly elevated right-atrial pressure||central venous pressure, unit: , categories: [no||yes]""",
}


test_46 = {
"expected": "IMPOSSIBLE",
"rationale": "Source is a composite sum of two drug classes, while target is a single class. Neither can be derived from the other without invalid assumptions.",
"ne": """## INPUT
Source: description:sum of ace-inh and arb-dose baseline in percentage of target dose , unit:% , categories: ""
Target: description: original dosage of arb concepts:angiotensin ii receptor antagonist|percentage target dosage, unit:% , categories:""",
"ev": """# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622, population=heart failure, age=>=60 years
Target : gissi-hf, design= randomized_controlled_trial, 6975= 6975, population = heart_failure, age =  <= 78 and >= 56 years old
Both cohorts share study-level condition(s): heartfailure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.

## INPUT
Source: description:sum of ace-inh and arb-dose baseline in percentage of target dose , concepts: agents acting on the renin-angiotensin system|percent target dosage, unit: %, categories: "",
Target: description: original dosage of arb concepts:angiotensin ii receptor antagonist|percentage target dosage, unit: %, categories: """,

}

test_46 = {
"expected": "IMPOSSIBLE",
"rationale": "The source is a composite dose (ACEi + ARB) which cannot be decomposed to isolate the specific ARB-only component required for the target",
"ne": """## INPUT
Source: description:sum of ace-inh and arb-dose in dose , unit:mg , categories: ""
Target: description: original dosage of arb concepts:angiotensin ii receptor antagonist|percentage target dosage, unit:% , categories:""",
"ev": """# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622, population=heart failure, age=>=60 years
Target : gissi-hf, design= randomized_controlled_trial, 6975= 6975, population = heart_failure, age =  <= 78 and >= 56 years old
Both cohorts share study-level condition(s): heartfailure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.

## INPUT
Source: description:sum of ace-inh and arb-dose in dose, concepts: agents acting on the renin-angiotensin system|dosage, unit: mg, categories: "",
Target: description: original dosage of arb concepts:angiotensin ii receptor antagonist|percentage target dosage, unit: %, categories: """,
}

test_47 = {
"expected": "PARTIAL",
"rationale": "Both variables measure the occurrence of percutaneous coronary intervention; the date-based target can be reduced to a binary yes/no indicator.",
"ne": """## INPUT
Source: description:percutaneous coronary intervention,  unit: , categories: "[yes||no]""
Target: description: month coronary angioplasty (only if coronary angioplasty=yes), unit: dd/mm/yyyy, categories:""",
"ev": """# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622, population=heart failure, age=>=60 years
Target : gissi-hf, design= randomized_controlled_trial, 6975= 6975, population = heart_failure, age =  <= 78 and >= 56 years old
Both cohorts share study-level condition(s): heartfailure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.

## INPUT
Source: description:percutaneous coronary intervention, concepts: percutaneous coronary intervention, unit: , categories: "[yes||no]",
Target: description: month coronary angioplasty (only if coronary angioplasty=yes), concepts: percutaneous transluminal angioplasty of coronary artery using imaging guidance with contrast|date of procedure, unit: dd/mm/yyyy, categories: """,
}


test_48 = {
"expected": "PARTIAL",
"rationale": "The source identifies a pathological Q-wave in Lead III, which is a subtype/specific finding of the general pathological Q-wave finding in the target.",
"ne": """## INPUT
Source: description:q-wave present in lead iii,  unit: , categories: "[yes||no]""
Target: description: pathological q waves, unit:, categories:[yes||no]""",
"ev": """# STUDY CONTEXT
Source: time-chf, design=randomized_controlled_trial, N=622, population=heart failure, age=>=60 years
Target : gissi-hf, design= randomized_controlled_trial, 6975= 6975, population = heart_failure, age =  <= 78 and >= 56 years old
Both cohorts share study-level condition(s): heartfailure. A variable encoding any of these shared conditions will be constant across both studies (zero variance) — classify such pairs as IMPOSSIBLE regardless of structural similarity.

## INPUT
Source: description:q-wave present in lead iii,, concepts: q wave - finding||lead iii, unit: , categories: "[yes||no]",
Target: description: pathological q waves, concepts: pathological q wave||electrocardiogram finding, unit:, categories: "[yes||no]""",
}
test_49 ={
"expected": "IMPOSSIBLE",
"rationale": "these two tests are different"
}


# ============================================================
# QUICK REFERENCE: expected results summary
# ============================================================
"""
  test_01  COMPLETE    equivalent units (ng/mL = ug/L)
  test_02  COMPLETE    equivalent units ({counts}/min = /min)
  test_03  COMPATIBLE  same entity, encoding difference (0/1 vs t/f)
  test_04  COMPATIBLE  same entity, unit conversion (umol/L vs mg/dL)
  test_05  COMPATIBLE  same entity, label recode (Female/Male vs m/f)
  test_06  PARTIAL     granularity collapse (3-class -> binary)
  test_07  PARTIAL     category collapse (multi-cause -> specific-cause binary)
  test_08  PARTIAL     dose same-drug cross-scale (mg vs %)
  test_09  PARTIAL     dose member-drug vs class cross-scale
  test_10  PARTIAL     dose member-drug vs class cross-scale (loop diuretic)
  test_11  PARTIAL     asymmetric member/class (binary vs continuous)
  test_12  PARTIAL     asymmetric member/class (binary vs binary)
  test_21  PARTIAL     same categories, temporal qualifier difference (preserve granularity!)
  test_13  IMPOSSIBLE  binary -> continuous fabrication
  test_14  IMPOSSIBLE  cause-of-death vs death-after-procedure
  test_15  IMPOSSIBLE  value vs method (different dimensions)
  test_16  IMPOSSIBLE  severity vs intervention (different dimensions)
  test_17  IMPOSSIBLE  sibling drug classes
  test_18  IMPOSSIBLE  trial-arm indicator vs lab value
  test_22  IMPOSSIBLE  device vs physiological finding (causal, not same entity)
  test_20  IMPOSSIBLE  drug type vs drug dose (different dimensions)
  test_19  EDGE        AF echo vs AF general (COMPATIBLE or PARTIAL ok)
  test_23  EDGE        AST same units, different concept granularity (COMPLETE or COMPATIBLE ok)
  test_24  EDGE        allergies binary vs qualitative (COMPLETE or COMPATIBLE ok)
  test_25  EDGE        erythrocytes same analyte, different units (COMPLETE or COMPATIBLE ok)
  test_26  EDGE        AV block echo vs ECG (COMPLETE or COMPATIBLE ok)
  test_27  EDGE        CCS class categorical vs continuous (PARTIAL ok)
  test_28  EDGE        PAOD severity vs date of intervention (IMPOSSIBLE or PARTIAL ok)
  test_29  EDGE        RAS inhibitors ACEi/ARB to RAS group (PARTIAL ok)
  test_30  EDGE        DCM year vs cardiomegaly presence (IMPOSSIBLE or PARTIAL ok)
  test_31  EDGE        Hypertension year vs first presentation (COMPLETE ok)
  test_32  EDGE        Heart rate vs frequency (COMPLETE ok)
  test_33  EDGE        Cerebrovascular disease mild vs occlusive (PARTIAL ok)
  test_34  EDGE        Beta-blocker use vs substance (PARTIAL ok)
  test_35  EDGE        Valvular disease general vs specific (PARTIAL ok)
  test_36  EDGE        SVES count vs ectopic beats presence (PARTIAL ok)
  test_37  EDGE        Cause of HF different category sets (PARTIAL ok
  test_38  EDGE        Time to composite endpoint with different definitions (PARTIAL ok)
  test_39  EDGE        Cause of death broad multi-class vs specific binary (IMPOSSIBLE or PARTIAL ok)
  test_40  EDGE        Peripheral edema severity same categories (COMPLETE ok)
  test_41  EDGE        Valvular disease general vs specific (IMPOSSIBLE or PARTIAL ok)
  test_42  EDGE        AF during echo vs history of AF (COMPLETE or PARTIAL ok)
  test_43  EDGE        AF vs paroxysmal AF (PARTIAL ok)
  
"""
