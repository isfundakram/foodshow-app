const tbody = document.querySelector('#walkin_table tbody');

function addRowLocal(wi) {
  const tr = document.createElement('tr');
  tr.innerHTML = `
    <td>${wi.walkin_type}</td>
    <td>${wi.customer_name}</td>
    <td>${wi.attendee_name}</td>
    <td><button class="badge-btn">Print</button></td>
  `;
  tr.querySelector('.badge-btn').addEventListener('click', () => {
    window.open(`/badge/${wi.queue_id}`, '_blank');
  });
  tbody.prepend(tr);
}

async function submitWalkin(e) {
  e.preventDefault();
  const form = e.target;
  const fd = new FormData(form);
  fd.append('auto_queue', 'true');
  const res = await fetch('/api/walkins', { method: 'POST', body: fd });
  const j = await res.json();
  if (j.ok) {
    const wi = {
      walkin_id: j.walkin_id,
      queue_id: j.queue_id,
      walkin_type: fd.get('walkin_type'),
      customer_name: fd.get('customer_name'),
      attendee_name: fd.get('attendee_name')
    };
    addRowLocal(wi);
    form.reset();
  } else {
    alert('Failed to add walk-in');
  }
}

document.getElementById('walkin_form').addEventListener('submit', submitWalkin);