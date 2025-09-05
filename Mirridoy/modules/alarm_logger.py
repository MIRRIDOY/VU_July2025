import os, json, uuid
import boto3
from datetime import datetime, timedelta, timezone

TABLE_NAME = os.environ["TABLE_NAME"]
TTL_DAYS = int(os.environ.get("TTL_DAYS", "90"))

ddb = boto3.resource("dynamodb")
table = ddb.Table(TABLE_NAME)

def _ttl_epoch(days: int) -> int:
    return int((datetime.now(timezone.utc) + timedelta(days=days)).timestamp())

def handler(event, context):
    """
    SNS event -> parse CloudWatch Alarm message (JSON) -> save to DynamoDB.
    Expects event.Records[].Sns.Message to be JSON from CloudWatch.
    """
    results = []
    for rec in event.get("Records", []):
        sns = rec.get("Sns", {})
        msg_raw = sns.get("Message", "")

        try:
            msg = json.loads(msg_raw)
        except Exception:
            msg = {"RawMessage": msg_raw}

        alarm_name = msg.get("AlarmName", "UnknownAlarm")
        new_state  = msg.get("NewStateValue", "UNKNOWN")
        old_state  = msg.get("OldStateValue", "UNKNOWN")
        state_time = msg.get("StateChangeTime") or datetime.now(timezone.utc).isoformat()
        reason     = msg.get("NewStateReason", "")
        region     = msg.get("Region", "N/A")
        trigger    = msg.get("Trigger", {})

        item = {
            "pk": alarm_name,             # partition key
            "sk": state_time,             # sort key (ISO8601)
            "id": str(uuid.uuid4()),
            "new_state": new_state,
            "old_state": old_state,
            "reason": reason,
            "region": region,
            "metric_name": trigger.get("MetricName"),
            "namespace": trigger.get("Namespace"),
            "threshold": trigger.get("Threshold"),
            "comparison": trigger.get("ComparisonOperator"),
            "evaluation_periods": trigger.get("EvaluationPeriods"),
            "datapoints_to_alarm": trigger.get("DatapointsToAlarm"),
            "ttl": _ttl_epoch(TTL_DAYS),
            "raw": msg,                   # keep full message for audit/debug
        }

        table.put_item(Item=item)
        results.append({"alarm": alarm_name, "state": new_state, "time": state_time})

    return {"saved": results}
