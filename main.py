import sys
sys.stdout.reconfigure(encoding='utf-8')

import os, json, base64, requests
from datetime import date, timedelta
from premailer import transform
from google.cloud import bigquery
from google.oauth2 import service_account

def _load_bq_client():
    creds_b64 = os.environ.get('GCP_CREDENTIALS_B64')
    if creds_b64:
        sa_info = json.loads(base64.b64decode(creds_b64).decode('utf-8'))
    else:
        sa_path = os.path.join(os.path.dirname(__file__), '..', 'sa_key.json')
        with open(sa_path) as f:
            sa_info = json.load(f)
    creds = service_account.Credentials.from_service_account_info(
        sa_info, scopes=['https://www.googleapis.com/auth/cloud-platform']
    )
    return bigquery.Client(credentials=creds, project=sa_info['project_id'])

client = _load_bq_client()

TENANT_ID     = os.environ['OTP_FRIDO_TENANT_ID']
CLIENT_ID     = os.environ['OTP_FRIDO_CLIENT_ID']
CLIENT_SECRET = os.environ['OTP_FRIDO_CLIENT_SECRET']
FROM_EMAIL    = os.environ.get('FROM_EMAIL', 'reports@myfrido.com')
TO_EMAILS     = os.environ.get('EMAIL_TO', 'arif@myfrido.com,sachin.s@myfrido.com,amit.n@myfrido.com,sachin.m@myfrido.com,pranjal.t@myfrido.com,yash.p@myfrido.com').split(',')
CC_EMAILS     = os.environ.get('EMAIL_CC', 'mukesh.c@myfrido.com,abhishek.v@myfrido.com,ravindra.d@myfrido.com,saivarun.g@myfrido.com,akash.d@myfrido.com,sourav.b@myfrido.com,abhay.p@myfrido.com,atharva.s@myfrido.com,nikhil.k@myfrido.com,ashikesh.n@myfrido.com,yash.s@myfrido.com,suraj.s@myfrido.com,hemant.k@myfrido.com,tushar.g@myfrido.com,Rahul.m@myfrido.com,farukh.m@myfrido.com,Krishna.kadam@myfrido.com,ranjit.j@myfrido.com,sagar.k@myfrido.com,Syed.h@myfrido.com').split(',')

today      = date.today()
cutoff     = today - timedelta(days=15)       # 7 Sep
start_date = cutoff - timedelta(days=30)      # 8 Aug
W   = f"DATE('{start_date}')"
END = f"DATE('{cutoff}')"
period_label = f"{start_date.strftime('%d %b %Y')} – {(cutoff - timedelta(days=1)).strftime('%d %b %Y')} (30 days)"

def q(sql):
    return list(client.query(sql).result())

def pct(val):
    if val is None: return '—'
    return f"{val}%"

def days(val):
    if val is None: return '—'
    return f"{val}d"

def num(val):
    if val is None: return '—'
    return f"{val:,}"

# ── Fetch all data ────────────────────────────────────────────────────────────
print("Fetching KPI cards...")
kpi = q(f"""
WITH fwd AS (
  SELECT awb, courier_partner, payment_mode,
    UPPER(TRIM(pickup_city)) AS pickup_city,
    drop_state, clickpost_unified_status AS status,
    DATE(created_at) AS created_dt, DATE(pickup_date) AS pickup_dt,
    DATE(delivery_date) AS delivery_dt, DATE(order_date) AS order_dt,
    DATE(expected_delivery_date_by_courier_partner) AS edd_dt,
    SAFE.PARSE_DATE('%Y-%m-%d', SUBSTR(rto_mark_date, 1, 10)) AS rto_mark_dt,
    SAFE.PARSE_DATE('%Y-%m-%d', SUBSTR(latest_timestamp, 1, 10)) AS latest_ts_dt,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(created_at, 1, 19))   AS created_ts,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(pickup_date, 1, 19))  AS pickup_ts,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(delivery_date, 1, 19)) AS delivery_ts,
    SAFE_CAST(out_for_delivery_attempts AS INT64) AS ndr_attempts
  FROM `frido-429506.production.Clickpost_Shipment_Tracking_Report`
  WHERE DATE(created_at) >= {W} AND DATE(created_at) < {END}
    AND shipment_type = 'Forward'
)
SELECT
  COUNT(DISTINCT awb) AS total_shipments,
  COUNTIF(status = 'Delivered') AS delivered_cnt,
  ROUND(COUNTIF(status = 'Delivered') / COUNT(DISTINCT awb) * 100, 1) AS del_pct,
  ROUND(COUNTIF(status LIKE 'RTO%') / COUNT(DISTINCT awb) * 100, 1) AS rto_pct,
  ROUND(COUNTIF(status = 'Delivered' AND ndr_attempts = 1) / NULLIF(COUNTIF(ndr_attempts IS NOT NULL AND ndr_attempts != 0), 0) * 100, 1) AS fasr_pct,
  ROUND(COUNTIF(status = 'Delivered' AND ndr_attempts > 1) / NULLIF(COUNTIF(ndr_attempts IS NOT NULL AND ndr_attempts != 0), 0) * 100, 1) AS rasr_pct,
  ROUND(COUNTIF(status = 'Delivered' AND delivery_dt > edd_dt) / NULLIF(COUNTIF(status = 'Delivered' AND edd_dt IS NOT NULL), 0) * 100, 1) AS edd_pct,
  ROUND(COUNTIF(status = 'Delivered' AND DATE_DIFF(delivery_dt, pickup_dt, DAY) <= 3) / NULLIF(COUNTIF(status = 'Delivered'), 0) * 100, 1) AS s2d_lte3_pct,
  ROUND(COUNTIF(status = 'Delivered' AND DATE_DIFF(delivery_dt, order_dt, DAY) <= 5) / NULLIF(COUNTIF(status = 'Delivered'), 0) * 100, 1) AS o2d_lte5_pct,
  ROUND(AVG(IF(created_dt IS NOT NULL AND order_dt IS NOT NULL
    AND DATE_DIFF(created_dt, order_dt, DAY) BETWEEN 0 AND 10,
    DATE_DIFF(created_dt, order_dt, DAY), NULL)), 1) AS avg_processing,
  ROUND(AVG(IF(pickup_ts IS NOT NULL AND created_ts IS NOT NULL
    AND TIMESTAMP_DIFF(pickup_ts, created_ts, MINUTE) BETWEEN 0 AND 14400,
    TIMESTAMP_DIFF(pickup_ts, created_ts, MINUTE) / 1440.0, NULL)), 1) AS avg_pickup_tat,
  ROUND(AVG(IF(pickup_ts IS NOT NULL AND delivery_ts IS NOT NULL AND status = 'Delivered'
    AND TIMESTAMP_DIFF(delivery_ts, pickup_ts, MINUTE) BETWEEN 0 AND 28800,
    TIMESTAMP_DIFF(delivery_ts, pickup_ts, MINUTE) / 1440.0, NULL)), 1) AS avg_intransit,
  ROUND(AVG(CASE WHEN status = 'Delivered' AND delivery_dt IS NOT NULL AND order_dt IS NOT NULL
    AND DATE_DIFF(delivery_dt, order_dt, DAY) BETWEEN 0 AND 20
    THEN DATE_DIFF(delivery_dt, order_dt, DAY) END), 1) AS avg_o2d,
  ROUND(AVG(CASE WHEN status = 'RTO-Delivered' AND rto_mark_dt IS NOT NULL AND latest_ts_dt IS NOT NULL
    AND DATE_DIFF(latest_ts_dt, rto_mark_dt, DAY) BETWEEN 0 AND 20
    THEN DATE_DIFF(latest_ts_dt, rto_mark_dt, DAY) END), 1) AS avg_rto_delivered
FROM fwd
""")[0]

print("Fetching RVP KPI cards...")
rvp_kpi = q(f"""
SELECT
  ROUND(AVG(CASE WHEN DATE(pickup_date) IS NOT NULL THEN DATE_DIFF(DATE(pickup_date), DATE(created_at), DAY) END), 1) AS avg_rvp_days,
  ROUND(AVG(CASE WHEN clickpost_unified_status = 'Delivered' THEN DATE_DIFF(DATE(delivery_date), DATE(pickup_date), DAY) END), 1) AS avg_rvp_to_delivery_days
FROM `frido-429506.production.Clickpost_Shipment_Tracking_Report`
WHERE DATE(created_at) >= {W} AND DATE(created_at) < {END}
  AND shipment_type = 'Reverse' AND Return_Type IN ('Return', 'Exchange')
""")[0]

print("Fetching WH Fit % KPI...")
wh_fit_kpi = q(f"""
WITH fwd AS (
  SELECT awb,
    CASE
      WHEN UPPER(TRIM(pickup_city)) IN ('PUNE','MAVAL') THEN 'PNQ'
      WHEN UPPER(TRIM(pickup_city)) IN ('MUMBAI','BHIWANDI','THANE') THEN 'MUM'
      WHEN UPPER(TRIM(pickup_city)) IN ('GURUGRAM','GURGAON','DELHI','HARYANA') THEN 'GGN'
      WHEN UPPER(TRIM(pickup_city)) IN ('BENGALURU','BANGALORE') THEN 'BLR'
      WHEN UPPER(TRIM(pickup_city)) = 'HYDERABAD' THEN 'HYD'
      WHEN UPPER(TRIM(pickup_city)) = 'KOLKATA' THEN 'KOL'
      WHEN UPPER(TRIM(pickup_city)) = 'CHENNAI' THEN 'CHN'
      ELSE NULL
    END AS facility_wh,
    drop_state
  FROM `frido-429506.production.Clickpost_Shipment_Tracking_Report`
  WHERE DATE(created_at) >= {W} AND DATE(created_at) < {END}
    AND shipment_type = 'Forward'
),
wh_map AS (SELECT DISTINCT shipping_address_state, nearest_wh FROM `frido-429506.inventory_sales_allocation.state_region_nearest_wh`),
scored AS (
  SELECT f.awb, f.facility_wh,
    MAX(CASE
      WHEN f.facility_wh IN ('PNQ','MUM') AND w.nearest_wh IN ('PNQ','MUM') THEN 1
      WHEN f.facility_wh NOT IN ('PNQ','MUM') AND f.facility_wh = w.nearest_wh THEN 1
      ELSE 0
    END) AS is_correct_alloc
  FROM fwd f LEFT JOIN wh_map w ON f.drop_state = w.shipping_address_state
  WHERE f.facility_wh IS NOT NULL
  GROUP BY 1,2
)
SELECT ROUND(COUNTIF(is_correct_alloc = 1) / COUNT(DISTINCT awb) * 100, 1) AS wh_fit_pct
FROM scored
""")[0]

