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
