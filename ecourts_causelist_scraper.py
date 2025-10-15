# ecourts_causelist_scraper.py
# Playwright-based robust scraper to find and download PDFs from URLs in urls.txt
# Saves PDFs and a JSON summary into the 'causelists' folder.

import os
import json
from datetime import datetime
from urllib.parse import urljoin, urlparse
from time import sleep

from bs4 import BeautifulSoup
import requests
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

OUTPUT_DIR = os.path.join(os.getcwd(), "causelists")
URL_FILE = "urls.txt"
TIMEOUT_MS = 60000  # page navigation timeout in ms
REQUEST_TIMEOUT = 60  # seconds for fallback requests
os.makedirs(OUTPUT_DIR, exist_ok=True)


def safe_filename(name: str) -> str:
    keepchars = (" ", ".", "_", "-")
    out = "".join(c for c in name if c.isalnum() or c in keepchars).strip()
    return out.replace(" ", "_") or "file"


def download_bytes_to_file(bts: bytes, out_path: str):
    with open(out_path, "wb") as f:
        f.write(bts)
    return out_path


def download_via_requests(url: str, referer: str = None, cookies: dict = None, headers: dict = None):
    headers = headers or {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/pdf,application/octet-stream,*/*;q=0.9",
    }
    if referer:
        headers["Referer"] = referer
    s = requests.Session()
    if cookies:
        s.cookies.update(cookies)
    r = s.get(url, headers=headers, timeout=REQUEST_TIMEOUT, allow_redirects=True, stream=True)
    r.raise_for_status()
    content_type = r.headers.get("Content-Type", "")
    # return bytes even if content-type isn't exactly pdf; caller can choose what to do
    return r.content, content_type


def ensure_unique_dest(out_dir: str, fname: str):
    dest = os.path.join(out_dir, fname)
    base, ext = os.path.splitext(dest)
    i = 1
    while os.path.exists(dest):
        dest = f"{base}_{i}{ext}"
        i += 1
    return dest


def try_download_from_anchor(page, anchor_handle, base_url, out_dir, context):
    """
    Try to trigger Playwright download by clicking the anchor. If no download event occurs,
    fall back to using context.request (Playwright request) or requests with cookies.
    Returns path on disk or None.
    """
    href = anchor_handle.get_attribute("href") or ""
    full = urljoin(base_url, href)
    fname = safe_filename(os.path.basename(urlparse(full).path) or urlparse(full).netloc)
    if not fname.lower().endswith(".pdf"):
        fname += ".pdf"
    dest = ensure_unique_dest(out_dir, fname)

    # Try clicking and waiting for download (works when anchor triggers a direct download)
    try:
        with page.expect_download(timeout=8000) as download_info:
            anchor_handle.click(force=True)
        download = download_info.value
        # save directly to dest
        download.save_as(dest)
        return dest
    except PlaywrightTimeoutError:
        # no download event - fallback to fetching the URL using Playwright's request context
        try:
            response = context.request.get(full, timeout=REQUEST_TIMEOUT * 1000)
            status = response.status
            if status != 200:
                return None
            body = response.body()
            # If content-type indicates pdf or body looks like PDF (starts with %PDF), save it
            ct = response.headers.get("content-type", "")
            if "pdf" in ct.lower() or (body and body[:4] == b"%PDF"):
                download_bytes_to_file(body, dest)
                return dest
            # else fallback to requests with cookies
        except Exception:
            pass

    # Last-resort: use requests with cookies from browser context
    try:
        cookies = {}
        for c in context.cookies():
            cookies[c["name"]] = c["value"]
        body, content_type = download_via_requests(full, referer=base_url, cookies=cookies)
        if body and (b"%PDF" in body[:8] or "pdf" in (content_type or "").lower()):
            download_bytes_to_file(body, dest)
            return dest
    except Exception:
        pass

    return None


def scrape_with_playwright(urls):
    results = []
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(accept_downloads=True)
        page = context.new_page()
        for url in urls:
            print(f"Processing: {url}")
            entry = {"url": url, "pdf_links": [], "downloaded": [], "html_saved": None, "error": None}
            try:
                # If URL is direct PDF: try to fetch via context.request or fallback to requests
                if url.lower().endswith(".pdf"):
                    entry["pdf_links"].append(url)
                    fname = safe_filename(os.path.basename(urlparse(url).path) or urlparse(url).netloc)
                    if not fname.lower().endswith(".pdf"):
                        fname += ".pdf"
                    dest = ensure_unique_dest(OUTPUT_DIR, fname)

                    # Try context.request.get first
                    try:
                        resp = context.request.get(url, timeout=REQUEST_TIMEOUT * 1000)
                        if resp.status == 200:
                            body = resp.body()
                            ct = resp.headers.get("content-type", "")
                            if b"%PDF" in body[:8] or "pdf" in ct.lower():
                                download_bytes_to_file(body, dest)
                                entry["downloaded"].append(dest)
                                print(f"  Saved direct PDF -> {dest}")
                                results.append(entry)
                                continue
                    except Exception as e:
                        # fallback below
                        pass

                    # fallback to requests
                    try:
                        body, content_type = download_via_requests(url)
                        if body and (b"%PDF" in body[:8] or "pdf" in (content_type or "").lower()):
                            download_bytes_to_file(body, dest)
                            entry["downloaded"].append(dest)
                            print(f"  Saved direct PDF (requests fallback) -> {dest}")
                        else:
                            print(f"  !! Direct URL did not return a PDF (Content-Type: {content_type})")
                    except Exception as e:
                        entry["error"] = str(e)
                        print(f"  Error downloading direct PDF: {e}")
                    results.append(entry)
                    continue

                # Navigate the page (handle JS)
                page.goto(url, timeout=TIMEOUT_MS, wait_until="domcontentloaded")
                sleep(1)  # let JS settle a bit
                html = page.content()
                soup = BeautifulSoup(html, "html.parser")

                # Find anchors that contain .pdf
                anchors = page.query_selector_all("a[href]")
                pdf_urls = []
                for a in anchors:
                    href = a.get_attribute("href") or ""
                    if ".pdf" in href.lower():
                        full = urljoin(url, href)
                        pdf_urls.append(full)

                # deduplicate preserving order
                seen = set()
                pdf_urls_unique = []
                for u in pdf_urls:
                    if u not in seen:
                        pdf_urls_unique.append(u)
                        seen.add(u)

                entry["pdf_links"] = pdf_urls_unique

                if pdf_urls_unique:
                    for pdf_link in pdf_urls_unique:
                        print(f"  Found pdf link: {pdf_link}")
                        # try to find the original anchor handle for this exact href to click
                        anchor_handle = None
                        try:
                            # Use CSS selector for a[href*=".pdf"] and match href attribute
                            candidate_handles = page.query_selector_all('a[href]')
                            for cand in candidate_handles:
                                h = cand.get_attribute("href") or ""
                                full = urljoin(url, h)
                                if full == pdf_link:
                                    anchor_handle = cand
                                    break
                        except Exception:
                            anchor_handle = None

                        saved = None
                        if anchor_handle:
                            saved = try_download_from_anchor(page, anchor_handle, url, OUTPUT_DIR, context)
                        else:
                            # If no handle (maybe anchor not present due to frames), try direct request with context cookies
                            try:
                                resp = context.request.get(pdf_link, timeout=REQUEST_TIMEOUT * 1000)
                                if resp.status == 200:
                                    body = resp.body()
                                    ct = resp.headers.get("content-type", "")
                                    if b"%PDF" in body[:8] or "pdf" in (ct or "").lower():
                                        fname = safe_filename(os.path.basename(urlparse(pdf_link).path) or urlparse(pdf_link).netloc)
                                        if not fname.lower().endswith(".pdf"):
                                            fname += ".pdf"
                                        dest = ensure_unique_dest(OUTPUT_DIR, fname)
                                        download_bytes_to_file(body, dest)
                                        saved = dest
                            except Exception:
                                saved = None

                        if not saved:
                            # last attempt: requests with cookies
                            try:
                                cookies = {}
                                for c in context.cookies():
                                    cookies[c["name"]] = c["value"]
                                body, content_type = download_via_requests(pdf_link, referer=url, cookies=cookies)
                                if body and (b"%PDF" in body[:8] or "pdf" in (content_type or "").lower()):
                                    fname = safe_filename(os.path.basename(urlparse(pdf_link).path) or urlparse(pdf_link).netloc)
                                    if not fname.lower().endswith(".pdf"):
                                        fname += ".pdf"
                                    dest = ensure_unique_dest(OUTPUT_DIR, fname)
                                    download_bytes_to_file(body, dest)
                                    saved = dest
                            except Exception:
                                saved = None

                        if saved:
                            entry["downloaded"].append(saved)
                            print(f"    Saved -> {saved}")
                        else:
                            print(f"    !! Failed to download -> {pdf_link}")

                else:
                    # no PDFs found — save HTML fallback for inspection
                    html_name = f"page_{(urlparse(url).netloc + urlparse(url).path).replace('/', '_')}"
                    fn = safe_filename(html_name)
                    if not fn.endswith(".html"):
                        fn += ".html"
                    saved_html = os.path.join(OUTPUT_DIR, fn)
                    with open(saved_html, "w", encoding="utf-8") as f:
                        f.write(html)
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

    # Save summary JSON
    ts = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    meta_file = os.path.join(OUTPUT_DIR, f"cause_list_summary_{ts}.json")
    with open(meta_file, "w", encoding="utf-8") as jf:
        json.dump(results, jf, indent=2, ensure_ascii=False)
    print(f"\nDone. Summary saved to: {meta_file}")
    print(f"Files saved in folder: {OUTPUT_DIR}")


def main():
    if not os.path.exists(URL_FILE):
        print(f"Error: {URL_FILE} not found in repository root. Create urls.txt with one URL per line.")
        return

    with open(URL_FILE, "r", encoding="utf-8") as fh:
        lines = [l.strip() for l in fh.readlines() if l.strip()]

    if not lines:
        print("No URLs found in urls.txt")
        return

    scrape_with_playwright(lines)


if __name__ == "__main__":
    main()
