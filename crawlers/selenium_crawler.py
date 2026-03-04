import time
import random
import re
import json
import pandas as pd
from bs4 import BeautifulSoup
from seleniumbase import SB
from config.settings import (
    SELENIUM_HEADLESS,
    SELENIUM_TIMEOUT,
    REQUEST_DELAY_MIN,
    REQUEST_DELAY_MAX,
)
from utils.geo_utils import get_city_bounds, split_into_grid


class SeleniumCrawler:
    """
    Free crawler using SeleniumBase with undetected Chrome mode.
    Scrapes Google Maps directly for business listings and reviews.
    No API key needed.
    """

    def __init__(self, headless=None):
        self.headless = headless if headless is not None else SELENIUM_HEADLESS

    def search_businesses(self, business_type, city, progress_callback=None):
        """
        Search for all businesses of a given type in a city.
        Uses grid splitting and multiple searches for full coverage.
        Returns a list of unique business dicts.
        """
        bounds = get_city_bounds(city)
        if not bounds:
            search_query = f"{business_type} in {city}"
            return self._single_search(search_query, progress_callback)

        grid_points = split_into_grid(bounds, cell_size_km=3.0)

        if len(grid_points) > 50:
            grid_points = split_into_grid(bounds, cell_size_km=5.0)

        all_businesses = {}
        total_cells = len(grid_points)

        with SB(uc=True, headless=self.headless) as sb:
            for idx, (lat, lng) in enumerate(grid_points):
                if progress_callback:
                    progress_callback(idx + 1, total_cells)

                search_url = (
                    f"https://www.google.com/maps/search/"
                    f"{business_type.replace(' ', '+')}/"
                    f"@{lat},{lng},14z"
                )

                try:
                    sb.open(search_url)
                    self._random_delay()
                    self._scroll_results_panel(sb)
                    businesses = self._extract_listings(sb)

                    for biz in businesses:
                        key = biz.get("name", "") + biz.get("address", "")
                        if key and key not in all_businesses:
                            all_businesses[key] = biz

                except Exception as e:
                    print(f"Error at grid ({lat}, {lng}): {e}")
                    continue

        return list(all_businesses.values())

    def get_reviews(self, place_url, max_reviews=50, progress_callback=None):
        """
        Scrape reviews for a single business from its Google Maps URL.
        Returns a list of review dicts.
        """
        reviews = []

        with SB(uc=True, headless=self.headless) as sb:
            try:
                sb.open(place_url)
                self._random_delay()

                try:
                    sb.click('button[aria-label*="Reviews"]', timeout=10)
                    self._random_delay()
                except Exception:
                    try:
                        sb.click('div[role="tab"]:nth-child(2)', timeout=5)
                        self._random_delay()
                    except Exception:
                        pass

                scroll_count = max_reviews // 5
                for i in range(scroll_count):
                    if progress_callback:
                        progress_callback(i + 1, scroll_count)

                    try:
                        sb.execute_script(
                            """
                            var panel = document.querySelector(
                                'div[role="main"] div.m6QErb.DxyBCb'
                            );
                            if (panel) {
                                panel.scrollBy(0, 1000);
                            }
                            """
                        )
                        time.sleep(0.5 + random.random())
                    except Exception:
                        break

                try:
                    sb.execute_script(
                        """
                        var buttons = document.querySelectorAll(
                            'button.w8nwRe.kyuRq'
                        );
                        buttons.forEach(function(btn) { btn.click(); });
                        """
                    )
                    time.sleep(1)
                except Exception:
                    pass

                page_source = sb.get_page_source()
                reviews = self._extract_reviews(page_source)

            except Exception as e:
                print(f"Error scraping reviews: {e}")

        return reviews[:max_reviews]

    def get_business_details(self, place_url):
        """Scrape detailed info for a single business."""
        details = {}

        with SB(uc=True, headless=self.headless) as sb:
            try:
                sb.open(place_url)
                self._random_delay()

                page_source = sb.get_page_source()
                soup = BeautifulSoup(page_source, "lxml")

                name_el = soup.select_one("h1.DUwDvf")
                if name_el:
                    details["name"] = name_el.get_text(strip=True)

                rating_el = soup.select_one("div.F7nice span[aria-hidden]")
                if rating_el:
                    try:
                        details["rating"] = float(rating_el.get_text(strip=True))
                    except ValueError:
                        pass

                review_count_el = soup.select_one(
                    'div.F7nice span[aria-label*="reviews"]'
                )
                if review_count_el:
                    text = review_count_el.get_text(strip=True)
                    numbers = re.findall(r"[\d,]+", text)
                    if numbers:
                        details["total_reviews"] = int(
                            numbers[0].replace(",", "")
                        )

                address_el = soup.select_one(
                    'button[data-item-id="address"] div.fontBodyMedium'
                )
                if address_el:
                    details["address"] = address_el.get_text(strip=True)

                phone_el = soup.select_one(
                    'button[data-item-id*="phone"] div.fontBodyMedium'
                )
                if phone_el:
                    details["phone"] = phone_el.get_text(strip=True)

                website_el = soup.select_one(
                    'a[data-item-id="authority"]'
                )
                if website_el:
                    details["website"] = website_el.get("href", "")

                details["url"] = place_url

            except Exception as e:
                print(f"Error fetching details: {e}")

        return details

    def _single_search(self, query, progress_callback=None):
        """Fallback: single search when bounds are not available."""
        businesses = []
        search_url = (
            f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
        )

        with SB(uc=True, headless=self.headless) as sb:
            try:
                sb.open(search_url)
                self._random_delay()
                self._scroll_results_panel(sb)
                businesses = self._extract_listings(sb)

                if progress_callback:
                    progress_callback(1, 1)

            except Exception as e:
                print(f"Error in single search: {e}")

        return businesses

    def _scroll_results_panel(self, sb, max_scrolls=15):
        """Scroll the results panel to load more listings."""
        for _ in range(max_scrolls):
            try:
                end_reached = sb.execute_script(
                    """
                    var feed = document.querySelector(
                        'div[role="feed"]'
                    );
                    if (feed) {
                        feed.scrollBy(0, 2000);
                        var endMsg = feed.querySelector(
                            'span.HlvSq'
                        );
                        return endMsg !== null;
                    }
                    return true;
                    """
                )
                time.sleep(1 + random.random())
                if end_reached:
                    break
            except Exception:
                break

    def _extract_listings(self, sb):
        """Extract business listings from the current results page."""
        businesses = []
        try:
            page_source = sb.get_page_source()
            soup = BeautifulSoup(page_source, "lxml")

            results = soup.select("div.Nv2PK")

            for item in results:
                biz = {}

                name_el = item.select_one("div.qBF1Pd")
                if name_el:
                    biz["name"] = name_el.get_text(strip=True)

                rating_el = item.select_one("span.MW4etd")
                if rating_el:
                    try:
                        biz["rating"] = float(rating_el.get_text(strip=True))
                    except ValueError:
                        biz["rating"] = None
                else:
                    biz["rating"] = None

                review_el = item.select_one("span.UY7F9")
                if review_el:
                    text = review_el.get_text(strip=True)
                    numbers = re.findall(r"[\d,]+", text)
                    if numbers:
                        biz["total_reviews"] = int(
                            numbers[0].replace(",", "")
                        )
                    else:
                        biz["total_reviews"] = 0
                else:
                    biz["total_reviews"] = 0

                addr_el = item.select_one("div.W4Efsd:nth-child(3)")
                if addr_el:
                    spans = addr_el.select("span")
                    if spans:
                        addr_parts = [
                            s.get_text(strip=True)
                            for s in spans
                            if s.get_text(strip=True)
                            and s.get_text(strip=True) != "\u00b7"
                        ]
                        biz["address"] = ", ".join(addr_parts)
                    else:
                        biz["address"] = ""
                else:
                    biz["address"] = ""

                link_el = item.select_one("a.hfpxzc")
                if link_el:
                    biz["url"] = link_el.get("href", "")
                    biz["place_id"] = self._extract_place_id(biz["url"])
                else:
                    biz["url"] = ""
                    biz["place_id"] = ""

                lat_lng = self._extract_lat_lng(biz.get("url", ""))
                biz["lat"] = lat_lng[0]
                biz["lng"] = lat_lng[1]

                if biz.get("name"):
                    businesses.append(biz)

        except Exception as e:
            print(f"Error extracting listings: {e}")

        return businesses

    def _extract_reviews(self, page_source):
        """Extract reviews from a business detail page."""
        reviews = []
        soup = BeautifulSoup(page_source, "lxml")

        review_elements = soup.select("div.jftiEf")

        for rev_el in review_elements:
            review = {}

            author_el = rev_el.select_one("div.d4r55")
            if author_el:
                review["author"] = author_el.get_text(strip=True)

            rating_el = rev_el.select_one('span.kvMYJc[aria-label]')
            if rating_el:
                label = rating_el.get("aria-label", "")
                numbers = re.findall(r"[\d.]+", label)
                if numbers:
                    try:
                        review["rating"] = float(numbers[0])
                    except ValueError:
                        review["rating"] = None

            time_el = rev_el.select_one("span.rsqaWe")
            if time_el:
                review["time"] = time_el.get_text(strip=True)

            text_el = rev_el.select_one("span.wiI7pd")
            if text_el:
                review["text"] = text_el.get_text(strip=True)
            else:
                review["text"] = ""

            if review.get("author"):
                reviews.append(review)

        return reviews

    def _extract_place_id(self, url):
        """Try to extract place_id from a Google Maps URL."""
        match = re.search(r"0x[\da-fA-F]+:0x[\da-fA-F]+", url)
        return match.group(0) if match else ""

    def _extract_lat_lng(self, url):
        """Extract latitude and longitude from a Google Maps URL."""
        match = re.search(r"@(-?[\d.]+),(-?[\d.]+)", url)
        if match:
            try:
                return (float(match.group(1)), float(match.group(2)))
            except ValueError:
                pass
        return (None, None)

    def _random_delay(self):
        """Wait a random amount of time to avoid detection."""
        delay = random.uniform(REQUEST_DELAY_MIN, REQUEST_DELAY_MAX)
        time.sleep(delay)
