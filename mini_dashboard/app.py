from flask import Flask, render_template, request
import json

app = Flask(__name__)

# Load cause list JSON
try:
    with open("../cause_list.json") as f:
        cases = json.load(f)["cases"]
except FileNotFoundError:
    cases = []

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
    app.run(debug=True)
