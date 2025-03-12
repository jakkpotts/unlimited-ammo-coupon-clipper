import agentql
from playwright.async_api import async_playwright
from app.schemas.store import StoreConfig, StoreDiscovery
from typing import Optional
import logging
import os
from urllib.parse import urlparse, urljoin

logger = logging.getLogger(__name__)

# Define AgentQL queries
STORE_INFO_QUERY = """
{
    header {
        title(The page title from the document head)
        sign_in_button(A button with text "Sign in" in the header navigation)
    }
}
"""

INITIAL_MODAL_QUERY = """
{
    welcome_modal(A modal asking if you've shopped before) {
        sign_in_button(A button with text "Sign in")
        create_account_button(A button with text "Create account")
        close_button(A button to close the modal)
    }
}
"""

LOGIN_OPTIONS_MODAL_QUERY = """
{
    login_modal(A "Welcome back!" modal with login options) {
        email_input(An input field for email or mobile number)
        passwordless_button(A button with text "Sign in without a password")
        password_button(A button with text "Sign in with password")
        create_account_link(A link with text "Create account")
        business_account_link(A link with text "Create a business account")
    }
}
"""

PASSWORD_MODAL_QUERY = """
{
    password_modal(A modal for password entry) {
        email_display(Text showing the email being used)
        change_email_link(A link to change the email)
        password_input(A password input field)
        show_password_button(A button to show/hide password)
        forgot_password_link(A link for forgotten passwords)
        sign_in_button(A button to submit the login)
        verification_code_link(A link to use verification code instead)
    }
}
"""

