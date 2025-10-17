# ecourts_causelist_scraper.py
# Playwright-based scraper to find and download PDFs from URLs in urls.txt
# Saves PDFs and a JSON summary into the 'causelists' folder.

import os
import json
from datetime import datetime
from urllib.parse import urljoin, urlparse
from time import sleep
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

OUTPUT_DIR = os.path.join(os.getcwd(), "causelists")
URL_FILE = "urls.txt"
PAGE_TIMEOUT = 60000  # ms
REQUEST_TIMEOUT = 60  # seconds

os.makedirs(OUTPUT_DIR, exist_ok=True)


def safe_filename(name: str) -> str:
    keepchars = (" ", ".", "_", "-")
    out = "".join(c for c in name if c.isalnum() or c in keepchars).strip()
    return out.replace(" ", "_") or "file"


def ensure_unique(dest: str) -> str:
    base, ext = os.path.splitext(dest)
    i = 1
    while os.path.exists(dest):
        dest = f"{base}_{i}{ext}"
        i += 1
    return dest


def save_bytes(b: bytes, out_path: str) -> str:
    with open(out_path, "wb") as f:
        f.write(b)
    return out_path


def download_via_context(context, url: str, referer: str = None):
    try:
        resp = context.request.get(url, timeout=REQUEST_TIMEOUT * 1000)
        if resp.status != 200:
            return None, f"HTTP {resp.status}"
        body = resp.body()
        return body, resp.headers.get("content-type", "")
    except Exception as e:
        return None, str(e)


def download_pdf_bytes(bytes_data, filename):
    fname = safe_filename(filename)
    if not fname.lower().endswith(".pdf"):
        fname += ".pdf"
    dest = os.path.join(OUTPUT_DIR, fname)
    dest = ensure_unique(dest)
    save_bytes(bytes_data, dest)
    return dest


def process_urls(urls):
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()

        for url in urls:
            print(f"Processing: {url}")
            entry = {"url": url, "pdf_links": [], "downloaded": [], "html_saved": None, "error": None}
            try:
                if url.lower().endswith(".pdf"):
                    # direct pdf link: try downloading
                    entry["pdf_links"].append(url)
                    body, info = download_via_context(context, url)
                    if body and (b"%PDF" in body[:8] or "pdf" in (info or "").lower()):
                        filename = os.path.basename(urlparse(url).path) or "file.pdf"
                        saved = download_pdf_bytes(body, filename)
                        entry["downloaded"].append(saved)
                        print(f"  Saved direct PDF -> {saved}")
                    else:
                        entry["error"] = f"Direct link did not return PDF ({info})"
                    results.append(entry)
                    continue

                # navigate page (handles JS)
                try:
                    page.goto(url, timeout=PAGE_TIMEOUT, wait_until="domcontentloaded")
                except PlaywrightTimeoutError:
                    page.goto(url, timeout=PAGE_TIMEOUT * 2, wait_until="networkidle")

                sleep(1)  # allow scripts to run

                # find anchors with .pdf in href
                anchors = page.query_selector_all("a[href]")
                pdf_links = []
                for a in anchors:
                    href = a.get_attribute("href") or ""
                    if ".pdf" in href.lower():
                        full = urljoin(url, href)
                        pdf_links.append(full)

                # deduplicate preserving order
                seen = set()
                uniq = []
                for u in pdf_links:
                    if u not in seen:
                        uniq.append(u)
                        seen.add(u)

                entry["pdf_links"] = uniq

                if uniq:
                    for pdf_link in uniq:
                        print(f"  Found pdf link: {pdf_link}")
                        # first try context.request.get
                        body, info = download_via_context(context, pdf_link, referer=url)
                        if body and (b"%PDF" in body[:8] or "pdf" in (info or "").lower()):
                            filename = os.path.basename(urlparse(pdf_link).path) or "file.pdf"
                            saved = download_pdf_bytes(body, filename)
                            entry["downloaded"].append(saved)
                            print(f"    Saved -> {saved}")
                            continue

                        # else try clicking and capturing download event
                        try:
                            # try to find the anchor element matching this href
                            selector = f'a[href="{pdf_link}"], a[href*="{os.path.basename(pdf_link)}"]'
                            handle = page.query_selector(selector)
                            if handle:
                                try:
                                    with page.expect_download(timeout=8000) as download_info:
                                        handle.click(force=True)
                                    dl = download_info.value
                                    fname = dl.suggested_filename or os.path.basename(urlparse(pdf_link).path) or "file.pdf"
                                    dest = os.path.join(OUTPUT_DIR, safe_filename(fname))
                                    dest = ensure_unique(dest)
                                    dl.save_as(dest)
                                    entry["downloaded"].append(dest)
                                    print(f"    Saved via click -> {dest}")
                                    continue
                                except Exception:
                                    pass
                        except Exception:
                            pass

                        # last resort: try using requests (no cookies transfer)
                        try:
                            import requests
                            headers = {"User-Agent": "Mozilla/5.0"}
                            r = requests.get(pdf_link, headers=headers, timeout=REQUEST_TIMEOUT, stream=True)
                            if r.status_code == 200 and ("pdf" in (r.headers.get("Content-Type","") or "").lower() or r.content[:4]==b"%PDF"):
                                fname = os.path.basename(urlparse(pdf_link).path) or "file.pdf"
                                dest = os.path.join(OUTPUT_DIR, safe_filename(fname))
                                dest = ensure_unique(dest)
                                with open(dest,"wb") as f:
                                    for ch in r.iter_content(8192):
                                        if ch:
                                            f.write(ch)
                                entry["downloaded"].append(dest)
                                print(f"    Saved via requests -> {dest}")
                                continue
                        except Exception as e:
                            print(f"    requests fallback failed: {e}")

                        print(f"    !! Failed to download -> {pdf_link}")

                else:
                    # save page HTML for inspection
                    html_name = f"page_{(urlparse(url).netloc + urlparse(url).path).replace('/', '_')}"
                    if not html_name.endswith(".html"):
                        html_name += ".html"
                    saved_html = os.path.join(OUTPUT_DIR, safe_filename(html_name))
                    saved_html = ensure_unique(saved_html)
                    with open(saved_html, "w", encoding="utf-8") as fh:
                        fh.write(page.content())
                    entry["html_saved"] = saved_html
                    print(f"  No PDF links found. Saved HTML fallback -> {saved_html}")

            except Exception as e:
                entry["error"] = str(e)
                print(f"  Error processing {url}: {e}")

            results.append(entry)

        try:
            browser.close()
        except Exception:
            pass

    # save summary
    ts = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    meta = os.path.join(OUTPUT_DIR, f"cause_list_summary_{ts}.json")
    with open(meta, "w", encoding="utf-8") as jf:
        json.dump(results, jf, indent=2, ensure_ascii=False)
    print(f"\nDone. Summary saved to: {meta}")
    print(f"Files saved in folder: {OUTPUT_DIR}")
    return results


def main():
    if not os.path.exists(URL_FILE):
        print(f"Error: {URL_FILE} not found in repository root.")
        return
    with open(URL_FILE, "r", encoding="utf-8") as fh:
        lines = [l.strip() for l in fh if l.strip()]
    if not lines:
        print("No URLs found in urls.txt")
        return
    process_urls(lines)


if __name__ == "__main__":
    main()
