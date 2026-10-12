"""
generate_docs.py
Generates DOCUMENTATION.docx for the cloud_run_logistics_report project.
"""

from docx import Document
from docx.shared import Pt, Inches, RGBColor, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement
import os

OUTPUT_PATH = r"c:\Users\PranjalTripati\OneDrive - Arcatron Mobility Pvt Ltd\Desktop\frido\MIS\cloud_run_logistics_report\DOCUMENTATION.docx"

# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────

HEADER_FILL = (173, 198, 255)   # light blue for table headers


def set_cell_bg(cell, rgb: tuple):
    """Fill a table cell with a solid background colour."""
    r, g, b = rgb
    tc = cell._tc
    tcPr = tc.get_or_add_tcPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), f'{r:02X}{g:02X}{b:02X}')
    tcPr.append(shd)


def add_header_row(table, cols, fill=HEADER_FILL):
    """Bold the first row and apply a fill."""
    row = table.rows[0]
    for i, text in enumerate(cols):
        cell = row.cells[i]
        cell.text = text
        for para in cell.paragraphs:
            for run in para.runs:
                run.bold = True
        set_cell_bg(cell, fill)


def add_table(doc, headers, rows, col_widths=None):
    """Create a styled table."""
    n_cols = len(headers)
    table = doc.add_table(rows=1 + len(rows), cols=n_cols)
    table.style = 'Table Grid'
    table.alignment = WD_TABLE_ALIGNMENT.LEFT

    # header
    add_header_row(table, headers)

    # data rows
    for r_idx, row_data in enumerate(rows):
        row = table.rows[r_idx + 1]
        for c_idx, cell_text in enumerate(row_data):
            row.cells[c_idx].text = str(cell_text)

    # column widths
    if col_widths:
        for r in table.rows:
            for c_idx, cell in enumerate(r.cells):
                if c_idx < len(col_widths):
                    cell.width = Inches(col_widths[c_idx])

    return table


def add_code_block(doc, code: str):
    """Add a monospace code paragraph."""
    para = doc.add_paragraph()
    run = para.add_run(code)
    run.font.name = 'Courier New'
    run.font.size = Pt(9)
    para.paragraph_format.left_indent = Inches(0.4)
    # light grey shading on the paragraph
    pPr = para._p.get_or_add_pPr()
    shd = OxmlElement('w:shd')
    shd.set(qn('w:val'), 'clear')
    shd.set(qn('w:color'), 'auto')
    shd.set(qn('w:fill'), 'F2F2F2')
    pPr.append(shd)
    return para


def h1(doc, text):
    doc.add_heading(text, level=1)


def h2(doc, text):
    doc.add_heading(text, level=2)


def h3(doc, text):
    doc.add_heading(text, level=3)


def para(doc, text, bold=False):
    p = doc.add_paragraph(text)
    if bold:
        for run in p.runs:
            run.bold = True
    return p


def bullet(doc, text, level=0):
    p = doc.add_paragraph(text, style='List Bullet')
    return p


def numbered(doc, text):
    p = doc.add_paragraph(text, style='List Number')
    return p


# ──────────────────────────────────────────────
# Build document
# ──────────────────────────────────────────────

doc = Document()

# Margins: 1 inch all around
for section in doc.sections:
    section.top_margin    = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin   = Inches(1)
    section.right_margin  = Inches(1)

# ── Title Page ──────────────────────────────────
title_para = doc.add_paragraph()
title_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title_para.add_run('cloud_run_logistics_report')
run.bold = True
run.font.size = Pt(28)
run.font.color.rgb = RGBColor(0x1F, 0x38, 0x64)

doc.add_paragraph()

subtitle_para = doc.add_paragraph()
subtitle_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
run2 = subtitle_para.add_run('Developer Documentation')
run2.font.size = Pt(18)
run2.font.color.rgb = RGBColor(0x44, 0x72, 0xC4)

doc.add_paragraph()

date_para = doc.add_paragraph()
date_para.alignment = WD_ALIGN_PARAGRAPH.CENTER
run3 = date_para.add_run('October 2026')
run3.font.size = Pt(14)

doc.add_page_break()

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — Project Overview
# ══════════════════════════════════════════════════════════════════════════════
h1(doc, 'Section 1 — Project Overview')

para(doc, (
    'This is a scheduled Cloud Run microservice that generates and emails a daily logistics KPI '
    'report for Frido (a D2C e-commerce company). It has no frontend — it wakes up, queries '
    'BigQuery, builds an HTML email, and sends it.'
))

h2(doc, 'Why It Exists')
para(doc, (
    'The operations and logistics team needs a daily consolidated view of courier performance, '
    'warehouse efficiency, RTO rates, and fulfilment speed. Without this, 26 stakeholders would '
    'have to query BigQuery themselves. The service automates this at 12:00 PM IST every day.'
))

h2(doc, 'What It Outputs')
para(doc, (
    'A single HTML email with 11 data sections covering 50+ KPIs — delivery rates, RTO, FASR, '
    'EDD breach, warehouse fit, TAT breakdowns, NDR analysis, COD vs Prepaid, city tier, zone, '
    'and reverse pickup metrics.'
))

h2(doc, 'Trigger')
para(doc, (
    'Google Cloud Scheduler fires a cron (30 6 * * * UTC = 12:00 PM IST) that hits the Cloud Run '
    'HTTP endpoint via an OIDC-authenticated GET request.'
))