print("Fetching monthly trend...")
monthly = q(f"""
WITH base AS (
  SELECT c.awb, c.clickpost_unified_status, c.created_at, c.delivery_date, c.pickup_date,
    c.order_date, c.expected_delivery_date_by_courier_partner,
    SAFE_CAST(c.out_for_delivery_attempts AS INT64) AS ofd_attempts,
    CASE
      WHEN UPPER(TRIM(c.pickup_city)) IN ('PUNE','MAVAL') THEN 'PNQ'
      WHEN UPPER(TRIM(c.pickup_city)) IN ('MUMBAI','BHIWANDI','THANE') THEN 'MUM'
      WHEN UPPER(TRIM(c.pickup_city)) IN ('GURUGRAM','GURGAON','DELHI','HARYANA') THEN 'GGN'
      WHEN UPPER(TRIM(c.pickup_city)) IN ('BENGALURU','BANGALORE') THEN 'BLR'
      WHEN UPPER(TRIM(c.pickup_city)) = 'HYDERABAD' THEN 'HYD'
      WHEN UPPER(TRIM(c.pickup_city)) = 'KOLKATA' THEN 'KOL'
      WHEN UPPER(TRIM(c.pickup_city)) = 'CHENNAI' THEN 'CHN'
      ELSE NULL
    END AS facility_wh,
    c.drop_state
  FROM `frido-429506.production.Clickpost_Shipment_Tracking_Report` c
  WHERE DATE(c.created_at) >= DATE_SUB(DATE_TRUNC({END}, MONTH), INTERVAL 6 MONTH)
    AND DATE(c.created_at) < {END}
    AND c.shipment_type = 'Forward'
),
wh_map AS (SELECT DISTINCT shipping_address_state, nearest_wh FROM `frido-429506.inventory_sales_allocation.state_region_nearest_wh`),
base_with_alloc AS (
  SELECT b.*, MAX(CASE
    WHEN b.facility_wh IN ('PNQ','MUM') AND w.nearest_wh IN ('PNQ','MUM') THEN 1
    WHEN b.facility_wh NOT IN ('PNQ','MUM') AND b.facility_wh = w.nearest_wh THEN 1
    ELSE 0
  END) AS is_correct_alloc
  FROM base b LEFT JOIN wh_map w ON b.drop_state = w.shipping_address_state
  GROUP BY 1,2,3,4,5,6,7,8,9,10
)
SELECT
  FORMAT_DATE('%b %Y', DATE_TRUNC(DATE(created_at), MONTH)) AS month_label,
  DATE_TRUNC(DATE(created_at), MONTH) AS month_dt,
  COUNT(DISTINCT awb) AS shipments,
  ROUND(COUNTIF(clickpost_unified_status = 'Delivered') / COUNT(DISTINCT awb) * 100, 1) AS del_pct,
  ROUND(COUNTIF(clickpost_unified_status LIKE 'RTO%') / COUNT(DISTINCT awb) * 100, 1) AS rto_pct,
  ROUND(COUNTIF(clickpost_unified_status = 'Delivered' AND ofd_attempts = 1)
    / NULLIF(COUNTIF(ofd_attempts IS NOT NULL AND ofd_attempts != 0), 0) * 100, 1) AS fasr_pct,
  ROUND(COUNTIF(clickpost_unified_status = 'Delivered' AND DATE(delivery_date) > DATE(expected_delivery_date_by_courier_partner))
    / NULLIF(COUNTIF(clickpost_unified_status = 'Delivered' AND expected_delivery_date_by_courier_partner IS NOT NULL), 0) * 100, 1) AS edd_pct,
  ROUND(COUNTIF(facility_wh IS NOT NULL AND is_correct_alloc = 1)
    / NULLIF(COUNTIF(facility_wh IS NOT NULL), 0) * 100, 1) AS correct_alloc_pct,
  ROUND(COUNTIF(clickpost_unified_status = 'Delivered' AND DATE_DIFF(DATE(delivery_date), DATE(pickup_date), DAY) <= 3)
    / NULLIF(COUNTIF(clickpost_unified_status = 'Delivered'), 0) * 100, 1) AS s2d_lte3_pct,
  ROUND(COUNTIF(clickpost_unified_status = 'Delivered' AND DATE_DIFF(DATE(delivery_date), DATE(order_date), DAY) <= 5)
    / NULLIF(COUNTIF(clickpost_unified_status = 'Delivered'), 0) * 100, 1) AS o2d_lte5_pct,
  ROUND(AVG(IF(DATE(created_at) IS NOT NULL AND DATE(order_date) IS NOT NULL
    AND DATE_DIFF(DATE(created_at), DATE(order_date), DAY) BETWEEN 0 AND 10,
    DATE_DIFF(DATE(created_at), DATE(order_date), DAY), NULL)), 1) AS avg_processing,
  ROUND(AVG(IF(SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(pickup_date, 1, 19)) IS NOT NULL
    AND SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(created_at, 1, 19)) IS NOT NULL
    AND TIMESTAMP_DIFF(SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(pickup_date, 1, 19)),
      SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(created_at, 1, 19)), MINUTE) BETWEEN 0 AND 14400,
    TIMESTAMP_DIFF(SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(pickup_date, 1, 19)),
      SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(created_at, 1, 19)), MINUTE) / 1440.0, NULL)), 1) AS avg_pickup_tat,
  ROUND(AVG(IF(SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(pickup_date, 1, 19)) IS NOT NULL
    AND SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(delivery_date, 1, 19)) IS NOT NULL
    AND clickpost_unified_status = 'Delivered'
    AND TIMESTAMP_DIFF(SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(delivery_date, 1, 19)),
      SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(pickup_date, 1, 19)), MINUTE) BETWEEN 0 AND 28800,
    TIMESTAMP_DIFF(SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(delivery_date, 1, 19)),
      SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(pickup_date, 1, 19)), MINUTE) / 1440.0, NULL)), 1) AS avg_intransit,
  ROUND(AVG(CASE WHEN clickpost_unified_status = 'Delivered' AND DATE(delivery_date) IS NOT NULL AND DATE(order_date) IS NOT NULL
    AND DATE_DIFF(DATE(delivery_date), DATE(order_date), DAY) BETWEEN 0 AND 20
    THEN DATE_DIFF(DATE(delivery_date), DATE(order_date), DAY) END), 1) AS avg_o2d
FROM base_with_alloc
GROUP BY 1,2 ORDER BY 2
""")

print("Fetching courier wise...")
couriers = q(f"""
WITH base AS (
  SELECT
    CASE
      WHEN LOWER(courier_partner) LIKE '%bluedart%' THEN 'Bluedart'
      WHEN LOWER(courier_partner) LIKE '%ekart%' THEN 'Ekart'
      WHEN LOWER(courier_partner) LIKE '%elastic%' THEN 'ElasticRun'
      WHEN LOWER(courier_partner) LIKE '%delhivery%' AND LEFT(awb, 4) = '5448' THEN 'Delhivery NDD'
      WHEN LOWER(courier_partner) LIKE '%delhivery%' THEN 'Delhivery'
      WHEN LOWER(courier_partner) LIKE '%safexpress%' THEN 'Safexpress'
      WHEN LOWER(courier_partner) LIKE '%shadowfax%' THEN 'Shadowfax'
      WHEN LOWER(courier_partner) LIKE '%shiprocket%' THEN 'Shiprocket'
      WHEN LOWER(courier_partner) LIKE '%sky air%' OR LOWER(courier_partner) LIKE '%skye air%' THEN 'Skye Air'
      WHEN LOWER(courier_partner) LIKE '%swift%' THEN 'Swift'
      WHEN LOWER(courier_partner) LIKE '%urbane bolt%' OR LOWER(courier_partner) LIKE '%urbanbolt%' THEN 'Urbane Bolt'
      WHEN LOWER(courier_partner) LIKE '%wareiq%' THEN 'WareIQ'
      WHEN LOWER(courier_partner) LIKE '%zippee%' THEN 'Zippee'
      ELSE courier_partner
    END AS courier_group,
    awb, clickpost_unified_status,
    SAFE_CAST(out_for_delivery_attempts AS INT64) AS ofd_attempts,
    DATE(delivery_date) AS delivery_dt, DATE(order_date) AS order_dt,
    DATE(expected_delivery_date_by_courier_partner) AS edd_dt,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(created_at, 1, 19))   AS created_ts,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(pickup_date, 1, 19))  AS pickup_ts,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(delivery_date, 1, 19)) AS delivery_ts
  FROM `frido-429506.production.Clickpost_Shipment_Tracking_Report`
  WHERE DATE(created_at) >= {W} AND DATE(created_at) < {END}
    AND shipment_type = 'Forward'
)
SELECT courier_group AS courier_partner,
  COUNT(DISTINCT awb) AS shipments,
  ROUND(COUNTIF(clickpost_unified_status = 'Delivered') / COUNT(DISTINCT awb) * 100, 1) AS del_pct,
  ROUND(COUNTIF(clickpost_unified_status LIKE 'RTO%') / COUNT(DISTINCT awb) * 100, 1) AS rto_pct,
  ROUND(COUNTIF(clickpost_unified_status = 'Delivered' AND ofd_attempts = 1)
    / NULLIF(COUNTIF(ofd_attempts IS NOT NULL AND ofd_attempts != 0), 0) * 100, 1) AS fasr_pct,
  ROUND(COUNTIF(clickpost_unified_status = 'Delivered' AND delivery_dt > edd_dt)
    / NULLIF(COUNTIF(clickpost_unified_status = 'Delivered' AND edd_dt IS NOT NULL), 0) * 100, 1) AS edd_pct,
  ROUND(COUNTIF(ofd_attempts >= 1 AND NOT (ofd_attempts = 1 AND clickpost_unified_status = 'Delivered'))
    / COUNT(DISTINCT awb) * 100, 1) AS ndr_pct,
  ROUND(COUNTIF(ofd_attempts >= 1 AND NOT (ofd_attempts = 1 AND clickpost_unified_status = 'Delivered')
      AND clickpost_unified_status = 'Delivered')
    / NULLIF(COUNTIF(ofd_attempts >= 1 AND NOT (ofd_attempts = 1 AND clickpost_unified_status = 'Delivered')), 0) * 100, 1) AS ndr_res_pct,
  ROUND(AVG(IF(pickup_ts IS NOT NULL AND created_ts IS NOT NULL
    AND TIMESTAMP_DIFF(pickup_ts, created_ts, MINUTE) BETWEEN 0 AND 14400,
    TIMESTAMP_DIFF(pickup_ts, created_ts, MINUTE) / 1440.0, NULL)), 1) AS avg_pickup_tat,
  ROUND(AVG(IF(pickup_ts IS NOT NULL AND delivery_ts IS NOT NULL AND clickpost_unified_status = 'Delivered'
    AND TIMESTAMP_DIFF(delivery_ts, pickup_ts, MINUTE) BETWEEN 0 AND 28800,
    TIMESTAMP_DIFF(delivery_ts, pickup_ts, MINUTE) / 1440.0, NULL)), 1) AS avg_intransit,
  ROUND(AVG(CASE WHEN clickpost_unified_status = 'Delivered' AND delivery_dt IS NOT NULL AND order_dt IS NOT NULL
    AND DATE_DIFF(delivery_dt, order_dt, DAY) BETWEEN 0 AND 20
    THEN DATE_DIFF(delivery_dt, order_dt, DAY) END), 1) AS avg_o2d
FROM base
GROUP BY 1 ORDER BY shipments DESC
""")

