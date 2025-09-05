from aws_cdk import (
    Stack, Duration, RemovalPolicy,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_cloudwatch as cloudwatch,
    aws_iam as iam,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_cloudwatch_actions as cw_actions,
    aws_dynamodb as dynamodb,
    CfnOutput,
)
from constructs import Construct

ALERT_EMAIL = "mirridoy697@gmail.com"   # <-- change if needed
SITE_NAME   = "Medilinks"               # must match canary.py env (SITE_NAME)
NAMESPACE   = "Canary"                  # must match canary.py env (NAMESPACE)
TARGET_URL  = "https://medilinks.com.au/"

class MirridoyStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # ---------- Lambda canary (already used by you) ----------
        canary = _lambda.Function(
            self, "WebCanary",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="canary.handler",
            code=_lambda.Code.from_asset("modules"),    # modules/canary.py
            timeout=Duration.seconds(30),
            environment={
                "TARGET_URL": TARGET_URL,
                "NAMESPACE": NAMESPACE,
                "SITE_NAME": SITE_NAME,
            },
        )
        canary.add_to_role_policy(iam.PolicyStatement(
            actions=["cloudwatch:PutMetricData", "logs:CreateLogGroup",
                     "logs:CreateLogStream", "logs:PutLogEvents"],
            resources=["*"],
        ))

        # Run every 5 minutes
        rule = events.Rule(
            self, "CanarySchedule",
            schedule=events.Schedule.rate(Duration.minutes(5)),
        )
        rule.add_target(targets.LambdaFunction(canary))

        # ---------- Metrics (MUST match canary namespace + dimensions) ----------
        availability_metric = cloudwatch.Metric(
            namespace=NAMESPACE,
            metric_name="Availability",
            period=Duration.minutes(5),
            statistic="Average",
            dimensions_map={"SiteName": SITE_NAME},
        )
        latency_metric = cloudwatch.Metric(
            namespace=NAMESPACE,
            metric_name="LatencyMs",
            period=Duration.minutes(5),
            statistic="Average",
            unit=cloudwatch.Unit.MILLISECONDS,
            dimensions_map={"SiteName": SITE_NAME},
        )

        # ---------- SNS topic + email subscription ----------
        alarm_topic = sns.Topic(self, "CanaryAlarmTopic")
        alarm_topic.add_subscription(subs.EmailSubscription(ALERT_EMAIL))  # confirm in email!

        # ---------- CloudWatch alarms -> SNS ----------
        availability_alarm = cloudwatch.Alarm(
            self, "AvailabilityAlarm",
            metric=availability_metric,
            threshold=0.5,   # 0 or 1; <0.5 means failure
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            alarm_description=f"{SITE_NAME} availability below 50% (last 5 min).",
        )
        latency_alarm = cloudwatch.Alarm(
            self, "LatencyAlarm",
            metric=latency_metric,
            threshold=2000,  # ms
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=1,
            datapoints_to_alarm=1,
            alarm_description=f"{SITE_NAME} average latency > 2000 ms (last 5 min).",
        )
        for a in (availability_alarm, latency_alarm):
            a.add_alarm_action(cw_actions.SnsAction(alarm_topic))
            a.add_ok_action(cw_actions.SnsAction(alarm_topic))   # notify on recovery too

        # ---------- DynamoDB table for alarm history ----------
        table = dynamodb.Table(
            self, "AlarmHistory",
            partition_key=dynamodb.Attribute(name="pk", type=dynamodb.AttributeType.STRING),  # AlarmName
            sort_key=dynamodb.Attribute(name="sk", type=dynamodb.AttributeType.STRING),      # StateChangeTime
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            time_to_live_attribute="ttl",          # epoch seconds; auto-expire items
            removal_policy=RemovalPolicy.DESTROY,  # change to RETAIN in production
        )

        # ---------- SNS subscriber Lambda: writes events to DynamoDB ----------
        alarm_logger = _lambda.Function(
            self, "AlarmLogger",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="alarm_logger.handler",
            code=_lambda.Code.from_asset("modules"),   # modules/alarm_logger.py
            timeout=Duration.seconds(30),
            environment={
                "TABLE_NAME": table.table_name,
                "TTL_DAYS": "90",   # keep alarm history for 90 days
            },
        )
        table.grant_write_data(alarm_logger)
        alarm_topic.add_subscription(subs.LambdaSubscription(alarm_logger))

        # ---------- (Optional) small dashboard ----------
        dashboard = cloudwatch.Dashboard(self, "CanaryDashboard",
                                         dashboard_name=f"{SITE_NAME}-Health")
        dashboard.add_widgets(
            cloudwatch.GraphWidget(
                title="Availability (0..1)",
                left=[availability_metric],
                left_y_axis=cloudwatch.YAxisProps(min=0, max=1),
            ),
            cloudwatch.GraphWidget(
                title="Latency (ms)",
                left=[latency_metric],
            ),
        )

        # ---------- Outputs ----------
        CfnOutput(self, "FunctionName", value=canary.function_name)
        CfnOutput(self, "Schedule", value=rule.rule_name)
        CfnOutput(self, "AlarmTopicArn", value=alarm_topic.topic_arn)
        CfnOutput(self, "AlarmLoggerName", value=alarm_logger.function_name)
        CfnOutput(self, "AlarmHistoryTable", value=table.table_name)
        CfnOutput(self, "DashboardName", value=dashboard.dashboard_name)
