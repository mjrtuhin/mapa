# MAPA (Map Analytics) - Project Progress

## Project Overview
MAPA is a marketing intelligence tool that uses Google Maps data to analyze local business markets. Users enter a business type and area, and the system crawls Google Maps to collect business listings, reviews, and nearby context (parking, schools, main roads, landmarks). AI then analyzes the reviews to find market gaps and saturation. A machine learning model predicts whether a new business with given features would succeed (4.1+ star rating).

## Tech Stack
- **Dashboard:** Streamlit
- **Crawlers:** Python (Google Places API)
- **AI Analysis:** Groq API (free LLM inference)
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

### Step 3 - Config, Requirements, and App Skeleton (2026-03-04)
- Created requirements.txt with all dependencies
- Created config/settings.py with env loading and project constants
- Created app.py -- Streamlit dashboard with 5 tabs: Overview, Reviews Analysis, Market Gaps, Nearby Context, Success Predictor
- Polished UI with sidebar inputs, metrics cards, and custom CSS

### Step 4 - Geo Utilities Module (2026-03-04)
- Created utils/geo_utils.py with city geocoding, bounding box lookup, grid splitting, and haversine distance
- Grid splitting divides a city into smaller cells (configurable size) for full search coverage

### Step 5 - Crawler Modules (2026-03-04)
- Created crawlers/google_api_crawler.py -- uses official Google Places API with grid splitting and deduplication
- Created crawlers/selenium_crawler.py -- free scraper using SeleniumBase UC mode with anti-detection, scroll-based loading, review extraction, and business detail scraping
- Both crawlers share the same grid splitting utility for full city coverage

### Step 6 - Nearby Context Collector (2026-03-04)
- Created crawlers/nearby_collector.py
- Searches 8 categories: parking, public transport, schools, main roads, shopping, hospitals, parks, tourist attractions
- Uses 500m radius from each business, calculates haversine distances
- Produces binary features (has_parking, has_school, etc.) and counts for ML

### Step 7 - AI Review Analysis Module (2026-03-04)
- Created analysis/review_analyzer.py using Groq API (free LLM inference)
- Three analysis modes: batch review analysis, market gap detection, single review analysis
- Batch mode: sentiment distribution, top positives/negatives, topic extraction
- Market gap mode: analyzes complaints across all businesses to find unmet needs and saturation
- Returns structured JSON for dashboard visualization

### Step 8 - Wired Dashboard (2026-03-04)
- Rewrote app.py to connect all modules into a working pipeline
- Overview tab: metrics cards, interactive folium map (color-coded by rating), business table, rating histogram
- Reviews tab: per-business sentiment pie chart, topic list, positives/negatives cards, cross-business comparison bar chart
- Market Gaps tab: gap cards, saturation cards, opportunity cards, AI-generated summary
- Nearby Context tab: bar chart of amenity counts, checklist with distances, cross-business comparison table
- Success Predictor tab: placeholder with preview of feature toggles (Phase 2)
- Full pipeline: search -> collect reviews -> AI analysis -> gap detection -> nearby context -> save to JSON
- Session state management for persistence across tab switches

### Step 9 - ML Notebook Created (2026-03-04)
- Created notebooks/business_success_predictor.ipynb
- 11 sections: setup, data loading, preparation, feature engineering, correlation analysis, train/test split, model training, comparison, feature importance, model saving, prediction function
- Three models compared: Logistic Regression, Random Forest, XGBoost
- Visualizations: rating distribution, success pie chart, correlation heatmap, model comparison bars, ROC curves, confusion matrices, feature importance
- Saves best model as joblib file for integration with Streamlit dashboard
- Includes predict_success() function ready for Phase 1 integration
