import agentql
from playwright.async_api import async_playwright
from app.schemas.store import StoreConfig
from typing import List, Dict, Any
import logging
import os

logger = logging.getLogger(__name__)

# Define AgentQL queries - matching store_discovery.py
STORE_INFO_QUERY = """
{
    header {
        title(the page title from the document head)
        sign_in_btn(a button with text "Sign in" in the header navigation)
    }
}
"""

INITIAL_MODAL_QUERY = """
{
    welcome_modal(a modal asking if you've shopped before) {
        sign_in_btn(a button with text "Sign in")
        create_account_btn(a button with text "Create account")
        close_btn(a button to close the modal)
    }
}
"""

LOGIN_OPTIONS_MODAL_QUERY = """
{
    login_modal(a "Welcome back!" modal with login options) {
        email_box(an input field for email or mobile number)
        passwordless_btn(a button with text "Sign in without a password")
        password_btn(a button with text "Sign in with password")
        create_account_link(a link with text "Create account")
        business_account_link(a link with text "Create a business account")
    }
}
"""

PASSWORD_MODAL_QUERY = """
{
    password_modal(a modal for password entry) {
        email_text(text showing the email being used)
        change_email_link(a link to change the email)
        password_box(a password input field)
        show_password_btn(a button to show/hide password)
        forgot_password_link(a link for forgotten passwords)
        sign_in_btn(a button to submit the login)
        verification_code_link(a link to use verification code instead)
    }
}
"""

# Define coupon-related queries
COUPON_NAV_QUERY = """
{
    coupon_section {
        nav_link(a link in the navigation that leads to digital coupons or deals) {
            exists
            click()
        }
    }
}
"""

COUPON_PAGE_QUERY = """
{
    coupon_section {
        heading(a heading containing text "Digital Coupons" or "Available Coupons").exists
        available_coupons[] {
            offer {
                title(the name or title of the coupon offer).text
                description(a description of what the coupon is for).text
                savings(the amount saved with $ or % symbols).text
                expiration(expiration date or valid through date).text
                terms(usage limits or restrictions).text
            }
            clip_btn(a button to clip or add the coupon to your account) {
                exists
                is_clipped: text("Clipped").exists || has_class("clipped") || has_class("added")
                click()
            }
        }
        pagination {
            load_more_btn(a button to load more coupons or show next page).exists
            click_if_exists {
                if(load_more_btn.exists) {
                    load_more_btn.click()
                }
            }
        }
    }
}
"""

