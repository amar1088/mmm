// Updated script.js matching the backend expectations

let currentTaskId = null;

function startCommenting() {
  console.log("🚀 Start button clicked");
  const form = document.getElementById('commentForm');
  const formData = new FormData(form);

  for (let [key, value] of formData.entries()) {
    console.log(`🟡 ${key}:`, value);
  }

  fetch('/', {
    method: 'POST',
    body: formData
  })
    .then(res => res.json())
    .then(data => {
      console.log("🟢 Response from server:", data);
      if (data.task_id) {
        currentTaskId = data.task_id;
        document.getElementById('stop_task_id').value = currentTaskId;
        document.getElementById('status').innerHTML = `
          <p><b>Status:</b> ${data.message}</p>
          <p><b>Task ID:</b> ${currentTaskId}</p>
        `;
        pollStatus();
      } else {
        document.getElementById('status').innerHTML = `<p><b>Error:</b> ${data.error || 'Unknown error'}</p>`;
      }
    })
    .catch(error => {
      console.error("❌ Fetch failed:", error);
      document.getElementById('status').innerHTML = `<p><b>Error:</b> ${error.message}</p>`;
    });
}

function stopCommenting() {
  const taskId = document.getElementById('stop_task_id').value.trim();
  if (!taskId) return alert("Please enter a valid Task ID to stop.");

  fetch('/stop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskId })
  })
    .then(res => res.json())
    .then(data => {
      document.getElementById('status').innerHTML = `<p><b>${data.message}</b></p>`;
    })
    .catch(error => {
      console.error("❌ Stop fetch failed:", error);
    });
}

function pollStatus() {
  if (!currentTaskId) return;
  fetch(`/status?task_id=${currentTaskId}`)
    .then(res => res.json())
    .then(data => {
      const l = data.latest || {};
      const s = data.summary || {};
      document.getElementById('status').innerHTML += `
        <p><strong>Success:</strong> ${s.success || 0} | <strong>Failed:</strong> ${s.failed || 0}</p>
        <p><strong>Post ID:</strong> ${l.post_id || '-'}</p>
        <p><strong>Comment:</strong> ${l.full_comment || '-'}</p>
        <p><strong>Time:</strong> ${l.timestamp || '-'}</p>
        <hr>
      `;
      setTimeout(pollStatus, 5000);
    })
    .catch(err => console.error("Polling error:", err));
}

