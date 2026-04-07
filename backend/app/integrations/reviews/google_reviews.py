"""Google Reviews integration — review links, monitoring, reply drafting."""

import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from app.database import SessionLocal
from app.models.integration import Integration
from app.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


class GoogleReviewsIntegration(BaseIntegration):
    name = "google_reviews"
    display_name = "Google Reviews"
    description = "Request reviews and monitor your Google rating"
    auth_type = "oauth2"
    capabilities = ["get_review_link", "get_reviews", "get_rating"]

    async def connect(self, business_id: Optional[str], auth_data: dict) -> bool:
        # Uses the same Google OAuth credentials as Calendar/Gmail
        from app.utils.encryption import encrypt_credentials
        db = SessionLocal()
        try:
            integ = db.query(Integration).filter(Integration.integration_type == self.name).first()
            if not integ:
                integ = Integration(integration_type=self.name, business_id=business_id)
                db.add(integ)
            integ.credentials = encrypt_credentials(auth_data)
            integ.status = "connected"
            integ.connected_at = datetime.now(timezone.utc)
            db.commit()
            return True
        except Exception as e:
            logger.error("Google Reviews connect failed: %s", e)
            return False
        finally:
            db.close()

    async def disconnect(self, business_id: Optional[str]) -> bool:
        db = SessionLocal()
        try:
            integ = db.query(Integration).filter(Integration.integration_type == self.name).first()
            if integ:
                integ.credentials = None
                integ.status = "disconnected"
                db.commit()
            return True
        finally:
            db.close()

    async def is_connected(self, business_id: Optional[str]) -> bool:
        db = SessionLocal()
        try:
            return db.query(Integration).filter(
                Integration.integration_type == self.name, Integration.status == "connected"
            ).first() is not None
        finally:
            db.close()

    async def test_connection(self, business_id: Optional[str]) -> bool:
        return await self.is_connected(business_id)

    async def execute_action(self, action_type: str, params: dict) -> Dict[str, Any]:
        if action_type == "request_review":
            # The review link is stored in business config; this just confirms it's available
            return {"success": True, "action_type": action_type, "details": {"message": "Review link available"}, "error": None}
        return {"success": False, "action_type": action_type, "details": None, "error": "Unknown action"}

    def get_review_link(self, place_id: str) -> str:
        """Generate the direct Google review link from a Place ID."""
        return "https://search.google.com/local/writereview?placeid={}".format(place_id)

    def get_recent_reviews(self, max_results: int = 20) -> List[dict]:
        """Fetch recent reviews via Google Business Profile API.
        Note: Requires Business Profile API access which has additional setup.
        """
        logger.info("Google Reviews fetch — requires Business Profile API setup")
        return []

    def get_average_rating(self) -> dict:
        """Get current rating. Requires Business Profile API."""
        return {"average": 0, "total": 0}


google_reviews = GoogleReviewsIntegration()
