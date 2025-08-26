import os, time, urllib.request, json
import boto3

cw = boto3.client("cloudwatch")
URL = os.environ["TARGET_URL"]
NAMESPACE = os.environ.get("NAMESPACE", "Canary")
SITE = os.environ.get("SITE_NAME", "MainSite")

def _put(metric, value, unit=None):
    datum = {"MetricName": metric, "Value": float(value),
             "Dimensions": [{"Name": "SiteName", "Value": SITE}]}
    if unit:
        datum["Unit"] = unit
    cw.put_metric_data(Namespace=NAMESPACE, MetricData=[datum])

def handler(event, context):
    start = time.time()
    ok = 0
    latency_ms = 0.0
    try:
        with urllib.request.urlopen(URL, timeout=10) as r:
            latency_ms = (time.time() - start) * 1000.0
            # count 2xx as success; (optional) treat 3xx as success by changing <400
            ok = 1 if 200 <= r.status < 300 else 0
    except Exception:
        latency_ms = (time.time() - start) * 1000.0
        ok = 0

    _put("LatencyMs", latency_ms, unit="Milliseconds")
    _put("Availability", ok)

    return {"ok": ok, "latency_ms": round(latency_ms, 1)}