class StoreDiscoveryService:
    def __init__(self):
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
            # Add a small delay for any remaining dynamic content
            await page.wait_for_timeout(500)
        except Exception as e:
            logger.warning(f"Page ready state wait failed: {str(e)}")

    async def analyze_store(self, discovery_config: StoreDiscovery) -> Optional[StoreConfig]:
        """Analyze a store website using AgentQL to determine its configuration"""
        async with async_playwright() as playwright:
            # Launch browser with stealth settings
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
                # Create and wrap page
                base_page = await context.new_page()
                page = await agentql.wrap_async(base_page)
                logger.info("Browser launched and page wrapped with AgentQL")
                
                # Add random delay before navigation
                await page.wait_for_timeout(1000 + (hash(str(discovery_config.url)) % 1000))
                
                # Navigate to the URL
                logger.info(f"Attempting to navigate to URL: {discovery_config.url}")
                await page.goto(str(discovery_config.url))
                await self._wait_for_page_ready(page)
                logger.info("Page loaded successfully")
                
                # Get store information and elements
                elements = await page.query_elements(STORE_INFO_QUERY)
                logger.info("Found store elements")
                
                if not elements or not elements.header:
                    logger.error("Could not find header elements")
                    return None
                
                # Get store name from page title
                store_name = None
                if elements.header.title:
                    try:
                        store_name = await elements.header.title.text_content()
                        # Clean up common title suffixes
                        common_suffixes = [
                            '| Official Site',
                            '| Home',
                            '| Online Grocery Shopping',
                            '- Official Site',
                            '- Home',
                            '- Online Grocery Shopping'
                        ]
                        for suffix in common_suffixes:
                            if store_name.endswith(suffix):
                                store_name = store_name[:-len(suffix)]
                        # Clean up whitespace
                        store_name = ' '.join(store_name.split()).strip()
                    except Exception as e:
                        logger.warning(f"Could not get page title: {str(e)}")
                
                if not store_name:
                    store_name = urlparse(str(discovery_config.url)).netloc.split('.')[0].title()
                    logger.info(f"Using fallback store name: {store_name}")
                
                # Get sign in button and extract login URL
                login_url = None
                parsed_url = urlparse(str(discovery_config.url))
                base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                domain = parsed_url.netloc.lower()

                if elements.header.sign_in_button:
                    try:
                        # Try to get href attribute
                        login_url = await elements.header.sign_in_button.get_attribute('href')
                        if login_url and not login_url.startswith('http'):
                            login_url = urljoin(base_url, login_url)
                    except Exception as e:
                        logger.warning(f"Could not get href from sign in button: {str(e)}")
                
                # Handle specific store login URLs
                if not login_url:
                    if 'albertsons' in domain:
                        login_url = f"{base_url}/account/sign-in"
                        logger.info("Using Albertsons-specific login URL")
                    else:
                        # Default fallback
                        login_url = f"{base_url}/signin"
                        logger.info("Using default fallback login URL")

                logger.info(f"Final login URL: {login_url}")
                
                # Create store config
                store_config = StoreConfig(
                    name=str(store_name),
                    base_url=base_url,
                    login_url=login_url,
                    credentials=discovery_config.credentials
                )
                logger.info(f"Created store config with credentials: {store_config.credentials}")
                
                return store_config
                
            except Exception as e:
                logger.error(f"Failed during store analysis: {str(e)}")
                return None
            finally:
                await context.close()
                await browser.close()

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
            # Step 1: Click initial sign in button
            elements = await page.query_elements(STORE_INFO_QUERY)
            if elements and elements.header and elements.header.sign_in_button:
                logger.info("Clicking initial sign in button")
                await self._wait_and_click(elements.header.sign_in_button, page)
                await self._wait_for_page_ready(page)

            # Step 2: Handle "Shopped with us before?" modal
            welcome_elements = await page.query_elements(INITIAL_MODAL_QUERY)
            if welcome_elements and welcome_elements.welcome_modal:
                logger.info("Found welcome modal, clicking sign in")
                await self._wait_and_click(welcome_elements.welcome_modal.sign_in_button, page)
                await self._wait_for_page_ready(page)

            # Step 3: Handle login options modal
            login_elements = await page.query_elements(LOGIN_OPTIONS_MODAL_QUERY)
            if login_elements and login_elements.login_modal:
                logger.info("Found login options modal")
                
                # Enter email/phone
                if login_elements.login_modal.email_input:
                    await login_elements.login_modal.email_input.fill(store_config.credentials.email)
                    logger.info("Entered email")

                # Click password option
                if login_elements.login_modal.password_button:
                    await self._wait_and_click(login_elements.login_modal.password_button, page)
                    await self._wait_for_page_ready(page)
                    logger.info("Selected password login option")

            # Step 4: Handle password entry modal
            password_elements = await page.query_elements(PASSWORD_MODAL_QUERY)
            if password_elements and password_elements.password_modal:
                logger.info("Found password modal")
                
                # Enter password
                if password_elements.password_modal.password_input:
                    await password_elements.password_modal.password_input.fill(store_config.credentials.password)
                    logger.info("Entered password")

                # Click sign in
                if password_elements.password_modal.sign_in_button:
                    await self._wait_and_click(password_elements.password_modal.sign_in_button, page)
                    await self._wait_for_page_ready(page)
                    logger.info("Submitted login form")

                return True

            return False

        except Exception as e:
            logger.error(f"Error during login flow: {str(e)}")
            return False

    async def verify_login(self, store_config: StoreConfig, user_id: int) -> bool:
        """Verify login credentials work for the store"""
        async with async_playwright() as playwright:
            # Launch browser with stealth settings
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
                # Create and wrap page
                base_page = await context.new_page()
                page = await agentql.wrap_async(base_page)
                logger.info("Browser launched and page wrapped with AgentQL")
                
                # Navigate to main page
                logger.info(f"Navigating to main URL: {store_config.base_url}")
                await page.goto(str(store_config.base_url))
                await self._wait_for_page_ready(page)
                
                # Handle the multi-step login flow
                login_success = await self._handle_login_flow(page, store_config)
                if not login_success:
                    logger.error("Failed to complete login flow")
                    return False

                # Verify successful login
                try:
                    await self._wait_for_page_ready(page)
                    
                    # Check if we're still on a login-related page
                    current_url = page.url
                    if any(x in current_url.lower() for x in ['/signin', '/login', '/account/sign-in']):
                        logger.error("Still on login page after submission - login likely failed")
                        return False
                    
                    logger.info(f"Successfully navigated to: {current_url}")
                    
                    # Cache the authenticated session with user-specific path
                    session_dir = os.path.join(os.getcwd(), "app", "sessions", str(user_id))
                    os.makedirs(session_dir, exist_ok=True)
                    
                    # Use store ID or base_url as unique identifier for the session file
                    store_id = store_config.id or hash(str(store_config.base_url))
                    session_file = os.path.join(session_dir, f"store_{store_id}_session.json")
                    
                    # Save the authenticated session state
                    await context.storage_state(path=session_file)
                    logger.info(f"Cached authenticated session for user {user_id} to: {session_file}")
                    
                    return True
                    
                except Exception as e:
                    logger.error(f"Error during post-login verification: {str(e)}")
                    return False
                
            except Exception as e:
                logger.error(f"Failed during login verification: {str(e)}")
                return False
            finally:
                await context.close()
                await browser.close()

    async def load_cached_session(self, store_config: StoreConfig, user_id: int, context) -> bool:
        """Load cached session for a store if available"""
        try:
            session_dir = os.path.join(os.getcwd(), "app", "sessions", str(user_id))
            store_id = store_config.id or hash(str(store_config.base_url))
            session_file = os.path.join(session_dir, f"store_{store_id}_session.json")
            
            if os.path.exists(session_file):
                # Load the session state into the context
                await context.storage_state(path=session_file)
                logger.info(f"Loaded cached session for user {user_id} from: {session_file}")
                return True
            else:
                logger.warning(f"No cached session found for user {user_id} and store: {store_config.name}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to load cached session: {str(e)}")
            return False 