print("Fetching facility...")
facilities = q(f"""
WITH fwd AS (
  SELECT awb,
    CASE
      WHEN UPPER(TRIM(pickup_city)) IN ('PUNE','MAVAL') THEN 'PNQ'
      WHEN UPPER(TRIM(pickup_city)) IN ('MUMBAI','BHIWANDI','THANE') THEN 'MUM'
      WHEN UPPER(TRIM(pickup_city)) IN ('GURUGRAM','GURGAON','DELHI','HARYANA') THEN 'GGN'
      WHEN UPPER(TRIM(pickup_city)) IN ('BENGALURU','BANGALORE') THEN 'BLR'
      WHEN UPPER(TRIM(pickup_city)) = 'HYDERABAD' THEN 'HYD'
      WHEN UPPER(TRIM(pickup_city)) = 'KOLKATA' THEN 'KOL'
      WHEN UPPER(TRIM(pickup_city)) = 'CHENNAI' THEN 'CHN'
      ELSE NULL
    END AS facility_wh,
    drop_state, clickpost_unified_status AS status,
    DATE(created_at) AS created_dt, DATE(pickup_date) AS pickup_dt,
    DATE(delivery_date) AS delivery_dt, DATE(order_date) AS order_dt,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(created_at, 1, 19))   AS created_ts,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(pickup_date, 1, 19))  AS pickup_ts,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(delivery_date, 1, 19)) AS delivery_ts
  FROM `frido-429506.production.Clickpost_Shipment_Tracking_Report`
  WHERE DATE(created_at) >= {W} AND DATE(created_at) < {END}
    AND shipment_type = 'Forward'
),
wh_map AS (SELECT DISTINCT shipping_address_state, nearest_wh FROM `frido-429506.inventory_sales_allocation.state_region_nearest_wh`),
fwd_with_wh AS (
  SELECT f.awb,
    CASE WHEN f.facility_wh IN ('PNQ','MUM') THEN 'PNQ + MUM' ELSE f.facility_wh END AS facility_grp,
    f.drop_state, f.status, f.created_dt, f.pickup_dt,
    f.delivery_dt, f.order_dt, f.pickup_ts, f.delivery_ts, f.created_ts,
    f.facility_wh,
    w.nearest_wh
  FROM fwd f LEFT JOIN wh_map w ON f.drop_state = w.shipping_address_state
),
-- demand-based correct/wrong: grouped by nearest WH (where order SHOULD come from)
-- correct = shipped from right WH for that state; wrong = shipped from wrong WH
demand_correct AS (
  SELECT
    CASE WHEN w.nearest_wh IN ('PNQ','MUM') THEN 'PNQ + MUM' ELSE w.nearest_wh END AS demand_grp,
    COUNTIF(
      (f.facility_wh IN ('PNQ','MUM') AND w.nearest_wh IN ('PNQ','MUM'))
      OR (f.facility_wh NOT IN ('PNQ','MUM') AND f.facility_wh = w.nearest_wh)
    ) AS correct_cnt,
    COUNT(*) AS judged_cnt
  FROM fwd f
  JOIN wh_map w ON f.drop_state = w.shipping_address_state
  WHERE f.facility_wh IS NOT NULL
  GROUP BY demand_grp
),
total AS (SELECT COUNT(DISTINCT awb) AS total_awb FROM fwd)
SELECT f.facility_grp AS facility_wh,
  COUNT(DISTINCT f.awb) AS shipments,
  ROUND(COUNT(DISTINCT f.awb) / MAX(t.total_awb) * 100, 1) AS alloc_pct,
  MAX(d.correct_cnt) AS correct_alloc_cnt,
  ROUND(MAX(d.correct_cnt) / NULLIF(MAX(d.judged_cnt), 0) * 100, 1) AS correct_alloc_pct,
  COUNTIF(f.created_dt IS NOT NULL AND f.order_dt IS NOT NULL AND DATE_DIFF(f.created_dt, f.order_dt, DAY) <= 1) AS processed_24hr_cnt,
  ROUND(COUNTIF(f.created_dt IS NOT NULL AND f.order_dt IS NOT NULL AND DATE_DIFF(f.created_dt, f.order_dt, DAY) <= 1) / COUNT(DISTINCT f.awb) * 100, 1) AS processed_24hr_pct,
  ROUND(AVG(IF(f.created_dt IS NOT NULL AND f.order_dt IS NOT NULL AND DATE_DIFF(f.created_dt, f.order_dt, DAY) BETWEEN 0 AND 10, DATE_DIFF(f.created_dt, f.order_dt, DAY), NULL)), 1) AS avg_processing,
  COUNTIF(f.pickup_dt IS NOT NULL AND f.created_dt IS NOT NULL AND DATE_DIFF(f.pickup_dt, f.created_dt, DAY) <= 1) AS pickup_24hr_cnt,
  ROUND(COUNTIF(f.pickup_dt IS NOT NULL AND f.created_dt IS NOT NULL AND DATE_DIFF(f.pickup_dt, f.created_dt, DAY) <= 1) / COUNT(DISTINCT f.awb) * 100, 1) AS pickup_24hr_pct,
  ROUND(AVG(IF(f.pickup_ts IS NOT NULL AND f.created_ts IS NOT NULL
    AND TIMESTAMP_DIFF(f.pickup_ts, f.created_ts, MINUTE) BETWEEN 0 AND 14400,
    TIMESTAMP_DIFF(f.pickup_ts, f.created_ts, MINUTE) / 1440.0, NULL)), 1) AS avg_pickup_tat,
  ROUND(AVG(IF(f.pickup_ts IS NOT NULL AND f.delivery_ts IS NOT NULL AND f.status = 'Delivered'
    AND TIMESTAMP_DIFF(f.delivery_ts, f.pickup_ts, MINUTE) BETWEEN 0 AND 28800,
    TIMESTAMP_DIFF(f.delivery_ts, f.pickup_ts, MINUTE) / 1440.0, NULL)), 1) AS avg_intransit,
  ROUND(AVG(CASE WHEN f.status = 'Delivered' AND f.delivery_dt IS NOT NULL AND f.order_dt IS NOT NULL
    AND DATE_DIFF(f.delivery_dt, f.order_dt, DAY) BETWEEN 0 AND 20
    THEN DATE_DIFF(f.delivery_dt, f.order_dt, DAY) END), 1) AS avg_o2d
FROM fwd_with_wh f
CROSS JOIN total t
LEFT JOIN demand_correct d ON f.facility_grp = d.demand_grp
WHERE f.facility_grp IS NOT NULL
GROUP BY 1 ORDER BY shipments DESC
""")

print("Fetching NDR...")
ndr_rows = q(f"""
WITH base AS (
  SELECT
    CASE
      WHEN LOWER(courier_partner) LIKE '%bluedart%' THEN 'Bluedart'
      WHEN LOWER(courier_partner) LIKE '%ekart%' THEN 'Ekart'
      WHEN LOWER(courier_partner) LIKE '%elastic%' THEN 'ElasticRun'
      WHEN LOWER(courier_partner) LIKE '%delhivery%' AND LEFT(awb, 4) = '5448' THEN 'Delhivery NDD'
      WHEN LOWER(courier_partner) LIKE '%delhivery%' THEN 'Delhivery'
      WHEN LOWER(courier_partner) LIKE '%safexpress%' THEN 'Safexpress'
      WHEN LOWER(courier_partner) LIKE '%shadowfax%' THEN 'Shadowfax'
      WHEN LOWER(courier_partner) LIKE '%shiprocket%' THEN 'Shiprocket'
      WHEN LOWER(courier_partner) LIKE '%sky air%' OR LOWER(courier_partner) LIKE '%skye air%' THEN 'Skye Air'
      WHEN LOWER(courier_partner) LIKE '%swift%' THEN 'Swift'
      WHEN LOWER(courier_partner) LIKE '%urbane bolt%' OR LOWER(courier_partner) LIKE '%urbanbolt%' THEN 'Urbane Bolt'
      WHEN LOWER(courier_partner) LIKE '%wareiq%' THEN 'WareIQ'
      WHEN LOWER(courier_partner) LIKE '%zippee%' THEN 'Zippee'
      ELSE courier_partner
    END AS courier_group,
    awb, clickpost_unified_status,
    SAFE_CAST(out_for_delivery_attempts AS INT64) AS ofd_attempts,
    DATE(delivery_date) AS delivery_dt, DATE(order_date) AS order_dt,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(pickup_date, 1, 19))  AS pickup_ts,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(delivery_date, 1, 19)) AS delivery_ts
  FROM `frido-429506.production.Clickpost_Shipment_Tracking_Report`
  WHERE DATE(created_at) >= {W} AND DATE(created_at) < {END}
    AND shipment_type = 'Forward'
)
SELECT courier_group AS courier_partner, COUNT(DISTINCT awb) AS shipments,
  COUNTIF(ofd_attempts >= 1 AND NOT (ofd_attempts = 1 AND clickpost_unified_status = 'Delivered')) AS ndr_count,
  ROUND(COUNTIF(ofd_attempts >= 1 AND NOT (ofd_attempts = 1 AND clickpost_unified_status = 'Delivered'))
    / COUNT(DISTINCT awb) * 100, 1) AS ndr_pct,
  COUNTIF(ofd_attempts >= 1 AND NOT (ofd_attempts = 1 AND clickpost_unified_status = 'Delivered')
    AND clickpost_unified_status = 'Delivered') AS ndr_resolved,
  ROUND(COUNTIF(ofd_attempts >= 1 AND NOT (ofd_attempts = 1 AND clickpost_unified_status = 'Delivered')
    AND clickpost_unified_status = 'Delivered')
    / NULLIF(COUNTIF(ofd_attempts >= 1 AND NOT (ofd_attempts = 1 AND clickpost_unified_status = 'Delivered')), 0) * 100, 1) AS ndr_resolved_pct,
  ROUND(COUNTIF(clickpost_unified_status LIKE 'RTO%' AND ofd_attempts >= 1)
    / NULLIF(COUNTIF(ofd_attempts >= 1 AND NOT (ofd_attempts = 1 AND clickpost_unified_status = 'Delivered')), 0) * 100, 1) AS became_rto_pct,
  ROUND(AVG(CASE WHEN ofd_attempts >= 1 AND NOT (ofd_attempts = 1 AND clickpost_unified_status = 'Delivered') THEN CAST(ofd_attempts AS FLOAT64) END), 1) AS avg_attempts,
  ROUND(AVG(IF(ofd_attempts >= 1 AND NOT (ofd_attempts = 1 AND clickpost_unified_status = 'Delivered')
    AND pickup_ts IS NOT NULL AND delivery_ts IS NOT NULL AND clickpost_unified_status = 'Delivered'
    AND TIMESTAMP_DIFF(delivery_ts, pickup_ts, MINUTE) BETWEEN 0 AND 28800,
    TIMESTAMP_DIFF(delivery_ts, pickup_ts, MINUTE) / 1440.0, NULL)), 1) AS avg_intransit,
  ROUND(AVG(CASE WHEN ofd_attempts >= 1 AND NOT (ofd_attempts = 1 AND clickpost_unified_status = 'Delivered')
    AND clickpost_unified_status = 'Delivered' AND delivery_dt IS NOT NULL AND order_dt IS NOT NULL
    AND DATE_DIFF(delivery_dt, order_dt, DAY) BETWEEN 0 AND 20
    THEN DATE_DIFF(delivery_dt, order_dt, DAY) END), 1) AS avg_o2d
FROM base
GROUP BY 1 ORDER BY shipments DESC
""")

