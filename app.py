from flask import Flask, jsonify
import boto3
from datetime import datetime, timedelta, timezone
import json
import os

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

# ===== ALERT ===== (giảm spam)
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

    old = load_state().get("ec2", [])

    send_alert(old, data)
    save_state({"ec2": data})
    save_log(data)

    html = f"""
    <meta http-equiv="refresh" content="60">
    <meta http-equiv="Cache-Control" content="no-cache">

    <h2>📊 CloudOps Multi-Region Dashboard</h2>
    <p>⏰ {now()}</p>

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