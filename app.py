from flask import Flask
import boto3
from datetime import datetime

app = Flask(__name__)

def get_ec2():
    ec2 = boto3.client('ec2')
    res = ec2.describe_instances()

    data = []
    for r in res['Reservations']:
        for i in r['Instances']:
            instance_id = i['InstanceId']
            state = i['State']['Name']

            name = "Không có tên"
            if 'Tags' in i:
                for tag in i['Tags']:
                    if tag['Key'] == 'Name':
                        name = tag['Value']

            data.append({
                "id": instance_id,
                "name": name,
                "state": state
            })
    return data

@app.route("/")
def home():
    data = get_ec2()

    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    html = f"""
    <meta http-equiv="refresh" content="10">
    <h2>📊 Báo cáo trạng thái EC2</h2>
    <p>⏰ Thời gian: {now}</p>
    <table border="1" cellpadding="8">
        <tr>
            <th>Tên</th>
            <th>Instance ID</th>
            <th>Trạng thái</th>
        </tr>
    """

    for i in data:
        color = "green" if i['state'] == "running" else "red"

        trangthai = "🟢 Đang chạy" if i['state'] == "running" else "🔴 Đã dừng"

        html += f"""
        <tr>
            <td>{i['name']}</td>
            <td>{i['id']}</td>
            <td style='color:{color}'>{trangthai}</td>
        </tr>
        """

    html += "</table>"

    return html

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
