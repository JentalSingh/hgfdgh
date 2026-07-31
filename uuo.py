#!/usr/bin/env python
# coding: utf-8

# In[ ]:


#!/usr/bin/env python
# coding: utf-8

# In[ ]:


#!/usr/bin/env python
# coding: utf-8

# In[ ]:


"""
Drury - Assessment Report Upload (Playwright + Proxy Rotation)
URL: https://www.lrapa-or.gov/forms/asbestos-abatement/
PDF: ba590df0f5a717af170927090483b811.pdf
"""

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
import time
import json
import random
from pathlib import Path

# ============================================================
# CONFIGURATION
# ============================================================
BASE_DIR = Path(__file__).resolve().parent
TARGET_URL = "https://www.larkin.edu/dps-applications/"
PDF_NAME = "c2281af181eaa959a7ee2d0db27dffec.pdf"
PDF_PATH = BASE_DIR / "input_pdfs" / PDF_NAME

# Proxy file (one proxy per line, format: ip:port or ip:port:user:pass)
PROXY_FILE = BASE_DIR / "proxies.txt"

# ============================================================
# PROXY FUNCTIONS
# ============================================================
def load_proxies():
    """Load proxies from file"""
    proxies = []
    if PROXY_FILE.exists():
        with open(PROXY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    proxies.append(line)
        print(f"✅ Loaded {len(proxies)} proxies")
    else:
        print(f"⚠️ Proxy file not found: {PROXY_FILE}")
    return proxies

def parse_proxy(proxy_str):
    """Parse proxy string to Playwright proxy dict"""
    proxy_str = proxy_str.replace('http://', '').replace('https://', '')
    parts = proxy_str.split(':')
    if len(parts) == 4:
        # ip:port:user:pass
        return {
            "server": f"http://{parts[0]}:{parts[1]}",
            "username": parts[2],
            "password": parts[3]
        }
    elif len(parts) == 2:
        # ip:port
        return {"server": f"http://{parts[0]}:{parts[1]}"}
    else:
        return None

def get_random_proxy():
    proxies = load_proxies()
    if not proxies:
        return None
    proxy_str = random.choice(proxies)
    return parse_proxy(proxy_str)

# ============================================================
# MAIN FUNCTION
# ============================================================
def main():
    print("\n" + "="*70)
    print("📄 DRURY - ASSESSMENT REPORT UPLOAD (PLAYWRIGHT + PROXY ROTATION)")
    print("="*70)
    print(f"📁 Target: {TARGET_URL}")
    print(f"📄 PDF: {PDF_NAME}")
    print("="*70)
    print("ℹ️  Proxy rotation enabled – tries random proxies")
    print("ℹ️  180 second polling – URL milte hi exit")
    print("="*70)

    if not PDF_PATH.exists():
        print(f"❌ PDF not found: {PDF_PATH}")
        return

    proxies = load_proxies()
    use_proxy = bool(proxies)

    max_attempts = 3 if use_proxy else 1
    attempt = 0
    success = False

    while attempt < max_attempts and not success:
        attempt += 1
        print(f"\n🔄 Attempt {attempt}/{max_attempts}")

        # Pick a proxy
        proxy_config = None
        if use_proxy:
            proxy_config = get_random_proxy()
            if proxy_config:
                print(f"🌐 Using proxy: {proxy_config.get('server')}")
            else:
                print("🌐 Direct connection (fallback)")

        with sync_playwright() as p:
            browser = None
            context = None
            page = None

            try:
                # Launch browser with proxy (if any)
                browser = p.chromium.launch(
                    headless=False,
                    args=[
                        "--start-maximized",
                        "--no-sandbox",
                        "--disable-dev-shm-usage",
                        "--ignore-certificate-errors",
                        "--disable-blink-features=AutomationControlled",
                        "--disable-gpu"
                    ]
                )

                context_options = {
                    "viewport": {"width": 1920, "height": 1080},
                    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                }
                if proxy_config:
                    context_options["proxy"] = proxy_config

                context = browser.new_context(**context_options)
                page = context.new_page()

                # ============================================================
                # INJECT MONITOR SCRIPT (XHR/Fetch & DOM watcher)
                # ============================================================
                page.add_init_script("""
                    (() => {
                        window.__pdf_url = null;
                        window.__upload_done = false;

                        const capture = (txt) => {
                            if (!txt) return;
                            let m = txt.match(/https?:\\/\\/[^"']+\\.pdf/);
                            if (m) {
                                window.__pdf_url = m[0].replace(/\\\\\\//g, "/");
                                window.__upload_done = true;
                                console.log('✅ URL captured:', window.__pdf_url);
                                return;
                            }
                            try {
                                let j = JSON.parse(txt);
                                let s = JSON.stringify(j);
                                let x = s.match(/https?:\\/\\/[^"']+\\.pdf/);
                                if (x) {
                                    window.__pdf_url = x[0].replace(/\\\\\\//g, "/");
                                    window.__upload_done = true;
                                    console.log('✅ URL from JSON:', window.__pdf_url);
                                }
                            } catch(e) {}
                        };

                        // Override XHR
                        const open = XMLHttpRequest.prototype.open;
                        const send = XMLHttpRequest.prototype.send;
                        XMLHttpRequest.prototype.open = function() {
                            this.addEventListener("load", () => capture(this.responseText));
                            return open.apply(this, arguments);
                        };
                        XMLHttpRequest.prototype.send = function() {
                            return send.apply(this, arguments);
                        };

                        // Override fetch
                        const origFetch = window.fetch;
                        window.fetch = function(...args) {
                            return origFetch.apply(this, args).then(response => {
                                const clone = response.clone();
                                clone.text().then(text => capture(text)).catch(() => {});
                                return response;
                            });
                        };

                        // DOM watcher for "Remove" links or file name text
                        const obs = new MutationObserver(() => {
                            if (window.__pdf_url) return;
                            document.querySelectorAll("input, a, [data-file]").forEach(e => {
                                let v = e.value || e.href || e.getAttribute('data-file') || "";
                                if (v && v.includes(".pdf")) {
                                    window.__pdf_url = v;
                                    window.__upload_done = true;
                                    console.log('✅ URL from DOM:', v);
                                }
                            });
                        });
                        obs.observe(document.documentElement, {
                            subtree: true,
                            childList: true,
                            attributes: true
                        });
                        console.log('✅ Monitor script injected');
                    })();
                """)

                # ============================================================
                # NAVIGATE
                # ============================================================
                print(f"\n🌐 Opening: {TARGET_URL}")
                page.goto(TARGET_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_load_state("load", timeout=30000)
                print("✅ Page loaded")
                time.sleep(3)

                # ============================================================
                # CLEAR PREVIOUS UPLOADS (if any)
                # ============================================================
                print("\n🗑️  Clearing previous uploads...")
                try:
                    # Click any "Remove" links
                    remove_btns = page.locator(".wpforms-remove-file, .remove-file, [class*='remove']")
                    count = remove_btns.count()
                    for i in range(count):
                        btn = remove_btns.nth(i)
                        if btn.is_visible() and btn.is_enabled():
                            btn.click()
                            time.sleep(1)
                except:
                    pass

                try:
                    # Clear file inputs
                    file_inputs = page.locator("input[type='file']")
                    count = file_inputs.count()
                    for i in range(count):
                        inp = file_inputs.nth(i)
                        inp.evaluate("el => el.value = ''")
                except:
                    pass

                # ============================================================
                # FIND FILE INPUT
                # ============================================================
                file_input = None
                selectors = [
                    "input[type='file'][accept*='.pdf']",
                    "input[type='file']",
                    ".wpforms-file-upload input",
                    "input[name*='file']",
                ]
                for selector in selectors:
                    elem = page.locator(selector).first
                    if elem.count() > 0 and elem.is_enabled():
                        file_input = elem
                        print(f"✅ Found file input: {selector}")
                        break

                if not file_input:
                    # Try XPath fallback
                    elem = page.locator("//input[@type='file']").first
                    if elem.count() > 0:
                        file_input = elem
                        print("✅ Found file input via XPath")
                    else:
                        raise Exception("No file input found")

                # Make sure it's visible
                file_input.evaluate("""
                    el => {
                        el.style.display = 'block';
                        el.style.visibility = 'visible';
                        el.style.opacity = '1';
                        el.style.height = 'auto';
                        el.style.width = 'auto';
                        el.style.position = 'relative';
                        el.scrollIntoView({behavior: 'smooth', block: 'center'});
                    }
                """)
                time.sleep(1)

                # ============================================================
                # UPLOAD PDF
                # ============================================================
                print(f"\n📤 Uploading: {PDF_PATH.name}")
                file_input.set_input_files(str(PDF_PATH))
                print("✅ PDF uploaded!")
                time.sleep(3)

                # ============================================================
                # POLLING – 180 seconds
                # ============================================================
                print("\n📡 Capturing upload URL...")
                print("⏳ Polling for 180 seconds...")
                pdf_url = None
                deadline = time.time() + 180

                while time.time() < deadline:
                    elapsed = int(time.time() - (deadline - 180))
                    remaining = int(deadline - time.time())

                    if elapsed % 10 == 0 and elapsed > 0:
                        print(f"   ⏳ {elapsed}s elapsed - {remaining}s remaining")

                    # Check if URL captured in page context
                    url = page.evaluate("() => window.__pdf_url")
                    if url:
                        pdf_url = url
                        print(f"\n✅ URL captured after {elapsed}s!")
                        break

                    # Also check network responses directly (Playwright's native)
                    # We could also add a response listener but we already have injection.
                    time.sleep(1)
                else:
                    print("\n❌ URL NOT FOUND after 180 seconds")

                # ============================================================
                # SAVE SCREENSHOT
                # ============================================================
                page.screenshot(path=str(BASE_DIR / "drury_result.png"))
                print("📸 Screenshot saved")

                # ============================================================
                # RESULTS
                # ============================================================
                print("\n" + "="*70)
                if pdf_url:
                    pdf_url = pdf_url.replace('\\/', '/')
                    print("✅ SUCCESS!")
                    print(f"🔗 PDF URL: {pdf_url}")
                    with open(BASE_DIR / "drury_url.txt", "w") as f:
                        f.write(pdf_url)
                    print(f"📁 URL saved to: drury_url.txt")
                    success = True
                else:
                    print("⚠️ Upload completed but URL not captured")
                    print("💡 Check screenshot")
                print("="*70)

                if success:
                    break

            except Exception as e:
                print(f"❌ Error on attempt {attempt}: {e}")
                import traceback
                traceback.print_exc()
            finally:
                if browser:
                    browser.close()
                    print("✅ Browser closed")

    if not success:
        print("\n❌ All attempts failed.")

if __name__ == "__main__":
    main()

