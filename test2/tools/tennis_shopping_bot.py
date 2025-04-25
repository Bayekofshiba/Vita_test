from collections.abc import Generator
from typing import Any

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage

class Test2Tool(Tool):
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        yield self.create_json_message({
            "result": "Hello, world!"
        })

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

import logging
from getpass import getpass
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Define constants
PRODUCT_CATEGORIES = ["racquet", "garment", "shoes", "other"]

def get_user_input(prompt, default=None):
    """Get user input with an optional default value."""
    user_input = input(prompt)
    return user_input.strip() if user_input else default

def get_password_input(prompt):
    """Get sensitive input securely (used here for credit card info only)."""
    return getpass(prompt)

def dify_headless_purchase_flow():
    """
    Simulate a headless browser purchase flow using a website URL provided by the user.
    This version always uses guest checkout (no password prompt for login) and is structured
    to be adapted for an agentic chatbot on Dify.
    """
    logging.info("Starting headless browser purchase flow")
    
    # --- Ask for the website URL ---
    website_url = get_user_input("Enter the website URL (default 'https://www.tennisexpress.com/'): ", default="https://www.tennisexpress.com/").strip()
    
    # === PRODUCT SELECTION ===
    item_name = get_user_input("Enter the exact product name: ").lower()
    category = get_user_input("What is the product category? (e.g., 'racquet', 'garment', 'shoes', 'other'): ").lower()
    while category not in PRODUCT_CATEGORIES:
        category = get_user_input("Invalid category. Please enter a valid category: ").lower()

    variant_details = {}
    if category == "racquet":
        variant_details["size"] = get_user_input("Enter the desired size: ").strip()
        variant_details["string_type"] = get_user_input("Enter the string type (e.g., 'polyester', 'multifilament'): ").lower()
        variant_details["string_name"] = get_user_input("Enter the desired string name (e.g., 'Luxilon Alu Power 125'): ").strip()
        variant_details["string_tension"] = get_user_input("Enter the desired string tension (e.g., '55 lbs'): ").strip()
    elif category in ["garment", "shoes"]:
        variant_details["size"] = get_user_input("Enter the desired size (e.g., 'M' for garments or '9' for shoes): ").strip()
        variant_details["color"] = get_user_input("Enter the desired color (e.g., 'black', 'red', 'blue'): ").strip()
    else:
        need_variant = get_user_input("Does this product have any customizable options? (yes/no): ").lower()
        if need_variant.startswith("y"):
            variant_details["option1"] = get_user_input("Enter the customization details (or press Enter to skip): ").strip() or None

    # === SHIPPING & ACCOUNT DETAILS ===
    first_name = get_user_input("First Name: ").strip()
    last_name = get_user_input("Last Name: ").strip()
    email = get_user_input("Email (for shipping and confirmation): ").strip()
    phone = get_user_input("Phone Number: ").strip()
    address = get_user_input("Street Address: ").strip()
    city = get_user_input("City: ").strip()
    state = get_user_input("State (abbreviation or full name): ").strip()
    postal_code = get_user_input("Zip/Postal Code: ").strip()
    country = get_user_input("Country (default 'United States'): ").strip() or "United States"

    # === PAYMENT INFORMATION ===
    # (Retain secure input for credit card details)
    card_number = get_password_input("Credit Card Number (use test card if demo): ")
    card_expiration = get_user_input("Card Expiration Date (MM/YY): ").strip()
    card_cvv = get_password_input("Card CVV: ")
    billing_address = get_user_input("Billing Address (if different, otherwise press Enter to use shipping address): ").strip() or address

    # === COUPON, SHIPPING OPTIONS, GIFT WRAPPING ===
    coupon_response = get_user_input("Do you have a coupon code? (yes/no): ").lower()
    coupon_code = None
    if coupon_response.startswith("y"):
        coupon_code = get_user_input("Enter the coupon code: ").strip()

    shipping_response = get_user_input("Do you want to select a different shipping option? (yes/no): ").lower()
    shipping_option = None
    if shipping_response.startswith("y"):
        shipping_option = get_user_input("Enter the shipping option (e.g., 'expedited', 'in-store pickup'): ").strip()

    gift_wrapping_response = get_user_input("Do you want to add gift wrapping? (yes/no): ").lower()
    gift_wrapping_message = None
    if gift_wrapping_response.startswith("y"):
        gift_wrapping_message = get_user_input("Enter the gift wrapping message: ").strip()

    # --- BROWSER AUTOMATION ---
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(website_url)

            # Always use guest checkout (login functionality removed)
            logging.info("Proceeding with guest checkout.")

            # --- Loop: Search for product and handle non-exact matches ---
            product_selected = False
            while not product_selected:
                page.fill('input[name="search"]', item_name)
                page.press('input[name="search"]', "Enter")
                try:
                    page.wait_for_selector('div.product-container a.product-link', timeout=10000)
                except PlaywrightTimeoutError as e:
                    logging.error(f"Error searching for product: {e}")
                    item_name = get_user_input("No products found. Enter a new product name: ").lower()
                    continue

                links = page.query_selector_all('div.product-container a.product-link')
                if not links:
                    item_name = get_user_input("No products found. Enter a new product name: ").lower()
                    continue

                # Try to find an exact match (case-insensitive)
                exact_match_found = None
                for link in links:
                    try:
                        title = link.inner_text().strip()
                    except Exception:
                        continue
                    if title.lower() == item_name.lower():
                        exact_match_found = link
                        break

                if exact_match_found:
                    exact_match_found.click()
                    product_selected = True
                else:
                    print("No exact match found. Please choose from the following options:")
                    options = []
                    for idx, link in enumerate(links):
                        try:
                            title = link.inner_text().strip()
                        except Exception:
                            title = f"Product {idx+1}"
                        options.append(title)
                        print(f"{idx+1}. {title}")

                    selection = get_user_input("Enter the number corresponding to your desired product, or press Enter to search again: ")
                    if not selection:
                        item_name = get_user_input("Enter a new product name: ").lower()
                        continue
                    try:
                        selection_index = int(selection) - 1
                        if selection_index < 0 or selection_index >= len(options):
                            print("Invalid selection. Please try again.")
                            continue
                        else:
                            links[selection_index].click()
                            product_selected = True
                    except ValueError:
                        print("Invalid input. Please try again.")
                        continue

            # --- Variant Selection based on Category ---
            if category == "racquet":
                try:
                    page.click(f'text="{variant_details["size"]}"')
                except PlaywrightTimeoutError:
                    logging.error("Racquet size option not found.")
                try:
                    page.click(f'text="{variant_details["string_type"]}"')
                except PlaywrightTimeoutError:
                    logging.error("String type option not found.")
                try:
                    page.fill('input[name="string_tension"]', variant_details["string_tension"])
                except PlaywrightTimeoutError:
                    logging.error("String tension field not found.")
            elif category in ["garment", "shoes"]:
                try:
                    page.click(f'text="{variant_details["size"]}"')
                except PlaywrightTimeoutError:
                    logging.error("Size option not found.")
            else:
                if variant_details.get("option1"):
                    try:
                        page.fill('input[name="customOption"]', variant_details["option1"])
                    except PlaywrightTimeoutError:
                        logging.error("Custom option field not found.")

            # --- Add to Cart ---
            try:
                page.click('#addToCartButton')
            except PlaywrightTimeoutError:
                logging.error("Add to cart button not found. Exiting flow.")
                browser.close()
                return "Error: Add to Cart Failed"

            # Optionally close any pop-ups (e.g., upsell offers)
            try:
                page.wait_for_selector('button.close-popup', timeout=3000)
                page.click('button.close-popup')
            except PlaywrightTimeoutError:
                pass  # No pop-up appeared

            # --- Navigate to Cart and Checkout ---
            try:
                page.wait_for_selector('a[href*="ViewCart"]', timeout=5000)
                page.click('a[href*="ViewCart"]')
                page.wait_for_selector('a[href*="Checkout"]', timeout=10000)
                page.click('a[href*="Checkout"]')
            except PlaywrightTimeoutError:
                logging.error("Cart or checkout navigation failed.")
                browser.close()
                return "Error: Checkout Navigation Failed"

            # --- Fill in Shipping Details ---
            page.fill('#firstName', first_name)
            page.fill('#lastName', last_name)
            page.fill('#email', email)
            page.fill('#phone', phone)
            page.fill('#address', address)
            page.fill('#city', city)
            try:
                page.select_option('#state', state)
            except PlaywrightTimeoutError:
                page.fill('#state', state)
            page.fill('#zip', postal_code)
            try:
                page.select_option('#country', country)
            except PlaywrightTimeoutError:
                pass

            # (Optional) Apply coupon if provided
            if coupon_code:
                try:
                    page.fill('#couponCode', coupon_code)
                    page.click('#applyCoupon')
                    page.wait_for_selector('.coupon-success', timeout=5000)
                except PlaywrightTimeoutError:
                    logging.error("Coupon application failed or not applicable.")

            # (Optional) Select shipping option if provided
            if shipping_option:
                try:
                    page.click(f'text="{shipping_option}"')
                except PlaywrightTimeoutError:
                    logging.error("Shipping option not found or not applicable.")

            # (Optional) Add gift wrapping if requested
            if gift_wrapping_message:
                try:
                    page.click('input[name="giftWrap"]')  # Example selector; update as needed.
                    page.fill('textarea[name="giftMessage"]', gift_wrapping_message)
                except PlaywrightTimeoutError:
                    logging.error("Gift wrapping options not found.")

            # --- Proceed to Payment ---
            try:
                page.click('#continueToPayment')
            except PlaywrightTimeoutError:
                logging.error("Continue to payment button not found. Exiting flow.")
                browser.close()
                return "Error: Unable to proceed to payment"

            # --- Fill in Payment Details ---
            page.fill('#cardNumber', card_number)
            page.fill('#cardExp', card_expiration)
            page.fill('#cardCVV', card_cvv)
            if billing_address and billing_address != address:
                page.fill('#billingAddress', billing_address)

            # --- Finalize Order ---
            try:
                page.click('#placeOrderButton')
            except PlaywrightTimeoutError:
                logging.error("Place order button not found. Exiting flow.")
                browser.close()
                return "Error: Order Placement Failed"

            # --- Wait for Confirmation ---
            try:
                page.wait_for_selector('.order-confirmation', timeout=15000)
                confirmation_text = page.inner_text('.order-confirmation')
                print("Order Confirmation:", confirmation_text)
            except PlaywrightTimeoutError:
                logging.error("Order confirmation not detected within the timeout period.")

            browser.close()
            return "Purchase flow executed successfully (please verify your order on the website)."

    except Exception as e:
        logging.error(f"An error occurred during the purchase flow: {e}")
        return f"Error: {e}"

# For testing as a standalone script, you can uncomment the following lines:
# if __name__ == "__main__":
#     result = dify_headless_purchase_flow()
#     print(result)
