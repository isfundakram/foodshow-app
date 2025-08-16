async function loadQueue() {
  const res = await fetch('/api/queue');
  const data = await res.json();
  return data.items || [];
}

async function markPrinted(queue_id) {
  const fd = new FormData();
  fd.append('queue_id', queue_id);
  await fetch('/api/queue/mark_printed', { method: 'POST', body: fd });
}

function renderQueue(items) {
  const tbody = document.querySelector('#queue_table tbody');
  tbody.innerHTML = '';
  items.forEach(item => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${item.customer_code || ''}</td>
      <td>${item.customer_name}</td>
      <td>${item.attendee_name}</td>
      <td>
        <button class="badge-btn" data-id="${item.queue_id}">Open Badge</button>
        <button class="queue-btn" data-id="${item.queue_id}">Mark Printed</button>
      </td>
    `;
    tr.querySelector('.badge-btn').addEventListener('click', () => {
      window.open(`/badge/${item.queue_id}`, '_blank');
    });
    tr.querySelector('.queue-btn').addEventListener('click', async () => {
      await markPrinted(item.queue_id);
      refresh();
    });
    tbody.appendChild(tr);
  });
}

async function refresh() {
  const items = await loadQueue();
  renderQueue(items);
}

refresh();
setInterval(refresh, 3000);