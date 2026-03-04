# MAPA (Map Analytics) - Project Progress

## Project Overview
MAPA is a marketing intelligence tool that uses Google Maps data to analyze local business markets. Users enter a business type and area, and the system crawls Google Maps to collect business listings, reviews, and nearby context (parking, schools, main roads, landmarks). AI then analyzes the reviews to find market gaps and saturation. A machine learning model predicts whether a new business with given features would succeed (4.1+ star rating).

## Tech Stack
- **Dashboard:** Streamlit
- **Crawlers:** Python (Google Places API)
- **AI Analysis:** spaCy, TextBlob (pluggable for LLM APIs later)
- **ML Model:** scikit-learn (Jupyter Notebook)
- **Data Storage:** Local CSV/JSON files initially

## Folder Structure
```
MAPA/
  crawlers/       - Google Maps crawlers and data collectors
  analysis/       - AI review analysis and gap detection
  dashboard/      - Streamlit app files
  notebooks/      - Jupyter notebooks for ML (Phase 2)
  data/           - Collected data storage
  utils/          - Shared utility functions
  config/         - Configuration files (API keys, settings)
```

## Progress Log

### Step 1 - Project Structure Created (2026-03-04)
- Created folder structure: crawlers, analysis, dashboard, notebooks, data, utils, config
- Created this progress.md file

### Step 2 - Research Completed (2026-03-04)
- Searched GitHub, Reddit, HuggingFace, Kaggle, and general web for similar projects
- Found 10+ existing projects doing pieces of what MAPA does (none do the full thing)
- Identified 8 major problems others faced (5-review API limit, anti-scraping, limited view update, cost, etc.)
- Documented recommended approach based on findings
- Full research saved in research_findings.md
