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

      document.getElementById('status').innerHTML = `
        <p><strong>Status:</strong> Task Running</p>
        <p><strong>Success:</strong> ${s.success || 0} | <strong>Failed:</strong> ${s.failed || 0}</p>
        <p><strong>Post ID:</strong> ${l.post_id || '-'}</p>
        <p><strong>Comment:</strong> ${l.full_comment || '-'}</p>
        <p><strong>Time:</strong> ${l.timestamp || '-'}</p>
        <p><strong>Task ID:</strong> ${currentTaskId}</p>
        <hr>
      `;

      // Real-time full log display
      const logsDiv = document.getElementById('logContent');
      logsDiv.innerHTML = "";
      if (data.logs && data.logs.length > 0) {
        data.logs.forEach(log => {
          logsDiv.innerHTML += `
            <hr>
            <p><strong>Success:</strong> ${s.success || 0} | <strong>Failed:</strong> ${s.failed || 0}</p>
            <p><strong>Post ID:</strong> ${log.post_id || '-'}</p>
            <p><strong>Comment:</strong> ${log.comment || '-'}</p>
            <p><strong>Time:</strong> ${log.time || '-'}</p>
          `;
        });
      } else {
        logsDiv.innerHTML = "<p>No logs yet...</p>";
      }

      setTimeout(pollStatus, 5000);
    })
    .catch(err => console.error("Polling error:", err));
}