print("Fetching COD vs Prepaid...")
cod_rows = q(f"""
SELECT payment_mode, COUNT(DISTINCT awb) AS shipments,
  ROUND(COUNT(DISTINCT awb) / SUM(COUNT(DISTINCT awb)) OVER() * 100, 1) AS share_pct,
  ROUND(COUNTIF(clickpost_unified_status = 'Delivered') / COUNT(DISTINCT awb) * 100, 1) AS del_pct,
  ROUND(COUNTIF(clickpost_unified_status LIKE 'RTO%') / COUNT(DISTINCT awb) * 100, 1) AS rto_pct,
  COUNTIF(clickpost_unified_status LIKE 'RTO%' AND SAFE_CAST(out_for_delivery_attempts AS INT64) = 0) AS z_rto_cnt,
  ROUND(COUNTIF(clickpost_unified_status LIKE 'RTO%' AND SAFE_CAST(out_for_delivery_attempts AS INT64) = 0) / COUNT(DISTINCT awb) * 100, 1) AS z_rto_pct,
  ROUND(COUNTIF(clickpost_unified_status = 'Delivered' AND DATE(delivery_date) > DATE(expected_delivery_date_by_courier_partner))
    / NULLIF(COUNTIF(clickpost_unified_status = 'Delivered' AND expected_delivery_date_by_courier_partner IS NOT NULL), 0) * 100, 1) AS edd_pct,
  COUNTIF(SAFE_CAST(out_for_delivery_attempts AS INT64) >= 1
    AND NOT (SAFE_CAST(out_for_delivery_attempts AS INT64) = 1 AND clickpost_unified_status = 'Delivered')) AS ndr_cnt,
  ROUND(COUNTIF(SAFE_CAST(out_for_delivery_attempts AS INT64) >= 1
    AND NOT (SAFE_CAST(out_for_delivery_attempts AS INT64) = 1 AND clickpost_unified_status = 'Delivered'))
    / COUNT(DISTINCT awb) * 100, 1) AS ndr_pct,
  COUNTIF(SAFE_CAST(out_for_delivery_attempts AS INT64) >= 1
    AND NOT (SAFE_CAST(out_for_delivery_attempts AS INT64) = 1 AND clickpost_unified_status = 'Delivered')
    AND clickpost_unified_status = 'Delivered') AS ndr_res_cnt,
  COUNTIF(SAFE_CAST(out_for_delivery_attempts AS INT64) >= 1
    AND NOT (SAFE_CAST(out_for_delivery_attempts AS INT64) = 1 AND clickpost_unified_status = 'Delivered')) AS ndr_total_cnt,
  ROUND(COUNTIF(SAFE_CAST(out_for_delivery_attempts AS INT64) >= 1
    AND NOT (SAFE_CAST(out_for_delivery_attempts AS INT64) = 1 AND clickpost_unified_status = 'Delivered')
    AND clickpost_unified_status = 'Delivered')
    / NULLIF(COUNTIF(SAFE_CAST(out_for_delivery_attempts AS INT64) >= 1
    AND NOT (SAFE_CAST(out_for_delivery_attempts AS INT64) = 1 AND clickpost_unified_status = 'Delivered')), 0) * 100, 1) AS ndr_res_pct,
  ROUND(AVG(IF(DATE(created_at) IS NOT NULL AND DATE(order_date) IS NOT NULL
    AND DATE_DIFF(DATE(created_at), DATE(order_date), DAY) BETWEEN 0 AND 10,
    DATE_DIFF(DATE(created_at), DATE(order_date), DAY), NULL)), 1) AS avg_processing,
  ROUND(AVG(IF(SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(pickup_date, 1, 19)) IS NOT NULL
    AND SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(created_at, 1, 19)) IS NOT NULL
    AND TIMESTAMP_DIFF(SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(pickup_date, 1, 19)),
      SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(created_at, 1, 19)), MINUTE) BETWEEN 0 AND 14400,
    TIMESTAMP_DIFF(SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(pickup_date, 1, 19)),
      SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(created_at, 1, 19)), MINUTE) / 1440.0, NULL)), 1) AS avg_pickup_tat,
  ROUND(AVG(IF(SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(pickup_date, 1, 19)) IS NOT NULL
    AND SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(delivery_date, 1, 19)) IS NOT NULL
    AND clickpost_unified_status = 'Delivered'
    AND TIMESTAMP_DIFF(SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(delivery_date, 1, 19)),
      SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(pickup_date, 1, 19)), MINUTE) BETWEEN 0 AND 28800,
    TIMESTAMP_DIFF(SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(delivery_date, 1, 19)),
      SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(pickup_date, 1, 19)), MINUTE) / 1440.0, NULL)), 1) AS avg_intransit,
  ROUND(AVG(CASE WHEN clickpost_unified_status = 'Delivered' AND DATE(delivery_date) IS NOT NULL AND DATE(order_date) IS NOT NULL
    AND DATE_DIFF(DATE(delivery_date), DATE(order_date), DAY) BETWEEN 0 AND 20
    THEN DATE_DIFF(DATE(delivery_date), DATE(order_date), DAY) END), 1) AS avg_o2d
FROM `frido-429506.production.Clickpost_Shipment_Tracking_Report`
WHERE DATE(created_at) >= {W} AND DATE(created_at) < {END}
  AND shipment_type = 'Forward'
GROUP BY 1 ORDER BY shipments DESC
""")

print("Fetching city tier...")
tier_rows = q(f"""
WITH fwd AS (
  SELECT s.awb, s.clickpost_unified_status AS status,
    COALESCE(p.City_Tier, 'Unknown') AS city_tier,
    DATE(s.created_at) AS created_dt, DATE(s.pickup_date) AS pickup_dt,
    DATE(s.delivery_date) AS delivery_dt, DATE(s.order_date) AS order_dt,
    DATE(s.expected_delivery_date_by_courier_partner) AS edd_dt,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(s.created_at, 1, 19))   AS created_ts,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(s.pickup_date, 1, 19))  AS pickup_ts,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(s.delivery_date, 1, 19)) AS delivery_ts,
    SAFE_CAST(s.out_for_delivery_attempts AS INT64) AS ndr_attempts
  FROM `frido-429506.production.Clickpost_Shipment_Tracking_Report` s
  LEFT JOIN `frido-429506.production.pincode_city_master` p ON SAFE_CAST(s.drop_pincode AS INT64) = p.Pincode
  WHERE DATE(s.created_at) >= {W} AND DATE(s.created_at) < {END}
    AND s.shipment_type = 'Forward'
),
total AS (SELECT COUNT(DISTINCT awb) AS total_awb FROM fwd)
SELECT f.city_tier,
  COUNT(DISTINCT f.awb) AS shipments,
  ROUND(COUNT(DISTINCT f.awb) / MAX(t.total_awb) * 100, 1) AS share_pct,
  ROUND(COUNTIF(f.status = 'Delivered') / COUNT(DISTINCT f.awb) * 100, 1) AS del_pct,
  ROUND(COUNTIF(f.status LIKE 'RTO%') / COUNT(DISTINCT f.awb) * 100, 1) AS rto_pct,
  COUNTIF(f.status LIKE 'RTO%' AND f.ndr_attempts = 0) AS z_rto_cnt,
  ROUND(COUNTIF(f.status LIKE 'RTO%' AND f.ndr_attempts = 0) / COUNT(DISTINCT f.awb) * 100, 1) AS z_rto_pct,
  ROUND(COUNTIF(f.status = 'Delivered' AND f.delivery_dt > f.edd_dt) / NULLIF(COUNTIF(f.status = 'Delivered' AND f.edd_dt IS NOT NULL), 0) * 100, 1) AS edd_pct,
  COUNTIF(f.ndr_attempts >= 1 AND NOT (f.ndr_attempts = 1 AND f.status = 'Delivered')) AS ndr_cnt,
  ROUND(COUNTIF(f.ndr_attempts >= 1 AND NOT (f.ndr_attempts = 1 AND f.status = 'Delivered'))
    / COUNT(DISTINCT f.awb) * 100, 1) AS ndr_pct,
  COUNTIF(f.ndr_attempts >= 1 AND NOT (f.ndr_attempts = 1 AND f.status = 'Delivered') AND f.status = 'Delivered') AS ndr_res_cnt,
  COUNTIF(f.ndr_attempts >= 1 AND NOT (f.ndr_attempts = 1 AND f.status = 'Delivered')) AS ndr_total_cnt,
  ROUND(COUNTIF(f.ndr_attempts >= 1 AND NOT (f.ndr_attempts = 1 AND f.status = 'Delivered') AND f.status = 'Delivered')
    / NULLIF(COUNTIF(f.ndr_attempts >= 1 AND NOT (f.ndr_attempts = 1 AND f.status = 'Delivered')), 0) * 100, 1) AS ndr_res_pct,
  ROUND(AVG(IF(f.created_dt IS NOT NULL AND f.order_dt IS NOT NULL
    AND DATE_DIFF(f.created_dt, f.order_dt, DAY) BETWEEN 0 AND 10,
    DATE_DIFF(f.created_dt, f.order_dt, DAY), NULL)), 1) AS avg_processing,
  ROUND(AVG(IF(f.pickup_ts IS NOT NULL AND f.created_ts IS NOT NULL
    AND TIMESTAMP_DIFF(f.pickup_ts, f.created_ts, MINUTE) BETWEEN 0 AND 14400,
    TIMESTAMP_DIFF(f.pickup_ts, f.created_ts, MINUTE) / 1440.0, NULL)), 1) AS avg_pickup_tat,
  ROUND(AVG(IF(f.pickup_ts IS NOT NULL AND f.delivery_ts IS NOT NULL AND f.status = 'Delivered'
    AND TIMESTAMP_DIFF(f.delivery_ts, f.pickup_ts, MINUTE) BETWEEN 0 AND 28800,
    TIMESTAMP_DIFF(f.delivery_ts, f.pickup_ts, MINUTE) / 1440.0, NULL)), 1) AS avg_intransit,
  ROUND(AVG(CASE WHEN f.status = 'Delivered' AND f.delivery_dt IS NOT NULL AND f.order_dt IS NOT NULL
    AND DATE_DIFF(f.delivery_dt, f.order_dt, DAY) BETWEEN 0 AND 20
    THEN DATE_DIFF(f.delivery_dt, f.order_dt, DAY) END), 1) AS avg_o2d
FROM fwd f CROSS JOIN total t WHERE f.city_tier != 'Unknown'
GROUP BY 1
ORDER BY CASE f.city_tier WHEN 'Tier I' THEN 1 WHEN 'Tier II' THEN 2 WHEN 'Tier III' THEN 3 END
""")

