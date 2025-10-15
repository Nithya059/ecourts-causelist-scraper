# ecourts_causelist_scraper.py
# Simple robust scraper to find and download PDFs from URLs in urls.txt
# Saves PDFs and a JSON summary into the 'causelists' folder.

import os
import requests
from bs4 import BeautifulSoup
import json
from datetime import datetime
from urllib.parse import urljoin, urlparse

# Constants
OUTPUT_DIR = os.path.join(os.getcwd(), "causelists")
URL_FILE = "urls.txt"
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
TIMEOUT = 20  # seconds

os.makedirs(OUTPUT_DIR, exist_ok=True)

def safe_filename(name: str) -> str:
    # Create filename safe for most filesystems
    keepchars = (" ", ".", "_", "-")
    out = "".join(c for c in name if c.isalnum() or c in keepchars).strip()
    return out.replace(" ", "_") or "file"

def fetch_page(url: str):
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
    resp.raise_for_status()
    return resp

def find_pdf_links(page_html: str, base_url: str):
    soup = BeautifulSoup(page_html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        # consider links that include .pdf or end with .pdf
        if ".pdf" in href.lower():
            full = urljoin(base_url, href)
            links.append(full)
    # deduplicate preserving order
    seen = set()
    out = []
    for u in links:
        if u not in seen:
            out.append(u)
            seen.add(u)
    return out

def download_pdf(url: str, out_dir: str):
    parsed = urlparse(url)
    fname = os.path.basename(parsed.path) or parsed.netloc
    fname = safe_filename(fname)
    if not fname.lower().endswith(".pdf"):
        fname = fname + ".pdf"
    dest = os.path.join(out_dir, fname)
    # avoid overwrite: add suffix if exists
    base, ext = os.path.splitext(dest)
    i = 1
    while os.path.exists(dest):
        dest = f"{base}_{i}{ext}"
        i += 1
    print(f"  -> Downloading: {url}")
    r = requests.get(url, headers=HEADERS, stream=True, timeout=TIMEOUT, allow_redirects=True)
    r.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    return dest

def save_html(html: str, out_dir: str, base_name: str):
    fn = safe_filename(base_name)
    if not fn.endswith(".html"):
        fn = fn + ".html"
    dest = os.path.join(out_dir, fn)
    with open(dest, "w", encoding="utf-8") as f:
        f.write(html)
    return dest

def main():
    results = []
    if not os.path.exists(URL_FILE):
        print(f"Error: {URL_FILE} not found in repository root. Create urls.txt with one URL per line.")
        return

    with open(URL_FILE, "r", encoding="utf-8") as fh:
        lines = [l.strip() for l in fh.readlines() if l.strip()]

    if not lines:
        print("No URLs found in urls.txt")
        return

    for url in lines:
        print(f"Processing: {url}")
        entry = {"url": url, "pdf_links": [], "downloaded": [], "html_saved": None, "error": None}
        try:
            # If the URL itself is a PDF:
            if url.lower().endswith(".pdf"):
                entry["pdf_links"].append(url)
                saved = download_pdf(url, OUTPUT_DIR)
                entry["downloaded"].append(saved)
                print(f"  Saved direct PDF -> {saved}")
                results.append(entry)
                continue

            # Fetch page
            resp = fetch_page(url)
            html = resp.text

            # Find PDF links
            pdfs = find_pdf_links(html, url)
            entry["pdf_links"] = pdfs

            if pdfs:
                for p in pdfs:
                    try:
                        saved = download_pdf(p, OUTPUT_DIR)
                        entry["downloaded"].append(saved)
                        print(f"  Saved -> {saved}")
                    except Exception as e:
                        print(f"  Failed to download {p}: {e}")
            else:
                # Save HTML fallback so you can inspect
                html_name = f"page_{(urlparse(url).netloc + urlparse(url).path).replace('/', '_')}"
                saved_html = save_html(html, OUTPUT_DIR, html_name)
                entry["html_saved"] = saved_html
                print(f"  No PDF links found. Saved HTML fallback -> {saved_html}")

        except Exception as e:
            entry["error"] = str(e)
            print(f"  Error processing {url}: {e}")

        results.append(entry)

    # save summary JSON
    ts = datetime.utcnow().strftime("%Y-%m-%d_%H%M%S")
    meta_file = os.path.join(OUTPUT_DIR, f"cause_list_summary_{ts}.json")
    with open(meta_file, "w", encoding="utf-8") as jf:
        json.dump(results, jf, indent=2, ensure_ascii=False)
    print(f"\nDone. Summary saved to: {meta_file}")
    print(f"Files saved in folder: {OUTPUT_DIR}")

if __name__ == "__main__":
    main()
