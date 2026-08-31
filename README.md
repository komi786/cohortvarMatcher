# 🧬 CohortVarMatcher: Semantic Variable Matching for Multi-Study Data Pooling

CohortVarMatcher is a metadata-driven framework for identifying **semantically comparable variables across heterogeneous clinical cohort studies**.

Given metadata dictionaries from multiple studies, CohortVarMatcher retrieves and ranks candidate matches between variables using a combination of **lexical, semantic, and biomedical knowledge-based retrieval**. The framework is designed to help researchers determine **which variables can potentially be compared or harmonized across cohorts and how they relate**, before requesting or pooling patient-level data.

The approach combines neural semantic retrieval with structured biomedical knowledge to improve matching when variables differ in terminology, naming conventions, granularity, or representation.

## 🔧 Key Features

- **Cross-cohort variable matching** based on study metadata
- **Hybrid retrieval** combining lexical and semantic similarity
- **Biomedical knowledge integration** using controlled vocabularies and ontological relationships
- **Candidate retrieval and re-ranking** for identifying the most likely variable correspondences
- Identification of different levels of correspondence, including **exact, highly relevant, and partial matches**
- Support for heterogeneous variable descriptions, names, codes, units, categorical values, and contextual metadata
- Evaluation of variable matching using a **reference standard (ground truth)**
- Experimental comparison of different retrieval and language-model configurations
- Reproducible evaluation pipeline for cross-cohort matching experiments

## 📊 Experimental Results

The experimental cross-cohort variable mapping results supporting the study are available on Zenodo.

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22212439.svg)](https://doi.org/10.5281/zenodo.22212439)

The mapping files are provided under restricted access and can be requested for research and peer-review purposes.

## 📌 Use Cases

- Identifying comparable variables across heterogeneous clinical cohort studies
- Assessing cross-study data availability for a research question
- Supporting metadata-driven cohort exploration
- Determining which variables may be suitable for subsequent harmonization
- Preparing multi-study datasets for federated analysis or joint modelling
- Supporting semantic interoperability before patient-level data access or pooling

## 🧩 Conceptual Workflow

Research question
→ Identify relevant cohorts
→ Inspect study metadata
→ Match comparable variables across cohorts
→ Assess correspondence and compatibility
→ Determine variables suitable for harmonization
→ Proceed to data access and downstream analysis

CohortVarMatcher therefore focuses on the **variable comparability and matching step**, rather than performing patient-level data harmonization itself.
