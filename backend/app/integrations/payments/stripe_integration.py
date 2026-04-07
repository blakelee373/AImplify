"""Stripe payments integration — invoices, payment links, revenue reports."""

import logging
from datetime import datetime, timedelta, timezone, date
from typing import Optional, Dict, Any, List

import stripe as stripe_sdk

from app.database import SessionLocal
from app.models.integration import Integration
from app.utils.encryption import encrypt_credentials, decrypt_credentials
from app.integrations.base import BaseIntegration

logger = logging.getLogger(__name__)


class StripeIntegration(BaseIntegration):
    name = "stripe"
    display_name = "Stripe Payments"
    description = "Send invoices and payment links to clients"
    auth_type = "api_key"
    capabilities = [
        "send_invoice", "create_payment_link",
        "get_payments", "get_revenue",
    ]

    def _configure(self):
        db = SessionLocal()
        try:
            integ = db.query(Integration).filter(
                Integration.integration_type == self.name,
                Integration.status == "connected",
            ).first()
            if not integ or not integ.credentials:
                raise RuntimeError("Stripe not connected")
            creds = decrypt_credentials(integ.credentials)
            stripe_sdk.api_key = creds.get("secret_key")
        finally:
            db.close()

    async def connect(self, business_id: Optional[str], auth_data: dict) -> bool:
        try:
            stripe_sdk.api_key = auth_data.get("secret_key")
            stripe_sdk.Account.retrieve()  # validate
        except Exception as e:
            logger.error("Stripe validation failed: %s", e)
            return False

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
        try:
            self._configure()
            stripe_sdk.Account.retrieve()
            return True
        except Exception:
            return False

    async def execute_action(self, action_type: str, params: dict) -> Dict[str, Any]:
        try:
            self._configure()
            if action_type == "send_invoice":
                result = self.send_invoice(**params)
                return {"success": True, "action_type": action_type, "details": result, "error": None}
            if action_type == "send_payment_link":
                url = self.create_payment_link(**params)
                return {"success": True, "action_type": action_type, "details": {"url": url}, "error": None}
            return {"success": False, "action_type": action_type, "details": None, "error": "Unknown action"}
        except Exception as e:
            return {"success": False, "action_type": action_type, "details": None, "error": str(e)}

    def send_invoice(self, client_email: str, amount: float, description: str, **kwargs) -> dict:
        self._configure()
        # Find or create customer
        customers = stripe_sdk.Customer.list(email=client_email, limit=1)
        if customers.data:
            customer = customers.data[0]
        else:
            customer = stripe_sdk.Customer.create(email=client_email)

        invoice = stripe_sdk.Invoice.create(customer=customer.id, auto_advance=True)
        stripe_sdk.InvoiceItem.create(
            customer=customer.id,
            invoice=invoice.id,
            amount=int(amount * 100),
            currency="usd",
            description=description,
        )
        invoice = stripe_sdk.Invoice.finalize_invoice(invoice.id)
        stripe_sdk.Invoice.send_invoice(invoice.id)
        return {"invoice_id": invoice.id, "amount": amount, "status": invoice.status}

    def create_payment_link(self, amount: float, description: str, **kwargs) -> str:
        self._configure()
        price = stripe_sdk.Price.create(
            unit_amount=int(amount * 100),
            currency="usd",
            product_data={"name": description},
        )
        link = stripe_sdk.PaymentLink.create(line_items=[{"price": price.id, "quantity": 1}])
        return link.url

    def get_daily_revenue(self, target_date: Optional[date] = None) -> dict:
        self._configure()
        d = target_date or date.today()
        start = int(datetime.combine(d, datetime.min.time()).replace(tzinfo=timezone.utc).timestamp())
        end = start + 86400
        charges = stripe_sdk.Charge.list(created={"gte": start, "lt": end}, limit=100)
        total = sum(c.amount for c in charges.data if c.paid) / 100
        return {"date": str(d), "revenue": total, "transaction_count": len(charges.data)}


stripe_integration = StripeIntegration()