h2(doc, 'Recipients')
para(doc, '6 primary (TO) + 20 secondary (CC) stakeholders at myfrido.com.')

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — Architecture & Data Flow
# ══════════════════════════════════════════════════════════════════════════════
h1(doc, 'Section 2 — Architecture & Data Flow')

ascii_diagram = (
    "┌─────────────────────────┐\n"
    "│   Cloud Scheduler       │\n"
    "│   12:00 PM IST daily    │\n"
    "│   (30 6 * * * UTC)      │\n"
    "└────────────┬────────────┘\n"
    "             │  OIDC GET\n"
    "             ▼\n"
    "┌─────────────────────────┐\n"
    "│   Cloud Run (main.py)   │\n"
    "│   asia-south1 · 1GB     │\n"
    "│   Timeout: 540s         │\n"
    "└────────────┬────────────┘\n"
    "             │  12 SQL queries\n"
    "             ▼\n"
    "┌─────────────────────────────────────┐\n"
    "│   BigQuery (frido-429506)           │\n"
    "│   · Clickpost_Shipment_Tracking_    │\n"
    "│     Report                          │\n"
    "│   · state_region_nearest_wh         │\n"
    "│   · pincode_city_master             │\n"
    "└────────────┬────────────────────────┘\n"
    "             │  50+ KPIs computed\n"
    "             ▼\n"
    "┌─────────────────────────┐\n"
    "│   Build HTML Report     │\n"
    "│   Premailer inlines CSS │\n"
    "│   11 sections           │\n"
    "└────────────┬────────────┘\n"
    "             │  OAuth token request\n"
    "             ├──────────────────────► Azure AD (OTP_FRIDO tenant)\n"
    "             │  access_token\n"
    "             ◄──────────────────────\n"
    "             │  POST /sendMail\n"
    "             ▼\n"
    "┌─────────────────────────┐\n"
    "│   Microsoft Graph API   │\n"
    "│   data.team@myfrido.com │\n"
    "└────────────┬────────────┘\n"
    "             │\n"
    "             ▼\n"
    "┌─────────────────────────────────────┐\n"
    "│   26 Stakeholders (HTML Email)      │\n"
    "│   6 TO + 20 CC                      │\n"
    "└─────────────────────────────────────┘"
)
add_code_block(doc, ascii_diagram)

para(doc, (
    'Cloud Scheduler fires a GET to the Cloud Run service. The service loads GCP credentials from '
    'an environment secret, runs 12 BigQuery queries, builds an HTML email with inlined CSS, '
    'obtains an OAuth token from Azure AD, and sends the email via Microsoft Graph API. Typical '
    'run time: 2–3 minutes. Cloud Run\'s 540-second timeout is a safety net.'
))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — File Structure
# ══════════════════════════════════════════════════════════════════════════════
h1(doc, 'Section 3 — File Structure')

add_table(doc,
    headers=['File', 'Role', 'Notes'],
    rows=[
        ['main.py',         'Core application (~1,300 lines)',
         'All data fetching, KPI computation, HTML generation, and email dispatch. Entry point is an HTTP handler.'],
        ['requirements.txt','Python dependencies',
         'google-cloud-bigquery, db-dtypes, requests, premailer'],
        ['Dockerfile',      'Container definition',
         'Builds the image pushed to gcr.io/frido-429506/logistics-report'],
        ['deploy.sh',       'CI/deploy script',
         'Builds Docker image, pushes to GCR, deploys to Cloud Run with secrets, creates/updates Cloud Scheduler job'],
        ['env.yaml',        'Configuration & email lists',
         'Email TO/CC lists, Azure AD credentials, GCP credentials (base64). Never commit real values — use Cloud Run Secret Manager for production.'],
        ['run_local.py',    'Local test helper',
         'Patches main.py to use a fixed date and overrides recipients to pranjal.t@myfrido.com only'],
    ],
    col_widths=[1.3, 1.8, 3.5]
)

h2(doc, 'Entry Point')
para(doc, (
    'main.py exposes one HTTP route. When Cloud Run receives the GET request it runs the full '
    'pipeline synchronously and returns 200 OK. There are no other routes.'
))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — Configuration & Environment Variables
# ══════════════════════════════════════════════════════════════════════════════
h1(doc, 'Section 4 — Configuration & Environment Variables')

add_table(doc,
    headers=['Variable', 'Source', 'Purpose'],
    rows=[
        ['GCP_CREDENTIALS_B64',   'Secret Manager',
         'Base64-encoded GCP service account JSON. Decoded at runtime and written to /tmp/gcp_creds.json for the BigQuery client.'],
        ['OTP_FRIDO_TENANT_ID',   'Secret Manager',
         'Azure AD tenant ID used to obtain the OAuth token for Graph API.'],
        ['OTP_FRIDO_CLIENT_ID',   'Secret Manager',
         'Azure AD app (client) ID.'],
        ['OTP_FRIDO_CLIENT_SECRET','Secret Manager',
         'Azure AD client secret. Rotates every ~12 months — update Secret Manager when it does.'],
        ['EMAIL_TO',              'env.yaml / Cloud Run env',
         'Comma-separated TO addresses (6 recipients).'],
        ['EMAIL_CC',              'env.yaml / Cloud Run env',
         'Comma-separated CC addresses (20 recipients).'],
        ['FROM_EMAIL',            'env.yaml / Cloud Run env',
         'Sender address (data.team@myfrido.com). Must be a mailbox the Azure AD app has Send-As permission on.'],
    ],
    col_widths=[1.8, 1.5, 3.3]
)

