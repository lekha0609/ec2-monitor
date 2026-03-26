from flask import Flask
import boto3
from datetime import datetime, date, timedelta, timezone
import json
import os

app = Flask(__name__)

# ===== TIME (VIỆT NAM) =====
VN_TZ = timezone(timedelta(hours=7))

def get_time_vn():
    return datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")

# ===== EC2 =====
def get_ec2():
    ec2 = boto3.client("ec2")
    res = ec2.describe_instances()

    instances = []

    for r in res["Reservations"]:
        for i in r["Instances"]:
            name = "Không tên"

            if "Tags" in i:
                for tag in i["Tags"]:
                    if tag["Key"] == "Name":
                        name = tag["Value"]

            instances.append({
                "id": i["InstanceId"],
                "name": name,
                "state": i["State"]["Name"]
            })

    return instances

# ===== COST =====
def get_cost():
    try:
        ce = boto3.client("ce")
        today = date.today().strftime("%Y-%m-%d")

        res = ce.get_cost_and_usage(
            TimePeriod={"Start": today, "End": today},
            Granularity="DAILY",
            Metrics=["UnblendedCost"]
        )

        cost = float(res["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"])
        return round(cost, 4)

    except Exception as e:
        print("Cost error:", e)
        return 0

# ===== LOG =====
def save_log(data):
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(f"{get_time_vn()} - {data}\n")

# ===== STATE (TRÁNH SPAM MAIL) =====
STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"running": 0}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

# ===== SNS =====
def send_alert(message):
    try:
        sns = boto3.client("sns")
        sns.publish(
            TopicArn=os.environ.get("SNS_TOPIC"),
            Subject="🚨 EC2 Alert",
            Message=message
        )
    except Exception as e:
        print("SNS error:", e)

# ===== ROUTE =====
@app.route("/")
def home():
    ec2_data = get_ec2()
    cost = get_cost()
    now = get_time_vn()

    running = sum(1 for i in ec2_data if i["state"] == "running")
    stopped = len(ec2_data) - running

    save_log(ec2_data)

    # ===== ALERT CHỈ KHI THAY ĐỔI =====
    old_state = load_state()

    if running != old_state.get("running", 0):
        message = f"""
📊 BÁO CÁO EC2

⏰ Thời gian: {now}
🟢 Đang chạy: {running}
🔴 Đã tắt: {stopped}
💰 Chi phí hôm nay: {cost} USD
        """

        send_alert(message)
        save_state({"running": running})

    # ===== HTML =====
    html = f"""
    <meta http-equiv="refresh" content="10">
    <h2>📊 EC2 Monitor (CloudOps)</h2>
    <p>⏰ {now}</p>
    <p>🟢 Running: {running} | 🔴 Stopped: {stopped}</p>
    <p>💰 Cost: {cost} USD</p>

    <table border="1" cellpadding="8">
        <tr>
            <th>Name</th>
            <th>ID</th>
            <th>Status</th>
        </tr>
    """

    for i in ec2_data:
        color = "green" if i["state"] == "running" else "red"

        html += f"""
        <tr>
            <td>{i['name']}</td>
            <td>{i['id']}</td>
            <td style="color:{color}">{i['state']}</td>
        </tr>
        """

    html += "</table>"

    return html


# ===== RUN LOCAL =====
if __name__ == "__main__":
    app.run(debug=True)