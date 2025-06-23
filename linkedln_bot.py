import os
import asyncio
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Load environment variables
load_dotenv()
EMAIL = os.getenv("LINKEDIN_EMAIL")
PASS  = os.getenv("LINKEDIN_PASSWORD")

async def connect_with_message(profile_url: str, message: str) -> str:
    """
    1) Log in to LinkedIn
    2) Navigate to the target profile_url
    3) Click the blue "Connect" button via JS fallback
    4) Click "Add a note"
    5) Fill in the message and click "Send"
    """
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, slow_mo=50)
        page    = await browser.new_page()

        try:
            # 1) Log in
            await page.goto("https://www.linkedin.com/login", wait_until="networkidle")
            await page.fill("input#username", EMAIL)
            await page.fill("input#password", PASS)
            await page.click("button[type='submit']")

            # 2) Wait for search bar to confirm home page
            await page.wait_for_selector('input[placeholder="Search"]', timeout=15000)
            print("✅ Logged in: search bar detected on home page")

            # 3) Navigate to the target profile
            url = profile_url.replace("in.linkedin.com", "www.linkedin.com")
            print(f"🌐 Navigating to profile: {url}")
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)

            # short pause for LinkedIn's client scripts to render the header
            await page.wait_for_timeout(2000)
            print("✅ Profile DOM loaded (skipped brittle header selector)")

            # 4) Click Connect via JS fallback
            await page.wait_for_timeout(1000)
            clicked = await page.evaluate("""
                () => {
                    const btn = Array.from(document.querySelectorAll('button'))
                        .find(b => b.getAttribute('aria-label')?.endsWith('to connect'));
                    if (!btn) return false;
                    btn.scrollIntoView({block:'center'});
                    btn.click();
                    return true;
                }
            """)
            if clicked:
                print("✅ Clicked Connect via JS fallback")
            else:
                raise Exception("❌ Could not find Connect button in JS fallback")

            # 5) Click "Add a note"
            await page.get_by_role("button", name="Add a note").click(timeout=5000)
            print("✅ Clicked Add a note")

            # 6) Fill in your message and click "Send"
            await page.fill("textarea[name='message']", message)
            await page.click("button:has-text('Send')", timeout=50000)
            print("✅ Message sent")

            return "✅ Connection request sent!"

        except Exception as e:
            print(f"❌ Error during automation: {e}")
            raise

        finally:
            await browser.close()

# CLI tester
if __name__ == "__main__":
    import sys
    url = sys.argv[1] if len(sys.argv) > 1 else input("Profile URL: ")
    msg = sys.argv[2] if len(sys.argv) > 2 else input("Message: ")
    result = asyncio.run(connect_with_message(url, msg))
    print(result)