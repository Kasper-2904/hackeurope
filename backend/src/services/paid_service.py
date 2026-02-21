"""Paid.ai service for agent usage metering and billing."""

from paid import Paid
from src.config import get_settings
from typing import Any, Dict


class PaidService:
    def __init__(self):
        self.settings = get_settings()
        self.client = Paid(token=self.settings.paid_api_key)

    def register_customer(self, team_id: str, team_name: str) -> str:
        """Register a team as a customer in Paid.ai."""
        try:
            customer = self.client.customers.create(
                name=team_name,
                external_id=team_id,
            )
            return customer.id
        except Exception as e:
            print(f"Paid.ai customer creation error: {e}")
            raise

    def record_usage(
        self, product_id: str, customer_id: str, event_name: str, data: Dict[str, Any] = None
    ):
        """Record usage of an agent via Paid.ai signals."""
        try:
            # First import to check if SignalV2 exists
            try:
                from paid import SignalV2

                signal = SignalV2(
                    event_name=event_name,
                    product_id=product_id,
                    customer_id=customer_id,
                    data=data or {},
                )
                return self.client.usage.record_bulk_v2(signals=[signal])
            except ImportError:
                # Fallback to older SDK
                from paid import Signal

                signal = Signal(
                    event_name=event_name,
                    product_id=product_id,
                    customer_id=customer_id,
                    data=data or {},
                )
                return self.client.usage.record_bulk(signals=[signal])
        except Exception as e:
            print(f"Paid.ai signal error: {e}")
            # Do not fail execution if tracking fails, just log it
            return None


def get_paid_service() -> PaidService:
    return PaidService()
