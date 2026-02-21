"""Stripe service for handling payments and seller onboarding."""

import stripe
from src.config import get_settings


class StripeService:
    def __init__(self):
        self.settings = get_settings()
        stripe.api_key = self.settings.stripe_secret_key

    def create_checkout_session(
        self, team_id: str, price_id: str, success_url: str, cancel_url: str
    ) -> str:
        """Create a Stripe checkout session for a team subscription."""
        try:
            session = stripe.checkout.Session.create(
                payment_method_types=["card"],
                line_items=[
                    {
                        "price": price_id,
                        "quantity": 1,
                    }
                ],
                mode="subscription",
                success_url=success_url,
                cancel_url=cancel_url,
                client_reference_id=team_id,
            )
            return session.url
        except stripe.error.StripeError as e:
            print(f"Stripe error: {e}")
            raise

    def create_connect_account(self, user_id: str, email: str) -> str:
        """Create a Stripe Connect Express account for a seller."""
        try:
            account = stripe.Account.create(
                type="express",
                email=email,
                capabilities={
                    "card_payments": {"requested": True},
                    "transfers": {"requested": True},
                },
                metadata={"user_id": user_id},
            )
            return account.id
        except stripe.error.StripeError as e:
            print(f"Stripe error: {e}")
            raise

    def create_account_link(self, account_id: str, refresh_url: str, return_url: str) -> str:
        """Create an account link for Stripe Connect onboarding."""
        try:
            account_link = stripe.AccountLink.create(
                account=account_id,
                refresh_url=refresh_url,
                return_url=return_url,
                type="account_onboarding",
            )
            return account_link.url
        except stripe.error.StripeError as e:
            print(f"Stripe error: {e}")
            raise


def get_stripe_service() -> StripeService:
    return StripeService()
