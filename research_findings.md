# MAPA Research Findings - What Others Have Done and What Problems They Faced

## 1. Existing Similar Projects

### A. Google Maps Review Scrapers (GitHub)

**omkarcloud/google-maps-reviews-scraper** (2400+ stars)
- Desktop tool that extracts 50+ data points from Google Maps
- Supports fast mode (120-1600 results per city in 1-10 minutes), fastest mode (30 seconds), and detailed mode
- Uses geolocation-based polygon mapping and zoom levels (15-18) for area targeting
- Free tier: 200 searches/month
- Limitation: country-level extraction takes 2-3 days; detailed mode for large cities takes 3-4 hours

**georgekhananaev/google-reviews-scraper-pro** (Works in 2026)
- Uses SeleniumBase with UC (undetected Chrome) mode for anti-detection
- Handles Google's February 2026 "limited view" restriction via search-based navigation
- Stores data in SQLite with MongoDB sync and S3 cloud storage
- Multi-language support (25+ languages), multi-threaded image downloading
- Has a REST API server (FastAPI) with background job processing

**gaspa93/googlemaps-scraper**
- Extracts reviews from Google Maps Points of Interest
- Includes MongoDB integration for incremental storage

**sabsar42/Google-Map-Scrapper-Streamlit-Web**
- Streamlit app that scrapes Google Maps businesses by search term
- Extracts names, addresses, websites, phone numbers, review ratings
- Exports to Excel -- simple but limited in scope

### B. Sentiment Analysis on Reviews (GitHub)