h2(doc, 'How Credentials Are Loaded')
para(doc, (
    'main.py checks for GCP_CREDENTIALS_B64 first. If present, it base64-decodes the value, '
    'writes it to /tmp/gcp_creds.json, and initialises the BigQuery client with that file. '
    'If absent it falls back to Application Default Credentials.'
))

h2(doc, 'Adding / Removing Recipients')
para(doc, (
    'Edit EMAIL_TO / EMAIL_CC in Cloud Run → Edit & Deploy New Revision → Variables & Secrets, '
    'or re-run deploy.sh with updated env.yaml values.'
))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — BigQuery Tables
# ══════════════════════════════════════════════════════════════════════════════
h1(doc, 'Section 5 — BigQuery Tables')

h2(doc, 'Date Window Logic')
para(doc, 'The report uses a rolling 30-day window with a 15-day lag:')
bullet(doc, 'today = current date (when Cloud Run fires)')
bullet(doc, 'cutoff_date = today − 15 days')
bullet(doc, 'start_date = cutoff_date − 30 days')
bullet(doc, 'period = start_date to (cutoff_date − 1 day)')

para(doc, (
    'Example: job fires 2026-10-04 → data window = 2026-08-20 to 2026-09-18 (30 days).'
))
para(doc, (
    'All 12 queries filter on created_at within [start_date, cutoff_date). '
    'The 6-month trend query extends to 180 days from cutoff.'
))

h2(doc, 'Primary Table — production.Clickpost_Shipment_Tracking_Report')
para(doc, (
    'Every shipment Frido dispatches is a row here, fed by Clickpost (a multi-carrier aggregator). '
    'Source for all 12 queries.'
))

add_table(doc,
    headers=['Column', 'Type', 'Meaning'],
    rows=[
        ['awb',                                    'STRING',    'Air Way Bill — unique shipment tracking number'],
        ['courier_partner',                        'STRING',    'Carrier name (BlueDart, Ekart, Delhivery, XpressBees, etc.)'],
        ['clickpost_unified_status',               'STRING',    'Normalised status: Delivered, RTO Delivered, InTransit, Out For Delivery, etc.'],
        ['shipment_type',                          'STRING',    'Forward (outbound to customer) or Reverse (return/exchange pickup)'],
        ['payment_mode',                           'STRING',    'COD or Prepaid'],
        ['created_at',                             'TIMESTAMP', 'When the AWB was created in Clickpost'],
        ['order_date',                             'DATE',      'Original order date in the OMS'],
        ['pickup_date',                            'DATE',      'When the courier physically picked up the parcel'],
        ['delivery_date',                          'DATE',      'When the parcel was delivered (Forward) or received at warehouse (Reverse)'],
        ['expected_delivery_date_by_courier_partner','DATE',    'EDD promised by the courier'],
        ['out_for_delivery_attempts',              'INT',       'Number of out-for-delivery scans (≥ 2 = NDR)'],
        ['drop_pincode',                           'STRING',    'Destination pincode'],
        ['drop_state',                             'STRING',    'Destination state'],
        ['pickup_city',                            'STRING',    'Origin city (maps to a Frido warehouse)'],
        ['zone_by_frido',                          'STRING',    'Frido\'s zone classification (A/B/C/D/E)'],
        ['rto_mark_date',                          'DATE',      'Date the shipment was marked as RTO'],
        ['latest_timestamp',                       'TIMESTAMP', 'Most recent status update from the carrier'],
        ['Return_Type',                            'STRING',    'For Reverse shipments: Return or Exchange'],
    ],
    col_widths=[2.0, 0.9, 3.7]
)

h2(doc, 'Secondary Table — inventory_sales_allocation.state_region_nearest_wh')
para(doc, 'Maps each Indian state to Frido\'s nearest warehouse. Used in the Warehouse Fit query.')

add_table(doc,
    headers=['Column', 'Meaning'],
    rows=[
        ['shipping_address_state', 'State name'],
        ['nearest_wh',             'Expected warehouse code (PNQ, MUM, GGN, BLR, HYD, KOL, CHN)'],
    ],
    col_widths=[2.0, 4.6]
)

h2(doc, 'Secondary Table — production.pincode_city_master')
para(doc, 'Maps pincodes to city tier. Used in the City Tier Breakdown query.')

add_table(doc,
    headers=['Column', 'Meaning'],
    rows=[
        ['Pincode',   '6-digit Indian pincode'],
        ['City_Tier', 'Tier I, Tier II, or Tier III'],
    ],
    col_widths=[2.0, 4.6]
)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — SQL Queries
# ══════════════════════════════════════════════════════════════════════════════
h1(doc, 'Section 6 — SQL Queries (All 12)')