print("Fetching zone breakdown...")
zone_rows = q(f"""
WITH fwd AS (
  SELECT s.awb, s.clickpost_unified_status AS status,
    COALESCE(NULLIF(TRIM(s.zone_by_frido), ''), 'Unknown') AS zone,
    DATE(s.created_at) AS created_dt, DATE(s.pickup_date) AS pickup_dt,
    DATE(s.delivery_date) AS delivery_dt, DATE(s.order_date) AS order_dt,
    DATE(s.expected_delivery_date_by_courier_partner) AS edd_dt,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(s.created_at, 1, 19))    AS created_ts,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(s.pickup_date, 1, 19))   AS pickup_ts,
    SAFE.PARSE_TIMESTAMP('%Y-%m-%d %H:%M:%S', SUBSTR(s.delivery_date, 1, 19)) AS delivery_ts,
    SAFE_CAST(s.out_for_delivery_attempts AS INT64) AS ndr_attempts
  FROM `frido-429506.production.Clickpost_Shipment_Tracking_Report` s
  WHERE DATE(s.created_at) >= {W} AND DATE(s.created_at) < {END}
    AND s.shipment_type = 'Forward'
),
total AS (SELECT COUNT(DISTINCT awb) AS total_awb FROM fwd)
SELECT f.zone,
  COUNT(DISTINCT f.awb) AS shipments,
  ROUND(COUNT(DISTINCT f.awb) / MAX(t.total_awb) * 100, 1) AS share_pct,
  ROUND(COUNTIF(f.status = 'Delivered') / COUNT(DISTINCT f.awb) * 100, 1) AS del_pct,
  ROUND(COUNTIF(f.status LIKE 'RTO%') / COUNT(DISTINCT f.awb) * 100, 1) AS rto_pct,
  COUNTIF(f.ndr_attempts >= 1 AND NOT (f.ndr_attempts = 1 AND f.status = 'Delivered')) AS ndr_cnt,
  ROUND(COUNTIF(f.ndr_attempts >= 1 AND NOT (f.ndr_attempts = 1 AND f.status = 'Delivered'))
    / COUNT(DISTINCT f.awb) * 100, 1) AS ndr_pct,
  COUNTIF(f.ndr_attempts >= 1 AND NOT (f.ndr_attempts = 1 AND f.status = 'Delivered') AND f.status = 'Delivered') AS ndr_res_cnt,
  COUNTIF(f.ndr_attempts >= 1 AND NOT (f.ndr_attempts = 1 AND f.status = 'Delivered')) AS ndr_total_cnt,
  ROUND(COUNTIF(f.ndr_attempts >= 1 AND NOT (f.ndr_attempts = 1 AND f.status = 'Delivered') AND f.status = 'Delivered')
    / NULLIF(COUNTIF(f.ndr_attempts >= 1 AND NOT (f.ndr_attempts = 1 AND f.status = 'Delivered')), 0) * 100, 1) AS ndr_res_pct,
  ROUND(COUNTIF(f.status = 'Delivered' AND f.delivery_dt > f.edd_dt) / NULLIF(COUNTIF(f.status = 'Delivered' AND f.edd_dt IS NOT NULL), 0) * 100, 1) AS edd_pct,
  ROUND(AVG(IF(f.created_dt IS NOT NULL AND f.order_dt IS NOT NULL
    AND DATE_DIFF(f.created_dt, f.order_dt, DAY) BETWEEN 0 AND 10,
    DATE_DIFF(f.created_dt, f.order_dt, DAY), NULL)), 1) AS avg_processing,
  ROUND(AVG(IF(f.pickup_ts IS NOT NULL AND f.created_ts IS NOT NULL
    AND TIMESTAMP_DIFF(f.pickup_ts, f.created_ts, MINUTE) BETWEEN 0 AND 14400,
    TIMESTAMP_DIFF(f.pickup_ts, f.created_ts, MINUTE) / 1440.0, NULL)), 1) AS avg_pickup_tat,
  ROUND(AVG(IF(f.pickup_ts IS NOT NULL AND f.delivery_ts IS NOT NULL AND f.status = 'Delivered'
    AND TIMESTAMP_DIFF(f.delivery_ts, f.pickup_ts, MINUTE) BETWEEN 0 AND 28800,
    TIMESTAMP_DIFF(f.delivery_ts, f.pickup_ts, MINUTE) / 1440.0, NULL)), 1) AS avg_intransit,
  ROUND(AVG(CASE WHEN f.status = 'Delivered' AND f.delivery_dt IS NOT NULL AND f.order_dt IS NOT NULL
    AND DATE_DIFF(f.delivery_dt, f.order_dt, DAY) BETWEEN 0 AND 20
    THEN DATE_DIFF(f.delivery_dt, f.order_dt, DAY) END), 1) AS avg_o2d
FROM fwd f CROSS JOIN total t WHERE f.zone != 'Unknown'
GROUP BY 1
ORDER BY f.zone
""")

print("Fetching transit TAT...")
tat_rows = q(f"""
WITH delivered AS (
  SELECT
    CASE
      WHEN LOWER(courier_partner) LIKE '%bluedart%' THEN 'Bluedart'
      WHEN LOWER(courier_partner) LIKE '%ekart%' THEN 'Ekart'
      WHEN LOWER(courier_partner) LIKE '%elastic%' THEN 'ElasticRun'
      WHEN LOWER(courier_partner) LIKE '%delhivery%' AND LEFT(awb, 4) = '5448' THEN 'Delhivery NDD'
      WHEN LOWER(courier_partner) LIKE '%delhivery%' THEN 'Delhivery'
      WHEN LOWER(courier_partner) LIKE '%safexpress%' THEN 'Safexpress'
      WHEN LOWER(courier_partner) LIKE '%shadowfax%' THEN 'Shadowfax'
      WHEN LOWER(courier_partner) LIKE '%shiprocket%' THEN 'Shiprocket'
      WHEN LOWER(courier_partner) LIKE '%sky air%' OR LOWER(courier_partner) LIKE '%skye air%' THEN 'Skye Air'
      WHEN LOWER(courier_partner) LIKE '%swift%' THEN 'Swift'
      WHEN LOWER(courier_partner) LIKE '%urbane bolt%' OR LOWER(courier_partner) LIKE '%urbanbolt%' THEN 'Urbane Bolt'
      WHEN LOWER(courier_partner) LIKE '%wareiq%' THEN 'WareIQ'
      WHEN LOWER(courier_partner) LIKE '%zippee%' THEN 'Zippee'
      ELSE courier_partner
    END AS courier_group,
    awb,
    DATE_DIFF(DATE(delivery_date), DATE(pickup_date), DAY) AS transit_days
  FROM `frido-429506.production.Clickpost_Shipment_Tracking_Report`
  WHERE DATE(created_at) >= {W} AND DATE(created_at) < {END}
    AND shipment_type = 'Forward' AND clickpost_unified_status = 'Delivered'
    AND pickup_date IS NOT NULL AND pickup_date != ''
    AND delivery_date IS NOT NULL AND delivery_date != ''
)
SELECT courier_group AS courier_partner, COUNT(awb) AS delivered,
  COUNTIF(transit_days <= 2) AS lte2d, ROUND(COUNTIF(transit_days <= 2)/COUNT(awb)*100,1) AS lte2d_pct,
  COUNTIF(transit_days BETWEEN 3 AND 4) AS d3_4, ROUND(COUNTIF(transit_days BETWEEN 3 AND 4)/COUNT(awb)*100,1) AS d3_4_pct,
  COUNTIF(transit_days = 5) AS d5, ROUND(COUNTIF(transit_days = 5)/COUNT(awb)*100,1) AS d5_pct,
  COUNTIF(transit_days > 5) AS d5plus, ROUND(COUNTIF(transit_days > 5)/COUNT(awb)*100,1) AS d5plus_pct
FROM delivered GROUP BY 1 ORDER BY delivered DESC
""")

print("Fetching RVP section 9...")
rvp_sec = q(f"""
WITH rvp AS (
  SELECT awb, clickpost_unified_status AS status,
    DATE(created_at) AS created_dt, DATE(pickup_date) AS pickup_dt, DATE(delivery_date) AS delivery_dt
  FROM `frido-429506.production.Clickpost_Shipment_Tracking_Report`
  WHERE DATE(created_at) >= {W} AND DATE(created_at) < {END}
    AND shipment_type = 'Reverse' AND Return_Type IN ('Return', 'Exchange')
)
SELECT
  COUNT(awb) AS rvp_created,
  COUNTIF(status IN ('PickedUp','InTransit','OutForDelivery','Delivered')) AS rvp_picked_up,
  COUNTIF(status = 'Delivered') AS rvp_delivered,
  COUNTIF(pickup_dt IS NOT NULL AND DATE_DIFF(pickup_dt, created_dt, DAY) <= 2) AS rvp_pickup_lte2d,
  COUNTIF(status = 'Delivered' AND pickup_dt IS NOT NULL AND DATE_DIFF(delivery_dt, pickup_dt, DAY) <= 5) AS rvp_wh_lte5d,
  ROUND(AVG(CASE WHEN pickup_dt IS NOT NULL THEN DATE_DIFF(pickup_dt, created_dt, DAY) END), 1) AS avg_rvp_pickup,
  ROUND(AVG(CASE WHEN status = 'Delivered' AND pickup_dt IS NOT NULL THEN DATE_DIFF(delivery_dt, pickup_dt, DAY) END), 1) AS avg_rvp_wh,
  ROUND(AVG(CASE WHEN status = 'Delivered' THEN DATE_DIFF(delivery_dt, created_dt, DAY) END), 1) AS avg_rvp_total
FROM rvp
""")[0]

print("All data fetched. Building HTML...")

# ── HTML helpers ──────────────────────────────────────────────────────────────
def v(val, red_if=None, green_if=None):
    """Format value with optional color class."""
    if val is None: return '<span class="kv">—</span>'
    is_red = red_if and red_if(val)
    cls = ' red' if is_red else ''
    style = ' style="color:#c00000;font-weight:bold;"' if is_red else ''
    return f'<span class="kv{cls}"{style}>{val}</span>'

def td(val, red_if=None, suffix=''):
    if val is None: return '<td>—</td>'
    s = f"{val}{suffix}"
    if red_if and red_if(val):
        return f'<td style="color:#000000;font-weight:bold;">{s}</td>'
    return f'<td>{s}</td>'

def td_name(val):
    return f'<td class="name">{val}</td>'

TS = 'style="background:#1F3864;color:#fff;font-weight:bold;border-color:#1F3864;padding:4px 7px;border:1px solid #1F3864;text-align:center;white-space:nowrap;"'
TSL = 'style="background:#1F3864;color:#fff;font-weight:bold;border-color:#1F3864;padding:4px 7px;border:1px solid #1F3864;text-align:left;white-space:nowrap;"'

def tr_total(*cells):
    inner = ''.join(f'<td {TS}>{c}</td>' for c in cells)
    return f'<tr>{inner}</tr>'

# ── Build HTML ────────────────────────────────────────────────────────────────
def build_monthly_rows():
    rows = ''
    for r in monthly:
        rows += f"""<tr>
          {td_name(r.month_label)}
          <td>{r.shipments:,}</td>
          {td(r.del_pct, lambda x: x < 75, '%')}
          {td(r.rto_pct, lambda x: x > 18, '%')}
          {td(r.fasr_pct, lambda x: x < 70, '%')}
          {td(r.edd_pct, lambda x: x > 30, '%')}
          {td(r.correct_alloc_pct, lambda x: x < 90, '%')}
          {td(r.s2d_lte3_pct, None, '%')}
          {td(r.o2d_lte5_pct, None, '%')}
          {td(r.avg_processing, None, 'd')}
          {td(r.avg_pickup_tat, None, 'd')}
          {td(r.avg_intransit, lambda x: x > 3, 'd')}
          {td(r.avg_o2d, lambda x: x > 5, 'd')}
        </tr>"""
    # totals row - averages
    ships_total = sum(r.shipments for r in monthly)
    n = len(monthly)
    rows += f"""<tr>
      <td {TSL}>&nbsp;</td>
      <td {TS}>{ships_total:,}</td>
      <td {TS}>{round(sum(r.del_pct or 0 for r in monthly)/n,1)}%</td>
      <td {TS}>{round(sum(r.rto_pct or 0 for r in monthly)/n,1)}%</td>
      <td {TS}>{round(sum(r.fasr_pct or 0 for r in monthly)/n,1)}%</td>
      <td {TS}>{round(sum(r.edd_pct or 0 for r in monthly)/n,1)}%</td>
      <td {TS}>{round(sum(r.correct_alloc_pct or 0 for r in monthly)/n,1)}%</td>
      <td {TS}>{round(sum(r.s2d_lte3_pct or 0 for r in monthly)/n,1)}%</td>
      <td {TS}>{round(sum(r.o2d_lte5_pct or 0 for r in monthly)/n,1)}%</td>
      <td {TS}>{round(sum(r.avg_processing or 0 for r in monthly)/n,1)}d</td>
      <td {TS}>{round(sum(r.avg_pickup_tat or 0 for r in monthly)/n,1)}d</td>
      <td {TS}>{round(sum(r.avg_intransit or 0 for r in monthly)/n,1)}d</td>
      <td {TS}>{round(sum(r.avg_o2d or 0 for r in monthly)/n,1)}d</td>
    </tr>"""
    return rows

