    import requests
from bs4 import BeautifulSoup
import os
import json
from datetime import datetime

# Create output folder
os.makedirs("causelists", exist_ok=True)

# Read URLs from urls.txt
with open("urls.txt", "r") as f:
    urls = [line.strip() for line in f if line.strip()]

# Store results
results = []

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
}

for url in urls:
    print(f"Fetching: {url}")
    try:
        r = requests.get(url, headers=headers, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        # Find all links ending with .pdf
        pdf_links = []
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().endswith(".pdf"):
                # Convert relative URL to absolute
                pdf_url = requests.compat.urljoin(url, href)
                pdf_links.append(pdf_url)

        # If no PDF links found, maybe this URL itself is a direct PDF
        if url.lower().endswith(".pdf"):
            pdf_links.append(url)

        downloaded = []
        for link in pdf_links:
            pdf_name = link.split("/")[-1]
            pdf_path = os.path.join("causelists", pdf_name)
            print(f"Downloading PDF: {link}")
            try:
                pdf_data = requests.get(link, headers=headers, timeout=20)
                with open(pdf_path, "wb") as f:
                    f.write(pdf_data.content)
                downloaded.append(pdf_name)
            except Exception as e:
                print(f"Error downloading {link}: {e}")

        results.append({
            "url": url,
            "pdfs_found": pdf_links,
            "pdfs_downloaded": downloaded
        })

    except Exception as e:
        print(f"Failed to fetch {url}: {e}")

# Save JSON summary
output_file = os.path.join("causelists", f"cause_list_{datetime.now().strftime('%Y-%m-%d')}.json")
with open(output_file, "w") as f:
    json.dump(results, f, indent=4)

print("Scraping complete.")
print(f"Results saved to {output_file}")