# ── Q1 ──
h2(doc, 'Q1 — Overall KPI Cards (main.py ~line 55)')
para(doc, 'Purpose: Compute headline metrics for the 30-day period shown in the top KPI cards.')
para(doc, 'Filters: Forward shipments, created_at in [start_date, cutoff_date)')
add_table(doc,
    headers=['Metric', 'Formula'],
    rows=[
        ['total_shipments',  'COUNT(DISTINCT awb)'],
        ['delivered_cnt',    "COUNT where status = 'Delivered'"],
        ['del_pct',          'delivered / total × 100'],
        ['rto_pct',          'COUNT(RTO Delivered) / total × 100'],
        ['fasr_pct',         'COUNT(Delivered with attempts = 1) / total delivered × 100'],
        ['rasr_pct',         'COUNT(Delivered with attempts ≥ 2) / COUNT(NDR shipments) × 100'],
        ['edd_pct',          'COUNT(delivery_date > EDD) / delivered × 100'],
        ['s2d_lte3_pct',     'COUNT(delivery_date − pickup_date ≤ 3) / delivered × 100'],
        ['o2d_lte5_pct',     'COUNT(delivery_date − order_date ≤ 5) / delivered × 100'],
        ['avg_processing',   'AVG(DATE_DIFF(pickup_date, order_date)) capped 0–10 days'],
        ['avg_pickup_tat',   'AVG(DATE_DIFF(pickup_date, created_at date)) capped 0–10 days'],
        ['avg_intransit',    'AVG(minutes from pickup to delivery) / 1440, capped 0–28800 min'],
        ['avg_o2d',          'AVG(DATE_DIFF(delivery_date, order_date)) capped 0–20 days'],
        ['avg_rto_delivered','AVG(DATE_DIFF(delivery_date, rto_mark_date)) for RTO Delivered'],
    ],
    col_widths=[1.8, 4.8]
)

# ── Q2 ──
h2(doc, 'Q2 — RVP KPI Cards (main.py ~line 102)')
para(doc, 'Purpose: Reverse Pickup headline metrics.')
para(doc, "Filters: Reverse shipments, Return_Type IN ('Return', 'Exchange'), created_at in range")
add_table(doc,
    headers=['Metric', 'Formula'],
    rows=[
        ['avg_rvp_days',             "AVG(DATE_DIFF(pickup_date, created_at date)) — time from request to physical pickup"],
        ['avg_rvp_to_delivery_days', "AVG(DATE_DIFF(delivery_date, pickup_date)) — time from pickup to warehouse receipt"],
    ],
    col_widths=[1.8, 4.8]
)

# ── Q3 ──
h2(doc, 'Q3 — Warehouse Fit % (main.py ~line 112)')
para(doc, 'Purpose: Measure what % of shipments went to the correct Frido warehouse based on destination state.')
para(doc, 'Logic:')
numbered(doc, "Map pickup_city to facility code using CASE (e.g. city LIKE '%pune%' → 'PNQ')")
numbered(doc, 'Join with state_region_nearest_wh on drop_state to get the expected facility')
numbered(doc, 'PNQ and MUM are treated as interchangeable (either counts as correct)')
numbered(doc, 'correct_alloc = 1 when actual facility matches expected (with PNQ/MUM swap rule)')
add_table(doc,
    headers=['Metric', 'Formula'],
    rows=[
        ['wh_fit_pct', 'SUM(correct_alloc) / COUNT(*) × 100'],
    ],
    col_widths=[1.8, 4.8]
)

# ── Q4 ──
h2(doc, 'Q4 — Monthly Trend (main.py ~line 147)')
para(doc, 'Purpose: 6-month historical trend for spotting improvement or regression.')
para(doc, 'Filters: Forward shipments, created_at in last 6 months from cutoff_date')
para(doc, "Grouping: FORMAT_DATE('%Y-%m', created_at) → one row per calendar month")
add_table(doc,
    headers=['Metric per Month', 'Description'],
    rows=[
        ['shipment_count',      'Total forward shipments in the calendar month'],
        ['del_pct',             'Delivery rate %'],
        ['rto_pct',             'RTO rate %'],
        ['fasr_pct',            'First attempt success rate %'],
        ['edd_pct',             'EDD breach rate %'],
        ['correct_alloc_pct',   'Warehouse fit %'],
        ['s2d_lte3_pct',        'Ship-to-deliver ≤ 3 days %'],
        ['o2d_lte5_pct',        'Order-to-deliver ≤ 5 days %'],
        ['avg_processing',      'Average processing TAT days'],
        ['avg_pickup_tat',      'Average pickup TAT days'],
        ['avg_intransit',       'Average in-transit days'],
        ['avg_o2d',             'Average order-to-deliver days'],
    ],
    col_widths=[1.8, 4.8]
)

# ── Q5 ──
h2(doc, 'Q5 — Courier-wise Performance (main.py ~line 218)')
para(doc, 'Purpose: Rank each carrier by volume and show their per-KPI performance side by side.')
para(doc, 'Courier normalisation:')
bullet(doc, 'Names lowercased for matching: bluedart → Bluedart, ekart → Ekart, xpressbees → XpressBees')
bullet(doc, "Special rule: if courier_partner LIKE '%delhivery%' AND awb LIKE '5448%' → label as 'Delhivery NDD'; otherwise 'Delhivery'")
bullet(doc, 'Remaining unmatched names passed through as-is')
add_table(doc,
    headers=['Metric', 'Description'],
    rows=[
        ['shipments',       'Total shipments for this courier'],
        ['del_pct',         'Delivery rate %'],
        ['rto_pct',         'RTO rate %'],
        ['fasr_pct',        'First attempt success rate %'],
        ['edd_pct',         'EDD breach rate %'],
        ['ndr_pct',         'NDR rate %'],
        ['ndr_res_pct',     'NDR resolution rate %'],
        ['avg_pickup_tat',  'Average pickup TAT days'],
        ['avg_intransit',   'Average in-transit days'],
        ['avg_o2d',         'Average order-to-deliver days'],
    ],
    col_widths=[1.8, 4.8]
)
para(doc, 'Order: ORDER BY shipments DESC')

