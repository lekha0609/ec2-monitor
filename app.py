from flask import Flask
import boto3
from datetime import datetime, date
import json
import os

app = Flask(__name__)

# ===== EC2 =====
def get_ec2():
    ec2 = boto3.client('ec2')
    res = ec2.describe_instances()

    data = []
    for r in res['Reservations']:
        for i in r['Instances']:
            name = "Không tên"
            if 'Tags' in i:
                for tag in i['Tags']:
                    if tag['Key'] == 'Name':
                        name = tag['Value']

            data.append({
                "id": i['InstanceId'],
                "name": name,
                "state": i['State']['Name']
            })
    return data

# ===== COST =====
def get_cost():
    try:
        ce = boto3.client('ce')
        today = date.today().strftime("%Y-%m-%d")

        res = ce.get_cost_and_usage(
            TimePeriod={'Start': today, 'End': today},
            Granularity='DAILY',
            Metrics=['UnblendedCost']
        )

        return round(float(res['ResultsByTime'][0]['Total']['UnblendedCost']['Amount']), 4)
    except:
        return 0

# ===== LOG =====
def save_log(data):
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(f"{datetime.now()} - {data}\n")

# ===== ALERT SNS =====
def send_alert(msg):
    try:
        sns = boto3.client('sns')
        sns.publish(
            TopicArn=os.environ.get("SNS_TOPIC"),
            Message=msg,
            Subject="🚨 EC2 Alert"
        )
    except:
        pass

# ===== ROUTE =====
@app.route("/")
def home():
    data = get_ec2()
    cost = get_cost()
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    running = sum(1 for i in data if i['state'] == 'running')
    stopped = len(data) - running

    # log
    save_log(data)

    html = f"""
    <html>
    <head>
        <meta http-equiv="refresh" content="10">
        <title>CloudOps Dashboard</title>
    </head>
    <body>
        <h2>📊 Dashboard CloudOps</h2>
        <p>⏰ {now}</p>

        <h3>📊 Thống kê</h3>
        <p>Tổng: {len(data)} | Running: {running} | Stopped: {stopped}</p>

        <h3>💰 Chi phí hôm nay</h3>
        <p>{cost} USD</p>

        <h3>🖥️ Danh sách EC2</h3>
        <table border="1" cellpadding="8">
            <tr>
                <th>Tên</th>
                <th>ID</th>
                <th>Trạng thái</th>
            </tr>
    """

    for i in data:
        color = "green" if i['state'] == "running" else "red"
        status = "🟢 Đang chạy" if i['state'] == "running" else "🔴 Dừng"

        html += f"""
        <tr>
            <td>{i['name']}</td>
            <td>{i['id']}</td>
            <td style='color:{color}'>{status}</td>
        </tr>
        """

    html += "</table></body></html>"

    return html