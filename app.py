from flask import Flask, request, jsonify, render_template, send_file
import os, threading, time, random, requests, uuid, json
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
LOG_FOLDER = 'logs'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(LOG_FOLDER, exist_ok=True)

status_data = {}
task_threads = {}
stop_flags = {}
token_last_used = {}

APP_ID = os.getenv("FB_APP_ID")
APP_SECRET = os.getenv("FB_APP_SECRET")

def read_file_lines(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def log_error(task_id, message):
    print(f"[{task_id}] ERROR: {message}")

def get_profile_name(token):
    try:
        res = requests.get(f"https://graph.facebook.com/me?access_token={token}", timeout=5)
        return res.json().get("name", "Unknown")
    except Exception as e:
        return "Unknown"

def validate_token(token):
    try:
        app_token = f"{APP_ID}|{APP_SECRET}"
        res = requests.get(f"https://graph.facebook.com/debug_token",
                           params={"input_token": token, "access_token": app_token})
        data = res.json()
        return data.get("data", {}).get("is_valid", False)
    except Exception as e:
        return False

def comment_worker(task_id, token_path, comment_path, post_ids, first_name, last_name, delay):
    stop_flag = stop_flags[task_id]
    status_data[task_id] = {"summary": {"success": 0, "failed": 0}, "latest": {}, "log": []}
    tokens = read_file_lines(token_path)
    comments = read_file_lines(comment_path)
    post_ids = [x.strip() for x in post_ids.split(",") if x.strip()]
    valid_tokens = [t for t in tokens if validate_token(t)]

    if not valid_tokens or not comments or not post_ids:
        log_error(task_id, "No valid tokens, comments, or post IDs.")
        return

    comment_num = 0
    while not stop_flag.is_set():
        token = valid_tokens[comment_num % len(valid_tokens)]
        now = time.time()
        last_used = token_last_used.get(token, 0)

        # Cooldown check: 60 seconds per token
        if now - last_used < 60:
            time.sleep(5)
            continue
        token_last_used[token] = now

        comment = comments[comment_num % len(comments)]
        post_id = post_ids[comment_num % len(post_ids)]
        profile_name = get_profile_name(token)

        name_parts = []
        if first_name.strip():
            name_parts.append(first_name.strip())
        name_parts.append(comment.strip())
        if last_name.strip():
            name_parts.append(last_name.strip())
        full_comment = " ".join(name_parts)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        status = "Failed"

        try:
            res = requests.post(f"https://graph.facebook.com/{post_id}/comments", data={
                "message": full_comment,
                "access_token": token
            })
            result = res.json()
            status = "Success" if "id" in result else "Failed"
        except Exception as e:
            log_error(task_id, str(e))

        summary = status_data[task_id]["summary"]
        summary["success" if status == "Success" else "failed"] += 1

        latest = {
            "comment_number": comment_num + 1,
            "comment": comment,
            "full_comment": full_comment,
            "token": f"Token #{(comment_num % len(valid_tokens)) + 1}",
            "post_id": post_id,
            "profile_name": profile_name,
            "timestamp": timestamp,
            "status": status
        }
        status_data[task_id]["latest"] = latest
        status_data[task_id]["log"].append(latest)

        comment_num += 1
        time.sleep(delay)


    # Save log to disk after task is stopped
    with open(os.path.join(LOG_FOLDER, f"{task_id}.json"), "w") as f:
        json.dump(status_data[task_id], f, indent=2)

    # Cleanup memory after 5 minutes
    def cleanup():
        time.sleep(300)
        status_data.pop(task_id, None)
    threading.Thread(target=cleanup, daemon=True).start()

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        token_file = request.files.get('token_file')
        comment_file = request.files.get('comment_file')
        post_ids = request.form.get('post_ids')
        first_name = request.form.get('first_name', '')
        last_name = request.form.get('last_name', '')
        delay = max(60, int(request.form.get('delay', 60)))

        if not token_file or not comment_file or not post_ids:
            return jsonify({"error": "Missing required fields."}), 400

        task_id = str(uuid.uuid4())
        token_path = os.path.join(UPLOAD_FOLDER, f'{task_id}_tokens.txt')
        comment_path = os.path.join(UPLOAD_FOLDER, f'{task_id}_comments.txt')
        token_file.save(token_path)
        comment_file.save(comment_path)

        stop_flags[task_id] = threading.Event()
        thread = threading.Thread(
            target=comment_worker,
            args=(task_id, token_path, comment_path, post_ids, first_name, last_name, delay),
            daemon=True
        )
        thread.start()
        task_threads[task_id] = thread

        return jsonify({"message": "Commenting started", "task_id": task_id})
    return render_template("index.html")

@app.route('/stop', methods=['POST'])
def stop():
    data = request.get_json()
    task_id = data.get("task_id")
    if not task_id:
        return jsonify({"error": "Task ID is required"}), 400

    if task_id in task_threads:
        stop_flags[task_id].set()
        del task_threads[task_id]
        del stop_flags[task_id]
        return jsonify({"message": f"Stopped task {task_id}"})
    return jsonify({"error": "Invalid task ID"}), 400

@app.route('/status')
def status():
    task_id = request.args.get("task_id")
    if not task_id:
        return jsonify({"error": "Task ID is required"}), 400
    return jsonify(status_data.get(task_id, {
        "summary": {"success": 0, "failed": 0},
        "latest": {}
    }))

@app.route('/export-log/<task_id>')
def export_log(task_id):
    filepath = os.path.join(LOG_FOLDER, f"{task_id}.json")
    if os.path.exists(filepath):
        return send_file(filepath, as_attachment=True)
    return jsonify({"error": "Log not found"}), 404

@app.route('/ping')
def ping():
    return "pong"

# Keep-alive pinger
def keep_alive():
    try:
        url = os.environ.get("RENDER_EXTERNAL_URL")
        if url:
            requests.get(url + "/ping", timeout=10)
    except:
        pass

scheduler = BackgroundScheduler()
scheduler.add_job(keep_alive, "interval", minutes=14)
scheduler.start()

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