# ── Q6 ──
h2(doc, 'Q6 — Facility Performance (main.py ~line 275)')
para(doc, "Purpose: Show warehouse-level processing speed and allocation accuracy.")
para(doc, "Facility grouping: pickup_city mapped to facility code; PNQ + MUM combined as 'PNQ + MUM'")
add_table(doc,
    headers=['Metric', 'Meaning'],
    rows=[
        ['alloc_pct',          '% of total period shipments from this facility'],
        ['correct_alloc_pct',  'Warehouse fit % (same logic as Q3)'],
        ['processed_24hr_pct', '% where AWB created → pickup ≤ 24 hours'],
        ['avg_processing',     'Avg order → AWB days'],
        ['pickup_24hr_pct',    '% where AWB → physical pickup ≤ 24 hours'],
        ['avg_pickup_tat',     'Avg AWB → pickup days'],
        ['avg_intransit',      'Avg pickup → delivery days'],
        ['avg_o2d',            'Avg order → delivery days'],
    ],
    col_widths=[1.8, 4.8]
)

# ── Q7 ──
h2(doc, 'Q7 — NDR Analysis (main.py ~line 340)')
para(doc, 'Purpose: Analyse Non-Delivery Reattempts — shipments the courier tried but could not deliver on first attempt.')
para(doc, 'NDR definition: out_for_delivery_attempts >= 1 AND NOT (attempts = 1 AND status = \'Delivered\')')
add_table(doc,
    headers=['Metric', 'Description'],
    rows=[
        ['shipments',        'Total shipments for this courier'],
        ['ndr_count',        'Count of NDR shipments'],
        ['ndr_pct',          'NDR rate %'],
        ['ndr_resolved',     'NDR shipments eventually delivered'],
        ['ndr_resolved_pct', 'NDR resolution rate %'],
        ['became_rto_pct',   '% of NDR that became RTO'],
        ['avg_attempts',     'Average delivery attempts'],
        ['avg_intransit',    'Average in-transit days'],
        ['avg_o2d',          'Average order-to-deliver days'],
    ],
    col_widths=[1.8, 4.8]
)

# ── Q8 ──
h2(doc, 'Q8 — COD vs Prepaid (main.py ~line 393)')
para(doc, (
    'Purpose: Compare performance between cash-on-delivery and prepaid orders. COD orders have '
    'higher RTO rates; this section quantifies the gap.'
))
para(doc, 'Grouping: payment_mode (COD / Prepaid)')
para(doc, 'Extra metric: z_rto_pct — RTOs where out_for_delivery_attempts = 0 (shipment returned without leaving facility)')

# ── Q9 ──
h2(doc, 'Q9 — City Tier Breakdown (main.py ~line 443)')
para(doc, 'Purpose: Compare metro (Tier I) vs semi-urban (Tier II) vs rural (Tier III) delivery performance.')
para(doc, 'Join: LEFT JOIN production.pincode_city_master ON drop_pincode = Pincode → adds City_Tier')
add_table(doc,
    headers=['Metric', 'Description'],
    rows=[
        ['share_pct',    '% of total shipments from this tier'],
        ['del_pct',      'Delivery rate %'],
        ['rto_pct',      'RTO rate %'],
        ['edd_pct',      'EDD breach rate %'],
        ['ndr_pct',      'NDR rate %'],
        ['ndr_res_pct',  'NDR resolution rate %'],
        ['z_rto_pct',    'Zero-attempt RTO rate %'],
        ['avg_processing','Avg processing TAT days'],
        ['avg_pickup_tat','Avg pickup TAT days'],
        ['avg_intransit', 'Avg in-transit days'],
        ['avg_o2d',       'Avg order-to-deliver days'],
    ],
    col_widths=[1.8, 4.8]
)

# ── Q10 ──
h2(doc, 'Q10 — Zone Breakdown (main.py ~line 493)')
para(doc, 'Purpose: Break performance by Frido\'s internal zone classification (delivery distance band).')
para(doc, 'Zone mapping (from zone_by_frido column):')
bullet(doc, 'Zone A = Local (same city)')
bullet(doc, 'Zone B = Metro-to-metro')
bullet(doc, 'Zone C = Metro-to-non-metro')
bullet(doc, 'Zone D = Cross-country')
bullet(doc, 'Zone E = Special/Other')

# ── Q11 ──
h2(doc, 'Q11 — Transit TAT Distribution (main.py ~line 541)')
para(doc, 'Purpose: Show what % of delivered shipments fell into each speed bucket, per courier.')
para(doc, 'Calculation: DATE_DIFF(delivery_date, pickup_date, DAY)')
add_table(doc,
    headers=['Bucket', 'Condition'],
    rows=[
        ['lte2d', '≤ 2 days'],
        ['d3_4',  '3–4 days'],
        ['d5',    'Exactly 5 days'],
        ['d5plus', '> 5 days'],
    ],
    col_widths=[1.8, 4.8]
)

# ── Q12 ──
h2(doc, 'Q12 — RVP Detailed Metrics (main.py ~line 577)')
para(doc, 'Purpose: Full reverse-pickup funnel with SLA compliance.')
add_table(doc,
    headers=['Metric', 'Meaning'],
    rows=[
        ['rvp_created',       'Total reverse requests in period'],
        ['rvp_picked_up',     'Count where pickup_date IS NOT NULL'],
        ['rvp_delivered',     'Count where delivery_date IS NOT NULL (received at warehouse)'],
        ['rvp_pickup_lte2d',  'Pickups completed within 2 days of request'],
        ['rvp_wh_lte5d',      'Warehouse receipts within 5 days of pickup'],
        ['avg_rvp_pickup',    'Avg days from request → pickup'],
        ['avg_rvp_wh',        'Avg days from pickup → warehouse receipt'],
        ['avg_rvp_total',     'Avg days from request → warehouse receipt'],
    ],
    col_widths=[1.8, 4.8]
)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — Report HTML Structure
# ══════════════════════════════════════════════════════════════════════════════
h1(doc, 'Section 7 — Report HTML Structure')