def build_courier_rows():
    rows = ''
    total_ships = 0
    for r in couriers:
        total_ships += r.shipments
        rows += f"""<tr>
          {td_name(r.courier_partner)}
          <td>{r.shipments:,}</td>
          {td(r.del_pct, lambda x: x < 75, '%')}
          {td(r.rto_pct, lambda x: x > 18, '%')}
          {td(r.fasr_pct, lambda x: x < 70, '%')}
          {td(r.edd_pct, lambda x: x > 30, '%')}
          {td(r.ndr_pct, lambda x: x > 15, '%')}
          {td(r.ndr_res_pct, lambda x: x < 60, '%')}
          {td(r.avg_pickup_tat, None, 'd')}
          {td(r.avg_intransit, lambda x: x > 3, 'd')}
          {td(r.avg_o2d, lambda x: x > 5, 'd')}
        </tr>"""
    total_ndr = sum(r.ndr_count for r in ndr_rows)
    total_ndr_res = sum(r.ndr_resolved for r in ndr_rows)
    total_ndr_pct = round(total_ndr / total_ships * 100, 1) if total_ships else 0
    total_ndr_res_pct = round(total_ndr_res / total_ndr * 100, 1) if total_ndr else 0
    rows += f"""<tr>
      <td {TSL}>Total / Avg</td>
      <td {TS}>{total_ships:,}</td>
      <td {TS}>{kpi.del_pct}%</td><td {TS}>{kpi.rto_pct}%</td>
      <td {TS}>{kpi.fasr_pct}%</td><td {TS}>{kpi.edd_pct}%</td>
      <td {TS}>{total_ndr_pct}%</td><td {TS}>{total_ndr_res_pct}%</td>
      <td {TS}>{kpi.avg_pickup_tat}d</td><td {TS}>{kpi.avg_intransit}d</td><td {TS}>{kpi.avg_o2d}d</td>
    </tr>"""
    return rows

def build_facility_rows():
    rows = ''
    for r in facilities:
        rows += f"""<tr>
          {td_name(r.facility_wh)}
          <td>{r.alloc_pct}%</td>
          {td(r.correct_alloc_pct, lambda x: x < 90, '%')}
          {td(r.processed_24hr_pct, lambda x: x < 80, '%')}
          {td(r.avg_processing, lambda x: x > 1, 'd')}
          {td(r.pickup_24hr_pct, lambda x: x < 75, '%')}
          {td(r.avg_pickup_tat, lambda x: x > 1, 'd')}
          {td(r.avg_intransit, lambda x: x > 3, 'd')}
          {td(r.avg_o2d, lambda x: x > 5, 'd')}
        </tr>"""
    total_ships_fac = sum(r.shipments for r in facilities)
    total_proc24    = sum(r.processed_24hr_cnt for r in facilities)
    total_pickup24  = sum(r.pickup_24hr_cnt for r in facilities)
    # overall correct alloc % comes from wh_fit_kpi (demand-based overall = same denominator)
    tot_correct_pct  = wh_fit_kpi.wh_fit_pct or 0
    tot_proc24_pct   = round(total_proc24   / total_ships_fac * 100, 1) if total_ships_fac else 0
    tot_pickup24_pct = round(total_pickup24 / total_ships_fac * 100, 1) if total_ships_fac else 0
    rows += f"""<tr>
      <td {TSL}>Total / Avg</td>
      <td {TS}>100%</td>
      <td {TS}>{tot_correct_pct}%</td>
      <td {TS}>{tot_proc24_pct}%</td>
      <td {TS}>{kpi.avg_processing}d</td>
      <td {TS}>{tot_pickup24_pct}%</td>
      <td {TS}>{kpi.avg_pickup_tat}d</td>
      <td {TS}>{kpi.avg_intransit}d</td><td {TS}>{kpi.avg_o2d}d</td>
    </tr>"""
    return rows

def build_ndr_rows():
    rows = ''
    for r in ndr_rows:
        rows += f"""<tr>
          {td_name(r.courier_partner)}
          <td>{r.shipments:,}</td>
          <td>{r.ndr_count:,}</td>
          {td(r.ndr_pct, lambda x: x > 15, '%')}
          <td>{r.ndr_resolved:,}</td>
          {td(r.ndr_resolved_pct, lambda x: x < 60, '%')}
          {td(r.became_rto_pct, lambda x: x > 25, '%')}
          <td>{r.avg_attempts}</td>
          {td(r.avg_intransit, lambda x: x > 3, 'd')}
          {td(r.avg_o2d, lambda x: x > 5, 'd')}
        </tr>"""
    total_ships    = sum(r.shipments for r in ndr_rows)
    total_ndr      = sum(r.ndr_count for r in ndr_rows)
    total_res      = sum(r.ndr_resolved for r in ndr_rows)
    total_rto_ndr  = sum(round(r.became_rto_pct * r.ndr_count / 100) for r in ndr_rows if r.became_rto_pct and r.ndr_count)
    total_attempts = sum((r.avg_attempts or 0) * r.ndr_count for r in ndr_rows if r.avg_attempts and r.ndr_count)
    avg_attempts   = round(total_attempts / total_ndr, 1) if total_ndr else 0
    became_rto_pct = round(total_rto_ndr / total_ndr * 100, 1) if total_ndr else 0
    rows += f"""<tr>
      <td {TSL}>Total / Avg</td>
      <td {TS}>{total_ships:,}</td><td {TS}>{total_ndr:,}</td>
      <td {TS}>{round(total_ndr/total_ships*100,1)}%</td>
      <td {TS}>{total_res:,}</td>
      <td {TS}>{round(total_res/total_ndr*100,1)}%</td>
      <td {TS}>{became_rto_pct}%</td><td {TS}>{avg_attempts}</td>
      <td {TS}>{kpi.avg_intransit}d</td><td {TS}>{kpi.avg_o2d}d</td>
    </tr>"""
    return rows

def build_cod_rows():
    rows = ''
    for r in cod_rows:
        rows += f"""<tr>
          {td_name(r.payment_mode)}
          <td>{r.shipments:,}</td>
          <td>{r.share_pct}%</td>
          {td(r.del_pct, lambda x: x < 75, '%')}
          {td(r.rto_pct, lambda x: x > 18, '%')}
          {td(r.edd_pct, lambda x: x > 30, '%')}
          {td(r.ndr_pct, lambda x: x > 15, '%')}
          {td(r.ndr_res_pct, lambda x: x < 60, '%')}
          {td(r.avg_processing, None, 'd')}
          {td(r.avg_pickup_tat, None, 'd')}
          {td(r.avg_intransit, lambda x: x > 3, 'd')}
          {td(r.avg_o2d, lambda x: x > 5, 'd')}
        </tr>"""
    total_ships    = sum(r.shipments for r in cod_rows)
    total_ndr_cod  = sum(r.ndr_cnt for r in cod_rows)
    total_ndr_res  = sum(r.ndr_res_cnt for r in cod_rows)
    total_ndr_tot  = sum(r.ndr_total_cnt for r in cod_rows)
    ndr_pct_tot    = round(total_ndr_cod  / total_ships * 100, 1) if total_ships else 0
    ndr_res_pct_tot= round(total_ndr_res  / total_ndr_tot * 100, 1) if total_ndr_tot else 0
    rows += f"""<tr>
      <td {TSL}>Total / Avg</td>
      <td {TS}>{total_ships:,}</td><td {TS}>100%</td>
      <td {TS}>{kpi.del_pct}%</td><td {TS}>{kpi.rto_pct}%</td>
      <td {TS}>{kpi.edd_pct}%</td>
      <td {TS}>{ndr_pct_tot}%</td><td {TS}>{ndr_res_pct_tot}%</td>
      <td {TS}>{kpi.avg_processing}d</td><td {TS}>{kpi.avg_pickup_tat}d</td>
      <td {TS}>{kpi.avg_intransit}d</td><td {TS}>{kpi.avg_o2d}d</td>
    </tr>"""
    return rows

def build_tier_rows():
    rows = ''
    for r in tier_rows:
        rows += f"""<tr>
          {td_name(r.city_tier)}
          <td>{r.shipments:,}</td>
          <td>{r.share_pct}%</td>
          {td(r.del_pct, lambda x: x < 75, '%')}
          {td(r.rto_pct, lambda x: x > 18, '%')}
          {td(r.edd_pct, lambda x: x > 30, '%')}
          {td(r.ndr_pct, lambda x: x > 15, '%')}
          {td(r.ndr_res_pct, lambda x: x < 60, '%')}
          {td(r.avg_processing, None, 'd')}
          {td(r.avg_pickup_tat, None, 'd')}
          {td(r.avg_intransit, lambda x: x > 3, 'd')}
          {td(r.avg_o2d, lambda x: x > 5, 'd')}
        </tr>"""
    total_ships     = sum(r.shipments for r in tier_rows)
    total_ndr_t     = sum(r.ndr_cnt for r in tier_rows)
    total_ndr_res_t = sum(r.ndr_res_cnt for r in tier_rows)
    total_ndr_tot_t = sum(r.ndr_total_cnt for r in tier_rows)
    ndr_pct_t      = round(total_ndr_t      / total_ships * 100, 1) if total_ships else 0
    ndr_res_pct_t  = round(total_ndr_res_t  / total_ndr_tot_t * 100, 1) if total_ndr_tot_t else 0
    rows += f"""<tr>
      <td {TSL}>Total / Avg</td>
      <td {TS}>{total_ships:,}</td><td {TS}>100%</td>
      <td {TS}>{kpi.del_pct}%</td><td {TS}>{kpi.rto_pct}%</td>
      <td {TS}>{kpi.edd_pct}%</td>
      <td {TS}>{ndr_pct_t}%</td><td {TS}>{ndr_res_pct_t}%</td>
      <td {TS}>{kpi.avg_processing}d</td><td {TS}>{kpi.avg_pickup_tat}d</td>
      <td {TS}>{kpi.avg_intransit}d</td><td {TS}>{kpi.avg_o2d}d</td>
    </tr>"""
    return rows

def build_zone_rows():
    rows = ''
    for r in zone_rows:
        rows += f"""<tr>
          {td_name('Zone ' + r.zone)}
          <td>{r.shipments:,}</td>
          <td>{r.share_pct}%</td>
          {td(r.del_pct, lambda x: x < 75, '%')}
          {td(r.rto_pct, lambda x: x > 18, '%')}
          {td(r.edd_pct, lambda x: x > 30, '%')}
          {td(r.ndr_pct, lambda x: x > 15, '%')}
          {td(r.ndr_res_pct, lambda x: x < 60, '%')}
          {td(r.avg_processing, None, 'd')}
          {td(r.avg_pickup_tat, None, 'd')}
          {td(r.avg_intransit, lambda x: x > 3, 'd')}
          {td(r.avg_o2d, lambda x: x > 5, 'd')}
        </tr>"""
    total_ships     = sum(r.shipments for r in zone_rows)
    total_ndr_t     = sum(r.ndr_cnt for r in zone_rows)
    total_ndr_res_t = sum(r.ndr_res_cnt for r in zone_rows)
    total_ndr_tot_t = sum(r.ndr_total_cnt for r in zone_rows)
    ndr_pct_t      = round(total_ndr_t / total_ships * 100, 1) if total_ships else 0
    ndr_res_pct_t  = round(total_ndr_res_t / total_ndr_tot_t * 100, 1) if total_ndr_tot_t else 0
    rows += f"""<tr>
      <td {TSL}>Total / Avg</td>
      <td {TS}>{total_ships:,}</td><td {TS}>100%</td>
      <td {TS}>{kpi.del_pct}%</td><td {TS}>{kpi.rto_pct}%</td>
      <td {TS}>{kpi.edd_pct}%</td>
      <td {TS}>{ndr_pct_t}%</td><td {TS}>{ndr_res_pct_t}%</td>
      <td {TS}>{kpi.avg_processing}d</td><td {TS}>{kpi.avg_pickup_tat}d</td>
      <td {TS}>{kpi.avg_intransit}d</td><td {TS}>{kpi.avg_o2d}d</td>
    </tr>"""
    return rows