**EAlmazanG/sentiment-analysis-reviews** (Most similar to MAPA's analysis piece)
- Uses Selenium for scraping Google Maps reviews
- Pandas for data processing, scikit-learn for ML classification
- Streamlit dashboard with 4 tabs: Status, Customer Insights, Bad Times Deep Dive, ML Lab
- Uses embeddings, UMAP/PCA for dimensionality reduction, LDA for topic extraction
- Optional GPT API integration for deeper insights
- Limitation: ML Lab tab is slow with large datasets, clustering results were "inconclusive"

**MK-ek11/sentiment_analysis_googlemap_reviews_with_chatgpt**
- Uses Google Maps API + Selenium + BeautifulSoup for scraping
- ChatGPT for sentiment analysis
- Combines official API with web scraping

### C. Business Success Prediction (Kaggle/Academic)

**Kaggle: "Predicting the Success of a Restaurant"**
- Binary classification (success/failure) using location features
- Common features: location, price range, city type, demographic data, real estate data, commercial data
- Models used: Ridge regression, Random Forest, Gradient Boosting, SVM
- Key metric: F1 score and AUC for binary classification

**Stanford CS 229 Final Project**
- Restaurant success prediction using Yelp data
- Linear logistic regression model (chosen for interpretability)
- Optimized using grid search with cross-validation

### D. HuggingFace Models for Review Analysis

**Kaludi/Reviews-Sentiment-Analysis** - Pre-trained model for review sentiment
**siebert/sentiment-roberta-large-english** - RoBERTa-based sentiment model (high accuracy)
**juliensimon/reviews-sentiment-analysis** - Fine-tuned review analysis model

---

## 2. Major Problems Others Faced

### Problem 1: Google Places API Only Returns 5 Reviews
The official Google Places API limits you to 5 reviews per business. There is no pagination. This has been a known issue since the API launched, and Google has explicitly stated they will not change it. This is the single biggest blocker for any project like MAPA.

**Solutions others used:**
- Web scraping with Selenium (most common)
- Third-party APIs like SerpApi, Outscraper, or Apify
- The omkarcloud scraper uses browser automation with anti-detection

### Problem 2: Google Nearby Search Returns Max 60 Results (120 with workaround)
Google Maps only shows up to 60 results per search query (across 3 pages of 20). Some tools get up to 120. For a whole city, this is nowhere near enough.

**Solutions others used:**
- Grid/polygon splitting: divide the city into smaller grid cells, search each cell individually, then combine and deduplicate results. This is how omkarcloud does it.
- Zoom level adjustment: smaller zoom = more granular area = more complete results
- Multiple search queries with slight variations

### Problem 3: Google's Anti-Scraping Measures
Google actively blocks scrapers with CAPTCHAs, IP blocking, rate limiting, and session detection.

**Solutions others used:**
- SeleniumBase UC (undetected Chrome) mode
- Rotating proxies
- Random delays between requests
- Browser fingerprint randomization
- Search-based navigation instead of direct URLs

### Problem 4: February 2026 "Limited View" Update
Google started hiding reviews, images, and other data from users who are not signed in. This broke most existing scrapers.

**Status:** Google appears to have partially rolled this back by late February 2026, but scrapers still need to handle it.

**Solutions:**
- Search-based navigation (bypasses the limited view without login)
- Authenticated browser sessions
- google-reviews-scraper-pro handled this on day one

### Problem 5: Dynamic Content Loading
Google Maps loads content dynamically with infinite scroll. No traditional pagination.

**Solutions:**
- Selenium with explicit waits and scroll simulation
- Monitoring DOM changes to detect when new content loads
- Retry logic for failed loads

### Problem 6: Cost of Third-Party APIs
- SerpApi: ~$0.015 per request (expensive at scale)
- Outscraper: cheaper but still adds up
- Google Places API itself: tiered pricing, roughly $0.02-0.04 per request for detailed data

**For MAPA's scale (entire cities), costs can be significant:**
- A city like Birmingham might have 2000+ restaurants
- Each business needs: listing data + reviews + nearby places = multiple API calls
- At $0.02/call, 2000 businesses with 5 calls each = $200 for one city/category

### Problem 7: Sentiment Analysis Accuracy
- Basic tools (TextBlob, VADER) give mediocre results on review text
- Fine-tuned transformers (RoBERTa, BERT) are much better but slower
- LLM-based analysis (GPT) is most accurate but costs money and raises privacy concerns

### Problem 8: ML Model for Business Success
- Limited public data for training (no financial data available)
- Star ratings as a proxy for success is imperfect
- Binary features lose nuance (distance to parking is more useful than has_parking: yes/no)
- Small datasets per city may not generalize well
- Overfitting risk with many features and few samples

---

## 3. Recommended Approach for MAPA

### Data Collection Strategy
1. **Primary: Google Places API (New)** for business listings and basic data
   - Use the Essentials tier (10,000 free requests/month)
   - Use FieldMask to request only needed fields (reduces cost)
   - Implement grid-splitting for full city coverage

2. **Reviews: Selenium-based scraping** (since API only gives 5 reviews)
   - Use SeleniumBase with UC mode for anti-detection
   - Implement scroll-based loading to get all reviews
   - Add random delays and proxy rotation
   - Handle the "limited view" scenario

3. **Nearby Context: Google Places API Nearby Search**
   - For each business, search for nearby amenities (parking, schools, transport, etc.)
   - Cache results to avoid duplicate API calls for businesses in the same area

### Analysis Strategy
1. **Sentiment Analysis:** Start with a HuggingFace transformer model (siebert/sentiment-roberta-large-english) for accuracy without API costs
2. **Topic Extraction:** Use LDA or BERTopic to find common themes in reviews
3. **Gap Analysis:** Compare sentiment scores and topic frequencies across businesses to find underserved needs

### ML Strategy (Phase 2)
1. **Features:** Binary and continuous mix (has_parking, distance_to_school, nearby_transport_count, avg_competitor_rating, review_count, etc.)
2. **Target:** Binary (rating >= 4.1 = success)
3. **Models to try:** Random Forest, Gradient Boosting (XGBoost), Logistic Regression
4. **Validation:** Cross-validation with stratified splits

---

## 4. Key Takeaways

1. **Nobody has built exactly what MAPA aims to be** -- a combined tool that does crawling + review analysis + market gap detection + nearby context + ML prediction all in one Streamlit dashboard. The closest projects do pieces of this.

2. **The review scraping problem is solvable** but requires Selenium-based approaches, not just the API.

3. **Grid-splitting is essential** for full city coverage (the API/Maps limit of 60-120 results per query is not enough).

4. **Cost management is critical** -- use the free tier strategically, cache aggressively, and avoid redundant API calls.

5. **The ML prediction piece is novel** -- most existing projects stop at sentiment analysis. Predicting business success from map features is less explored and has real value.

---

## Sources
- [omkarcloud/google-maps-reviews-scraper](https://github.com/omkarcloud/google-maps-reviews-scraper)
- [georgekhananaev/google-reviews-scraper-pro](https://github.com/georgekhananaev/google-reviews-scraper-pro)
- [EAlmazanG/sentiment-analysis-reviews](https://github.com/EAlmazanG/sentiment-analysis-reviews)
- [MK-ek11/sentiment_analysis_googlemap_reviews_with_chatgpt](https://github.com/MK-ek11/sentiment_analysis_googlemap_reviews_with_chatgpt)
- [sabsar42/Google-Map-Scrapper-Streamlit-Web](https://github.com/sabsar42/Google-Map-Scrapper-Streamlit-Web)
- [Kaggle: Predicting the Success of a Restaurant](https://www.kaggle.com/code/thiagopanini/predicting-the-success-of-a-restaurant)
- [Kaggle: Restaurant Revenue Prediction](https://www.kaggle.com/c/restaurant-revenue-prediction)
- [HuggingFace: siebert/sentiment-roberta-large-english](https://huggingface.co/siebert/sentiment-roberta-large-english)
- [HuggingFace: Kaludi/Reviews-Sentiment-Analysis](https://huggingface.co/Kaludi/Reviews-Sentiment-Analysis)
- [SerpApi: How AI Can Predict Business Success](https://serpapi.com/blog/how-ai-can-predict-the-success-of-your-business-using-data-from-google-maps/)
- [Livescraper: Bypassing the 5-Review Limit](https://livescraper.com/blog/how-to-scrape-all-google-reviews-in-2025-bypassing-the-5-review-limit/)
- [Google Places API Pricing](https://developers.google.com/maps/billing-and-pricing/pricing)
- [Google Maps Limited View Update](https://www.botsol.com/blog/google-maps-limited-view-update)
- [Outscraper: Google Places API Alternatives](https://outscraper.com/google-places-api-alternatives/)
- [Google Places API Limits (Apify)](https://blog.apify.com/google-places-api-limits/)
