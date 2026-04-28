#!/usr/bin/env python3
# ===== GATISHAKTI PH-30 PORTAL (FULL — ALL 36 COLUMNS) =====

import socketserver
from http.server import SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from sqlalchemy import create_engine, text
import os, socket, socketserver, webbrowser, traceback, secrets, csv
from datetime import date, datetime

# ================= DB CONFIG =================
engine = create_engine(
    "postgresql://postgres:postgres@192.168.1.156:5432/Indian_Railway",
    connect_args={"options": "-csearch_path=gatishakti"},
    pool_pre_ping=True
)

# ================= MASTER BLOCK DATA =================
# Format: block_section -> list of (direction, tvu, agency)
BLOCK_DATA = {
    "DUG-RSM":  [("East", 84666, "CPM/GS/NAG")],
    "SKS-AGN":  [("", "", "CPM/GS/NAG")],

    "RSM-MUP": [
        ("East", 38545, "CPM/GS/NAG"),
        ("East", 48211, "CPM/GS/NAG"),
    ],

    "BAKL-MUA": [
        ("East", 30109, "CPM/GS/NAG"),
        ("East", 9733,  "CPM/GS/NAG"),
    ],

    "RJN-BAKL": [
        ("East", 19520, "CPM/GS/NAG"),
        ("East", 34694, "CPM/GS/NAG"),
    ],

    "JTR-DGG": [
        ("East", 22692, "CPM/GS/NAG"),
        ("East", 25374, "CPM/GS/NAG"),
    ],

    "BTC-KGE": [
        ("North", "",    "CPM/GS/NAG"),
        ("North", "",    "CPM/GS/NAG"),
        ("North", "",    "CPM/GS/NAG"),
        ("North", 38993, "CPM/GS/NAG"),
        ("North", 49872, "CPM/GS/NAG"),
    ],

    "G-GJ": [
        ("",      "",    "CPM/GS/NAG"),
        ("East",  52900, "CPM/GS/NAG"),
    ],

    "BRD-KT": [
        ("Central", 105294, "CPM/GS/NAG"),
        ("Central",  34977, "CPM/GS/NAG"),
    ],

    "G-CAF":   [("", "", "CPM/GS/NAG")] * 10,
    "G-BTC":   [("", "", "CPM/GS/NAG")] * 3,
    "G-JBP":   [("", "", "CPM/GS/NAG")] * 2,
    "TMR-TRDI":[("", "", "CPM/GS/NAG")] * 6,
    "HTT-BTC": [("South", 53268, "CPM/GS/NAG")],
}

# ================= INIT DB =================
def init_db():
    with engine.begin() as db:
        db.execute(text("CREATE SCHEMA IF NOT EXISTS gatishakti"))
        db.execute(text("""
        CREATE TABLE IF NOT EXISTS ph30_lc_projects (
            id                      SERIAL PRIMARY KEY,
            lc_no                   VARCHAR(50),
            km                      VARCHAR(50),
            block_section           VARCHAR(100),
            sectional_den           VARCHAR(100),
            tvu                     INTEGER,
            executing_agency        VARCHAR(100),
            sanction_year           VARCHAR(20),
            sanction_date           DATE,
            rob_rub                 VARCHAR(20),
            gad                     VARCHAR(50),
            gad_status              VARCHAR(50),
            lc_closure_permission   VARCHAR(50),
            collector_consent_date  DATE,
            cost_sharing            VARCHAR(5),
            state_estimate_sanction VARCHAR(100),
            estimate_position       VARCHAR(5),
            estimate_status         VARCHAR(100),
            crs_construction        VARCHAR(5),
            crs_closure             VARCHAR(5),
            crs_shifting            VARCHAR(5),
            tender_flag             VARCHAR(5),
            tender_status           VARCHAR(100),
            drawing_approved        VARCHAR(5),
            land_acq_required       VARCHAR(5),
            land_area               VARCHAR(50),
            st_clearance            VARCHAR(50),
            st_clearance_date       DATE,
            sanctioned_cost         NUMERIC(12,2),
            railway_share           NUMERIC(12,2),
            state_share             NUMERIC(12,2),
            exp_upto_mar24          NUMERIC(12,2),
            outlay                  NUMERIC(12,2),
            exp_2024_25             NUMERIC(12,2),
            exp_upto_date           NUMERIC(12,2),
            progress                NUMERIC(5,2),
            tdc                     DATE,
            remarks                 TEXT,
            created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """))

        # Add missing columns if table already existed with fewer columns
        for col, defn in [
            ("lc_closure_permission",  "VARCHAR(100)"),
            ("collector_consent_date", "DATE"),
            ("cost_sharing",           "VARCHAR(5)"),
            ("state_estimate_sanction","VARCHAR(255)"),
            ("estimate_position",      "VARCHAR(5)"),
            ("crs_construction",       "VARCHAR(5)"),
            ("crs_closure",            "VARCHAR(5)"),
            ("crs_shifting",           "VARCHAR(5)"),
            ("tender_flag",            "VARCHAR(5)"),
            ("tender_status",          "VARCHAR(255)"),
            ("drawing_approved",       "VARCHAR(5)"),
            ("land_acq_required",      "VARCHAR(5)"),
            ("land_area",              "VARCHAR(50)"),
            ("st_clearance",           "VARCHAR(100)"),
            ("st_clearance_date",      "DATE"),
            ("sanctioned_cost",        "NUMERIC(14,2)"),
            ("railway_share",          "NUMERIC(14,2)"),
            ("state_share",            "NUMERIC(14,2)"),
            ("exp_upto_mar24",         "NUMERIC(14,2)"),
            ("outlay",                 "NUMERIC(14,2)"),
            ("exp_2024_25",            "NUMERIC(14,2)"),
            ("exp_upto_date",          "NUMERIC(14,2)"),
        ]:
            try:
                db.execute(text(
                    f"ALTER TABLE ph30_lc_projects ADD COLUMN IF NOT EXISTS {col} {defn}"
                ))
            except Exception:
                pass

        # Fix columns that existed as wrong types in older versions of the table
        for col, new_type in [
            ("sanction_year",  "VARCHAR(20)  USING sanction_year::VARCHAR"),
            ("gad",            "VARCHAR(100) USING gad::VARCHAR"),
            ("gad_status",     "VARCHAR(255) USING gad_status::VARCHAR"),
            ("tender_status",  "VARCHAR(255) USING tender_status::VARCHAR"),
            ("estimate_status","VARCHAR(255) USING estimate_status::VARCHAR"),
            ("land_area",      "VARCHAR(50)  USING land_area::VARCHAR"),
        ]:
            try:
                db.execute(text(
                    f"ALTER TABLE ph30_lc_projects ALTER COLUMN {col} TYPE {new_type}"
                ))
            except Exception:
                pass

init_db()

# ================= HELPERS =================
def respond(handler, html):
    handler.send_response(200)
    handler.send_header("Content-type", "text/html; charset=utf-8")
    handler.end_headers()
    handler.wfile.write(html.encode("utf-8"))

def safe_date(val):
    return val if val and val.strip() else None

def safe_num(val, default=None):
    try:
        return float(val) if val and str(val).strip() else default
    except (ValueError, TypeError):
        return default

