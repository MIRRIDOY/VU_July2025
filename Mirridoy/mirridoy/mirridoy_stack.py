from aws_cdk import (
    Stack, Duration,
    aws_lambda as _lambda,
    aws_events as events,
    aws_events_targets as targets,
    aws_cloudwatch as cloudwatch,
    aws_iam as iam,
    aws_sns as sns,
    aws_sns_subscriptions as subs,
    aws_cloudwatch_actions as cloudwatch_actions,
    CfnOutput,
)
from constructs import Construct

class MirridoyStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # --- Lambda canary ---
        canary = _lambda.Function(
            self, "WebCanary",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="canary.handler",
            code=_lambda.Code.from_asset("modules"),  # Ensure modules/canary.py exists
            timeout=Duration.seconds(30),
            environment={
                "TARGET_URL": "https://medilinks.com.au/",
                "NAMESPACE": "Canary",
                "SITE_NAME": "Medilinks",
            },
        )

        # Allow Lambda to publish metrics and write logs
        canary.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "cloudwatch:PutMetricData",
                "logs:CreateLogGroup",
                "logs:CreateLogStream",
                "logs:PutLogEvents"
            ],
            resources=["*"],
        ))

        # Schedule: run every 5 minutes
        rule = events.Rule(
            self, "CanarySchedule",
            schedule=events.Schedule.rate(Duration.minutes(5)),
        )
        rule.add_target(targets.LambdaFunction(canary))

        # Metrics
        availability_metric = cloudwatch.Metric(
            namespace="Canary",
            metric_name="Availability",
            period=Duration.minutes(5),
            statistic="Average",
        )
        latency_metric = cloudwatch.Metric(
            namespace="Canary",
            metric_name="LatencyMs",
            period=Duration.minutes(5),
            statistic="Average",
        )

        # --- SNS Topic for Alerts ---
        alarm_topic = sns.Topic(self, "CanaryAlarmTopic")
        alarm_topic.add_subscription(subs.EmailSubscription("mirridoy697@gmail.com"))  

        # Alarms
        availability_alarm = cloudwatch.Alarm(
            self, "AvailabilityAlarm",
            metric=availability_metric,
            threshold=0.5,
            comparison_operator=cloudwatch.ComparisonOperator.LESS_THAN_THRESHOLD,
            evaluation_periods=1,
            datapoints_to_alarm=1,
        )
        latency_alarm = cloudwatch.Alarm(
            self, "LatencyAlarm",
            metric=latency_metric,
            threshold=2000,
            comparison_operator=cloudwatch.ComparisonOperator.GREATER_THAN_THRESHOLD,
            evaluation_periods=1,
            datapoints_to_alarm=1,
        )

        # Add SNS notification actions
        availability_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))
        latency_alarm.add_alarm_action(cloudwatch_actions.SnsAction(alarm_topic))

        # Outputs
        CfnOutput(self, "FunctionName", value=canary.function_name)
        CfnOutput(self, "Schedule", value=rule.rule_name)
        CfnOutput(self, "AlarmTopicArn", value=alarm_topic.topic_arn)
