# ecourts_causelist_scraper.py
# Author: Your Name
# Goal: Fetch cause list from Indian eCourts site and optionally download PDFs

import requests
from bs4 import BeautifulSoup
import json
import os
from datetime import date

# Folder to save cause list files
SAVE_DIR = "causelists"
os.makedirs(SAVE_DIR, exist_ok=True)

# Input file that contains court URLs
URL_FILE = "urls.txt"

def fetch_html(url):
    """Fetch HTML content of a given URL"""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.text
    except Exception as e:
        print(f"Error fetching {url}: {e}")
        return None

def parse_cause_list(html):
    """Parse cause list details from the court page"""
    soup = BeautifulSoup(html, "html.parser")
    cause_list = []

    # This selector may need adjustment based on court site structure
    rows = soup.find_all("tr")
    for row in rows:
        cols = row.find_all("td")
        if len(cols) >= 3:
            case = {
                "serial_no": cols[0].get_text(strip=True),
                "case_no": cols[1].get_text(strip=True),
                "party": cols[2].get_text(strip=True)
            }
            cause_list.append(case)
    return cause_list

def download_pdf(url, filename):
    """Download cause list PDF if available"""
    try:
        response = requests.get(url, stream=True)
        if response.status_code == 200:
            filepath = os.path.join(SAVE_DIR, filename)
            with open(filepath, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
            print(f"PDF saved: {filepath}")
    except Exception as e:
        print(f"PDF download failed: {e}")

def main():
    if not os.path.exists(URL_FILE):
        print("⚠️ Please add a file named 'urls.txt' with court URLs.")
        return

    with open(URL_FILE, "r") as f:
        urls = [line.strip() for line in f.readlines() if line.strip()]

    all_data = {}
    for url in urls:
        print(f"\nFetching: {url}")
        html = fetch_html(url)
        if not html:
            continue

        cause_list = parse_cause_list(html)
        all_data[url] = cause_list

        # Try finding a link to PDF
        soup = BeautifulSoup(html, "html.parser")
        pdf_link = soup.find("a", href=lambda h: h and ".pdf" in h.lower())
        if pdf_link:
            pdf_url = pdf_link["href"]
            filename = f"CauseList_{date.today()}.pdf"
            download_pdf(pdf_url, filename)
        else:
            print("No PDF found on this page.")

    # Save all cause list data as JSON
    json_file = os.path.join(SAVE_DIR, f"cause_list_{date.today()}.json")
    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(all_data, f, indent=4, ensure_ascii=False)
    print(f"\n✅ Cause list saved to {json_file}")

if __name__ == "__main__":
    main()