para(doc, (
    'The report is a single self-contained HTML file. CSS is inlined by premailer so it renders '
    'correctly in email clients that strip <style> tags (Gmail, Outlook).'
))
para(doc, 'Visual theme: Dark blue header (#1F3864), white body, responsive at 768px breakpoint.')

add_table(doc,
    headers=['Section', 'Data Source', 'What It Shows'],
    rows=[
        ['Header',                'Computed dates',    'Title, period label, data freshness note'],
        ['Overall KPIs',          'Q1 + Q2 + Q3',      '12 KPI cards in a 4-column grid. Each card has a label, value, and red highlight if breached.'],
        ['Monthly Trend',         'Q4',                '6-month table with one row per month + Totals row. Columns: shipments, del%, RTO%, FASR%, EDD%, WH fit%, S2D ≤3d%, O2D ≤5d%, avg TATs.'],
        ['Courier Performance',   'Q5',                'Table ranked by shipment volume.'],
        ['Facility / Warehouse',  'Q6',                'One row per facility (PNQ+MUM, GGN, BLR, HYD, KOL, CHN).'],
        ['NDR Analysis',          'Q7',                'Per-courier NDR table.'],
        ['COD vs Prepaid',        'Q8',                'Two rows (COD, Prepaid).'],
        ['City Tier',             'Q9',                'Three rows (Tier I/II/III).'],
        ['Zone Breakdown',        'Q10',               'One row per zone A–E.'],
        ['Transit TAT Distribution','Q11',             'Per-courier speed buckets: ≤2d%, 3–4d%, 5d%, >5d%.'],
        ['Reverse Pickup (RVP)', 'Q12',                'One summary row: created, picked up, delivered, SLA compliance, avg TATs.'],
        ['Footer',               'Static',             '"Report generated on {today}"'],
    ],
    col_widths=[1.6, 1.2, 3.8]
)

h2(doc, 'HTML Generation Steps')
numbered(doc, 'Python string templates build each section as an HTML <table> or <div> block.')
numbered(doc, "Threshold checks are inline Python conditionals that add style='background:#ffe0e0' to individual <td> cells when breached.")
numbered(doc, 'All sections concatenated into a full <!DOCTYPE html> document.')
numbered(doc, 'premailer.transform(html) inlines every CSS rule.')
numbered(doc, 'Final string passed as the Graph API email body.')

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 8 — Threshold Rules
# ══════════════════════════════════════════════════════════════════════════════
h1(doc, 'Section 8 — Threshold Rules (Red Highlighting)')

para(doc, (
    'Cells turn red (background #ffe0e0) when a metric is outside its target range. '
    'Hardcoded in main.py as inline Python conditionals.'
))

add_table(doc,
    headers=['Metric', 'Red When', 'Target'],
    rows=[
        ['Delivery %',            '< 75%',  '≥ 75%'],
        ['RTO % (tables)',        '> 18%',  '≤ 18%'],
        ['RTO % (KPI card)',      '> 7%',   '≤ 7%'],
        ['FASR %',                '< 70%',  '≥ 70%'],
        ['EDD Breach %',          '> 30%',  '≤ 30%'],
        ['Warehouse Fit %',       '< 90%',  '≥ 90%'],
        ['NDR %',                 '> 15%',  '≤ 15%'],
        ['NDR Resolution %',      '< 60%',  '≥ 60%'],
        ['Avg In-Transit (days)', '> 3.0',  '≤ 3.0'],
        ['Avg O2D (days)',        '> 5.0',  '≤ 5.0'],
        ['Processing 24hr %',     '< 80%',  '≥ 80%'],
        ['Pickup 24hr %',         '< 75%',  '≥ 75%'],
        ['Transit > 5 days %',    '> 8%',   '≤ 8%'],
    ],
    col_widths=[2.0, 1.5, 1.5]
)

h2(doc, 'How to Change a Threshold')
para(doc, (
    'Search main.py for the metric name or current value. Each threshold is a simple Python '
    'comparison like:'
))
add_code_block(doc, "    bg = '#ffe0e0' if del_pct < 75 else 'white'")
para(doc, (
    'Change the value and redeploy. There is no config file for thresholds — they are inline '
    'in the HTML-building code.'
))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 9 — Email Delivery (Microsoft Graph API)
# ══════════════════════════════════════════════════════════════════════════════
h1(doc, 'Section 9 — Email Delivery (Microsoft Graph API)')

para(doc, (
    'The report is sent using Microsoft Graph API rather than SMTP. This avoids firewall/port '
    'issues in GCP and uses Frido\'s existing Microsoft 365 tenant.'
))

h2(doc, 'OAuth Flow')
numbered(doc, 'POST to https://login.microsoftonline.com/{OTP_FRIDO_TENANT_ID}/oauth2/v2.0/token')
numbered(doc, 'Body: grant_type=client_credentials, client_id, client_secret, scope=https://graph.microsoft.com/.default')
numbered(doc, 'Response: access_token (valid ~60 min)')
numbered(doc, 'POST to https://graph.microsoft.com/v1.0/users/{FROM_EMAIL}/sendMail with Authorization: Bearer {token}')
numbered(doc, 'saveToSentItems: false — the sent email does not appear in the sender\'s Sent folder')

