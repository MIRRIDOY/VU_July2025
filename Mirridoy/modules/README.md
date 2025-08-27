 Website Canary (AWS CDK • Python)

This project uses **AWS CDK** to deploy a simple **website canary**.  
It runs a Lambda function every 5 minutes to check the availability and latency of a target site (`https://medilinks.com.au/`), publishes metrics to **CloudWatch**, and raises **SNS email alerts** when thresholds are breached.

Features
- **Lambda Canary**: Pings the target site every 5 minutes.
- Publishes custom CloudWatch metrics:
  - `Availability` → 1 if site responds with 2xx, else 0.
  - `LatencyMs` → response time in milliseconds.
- **CloudWatch Alarms**:
  - Availability `< 0.5` → site down.
  - Latency `> 2000 ms` → site too slow.
- **SNS Notifications**: Sends alerts to your email.