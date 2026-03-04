import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import json
import os
import time
import glob

from config.settings import DATA_DIR, GOOGLE_MAPS_API_KEY, GROQ_API_KEY
import math


def is_valid_coord(val):
    if val is None:
        return False
    try:
        return not math.isnan(float(val))
    except (TypeError, ValueError):
        return False

st.set_page_config(
    page_title="MAPA - Map Analytics",
    page_icon="📍",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #1a1a2e;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #6c757d;
        margin-top: 0;
    }
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1.5rem;
        border-radius: 12px;
        color: white;
        text-align: center;
    }
    .gap-card {
        background: #fff3cd;
        border-left: 4px solid #ffc107;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 4px;
    }
    .opportunity-card {
        background: #d4edda;
        border-left: 4px solid #28a745;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 4px;
    }
    .saturated-card {
        background: #f8d7da;
        border-left: 4px solid #dc3545;
        padding: 1rem;
        margin: 0.5rem 0;
        border-radius: 4px;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 24px;
        border-radius: 8px 8px 0 0;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if "businesses" not in st.session_state:
    st.session_state.businesses = []
if "reviews" not in st.session_state:
    st.session_state.reviews = {}
if "analysis" not in st.session_state:
    st.session_state.analysis = {}
if "gaps" not in st.session_state:
    st.session_state.gaps = {}
if "nearby_data" not in st.session_state:
    st.session_state.nearby_data = {}
if "master_summary" not in st.session_state:
    st.session_state.master_summary = ""
if "search_done" not in st.session_state:
    st.session_state.search_done = False


with st.sidebar:
    st.image("https://img.icons8.com/color/96/map-pin.png", width=60)
    st.title("MAPA")
    st.caption("Map Analytics Platform")
    st.divider()

    business_type = st.text_input(
        "Business Type",
        placeholder="e.g. Restaurants, Grocery Shops, Clothing Stores",
    )

    area = st.text_input(
        "Area / City",
        placeholder="e.g. Birmingham, London, Manchester",
    )

    data_source = st.radio(
        "Data Source",
        ["Selenium (Free)", "Google Places API"],
        index=0,
        help="Selenium is free but slower. Google Places API needs an API key.",
    )

    review_limit = st.slider(
        "Max Reviews per Business",
        min_value=10,
        max_value=200,
        value=50,
        step=10,
    )

    collect_nearby = st.checkbox("Collect Nearby Context", value=False,
                                  help="Find parking, schools, transport near each business. Takes longer.")

    st.divider()

    search_btn = st.button(
        "Search & Analyse", type="primary", use_container_width=True
    )

    if st.session_state.search_done:
        st.divider()
        st.success(f"Found {len(st.session_state.businesses)} businesses")


def save_csv(dataframe, filename):
    """Save a dataframe to CSV in the data folder."""
    path = os.path.join(DATA_DIR, filename)
    dataframe.to_csv(path, index=False)
    print(f"[MAPA] Saved: {path}")
    return path


def run_search(business_type, area, data_source, review_limit, collect_nearby_flag):
    """Run the full search, review collection, and analysis pipeline."""

    tag = f"{business_type}_{area}".replace(" ", "_").lower()

    status = st.status("Starting MAPA analysis...", expanded=True)

    status.write("Step 1/4: Searching for businesses...")
    progress_bar = st.progress(0)

    if data_source == "Google Places API":
        if not GOOGLE_MAPS_API_KEY:
            st.error("Google Maps API key not set. Add it to your .env file or use Selenium.")
            return
        from crawlers.google_api_crawler import GoogleAPICrawler
        crawler = GoogleAPICrawler()
    else:
        from crawlers.selenium_crawler import SeleniumCrawler
        crawler = SeleniumCrawler()

    def search_progress(current, total):
        progress_bar.progress(current / total)
        status.write(f"Searching grid cell {current}/{total}...")

    businesses = crawler.search_businesses(business_type, area, search_progress)
    st.session_state.businesses = businesses
    progress_bar.progress(1.0)
    status.write(f"Found {len(businesses)} businesses!")

    if businesses:
        biz_df = pd.DataFrame(businesses)
        save_csv(biz_df, f"{tag}_businesses.csv")
        status.write(f"Auto-saved {len(businesses)} businesses to CSV.")

    if not businesses:
        status.update(label="No businesses found.", state="error")
        return

    status.write("Step 2/4: Collecting reviews (single browser session)...")
    progress_bar_reviews = st.progress(0)
    all_reviews = {}
    review_businesses = businesses[:20]

    if data_source == "Selenium (Free)":
        from crawlers.selenium_crawler import SeleniumCrawler
        review_crawler = SeleniumCrawler()

        def review_progress(current, total):
            progress_bar_reviews.progress(current / total)
            status.write(f"Getting reviews: {current}/{total}...")

        all_reviews = review_crawler.get_reviews_bulk(
            review_businesses, max_reviews=review_limit, progress_callback=review_progress
        )

        for biz_name, revs in all_reviews.items():
            if revs:
                rows = []
                for r in revs:
                    r["business_name"] = biz_name
                    rows.append(r)
                rev_df = pd.DataFrame(rows)
                rev_path = os.path.join(DATA_DIR, f"{tag}_reviews.csv")
                if os.path.exists(rev_path):
                    rev_df.to_csv(rev_path, mode="a", header=False, index=False)
                else:
                    rev_df.to_csv(rev_path, index=False)
        status.write(f"Auto-saved reviews to CSV.")
    else:
        from crawlers.google_api_crawler import GoogleAPICrawler
        api_crawler = GoogleAPICrawler()

        for idx, biz in enumerate(review_businesses):
            progress_bar_reviews.progress((idx + 1) / len(review_businesses))
            pid = biz.get("place_id", "")
            if pid:
                details = api_crawler.get_place_details(pid)
                revs = details.get("reviews", [])
                all_reviews[biz["name"]] = revs

                if revs:
                    rows = []
                    for r in revs:
                        r["business_name"] = biz.get("name", "")
                        rows.append(r)
                    rev_df = pd.DataFrame(rows)
                    rev_path = os.path.join(DATA_DIR, f"{tag}_reviews.csv")
                    if os.path.exists(rev_path):
                        rev_df.to_csv(rev_path, mode="a", header=False, index=False)
                    else:
                        rev_df.to_csv(rev_path, index=False)

    st.session_state.reviews = all_reviews
    progress_bar_reviews.progress(1.0)

    status.write("Step 3/4: Analyzing reviews with AI...")
    if GROQ_API_KEY:
        from analysis.review_analyzer import ReviewAnalyzer
        analyzer = ReviewAnalyzer()

        analysis_results = {}
        for biz_name, revs in all_reviews.items():
            if revs:
                analysis_results[biz_name] = analyzer.analyze_reviews(
                    revs, business_type
                )

        st.session_state.analysis = analysis_results

        if analysis_results:
            analysis_rows = []
            for biz_name, result in analysis_results.items():
                sentiment = result.get("sentiment", {})
                analysis_rows.append({
                    "business_name": biz_name,
                    "positive_pct": sentiment.get("positive_pct", 0),
                    "negative_pct": sentiment.get("negative_pct", 0),
                    "neutral_pct": sentiment.get("neutral_pct", 0),
                    "summary": result.get("summary", ""),
                    "top_positives": " | ".join(result.get("top_positives", [])),
                    "top_negatives": " | ".join(result.get("top_negatives", [])),
                    "topics": " | ".join(result.get("topics", [])),
                })
            analysis_df = pd.DataFrame(analysis_rows)
            save_csv(analysis_df, f"{tag}_analysis.csv")
            status.write("Auto-saved analysis results to CSV.")

        status.write("Detecting market gaps...")
        gaps = analyzer.detect_market_gaps(all_reviews, business_type, area)
        st.session_state.gaps = gaps

        if gaps:
            gaps_rows = []
            for gap in gaps.get("gaps", []):
                gaps_rows.append({"type": "gap", "description": gap})
            for sat in gaps.get("saturated", []):
                gaps_rows.append({"type": "saturated", "description": sat})
            for opp in gaps.get("opportunities", []):
                gaps_rows.append({"type": "opportunity", "description": opp})
            if gaps_rows:
                gaps_df = pd.DataFrame(gaps_rows)
                save_csv(gaps_df, f"{tag}_market_gaps.csv")
                status.write("Auto-saved market gaps to CSV.")

        status.write("Generating comprehensive review summary...")
        master = analyzer.generate_master_summary(all_reviews, business_type, area)
        st.session_state.master_summary = master

        master_path = os.path.join(DATA_DIR, f"{tag}_master_summary.txt")
        with open(master_path, "w") as f:
            f.write(master)
        status.write("Auto-saved master summary.")
    else:
        st.warning("Groq API key not set. Skipping AI analysis. Add GROQ_API_KEY to .env.")

    if collect_nearby_flag:
        status.write("Step 4/4: Collecting nearby context...")
        from crawlers.nearby_collector import NearbyCollector
        collector = NearbyCollector()

        progress_bar_nearby = st.progress(0)
        nearby_results = {}

        for idx, biz in enumerate(businesses[:10]):
            progress_bar_nearby.progress((idx + 1) / min(len(businesses), 10))
            status.write(f"Checking nearby for: {biz.get('name', 'Unknown')}...")

            lat, lng = biz.get("lat"), biz.get("lng")
            if is_valid_coord(lat) and is_valid_coord(lng):
                nearby_results[biz["name"]] = collector.collect_nearby(lat, lng)

                features = collector.to_features(nearby_results[biz["name"]])
                features["business_name"] = biz["name"]
                nearby_df = pd.DataFrame([features])
                nearby_path = os.path.join(DATA_DIR, f"{tag}_nearby.csv")
                if os.path.exists(nearby_path):
                    nearby_df.to_csv(nearby_path, mode="a", header=False, index=False)
                else:
                    nearby_df.to_csv(nearby_path, index=False)
                status.write(f"Auto-saved nearby data for {biz['name']}.")

        st.session_state.nearby_data = nearby_results
        progress_bar_nearby.progress(1.0)
    else:
        status.write("Step 4/4: Skipping nearby context (not selected).")

    st.session_state.search_done = True
    status.update(label="Analysis complete!", state="complete")
    st.success(f"All data saved as CSV files in the data/ folder with prefix: {tag}_")


if search_btn:
    if not business_type or not area:
        st.error("Please enter both a business type and an area.")
    else:
        run_search(business_type, area, data_source, review_limit, collect_nearby)


st.markdown('<p class="main-header">MAPA</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">Market Analysis Platform -- Find gaps, spot opportunities, predict success.</p>',
    unsafe_allow_html=True,
)

tab_overview, tab_reviews, tab_gaps, tab_nearby, tab_predict, tab_download, tab_history = st.tabs(
    ["Overview", "Reviews Analysis", "Market Gaps", "Nearby Context", "Success Predictor", "Download Data", "Search History"]
)


with tab_overview:
    st.subheader("Business Overview")

    if not st.session_state.search_done:
        st.info("Enter a business type and area in the sidebar, then click 'Search & Analyse'.")
    else:
        businesses = st.session_state.businesses

        ratings = [b["rating"] for b in businesses if b.get("rating")]
        total_reviews_count = sum(b.get("total_reviews", 0) for b in businesses)
        avg_rating = round(sum(ratings) / len(ratings), 2) if ratings else 0

        successful = len([
            b for b in businesses
            if b.get("rating") and b["rating"] >= 4.1
            and b.get("total_reviews", 0) >= 100
        ])
        success_pct = f"{round(successful / len(businesses) * 100)}%" if businesses else "N/A"

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Businesses Found", len(businesses))
        with col2:
            st.metric("Avg Rating", f"{avg_rating} / 5")
        with col3:
            st.metric("Total Reviews", f"{total_reviews_count:,}")
        with col4:
            st.metric("Successful (4.1+ & 100+ rev)", success_pct)

        st.markdown("---")

        col_map, col_table = st.columns([3, 2])

        with col_map:
            st.markdown("**Map View**")
            valid_locations = [
                b for b in businesses
                if is_valid_coord(b.get("lat")) and is_valid_coord(b.get("lng"))
            ]

            if valid_locations:
                center_lat = sum(b["lat"] for b in valid_locations) / len(valid_locations)
                center_lng = sum(b["lng"] for b in valid_locations) / len(valid_locations)

                m = folium.Map(location=[center_lat, center_lng], zoom_start=13)

                for biz in valid_locations:
                    is_success = (biz.get("rating", 0) >= 4.1 and biz.get("total_reviews", 0) >= 100)
                    color = "green" if is_success else "orange" if biz.get("rating", 0) >= 3.5 else "red"
                    folium.CircleMarker(
                        location=[biz["lat"], biz["lng"]],
                        radius=6,
                        popup=f"{biz.get('name', 'Unknown')}\nRating: {biz.get('rating', 'N/A')}\nReviews: {biz.get('total_reviews', 0)}",
                        color=color,
                        fill=True,
                        fill_color=color,
                        fill_opacity=0.7,
                    ).add_to(m)

                st_folium(m, width=700, height=450)
                st.caption("Green = successful (4.1+ stars & 100+ reviews) | Orange = moderate | Red = low rated")
            else:
                st.warning("No location data available for map.")

        with col_table:
            st.markdown("**Business Listings**")
            df = pd.DataFrame(businesses)
            display_cols = ["name", "rating", "total_reviews", "address"]
            available_cols = [c for c in display_cols if c in df.columns]
            if available_cols:
                st.dataframe(
                    df[available_cols].sort_values(
                        by="rating", ascending=False, na_position="last"
                    ),
                    use_container_width=True,
                    height=400,
                )

        st.markdown("---")
        st.markdown("**Rating Distribution**")
        if ratings:
            fig = px.histogram(
                x=ratings,
                nbins=10,
                labels={"x": "Rating", "y": "Count"},
                color_discrete_sequence=["#667eea"],
            )
            fig.update_layout(
                xaxis_title="Rating",
                yaxis_title="Number of Businesses",
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True)


with tab_reviews:
    st.subheader("Reviews Analysis")
    st.caption("AI-powered sentiment analysis and topic extraction from customer reviews.")

    if not st.session_state.search_done or not st.session_state.analysis:
        st.info("Run a search first to see review analysis. Make sure GROQ_API_KEY is set in .env.")
    else:
        if st.session_state.master_summary:
            st.markdown("**Comprehensive Market Review Analysis**")
            st.markdown(
                f'<div style="background-color:#f8f9fa; padding:20px; border-radius:10px; '
                f'border-left:4px solid #007bff; line-height:1.8; font-size:15px;">'
                f'{st.session_state.master_summary}</div>',
                unsafe_allow_html=True,
            )
            st.markdown("---")

        analysis = st.session_state.analysis

        biz_names = list(analysis.keys())
        selected_biz = st.selectbox("Select a business:", biz_names)

        if selected_biz and selected_biz in analysis:
            result = analysis[selected_biz]

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Sentiment Distribution**")
                sentiment = result.get("sentiment", {})
                if sentiment:
                    fig = go.Figure(data=[go.Pie(
                        labels=["Positive", "Negative", "Neutral"],
                        values=[
                            sentiment.get("positive_pct", 0),
                            sentiment.get("negative_pct", 0),
                            sentiment.get("neutral_pct", 0),
                        ],
                        marker_colors=["#28a745", "#dc3545", "#6c757d"],
                        hole=0.4,
                    )])
                    fig.update_layout(height=350)
                    st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.markdown("**Summary**")
                st.write(result.get("summary", "No summary available."))

                st.markdown("**Key Topics**")
                topics = result.get("topics", [])
                for topic in topics:
                    st.markdown(f"- {topic}")

            col3, col4 = st.columns(2)

            with col3:
                st.markdown("**Top Praised Aspects**")
                positives = result.get("top_positives", [])
                for p in positives:
                    st.markdown(f'<div class="opportunity-card">{p}</div>', unsafe_allow_html=True)

            with col4:
                st.markdown("**Top Criticized Aspects**")
                negatives = result.get("top_negatives", [])
                for n in negatives:
                    st.markdown(f'<div class="saturated-card">{n}</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("**All Business Sentiment Comparison**")

        comparison_data = []
        for biz_name, result in analysis.items():
            sentiment = result.get("sentiment", {})
            comparison_data.append({
                "Business": biz_name,
                "Positive %": sentiment.get("positive_pct", 0),
                "Negative %": sentiment.get("negative_pct", 0),
                "Neutral %": sentiment.get("neutral_pct", 0),
            })

        if comparison_data:
            comp_df = pd.DataFrame(comparison_data)
            fig = px.bar(
                comp_df,
                x="Business",
                y=["Positive %", "Negative %", "Neutral %"],
                barmode="stack",
                color_discrete_sequence=["#28a745", "#dc3545", "#6c757d"],
            )
            fig.update_layout(
                xaxis_tickangle=-45,
                height=400,
                yaxis_title="Percentage",
            )
            st.plotly_chart(fig, use_container_width=True)


with tab_gaps:
    st.subheader("Market Gaps")
    st.caption("Where customer needs are not being met in the selected area.")

    if not st.session_state.search_done or not st.session_state.gaps:
        st.info("Run a search first to see market gap analysis.")
    else:
        gaps = st.session_state.gaps

        st.markdown("**Summary**")
        st.write(gaps.get("summary", "No summary available."))

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**Market Gaps (Unmet Needs)**")
            for gap in gaps.get("gaps", []):
                st.markdown(f'<div class="gap-card">{gap}</div>', unsafe_allow_html=True)

        with col2:
            st.markdown("**Saturation Points (Oversupplied)**")
            for sat in gaps.get("saturated", []):
                st.markdown(f'<div class="saturated-card">{sat}</div>', unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("**Business Opportunities**")
        for opp in gaps.get("opportunities", []):
            st.markdown(f'<div class="opportunity-card">{opp}</div>', unsafe_allow_html=True)


with tab_nearby:
    st.subheader("Nearby Context")
    st.caption("Factors that influence business success: parking, transport, schools, landmarks.")

    if not st.session_state.search_done or not st.session_state.nearby_data:
        st.info("Run a search with 'Collect Nearby Context' enabled to see this data.")
    else:
        nearby = st.session_state.nearby_data
        biz_names = list(nearby.keys())

        selected_biz = st.selectbox("Select a business:", biz_names, key="nearby_select")

        if selected_biz and selected_biz in nearby:
            biz_nearby = nearby[selected_biz]

            categories = list(biz_nearby.keys())
            counts = [biz_nearby[c].get("count", 0) for c in categories]
            has_nearby = [biz_nearby[c].get("has_nearby", False) for c in categories]

            col1, col2 = st.columns(2)

            with col1:
                st.markdown("**Nearby Amenity Counts**")
                fig = px.bar(
                    x=categories,
                    y=counts,
                    labels={"x": "Category", "y": "Count"},
                    color=counts,
                    color_continuous_scale="Viridis",
                )
                fig.update_layout(height=350)
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.markdown("**Amenity Checklist**")
                for cat in categories:
                    status_icon = "Yes" if biz_nearby[cat].get("has_nearby") else "No"
                    closest = biz_nearby[cat].get("closest_distance_km")
                    dist_text = f" ({closest} km)" if closest else ""
                    color = "#28a745" if status_icon == "Yes" else "#dc3545"
                    st.markdown(
                        f'<span style="color:{color}; font-weight:bold;">[{status_icon}]</span> '
                        f'{cat.replace("_", " ").title()}{dist_text}',
                        unsafe_allow_html=True,
                    )

        st.markdown("---")
        st.markdown("**Nearby Context Comparison Across All Businesses**")

        comparison_rows = []
        for biz_name, biz_nearby in nearby.items():
            row = {"Business": biz_name}
            for cat, data in biz_nearby.items():
                row[cat.replace("_", " ").title()] = data.get("count", 0)
            comparison_rows.append(row)

        if comparison_rows:
            comp_df = pd.DataFrame(comparison_rows)
            st.dataframe(comp_df, use_container_width=True)


with tab_predict:
    st.subheader("Success Predictor")
    st.caption("Will a new business with these features be successful? (4.1+ stars AND 100+ reviews)")

    model_path = os.path.join(os.path.dirname(__file__), "models", "best_model.joblib")
    model_exists = os.path.exists(model_path)

    if not model_exists:
        st.warning(
            "No trained model found. To use predictions:\n\n"
            "1. Collect data using the Search tab (multiple cities/categories recommended)\n"
            "2. Open notebooks/business_success_predictor.ipynb\n"
            "3. Run all cells to train the model\n"
            "4. Come back here and refresh"
        )

    st.markdown("---")
    st.markdown("**Enter features for your hypothetical business:**")

    col1, col2 = st.columns(2)
    with col1:
        pred_parking = st.toggle("Has Parking Nearby", key="pred_parking")
        pred_transport = st.toggle("Near Public Transport", key="pred_transport")
        pred_school = st.toggle("Near School/University", key="pred_school")
        pred_road = st.toggle("On Main Road", key="pred_road")
    with col2:
        pred_shopping = st.toggle("Near Shopping Area", key="pred_shopping")
        pred_hospital = st.toggle("Near Hospital", key="pred_hospital")
        pred_park = st.toggle("Near Park", key="pred_park")
        pred_tourist = st.toggle("Near Tourist Attraction", key="pred_tourist")

    st.markdown("---")
    st.markdown("**Additional details:**")

    col3, col4 = st.columns(2)
    with col3:
        pred_parking_count = st.number_input("Parking spots nearby", min_value=0, max_value=20, value=2, key="pred_parking_count")
        pred_transport_count = st.number_input("Transport stops nearby", min_value=0, max_value=20, value=1, key="pred_transport_count")
        pred_school_count = st.number_input("Schools nearby", min_value=0, max_value=10, value=0, key="pred_school_count")
        pred_road_count = st.number_input("Main roads nearby", min_value=0, max_value=5, value=1, key="pred_road_count")
    with col4:
        pred_shopping_count = st.number_input("Shopping areas nearby", min_value=0, max_value=10, value=0, key="pred_shopping_count")
        pred_hospital_count = st.number_input("Hospitals nearby", min_value=0, max_value=5, value=0, key="pred_hospital_count")
        pred_park_count = st.number_input("Parks nearby", min_value=0, max_value=10, value=1, key="pred_park_count")
        pred_tourist_count = st.number_input("Tourist spots nearby", min_value=0, max_value=10, value=0, key="pred_tourist_count")

    predict_btn = st.button("Predict Success", type="primary", use_container_width=True, key="predict_btn")

    if predict_btn:
        if not model_exists:
            st.error("Train the ML model first using the Jupyter notebook.")
        else:
            import joblib

            features_path = os.path.join(os.path.dirname(__file__), "models", "features.json")
            scaler_path = os.path.join(os.path.dirname(__file__), "models", "scaler.joblib")

            model = joblib.load(model_path)
            scaler = joblib.load(scaler_path)

            with open(features_path, "r") as f:
                feature_config = json.load(f)

            feature_input = {
                "has_parking": int(pred_parking),
                "has_public_transport": int(pred_transport),
                "has_schools": int(pred_school),
                "has_main_road": int(pred_road),
                "has_shopping": int(pred_shopping),
                "has_hospital": int(pred_hospital),
                "has_park": int(pred_park),
                "has_tourist_attraction": int(pred_tourist),
                "parking_count": pred_parking_count,
                "public_transport_count": pred_transport_count,
                "schools_count": pred_school_count,
                "main_road_count": pred_road_count,
                "shopping_count": pred_shopping_count,
                "hospital_count": pred_hospital_count,
                "park_count": pred_park_count,
                "tourist_attraction_count": pred_tourist_count,
                "parking_closest_km": 0.1 if pred_parking else 999,
                "public_transport_closest_km": 0.2 if pred_transport else 999,
                "schools_closest_km": 0.3 if pred_school else 999,
                "main_road_closest_km": 0.05 if pred_road else 999,
                "shopping_closest_km": 0.2 if pred_shopping else 999,
                "hospital_closest_km": 0.3 if pred_hospital else 999,
                "park_closest_km": 0.15 if pred_park else 999,
                "tourist_attraction_closest_km": 0.2 if pred_tourist else 999,
                "total_reviews": 0,
                "total_nearby_amenities": sum([
                    pred_parking_count, pred_transport_count, pred_school_count,
                    pred_road_count, pred_shopping_count, pred_hospital_count,
                    pred_park_count, pred_tourist_count,
                ]),
                "amenity_diversity": sum([
                    int(pred_parking), int(pred_transport), int(pred_school),
                    int(pred_road), int(pred_shopping), int(pred_hospital),
                    int(pred_park), int(pred_tourist),
                ]),
            }

            feature_names = feature_config["features"]
            feature_values = [feature_input.get(f, 0) for f in feature_names]
            X_input = pd.DataFrame([feature_values], columns=feature_names)

            model_name = feature_config.get("best_model", "")
            if model_name == "Logistic Regression":
                X_input = pd.DataFrame(scaler.transform(X_input), columns=feature_names)

            prediction = model.predict(X_input)[0]
            probability = model.predict_proba(X_input)[0]

            st.markdown("---")
            st.markdown("**Prediction Result:**")

            if prediction == 1:
                st.success(
                    f"This business is likely to be SUCCESSFUL "
                    f"(probability: {probability[1]:.0%})"
                )
            else:
                st.error(
                    f"This business may STRUGGLE to succeed "
                    f"(success probability: {probability[1]:.0%})"
                )

            col_r1, col_r2 = st.columns(2)
            with col_r1:
                fig = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=probability[1] * 100,
                    title={"text": "Success Probability"},
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar": {"color": "#28a745" if prediction == 1 else "#dc3545"},
                        "steps": [
                            {"range": [0, 40], "color": "#f8d7da"},
                            {"range": [40, 60], "color": "#fff3cd"},
                            {"range": [60, 100], "color": "#d4edda"},
                        ],
                    },
                ))
                fig.update_layout(height=300)
                st.plotly_chart(fig, use_container_width=True)

            with col_r2:
                st.markdown("**What this means:**")
                if probability[1] >= 0.7:
                    st.write("Strong indicators of success. This location has good amenities and infrastructure nearby.")
                elif probability[1] >= 0.5:
                    st.write("Moderate chance of success. Some positive factors but room for improvement in location features.")
                else:
                    st.write("Lower chance of success based on location features alone. Consider areas with better infrastructure.")

                st.markdown(f"**Model used:** {model_name}")
                st.markdown(f"**Success = 4.1+ stars AND 100+ reviews**")