def build_tat_rows():
    rows = ''
    for r in tat_rows:
        rows += f"""<tr>
          {td_name(r.courier_partner)}
          <td>{r.delivered:,}</td>
          <td>{r.lte2d:,}</td><td>{r.lte2d_pct}%</td>
          <td>{r.d3_4:,}</td><td>{r.d3_4_pct}%</td>
          <td>{r.d5:,}</td><td>{r.d5_pct}%</td>
          {td(r.d5plus, None)}{td(r.d5plus_pct, lambda x: x > 8, '%')}
        </tr>"""
    total_del   = sum(r.delivered for r in tat_rows)
    total_lte2  = sum(r.lte2d for r in tat_rows)
    total_34    = sum(r.d3_4 for r in tat_rows)
    total_5     = sum(r.d5 for r in tat_rows)
    total_5p    = sum(r.d5plus for r in tat_rows)
    rows += f"""<tr>
      <td {TSL}>Total / Avg</td>
      <td {TS}>{total_del:,}</td>
      <td {TS}>{total_lte2:,}</td><td {TS}>{round(total_lte2/total_del*100,1)}%</td>
      <td {TS}>{total_34:,}</td><td {TS}>{round(total_34/total_del*100,1)}%</td>
      <td {TS}>{total_5:,}</td><td {TS}>{round(total_5/total_del*100,1)}%</td>
      <td {TS}>{total_5p:,}</td><td {TS}>{round(total_5p/total_del*100,1)}%</td>
    </tr>"""
    return rows

r = rvp_sec
rvp_pickup_pct   = round(r.rvp_picked_up / r.rvp_created * 100, 1) if r.rvp_created else 0
rvp_del_pct      = round(r.rvp_delivered / r.rvp_created * 100, 1) if r.rvp_created else 0
rvp_lte2d_pct    = round(r.rvp_pickup_lte2d / r.rvp_created * 100, 1) if r.rvp_created else 0
rvp_wh5d_pct     = round(r.rvp_wh_lte5d / r.rvp_picked_up * 100, 1) if r.rvp_picked_up else 0

