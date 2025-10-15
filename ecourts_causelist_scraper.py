# ecourts_causelist_scraper.py
# Updated version using Playwright (headless browser)
# Works even for sites that block requests or load PDFs dynamically.

import os
import json
from datetime import datetime
from urllib.parse import urlparse
from playwright.sync_api import sync_playwright

# === SETTINGS ===
OUTPUT_DIR = os.path.join(os.getcwd(), "causelists")
URL_FILE = "urls.txt"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def safe_filename(name: str) -> str:
    keep = (" ", ".", "_", "-")
    out = "".join(c for c in name if c.isalnum() or c in keep).strip()
    return out.replace(" ", "_") or "file"


def save_file(url, content):
    parsed = urlparse(url)
    fname = safe_filename(os.path.basename(parsed.path))
    if not fname.lower().endswith(".pdf"):
        fname += ".pdf"
    path = os.path.join(OUTPUT_DIR, fname)
    with open(path, "wb") as f:
        f.write(content)
    return path


def main():
    results = []
    if not os.path.exists(URL_FILE):
        print("❌ Error: urls.txt not found")
        return

    with open(URL_FILE, "r", encoding="utf-8") as f:
        urls = [x.strip() for x in f.readlines() if x.strip()]

    if not urls:
        print("❌ No URLs found in urls.txt")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()

        for url in urls:
            print(f"\n🌐 Processing: {url}")
            entry = {"url": url, "pdf_links": [], "downloaded": [], "error": None}
            try:
                if url.lower().endswith(".pdf"):
                    print("Direct PDF link found — downloading...")
                    r = page.request.get(url)
                    if r.ok:
                        saved = save_file(url, r.body())
                        entry["pdf_links"].append(url)
                        entry["downloaded"].append(saved)
                        print(f"✅ Saved direct PDF -> {saved}")
                    else:
                        entry["error"] = f"Download failed ({r.status})"
                else:
                    page.goto(url, timeout=60000)
                    anchors = page.query_selector_all("a[href]")
                    pdfs = []
                    for a in anchors:
                        href = a.get_attribute("href")
                        if href and ".pdf" in href.lower():
                            pdfs.append(page.urljoin(href))
                    pdfs = list(dict.fromkeys(pdfs))  # unique
                    entry["pdf_links"] = pdfs

                    if pdfs:
                        for pdf in pdfs:
                            print(f"📄 Downloading: {pdf}")
                            r = page.request.get(pdf)
                            if r.ok:
                                saved = save_file(pdf, r.body())
                                entry["downloaded"].append(saved)
                                print(f"✅ Saved -> {saved}")
                            else:
                                print(f"⚠️ Failed: {pdf} ({r.status})")
                    else:
                        entry["error"] = "No PDF links found."

            except Exception as e:
                entry["error"] = str(e)
                print(f"❌ Error: {e}")

            results.append(entry)

        browser.close()

    ts = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    summary_path = os.path.join(OUTPUT_DIR, f"cause_list_summary_{ts}.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Done. Summary saved to {summary_path}")
    print("📁 Files saved in: causelists/")


if __name__ == "__main__":
    main()