with tab_download:
    st.subheader("Download Data")
    st.caption("Download collected data as CSV files.")

    csv_files = glob.glob(os.path.join(DATA_DIR, "*.csv"))

    if not csv_files:
        st.info("No data files yet. Run a search first to collect data.")
    else:
        st.markdown(f"**{len(csv_files)} files available:**")

        for filepath in sorted(csv_files):
            filename = os.path.basename(filepath)
            file_size = os.path.getsize(filepath)
            size_str = f"{file_size / 1024:.1f} KB" if file_size > 1024 else f"{file_size} bytes"

            col_name, col_size, col_btn = st.columns([3, 1, 1])
            with col_name:
                st.markdown(f"**{filename}**")
            with col_size:
                st.caption(size_str)
            with col_btn:
                with open(filepath, "r") as f:
                    csv_content = f.read()
                st.download_button(
                    label="Download",
                    data=csv_content,
                    file_name=filename,
                    mime="text/csv",
                    key=f"dl_{filename}",
                )

        st.markdown("---")
        if st.button("Delete all data files", type="secondary", key="delete_all_data"):
            for filepath in csv_files:
                os.remove(filepath)
            st.success("All data files deleted.")
            st.rerun()


with tab_history:
    st.subheader("Search History")
    st.caption("Load previously collected data without re-crawling.")

    csv_files = glob.glob(os.path.join(DATA_DIR, "*_businesses.csv"))

    if not csv_files:
        st.info("No previous searches found. Run a search first.")
    else:
        search_options = []
        for filepath in sorted(csv_files, reverse=True):
            filename = os.path.basename(filepath)
            tag = filename.replace("_businesses.csv", "")
            mod_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(os.path.getmtime(filepath)))
            search_options.append({"tag": tag, "path": filepath, "date": mod_time})

        st.markdown(f"**{len(search_options)} previous searches found:**")

        for opt in search_options:
            col_tag, col_date, col_btn = st.columns([3, 2, 1])
            with col_tag:
                st.markdown(f"**{opt['tag'].replace('_', ' ').title()}**")
            with col_date:
                st.caption(opt["date"])
            with col_btn:
                if st.button("Load", key=f"load_{opt['tag']}"):
                    biz_df = pd.read_csv(opt["path"])
                    st.session_state.businesses = biz_df.to_dict("records")

                    tag = opt["tag"]
                    reviews_path = os.path.join(DATA_DIR, f"{tag}_reviews.csv")
                    if os.path.exists(reviews_path):
                        rev_df = pd.read_csv(reviews_path)
                        grouped = {}
                        for biz_name, group in rev_df.groupby("business_name"):
                            grouped[biz_name] = group.to_dict("records")
                        st.session_state.reviews = grouped

                    analysis_path = os.path.join(DATA_DIR, f"{tag}_analysis.csv")
                    if os.path.exists(analysis_path):
                        ana_df = pd.read_csv(analysis_path)
                        analysis_dict = {}
                        for _, row in ana_df.iterrows():
                            analysis_dict[row["business_name"]] = {
                                "sentiment": {
                                    "positive_pct": row.get("positive_pct", 0),
                                    "negative_pct": row.get("negative_pct", 0),
                                    "neutral_pct": row.get("neutral_pct", 0),
                                },
                                "summary": row.get("summary", ""),
                                "top_positives": str(row.get("top_positives", "")).split(" | "),
                                "top_negatives": str(row.get("top_negatives", "")).split(" | "),
                                "topics": str(row.get("topics", "")).split(" | "),
                            }
                        st.session_state.analysis = analysis_dict

                    gaps_path = os.path.join(DATA_DIR, f"{tag}_market_gaps.csv")
                    if os.path.exists(gaps_path):
                        gaps_df = pd.read_csv(gaps_path)
                        gaps_dict = {"gaps": [], "saturated": [], "opportunities": [], "summary": "Loaded from history."}
                        for _, row in gaps_df.iterrows():
                            gap_type = row.get("type", "")
                            desc = row.get("description", "")
                            if gap_type in gaps_dict:
                                gaps_dict[gap_type].append(desc)
                            elif gap_type == "gap":
                                gaps_dict["gaps"].append(desc)
                            elif gap_type == "opportunity":
                                gaps_dict["opportunities"].append(desc)
                        st.session_state.gaps = gaps_dict

                    master_path = os.path.join(DATA_DIR, f"{tag}_master_summary.txt")
                    if os.path.exists(master_path):
                        with open(master_path, "r") as f:
                            st.session_state.master_summary = f.read()
                    else:
                        st.session_state.master_summary = ""

                    st.session_state.search_done = True
                    st.success(f"Loaded: {tag.replace('_', ' ').title()}")
                    st.rerun()
