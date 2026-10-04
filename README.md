# cloud_run_logistics_report_Logistics-Ops-Performance-Report

A scheduled Google Cloud Run service that generates and emails a daily **Logistics & Ops Performance Report** for Frido.

## What it does

- Runs daily at **12:00 PM IST** via Cloud Scheduler
- Queries **BigQuery** (`frido-429506`) for shipment data from the last 30 days
- Computes **50+ KPIs** across delivery, RTO, FASR, EDD breach, NDR, warehouse fit, TAT, and reverse pickup
- Generates a **responsive HTML email** with 11 data sections and threshold-based red highlighting
- Sends it to **26 stakeholders** via Microsoft Graph API (Microsoft 365)

## Project structure

```
main.py           # Core logic: data fetch, KPI computation, HTML generation, email dispatch
requirements.txt  # Python dependencies
Dockerfile        # Container definition
deploy.sh         # Build, push, deploy to Cloud Run + create Cloud Scheduler job
env.yaml          # Config: email lists, Azure AD credentials, GCP credentials
run_local.py      # Local test helper (sends only to pranjal.t@myfrido.com)
DOCUMENTATION.docx  # Full developer documentation
```

## Quick start (local test)

```bash
# 1. Fill in real credentials in env.yaml (never commit these)
# 2. Run locally — sends report only to pranjal.t@myfrido.com
python run_local.py
```

## Deploy

```bash
bash deploy.sh
```

Requires `gcloud` CLI authenticated with Cloud Run Admin + Secret Manager Admin on `frido-429506`.

## Data sources (BigQuery)

| Table | Purpose |
|---|---|
| `production.Clickpost_Shipment_Tracking_Report` | All shipment records (primary source) |
| `inventory_sales_allocation.state_region_nearest_wh` | State → nearest warehouse mapping |
| `production.pincode_city_master` | Pincode → city tier mapping |

## Report sections

1. Overall KPIs (delivery %, RTO %, FASR %, EDD breach %, warehouse fit %, TATs)
2. Monthly Trend (6-month history)
3. Courier Performance (ranked by volume)
4. Facility / Warehouse Performance
5. NDR Analysis
6. COD vs Prepaid
7. City Tier Breakdown (Tier I / II / III)
8. Zone Breakdown (Zone A–E)
9. Transit TAT Distribution
10. Reverse Pickup (RVP) Metrics
11. Footer

## Documentation

See `DOCUMENTATION.docx` for full developer documentation including all SQL query details, KPI definitions, threshold rules, deployment steps, and architecture diagrams.
