async function fetchRegistered() {
  const res = await fetch('/api/registered');
  const data = await res.json();
  return data.items || [];
}

function rowMatchesFilters(row, filters) {
  return (!filters.customer_code || row.customer_code.toLowerCase().includes(filters.customer_code)) &&
         (!filters.customer_name || row.customer_name.toLowerCase().includes(filters.customer_name)) &&
         (!filters.attendee_name || row.attendee_name.toLowerCase().includes(filters.attendee_name)) &&
         (!filters.registration_id || row.registration_id.toLowerCase().includes(filters.registration_id));
}

function currentFilters() {
  return {
    customer_code: document.getElementById('f_customer_code').value.trim().toLowerCase(),
    customer_name: document.getElementById('f_customer_name').value.trim().toLowerCase(),
    attendee_name: document.getElementById('f_attendee_name').value.trim().toLowerCase(),
    registration_id: document.getElementById('f_registration_id').value.trim().toLowerCase(),
  };
}

async function markHere(registration_id, btn) {
  const fd = new FormData();
  fd.append('registration_id', registration_id);
  const res = await fetch('/api/attendance', { method: 'POST', body: fd });
  if (res.ok) {
    btn.classList.add('active');
    btn.disabled = true;
  }
}

async function addToQueueAndOpenBadge(rec) {
  const fd = new FormData();
  fd.append('source', 'registered');
  fd.append('registration_id', rec.registration_id);
  fd.append('walkin_id', '');
  fd.append('customer_code', rec.customer_code);
  fd.append('customer_name', rec.customer_name);
  fd.append('attendee_name', rec.attendee_name);
  const r = await fetch('/api/queue/add', { method: 'POST', body: fd });
  const j = await r.json();
  if (j.queue_id) {
    window.open(`/badge/${j.queue_id}`, '_blank');
  }
}

function renderRows(items) {
  const tbody = document.querySelector('#reg_table tbody');
  tbody.innerHTML = '';
  const filters = currentFilters();
  items.filter(r => rowMatchesFilters(r, filters)).forEach(rec => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td>${rec.customer_code}</td>
      <td>${rec.customer_name}</td>
      <td>${rec.attendee_name}</td>
      <td>${rec.registration_id}</td>
      <td></td>
      <td></td>
    `;
    const hereCell = tr.children[4];
    const printCell = tr.children[5];

    const hereBtn = document.createElement('button');
    hereBtn.className = 'here-btn';
    hereBtn.textContent = 'Here';
    if (rec.here === 'true') { hereBtn.classList.add('active'); hereBtn.disabled = true; }
    hereBtn.addEventListener('click', () => markHere(rec.registration_id, hereBtn));

    const printBtn = document.createElement('button');
    printBtn.className = 'badge-btn';
    printBtn.textContent = 'Print';
    printBtn.addEventListener('click', () => addToQueueAndOpenBadge(rec));

    hereCell.appendChild(hereBtn);
    printCell.appendChild(printBtn);
    tbody.appendChild(tr);
  });
}

async function bootstrap() {
  const items = await fetchRegistered();
  const inputs = ['f_customer_code','f_customer_name','f_attendee_name','f_registration_id'];
  inputs.forEach(id => document.getElementById(id).addEventListener('input', () => renderRows(items)));
  document.getElementById('clear_filters').addEventListener('click', () => {
    inputs.forEach(id => document.getElementById(id).value = '');
    renderRows(items);
  });
  renderRows(items);
}

bootstrap();