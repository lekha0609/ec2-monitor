from flask import Flask, jsonify
import boto3
from datetime import datetime, date, timedelta, timezone
import json
import os
import matplotlib.pyplot as plt
import io

app = Flask(__name__)

# ===== TIME VN =====
VN_TZ = timezone(timedelta(hours=7))

def now():
    return datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")

# ===== EC2 =====
def get_ec2():
    ec2 = boto3.client("ec2")
    res = ec2.describe_instances()

    data = []
    for r in res["Reservations"]:
        for i in r["Instances"]:
            name = "Không tên"

            if "Tags" in i:
                for tag in i["Tags"]:
                    if tag["Key"] == "Name":
                        name = tag["Value"]

            data.append({
                "id": i["InstanceId"],
                "name": name,
                "state": i["State"]["Name"]
            })

    return data

# ===== COST =====
def get_cost_month():
    try:
        ce = boto3.client("ce")

        today = date.today()
        start = today.replace(day=1).strftime("%Y-%m-%d")
        end = today.strftime("%Y-%m-%d")

        res = ce.get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity="MONTHLY",
            Metrics=["UnblendedCost"]
        )

        return round(float(res["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"]), 4)
    except:
        return 0

# ===== COST 7 DAYS =====
def get_cost_7days():
    try:
        ce = boto3.client("ce")

        end = date.today()
        start = (end - timedelta(days=7)).strftime("%Y-%m-%d")
        end = end.strftime("%Y-%m-%d")

        res = ce.get_cost_and_usage(
            TimePeriod={"Start": start, "End": end},
            Granularity="DAILY",
            Metrics=["UnblendedCost"]
        )

        dates, costs = [], []

        for d in res["ResultsByTime"]:
            dates.append(d["TimePeriod"]["Start"])
            costs.append(float(d["Total"]["UnblendedCost"]["Amount"]))

        return dates, costs
    except:
        return [], []

# ===== CHART (TRẢ ẢNH RIÊNG) =====
@app.route("/chart")
def chart():
    dates, costs = get_cost_7days()

    if not dates:
        return "No data"

    plt.figure()
    plt.plot(dates, costs, marker='o')
    plt.xticks(rotation=45)
    plt.title("Chi phí 7 ngày")

    img = io.BytesIO()
    plt.savefig(img, format="png", bbox_inches='tight')
    img.seek(0)

    return app.response_class(img.getvalue(), mimetype='image/png')

# ===== LOG =====
def save_log(data):
    with open("log.txt", "a", encoding="utf-8") as f:
        f.write(f"{now()} - {data}\n")

def read_log():
    if not os.path.exists("log.txt"):
        return "Chưa có log"
    return open("log.txt", encoding="utf-8").read()

# ===== STATE =====
STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {}

def save_state(state):
    json.dump(state, open(STATE_FILE, "w"))

# ===== ALERT =====
def send_alert(old, new):
    try:
        sns = boto3.client("sns")

        old_map = {i["id"]: i["state"] for i in old}
        changes = []

        for i in new:
            if i["id"] not in old_map or old_map[i["id"]] != i["state"]:
                changes.append(f"{i['name']} ({i['id']}) → {i['state']}")

        if changes:
            msg = "🚨 EC2 THAY ĐỔI\n\n⏰ " + now() + "\n\n" + "\n".join(changes)

            sns.publish(
                TopicArn=os.environ.get("SNS_TOPIC"),
                Subject="EC2 Alert",
                Message=msg
            )
    except Exception as e:
        print("SNS lỗi:", e)

# ===== MAIN PAGE =====
@app.route("/")
def home():
    data = get_ec2()
    cost = get_cost_month()

    old = load_state().get("ec2", [])

    send_alert(old, data)
    save_state({"ec2": data})
    save_log(data)

    html = f"""
    <meta http-equiv="refresh" content="10">
    <meta http-equiv="Cache-Control" content="no-cache">

    <h2>📊 CloudOps Dashboard</h2>
    <p>⏰ {now()}</p>

    <h3>💰 Cost tháng: {cost} USD</h3>

    <h3>📈 Biểu đồ</h3>
    <img src="/chart">

    <h3>🖥️ EC2</h3>
    <table border="1" cellpadding="8">
        <tr>
            <th>Name</th>
            <th>ID</th>
            <th>Status</th>
        </tr>
    """

    for i in data:
        color = "green" if i["state"] == "running" else "red"

        html += f"""
        <tr>
            <td>{i['name']}</td>
            <td>{i['id']}</td>
            <td>
                <span style="
                    display:inline-block;
                    width:12px;
                    height:12px;
                    border-radius:50%;
                    background:{color};
                    margin-right:5px;
                "></span>
                {i['state']}
            </td>
        </tr>
        """

    html += "</table><br><a href='/logs'>📄 Xem log</a>"

    return html

# ===== LOG VIEW =====
@app.route("/logs")
def logs():
    return f"<pre>{read_log()}</pre>"

# ===== API =====
@app.route("/api/ec2")
def api():
    return jsonify(get_ec2())

if __name__ == "__main__":
    app.run(debug=True)