class DynamicCouponService:
    def __init__(self):
        # Suppress AgentQL info messages
        agentql_logger = logging.getLogger('agentql')
        agentql_logger.setLevel(logging.WARNING)
        
        # Debug logging for environment variables
        logger.info(f"Reading environment variables...")
        logger.info(f"AGENTQL_API_KEY: {'*' * len(os.getenv('AGENTQL_API_KEY', ''))}")
        logger.info(f"AGENTQL_ENVIRONMENT: {os.getenv('AGENTQL_ENVIRONMENT')}")
        
        # Clean and parse timeout value
        timeout_str = os.getenv("AGENTQL_TIMEOUT", "30000")
        timeout_value = ''.join(c for c in timeout_str if c.isdigit())
        self.timeout = int(timeout_value) if timeout_value else 30000
        logger.info(f"AGENTQL_TIMEOUT parsed value: {self.timeout}")
        
        # Initialize AgentQL with API key
        self.agentql_api_key = os.getenv("AGENTQL_API_KEY")
        if not self.agentql_api_key:
            raise ValueError("AGENTQL_API_KEY environment variable is required")
            
        # Set AgentQL API key
        agentql.api_key = self.agentql_api_key
        logger.info("AgentQL API key set successfully")

    async def _wait_for_page_ready(self, page):
        """Helper method to wait for page to be fully loaded"""
        try:
            await page.wait_for_page_ready_state()
            # Add a longer delay for dynamic content and JS initialization
            await page.wait_for_timeout(2000)
        except Exception as e:
            logger.warning(f"Page ready state wait failed: {str(e)}")

    async def _wait_for_elements(self, page, query, max_retries=3):
        """Helper to wait for elements to be available with retries"""
        retry_count = 0
        while retry_count < max_retries:
            try:
                elements = await page.query_elements(query)
                if elements:
                    return elements
            except Exception as e:
                logger.warning(f"Attempt {retry_count + 1} failed to find elements: {str(e)}")
            
            retry_count += 1
            await page.wait_for_timeout(1000)
        return None

    async def _wait_and_click(self, element, page, delay_ms=500):
        """Helper to wait and click an element with logging"""
        if element:
            try:
                await page.wait_for_timeout(delay_ms)
                await element.click()
                return True
            except Exception as e:
                logger.warning(f"Failed to click element: {str(e)}")
        return False

    async def _handle_login_flow(self, page, store_config):
        """Handle the multi-step login flow"""
        try:
            # Initial page load and element detection
            logger.info("Waiting for initial page load...")
            await self._wait_for_page_ready(page)
            
            # Step 1: Find and click initial sign in button with retries
            elements = await self._wait_for_elements(page, STORE_INFO_QUERY)
            if not elements or not elements.header:
                logger.error("Could not find header section after retries")
                # Dump page content for debugging
                try:
                    content = await page.content()
                    logger.debug(f"Page content: {content[:500]}...")  # First 500 chars
                except Exception as e:
                    logger.error(f"Failed to get page content: {str(e)}")
                return False
                
            if not elements.header.sign_in_btn:
                logger.error("Could not find sign in button in header after retries")
                return False
                
            logger.info("Clicking initial sign in button")
            await self._wait_and_click(elements.header.sign_in_btn, page)
            await self._wait_for_page_ready(page)

            # Step 2: Handle "Shopped with us before?" modal
            welcome_elements = await page.query_elements(INITIAL_MODAL_QUERY)
            if welcome_elements and welcome_elements.welcome_modal:
                if welcome_elements.welcome_modal.sign_in_btn:
                    logger.info("Found welcome modal, clicking sign in")
                    await self._wait_and_click(welcome_elements.welcome_modal.sign_in_btn, page)
                    await self._wait_for_page_ready(page)
                else:
                    logger.warning("Welcome modal found but missing sign in button")

            # Step 3: Handle login options modal
            login_elements = await page.query_elements(LOGIN_OPTIONS_MODAL_QUERY)
            if not login_elements or not login_elements.login_modal:
                logger.error("Could not find login modal")
                return False
                
            logger.info("Found login options modal")
            
            # Enter email/phone
            if not login_elements.login_modal.email_box:
                logger.error("Could not find email input field")
                return False
                
            await login_elements.login_modal.email_box.fill(store_config.credentials.email)
            logger.info("Entered email")

            # Click password option
            if not login_elements.login_modal.password_btn:
                logger.error("Could not find password button")
                return False
                
            await self._wait_and_click(login_elements.login_modal.password_btn, page)
            await self._wait_for_page_ready(page)
            logger.info("Selected password login option")

            # Step 4: Handle password entry modal
            password_elements = await page.query_elements(PASSWORD_MODAL_QUERY)
            if not password_elements or not password_elements.password_modal:
                logger.error("Could not find password modal")
                return False
                
            logger.info("Found password modal")
            
            # Enter password
            if not password_elements.password_modal.password_box:
                logger.error("Could not find password input field")
                return False
                
            await password_elements.password_modal.password_box.fill(store_config.credentials.password)
            logger.info("Entered password")

            # Click sign in
            if not password_elements.password_modal.sign_in_btn:
                logger.error("Could not find sign in button in password modal")
                return False
                
            await self._wait_and_click(password_elements.password_modal.sign_in_btn, page)
            logger.info("Clicked sign in button")
            
            # Wait for login to complete and verify
            max_retries = 5
            retry_count = 0
            while retry_count < max_retries:
                await self._wait_for_page_ready(page)
                
                # Check if we're still on a login-related page
                current_url = str(page.url).lower()
                if any(x in current_url for x in ['/signin', '/login', '/account/sign-in']):
                    logger.warning(f"Still on login page after {retry_count + 1} attempts")
                    retry_count += 1
                    await page.wait_for_timeout(1000)  # Wait a second before retrying
                    continue
                    
                # Verify login success by checking for login elements
                verify_elements = await page.query_elements(STORE_INFO_QUERY)
                if verify_elements and verify_elements.header:
                    if not verify_elements.header.sign_in_btn:
                        logger.info("Login successful - sign in button no longer present")
                        return True
                    else:
                        logger.warning("Sign in button still present after login attempt")
                else:
                    logger.warning("Could not verify header elements after login attempt")
                
                retry_count += 1
                await page.wait_for_timeout(1000)
            
            logger.error("Failed to verify login completion after maximum retries")
            return False

        except Exception as e:
            logger.error(f"Error during login flow: {str(e)}")
            return False

    async def _navigate_to_coupons(self, page) -> bool:
        """Navigate to the coupons section of the store"""
        try:
            logger.info("Attempting to navigate to coupons section...")
            
            # Look for and click coupon link
            nav_result = await page.query_elements(COUPON_NAV_QUERY)
            if nav_result and nav_result.coupon_section and nav_result.coupon_section.nav_link:
                logger.info("Found coupon navigation link")
                await self._wait_for_page_ready(page)
                
                # Verify we're on the coupons page
                page_result = await page.query_elements(COUPON_PAGE_QUERY)
                if page_result and page_result.coupon_section and page_result.coupon_section.heading:
                    logger.info("Successfully navigated to coupons page")
                    return True
                    
            logger.warning("Could not find or navigate to coupons section")
            return False
            
        except Exception as e:
            logger.error(f"Error navigating to coupons: {str(e)}")
            return False

    async def _clip_coupons(self, page) -> List[Dict[str, Any]]:
        """Clip all available coupons on the page"""
        clipped_coupons = []
        try:
            logger.info("Starting to clip coupons...")
            
            while True:
                # Get current page of coupons
                page_result = await page.query_elements(COUPON_PAGE_QUERY)
                if not page_result or not page_result.coupon_section:
                    break
                
                coupons = page_result.coupon_section.available_coupons or []
                if not coupons:
                    logger.info("No more coupons found on page")
                    break
                
                # Process each coupon
                for coupon in coupons:
                    try:
                        if (coupon.clip_btn and 
                            coupon.clip_btn.exists and 
                            not coupon.clip_btn.is_clipped):
                            
                            # Click the clip button
                            logger.info(f"Attempting to clip coupon: {coupon.offer.title}")
                            await self._wait_and_click(coupon.clip_btn, page)
                            await self._wait_for_page_ready(page)
                            
                            # Verify clip was successful
                            verify = await page.query_elements(COUPON_PAGE_QUERY)
                            current_coupon = next(
                                (c for c in verify.coupon_section.available_coupons 
                                 if c.offer.title == coupon.offer.title), 
                                None
                            )
                            
                            if current_coupon and current_coupon.clip_btn.is_clipped:
                                logger.info(f"Successfully clipped coupon: {coupon.offer.title}")
                                clipped_coupons.append({
                                    "title": coupon.offer.title,
                                    "description": coupon.offer.description,
                                    "savings": coupon.offer.savings,
                                    "expiration": coupon.offer.expiration,
                                    "terms": coupon.offer.terms
                                })
                            else:
                                logger.warning(f"Failed to verify clip for coupon: {coupon.offer.title}")
                            
                    except Exception as e:
                        logger.error(f"Error clipping individual coupon: {str(e)}")
                        continue
                
                # Check for more coupons
                if (page_result.coupon_section.pagination and 
                    page_result.coupon_section.pagination.load_more_btn):
                    logger.info("Found 'Load More' button, loading next page...")
                    await self._wait_and_click(page_result.coupon_section.pagination.load_more_btn, page)
                    await self._wait_for_page_ready(page)
                else:
                    break
            
            logger.info(f"Finished clipping coupons. Total clipped: {len(clipped_coupons)}")
            return clipped_coupons
            
        except Exception as e:
            logger.error(f"Error in coupon clipping process: {str(e)}")
            return clipped_coupons

    async def clip_coupons(self, store_config: StoreConfig, user_id: int) -> Dict[str, Any]:
        """Main method to handle the coupon clipping process for any store"""
        result = {
            "success": False,
            "store": store_config.name,
            "clipped_coupons": [],
            "error": None
        }

        browser = None
        try:
            logger.info(f"Starting coupon clipping process for store: {store_config.name}")
            
            # Launch browser with stealth settings
            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=False,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                    '--no-sandbox',
                    '--disable-web-security',
                    '--disable-features=IsolateOrigins,site-per-process'
                ]
            )
            
            # Create context with realistic browser profile
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
                java_script_enabled=True,
                ignore_https_errors=True,
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                    'Cache-Control': 'max-age=0'
                }
            )
            
            try:
                # Try to load cached session
                session_dir = os.path.join(os.getcwd(), "app", "sessions", str(user_id))
                store_id = store_config.id or hash(str(store_config.base_url))
                session_file = os.path.join(session_dir, f"store_{store_id}_session.json")
                
                session_loaded = False
                if os.path.exists(session_file):
                    try:
                        # Load the session state into the context
                        await context.storage_state(path=session_file)
                        logger.info(f"Loaded cached session for user {user_id} from: {session_file}")
                        session_loaded = True
                    except Exception as e:
                        logger.warning(f"Failed to load cached session: {str(e)}")
                
                # Create and wrap page
                base_page = await context.new_page()
                page = await agentql.wrap_async(base_page)
                logger.info("Browser launched and page wrapped with AgentQL")
                
                # Navigate to main page
                logger.info(f"Navigating to main URL: {store_config.base_url}")
                await page.goto(str(store_config.base_url))
                await self._wait_for_page_ready(page)
                
                # If session was loaded, verify we're still logged in
                if session_loaded:
                    verify_elements = await self._wait_for_elements(page, STORE_INFO_QUERY)
                    if verify_elements and verify_elements.header and not verify_elements.header.sign_in_btn:
                        logger.info("Cached session is still valid")
                    else:
                        logger.warning("Cached session expired, falling back to full login")
                        session_loaded = False
                
                # Perform full login if needed
                if not session_loaded:
                    login_success = await self._handle_login_flow(page, store_config)
                    if not login_success:
                        result["error"] = "Failed to login"
                        logger.error("Login failed")
                        return result
                    
                    # Cache the new session
                    os.makedirs(session_dir, exist_ok=True)
                    await context.storage_state(path=session_file)
                    logger.info(f"Cached new session for user {user_id} to: {session_file}")

                # Navigate to coupons section
                if not await self._navigate_to_coupons(page):
                    result["error"] = "Failed to navigate to coupons section"
                    logger.error("Navigation to coupons failed")
                    return result

                # Clip all available coupons
                clipped_coupons = await self._clip_coupons(page)
                result["clipped_coupons"] = clipped_coupons
                result["success"] = len(clipped_coupons) > 0
                
                if result["success"]:
                    logger.info(f"Successfully clipped {len(clipped_coupons)} coupons")
                else:
                    logger.warning("No coupons were clipped")
                
            except Exception as e:
                logger.error(f"Error during coupon clipping process: {str(e)}")
                result["error"] = str(e)
                
            finally:
                await context.close()
                
        except Exception as e:
            logger.error(f"Failed to complete coupon clipping process: {str(e)}", exc_info=True)
            result["error"] = str(e)
        finally:
            if browser:
                await browser.close()
                logger.info("Browser closed")
                
        return result 