from flask import Flask, request, jsonify, render_template
import os, threading, time, requests, uuid
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

status_data = {}
task_threads = {}
stop_flags = {}
running_tasks = {}
summaries = {}

def read_file_lines(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def clean_comment(text):
    return text.strip().replace('<b>', '').replace('</b>', '').replace('>/<B>', '')

# MAIN COMMENTING LOGIC
def comment_task(task_id, post_ids, first, last, comments, tokens, delay):
    i = 0
    total_posts = len(post_ids)
    total_comments = len(comments)
    total_tokens = len(tokens)

    while running_tasks.get(task_id):
        if stop_flags[task_id].is_set():
            print(f"[{task_id}] Stop flag received. Stopping task.")
            break

        try:
            post_id = post_ids[i % total_posts].strip()
            comment = comments[i % total_comments].strip()
            token = tokens[i % total_tokens].strip()

            # Construct comment
            name_parts = []
            if first.strip():
                name_parts.append(first.strip())
            name_parts.append(comment)
            if last.strip():
                name_parts.append(last.strip())
            full_comment = clean_comment(" ".join(name_parts))

            url = f"https://graph.facebook.com/{post_id}/comments"
            params = {"access_token": token, "message": full_comment}

            res = requests.post(url, data=params, timeout=10)

            # Logging this attempt
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = {
                "post_id": post_id,
                "comment": full_comment,
                "time": timestamp
            }
            status_data.setdefault(task_id, {"logs": []})["logs"].append(log_entry)
            status_data[task_id]["full_comment"] = full_comment
            status_data[task_id]["post_id"] = post_id
            status_data[task_id]["timestamp"] = timestamp

            if res.status_code == 200:
                summaries[task_id]['success'] += 1
                print(f"[{task_id}] ✅ Comment success: {full_comment}")
            else:
                summaries[task_id]['failed'] += 1
                print(f"[{task_id}] ❌ Comment failed [{res.status_code}]: {res.text}")
                # But don't remove the token

        except Exception as e:
            summaries[task_id]['failed'] += 1
            print(f"[{task_id}] ⚠️ Exception: {str(e)}")

        i += 1
        time.sleep(delay)

# WRAPPER FOR THREADING
def comment_thread(task_id, token_path, comment_path, post_ids_raw, first, last, delay):
    comments = read_file_lines(comment_path)
    tokens = read_file_lines(token_path)
    post_ids = [p.strip() for p in post_ids_raw.split(',') if p.strip()]

    running_tasks[task_id] = True
    summaries[task_id] = {'success': 0, 'failed': 0}

    try:
        comment_task(task_id, post_ids, first, last, comments, tokens, delay)
    finally:
        running_tasks[task_id] = False
        print(f"[{task_id}] Task completed.")

@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'POST':
        token_file = request.files.get('token_file')
        comment_file = request.files.get('comment_file')
        post_ids = request.form.get('post_ids')
        first_name = request.form.get('first_name', '')
        last_name = request.form.get('last_name', '')

        try:
            delay = max(10, int(request.form.get('delay', 60)))
        except:
            delay = 60

        if not token_file or not comment_file or not post_ids:
            return jsonify({"error": "Missing required fields."}), 400

        task_id = str(uuid.uuid4())
        token_path = os.path.join(UPLOAD_FOLDER, f'{task_id}_tokens.txt')
        comment_path = os.path.join(UPLOAD_FOLDER, f'{task_id}_comments.txt')
        token_file.save(token_path)
        comment_file.save(comment_path)

        stop_flags[task_id] = threading.Event()
        thread = threading.Thread(
            target=comment_thread,
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
        running_tasks[task_id] = False
        del task_threads[task_id]
        del stop_flags[task_id]
        return jsonify({"message": f"Stopped task {task_id}"})
    return jsonify({"error": "Invalid task ID"}), 400

@app.route('/status')
def status():
    task_id = request.args.get("task_id")
    if not task_id:
        return jsonify({"error": "Missing task_id"}), 400

    summary = summaries.get(task_id, {"success": 0, "failed": 0})
    logs = status_data.get(task_id, {}).get("logs", [])
    return jsonify({
        "success": summary["success"],
        "failed": summary["failed"],
        "running": running_tasks.get(task_id, False),
        "logs": logs
    })

@app.route('/ping')
def ping():
    return "pong"

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
