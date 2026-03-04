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
        all_businesses = {}

        bounds = get_city_bounds(city)

        if bounds:
            grid_points = split_into_grid(bounds, cell_size_km=3.0)
            if len(grid_points) > 50:
                grid_points = split_into_grid(bounds, cell_size_km=5.0)
        else:
            grid_points = []

        with SB(uc=True, headless=self.headless) as sb:
            if not grid_points:
                search_url = (
                    "https://www.google.com/maps/search/"
                    f"{business_type.replace(' ', '+')}+in+{city.replace(' ', '+')}"
                )
                print(f"[MAPA] Searching: {search_url}")

                try:
                    sb.open(search_url)
                    time.sleep(5)
                    self._handle_consent(sb)
                    time.sleep(3)
                    self._scroll_results_panel(sb)
                    businesses = self._extract_listings(sb)
                    print(f"[MAPA] Found {len(businesses)} from single search")

                    for biz in businesses:
                        key = biz.get("name", "") + biz.get("address", "")
                        if key and key not in all_businesses:
                            all_businesses[key] = biz

                    if progress_callback:
                        progress_callback(1, 1)

                except Exception as e:
                    print(f"[MAPA] Error in search: {e}")
            else:
                total_cells = len(grid_points)
                for idx, (lat, lng) in enumerate(grid_points):
                    if progress_callback:
                        progress_callback(idx + 1, total_cells)

                    search_url = (
                        "https://www.google.com/maps/search/"
                        f"{business_type.replace(' ', '+')}/"
                        f"@{lat},{lng},14z"
                    )
                    print(f"[MAPA] Grid {idx+1}/{total_cells}: {search_url}")

                    try:
                        sb.open(search_url)
                        time.sleep(4)

                        if idx == 0:
                            self._handle_consent(sb)
                            time.sleep(2)

                        self._scroll_results_panel(sb)
                        businesses = self._extract_listings(sb)
                        print(f"[MAPA] Grid {idx+1}: found {len(businesses)}")

                        for biz in businesses:
                            key = biz.get("name", "") + biz.get("address", "")
                            if key and key not in all_businesses:
                                all_businesses[key] = biz

                    except Exception as e:
                        print(f"[MAPA] Error at grid ({lat}, {lng}): {e}")
                        continue

                    self._random_delay()

        print(f"[MAPA] Total unique businesses: {len(all_businesses)}")
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
                time.sleep(5)
                self._handle_consent(sb)

                try:
                    sb.click('button[aria-label*="Reviews"]', timeout=10)
                    time.sleep(3)
                except Exception:
                    try:
                        sb.click('div[role="tab"]:nth-child(2)', timeout=5)
                        time.sleep(3)
                    except Exception:
                        pass

                scroll_count = max_reviews // 5
                for i in range(scroll_count):
                    if progress_callback:
                        progress_callback(i + 1, scroll_count)

                    try:
                        sb.execute_script(
                            """
                            var panels = document.querySelectorAll('div.m6QErb.DxyBCb');
                            var panel = panels[panels.length - 1];
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
                        document.querySelectorAll('button.w8nwRe.kyuRq').forEach(
                            function(btn) { btn.click(); }
                        );
                        """
                    )
                    time.sleep(1)
                except Exception:
                    pass

                page_source = sb.get_page_source()
                reviews = self._extract_reviews(page_source)
                print(f"[MAPA] Extracted {len(reviews)} reviews")

            except Exception as e:
                print(f"[MAPA] Error scraping reviews: {e}")

        return reviews[:max_reviews]

    def get_business_details(self, place_url):
        """Scrape detailed info for a single business."""
        details = {}

        with SB(uc=True, headless=self.headless) as sb:
            try:
                sb.open(place_url)
                time.sleep(5)
                self._handle_consent(sb)

                page_source = sb.get_page_source()
                soup = BeautifulSoup(page_source, "lxml")

                name_el = soup.select_one("h1.DUwDvf") or soup.select_one("h1")
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
                print(f"[MAPA] Error fetching details: {e}")

        return details

    def _handle_consent(self, sb):
        """Handle Google's cookie consent popup if it appears."""
        try:
            sb.execute_script(
                """
                var buttons = document.querySelectorAll('button');
                for (var i = 0; i < buttons.length; i++) {
                    var text = buttons[i].textContent.toLowerCase();
                    if (text.includes('reject all') || text.includes('reject')
                        || text.includes('decline')) {
                        buttons[i].click();
                        return true;
                    }
                }
                var accept = document.querySelector('button[aria-label*="Accept"]');
                if (accept) { accept.click(); return true; }
                var forms = document.querySelectorAll('form');
                for (var j = 0; j < forms.length; j++) {
                    var btns = forms[j].querySelectorAll('button');
                    if (btns.length >= 2) {
                        btns[0].click();
                        return true;
                    }
                }
                return false;
                """
            )
            time.sleep(2)
        except Exception:
            pass

    def _scroll_results_panel(self, sb, max_scrolls=15):
        """Scroll the results panel to load more listings."""
        for i in range(max_scrolls):
            try:
                result = sb.execute_script(
                    """
                    var feed = document.querySelector('div[role="feed"]');
                    if (!feed) {
                        var panels = document.querySelectorAll('div.m6QErb');
                        for (var i = 0; i < panels.length; i++) {
                            if (panels[i].scrollHeight > panels[i].clientHeight) {
                                feed = panels[i];
                                break;
                            }
                        }
                    }
                    if (feed) {
                        var oldScroll = feed.scrollTop;
                        feed.scrollBy(0, 2000);
                        var endMsg = feed.querySelector('span.HlvSq')
                                  || feed.querySelector('p.fontBodyMedium span');
                        var atBottom = (feed.scrollTop === oldScroll);
                        return {'found': true, 'end': endMsg !== null || atBottom};
                    }
                    return {'found': false, 'end': true};
                    """
                )
                time.sleep(1.5 + random.random())

                if result and result.get("end"):
                    print(f"[MAPA] Scroll ended at iteration {i+1}")
                    break
                if result and not result.get("found"):
                    print("[MAPA] No scrollable panel found")
                    break
            except Exception as e:
                print(f"[MAPA] Scroll error: {e}")
                break

    def _extract_listings(self, sb):
        """Extract business listings from the current results page."""
        businesses = []
        try:
            page_source = sb.get_page_source()
            soup = BeautifulSoup(page_source, "lxml")

            results = soup.select("div.Nv2PK")

            if not results:
                results = soup.select('a[href*="/maps/place/"]')
                print(f"[MAPA] Fallback selector found {len(results)} links")

                for link in results:
                    biz = {}
                    href = link.get("href", "")
                    label = link.get("aria-label", "")

                    if label:
                        biz["name"] = label
                    else:
                        continue

                    biz["url"] = href
                    biz["place_id"] = self._extract_place_id(href)
                    lat_lng = self._extract_lat_lng(href)
                    biz["lat"] = lat_lng[0]
                    biz["lng"] = lat_lng[1]
                    biz["rating"] = None
                    biz["total_reviews"] = 0
                    biz["address"] = ""

                    rating_match = re.search(r"(\d\.\d)\s+stars?", label, re.IGNORECASE)
                    if rating_match:
                        biz["rating"] = float(rating_match.group(1))

                    businesses.append(biz)

                if businesses:
                    return businesses

            print(f"[MAPA] Primary selector found {len(results)} items")

            for item in results:
                biz = {}

                name_el = item.select_one("div.qBF1Pd")
                if not name_el:
                    name_el = item.select_one("span.fontHeadlineSmall")
                if not name_el:
                    link = item.select_one("a[aria-label]")
                    if link:
                        biz["name"] = link.get("aria-label", "")
                if name_el:
                    biz["name"] = name_el.get_text(strip=True)

                if not biz.get("name"):
                    continue

                rating_el = item.select_one("span.MW4etd")
                if not rating_el:
                    rating_el = item.select_one("span.fontBodyMedium span[aria-hidden]")
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
                    all_text = item.get_text()
                    review_match = re.search(r"\((\d[\d,]*)\)", all_text)
                    if review_match:
                        biz["total_reviews"] = int(
                            review_match.group(1).replace(",", "")
                        )
                    else:
                        biz["total_reviews"] = 0

                biz["address"] = ""
                addr_parts = []
                info_divs = item.select("div.W4Efsd")
                for div in info_divs:
                    spans = div.select("span")
                    for s in spans:
                        text = s.get_text(strip=True)
                        if text and text != "\u00b7" and not re.match(r"^\d\.\d$", text):
                            addr_parts.append(text)
                if addr_parts:
                    biz["address"] = ", ".join(addr_parts[:3])

                link_el = item.select_one("a.hfpxzc")
                if not link_el:
                    link_el = item.select_one("a[href*='/maps/place/']")
                if link_el:
                    biz["url"] = link_el.get("href", "")
                    biz["place_id"] = self._extract_place_id(biz["url"])
                else:
                    biz["url"] = ""
                    biz["place_id"] = ""

                lat_lng = self._extract_lat_lng(biz.get("url", ""))
                biz["lat"] = lat_lng[0]
                biz["lng"] = lat_lng[1]

                businesses.append(biz)

        except Exception as e:
            print(f"[MAPA] Error extracting listings: {e}")

        return businesses

    def _extract_reviews(self, page_source):
        """Extract reviews from a business detail page."""
        reviews = []
        soup = BeautifulSoup(page_source, "lxml")

        review_elements = soup.select("div.jftiEf")
        if not review_elements:
            review_elements = soup.select("div[data-review-id]")

        for rev_el in review_elements:
            review = {}

            author_el = rev_el.select_one("div.d4r55")
            if not author_el:
                author_el = rev_el.select_one("button[aria-label] div")
            if author_el:
                review["author"] = author_el.get_text(strip=True)

            rating_el = rev_el.select_one('span.kvMYJc[aria-label]')
            if not rating_el:
                rating_el = rev_el.select_one('span[role="img"][aria-label]')
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
            if not text_el:
                text_el = rev_el.select_one("div.MyEned span")
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
