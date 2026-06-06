from pathlib import Path
import requests


def load_pushover_keys(filename):
    project_dir = Path(__file__).resolve().parent.parent
    key_file = project_dir / filename
    data = {}

    with open(key_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, value = line.split("=", 1)
                data[key.strip()] = value.strip()

    return data


def send_pushover_notification(title, message, priority, enabled, filename, api_url, timeout_seconds):
    if not enabled:
        return False

    try:
        keys = load_pushover_keys(filename)
    except Exception as e:
        print("Pushover key file error:", e)
        return False

    user_key = keys.get("PUSHOVER_USER_KEY")
    app_token = keys.get("PUSHOVER_APP_TOKEN")

    if not user_key or not app_token:
        print("Pushover config missing: PUSHOVER_USER_KEY or PUSHOVER_APP_TOKEN")
        return False

    try:
        response = requests.post(
            api_url,
            data={
                "token": app_token,
                "user": user_key,
                "title": title,
                "message": message,
                "priority": priority,
            },
            timeout=timeout_seconds,
        )

        print("Pushover status:", response.status_code)
        print("Pushover response:", response.text)

        response.raise_for_status()
        return True

    except Exception as e:
        print("Pushover request failed:", e)
        return False


def build_push_message(page_name, page_data, smoke_priority, default_priority):
    content = page_data[page_name]

    if page_name == "smoke":
        return "Smoke Alert", "Critical smoke event detected", smoke_priority

    title = f"{content['title']} Alert"
    unit = content["unit"]
    value = content["value"]

    if unit:
        message = f"{content['title']} critical: {value} {unit}"
    else:
        message = f"{content['title']} critical: {value}"

    return title, message, default_priority


def update_alert_states_from_page_data(page_data, alert_states):
    for page_name in alert_states.keys():
        alert_states[page_name] = page_data[page_name]["critical"]


def process_push_notifications(
    page_data,
    alert_states,
    pushover_enabled,
    pushover_keys_file,
    pushover_api_url,
    pushover_timeout_seconds,
    pushover_smoke_priority,
    pushover_default_priority,
):
    if page_data["smoke"]["critical"]:
        if not alert_states["smoke"]:
            title, message, priority = build_push_message(
                "smoke",
                page_data,
                pushover_smoke_priority,
                pushover_default_priority,
            )
            send_pushover_notification(
                title,
                message,
                priority,
                pushover_enabled,
                pushover_keys_file,
                pushover_api_url,
                pushover_timeout_seconds,
            )
        update_alert_states_from_page_data(page_data, alert_states)
        return

    for page_name in alert_states.keys():
        if page_name == "smoke":
            continue

        if not page_data[page_name]["critical"]:
            alert_states[page_name] = False
            continue

        if alert_states[page_name]:
            continue

        title, message, priority = build_push_message(
            page_name,
            page_data,
            pushover_smoke_priority,
            pushover_default_priority,
        )
        send_pushover_notification(
            title,
            message,
            priority,
            pushover_enabled,
            pushover_keys_file,
            pushover_api_url,
            pushover_timeout_seconds,
        )
        alert_states[page_name] = True