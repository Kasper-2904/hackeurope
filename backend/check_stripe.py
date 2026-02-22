import sys, os
sys.path.append(os.path.join(os.getcwd(), 'backend'))
import asyncio
from dotenv import load_dotenv
load_dotenv('backend/.env')
import stripe
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')

async def main():
    seat = os.getenv('STRIPE_PRICE_SEAT')
    print("Seat ID:", seat)
    if seat.startswith('prod_'):
        prices = stripe.Price.list(product=seat)
        print("Prices for product:", prices)
        if len(prices.data) > 0:
            print("Using price:", prices.data[0].id)
    else:
        print("Seat ID is not a product ID")

asyncio.run(main())
