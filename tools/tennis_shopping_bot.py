from collections.abc import Generator
from typing import Any, Dict, Optional
import logging

from dify_plugin import Tool
from dify_plugin.entities.tool import ToolInvokeMessage
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# Define constants
PRODUCT_CATEGORIES = ["racquet", "garment", "shoes", "other"]

class PurchaseFlowTool(Tool):
    """
    A Dify plugin tool for performing headless browser purchases using Playwright.
    Takes purchase details from the chat and executes an automated purchase flow.
    """
    
    def _invoke(self, tool_parameters: dict[str, Any]) -> Generator[ToolInvokeMessage]:
        """Process the purchase request with provided parameters from the chat."""
        try:
            # Required parameters
            website_url = str(tool_parameters.get("website_url", "https://www.tennisexpress.com/")).strip()
            item_name = str(tool_parameters.get("item_name", "")).lower().strip()
            category = str(tool_parameters.get("category", "")).lower().strip()
            
            # Validate category
            if category not in PRODUCT_CATEGORIES:
                yield self.create_text_message(f"Invalid category '{category}'. Valid categories are: {', '.join(PRODUCT_CATEGORIES)}")
                return
            
            # Extract all other required parameters
            params = self._extract_parameters(tool_parameters)
            if "error" in params:
                yield self.create_text_message(params["error"])
                return
                
            # Execute purchase flow
            yield self.create_text_message("Starting purchase flow...")
            
            result = self._execute_purchase_flow(
                website_url=website_url,
                item_name=item_name,
                category=category,
                **params
            )
            
            # Return result
            yield self.create_json_message({
                "success": not result.startswith("Error:"),
                "message": result
            })
            
        except Exception as e:
            logging.error(f"Error in purchase flow: {str(e)}")
            yield self.create_json_message({
                "success": False,
                "message": f"Error in purchase flow: {str(e)}"
            })
    
    def _extract_parameters(self, tool_parameters: dict[str, Any]) -> Dict[str, Any]:
        """Extract and validate all parameters from the tool input."""
        params = {}
        
        # Variant details
        params["variant_details"] = tool_parameters.get("variant_details", {})
        
        # User details
        params["first_name"] = str(tool_parameters.get("first_name", "")).strip()
        params["last_name"] = str(tool_parameters.get("last_name", "")).strip()
        params["email"] = str(tool_parameters.get("email", "")).strip()
        params["phone"] = str(tool_parameters.get("phone", "")).strip()
        params["address"] = str(tool_parameters.get("address", "")).strip()
        params["city"] = str(tool_parameters.get("city", "")).strip()
        params["state"] = str(tool_parameters.get("state", "")).strip()
        params["postal_code"] = str(tool_parameters.get("postal_code", "")).strip()
        params["country"] = str(tool_parameters.get("country", "United States")).strip()
        
        # Payment information
        params["card_number"] = str(tool_parameters.get("card_number", "")).strip()
        params["card_expiration"] = str(tool_parameters.get("card_expiration", "")).strip()
        params["card_cvv"] = str(tool_parameters.get("card_cvv", "")).strip()
        params["billing_address"] = str(tool_parameters.get("billing_address", params["address"])).strip()
        
        # Optional parameters
        params["coupon_code"] = tool_parameters.get("coupon_code")
        params["shipping_option"] = tool_parameters.get("shipping_option")
        params["gift_wrapping_message"] = tool_parameters.get("gift_wrapping_message")
        
        # Parameter validation
        required_fields = ["first_name", "last_name", "email", "phone", 
                          "address", "city", "state", "postal_code", 
                          "card_number", "card_expiration", "card_cvv"]
        
        missing_fields = [field for field in required_fields if not params[field]]
        
        if missing_fields:
            return {"error": f"Missing required fields: {', '.join(missing_fields)}"}
            
        return params
    
    def _execute_purchase_flow(
        self, website_url: str, item_name: str, category: str, **kwargs
    ) -> str:
        """Execute the purchase flow using Playwright."""
        try:
            # Extract parameters from kwargs
            variant_details = kwargs.get("variant_details", {})
            first_name = kwargs.get("first_name", "")
            last_name = kwargs.get("last_name", "")
            email = kwargs.get("email", "")
            phone = kwargs.get("phone", "")
            address = kwargs.get("address", "")
            city = kwargs.get("city", "")
            state = kwargs.get("state", "")
            postal_code = kwargs.get("postal_code", "")
            country = kwargs.get("country", "United States")
            card_number = kwargs.get("card_number", "")
            card_expiration = kwargs.get("card_expiration", "")
            card_cvv = kwargs.get("card_cvv", "")
            billing_address = kwargs.get("billing_address", address)
            coupon_code = kwargs.get("coupon_code")
            shipping_option = kwargs.get("shipping_option")
            gift_wrapping_message = kwargs.get("gift_wrapping_message")
            
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                
                # Log for debugging
                logging.info(f"Navigating to {website_url}")
                page.goto(website_url)
                
                # --- Search for product ---
                product_selected = False
                max_attempts = 3
                attempts = 0
                
                while not product_selected and attempts < max_attempts:
                    attempts += 1
                    logging.info(f"Searching for product: {item_name} (attempt {attempts})")
                    
                    try:
                        page.fill('input[name="search"]', item_name)
                        page.press('input[name="search"]', "Enter")
                        page.wait_for_selector('div.product-container a.product-link', timeout=10000)
                    except PlaywrightTimeoutError:
                        logging.error("Error searching for product - selector not found")
                        if attempts >= max_attempts:
                            browser.close()
                            return "Error: Product search failed after multiple attempts"
                        continue
                        
                    links = page.query_selector_all('div.product-container a.product-link')
                    if not links:
                        logging.error("No product links found")
                        if attempts >= max_attempts:
                            browser.close()
                            return "Error: No products found matching the search criteria"
                        continue
                    
                    # Try to find an exact match (case-insensitive)
                    exact_match_found = None
                    for link in links:
                        try:
                            title = link.inner_text().strip()
                            if title.lower() == item_name.lower():
                                exact_match_found = link
                                break
                        except Exception:
                            continue
                    
                    if exact_match_found:
                        exact_match_found.click()
                        product_selected = True
                    else:
                        # Select the first product if no exact match
                        links[0].click()
                        product_selected = True
                
                if not product_selected:
                    browser.close()
                    return "Error: Unable to select a product"
                
                # --- Variant Selection based on Category ---
                logging.info(f"Selecting variants for category: {category}")
                if category == "racquet":
                    try:
                        if variant_details.get("size"):
                            page.click(f'text="{variant_details["size"]}"', timeout=5000)
                    except PlaywrightTimeoutError:
                        logging.warning("Racquet size option not found")
                    
                    try:
                        if variant_details.get("string_type"):
                            page.click(f'text="{variant_details["string_type"]}"', timeout=5000)
                    except PlaywrightTimeoutError:
                        logging.warning("String type option not found")
                    
                    try:
                        if variant_details.get("string_tension"):
                            page.fill('input[name="string_tension"]', variant_details["string_tension"])
                    except PlaywrightTimeoutError:
                        logging.warning("String tension field not found")
                
                elif category in ["garment", "shoes"]:
                    try:
                        if variant_details.get("size"):
                            page.click(f'text="{variant_details["size"]}"', timeout=5000)
                    except PlaywrightTimeoutError:
                        logging.warning("Size option not found")
                    
                    try:
                        if variant_details.get("color"):
                            page.click(f'text="{variant_details["color"]}"', timeout=5000)
                    except PlaywrightTimeoutError:
                        logging.warning("Color option not found")
                
                elif variant_details.get("option1"):
                    try:
                        page.fill('input[name="customOption"]', variant_details["option1"])
                    except PlaywrightTimeoutError:
                        logging.warning("Custom option field not found")
                
                # --- Add to Cart ---
                logging.info("Adding product to cart")
                try:
                    page.click('#addToCartButton', timeout=5000)
                except PlaywrightTimeoutError:
                    # Try alternative selectors
                    try:
                        page.click('button:has-text("Add to Cart")', timeout=5000)
                    except PlaywrightTimeoutError:
                        browser.close()
                        return "Error: Add to Cart button not found"
                
                # Close potential pop-ups
                try:
                    page.wait_for_selector('button.close-popup', timeout=3000)
                    page.click('button.close-popup')
                except PlaywrightTimeoutError:
                    pass  # No pop-up appeared
                
                # --- Navigate to Cart and Checkout ---
                logging.info("Navigating to checkout")
                try:
                    # Try multiple possible cart/checkout flows
                    try:
                        page.wait_for_selector('a[href*="ViewCart"]', timeout=5000)
                        page.click('a[href*="ViewCart"]')
                    except PlaywrightTimeoutError:
                        try:
                            page.click('a:has-text("Cart")', timeout=3000)
                        except PlaywrightTimeoutError:
                            pass
                    
                    # Try to find checkout button
                    try:
                        page.wait_for_selector('a[href*="Checkout"]', timeout=8000)
                        page.click('a[href*="Checkout"]')
                    except PlaywrightTimeoutError:
                        try:
                            page.click('button:has-text("Checkout")', timeout=5000)
                        except PlaywrightTimeoutError:
                            browser.close()
                            return "Error: Checkout button not found"
                            
                except Exception as e:
                    logging.error(f"Error during cart/checkout navigation: {e}")
                    browser.close()
                    return f"Error: Cart/checkout navigation failed: {str(e)}"
                
                # --- Fill in Shipping Details ---
                logging.info("Filling shipping details")
                try:
                    # Try multiple common form field selectors
                    try:
                        page.fill('#firstName', first_name)
                    except:
                        try:
                            page.fill('input[name="firstName"]', first_name)
                        except:
                            page.fill('[placeholder="First Name"]', first_name)
                    
                    try:
                        page.fill('#lastName', last_name)
                    except:
                        try:
                            page.fill('input[name="lastName"]', last_name)
                        except:
                            page.fill('[placeholder="Last Name"]', last_name)
                    
                    try:
                        page.fill('#email', email)
                    except:
                        try:
                            page.fill('input[name="email"]', email)
                        except:
                            page.fill('[placeholder="Email"]', email)
                    
                    try:
                        page.fill('#phone', phone)
                    except:
                        try:
                            page.fill('input[name="phone"]', phone)
                        except:
                            page.fill('[placeholder="Phone"]', phone)
                    
                    try:
                        page.fill('#address', address)
                    except:
                        try:
                            page.fill('input[name="address"]', address)
                        except:
                            page.fill('[placeholder="Address"]', address)
                    
                    try:
                        page.fill('#city', city)
                    except:
                        try:
                            page.fill('input[name="city"]', city)
                        except:
                            page.fill('[placeholder="City"]', city)
                    
                    # State field - might be dropdown or text input
                    try:
                        page.select_option('#state', state)
                    except:
                        try:
                            page.fill('#state', state)
                        except:
                            try:
                                page.select_option('select[name="state"]', state)
                            except:
                                try:
                                    page.fill('input[name="state"]', state)
                                except:
                                    logging.warning("State field not found or not fillable")
                    
                    try:
                        page.fill('#zip', postal_code)
                    except:
                        try:
                            page.fill('input[name="zip"]', postal_code)
                        except:
                            try:
                                page.fill('#postal_code', postal_code)
                            except:
                                try:
                                    page.fill('input[name="postal_code"]', postal_code)
                                except:
                                    logging.warning("Postal code field not found")
                    
                    # Country field - might be dropdown or already set
                    try:
                        page.select_option('#country', country)
                    except:
                        try:
                            page.select_option('select[name="country"]', country)
                        except:
                            logging.warning("Country field not found or not fillable")
                
                except Exception as e:
                    logging.error(f"Error filling shipping details: {e}")
                
                # Apply coupon if provided
                if coupon_code:
                    logging.info(f"Applying coupon: {coupon_code}")
                    try:
                        try:
                            page.fill('#couponCode', coupon_code)
                            page.click('#applyCoupon')
                        except:
                            try:
                                page.fill('input[name="couponCode"]', coupon_code)
                                page.click('button:has-text("Apply")')
                            except:
                                logging.warning("Coupon field not found")
                    except Exception as e:
                        logging.error(f"Error applying coupon: {e}")
                
                # Select shipping option if provided
                if shipping_option:
                    logging.info(f"Selecting shipping option: {shipping_option}")
                    try:
                        page.click(f'text="{shipping_option}"')
                    except PlaywrightTimeoutError:
                        logging.warning("Shipping option not found")
                
                # Add gift wrapping if requested
                if gift_wrapping_message:
                    logging.info("Adding gift wrapping")
                    try:
                        page.click('input[name="giftWrap"]')
                        page.fill('textarea[name="giftMessage"]', gift_wrapping_message)
                    except PlaywrightTimeoutError:
                        logging.warning("Gift wrapping options not found")
                
                # --- Proceed to Payment ---
                logging.info("Proceeding to payment")
                try:
                    try:
                        page.click('#continueToPayment', timeout=5000)
                    except PlaywrightTimeoutError:
                        try:
                            page.click('button:has-text("Continue to Payment")', timeout=5000)
                        except PlaywrightTimeoutError:
                            try:
                                page.click('button:has-text("Next")', timeout=5000)
                            except PlaywrightTimeoutError:
                                logging.warning("Continue to payment button not found")
                except Exception as e:
                    logging.error(f"Error proceeding to payment: {e}")
                
                # --- Fill in Payment Details ---
                logging.info("Filling payment details")
                try:
                    try:
                        page.fill('#cardNumber', card_number)
                    except:
                        try:
                            page.fill('input[name="cardNumber"]', card_number)
                        except:
                            page.fill('[placeholder="Card Number"]', card_number)
                    
                    try:
                        page.fill('#cardExp', card_expiration)
                    except:
                        try:
                            page.fill('input[name="cardExp"]', card_expiration)
                        except:
                            try:
                                page.fill('[placeholder="MM/YY"]', card_expiration)
                            except:
                                # Try separate month/year fields
                                expiry = card_expiration.split('/')
                                if len(expiry) == 2:
                                    try:
                                        page.fill('#expMonth', expiry[0].strip())
                                        page.fill('#expYear', expiry[1].strip())
                                    except:
                                        logging.warning("Expiration date fields not found")
                    
                    try:
                        page.fill('#cardCVV', card_cvv)
                    except:
                        try:
                            page.fill('input[name="cardCVV"]', card_cvv)
                        except:
                            page.fill('[placeholder="CVV"]', card_cvv)
                    
                    # Fill billing address if different
                    if billing_address and billing_address != address:
                        try:
                            page.fill('#billingAddress', billing_address)
                        except:
                            try:
                                page.fill('input[name="billingAddress"]', billing_address)
                            except:
                                logging.warning("Billing address field not found")
                
                except Exception as e:
                    logging.error(f"Error filling payment details: {e}")
                
                # --- Finalize Order ---
                logging.info("Placing order")
                try:
                    try:
                        page.click('#placeOrderButton', timeout=5000)
                    except PlaywrightTimeoutError:
                        try:
                            page.click('button:has-text("Place Order")', timeout=5000)
                        except PlaywrightTimeoutError:
                            try:
                                page.click('button:has-text("Complete Purchase")', timeout=5000)
                            except PlaywrightTimeoutError:
                                browser.close()
                                return "Error: Place order button not found"
                except Exception as e:
                    logging.error(f"Error placing order: {e}")
                    browser.close()
                    return f"Error: Failed to place order: {str(e)}"
                
                # --- Wait for Confirmation ---
                logging.info("Waiting for order confirmation")
                try:
                    try:
                        page.wait_for_selector('.order-confirmation', timeout=15000)
                        confirmation_text = page.inner_text('.order-confirmation')
                    except PlaywrightTimeoutError:
                        try:
                            page.wait_for_selector('text="Thank you for your order"', timeout=10000)
                            confirmation_text = "Order placed successfully"
                        except PlaywrightTimeoutError:
                            try:
                                page.wait_for_selector('text="Order Confirmation"', timeout=10000)
                                confirmation_text = "Order confirmed"
                            except PlaywrightTimeoutError:
                                browser.close()
                                return "Order may have been placed, but confirmation was not detected"
                
                except Exception as e:
                    logging.error(f"Error detecting confirmation: {e}")
                    browser.close()
                    return "Order may have been placed, but confirmation could not be verified"
                
                browser.close()
                return f"Purchase flow executed successfully: {confirmation_text}"
        
        except Exception as e:
            logging.error(f"An error occurred during the purchase flow: {e}")
            return f"Error: {str(e)}"