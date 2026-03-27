from flask import Flask, jsonify
import boto3
from datetime import datetime, timedelta, timezone
import json
import os
import matplotlib.pyplot as plt
import io

app = Flask(__name__)

# ===== TIME VN =====
VN_TZ = timezone(timedelta(hours=7))

def now():
    return datetime.now(VN_TZ).strftime("%d/%m/%Y %H:%M:%S")

# ===== GET ALL REGIONS =====
def get_all_regions():
    ec2 = boto3.client("ec2", region_name="us-east-1")
    res = ec2.describe_regions()
    return [r["RegionName"] for r in res["Regions"]]

# ===== EC2 MULTI REGION =====
def get_ec2():
    regions = get_all_regions()
    all_data = []

    for region in regions:
        try:
            ec2 = boto3.client("ec2", region_name=region)
            res = ec2.describe_instances()

            for r in res["Reservations"]:
                for i in r["Instances"]:
                    name = "Không tên"

                    if "Tags" in i:
                        for tag in i["Tags"]:
                            if tag["Key"] == "Name":
                                name = tag["Value"]

                    all_data.append({
                        "region": region,
                        "id": i["InstanceId"],
                        "name": name,
                        "state": i["State"]["Name"]
                    })

        except Exception as e:
            print("Lỗi region:", region, e)

    return all_data

# ===== COST =====
# def get_cost_month():
#     try:
#         ce = boto3.client("ce")
#         today = date.today()

#         start = today.replace(day=1).strftime("%Y-%m-%d")
#         end = today.strftime("%Y-%m-%d")

#         res = ce.get_cost_and_usage(
#             TimePeriod={"Start": start, "End": end},
#             Granularity="MONTHLY",
#             Metrics=["UnblendedCost"]
#         )

#         return round(float(res["ResultsByTime"][0]["Total"]["UnblendedCost"]["Amount"]), 4)
#     except:
#         return 0

# ===== COST 7 DAYS =====
# def get_cost_7days():
#     try:
#         ce = boto3.client("ce")

#         end = date.today()
#         start = (end - timedelta(days=7)).strftime("%Y-%m-%d")
#         end = end.strftime("%Y-%m-%d")

#         res = ce.get_cost_and_usage(
#             TimePeriod={"Start": start, "End": end},
#             Granularity="DAILY",
#             Metrics=["UnblendedCost"]
#         )

#         dates, costs = [], []

#         for d in res["ResultsByTime"]:
#             dates.append(d["TimePeriod"]["Start"])
#             costs.append(float(d["Total"]["UnblendedCost"]["Amount"]))

#         return dates, costs
#     except:
#         return [], []

# ===== CHART =====

@app.route("/chart")
def chart():
    return "Chart disabled"

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

# ===== MAIN =====
@app.route("/")
def home():
    data = get_ec2()
    # cost = get_cost_month()

    old = load_state().get("ec2", [])

    send_alert(old, data)
    save_state({"ec2": data})
    save_log(data)

    html = f"""
    <meta http-equiv="refresh" content="10">
    <meta http-equiv="Cache-Control" content="no-cache">

    <h2>📊 CloudOps Multi-Region Dashboard</h2>
    <p>⏰ {now()}</p>

    

    <h3>📈 Biểu đồ</h3>
    <img src="/chart">

    <h3>🖥️ EC2</h3>
    <table border="1" cellpadding="8">
        <tr>
            <th>Region</th>
            <th>Name</th>
            <th>ID</th>
            <th>Status</th>
        </tr>
    """

    for i in data:
        color = "green" if i["state"] == "running" else "red"

        html += f"""
        <tr>
            <td>{i['region']}</td>
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