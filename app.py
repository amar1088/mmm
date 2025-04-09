from flask import Flask, request, jsonify
import os, threading, time, requests, uuid
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

status_data = {}
task_threads = {}
stop_flags = {}

def read_file_lines(path):
    with open(path, 'r', encoding='utf-8') as f:
        return [x.strip() for x in f if x.strip()]

def clean_comment(text):
    return text.replace('<b>', '').replace('</b>', '').replace('>/<B>', '').strip()

def get_profile_name(token):
    try:
        res = requests.get(f"https://graph.facebook.com/me?access_token={token}", timeout=5)
        data = res.json()
        name = data.get("name", "Unknown")
        return f"[Page] {name}" if "category" in data else f"[Profile] {name}"
    except:
        return "Unknown"

def comment_worker(task_id, token_path, comment_path, post_ids_raw, first, last, delay):
    tokens = read_file_lines(token_path)
    comments = read_file_lines(comment_path)
    post_ids = [x.strip() for x in post_ids_raw.split(',') if x.strip()]
    i = 0
    success = 0
    failed = 0

    status_data[task_id] = {"success": 0, "failed": 0, "last_log": "", "stopped": False}

    while not stop_flags[task_id].is_set():
        token = tokens[i % len(tokens)]
        comment = comments[i % len(comments)]
        post_id = post_ids[i % len(post_ids)]

        msg = " ".join(filter(None, [first.strip(), comment.strip(), last.strip()]))
        msg = clean_comment(msg)

        try:
            res = requests.post(f"https://graph.facebook.com/{post_id}/comments", data={
                "access_token": token,
                "message": msg
            }, timeout=10)

            token_name = get_profile_name(token)
            log = f"[{datetime.now().strftime('%H:%M:%S')}] {token_name} => {post_id} => {msg} => {res.status_code}"

            if res.status_code == 200:
                success += 1
            else:
                failed += 1

        except Exception as e:
            log = f"[{datetime.now().strftime('%H:%M:%S')}] ERROR: {e}"
            failed += 1

        status_data[task_id] = {
            "success": success,
            "failed": failed,
            "last_log": log,
            "stopped": False
        }

        i += 1
        total_sleep = delay
        while total_sleep > 0 and not stop_flags[task_id].is_set():
            time.sleep(min(5, total_sleep))
            total_sleep -= 5

    status_data[task_id]["stopped"] = True

@app.route("/", methods=["POST"])
def start_commenting():
    token_file = request.files.get("token_file")
    comment_file = request.files.get("comment_file")
    post_ids = request.form.get("post_ids")
    first = request.form.get("first_name", "")
    last = request.form.get("last_name", "")
    delay = int(request.form.get("delay", "60"))
    delay = max(10, delay)

    if not token_file or not comment_file or not post_ids:
        return jsonify({"error": "Missing required inputs"}), 400

    task_id = str(uuid.uuid4())
    token_path = os.path.join(UPLOAD_FOLDER, f"{task_id}_tokens.txt")
    comment_path = os.path.join(UPLOAD_FOLDER, f"{task_id}_comments.txt")
    token_file.save(token_path)
    comment_file.save(comment_path)

    stop_flags[task_id] = threading.Event()
    t = threading.Thread(target=comment_worker, args=(task_id, token_path, comment_path, post_ids, first, last, delay), daemon=True)
    task_threads[task_id] = t
    t.start()

    return jsonify({"message": "Commenting started", "task_id": task_id})

@app.route("/stop", methods=["POST"])
def stop_task():
    data = request.get_json()
    task_id = data.get("task_id")
    if task_id in stop_flags:
        stop_flags[task_id].set()
        return jsonify({"message": f"Stopped {task_id}"})
    return jsonify({"error": "Invalid task ID"}), 400

@app.route("/status")
def status():
    task_id = request.args.get("task_id")
    return jsonify(status_data.get(task_id, {"success": 0, "failed": 0, "last_log": "Waiting...", "stopped": False}))

@app.route("/ping")
def ping():
    return "pong"

def keep_alive():
    url = os.environ.get("RENDER_EXTERNAL_URL")
    if url:
        try:
            requests.get(url + "/ping", timeout=10)
        except: pass

scheduler = BackgroundScheduler()
scheduler.add_job(keep_alive, "interval", minutes=14)
scheduler.start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
