

import boto3
from datetime import datetime
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

SNS_TOPIC_ARN = "arn:aws:sns:ap-southeast-1:885232248435:qos-ric-alerts"
AWS_REGION    = "ap-southeast-1"

_last_alert_time = {}
ALERT_COOLDOWN_SEC = 60


class MockAlert:
    @staticmethod
    def send(message: str, user_type: str = "unknown", compliance: float = 0.0):
        print("\n" + "!"*50)
        print(f"  [MOCK ALERT] SLA VIOLATION DETECTED")
        print(f"  User type  : {user_type.upper()}")
        print(f"  Compliance : {compliance*100:.1f}%")
        print(f"  Message    : {message}")
        print(f"  Time       : {datetime.now().strftime('%H:%M:%S')}")
        print("!"*50 + "\n")
        return True


def send_alert(message: str, user_type: str = "unknown", compliance: float = 0.0) -> bool:
    global _last_alert_time

    now  = datetime.now().timestamp()
    last = _last_alert_time.get(user_type, 0)
    if now - last < ALERT_COOLDOWN_SEC:
        print(f"[SNS] Cooldown aktif — skip")
        return False

    timestamp_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    full_message = (
        f"[QoS-RIC ALERT]\n"
        f"Waktu    : {timestamp_str}\n"
        f"Tipe user: {user_type.upper()}\n"
        f"SLA rate : {compliance*100:.1f}% (threshold: 90%)\n"
        f"Pesan    : {message}\n\n"
        f"Periksa dashboard: http://54.251.207.185:5000"
    )

    try:
        sns = boto3.client("sns", region_name=AWS_REGION)
        response = sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=full_message,
            Subject=f"[QoS-RIC] SLA Violation - {user_type.upper()}"
        )
        _last_alert_time[user_type] = now
        print(f"[SNS] Alert terkirim! MessageId: {response['MessageId']}")
        return True
    except Exception as e:
        print(f"[SNS] Gagal: {e}")
        MockAlert.send(message, user_type, compliance)
        return False


if __name__ == "__main__":
    print("Testing SNS alert...")
    send_alert(
        message    = "Test alert dari QoS-RIC di AWS",
        user_type  = "emergency",
        compliance = 0.82
    )
