import time
import random
import re
from bs4 import BeautifulSoup
from seleniumbase import SB
from config.settings import (
    SELENIUM_HEADLESS,
    REQUEST_DELAY_MIN,
    REQUEST_DELAY_MAX,
)
from utils.geo_utils import haversine_distance


NEARBY_CATEGORIES = {
    "parking": ["parking", "car park", "parking lot"],
    "public_transport": ["bus stop", "train station", "metro station", "tram stop"],
    "schools": ["school", "college", "university"],
    "main_road": ["main road", "high street", "highway"],
    "shopping": ["shopping centre", "shopping mall", "market"],
    "hospital": ["hospital", "clinic", "medical centre"],
    "park": ["park", "garden", "playground"],
    "tourist_attraction": ["museum", "gallery", "landmark", "monument"],
}

SEARCH_RADIUS_KM = 0.5


class NearbyCollector:
    """
    Collects nearby context for each business location.
    Uses Selenium to search Google Maps for nearby amenities.
    Produces binary and count features for ML.
    """

    def __init__(self, headless=None):
        self.headless = headless if headless is not None else SELENIUM_HEADLESS

    def collect_nearby(self, business_lat, business_lng, progress_callback=None):
        """
        For a given business location, find nearby amenities.
        Returns a dict with category counts and closest distances.
        """
        results = {}
        categories = list(NEARBY_CATEGORIES.keys())
        total = len(categories)

        with SB(uc=True, headless=self.headless) as sb:
            for idx, category in enumerate(categories):
                if progress_callback:
                    progress_callback(idx + 1, total)

                search_terms = NEARBY_CATEGORIES[category]
                category_results = []

                for term in search_terms[:1]:
                    search_url = (
                        f"https://www.google.com/maps/search/"
                        f"{term.replace(' ', '+')}/"
                        f"@{business_lat},{business_lng},16z"
                    )

                    try:
                        sb.open(search_url)
                        time.sleep(2 + random.random())

                        page_source = sb.get_page_source()
                        soup = BeautifulSoup(page_source, "lxml")

                        listings = soup.select("div.Nv2PK")
                        for item in listings:
                            name_el = item.select_one("div.qBF1Pd")
                            link_el = item.select_one("a.hfpxzc")

                            if name_el and link_el:
                                url = link_el.get("href", "")
                                lat_lng = self._extract_lat_lng(url)

                                if lat_lng[0] and lat_lng[1]:
                                    dist = haversine_distance(
                                        business_lat,
                                        business_lng,
                                        lat_lng[0],
                                        lat_lng[1],
                                    )

                                    if dist <= SEARCH_RADIUS_KM:
                                        category_results.append(
                                            {
                                                "name": name_el.get_text(
                                                    strip=True
                                                ),
                                                "distance_km": round(dist, 3),
                                                "lat": lat_lng[0],
                                                "lng": lat_lng[1],
                                            }
                                        )

                    except Exception as e:
                        print(f"Error searching {term}: {e}")
                        continue

                results[category] = {
                    "count": len(category_results),
                    "has_nearby": len(category_results) > 0,
                    "closest_distance_km": (
                        min(r["distance_km"] for r in category_results)
                        if category_results
                        else None
                    ),
                    "places": category_results,
                }

                time.sleep(random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX))

        return results

    def collect_bulk(self, businesses, progress_callback=None):
        """
        Collect nearby context for a list of businesses.
        Each business dict must have 'lat' and 'lng' keys.
        Returns the same list with a 'nearby' key added.
        """
        total = len(businesses)
        for idx, biz in enumerate(businesses):
            if progress_callback:
                progress_callback(idx + 1, total)

            lat = biz.get("lat")
            lng = biz.get("lng")

            if lat and lng:
                biz["nearby"] = self.collect_nearby(lat, lng)
            else:
                biz["nearby"] = {}

        return businesses

    def to_features(self, nearby_data):
        """
        Convert nearby context data into flat binary/numeric features
        suitable for ML models.
        """
        features = {}

        for category in NEARBY_CATEGORIES:
            cat_data = nearby_data.get(category, {})
            features[f"has_{category}"] = 1 if cat_data.get("has_nearby") else 0
            features[f"{category}_count"] = cat_data.get("count", 0)
            features[f"{category}_closest_km"] = cat_data.get(
                "closest_distance_km"
            )

        return features

    def _extract_lat_lng(self, url):
        """Extract latitude and longitude from a Google Maps URL."""
        match = re.search(r"@(-?[\d.]+),(-?[\d.]+)", url)
        if match:
            try:
                return (float(match.group(1)), float(match.group(2)))
            except ValueError:
                pass
        return (None, None)
