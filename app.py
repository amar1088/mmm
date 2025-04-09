from flask import Flask, request, jsonify
import threading
import uuid
import time
import requests
import random

app = Flask(__name__)

running_tasks = {}
summaries = {}
logs = {}

def clean_comment(text):
    return text.strip().replace('<b>', '').replace('</b>', '').replace('>/<B>', '')

def comment_task(task_id, post_ids, first, last, comments, tokens, delay):
    summaries[task_id] = {'success': 0, 'failed': 0}
    logs[task_id] = []
    
    random.shuffle(tokens)  # Randomize token order once
    i = 0

    while running_tasks.get(task_id) and tokens:
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
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')

            if res.status_code == 200:
                summaries[task_id]['success'] += 1
                logs[task_id].append(f"[{timestamp}] ✅ Commented on {post_id}")
                i += 1
            else:
                error_msg = res.text
                logs[task_id].append(f"[{timestamp}] ❌ Failed on {post_id}: {error_msg}")
                summaries[task_id]['failed'] += 1

                # If token is invalid, remove it from list
                if "OAuthException" in error_msg or "Error validating access token" in error_msg:
                    logs[task_id].append(f"[{timestamp}] ⛔ Removing invalid token.")
                    tokens.pop(i % len(tokens))  # Remove invalid token
                else:
                    i += 1  # Move forward if error not token-related

        except Exception as e:
            summaries[task_id]['failed'] += 1
            logs[task_id].append(f"[ERROR] {str(e)}")
            i += 1

        time.sleep(delay)

    logs[task_id].append("== Task stopped or no valid tokens left ==")

@app.route('/start', methods=['POST'])
def start():
    try:
        post_ids = request.files['posts'].read().decode().splitlines()
        comments = request.files['comments'].read().decode().splitlines()
        tokens = request.files['tokens'].read().decode().splitlines()
        first = request.form.get('first', '')
        last = request.form.get('last', '')
        delay = int(request.form.get('delay', '5'))
        task_id = str(uuid.uuid4())
        running_tasks[task_id] = True
        thread = threading.Thread(target=comment_task, args=(task_id, post_ids, first, last, comments, tokens, delay))
        thread.start()
        return jsonify({'task_id': task_id})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/stop', methods=['POST'])
def stop():
    task_id = request.form.get('task_id')
    if task_id in running_tasks:
        running_tasks[task_id] = False
        return 'Task stopped successfully.'
    return 'Invalid Task ID.'

@app.route('/status/<task_id>')
def status(task_id):
    if task_id not in summaries:
        return jsonify({'status': 'Not Found'})
    summary = summaries[task_id]
    is_running = running_tasks.get(task_id, False)
    return jsonify({
        'status': 'Task Running' if is_running else 'Stopped',
        'success': summary['success'],
        'failed': summary['failed'],
        'log': logs.get(task_id, [])[-10:],
        'task_id': task_id
    })

if __name__ == '__main__':
    import os
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
