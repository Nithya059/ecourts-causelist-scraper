from flask import Flask, render_template, request
import json
import argparse
from datetime import datetime, timedelta
import os

app = Flask(__name__)

# Load cause list JSON
json_path = os.path.join("..", "cause_list.json")
try:
    with open(json_path) as f:
        cases = json.load(f).get("cases", [])
except FileNotFoundError:
    cases = []

# ---------------- CLI FLAGS ---------------- #
parser = argparse.ArgumentParser(description="Mini eCourts Dashboard CLI")
parser.add_argument("--today", action="store_true", help="Show today's cases")
parser.add_argument("--tomorrow", action="store_true", help="Show tomorrow's cases")
parser.add_argument("--causelist", action="store_true", help="Show all cases")
parser.add_argument("--search", type=str, help="Search by CNR")
parser.add_argument("--count", action="store_true", help="Show total cases")
args = parser.parse_args()

filtered_cases = cases

if args.today:
    today_str = datetime.now().strftime("%d-%m-%Y")
    filtered_cases = [c for c in cases if c.get("Date") == today_str]
elif args.tomorrow:
    tomorrow_str = (datetime.now() + timedelta(days=1)).strftime("%d-%m-%Y")
    filtered_cases = [c for c in cases if c.get("Date") == tomorrow_str]
elif args.search:
    query = args.search.strip().lower()
    filtered_cases = [c for c in cases if query in c["CNR"].lower()]

if args.count:
    print(f"Total cases: {len(filtered_cases)}")
    exit()

# Replace original cases with filtered ones for dashboard
cases = filtered_cases

# ---------------- FLASK ROUTE ---------------- #
@app.route("/", methods=["GET", "POST"])
def index():
    query = ""
    results = cases
    if request.method == "POST":
        query = request.form.get("cnr", "").strip()
        results = [case for case in cases if query.lower() in case["CNR"].lower()]
        if not results:
            results = []
    return render_template("index.html", cases=results, query=query)

if __name__ == "__main__":
    # Run Flask dashboard
    app.run(debug=True)
