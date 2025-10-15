# app.py
# Flask app that uses Playwright to load eCourts cause list page,
# fill/select inputs, fetch PDF links and return PDF to the user.

import os
import io
from flask import Flask, render_template, request, send_file, jsonify
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from urllib.parse import urljoin, urlparse
import time

APP_PORT = int(os.environ.get("PORT", 5000))
EC_BASE = "https://services.ecourts.gov.in/ecourtindia_v6/?p=cause_list/"

app = Flask(__name__, template_folder="templates")

def find_option_value_by_text(page, select_selector, visible_text):
    """
    Helper to pick option by visible text (returns option value or None)
    """
    try:
        return page.evaluate(
            """(sel, text) => {
                const s = document.querySelector(sel);
                if (!s) return null;
                const opts = Array.from(s.options);
                const o = opts.find(x => (x.text || x.innerText || "").trim().toLowerCase() === text.trim().toLowerCase());
                return o ? o.value : null;
            }""",
            select_selector, visible_text
        )
    except Exception:
        return None

def navigate_and_get_pdf(state, district, complex_name, court_name, date_str, timeout_ms=60000):
    """
    Uses Playwright to open ecourts page, set selectors, click search,
    find PDF link and return bytes and filename.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        try:
            page.goto(EC_BASE, timeout=timeout_ms, wait_until="domcontentloaded")
        except PlaywrightTimeoutError:
            page.goto(EC_BASE, timeout=timeout_ms*2, wait_until="networkidle")

        # Wait a short time for JS to populate selects
        time.sleep(1.0)

        # Try common select selectors for state/district — many eCourt pages use 'state_code' etc.
        # We'll attempt a few common names; fallback to matching visible text.
        select_candidates = {
            "state": ['select[name="state"]','select[id="state"]','select[name="state_code"]','select#state'],
            "district": ['select[name="district"]','select[id="district"]','select[name="district_code"]','select#district'],
            "complex": ['select[name="court_complex"]','select[id="court_complex"]','select[name="courtcomplex"]'],
            "court": ['select[name="court_name"]','select[id="court_name"]','select[name="court"]']
        }

        # Utility to set select by value or by visible text
        def set_select(field_name, text_value):
            if not text_value:
                return False
            for sel in select_candidates.get(field_name, []):
                try:
                    # try to find option with matching visible text and get its value
                    val = find_option_value_by_text(page, sel, text_value)
                    if val:
                        page.select_option(sel, val)
                        return True
                    # else try to directly select by value (if user provided exact value)
                    page.select_option(sel, str(text_value))
                    return True
                except Exception:
                    continue
            # As last resort, try executing a script to set by matching innerText
            try:
                page.evaluate(
                    """(txt) => {
                        const selects = Array.from(document.querySelectorAll('select'));
                        for (const s of selects) {
                            for (const o of s.options) {
                                if ((o.text||'').trim().toLowerCase()===txt.trim().toLowerCase()) {
                                    s.value = o.value;
                                    const ev = new Event('change', { bubbles: true });
                                    s.dispatchEvent(ev);
                                    return true;
                                }
                            }
                        }
                        return false;
                    }""",
                    text_value
                )
                return True
            except Exception:
                return False

        # Set the fields (best-effort)
        set_select("state", state)
        time.sleep(0.3)
        set_select("district", district)
        time.sleep(0.3)
        set_select("complex", complex_name)
        time.sleep(0.3)
        set_select("court", court_name)
        time.sleep(0.3)

        # If there is a date input, attempt to set it (common names)
        try:
            for selector in ['input[name="cause_list_date"]','input[id="cause_list_date"]','input[name="date"]','input[type="date"]']:
                try:
                    el = page.query_selector(selector)
                    if el:
                        el.fill(date_str)
                        # trigger change events if needed
                        page.evaluate("(sel)=>{const e=document.querySelector(sel); if(e){e.dispatchEvent(new Event('input',{bubbles:true})); e.dispatchEvent(new Event('change',{bubbles:true}));}}", selector)
                        break
                except Exception:
                    continue
        except Exception:
            pass

        # Now try to click search/button - try common button texts
        clicked = False
        for txt in ["Get Cause List","Search","Get Cause List / Cause List","Submit","Proceed","Get CauseList","Get Cause"]: 
            try:
                el = page.query_selector(f"button:has-text('{txt}')")
                if el:
                    el.click()
                    clicked = True
                    break
            except Exception:
                continue

        # If not clicked, try to find anchors or inputs type submit
        if not clicked:
            try:
                el = page.query_selector('input[type="submit"], button[type="submit"]')
                if el:
                    el.click()
            except Exception:
                pass

        # Wait for results to appear — look for any link containing .pdf
        page.wait_for_timeout(1500)
        # Try to locate any anchor with .pdf
        anchors = page.query_selector_all("a[href]")
        pdf_links = []
        for a in anchors:
            href = a.get_attribute("href") or ""
            if ".pdf" in href.lower():
                full = urljoin(EC_BASE, href)
                pdf_links.append(full)

        # If no PDF links found on page, try network requests for links (some sites embed)
        # If still empty, save HTML for debugging and return error
        if not pdf_links:
            # return page content as debug info
            html = page.content()
            browser.close()
            return {"error": "no_pdf_found", "html": html}

        # Try to download first pdf link using Playwright request
        pdf_url = pdf_links[0]
        try:
            resp = context.request.get(pdf_url, timeout=60000)
            if resp.status != 200:
                # fallback: try normal download via page click (and wait for download)
                try:
                    download = page.wait_for_event("download", timeout=8000)
                except Exception:
                    pass
            data = resp.body()
            # detect filename
            parsed = urlparse(pdf_url)
            name = os.path.basename(parsed.path) or "cause_list.pdf"
            browser.close()
            return {"pdf_bytes": data, "filename": name}
        except Exception as e:
            browser.close()
            return {"error": "download_failed", "exception": str(e)}

@app.route("/", methods=["GET"])
def index():
    # Simple UI served
    return render_template("index.html")

@app.route("/fetch", methods=["POST"])
def fetch():
    # Accept JSON or form data
    state = request.form.get("state") or request.json.get("state") if request.is_json else request.form.get("state")
    district = request.form.get("district") or request.json.get("district") if request.is_json else request.form.get("district")
    complex_name = request.form.get("complex") or request.json.get("complex") if request.is_json else request.form.get("complex")
    court_name = request.form.get("court") or request.json.get("court") if request.is_json else request.form.get("court")
    date_str = request.form.get("date") or request.json.get("date") if request.is_json else request.form.get("date")

    # Validate
    if not any([state, district, complex_name, court_name, date_str]):
        return jsonify({"ok": False, "error": "Provide at least one field (state/district/complex/court/date)."}), 400

    res = navigate_and_get_pdf(state or "", district or "", complex_name or "", court_name or "", date_str or "")
    if res.get("error"):
        # helpful debug response
        return jsonify({"ok": False, "reason": res.get("error"), "html_snippet": (res.get("html")[:2000] if res.get("html") else None)}), 500

    pdf_bytes = res.get("pdf_bytes")
    filename = res.get("filename", "cause_list.pdf")
    return send_file(io.BytesIO(pdf_bytes), download_name=filename, as_attachment=True, mimetype="application/pdf")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=APP_PORT)