html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Calibri, Arial, sans-serif; font-size: 13px; color: #222; background: #f4f6f9; }}
  .wrapper {{ width: 100%; max-width: 680px; margin: 0 auto; background: #fff; }}
  .header {{ background: #1F3864; color: #fff; padding: 10px 20px; }}
  .header h1 {{ font-size: 17px; font-weight: bold; }}
  .header .sub {{ font-size: 11px; color: #aac4e0; margin-top: 5px; }}
  .section {{ padding: 14px 12px; border-bottom: 1px solid #e4e8ef; }}
  .section-title {{ font-size: 11px; font-weight: bold; color: #1F3864; border-left: 3px solid #2E75B6; padding-left: 8px; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 0.5px; }}
  .kpi-outer {{ width: 100%; border-collapse: separate; border-spacing: 5px; margin-bottom: 6px; table-layout: fixed; }}
  .kpi-cell {{ border: 1px solid #dde3ee; border-radius: 4px; padding: 8px 8px; background: #fafbfd; text-align: left; vertical-align: top; width: 25%; overflow: hidden; }}
  .kpi-cell .kl {{ font-size: 9px; color: #555; font-weight: 700; text-transform: uppercase; letter-spacing: 0.3px; line-height: 1.3; display: block; margin-bottom: 3px; }}
  .kpi-cell .kv {{ font-size: 18px; font-weight: bold; color: #1F3864; display: block; line-height: 1.2; }}
  .kpi-cell .kv.red {{ color: #c00000; font-weight: bold; }}
  .kpi-cell .ksub {{ font-size: 9px; color: #999; display: block; margin-top: 2px; }}
  .tbl-wrap {{ width: 100%; overflow-x: auto; -webkit-overflow-scrolling: touch; display: block; }}
  .dtbl {{ width: 100%; border-collapse: collapse; font-size: 10px; white-space: nowrap; }}
  .dtbl th {{ background: #1F3864; color: #fff; padding: 5px 7px; text-align: center; font-size: 9px; font-weight: bold; white-space: nowrap; }}
  .dtbl th.left {{ text-align: left; }}
  .dtbl td {{ padding: 4px 7px; border: 1px solid #e0e5ef; text-align: center; color: #222; background: #fff; white-space: nowrap; }}
  .dtbl td.name {{ text-align: left; font-weight: bold; color: #1F3864; }}
  .dtbl tr:nth-child(even) td {{ background: #f7f9fc; }}
  .dtbl tr.total-row td {{ background: #1F3864 !important; color: #fff !important; font-weight: bold; border-color: #1F3864; }}
  .dtbl tr.total-row td.name {{ color: #fff !important; }}
  .red-text {{ color: #c00000 !important; font-weight: bold; }}
  .footer {{ background: #1F3864; color: #aac4e0; font-size: 10px; padding: 10px 16px; text-align: center; }}
  .note {{ font-size: 10px; color: #888; margin-top: 6px; font-style: italic; line-height: 1.5; }}
  @media (max-width: 768px) {{
    .wrapper {{ width: 100%; max-width: 100%; padding: 0; }}
    .section {{ padding: 10px 0px; }}
    .section-title {{ margin-left: 4px; }}
    .note {{ margin-left: 4px; margin-right: 4px; font-size: 9px; }}
    .header {{ padding: 12px 8px; }}
    .footer {{ padding: 10px 8px; }}
    .kpi-outer {{ border-spacing: 3px; }}
    .kpi-cell {{ padding: 6px 4px; }}
    .kpi-cell .kv {{ font-size: 15px; }}
    .dtbl {{ font-size: 8px; }}
    .dtbl th {{ font-size: 7px; padding: 3px 2px; word-break: break-word; line-height: 1.2; }}
    .dtbl td {{ font-size: 8px; padding: 3px 2px; }}
    .dtbl td.name {{ white-space: normal; word-break: break-word; }}
  }}
</style>
</head>
<body>
<div class="wrapper">

  <!-- HEADER -->
  <div class="header">
    <h1>Frido Logistics &amp; Operations Report</h1>
    <div class="sub">Period: {period_label} &nbsp;|&nbsp; Data as of: {today.strftime('%d %b %Y')}</div>
  </div>

  <!-- SECTION 1: KPI CARDS -->
  <div class="section">
    <div class="section-title">Overall KPIs</div>
    <table class="kpi-outer" role="presentation">
      <tr>
        <td class="kpi-cell">
          <span class="kl">Shipments</span>
          <span class="kv">{kpi.total_shipments:,}</span>
          <span class="ksub">total dispatched</span>
        </td>
        <td class="kpi-cell">
          <span class="kl">Del %</span>
          <span class="kv{'  red' if (kpi.del_pct or 0) < 75 else ''}">{kpi.del_pct}%</span>
          <span class="ksub">{kpi.delivered_cnt:,} delivered</span>
        </td>
        <td class="kpi-cell">
          <span class="kl">RTO %</span>
          <span class="kv{' red' if (kpi.rto_pct or 0) > 7 else ''}">{kpi.rto_pct}%</span>
          <span class="ksub">returned to origin</span>
        </td>
        <td class="kpi-cell">
          <span class="kl">FASR %</span>
          <span class="kv{' red' if (kpi.fasr_pct or 0) < 70 else ''}">{kpi.fasr_pct}%</span>
          <span class="ksub">1st attempt success</span>
        </td>
      </tr>
    </table>
    <table class="kpi-outer" role="presentation" style="margin-top:0;">
      <tr>
        <td class="kpi-cell">
          <span class="kl">RASR %</span>
          <span class="kv{' red' if (kpi.rasr_pct or 0) < 70 else ''}">{kpi.rasr_pct}%</span>
          <span class="ksub">reattempt success</span>
        </td>
        <td class="kpi-cell">
          <span class="kl">EDD Breach %</span>
          <span class="kv{' red' if (kpi.edd_pct or 0) > 30 else ''}">{kpi.edd_pct}%</span>
          <span class="ksub">delivered after EDD</span>
        </td>
        <td class="kpi-cell">
          <span class="kl">S2D ≤3d %</span>
          <span class="kv">{kpi.s2d_lte3_pct}%</span>
          <span class="ksub">ship to deliver ≤3d</span>
        </td>
        <td class="kpi-cell">
          <span class="kl">O2D ≤5d %</span>
          <span class="kv">{kpi.o2d_lte5_pct}%</span>
          <span class="ksub">order to deliver ≤5d</span>
        </td>
      </tr>
    </table>
    <table class="kpi-outer" role="presentation" style="margin-top:0;">
      <tr>
        <td class="kpi-cell">
          <span class="kl">WH Fit %</span>
          <span class="kv{' red' if (wh_fit_kpi.wh_fit_pct or 0) < 90 else ''}">{wh_fit_kpi.wh_fit_pct}%</span>
          <span class="ksub">correct WH allocation</span>
        </td>
        <td class="kpi-cell">
          <span class="kl">Avg Processing</span>
          <span class="kv">{kpi.avg_processing}d</span>
          <span class="ksub">order → AWB</span>
        </td>
        <td class="kpi-cell">
          <span class="kl">Avg Pickup TAT</span>
          <span class="kv">{kpi.avg_pickup_tat}d</span>
          <span class="ksub">AWB → pickup</span>
        </td>
        <td class="kpi-cell">
          <span class="kl">Pickup → Del.</span>
          <span class="kv{' red' if (kpi.avg_intransit or 0) > 3 else ''}">{kpi.avg_intransit}d</span>
          <span class="ksub">pickup → del.</span>
        </td>
      </tr>
    </table>
    <table class="kpi-outer" role="presentation" style="margin-top:0;">
      <tr>
        <td class="kpi-cell">
          <span class="kl">Avg Fulfillment</span>
          <span class="kv{' red' if (kpi.avg_o2d or 0) > 5 else ''}">{kpi.avg_o2d}d</span>
          <span class="ksub">order → delivery</span>
        </td>
        <td class="kpi-cell">
          <span class="kl">RTO Del TAT</span>
          <span class="kv">{'—' if kpi.avg_rto_delivered is None else str(kpi.avg_rto_delivered)+'d'}</span>
          <span class="ksub">RTO → DEL</span>
        </td>
        <td class="kpi-cell">
          <span class="kl">Avg RVP</span>
          <span class="kv">{rvp_kpi.avg_rvp_days}d</span>
          <span class="ksub">creation → pickup</span>
        </td>
        <td class="kpi-cell">
          <span class="kl">Avg RVP → Del.</span>
          <span class="kv">{rvp_kpi.avg_rvp_to_delivery_days}d</span>
          <span class="ksub">pickup → del.</span>
        </td>
      </tr>
    </table>
  </div>

  <!-- SECTION 2: MONTHLY TREND -->
  <div class="section">
    <div class="section-title">Monthly Trend (Last 6 Months)</div>
    <div class="tbl-wrap">
    <table class="dtbl">
      <colgroup>
        <col style="width:14%"><col style="width:7%"><col style="width:6%"><col style="width:6%">
        <col style="width:7%"><col style="width:6%"><col style="width:7%">
        <col style="width:7%"><col style="width:7%"><col style="width:8%">
        <col style="width:8%"><col style="width:8%"><col style="width:9%">
      </colgroup>
      <tr>
        <th class="left">Month</th>
        <th>Ships</th><th>Del %</th><th>RTO %</th>
        <th>FASR %</th><th>EDD Breach%</th><th>WH Fit %</th>
        <th>S2D ≤3d</th><th>O2D ≤5d</th><th>Avg Proc</th>
        <th>Avg Pickup</th><th>Avg Intransit</th><th>Avg O2D</th>
      </tr>
      {build_monthly_rows()}
    </table>
    </div>
    <p class="note">Red = breached. Del% ≥75% | RTO% ≤18% | FASR% ≥70% | EDD Breach% ≤30% | WH Fit% ≥90% | Avg Intransit ≤3d | Avg O2D ≤5d</p>
  </div>

  <!-- SECTION 3: COURIER WISE -->
  <div class="section">
    <div class="section-title">Performance by Courier</div>
    <div class="tbl-wrap">
    <table class="dtbl">
      <colgroup>
        <col style="width:16%"><col style="width:7%"><col style="width:6%"><col style="width:6%">
        <col style="width:7%"><col style="width:6%"><col style="width:7%"><col style="width:7%">
        <col style="width:8%"><col style="width:8%"><col style="width:8%">
      </colgroup>
      <tr>
        <th class="left">Courier</th>
        <th>Ships</th><th>Del %</th><th>RTO %</th>
        <th>FASR %</th><th>EDD Breach%</th><th>NDR %</th><th>NDR Res%</th>
        <th>Avg Pickup</th><th>Avg Intransit</th><th>Avg O2D</th>
      </tr>
      {build_courier_rows()}
    </table>
    </div>
    <p class="note">Red = breached. Del% ≥75% | RTO% ≤18% | FASR% ≥70% | EDD Breach% ≤30% | NDR% ≤15% | NDR Res% ≥60% | Avg Intransit ≤3d | Avg O2D ≤5d</p>
  </div>

  <!-- SECTION 4: FACILITY -->
  <div class="section">
    <div class="section-title">Performance by Facility / Warehouse</div>
    <div class="tbl-wrap">
    <table class="dtbl">
      <colgroup>
        <col style="width:14%"><col style="width:12%"><col style="width:14%"><col style="width:14%">
        <col style="width:13%"><col style="width:10%"><col style="width:11%"><col style="width:12%">
      </colgroup>
      <tr>
        <th class="left">Facility</th>
        <th>Allocation %</th><th>WH Fit %</th><th>Processed ≤24hr %</th>
        <th>Avg Processing</th><th>Pickup ≤24hr %</th><th>Avg Pickup Time</th><th>Avg Intransit</th><th>Avg O2D</th>
      </tr>
      {build_facility_rows()}
    </table>
    </div>
    <p class="note">Red = breached. WH Fit% ≥90% | Processed ≤24hr% ≥80% | Pickup ≤24hr% ≥75% | Avg Intransit ≤3d | Avg O2D ≤5d</p>
  </div>

  <!-- SECTION 5: NDR -->
  <div class="section">
    <div class="section-title">NDR (Non-Delivery Reattempt) View</div>
    <div class="tbl-wrap">
    <table class="dtbl">
      <colgroup>
        <col style="width:15%"><col style="width:7%"><col style="width:8%"><col style="width:7%">
        <col style="width:9%"><col style="width:9%"><col style="width:10%">
        <col style="width:8%"><col style="width:9%"><col style="width:9%">
      </colgroup>
      <tr>
        <th class="left">Courier</th>
        <th>Ships</th><th>NDR Count</th><th>NDR %</th>
        <th>Resolved</th><th>Resolved %</th><th>Became RTO %</th>
        <th>Avg Attempt</th><th>Avg Intransit</th><th>Avg O2D</th>
      </tr>
      {build_ndr_rows()}
    </table>
    </div>
    <p class="note">Red = breached. NDR% ≤15% | Resolved% ≥60% | Became RTO% ≤25% | Avg Intransit ≤3d | Avg O2D ≤5d</p>
  </div>

  <!-- SECTION 6: COD VS PREPAID -->
  <div class="section">
    <div class="section-title">COD vs Prepaid Split</div>
    <div class="tbl-wrap">
    <table class="dtbl">
      <colgroup>
        <col style="width:11%"><col style="width:8%"><col style="width:7%">
        <col style="width:7%"><col style="width:7%"><col style="width:7%">
        <col style="width:7%"><col style="width:8%"><col style="width:8%">
        <col style="width:9%"><col style="width:10%"><col style="width:11%">
      </colgroup>
      <tr>
        <th class="left">Payment</th>
        <th>Ships</th><th>Share %</th>
        <th>Del %</th><th>RTO %</th>
        <th>EDD Breach%</th><th>NDR %</th><th>NDR Res%</th>
        <th>Avg Proc</th><th>Avg Pickup</th><th>Avg Intransit</th><th>Avg O2D</th>
      </tr>
      {build_cod_rows()}
    </table>
    </div>
    <p class="note">Red = breached thresholds.</p>
  </div>

  <!-- SECTION 7: CITY TIER -->
  <div class="section">
    <div class="section-title">City Tier Breakdown</div>
    <div class="tbl-wrap">
    <table class="dtbl">
      <colgroup>
        <col style="width:11%"><col style="width:8%"><col style="width:7%">
        <col style="width:7%"><col style="width:7%"><col style="width:7%">
        <col style="width:7%"><col style="width:8%"><col style="width:8%">
        <col style="width:9%"><col style="width:10%"><col style="width:11%">
      </colgroup>
      <tr>
        <th class="left">Tier</th>
        <th>Ships</th><th>Share %</th>
        <th>Del %</th><th>RTO %</th>
        <th>EDD Breach%</th><th>NDR %</th><th>NDR Res%</th>
        <th>Avg Proc</th><th>Avg Pickup</th><th>Avg Intransit</th><th>Avg O2D</th>
      </tr>
      {build_tier_rows()}
    </table>
    </div>
    <p class="note">Pincode mapped to Tier via pincode_city_master. Red = breached thresholds.</p>
  </div>

  <!-- SECTION 8: ZONE BREAKDOWN -->
  <div class="section">
    <div class="section-title">Zone-wise Breakdown (zone_by_frido)</div>
    <div class="tbl-wrap">
    <table class="dtbl">
      <colgroup>
        <col style="width:11%"><col style="width:8%"><col style="width:7%">
        <col style="width:7%"><col style="width:7%"><col style="width:7%">
        <col style="width:7%"><col style="width:8%"><col style="width:8%">
        <col style="width:9%"><col style="width:10%"><col style="width:11%">
      </colgroup>
      <tr>
        <th class="left">Zone</th>
        <th>Ships</th><th>Share %</th>
        <th>Del %</th><th>RTO %</th>
        <th>EDD Breach%</th><th>NDR %</th><th>NDR Res%</th>
        <th>Avg Proc</th><th>Avg Pickup</th><th>Avg Intransit</th><th>Avg O2D</th>
      </tr>
      {build_zone_rows()}
    </table>
    </div>
    <p class="note">Zone A = local, B = metro-metro, C = metro-non-metro, D = cross-country, E = special. Red = breached thresholds.</p>
  </div>

  <!-- SECTION 9: TRANSIT TAT -->
  <div class="section">
    <div class="section-title">Transit TAT Distribution by Courier (Pickup → Delivery)</div>
    <div class="tbl-wrap">
    <table class="dtbl">
      <colgroup>
        <col style="width:18%"><col style="width:10%">
        <col style="width:8%"><col style="width:8%">
        <col style="width:8%"><col style="width:8%">
        <col style="width:7%"><col style="width:8%">
        <col style="width:8%"><col style="width:8%">
      </colgroup>
      <tr>
        <th class="left">Courier</th><th>Delivered</th>
        <th>≤2d</th><th>≤2d %</th>
        <th>3–4d</th><th>3-4d %</th>
        <th>5d</th><th>5d %</th>
        <th>5+d</th><th>5+d %</th>
      </tr>
      {build_tat_rows()}
    </table>
    </div>
    <p class="note">Red = 5+d% above 8% threshold.</p>
  </div>

  <!-- SECTION 9: RVP -->
  <div class="section">
    <div class="section-title">Reverse Pickup (RVP) — Customer Returns &amp; Exchanges</div>
    <div class="tbl-wrap">
    <table class="dtbl">
      <colgroup>
        <col style="width:40%"><col style="width:12%"><col style="width:13%"><col style="width:35%">
      </colgroup>
      <tr>
        <th class="left">Metric</th>
        <th>Count</th><th>Rate / TAT</th>
        <th class="left">Note</th>
      </tr>
      <tr><td class="name">RVP Created (Return + Exchange Initiated)</td><td>{r.rvp_created:,}</td><td>100%</td><td style="text-align:left;">All reverse requests in period</td></tr>
      <tr><td class="name">RVP Picked Up from Customer</td><td>{r.rvp_picked_up:,}</td><td{'  class="red-text"' if rvp_pickup_pct < 80 else ''}>{rvp_pickup_pct}%</td><td style="text-align:left;">{r.rvp_created - r.rvp_picked_up:,} pickups pending</td></tr>
      <tr><td class="name">RVP Delivered to Warehouse</td><td>{r.rvp_delivered:,}</td><td>{rvp_del_pct}%</td><td style="text-align:left;">Of created; {round(r.rvp_delivered/r.rvp_picked_up*100,1) if r.rvp_picked_up else 0}% of picked up</td></tr>
      <tr><td class="name">RVP Picked Up within 2d of Creation</td><td>{r.rvp_pickup_lte2d:,}</td><td>{rvp_lte2d_pct}%</td><td style="text-align:left;">Pickup SLA: ≤2 days of initiation</td></tr>
      <tr><td class="name">RVP Delivered to WH within 5d of Pickup</td><td>{r.rvp_wh_lte5d:,}</td><td>{rvp_wh5d_pct}%</td><td style="text-align:left;">WH delivery SLA: ≤5 days of pickup</td></tr>
      <tr><td class="name">Avg RVP Created → Pickup</td><td>—</td><td>{r.avg_rvp_pickup}d</td><td style="text-align:left;">Target ≤2d</td></tr>
      <tr><td class="name">Avg RVP Pickup → WH</td><td>—</td><td>{r.avg_rvp_wh}d</td><td style="text-align:left;">Target ≤5d</td></tr>
      <tr><td class="name">Avg RVP Total TAT</td><td>—</td><td>{r.avg_rvp_total}d</td><td style="text-align:left;">End-to-end: initiated → WH received</td></tr>
    </table>
    </div>
  </div>

  <!-- FOOTER -->
  <div class="footer">
    Frido Logistics &amp; Operations Report &nbsp;|&nbsp; {today.strftime('%d %b %Y')}
  </div>

</div>
</body>
</html>"""

print("Inlining CSS with premailer...")
inlined = transform(html, remove_classes=False, strip_important=False)

print("Getting Graph token...")
resp = requests.post(
    f'https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token',
    data={'grant_type':'client_credentials','client_id':CLIENT_ID,'client_secret':CLIENT_SECRET,'scope':'https://graph.microsoft.com/.default'}
)
resp.raise_for_status()
token = resp.json()['access_token']

payload = {
    'message': {
        'subject': f'Frido Logistics & Ops Performance Report | {start_date.strftime("%d %b")} – {(cutoff - timedelta(days=1)).strftime("%d %b %Y")}',
        'body': {'contentType': 'HTML', 'content': inlined},
        'toRecipients': [{'emailAddress': {'address': e.strip()}} for e in TO_EMAILS],
        'ccRecipients':  [{'emailAddress': {'address': e.strip()}} for e in CC_EMAILS],
    },
    'saveToSentItems': False,
}
resp = requests.post(
    f'https://graph.microsoft.com/v1.0/users/{FROM_EMAIL}/sendMail',
    headers={'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'},
    json=payload
)
resp.raise_for_status()
print(f'Email sent to {TO_EMAILS} — status {resp.status_code}')
