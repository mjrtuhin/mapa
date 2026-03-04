import time
import googlemaps
import pandas as pd
from config.settings import GOOGLE_MAPS_API_KEY, REQUEST_DELAY_MIN
from utils.geo_utils import get_city_bounds, split_into_grid


class GoogleAPICrawler:
    """
    Crawler that uses the official Google Places API.
    Requires a valid GOOGLE_MAPS_API_KEY in .env.
    Limited to 5 reviews per business (API restriction).
    """

    def __init__(self):
        if not GOOGLE_MAPS_API_KEY:
            raise ValueError(
                "Google Maps API key not found. "
                "Add GOOGLE_MAPS_API_KEY to your .env file."
            )
        self.client = googlemaps.Client(key=GOOGLE_MAPS_API_KEY)

    def search_businesses(self, business_type, city, progress_callback=None):
        """
        Search for all businesses of a given type in a city.
        Uses grid splitting to overcome the 60-result limit.
        Returns a list of unique business dicts.
        """
        bounds = get_city_bounds(city)
        if not bounds:
            return []

        grid_points = split_into_grid(bounds, cell_size_km=2.0)
        all_businesses = {}
        total_cells = len(grid_points)

        for idx, (lat, lng) in enumerate(grid_points):
            if progress_callback:
                progress_callback(idx + 1, total_cells)

            try:
                results = self.client.places_nearby(
                    location=(lat, lng),
                    radius=1500,
                    keyword=business_type,
                    type=self._map_business_type(business_type),
                )

                self._process_results(results, all_businesses)

                while results.get("next_page_token"):
                    time.sleep(2)
                    results = self.client.places_nearby(
                        page_token=results["next_page_token"]
                    )
                    self._process_results(results, all_businesses)

            except Exception as e:
                print(f"Error at grid ({lat}, {lng}): {e}")
                continue

            time.sleep(REQUEST_DELAY_MIN)

        return list(all_businesses.values())

    def get_place_details(self, place_id):
        """Get detailed info for a single place including reviews (max 5)."""
        try:
            result = self.client.place(
                place_id,
                fields=[
                    "name",
                    "formatted_address",
                    "geometry",
                    "rating",
                    "user_ratings_total",
                    "reviews",
                    "opening_hours",
                    "website",
                    "formatted_phone_number",
                    "price_level",
                    "types",
                    "business_status",
                ],
            )
            return result.get("result", {})
        except Exception as e:
            print(f"Error fetching details for {place_id}: {e}")
            return {}

    def _process_results(self, results, business_dict):
        """Deduplicate and store results by place_id."""
        for place in results.get("results", []):
            pid = place.get("place_id")
            if pid and pid not in business_dict:
                business_dict[pid] = {
                    "place_id": pid,
                    "name": place.get("name", ""),
                    "address": place.get("vicinity", ""),
                    "lat": place.get("geometry", {})
                    .get("location", {})
                    .get("lat"),
                    "lng": place.get("geometry", {})
                    .get("location", {})
                    .get("lng"),
                    "rating": place.get("rating"),
                    "total_reviews": place.get("user_ratings_total", 0),
                    "types": place.get("types", []),
                    "business_status": place.get("business_status", ""),
                    "price_level": place.get("price_level"),
                }

    def _map_business_type(self, query):
        """Map common business queries to Google Places types."""
        type_mapping = {
            "restaurant": "restaurant",
            "grocery": "grocery_or_supermarket",
            "clothing": "clothing_store",
            "cafe": "cafe",
            "gym": "gym",
            "pharmacy": "pharmacy",
            "bakery": "bakery",
            "bank": "bank",
            "salon": "beauty_salon",
            "barber": "hair_care",
            "dentist": "dentist",
            "doctor": "doctor",
            "hotel": "lodging",
            "bar": "bar",
            "school": "school",
        }

        query_lower = query.lower()
        for keyword, gtype in type_mapping.items():
            if keyword in query_lower:
                return gtype
        return ""
