import boto3
import json
import os

STATE_FILE = "state.json"
SNS_ARN = "arn:aws:sns:ap-southeast-1:693517970746:CloudOps_Alert"

def check_ec2():
    ec2 = boto3.client('ec2')
    res = ec2.describe_instances()

    new = {}
    changes = []

    old = {}
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            old = json.load(f)

    for r in res['Reservations']:
        for i in r['Instances']:
            id = i['InstanceId']
            state = i['State']['Name']
            new[id] = state

            if old.get(id) != state:
                changes.append(f"{id}: {old.get(id)} → {state}")

    with open(STATE_FILE, "w") as f:
        json.dump(new, f)

    if changes:
        sns = boto3.client('sns')
        sns.publish(
            TopicArn=SNS_ARN,
            Message="\n".join(changes),
            Subject="EC2 Changed"
        )

    return new

# chạy khi CI/CD gọi
if __name__ == "__main__":
    data = check_ec2()
    print(data)