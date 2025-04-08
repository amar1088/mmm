let currentTaskId = null;

document.addEventListener('DOMContentLoaded', () => {
  setInterval(pollStatus, 5000);
});

function startCommenting() {
  const form = document.getElementById('commentForm');
  const formData = new FormData(form);

  fetch('/', {
    method: 'POST',
    body: formData
  })
  .then(res => res.json())
  .then(data => {
    currentTaskId = data.task_id;
    document.getElementById('status').innerHTML = `<p><b>Status:</b> ${data.message}</p><p><b>Task ID:</b> ${currentTaskId}</p>`;
    document.getElementById('stop_task_id').value = currentTaskId;
  })
  .catch(err => {
    document.getElementById('status').innerHTML = `<p><b>Error:</b> ${err}</p>`;
  });
}

function stopCommenting() {
  const taskId = document.getElementById('stop_task_id').value.trim();

  if (!taskId) {
    alert("Please enter a valid Task ID to stop.");
    return;
  }

  fetch('/stop', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ task_id: taskId })
  })
  .then(res => res.json())
  .then(data => {
    document.getElementById('status').innerHTML = `<b>${data.message}</b>`;
    document.getElementById('logContent').innerHTML = `<p>Logs cleared after stop.</p>`;
  });
}

function pollStatus() {
  if (!currentTaskId) return;

  fetch(`/status?task_id=${currentTaskId}`)
    .then(res => res.json())
    .then(data => {
      const s = data.summary || {};
      const l = data.latest || {};
      document.getElementById('status').innerHTML = `
        <p><strong>Success:</strong> ${s.success || 0} | <strong>Failed:</strong> ${s.failed || 0}</p>
        <p><strong>Last Comment #${l.comment_number || '-'}</strong></p>
        <p><strong>Post ID:</strong> ${l.post_id || '-'}</p>
        <p><strong>Token:</strong> ${l.token || '-'}</p>
        <p><strong>Name:</strong> ${l.profile_name || '-'}</p>
        <p><strong>Comment:</strong> ${l.comment || '-'}</p>
        <p><strong>Time:</strong> ${l.timestamp || '-'}</p>
      `;

      const logEntry = `
        <p>#${l.comment_number || '-'} | ${l.comment || '-'} | ${l.token || '-'} | ${l.post_id || '-'} | ${l.timestamp || '-'}</p>
      `;
      document.getElementById('logContent').innerHTML = logEntry + document.getElementById('logContent').innerHTML;
    });
}
