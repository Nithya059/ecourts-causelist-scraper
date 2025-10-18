# eCourts Cause List Scraper 🏛️

## 📖 Overview
This project is part of my internship task — a Python script that scrapes cause lists from Indian eCourts website and downloads the PDF if available.

## 🚀 Features
- Fetch court cause lists automatically.
- Save details as JSON.
- Download PDF of cause list if found.
- Easy to extend and automate.

## 🧩 Files
| File | Purpose |
|------|----------|
| `ecourts_causelist_scraper.py` | Main script |
| `requirements.txt` | Python dependencies |
| `urls.txt` | Court URLs list |
| `.gitignore` | Ignore unnecessary files |
| `causelists/` | Folder to store outputs |

## ⚙️ How It Works
1. Reads URLs from `urls.txt`.
2. Fetches HTML pages.
3. Parses the cause list table.
4. Finds and downloads PDF (if link found).
5. Saves all info into `causelists/cause_list_<date>.json`.

## 📦 Installation & Usage
You can run this project locally (if needed):


pip install -r requirements.txt
python ecourts_causelist_scraper.py



### ⚡ Run the Workflow
1. Go to **Actions → Court Data Fetcher**.
2. Click **Run workflow → Run workflow**.
3. Wait 1–2 minutes — GitHub will:
- Fetch PDFs  
- Parse the data  
- Create `cause_list.json` in the repo



### 📁 View Output Files
After the workflow finishes:
- Go to your repository **Files tab**
- Open the `data/` folder
- You’ll see:
- `cause_list.pdf` — downloaded file
- `cause_list.json` — parsed data

---

### 💻 View Mini Dashboard
To view the data dashboard:

1. Open the **`index.html`** file in your repo.  
2. Click **“Raw”** → then long press and copy the link.  
3. Visit
https://htmlpreview.github.io/?https://raw.githubusercontent.com/Nithya059/ecourts-causelist-scraper/main/mini_dashboard/index.html
5. Paste your raw file link — your dashboard will open instantly!