h2(doc, 'Email Payload JSON')
email_json = '''{
  "message": {
    "subject": "Frido Logistics & Ops Performance Report | 16 Aug – 14 Sep 2026",
    "body": { "contentType": "HTML", "content": "<full HTML report>" },
    "toRecipients": [ ... ],
    "ccRecipients": [ ... ]
  },
  "saveToSentItems": false
}'''
add_code_block(doc, email_json)

h2(doc, 'Common Failure Modes')
add_table(doc,
    headers=['Symptom', 'Likely Cause', 'Fix'],
    rows=[
        ['401 Unauthorized from Graph API',
         'OTP_FRIDO_CLIENT_SECRET expired',
         'Rotate secret in Azure AD, update Secret Manager'],
        ['403 Forbidden',
         'App lacks Send-As permission on data.team@myfrido.com',
         'Add Mail.Send application permission in Azure AD'],
        ['400 Bad Request',
         'Malformed recipient address',
         'Check env vars for stray spaces or invalid emails'],
        ['Email not received',
         'Delivered to spam',
         'Mark data.team@myfrido.com as safe sender'],
    ],
    col_widths=[1.6, 2.1, 2.9]
)

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 10 — Deployment
# ══════════════════════════════════════════════════════════════════════════════
h1(doc, 'Section 10 — Deployment')

h2(doc, 'Prerequisites')
bullet(doc, 'gcloud CLI authenticated with Cloud Run Admin, Storage Admin, Secret Manager Admin roles on frido-429506')
bullet(doc, 'Docker daemon running locally')
bullet(doc, 'Secrets already created in Secret Manager: OTP_FRIDO_TENANT_ID, OTP_FRIDO_CLIENT_ID, OTP_FRIDO_CLIENT_SECRET, GCP_CREDENTIALS_B64')

h2(doc, 'Deploy Command')
add_code_block(doc, 'bash deploy.sh')

h2(doc, 'deploy.sh Steps')
numbered(doc, 'docker build -t gcr.io/frido-429506/logistics-report .')
numbered(doc, 'docker push gcr.io/frido-429506/logistics-report')
numbered(doc, (
    'gcloud run deploy logistics-report with: --image, --region asia-south1, '
    '--memory 1Gi, --timeout 540, --no-allow-unauthenticated, '
    '--set-secrets (4 secrets), --set-env-vars (EMAIL_TO, EMAIL_CC, FROM_EMAIL)'
))
numbered(doc, (
    'Creates/updates Cloud Scheduler job: name=logistics-report-daily, '
    'schedule=30 6 * * *, HTTP GET to Cloud Run URL, OIDC auth'
))

h2(doc, 'Cloud Run Configuration')
add_table(doc,
    headers=['Setting', 'Value'],
    rows=[
        ['Image',           'gcr.io/frido-429506/logistics-report'],
        ['Region',          'asia-south1 (Mumbai)'],
        ['Memory',          '1 GB'],
        ['Timeout',         '540 seconds'],
        ['Min instances',   '0 (scales to zero)'],
        ['Authentication',  'OIDC (no public access)'],
    ],
    col_widths=[2.0, 4.6]
)

h2(doc, 'Updating')
para(doc, (
    'For any code change, edit main.py (or other files), then re-run bash deploy.sh. '
    'The script always builds a new image and deploys a new revision.'
))

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 11 — Local Testing
# ══════════════════════════════════════════════════════════════════════════════
h1(doc, 'Section 11 — Local Testing')

para(doc, 'Use run_local.py to test without deploying and without emailing 26 people.')

h2(doc, 'What run_local.py Does')
numbered(doc, 'Reads env.yaml and exports all key-value pairs as environment variables.')
numbered(doc, 'Patches main.py in memory to replace today = date.today() with a hardcoded date (default: 2026-09-30).')
numbered(doc, 'Overrides EMAIL_TO to pranjal.t@myfrido.com only and clears EMAIL_CC.')
numbered(doc, 'Writes patched code to a temp file and executes it with exec().')

h2(doc, 'How to Run')
add_code_block(doc, '# Make sure env.yaml has real credential values (never commit these)\npython run_local.py')

h2(doc, 'Changing the Test Date')
para(doc, 'Open run_local.py and find:')
add_code_block(doc, '    today = date(2026, 9, 30)')
para(doc, 'Change it to any date. Query window = [today - 45 days, today - 15 days).')

h2(doc, 'Testing Without Sending Email')
para(doc, 'Add this line temporarily:')
add_code_block(doc, "    with open('/tmp/report_preview.html', 'w') as f:\n        f.write(html_content)")
para(doc, 'Then open /tmp/report_preview.html in a browser.')

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 12 — Error Handling & Monitoring
# ══════════════════════════════════════════════════════════════════════════════
h1(doc, 'Section 12 — Error Handling & Monitoring')

h2(doc, 'What Surfaces as Errors')
add_table(doc,
    headers=['Failure', 'How It Surfaces'],
    rows=[
        ['BigQuery auth failure',
         'Python exception, Cloud Run logs, job marked failed in Cloud Scheduler'],
        ['BigQuery query error',
         'Exception with BigQuery error message in Cloud Run logs'],
        ['Graph API 4xx/5xx',
         'resp.raise_for_status() raises exception — logged, job fails'],
        ['Azure AD token failure',
         'HTTP error on token POST — exception, job fails'],
        ['premailer CSS error',
         'Exception during HTML transform — job fails'],
    ],
    col_widths=[2.2, 4.4]
)