# ================= HANDLER =================
class Handler(SimpleHTTPRequestHandler):

    def do_GET(self):
        path = urlparse(self.path).path
        routes = {
            "/":          self.home,
            "/ph30":      self.ph30_form,
            "/ph30_view": self.ph30_view,
        }
        return routes.get(path, lambda: respond(self, "<h2>404 Not Found</h2>"))()

    def do_POST(self):
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode("utf-8")
        q = parse_qs(body)
        if path == "/save_ph30":
            return self.save_ph30(q)
        if path == "/delete_ph30":
            return self.delete_ph30(q)
        respond(self, "<h2>404</h2>")

    # ================= HOME =================
    def home(self):
        return respond(self, """<!DOCTYPE html>
<html>
<head>
<meta charset='utf-8'>
<title>GatiShakti PH-30 Portal</title>

<style>
:root {
  --bg: #020617;
  --card: rgba(30, 41, 59, 0.6);
  --border: rgba(255, 255, 255, 0.08);
  --primary: #3b82f6;
  --secondary: #22c55e;
  --text: #e2e8f0;
  --muted: #94a3b8;
}

/* Base */
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
  font-family: 'Inter', sans-serif;
}

body {
  background: radial-gradient(circle at top, #7DAACB, #E8DBB3);
  color: var(--text);    
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* Main container */
.wrapper {
  text-align: center;
}

/* Title */
h1 {
  font-size: 36px;
  font-weight: 600;
  margin-bottom: 10px;
  color: black;
}

.subtitle {
  color: var(--muted);
  margin-bottom: 40px;
  font-size: 14px;
}

/* Cards container */
.container {
  display: flex;
  gap: 30px;
  justify-content: center;
}

/* Card */
.card {
  backdrop-filter: blur(14px);
  background: var(--card);
  border: 1px solid var(--border);
  padding: 35px;
  border-radius: 18px;
  width: 240px;
  text-decoration: none;
  color: var(--text);
  transition: 0.3s ease;
  position: relative;
  overflow: hidden;
}

/* Glow effect */
.card::before {
  content: "";
  position: absolute;
  inset: 0;
  background: linear-gradient(120deg, transparent, rgba(255,255,255,0.1), transparent);
  opacity: 0;
  transition: 0.3s;
}

.card:hover::before {
  opacity: 5;
}

/* Hover lift */
.card:hover {
  transform: translateY(-8px) scale(1.02);
  border-color: rgba(255, 0, 0, 0.2);
}

/* Icons */
.icon {
  font-size: 32px;
  margin-bottom: 12px;
}

/* Button accents */
.primary {
  box-shadow: 0 0 25px rgba(59,130,246,0.2);
}

.secondary {
  box-shadow: 0 0 25px rgba(34,197,94,0.2);
}

/* Footer */
.footer {
  margin-top: 50px;
  font-size: 12px;
  color: var(--muted);
}
</style>

</head>

<body>

<div class="wrapper">

  <h1>🚄 GatiShakti PH-30</h1>
  <div class="subtitle">Smart Level Crossing Management Portal</div>

  <div class="container">

    <a href="/ph30" class="card primary">
      <div class="icon">➕</div>
      <div>Add New Entry</div>
    </a>

    <a href="/ph30_view" class="card secondary">
      <div class="icon">📊</div>
      <div>View Dashboard</div>
    </a>

  </div>

  <div class="footer">
    © 2026 GatiShakti | Inspired UI
  </div>

</div>

</body>
</html>""")

    # ================= FORM =================
    def ph30_form(self):
        import json as _json

        block_options = "\n".join(
            f"<option value='{b}'>{b}</option>" for b in sorted(BLOCK_DATA.keys())
        )

        # Build JSON BEFORE the f-string so it can be interpolated directly
        json_block = _json.dumps(BLOCK_DATA)

        html = """<!DOCTYPE html>
<html>
<head>
<meta charset='utf-8'>
<title>PH-30 Entry</title>

<style>
:root {
  --bg: #f8f5fb;
  --card: #ffffff;
  --border: #e5e7eb;
  --text: #0f172a;
  --muted: #64748b;
  --primary: #6366f1;
}

/* Base */
* {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

/* Body */
body {
  font-family: 'PanRoman', sans-serif;
  background: radial-gradient(circle at top, #7DAACB, #E8DBB3);
  color: var(--text);
  padding: 40px 20px;
  font-family: 'CWindowsFonts', 'Inter', sans-serif;
}

/* Headings */
h1, h2, h3 {
  font-family: 'CWindowsFonts', sans-serif;
}

/* Title */
h2 {
  text-align: center;
  margin-bottom: 35px;
  font-size: 34px;
  font-weight: 600;
  letter-spacing: -0.5px;
}

/* Card */
.card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 20px;
  padding: 24px;
  margin-bottom: 18px;
  box-shadow: 0 8px 25px rgba(0,0,0,0.04);
}

/* Section */
.sec {
  font-size: 13px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  color: var(--muted);
  margin-bottom: 18px;
}

/* Grid */
.g4, .g3, .g2 {
  display: grid;
  gap: 18px;
}

.g4 { grid-template-columns: repeat(4, 1fr); }
.g3 { grid-template-columns: repeat(3, 1fr); }
.g2 { grid-template-columns: repeat(2, 1fr); }

.s2 { grid-column: span 2; }
.s3 { grid-column: span 3; }
.s4 { grid-column: span 4; }

/* Fields */
.f {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.f label {
  font-size: 13px;
  color: var(--muted);
}

/* Inputs */
.f input,
.f select,
.f textarea {
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: 25px;
  padding: 10px 12px;
  font-size: 14px;
  color: var(--text);
  transition: all 0.2s ease;

  /* IMPORTANT: font applied */
  font-family: 'CWindowsFonts', 'Inter', sans-serif;
}

/* Placeholder */
.f input::placeholder,
.f textarea::placeholder {
  color: #000000;
  font-family: 'CWindowsFonts', 'Inter', sans-serif;
}

/* Focus */
.f input:focus,
.f select:focus,
.f textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 2px rgba(99,102,241,0.15);
}

/* Textarea */
.f textarea {
  min-height: 80px;
}

/* Seg buttons */
.seg {
  display: flex;
  border-radius: 25px;
  overflow: hidden;
  border: 1px solid var(--border);
}

.seg button {
  flex: 1;
  background: transparent;
  border: none;
  padding: 9px;
  cursor: pointer;
  color: var(--muted);
  font-size: 13px;
  transition: 0.2s;

  font-family: 'CWindowsFonts', sans-serif;
}

.seg button:hover {
  background: #f1f5f9;
}

.seg .y {
  background: #ecfdf5;
  color: #16a34a;
  font-weight: 500;
}

.seg .n {
  background: #fef2f2;
  color: #dc2626;
  font-weight: 500;
}

/* Buttons */
.actions {
  display: flex;
  gap: 12px;
  margin-top: 18px;
}

.btn {
  flex: 1;
  padding: 12px;
  border-radius: 50px;
  font-weight: 500;
  font-size: 14px;
  cursor: pointer;
  border: none;
  transition: 0.2s;

  font-family: 'CWindowsFonts', sans-serif;
}

/* Primary */
.btn-save {
  background: var(--primary);
  color: rgb(0, 0, 0);
}

.btn-save:hover {
  opacity: 0.9;
}

/* Back */
.btn-back {
  background: #808285;
  color: #0f172a;
  text-align: center;
  text-decoration: none;
  line-height: 44px;
}

/* Message */
#msg {
  text-align: center;
  padding: 10px;
  border-radius: 8px;
  margin-top: 12px;
  display: none;
  font-size: 13px;

  font-family: 'CWindowsFonts', sans-serif;
}

/* Responsive */
@media(max-width:900px) {
  .g4 { grid-template-columns: repeat(2,1fr); }
}

@media(max-width:500px) {
  .g3, .g2 { grid-template-columns: 1fr; }
}
</style>

</head>

<body>

<h2>🚄 PH-30 Full Entry</h2>

<form id="ph30form">

<!-- SECTION 1: LOCATION -->
  <div class="card">
    <div class="sec">Location &amp; Identity</div>
    <div class="g4">
      <div class="f"><label>LC No.</label>
        <input name="lc_no" placeholder="e.g. LC-142"></div>
      <div class="f"><label>KM</label>
        <input name="km" placeholder="e.g. 214+300"></div>
      <div class="f s2"><label>Block Section</label>
        <select id="block_section" name="block_section" onchange="fillBlock(this.value)">
          <option value="">-- Select --</option>
        </select>
      </div>
      <div class="f s2"><label>Sectional Sr. DEN / DEN</label>
        <input name="sectional_den" id="sectional_den" placeholder="Auto-filled or manual"></div>
      <div class="f"><label>TVU</label>
        <input name="tvu" id="tvu" placeholder="Auto-filled or manual"></div>
      <div class="f"><label>Executing Agency</label>
        <input name="executing_agency" id="executing_agency" placeholder="Auto-filled or manual"></div>
    </div>
  </div>

<!-- SECTION 2: SANCTION -->
  <div class="card">
    <div class="sec">Sanction Details</div>
    <div class="g4">
      <div class="f"><label>Year of Sanction</label>
        <input name="sanction_year" placeholder="e.g. 2022-23"></div>
      <div class="f"><label>Date of Sanction</label>
        <input type="date" name="sanction_date"></div>
      <div class="f"><label>ROB / RUB</label>
        <input name="rob_rub" placeholder="ROB / RUB"></div>
      <div class="f"><label>GAD No.</label>
        <input name="gad" placeholder="GAD No."></div>
      <div class="f"><label>GAD Status</label>
        <input name="gad_status" placeholder="Approved / Pending"></div>
      <div class="f"><label>LC Closing Permission</label>
        <input name="lc_closure_permission" placeholder="Granted / Awaited"></div>
      <div class="f"><label>Date of Collector Consent</label>
        <input type="date" name="collector_consent_date"></div>
    </div>
  </div>

<!-- SECTION 3: COST SHARING & ESTIMATES -->
  <div class="card">
    <div class="sec">Cost Sharing &amp; Estimates</div>
    <div class="g4">
      <div class="f">
        <label>Cost Sharing Y/N</label>
        <div class="seg">
          <button type="button" class="y" onclick="tog(this,'cost_sharing','Y')">Y</button>
          <button type="button"          onclick="tog(this,'cost_sharing','N')">N</button>
        </div>
        <input type="hidden" name="cost_sharing" value="Y">
      </div>
      <div class="f s3"><label>Sanction of Estimate by State Govt.</label>
        <input name="state_estimate_sanction" placeholder="Sanctioned / Awaited / NA"></div>
      <div class="f">
        <label>Estimate Position Y/N</label>
        <div class="seg">
          <button type="button" class="y" onclick="tog(this,'estimate_position','Y')">Y</button>
          <button type="button"          onclick="tog(this,'estimate_position','N')">N</button>
        </div>
        <input type="hidden" name="estimate_position" value="Y">
      </div>
      <div class="f s3"><label>Estimate Status</label>
        <input name="estimate_status" placeholder="Final / Provisional / Under prep."></div>
    </div>
  </div>

<!-- SECTION 4: CRS & CLEARANCES -->
  <div class="card">
    <div class="sec">CRS Sanctions &amp; Clearances</div>
    <div class="g3" style="margin-bottom:10px">
      <div class="f">
        <label>CRS Sanction – Construction</label>
        <div class="seg">
          <button type="button" class="y" onclick="tog(this,'crs_construction','Y')">Yes</button>
          <button type="button"          onclick="tog(this,'crs_construction','N')">No</button>
        </div>
        <input type="hidden" name="crs_construction" value="Y">
      </div>
      <div class="f">
        <label>CRS Sanction – LC Closure</label>
        <div class="seg">
          <button type="button" class="y" onclick="tog(this,'crs_closure','Y')">Yes</button>
          <button type="button"          onclick="tog(this,'crs_closure','N')">No</button>
        </div>
        <input type="hidden" name="crs_closure" value="Y">
      </div>
      <div class="f">
        <label>CRS Sanction – LC Shifting</label>
        <div class="seg">
          <button type="button" class="y" onclick="tog(this,'crs_shifting','Y')">Yes</button>
          <button type="button"          onclick="tog(this,'crs_shifting','N')">No</button>
        </div>
        <input type="hidden" name="crs_shifting" value="Y">
      </div>
      <div class="f">
        <label>Tender Position Y/N</label>
        <div class="seg">
          <button type="button" class="y" onclick="tog(this,'tender_flag','Y')">Y</button>
          <button type="button"          onclick="tog(this,'tender_flag','N')">N</button>
        </div>
        <input type="hidden" name="tender_flag" value="Y">
      </div>
      <div class="f">
        <label>Structural Drawing Approved</label>
        <div class="seg">
          <button type="button" class="y" onclick="tog(this,'drawing_approved','Y')">Yes</button>
          <button type="button"          onclick="tog(this,'drawing_approved','N')">No</button>
        </div>
        <input type="hidden" name="drawing_approved" value="Y">
      </div>
      <div class="f">
        <label>Land Acquisition Involved Y/N</label>
        <div class="seg">
          <button type="button" class="y" onclick="tog(this,'land_acq_required','Y')">Y</button>
          <button type="button"          onclick="tog(this,'land_acq_required','N')">N</button>
        </div>
        <input type="hidden" name="land_acq_required" value="Y">
      </div>
    </div>
    <div class="g4">
      <div class="f s2"><label>Tender Status</label>
        <input name="tender_status" placeholder="NIT floated / Under eval. / Awarded"></div>
      <div class="f"><label>Area of Land Acquisition (Sqm)</label>
        <input name="land_area" placeholder="0.00"></div>
      <div class="f"><label>S&amp;T Clearance</label>
        <input name="st_clearance" placeholder="Given / Awaited / NA"></div>
      <div class="f"><label>S&amp;T Clearance Date</label>
        <input type="date" name="st_clearance_date"></div>
    </div>
  </div>

<!-- SECTION 5: FINANCIAL -->
  <div class="card">
    <div class="sec">Financial (₹ Cr)</div>
    <div class="g4">
      <div class="f"><label>Sanctioned Cost</label>
        <input name="sanctioned_cost" placeholder="0.00"></div>
      <div class="f"><label>Railway Share</label>
        <input name="railway_share" placeholder="0.00"></div>
      <div class="f"><label>State Share</label>
        <input name="state_share" placeholder="0.00"></div>
      <div class="f"><label>Exp. upto Mar-24</label>
        <input name="exp_upto_mar24" placeholder="0.00"></div>
      <div class="f"><label>Outlay</label>
        <input name="outlay" placeholder="0.00"></div>
      <div class="f"><label>Exp. during 2024-25</label>
        <input name="exp_2024_25" placeholder="0.00"></div>
      <div class="f"><label>Exp. upto Date</label>
        <input name="exp_upto_date" placeholder="0.00"></div>
      <div class="f"><label>% Progress</label>
        <input name="progress" placeholder="0 – 100"></div>
      <div class="f"><label>TDC</label>
        <input type="date" name="tdc"></div>
    </div>
  </div>

<!-- SECTION 6: REMARKS -->
  <div class="card">
    <div class="sec">Remarks</div>
    <div class="f">
      <textarea name="remarks" placeholder="Additional remarks…"></textarea>
    </div>
  </div>

  <div class="actions">
    <a href="/" class="btn btn-back">← Back</a>
    <button type="button" class="btn btn-save" onclick="saveEntry()">💾 Save Entry</button>
  </div>
  <div id="msg"></div>

</form>

<script>
// ================= MASTER BLOCK DATA =================
// Format: block_section -> list of (direction, tvu, agency)
const BLOCK_DATA = {
  "DUG-RSM":  [["East", 84666, "CPM/GS/NAG"]],
  "SKS-AGN":  [["", "", "CPM/GS/NAG"]],

  "RSM-MUP": [
    ["East", 38545, "CPM/GS/NAG"],
    ["East", 48211, "CPM/GS/NAG"]
  ],

  "BAKL-MUA": [
    ["East", 30109, "CPM/GS/NAG"],
    ["East", 9733,  "CPM/GS/NAG"]
  ],

  "RJN-BAKL": [
    ["East", 19520, "CPM/GS/NAG"],
    ["East", 34694, "CPM/GS/NAG"]
  ],

  "JTR-DGG": [
    ["East", 22692, "CPM/GS/NAG"],
    ["East", 25374, "CPM/GS/NAG"]
  ],

  "BTC-KGE": [
    ["North", "", "CPM/GS/NAG"],
    ["North", "", "CPM/GS/NAG"],
    ["North", "", "CPM/GS/NAG"],
    ["North", 38993, "CPM/GS/NAG"],
    ["North", 49872, "CPM/GS/NAG"]
  ],

  "G-GJ": [
    ["", "", "CPM/GS/NAG"],
    ["East", 52900, "CPM/GS/NAG"]
  ],

  "BRD-KT": [
    ["Central", 105294, "CPM/GS/NAG"],
    ["Central", 34977, "CPM/GS/NAG"]
  ],

  "HTT-BTC": [["South", 53268, "CPM/GS/NAG"]]
};


window.onload = function () {
  const select = document.getElementById("block_section");

  for (let block in BLOCK_DATA) {
    const option = document.createElement("option");
    option.value = block;
    option.textContent = block;
    select.appendChild(option);
  }
};

function fillBlock(block){
  const data = BLOCK_DATA[block];
  if(!data || data.length === 0) return;

  const first = data[0];

  document.getElementById('sectional_den').value = first[0] || "";
  document.getElementById('tvu').value = first[1] || "";
  document.getElementById('executing_agency').value = first[2] || "";
}

function tog(btn, field, val){
  const parent = btn.parentElement;
  parent.querySelectorAll("button").forEach(b => b.className = "");
  btn.className = val === "Y" ? "y" : "n";
  document.querySelector(`input[name="${field}"]`).value = val;
}

async function saveEntry(){
  const fd = new FormData(document.getElementById("ph30form"));
  const res = await fetch("/save_ph30", {
    method:"POST",
    body:new URLSearchParams(fd)
  });

  const text = await res.text();
  const msg = document.getElementById("msg");

  msg.style.display = "block";

  if(res.ok){
    msg.style.background = "#14532d";
    msg.innerText = text;
  } else {
    msg.style.background = "#7f1d1d";
    msg.innerText = text;
  }
}
</script>

</body>
</html>"""

        return respond(self, html)

    # ================= DELETE =================
    def delete_ph30(self, q):
        try:
            rid = int(q.get("id", [0])[0])
            with engine.begin() as db:
                db.execute(text("DELETE FROM ph30_lc_projects WHERE id = :id"), {"id": rid})
            return respond(self, "ok")
        except Exception as e:
            return respond(self, f"error: {e}")

    # ================= SAVE =================
    def save_ph30(self, q):
        def v(key, default=""):
            return q.get(key, [default])[0]

        block = v("block_section")

        # BLOCK_DATA lookup — first matching row used for auto-fill defaults
        block_rows = BLOCK_DATA.get(block, [])
        auto_den, auto_tvu, auto_agency = block_rows[0] if block_rows else ("", "", "")

        # Use form value if provided, else fall back to BLOCK_DATA
        sectional_den    = v("sectional_den")    or str(auto_den)
        tvu_val          = v("tvu")              or str(auto_tvu)
        executing_agency = v("executing_agency") or str(auto_agency)

        try:
            with engine.begin() as db:
                db.execute(text("""
                    INSERT INTO ph30_lc_projects (
                        lc_no, km, block_section, sectional_den,
                        tvu, executing_agency, sanction_year, sanction_date,
                        rob_rub, gad, gad_status,
                        lc_closure_permission, collector_consent_date,
                        cost_sharing, state_estimate_sanction,
                        estimate_position, estimate_status,
                        crs_construction, crs_closure, crs_shifting,
                        tender_flag, tender_status,
                        drawing_approved, land_acq_required, land_area,
                        st_clearance, st_clearance_date,
                        sanctioned_cost, railway_share, state_share,
                        exp_upto_mar24, outlay, exp_2024_25, exp_upto_date,
                        progress, tdc, remarks
                    ) VALUES (
                        :lc_no, :km, :block_section, :sectional_den,
                        :tvu, :executing_agency, :sanction_year, :sanction_date,
                        :rob_rub, :gad, :gad_status,
                        :lc_closure_permission, :collector_consent_date,
                        :cost_sharing, :state_estimate_sanction,
                        :estimate_position, :estimate_status,
                        :crs_construction, :crs_closure, :crs_shifting,
                        :tender_flag, :tender_status,
                        :drawing_approved, :land_acq_required, :land_area,
                        :st_clearance, :st_clearance_date,
                        :sanctioned_cost, :railway_share, :state_share,
                        :exp_upto_mar24, :outlay, :exp_2024_25, :exp_upto_date,
                        :progress, :tdc, :remarks
                    )
                """), {
                    "lc_no":                   v("lc_no"),
                    "km":                      v("km"),
                    "block_section":           block,
                    "sectional_den":           sectional_den,
                    "tvu":                     int(tvu_val) if str(tvu_val).strip().isdigit() else None,
                    "executing_agency":        executing_agency,
                    "sanction_year":           v("sanction_year"),
                    "sanction_date":           safe_date(v("sanction_date")),
                    "rob_rub":                 v("rob_rub"),
                    "gad":                     v("gad"),
                    "gad_status":              v("gad_status"),
                    "lc_closure_permission":   v("lc_closure_permission"),
                    "collector_consent_date":  safe_date(v("collector_consent_date")),
                    "cost_sharing":            v("cost_sharing", "Y"),
                    "state_estimate_sanction": v("state_estimate_sanction"),
                    "estimate_position":       v("estimate_position", "Y"),
                    "estimate_status":         v("estimate_status"),
                    "crs_construction":        v("crs_construction", "Y"),
                    "crs_closure":             v("crs_closure", "Y"),
                    "crs_shifting":            v("crs_shifting", "Y"),
                    "tender_flag":             v("tender_flag", "Y"),
                    "tender_status":           v("tender_status"),
                    "drawing_approved":        v("drawing_approved", "Y"),
                    "land_acq_required":       v("land_acq_required", "Y"),
                    "land_area":               v("land_area"),
                    "st_clearance":            v("st_clearance"),
                    "st_clearance_date":       safe_date(v("st_clearance_date")),
                    "sanctioned_cost":         safe_num(v("sanctioned_cost")),
                    "railway_share":           safe_num(v("railway_share")),
                    "state_share":             safe_num(v("state_share")),
                    "exp_upto_mar24":          safe_num(v("exp_upto_mar24")),
                    "outlay":                  safe_num(v("outlay")),
                    "exp_2024_25":             safe_num(v("exp_2024_25")),
                    "exp_upto_date":           safe_num(v("exp_upto_date")),
                    "progress":                safe_num(v("progress")),
                    "tdc":                     safe_date(v("tdc")),
                    "remarks":                 v("remarks"),
                })

            return respond(self, "✅ Entry saved successfully")
        except Exception as e:
            return respond(self, f"❌ Error: {e}")

    # ================= VIEW DASHBOARD =================
    def ph30_view(self):
            try:
                with engine.begin() as db:
                  rows = db.execute(text("""
        SELECT DISTINCT ON (lc_no)
            id, lc_no, km, block_section, sectional_den, tvu,
            executing_agency, sanction_year,
            gad_status, lc_closure_permission,
            cost_sharing, estimate_status,
            crs_construction, crs_closure, crs_shifting,
            tender_flag, tender_status,
            drawing_approved, land_acq_required,
            sanctioned_cost, railway_share, state_share,
            exp_upto_mar24, outlay, exp_2024_25, exp_upto_date,
            progress, tdc, remarks
        FROM ph30_lc_projects
        ORDER BY lc_no, id DESC
    """)).mappings().all()
            except Exception as e:
                return respond(self, f"<h3>DB Error: {e}</h3>")
     
            # ── Cell helpers ─────────────────────────────────────────────────
     
            def yn_badge(val):
                if str(val or "").upper() in ("Y", "YES"):
                    return "<span class='badge badge-yes'>Y</span>"
                return "<span class='badge badge-no'>N</span>"
     
            def prog_bar(val):
                try:
                    p = min(float(val or 0), 100)
                except (ValueError, TypeError):
                    p = 0
                color = "#10b981" if p >= 75 else "#f59e0b" if p >= 40 else "#ef4444"
                return (
                    f"<div class='prog-wrap'>"
                    f"<div class='prog-track'>"
                    f"<div class='prog-fill' style='width:{p:.0f}%;background:{color}'></div>"
                    f"</div><span class='prog-label'>{p:.0f}%</span></div>"
                )
     
            def status_chip(val):
                if not val:
                    return "<span class='cell-muted'>—</span>"
                v = str(val).lower()
                if   any(k in v for k in ("approv","complet","granted")): cls = "chip-green"
                elif any(k in v for k in ("under","progress","award")):   cls = "chip-blue"
                elif any(k in v for k in ("pending","revision")):          cls = "chip-gold"
                elif any(k in v for k in ("not ","cancel")):               cls = "chip-red"
                elif any(k in v for k in ("submit","applied")):            cls = "chip-purple"
                elif "draft" in v:                                          cls = "chip-orange"
                else:                                                        cls = "chip-default"
                return f"<span class='chip {cls}'>{val}</span>"
     
            def num_cell(val):
                if val is None or val == "":
                    return "<span class='cell-muted'>—</span>"
                try:
                    return f"<span class='cell-num'>{float(val):.2f}</span>"
                except (ValueError, TypeError):
                    return f"<span class='cell-muted'>{val}</span>"
     
            # ── KPI aggregates (computed in Python, stamped into HTML) ───────
     
            total        = len(rows)
            gad_approved = sum(1 for r in rows if "approv" in str(r["gad_status"] or "").lower())
            tender_yes   = sum(1 for r in rows if str(r["tender_flag"] or "").upper() in ("Y","YES"))
            crs_yes      = sum(1 for r in rows if str(r["crs_construction"] or "").upper() in ("Y","YES"))
            land_yes     = sum(1 for r in rows if str(r["land_acq_required"] or "").upper() in ("Y","YES"))
            prog_vals    = [float(r["progress"]) for r in rows if r["progress"] not in (None,"")]
            avg_prog     = f"{sum(prog_vals)/len(prog_vals):.0f}%" if prog_vals else "0%"
            total_exp    = sum(float(r["exp_upto_date"]   or 0) for r in rows)
            total_sanct  = sum(float(r["sanctioned_cost"] or 0) for r in rows)
     
            # ── Table rows ───────────────────────────────────────────────────
     
            rows_html = ""
            for r in rows:
                rid       = r["id"]
                srch      = " ".join([
                    str(r["lc_no"] or ""), str(r["block_section"] or ""),
                    str(r["executing_agency"] or ""), str(r["sectional_den"] or ""),
                ]).lower()
                tdr       = str(r["tender_flag"] or "").upper()
                tdc_s     = str(r["tdc"])[:10] if r["tdc"] else "—"
                rows_html += (
                    f"<tr id='row-{rid}' data-progress='{r['progress'] or 0}'"
                    f" data-gad='{r['gad_status'] or ''}'"
                    f" data-agency='{r['executing_agency'] or ''}'"
                    f" data-tender='{tdr}' data-search='{srch}'>"
                    f"<td><button class='del-btn' onclick='delRow({rid})'>✕</button></td>"
                    f"<td class='cell-id'>{rid}</td>"
                    f"<td><span class='cell-lc'>{r['lc_no'] or '—'}</span></td>"
                    f"<td class='cell-km'>{r['km'] or '—'}</td>"
                    f"<td class='cell-text'>{r['block_section'] or '—'}</td>"
                    f"<td class='cell-muted'>{r['sectional_den'] or '—'}</td>"
                    f"<td class='cell-num' style='text-align:left'>{int(r['tvu'] or 0):,}</td>"
                    f"<td class='cell-text'>{r['executing_agency'] or '—'}</td>"
                    f"<td class='cell-muted grp-sep'>{r['sanction_year'] or '—'}</td>"
                    f"<td>{status_chip(r['gad_status'])}</td>"
                    f"<td>{status_chip(r['lc_closure_permission'])}</td>"
                    f"<td>{yn_badge(r['cost_sharing'])}</td>"
                    f"<td>{status_chip(r['estimate_status'])}</td>"
                    f"<td>{yn_badge(r['crs_construction'])}</td>"
                    f"<td class='grp-sep'>{yn_badge(r['crs_closure'])}</td>"
                    f"<td>{yn_badge(r['crs_shifting'])}</td>"
                    f"<td>{yn_badge(r['tender_flag'])}</td>"
                    f"<td>{status_chip(r['tender_status'])}</td>"
                    f"<td class='grp-sep'>{yn_badge(r['drawing_approved'])}</td>"
                    f"<td>{yn_badge(r['land_acq_required'])}</td>"
                    f"<td>{num_cell(r['sanctioned_cost'])}</td>"
                    f"<td>{num_cell(r['railway_share'])}</td>"
                    f"<td>{num_cell(r['state_share'])}</td>"
                    f"<td>{num_cell(r['exp_upto_mar24'])}</td>"
                    f"<td>{num_cell(r['outlay'])}</td>"
                    f"<td class='grp-sep'>{num_cell(r['exp_2024_25'])}</td>"
                    f"<td>{prog_bar(r['progress'])}</td>"
                    f"<td class='cell-muted'>{tdc_s}</td>"
                    f"<td><button class='remark-btn' onclick=\"openRemark(`{r['remarks'] or '—'}`)\">View</button></td>"
                    f"</tr>"
                )
     
            # ── Dynamic dropdown options ─────────────────────────────────────
     
            gad_opts = "".join(
                f"<option value='{v}'>{v}</option>"
                for v in sorted({
                    str(r.get("gad_status") or "").strip()
                    for r in rows
                } - {""})
            )
            
            agency_opts = "".join(
                f"<option value='{v}'>{v}</option>"
                for v in sorted({
                    str(r.get("executing_agency") or "").strip()
                    for r in rows
                } - {""})
            )
            
            # ── Minimal sort-data JSON (scalar fields only) ──────────────────
            
            import json  # 🔴 REQUIRED (keep at top ideally)
            
            sort_json = json.dumps([
                {
                    "id": r.get("id"),
                    "lc_no": str(r.get("lc_no") or ""),
                    "km": str(r.get("km") or ""),
                    "block_section": str(r.get("block_section") or ""),
                    "sectional_den": str(r.get("sectional_den") or ""),
                    "tvu": str(r.get("tvu") or ""),
                    "executing_agency": str(r.get("executing_agency") or ""),
                    "sanction_year": str(r.get("sanction_year") or ""),
                    "progress": float(r.get("progress") or 0),
                    "tdc": str(r.get("tdc"))[:10] if r.get("tdc") else "",
                }
                for r in rows
            ], ensure_ascii=False)
            
            # ── Empty state row ─────────────────────────────────────────────
            
            empty_row = (
                "<tr><td colspan='30'><div class='empty-state'>"
                "<div class='icon'>📭</div><p>No records found</p>"
                "</div></td></tr>"
            )
     
            # ── Assemble page  ───────────────────────────────────────────────
            # CSS is split into a separate string to avoid f-string brace conflicts.
     
            CSS = """
    :root{--bg-base:#060d1a;
    --bg-panel:#ffffff;
    --bg-card:#ffffff;
    --bg-row-hover:#132340;
    --border:#1a2d4a;
    --border-light:#1e3558;
    --accent:#000000;
    --text-primary:#e2f0ff;
    --text-second:#7da8cc;
    --text-muted:#3d6285;
    --header-bg:#ffffff;
    }

    *,*::before,
    *::after{
    box-sizing:border-box;
    margin:0;
    padding:0
    }

    body{
    background: radial-gradient(circle at top, #7DAACB, #E8DBB3);
    color:var(--text-primary);
    font-family:'DM Sans', sans-serif;
    min-height:100vh;
    overflow-x:hidden
    }

    body::before{
    content:'';
    position:fixed;
    inset:0;
    z-index:0;
    pointer-events:none;
    background-image:linear-gradient(rgba(0,212,255,.03) 1px,transparent 1px),
    linear-gradient(90deg,rgba(0,212,255,.03) 1px,transparent 1px);
    background-size:40px 40px
    }

    .page-wrapper{
    position:relative;
    z-index:1;
    padding:24px 28px 60px
    }

    /* topbar */
    .topbar{
    display:flex;
    align-items:center;
    gap:16px;
    margin-bottom:24px;
    flex-wrap:wrap;
    border-bottom:1px solid var(--border);
    padding-bottom:20px
    }

    .logo-icon{
    width:44px;
    height:44px;
    border-radius:10px;
    font-size:22px;
    background:linear-gradient(135deg,#0ea5e9,#0369a1);
    display:flex;align-items:center;
    justify-content:center;
    box-shadow:0 0 20px rgba(14,165,233,.4)
    }

    .logo-title{
    font-family:'Space Mono',monospace;
    font-size:16px;
    font-weight:700;
    color:var(--accent);
    letter-spacing:2px
    }

    .logo-sub{
    font-size:11px;
    color:var(--text-muted);
    letter-spacing:1px;
    text-transform:uppercase
    }

    .topbar-actions{
    margin-left:auto;
    display:flex;
    gap:10px;
    align-items:center
    }

    .btn{
    padding:8px 18px;
    border-radius:7px;
    font-size:13px;
    font-family:'DM Sans',sans-serif;
    font-weight:500;
    cursor:pointer;
    border:none;
    text-decoration:none;
    display:inline-flex;
    align-items:center;
    ap:6px;
    transition:all .2s
    }

    .btn-primary{
    background:linear-gradient(135deg,#0284c7,#0ea5e9);
    color:#fff;
    box-shadow:0 4px 14px rgba(2,132,199,.35)
    }

    .btn-primary:hover{
    transform:translateY(-1px);
    box-shadow:0 6px 20px rgba(2,132,199,.5)
    }

    .btn-secondary{
    background:var(--bg-card);
    color:var(--text-second);
    border:1px solid var(--border-light)
    }

    .btn-secondary:hover{
    background:var(--bg-row-hover);
    color:var(--text-primary)
    }

    /* stat cards */
    .stats-grid{
    display:grid;
    grid-template-columns:repeat(auto-fit,minmax(160px,1fr));
    gap:14px;
    margin-bottom:24px;
    animation:fadeInUp .4s ease both
    }

    .stat-card{
    background:var(--bg-card);
    border:1px solid var(--border);
    border-radius:12px;
    padding:16px 18px;
    position:relative;
    overflow:hidden;
    transition:border-color .2s,transform .2s
    }

    .stat-card:hover{
    border-color:var(--border-light);
    transform:translateY(-2px)
    }

    .stat-card::before{
    content:'';
    position:absolute;
    top:0;
    left:0;
    right:0;
    height:2px
    }

    .stat-card.blue::before{
    background:linear-gradient(90deg,#0ea5e9,#38bdf8)
    }
    .stat-card.green::before{
    background:linear-gradient(90deg,#10b981,#34d399)
    }
    .stat-card.gold::before{
    background:linear-gradient(90deg,#f59e0b,#fbbf24)
    }
    .stat-card.red::before{
    background:linear-gradient(90deg,#ef4444,#f87171)
    }
    .stat-card.purple::before{
    background:linear-gradient(90deg,#a78bfa,#c4b5fd)
    }
    .stat-card.cyan::before{
    background:linear-gradient(90deg,#00d4ff,#0ea5e9)
    }

    .stat-label{
      color: blac;
    font-size:10px;
    color:var(--text-muted);
    text-transform:uppercase;
    letter-spacing:1.2px;
    margin-bottom:8px
    }

    .stat-value{
      color: rgb(0, 0, 0);
    font-family:'Space Mono',monospace;
    font-size:28px;
    font-weight:700;
    line-height:1;
    /* animation:glowPulse 3s ease-in-out infinite */
    }

    .stat-card.blue.stat-value{
    color:#38bdf8
    }
    .stat-card.green.stat-value{
    color:#34d399
    }
    .stat-card.gold.stat-value{
    color:#fbbf24
    }
    .stat-card.red.stat-value{
    color:#f87171
    }
    .stat-card.purple.stat-value{
    color:#c4b5fd
    }
    .stat-card.cyan.stat-value{
    color:#00d4ff
    }
    .stat-sub{
    font-size:11px;
    color:var(--text-muted);
    margin-top:5px
    }

    /* filter bar */
    .filter-bar{
    display:flex;
    gap:10px;
    flex-wrap:wrap;
    align-items:center;
    background:var(--bg-panel);
    border:1px solid var(--border);
    border-radius:10px;
    padding:12px 16px;
    margin-bottom:18px;
    animation:fadeInUp .45s ease both
    }

    .filter-bar label{
    font-size:11px;
    color:var(--text-muted);
    text-transform:uppercase;
    letter-spacing:1px
    }

    .filter-input,.filter-select{
    background:var(--bg-card);
    border:1px solid var(--border);
    color:var(--text-primary);
    border-radius:25px;
    padding:6px 12px;
    font-size:12px;
    font-family:'DM Sans',sans-serif;
    transition:border-color .2s
    }

    .filter-input:focus,.filter-select:focus{
    outline:none;
    border-color:var(--accent);
    box-shadow:0 0 0 2px rgba(0,212,255,.1)
    }
    .filter-input{
    width:220px
    }
    .filter-select{
      color: #000000;
    width:150px
    }
    .filter-divider{
    width:1px;
    height:24px;
    background:var(--border);
    margin:0 4px
    }
    .filter-count{
    font-size:12px;
    color:rgb(122, 122, 122);
    margin-left:auto
    }
    .filter-count span{
    color:var(--accent);
    font-family:'Space Mono',monospace
    }

    /* table */
    .table-wrapper{
    background:var(--bg-panel);
    border:1px solid var(--border);
    border-radius:12px;
    overflow:hidden;
    animation:fadeInUp .5s ease both
    }

    .table-scroll{
    overflow-x:auto;
    max-height:calc(100vh - 380px);
    overflow-y:auto;
    display:block;              /* ✅ ADD */
    }
    .table-scroll::-webkit-scrollbar{
    width:6px;height:6px
    }
    .table-scroll::-webkit-scrollbar-track{
    background:var(--bg-base)
    }
    .table-scroll::-webkit-scrollbar-thumb{
    background:var(--border-light);border-radius:3px
    }
    .table-scroll::-webkit-scrollbar-thumb:hover{
    background:var(--accent)
    }

    table{
    border-collapse:collapse;
    width:100%;
    min-width:2200px
    }

    .col-group-header{
    background:#ffffff;
    text-align:center;
    font-size:9px;
    font-weight:700;
    letter-spacing:2px;
    text-transform:uppercase;
    padding:6px 0;
    border-bottom:1px solid var(--border)
    }

    .cg-identity{
    color:#38bdf8;
    border-right:1px solid var(--border)
    }
    .cg-clearance{
    color:#a78bfa;
    border-right:1px solid var(--border)
    }
    .cg-works{
    color:#34d399;
    border-right:1px solid var(--border)
    }
    .cg-finance{
    color:#fbbf24;
    border-right:1px solid var(--border)}
    .cg-status{
    color:#f97316
    }

    thead th{
    background:var(--header-bg);
    color:var(--text-second);
    padding:10px 12px;
    font-size:10px;
    font-weight:700;
    text-transform:uppercase;
    letter-spacing:1px;
    white-space:nowrap;
    position:sticky;
    top:0;z-index:10;
    border-bottom:1px solid var(--border);
    cursor:pointer;
    user-select:none;
    transition:color .15s
    }

    thead th:hover{
    color:var(--accent)
    }
    thead th.sort-asc::after {
    content:' ↑';
    color:var(--accent)
    }
    thead th.sort-desc::after{
    content:' ↓';
    color:var(--accent)
    }
    th.grp-sep,td.grp-sep{
    border-right:1px solid #1a2d4a !important
    }
    tbody tr{
    transition:background .15s
    }
    tbody tr:nth-child(odd){
    background:#0b1628
    }
    tbody tr:nth-child(even){
    background:#0d1a2e
    }
    tbody tr:hover{
    background:var(--bg-row-hover)
    }
    tbody tr.filtered-out{
    display:none
    }

    td{
    padding:9px 12px;
    font-size:12px;
    border-bottom:1px solid rgba(26,45,74,.5);
    white-space:nowrap;
    vertical-align:middle;
    color:var(--text-primary)
    }

    .cell-id{
    font-family:'Space Mono',monospace;
    font-size:11px;
    color:var(--text-muted)
    }
    .cell-lc{font-family:'Space Mono',monospace;
    font-size:12px;color:var(--accent);
    font-weight:700
    }
    .cell-km{
    color:var(--text-second)
    }
    .cell-text{
    color:var(--text-primary)
    }
    .cell-muted{
    color:var(--text-second);
    font-size:11px
    }
    .cell-num{
    font-family:'Space Mono',monospace;
    font-size:11px;
    color:#93c5fd;
    display:block;
    text-align:right
    }
    .cell-remarks{
    max-width:200px;
    white-space:normal;
    font-size:11px;
    color:var(--text-muted);
    line-height:1.4
    }
    .badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 10px;
  font-weight: 700;
  font-family: 'Space Mono', monospace;
  letter-spacing: 0.5px;
}

.badge-yes {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
  border: 1px solid rgba(16, 185, 129, 0.3);
}

.badge-no {
  background: rgba(239, 68, 68, 0.12);
  color: #f87171;
  border: 1px solid rgba(239, 68, 68, 0.25);
}

.chip {
  display: inline-block;
  padding: 3px 9px;
  border-radius: 5px;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.3px;
  white-space: nowrap;
}

.chip-blue {
  background: rgba(14, 165, 233, 0.15);
  color: #38bdf8;
}

.chip-green {
  background: rgba(16, 185, 129, 0.15);
  color: #34d399;
}

.chip-gold {
  background: rgba(245, 158, 11, 0.15);
  color: #fbbf24;
}

.chip-red {
  background: rgba(239, 68, 68, 0.15);
  color: #f87171;
}

.chip-purple {
  background: rgba(167, 139, 250, 0.15);
  color: #c4b5fd;
}

.chip-orange {
  background: rgba(249, 115, 22, 0.15);
  color: #fb923c;
}

.chip-default {
  background: rgba(125, 168, 204, 0.1);
  color: #7da8cc;
}

.prog-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.prog-track {
  width: 80px;
  height: 6px;
  background: #0f2137;
  border-radius: 3px;
  overflow: hidden;
  flex-shrink: 0;
}

.prog-fill {
  height: 100%;
  border-radius: 3px;
}

.prog-label {
  font-family: 'Space Mono', monospace;
  font-size: 10px;
  color: var(--text-muted);
  min-width: 28px;
}

.del-btn {
  width: 26px;
  height: 26px;
  border-radius: 6px;
  background: rgba(127, 29, 29, 0.4);
  border: 1px solid rgba(239, 68, 68, 0.2);
  color: #f87171;
  font-size: 12px;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.del-btn:hover {
  background: rgba(239, 68, 68, 0.3);
  border-color: #ef4444;
  transform: scale(1.1);
}

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-top: 1px solid var(--border);
  font-size: 11px;
  color: var(--text-muted);
  background: var(--header-bg);
}

.table-footer b {
  color: var(--accent);
  font-family: 'Space Mono', monospace;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
  color: var(--text-muted);
}

.empty-state .icon {
  font-size: 40px;
  margin-bottom: 12px;
  opacity: 0.4;
}

.remark-btn{
  padding:4px 10px;
  font-size:11px;
  border-radius:6px;
  background:var(--bg-card);
  border:1px solid var(--border);
  cursor:pointer;
}

.modal{
  display:none;
  position:fixed;
  inset:0;
  background:rgba(0,0,0,0.6);
  align-items:center;
  justify-content:center;
  z-index:999;
}

.modal-box{
  background:#0b1628;
  padding:20px;
  border-radius:10px;
  width:400px;
  max-height:70vh;
  overflow-y:auto;
  color:var(--text-primary);
}

.close{
  float:right;
  cursor:pointer;
  font-size:18px;
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(16px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@keyframes glowPulse {
  0%, 100% {
    text-shadow: none;
  }
  50% {
    text-shadow: 0 0 12px currentColor;
  }
}
    """
     
            JS = """
    const ROW_DATA = __SORT_JSON__;
    const dataMap  = Object.fromEntries(ROW_DATA.map(d => [d.id, d]));
    let sortCol = 'id', sortDir = 1;
     
    document.querySelectorAll('thead th[data-col]').forEach(th => {
      th.addEventListener('click', () => {
        const col = th.dataset.col;
        sortDir = (sortCol === col) ? sortDir * -1 : 1;
        sortCol = col;
        document.querySelectorAll('thead th').forEach(t => t.classList.remove('sort-asc','sort-desc'));
        th.classList.add(sortDir === 1 ? 'sort-asc' : 'sort-desc');
        const tbody = document.getElementById('tableBody');
        const trs   = Array.from(tbody.querySelectorAll('tr[id^="row-"]'));
        trs.sort((a, b) => {
          const ida = parseInt(a.id.replace('row-',''));
          const idb = parseInt(b.id.replace('row-',''));
          const da  = dataMap[ida]?.[col] ?? '';
          const db  = dataMap[idb]?.[col] ?? '';
          const na  = parseFloat(da), nb = parseFloat(db);
          if (!isNaN(na) && !isNaN(nb)) return (na - nb) * sortDir;
          return String(da).localeCompare(String(db)) * sortDir;
        });
        trs.forEach(r => tbody.appendChild(r));
        applyFilters();
      });
    });
     
    function applyFilters() {
      const search   = document.getElementById('searchInput').value.toLowerCase().trim();
      const gad      = document.getElementById('filterGAD').value;
      const agency   = document.getElementById('filterAgency').value;
      const tender   = document.getElementById('filterTender').value;
      const progBand = document.getElementById('filterProgress').value;
      let visible    = 0;
      document.querySelectorAll('#tableBody tr').forEach(row => {
        if (!row.dataset.search) return;
        const ms = !search   || row.dataset.search.includes(search);
        const mg = !gad      || row.dataset.gad    === gad;
        const ma = !agency   || row.dataset.agency === agency;
        const mt = !tender   || row.dataset.tender === tender;
        const prog = parseFloat(row.dataset.progress || 0);
        let mp = true;
        if (progBand) {
          const [lo, hi] = progBand.split('-').map(Number);
          mp = prog >= lo && prog <= hi;
        }
        const show = ms && mg && ma && mt && mp;
        row.classList.toggle('filtered-out', !show);
        if (show) visible++;
      });
      document.getElementById('visibleCount').textContent = visible;
    }
     
    function clearFilters() {
      ['searchInput','filterGAD','filterAgency','filterTender','filterProgress']
        .forEach(id => { document.getElementById(id).value = ''; });
      applyFilters();
    }
     
    async function delRow(id) {
      if (!confirm('Delete record ID ' + id + '?')) return;
      try {
        const res = await fetch('/delete_ph30', {
          method:'POST',
          headers:{'Content-Type':'application/x-www-form-urlencoded'},
          body:'id='+id
        });
        const txt = await res.text();
        if (txt.includes('ok')) {
          document.getElementById('row-'+id)?.remove();
          const vc = document.getElementById('visibleCount');
          const tc = document.getElementById('totalCount');
          if(vc) vc.textContent = Math.max(0, parseInt(vc.textContent)-1);
          if(tc) tc.textContent = Math.max(0, parseInt(tc.textContent)-1);
        } else { alert('Delete failed: '+txt); }
      } catch(e) { alert('Error: '+e.message); }
    }
     
    function exportCSV() {
      const hdrs = ['ID','LC No','KM','Block Section','DEN','TVU','Agency','Year',
        'GAD Status','LC Permission','Cost Sharing','Est Status','CRS Const',
        'CRS Closure','CRS Shift','Tender','Tender Status','Drawing','Land Acq',
        'Sanct Cost','Rly Share','State Share','Exp Mar24','Outlay','Exp 24-25',
        'Progress','TDC','Remarks'];
      const esc  = v => '"'+String(v).replace(/"/g,'""')+'"';
      const rows = Array.from(
        document.querySelectorAll('#tableBody tr:not(.filtered-out)[data-search]')
      ).map(tr => Array.from(tr.querySelectorAll('td')).slice(1)
        .map(td => esc(td.innerText.trim())).join(','));
      const csv  = [hdrs.join(','), ...rows].join('\\n');
      const a = Object.assign(document.createElement('a'), {
        href    : 'data:text/csv;charset=utf-8,'+encodeURIComponent(csv),
        download: 'ph30_'+new Date().toISOString().slice(0,10)+'.csv'
      });
      a.click();
    }

    function openRemark(text){
  document.getElementById("remarkContent").innerText = text;
  document.getElementById("remarkModal").style.display = "flex";
}

function closeRemark(){
  document.getElementById("remarkModal").style.display = "none";
}
    """
     
            # Inject the sort JSON into the JS (avoids f-string brace escaping)
            JS = JS.replace("__SORT_JSON__", sort_json)
     
            html = (
"<!DOCTYPE html>\n"
"<html lang='en'>\n"

"<head>\n"
"  <meta charset='utf-8'>\n"
"  <meta name='viewport' content='width=device-width, initial-scale=1.0'>\n"

"  <title>PH-30 Dashboard</title>\n"

"  <link href='https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700"
"&family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,500;0,9..40,700&display=swap' rel='stylesheet'>\n"
f"  <style>{CSS}</style>\n"
"</head>\n"

"<body>\n"

"<div class='page-wrapper'>\n"

# TOP BAR
"<div class='topbar'>\n"
"  <div style='display:flex;align-items:center;gap:12px'>\n"
"    <div class='logo-icon'>🚦</div>\n"
"    <div>\n"
"      <div class='logo-title'>PH-30</div>\n"
"      <div class='logo-sub'>Level Crossing Projects</div>\n"
"    </div>\n"
"  </div>\n"

"  <div class='topbar-actions'>\n"
"    <button class='btn btn-secondary' onclick='exportCSV()'>⬇ Export CSV</button>\n"
"    <a href='/ph30' class='btn btn-primary'>＋ Add Entry</a>\n"
"    <a href='/' class='btn btn-secondary'>← Home</a>\n"
"  </div>\n"
"</div>\n"


# STATS
"<div class='stats-grid'>\n"

f"<div class='stat-card blue'><div class='stat-label'>Total LCs</div><div class='stat-value'>{total}</div><div class='stat-sub'>All projects</div></div>\n"
f"<div class='stat-card green'><div class='stat-label'>GAD Approved</div><div class='stat-value'>{gad_approved}</div><div class='stat-sub'>Drawing ready</div></div>\n"
f"<div class='stat-card gold'><div class='stat-label'>Tenders Floated</div><div class='stat-value'>{tender_yes}</div><div class='stat-sub'>Procurement stage</div></div>\n"
f"<div class='stat-card purple'><div class='stat-label'>CRS Cleared</div><div class='stat-value'>{crs_yes}</div><div class='stat-sub'>Construction</div></div>\n"
f"<div class='stat-card cyan'><div class='stat-label'>Avg Progress</div><div class='stat-value'>{avg_prog}</div><div class='stat-sub'>Completion</div></div>\n"
f"<div class='stat-card red'><div class='stat-label'>Land Acq. Pending</div><div class='stat-value'>{land_yes}</div><div class='stat-sub'>Needs attention</div></div>\n"

"</div>\n"


# FILTER
"<div class='filter-bar'>\n"

"  <label>Search</label>\n"
"  <input type='text' class='filter-input' id='searchInput' placeholder='LC No, Block Section, Agency…' oninput='applyFilters()'>\n"

"  <div class='filter-divider'></div>\n"

"  <label>GAD Status</label>\n"
f"  <select class='filter-select' id='filterGAD' onchange='applyFilters()'><option value=''>All</option>{gad_opts}</select>\n"

"  <label>Agency</label>\n"
f"  <select class='filter-select' id='filterAgency' onchange='applyFilters()'><option value=''>All</option>{agency_opts}</select>\n"

"  <label>Tender</label>\n"
"  <select class='filter-select' id='filterTender' onchange='applyFilters()'>\n"
"    <option value=''>All</option>\n"
"    <option value='Y'>Yes</option>\n"
"    <option value='N'>No</option>\n"
"  </select>\n"

"  <label>Progress</label>\n"
"  <select class='filter-select' id='filterProgress' onchange='applyFilters()'>\n"
"    <option value=''>All</option>\n"
"    <option value='0-25'>0–25%</option>\n"
"    <option value='26-50'>26–50%</option>\n"
"    <option value='51-75'>51–75%</option>\n"
"    <option value='76-100'>76–100%</option>\n"
"  </select>\n"

"  <button class='btn btn-secondary' onclick='clearFilters()' style='padding:6px 14px;font-size:12px;border-radius:25px;color:#000000;'>✕ Clear</button>\n"

f"  <div class='filter-count'>Showing <span id='visibleCount'>{total}</span> of <span id='totalCount'>{total}</span> records</div>\n"

"</div>\n"


# TABLE
"<div class='table-wrapper'>\n"
"<div class='table-scroll'>\n"

"<table id='mainTable'>\n"

"<thead>\n"

"<tr>\n"
"<th style='background:#ffffff;border-bottom:1px solid #000000' colspan='2'></th>\n"
"<th class='col-group-header cg-identity' colspan='7'>IDENTIFICATION</th>\n"
"<th class='col-group-header cg-clearance' colspan='6'>CLEARANCES &amp; PERMISSIONS</th>\n"
"<th class='col-group-header cg-works' colspan='4'>WORKS STATUS</th>\n"
"<th class='col-group-header cg-finance' colspan='7'>FINANCIAL (₹ Cr)</th>\n"
"<th class='col-group-header cg-status' colspan='3'>STATUS</th>\n"
"</tr>\n"

"<tr>\n"
"<th style='width:36px'></th>\n"
"<th data-col='id'>ID</th>\n"
"<th data-col='lc_no'>LC No.</th>\n"
"<th data-col='km'>KM</th>\n"
"<th data-col='block_section'>Block Section</th>\n"
"<th data-col='sectional_den'>DEN</th>\n"
"<th data-col='tvu'>TVU</th>\n"
"<th data-col='executing_agency'>Agency</th>\n"
"<th data-col='sanction_year' class='grp-sep'>Yr</th>\n"
"<th data-col='gad_status'>GAD Status</th>\n"
"<th data-col='lc_closure_permission'>LC Permission</th>\n"
"<th data-col='cost_sharing'>Cost Shr</th>\n"
"<th data-col='estimate_status'>Est. Status</th>\n"
"<th data-col='crs_construction'>CRS Const</th>\n"
"<th data-col='crs_closure' class='grp-sep'>CRS Closure</th>\n"
"<th data-col='crs_shifting'>CRS Shift</th>\n"
"<th data-col='tender_flag'>Tender</th>\n"
"<th data-col='tender_status'>Tender Status</th>\n"
"<th data-col='drawing_approved' class='grp-sep'>Drawing</th>\n"
"<th data-col='land_acq_required'>Land Acq</th>\n"
"<th data-col='sanctioned_cost'>Sanct Cost</th>\n"
"<th data-col='railway_share'>Rly Share</th>\n"
"<th data-col='state_share'>State Share</th>\n"
"<th data-col='exp_upto_mar24'>Exp Mar24</th>\n"
"<th data-col='outlay'>Outlay</th>\n"
"<th data-col='exp_2024_25' class='grp-sep'>Exp 24-25</th>\n"
"<th data-col='progress'>Progress</th>\n"
"<th data-col='tdc'>TDC</th>\n"
"<th data-col='remarks'>Remarks</th>\n"
"</tr>\n"

"</thead>\n"

f"<tbody id='tableBody'>{rows_html}</tbody>\n"

"</table>\n"
"</div>\n"


# FOOTER
"<div class='table-footer'>\n"
f"<span>Total records: <b>{total}</b></span>\n"
f"<span>Total Expenditure: ₹<b>{total_exp}</b> Cr | Total Sanctioned: ₹<b>{total_sanct}</b> Cr</span>\n"
"</div>\n"

"</div>\n"
"</div>\n"

f"<script>{JS}</script>\n"

"<div id='remarkModal' class='modal'>\n"
"  <div class='modal-box'>\n"
"    <span class='close' onclick='closeRemark()'>×</span>\n"
"    <div id='remarkContent'></div>\n"
"  </div>\n"
"</div>\n"

"</body>\n"
"</html>"
)
 
            return respond(self, html)


# ================= SERVER =================
PORT = 8000

socketserver.TCPServer.allow_reuse_address = True

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"🚀 Running at http://localhost:{PORT}")
    httpd.serve_forever()
