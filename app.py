import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import json
import os
import time

from config.settings import DATA_DIR, GOOGLE_MAPS_API_KEY, GROQ_API_KEY

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


def run_search(business_type, area, data_source, review_limit, collect_nearby_flag):
    """Run the full search, review collection, and analysis pipeline."""

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

    if not businesses:
        status.update(label="No businesses found.", state="error")
        return

    status.write("Step 2/4: Collecting reviews...")
    progress_bar_reviews = st.progress(0)
    all_reviews = {}

    if data_source == "Selenium (Free)":
        from crawlers.selenium_crawler import SeleniumCrawler
        review_crawler = SeleniumCrawler()

        for idx, biz in enumerate(businesses[:20]):
            progress_bar_reviews.progress((idx + 1) / min(len(businesses), 20))
            status.write(f"Getting reviews for: {biz.get('name', 'Unknown')}...")

            url = biz.get("url", "")
            if url:
                reviews = review_crawler.get_reviews(url, max_reviews=review_limit)
                all_reviews[biz["name"]] = reviews
    else:
        from crawlers.google_api_crawler import GoogleAPICrawler
        api_crawler = GoogleAPICrawler()

        for idx, biz in enumerate(businesses[:20]):
            progress_bar_reviews.progress((idx + 1) / min(len(businesses), 20))
            pid = biz.get("place_id", "")
            if pid:
                details = api_crawler.get_place_details(pid)
                all_reviews[biz["name"]] = details.get("reviews", [])

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

        status.write("Detecting market gaps...")
        gaps = analyzer.detect_market_gaps(all_reviews, business_type, area)
        st.session_state.gaps = gaps
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
            if lat and lng:
                nearby_results[biz["name"]] = collector.collect_nearby(lat, lng)

        st.session_state.nearby_data = nearby_results
        progress_bar_nearby.progress(1.0)
    else:
        status.write("Step 4/4: Skipping nearby context (not selected).")

    save_path = os.path.join(DATA_DIR, f"{business_type}_{area}.json")
    save_data = {
        "businesses": businesses,
        "reviews": {k: v for k, v in all_reviews.items()},
        "analysis": st.session_state.analysis,
        "gaps": st.session_state.gaps,
        "nearby": st.session_state.nearby_data,
    }
    with open(save_path, "w") as f:
        json.dump(save_data, f, indent=2, default=str)

    st.session_state.search_done = True
    status.update(label="Analysis complete!", state="complete")


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

tab_overview, tab_reviews, tab_gaps, tab_nearby, tab_predict = st.tabs(
    ["Overview", "Reviews Analysis", "Market Gaps", "Nearby Context", "Success Predictor"]
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

        high_rated = len([r for r in ratings if r >= 4.1])
        saturation = f"{round(high_rated / len(ratings) * 100)}%" if ratings else "N/A"

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Businesses Found", len(businesses))
        with col2:
            st.metric("Avg Rating", f"{avg_rating} / 5")
        with col3:
            st.metric("Total Reviews", f"{total_reviews_count:,}")
        with col4:
            st.metric("Above 4.1 Stars", saturation)

        st.markdown("---")

        col_map, col_table = st.columns([3, 2])

        with col_map:
            st.markdown("**Map View**")
            valid_locations = [
                b for b in businesses if b.get("lat") and b.get("lng")
            ]

            if valid_locations:
                center_lat = sum(b["lat"] for b in valid_locations) / len(valid_locations)
                center_lng = sum(b["lng"] for b in valid_locations) / len(valid_locations)

                m = folium.Map(location=[center_lat, center_lng], zoom_start=13)

                for biz in valid_locations:
                    color = "green" if biz.get("rating", 0) >= 4.1 else "orange" if biz.get("rating", 0) >= 3.5 else "red"
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
    st.caption("ML-powered prediction: will a new business succeed in this area?")

    st.info(
        "This feature uses a trained model from Phase 2 (Jupyter Notebook). "
        "Once the model is trained on collected data, it will be integrated here."
    )

    st.markdown("**How it will work:**")
    st.markdown(
        "1. Collect data for businesses in a city using the Search tab\n"
        "2. Train the ML model in the Jupyter notebook (Phase 2)\n"
        "3. Come back here, enter features for a hypothetical new business\n"
        "4. The model predicts whether it would achieve 4.1+ stars"
    )

    st.markdown("---")
    st.markdown("**Preview: Feature Input (coming soon)**")

    col1, col2 = st.columns(2)
    with col1:
        st.toggle("Has Parking Nearby", disabled=True)
        st.toggle("Near Public Transport", disabled=True)
        st.toggle("Near School/University", disabled=True)
        st.toggle("On Main Road", disabled=True)
    with col2:
        st.toggle("Near Shopping Area", disabled=True)
        st.toggle("Near Hospital", disabled=True)
        st.toggle("Near Park", disabled=True)
        st.toggle("Near Tourist Attraction", disabled=True)