h2(doc, 'What Fails Silently')
bullet(doc, 'Bad recipient email in CC list: Graph API may silently skip invalid addresses. Check CC list in env.yaml carefully.')
bullet(doc, 'NULL BigQuery values: SAFE.PARSE_DATE() and SAFE.PARSE_TIMESTAMP() return NULL for unparseable values. Report shows "—" for those cells rather than crashing.')
bullet(doc, 'Outlier TAT values: Values outside capped ranges are excluded from averages via IF() conditions in SQL. Silently dropped, not flagged.')

h2(doc, 'Monitoring')
bullet(doc, 'Cloud Scheduler: Job history in GCP Console shows success/failure with HTTP response code.')
bullet(doc, 'Cloud Run logs: main.py prints progress: "Fetching data...", "All data fetched", "Building HTML...", "Email sent to N recipients (HTTP 202)".')
bullet(doc, 'No alerting is configured. For failure alerts, add Cloud Monitoring alert on Cloud Scheduler job failure or Cloud Run error log count > 0.')

h2(doc, 'Data Quality Safeguards in SQL')
bullet(doc, 'SAFE.PARSE_DATE() / SAFE.PARSE_TIMESTAMP() — never crash on bad date strings')
bullet(doc, 'NULLIF(denominator, 0) — prevents division-by-zero in all percentage calculations')
bullet(doc, 'DATE_DIFF results capped with IF(diff BETWEEN 0 AND N, diff, NULL) — excludes data entry errors')
bullet(doc, 'All joins are LEFT JOIN — missing pincode/state mappings produce NULL rather than dropping rows')

# ══════════════════════════════════════════════════════════════════════════════
# SECTION 13 — KPI Glossary
# ══════════════════════════════════════════════════════════════════════════════
h1(doc, 'Section 13 — KPI Glossary')

para(doc, 'Every abbreviation used in the report and codebase.')

add_table(doc,
    headers=['Abbreviation', 'Full Name', 'Definition'],
    rows=[
        ['AWB',          'Air Way Bill',                  'Unique shipment tracking number issued by the courier'],
        ['del%',         'Delivery Rate',                 '% of forward shipments delivered to the customer'],
        ['RTO%',         'Return to Origin Rate',         "% of forward shipments returned to Frido's warehouse"],
        ['FASR%',        'First Attempt Success Rate',    '% of delivered shipments delivered on the first delivery attempt'],
        ['RASR%',        'Reattempt Success Rate',        '% of NDR shipments eventually delivered after ≥1 failed attempt'],
        ['EDD Breach%',  'Expected Delivery Date Breach', '% of delivered shipments where actual delivery > EDD'],
        ['NDR',          'Non-Delivery Reattempt',        'Shipment where courier attempted delivery but failed, requiring reattempt'],
        ['NDR Res%',     'NDR Resolution Rate',           '% of NDR shipments eventually delivered (not returned)'],
        ['S2D ≤3d%',     'Ship-to-Deliver ≤ 3 days',     '% of delivered shipments where delivery_date - pickup_date ≤ 3'],
        ['O2D ≤5d%',     'Order-to-Deliver ≤ 5 days',    '% of delivered shipments where delivery_date - order_date ≤ 5'],
        ['O2D',          'Order to Delivery',             "Days from order placement to delivery at customer's door"],
        ['Processing TAT','Processing Turnaround Time',   'Days from order date to AWB creation (warehouse processing time)'],
        ['Pickup TAT',   'Pickup Turnaround Time',        'Days from AWB creation to physical pickup by courier'],
        ['Transit TAT',  'Transit Turnaround Time',       'Days from physical pickup to delivery'],
        ['WH Fit%',      'Warehouse Fit',                 '% of shipments correctly allocated to the nearest Frido warehouse'],
        ['Z-RTO%',       'Zero-attempt RTO',              '% of RTOs where out_for_delivery_attempts = 0 (never left facility)'],
        ['RVP',          'Reverse Pickup',                'Process of picking up a return/exchange from customer back to warehouse'],
        ['COD',          'Cash on Delivery',              'Customer pays cash at door; higher RTO risk'],
        ['Prepaid',      'Prepaid order',                 'Customer paid online; lower RTO risk'],
        ['EDD',          'Expected Delivery Date',        'Date the courier committed to deliver the shipment'],
        ['NDD',          'Next Day Delivery',             "Delhivery's express service (AWB starting with 5448)"],
        ['PNQ',          'Pune warehouse',                'Frido facility in Pune (interchangeable with MUM for allocation)'],
        ['MUM',          'Mumbai warehouse',              'Frido facility in Mumbai'],
        ['GGN',          'Gurgaon warehouse',             'Frido facility in Gurgaon (NCR)'],
        ['BLR',          'Bengaluru warehouse',           'Frido facility in Bengaluru'],
        ['HYD',          'Hyderabad warehouse',           'Frido facility in Hyderabad'],
        ['KOL',          'Kolkata warehouse',             'Frido facility in Kolkata'],
        ['CHN',          'Chennai warehouse',             'Frido facility in Chennai'],
    ],
    col_widths=[1.0, 1.8, 3.8]
)

# ── Save ────────────────────────────────────────
doc.save(OUTPUT_PATH)
print(f"Saved: {OUTPUT_PATH}")
print(f"Size : {os.path.getsize(OUTPUT_PATH):,} bytes")
