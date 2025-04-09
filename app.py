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
summaries = {}
running_tasks = {}

def read_file_lines(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def clean_comment(text):
    return text.strip().replace('<b>', '').replace('</b>', '').replace('>/<B>', '')

def comment_task(task_id, post_ids, first, last, comments, tokens, delay):
    summaries[task_id] = {'success': 0, 'failed': 0}
    running_tasks[task_id] = True
    i = 0
    while running_tasks.get(task_id):
        try:
            comment = comments[i % len(comments)].strip()
            token = tokens[i % len(tokens)].strip()
            post_id = post_ids[i % len(post_ids)].strip()

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
            if res.status_code == 200:
                summaries[task_id]['success'] += 1
            else:
                summaries[task_id]['failed'] += 1
        except:
            summaries[task_id]['failed'] += 1

        i += 1
        for _ in range(delay):
            if not running_tasks.get(task_id):
                break
            time.sleep(1)

@app.route("/", methods=["GET"])
def index():
    return "Use the form to submit a POST request."

@app.route("/", methods=["POST"])
def start_commenting():
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

    post_id_list = [p.strip() for p in post_ids.split(',') if p.strip()]
    comments = read_file_lines(comment_path)
    tokens = read_file_lines(token_path)

    thread = threading.Thread(
        target=comment_task,
        args=(task_id, post_id_list, first_name, last_name, comments, tokens, delay),
        daemon=True
    )
    thread.start()
    task_threads[task_id] = thread

    return jsonify({"message": "Commenting started", "task_id": task_id})

@app.route('/stop', methods=['POST'])
def stop():
    data = request.get_json()
    task_id = data.get("task_id")
    if not task_id:
        return jsonify({"error": "Task ID is required"}), 400

    if task_id in running_tasks:
        running_tasks[task_id] = False
        return jsonify({"message": f"Stopped task {task_id}"})
    return jsonify({"error": "Invalid task ID"}), 400

@app.route('/status')
def status():
    task_id = request.args.get("task_id")
    if not task_id:
        return jsonify({"error": "Task ID is required"}), 400
    return jsonify({
        "summary": summaries.get(task_id, {"success": 0, "failed": 0}),
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
