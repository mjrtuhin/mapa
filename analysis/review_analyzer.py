import json
from groq import Groq
from config.settings import GROQ_API_KEY


class ReviewAnalyzer:
    """
    Analyzes business reviews using Groq API (free LLM inference).
    Performs sentiment analysis, topic extraction, and market gap detection.
    """

    def __init__(self):
        if not GROQ_API_KEY:
            raise ValueError(
                "Groq API key not found. "
                "Add GROQ_API_KEY to your .env file. "
                "Get a free key at https://console.groq.com"
            )
        self.client = Groq(api_key=GROQ_API_KEY)
        self.model = "llama-3.3-70b-versatile"

    def analyze_reviews(self, reviews, business_type):
        """
        Analyze a batch of reviews for a single business.
        Returns sentiment scores and key topics.
        """
        if not reviews:
            return {"sentiment": {}, "topics": [], "summary": "No reviews available."}

        review_texts = []
        for r in reviews[:30]:
            text = r.get("text", "")
            rating = r.get("rating", "")
            if text:
                review_texts.append(f"[Rating: {rating}] {text}")

        combined = "\n---\n".join(review_texts)

        prompt = f"""Analyze these {business_type} reviews. Return a JSON object with exactly these keys:

1. "sentiment": an object with keys "positive_pct", "negative_pct", "neutral_pct" (numbers that add to 100)
2. "top_positives": list of 5 most praised aspects (strings)
3. "top_negatives": list of 5 most criticized aspects (strings)
4. "topics": list of 5 main topics mentioned across reviews (strings)
5. "summary": a 2-3 sentence summary of the overall sentiment

Reviews:
{combined}

Return ONLY valid JSON, no extra text."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=1000,
            )

            content = response.choices[0].message.content.strip()

            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            return json.loads(content)

        except json.JSONDecodeError:
            return {
                "sentiment": {
                    "positive_pct": 0,
                    "negative_pct": 0,
                    "neutral_pct": 0,
                },
                "top_positives": [],
                "top_negatives": [],
                "topics": [],
                "summary": "Failed to parse analysis results.",
            }
        except Exception as e:
            return {
                "sentiment": {
                    "positive_pct": 0,
                    "negative_pct": 0,
                    "neutral_pct": 0,
                },
                "top_positives": [],
                "top_negatives": [],
                "topics": [],
                "summary": f"Analysis error: {str(e)}",
            }

    def detect_market_gaps(self, all_reviews_by_business, business_type, area):
        """
        Analyze reviews across ALL businesses in an area to find market gaps.
        all_reviews_by_business: dict of {business_name: [reviews]}
        Returns gap analysis and saturation points.
        """
        summary_parts = []

        for biz_name, reviews in list(all_reviews_by_business.items())[:20]:
            negative_reviews = [
                r.get("text", "")
                for r in reviews
                if r.get("rating") and r.get("rating") <= 3
            ]
            if negative_reviews:
                combined = " | ".join(negative_reviews[:5])
                summary_parts.append(f"[{biz_name}] Complaints: {combined}")

        if not summary_parts:
            return {
                "gaps": [],
                "saturated": [],
                "opportunities": [],
                "summary": "Not enough negative reviews to identify clear gaps.",
            }

        combined_complaints = "\n".join(summary_parts)

        prompt = f"""You are a market research analyst. Analyze these customer complaints from {business_type} businesses in {area}.

Identify market gaps (unmet needs) and saturation points (too many similar offerings).

Complaints by business:
{combined_complaints}

Return a JSON object with exactly these keys:
1. "gaps": list of 5 market gaps where customer needs are not being met (strings)
2. "saturated": list of 3 areas where the market is oversaturated (strings)
3. "opportunities": list of 5 specific business opportunities based on the gaps (strings)
4. "summary": a 3-4 sentence summary of the market landscape

Return ONLY valid JSON, no extra text."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.4,
                max_tokens=1500,
            )

            content = response.choices[0].message.content.strip()

            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            return json.loads(content)

        except Exception as e:
            return {
                "gaps": [],
                "saturated": [],
                "opportunities": [],
                "summary": f"Analysis error: {str(e)}",
            }

    def analyze_single_review(self, review_text):
        """Quick sentiment analysis for a single review."""
        if not review_text:
            return {"sentiment": "neutral", "score": 0.5, "topics": []}

        prompt = f"""Analyze this review. Return JSON with:
1. "sentiment": "positive", "negative", or "neutral"
2. "score": float 0-1 (0=very negative, 1=very positive)
3. "topics": list of 2-3 key topics mentioned

Review: {review_text}

Return ONLY valid JSON."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,
                max_tokens=200,
            )

            content = response.choices[0].message.content.strip()

            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            return json.loads(content)

        except Exception:
            return {"sentiment": "neutral", "score": 0.5, "topics": []}
