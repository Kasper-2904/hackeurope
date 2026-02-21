"""Paid.ai service for agent usage metering and billing."""

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.storage.models import UsageRecord

logger = logging.getLogger(__name__)


class PaidService:
    """Manages Paid.ai customer/order lifecycle and usage signal tracking.

    DB is the source of truth for daily limits (not the Paid.ai API).
    Paid.ai SDK calls are fire-and-forget; failures are logged, never raised.
    When paid_api_key is empty, local tracking still works.
    """

    def __init__(self, settings=None):
        self.settings = settings or get_settings()
        self._enabled = bool(self.settings.paid_api_key)
        self._client = None
        self._customer_cache: dict[str, str] = {}
        self._order_cache: dict[str, str] = {}

        if self._enabled:
            from paid import Paid

            self._client = Paid(token=self.settings.paid_api_key)

    def _ensure_customer(self, team_id: str, team_name: str = "") -> str | None:
        """Get or create a Paid.ai customer for a team. Returns customer_id or None."""
        if not self._enabled:
            return None
        if team_id in self._customer_cache:
            return self._customer_cache[team_id]
        try:
            # Try to find existing customer by external_id first
            try:
                customer = self._client.customers.get_customer_by_external_id(
                    external_id=team_id,
                )
                self._customer_cache[team_id] = customer.id
                return customer.id
            except Exception:
                pass  # Not found — create new

            customer = self._client.customers.create_customer(
                name=team_name or f"Team {team_id}",
                external_id=team_id,
            )
            self._customer_cache[team_id] = customer.id
            return customer.id
        except Exception as e:
            logger.warning("Paid.ai customer creation failed for team %s: %s", team_id, e)
            return None

    def _ensure_order(self, customer_id: str, team_id: str) -> str | None:
        """Get or create a Paid.ai order for a customer. Returns order_id or None."""
        if not self._enabled or not customer_id:
            return None
        if team_id in self._order_cache:
            return self._order_cache[team_id]
        try:
            order = self._client.orders.create_order(
                customer_id=customer_id,
                name=f"Agent Usage - {team_id}",
            )
            self._order_cache[team_id] = order.id
            return order.id
        except Exception as e:
            logger.warning("Paid.ai order creation failed for team %s: %s", team_id, e)
            return None

    def _send_signal(self, team_id: str, event_name: str, data: dict[str, Any] | None = None) -> str | None:
        """Send a usage signal to Paid.ai. Returns signal info or None."""
        if not self._enabled:
            return None
        try:
            from paid import CustomerByExternalId, Signal

            signal_kwargs: dict[str, Any] = {
                "event_name": event_name,
                "customer": CustomerByExternalId(external_customer_id=team_id),
                "data": data,
            }

            if self.settings.paid_product_id:
                from paid.types.product_by_id import ProductById

                signal_kwargs["attribution"] = ProductById(product_id=self.settings.paid_product_id)

            signal = Signal(**signal_kwargs)
            result = self._client.signals.create_signals(signals=[signal])
            return str(result) if result else None
        except Exception as e:
            logger.warning("Paid.ai signal failed: %s", e)
            return None

    async def check_usage_limit(self, team_id: str, db: AsyncSession) -> bool:
        """Check if team is within its daily free-tier limit.

        Returns True if the team can proceed, False if limit exceeded.
        """
        limit = self.settings.free_tier_daily_limit
        if limit <= 0:
            return True

        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        result = await db.execute(
            select(func.count(UsageRecord.id)).where(
                UsageRecord.team_id == team_id,
                UsageRecord.created_at >= today_start,
            )
        )
        count = result.scalar() or 0
        return count < limit

    async def track_usage(
        self,
        db: AsyncSession,
        *,
        team_id: str,
        user_id: str | None = None,
        usage_type: str,
        marketplace_agent_id: str | None = None,
        data: dict[str, Any] | None = None,
        cost: float = 0.0,
    ) -> UsageRecord:
        """Record usage both locally (DB) and remotely (Paid.ai).

        Caller should check_usage_limit() first if they want to enforce limits.
        """
        paid_signal_id = None
        if self._enabled and team_id:
            customer_id = self._ensure_customer(team_id)
            if customer_id:
                self._ensure_order(customer_id, team_id)
                paid_signal_id = self._send_signal(
                    team_id=team_id,
                    event_name="agent_execution",
                    data=data,
                )

        record = UsageRecord(
            id=str(uuid4()),
            team_id=team_id,
            user_id=user_id,
            marketplace_agent_id=marketplace_agent_id,
            usage_type=usage_type,
            quantity=1,
            cost=cost,
            paid_signal_id=paid_signal_id,
        )
        db.add(record)
        await db.flush()  # Ensure record is durable within the transaction
        return record


_paid_service: PaidService | None = None


def get_paid_service() -> PaidService:
    """Get the global PaidService instance."""
    global _paid_service
    if _paid_service is None:
        _paid_service = PaidService()
    return _paid_service
