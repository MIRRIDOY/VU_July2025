import urllib3
import time
import boto3

cloudwatch = boto3.client('cloudwatch')
URL = "https://example.com"  
http = urllib3.PoolManager()

def lambda_handler(event, context):
    availability = 1
    latency = 0
    
    start_time = time.time()
    try:
        response = http.request('GET', URL)
        latency = (time.time() - start_time) * 1000  # ms
        if response.status != 200:
            availability = 0
    except Exception:
        availability = 0
        latency = 0

    # Push metrics to CloudWatch
    cloudwatch.put_metric_data(
        Namespace='WebsiteMonitoring',
        MetricData=[
            {'MetricName': 'Availability', 'Value': availability, 'Unit': 'Count'},
            {'MetricName': 'Latency', 'Value': latency, 'Unit': 'Milliseconds'}
        ]
    )

    return {"availability": availability, "latency": latency}
