import math
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut


def geocode_city(city_name):
    """Convert a city name to latitude and longitude coordinates."""
    geolocator = Nominatim(user_agent="mapa-analytics")
    try:
        location = geolocator.geocode(city_name, timeout=10)
        if location:
            return {
                "lat": location.latitude,
                "lng": location.longitude,
                "display_name": location.address,
            }
        return None
    except GeocoderTimedOut:
        return None


def get_city_bounds(city_name):
    """Get the bounding box of a city for grid splitting."""
    geolocator = Nominatim(user_agent="mapa-analytics")
    try:
        location = geolocator.geocode(city_name, timeout=10, exactly_one=True)
        if location and hasattr(location, "raw"):
            bbox = location.raw.get("boundingbox", [])
            if len(bbox) == 4:
                return {
                    "south": float(bbox[0]),
                    "north": float(bbox[1]),
                    "west": float(bbox[2]),
                    "east": float(bbox[3]),
                }
        return None
    except GeocoderTimedOut:
        return None


def split_into_grid(bounds, cell_size_km=2.0):
    """
    Split a bounding box into grid cells for full area coverage.
    Each cell is roughly cell_size_km x cell_size_km.
    Returns a list of (lat, lng) center points for each cell.
    """
    if not bounds:
        return []

    lat_degree_km = 111.0
    lng_degree_km = 111.0 * math.cos(
        math.radians((bounds["north"] + bounds["south"]) / 2)
    )

    lat_step = cell_size_km / lat_degree_km
    lng_step = cell_size_km / lng_degree_km

    grid_points = []
    current_lat = bounds["south"] + lat_step / 2

    while current_lat < bounds["north"]:
        current_lng = bounds["west"] + lng_step / 2
        while current_lng < bounds["east"]:
            grid_points.append((round(current_lat, 6), round(current_lng, 6)))
            current_lng += lng_step
        current_lat += lat_step

    return grid_points


def haversine_distance(lat1, lng1, lat2, lng2):
    """Calculate the distance in km between two lat/lng points."""
    R = 6371

    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c
