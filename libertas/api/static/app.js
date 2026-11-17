// Writes carry this header: browsers cannot attach it cross-site without a CORS preflight the API never grants.
const CLIENT = { 'X-Libertas-Client': 'forum' };
// Libertas live page. Captured content is only ever inserted with textContent, never as HTML.
const $ = (id) => document.getElementById(id);
function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = String(text);
  return e;
}
function row(cells, head = false) {
  const tr = el('tr');
  for (const c of cells) tr.append(el(head ? 'th' : 'td', null, c));
  return tr;
}

async function refreshStatus() {
  const s = await (await fetch('/api/status')).json();
  $('mode').textContent = s.mode.toUpperCase() + (s.simulation ? ' · SIMULATION' : '');
  $('kill').textContent = s.kill_engaged ? 'KILL SWITCH ENGAGED' : 'collecting';
  $('kill').className = 'pill ' + (s.kill_engaged ? 'red' : 'green');
  $('ttd').textContent = s.ttd
    ? `time-to-detect median ${s.ttd.median_s}s · p95 ${s.ttd.p95_s}s (n=${s.ttd.n})`
    : 'time-to-detect: waiting for a fresh post';
  $('counts').textContent = `items ${s.counts.items} · captures ${s.counts.captures} · alerts ${s.counts.alerts}` +
    ` · audit ${s.audit.ok ? 'intact' : 'BROKEN'} (${s.audit.entries_checked})`;
  const t = $('sources');
  t.replaceChildren(row(['Source', 'State', 'Last pulse', 'Items', 'Descriptor (Pulsus)'], true));
  for (const src of s.sources) {
    const h = src.health || {};
    const d = h.descriptor;
    const desc = d ? `${d.result} in ${d.seconds}s` +
      (d.private ? ' · private' : '') +
      (d.pow_enabled ? ` · PoW armed (effort ${d.pow_effort})` : '') +
      (d.intro_points ? ` · ${d.intro_points} intro pts` : '') : 'pending';
    t.append(row([src.name, h.state || '?', h.last_pulse_s != null ? `${h.last_pulse_s}s (${h.last_outcome})` : '—',
                  src.items, desc]));
  }
}

function alertCard(a) {
  const c = el('div', `alert sev-${a.severity}` + (a.deleted ? ' gone' : '') + (a.status === 'historical' ? ' hist' : ''));
  const title = el('div', 'title', `${a.severity} · ${a.score} · ${a.title}`);
  if (a.deleted) title.append(el('span', 'badge', 'DELETED AT SOURCE · evidence kept'));
  if (a.status === 'historical') title.append(el('span', 'badge', 'backfill'));
  c.append(title);
  c.append(el('div', 'meta', `${a.source_name} · by ${a.author || '?'} · posted ${a.posted_at || '?'} · first seen ` +
    `${a.first_seen} · detection lag ${a.detection_lag_s ?? '?'} s`));
  if (a.deep) {
    c.append(el('div', 'meta', `DEEP LANE: ${a.deep.severity} ${a.deep.score} · authenticity ${a.deep.authenticity}` +
      (a.deep.actor ? ` · actor ${a.deep.actor}` : '') +
      (a.deep.latency_s != null ? ` · confirmed ${a.deep.latency_s}s after the fast alert` : '') +
      (a.fast ? ` · fast lane said ${a.fast.severity} ${a.fast.score}` : '')));
    const dl = el('ul');
    for (const r of (a.deep.reasons || []).slice(0, 7)) dl.append(el('li', null, r));
    c.append(dl);
  } else {
    c.append(el('div', 'meta', 'PROVISIONAL (fast lane only): deep lane pending'));
  }
  const ul = el('ul');
  for (const r of (a.reasons || []).slice(0, 4)) ul.append(el('li', null, 'fast: ' + r));
  c.append(ul);
  if (a.factors) {
    const f = a.factors;
    c.append(el('div', 'meta', `factors: sector ${f.sector} · sensitivity ${f.sensitivity} · scale ${f.scale} · ` +
      `india ${f.india_relevance} · credibility ${f.credibility} · category ${f.category}`));
  }
  c.append(el('div', 'meta', `evidence: capture sha256 ${a.first_capture_sha || '—'}`));
  const btn = el('button', null, 'Build evidence pack');
  const out = el('span', 'meta');
  btn.addEventListener('click', async () => {
    btn.disabled = true;
    out.textContent = ' sealing, timestamping and signing…';
    try {
      const r = await fetch(`/api/items/${a.item_id}/evidence`, { method: 'POST', headers: CLIENT });
      const p = await r.json();
      if (!r.ok) throw new Error(p.detail || r.status);
      out.textContent = ` ${p.pack_id}: ${p.captures} captures, ${p.timestamped}/${p.batches} batches timestamped `;
      const link = el('a', null, 'download ZIP');
      link.href = p.download;
      link.setAttribute('download', `${p.pack_id}.zip`);
      out.append(link);
      logEvent(`evidence pack ${p.pack_id} built (manifest ${p.manifest_sha256.slice(0, 16)}…)`);
    } catch (e) {
      out.textContent = ` failed: ${e.message}`;
    } finally {
      btn.disabled = false;
    }
  });
  const row = el('div', 'meta');
  row.append(btn, out);
  c.append(row);
  return c;
}

async function loadAlerts() {
  const list = await (await fetch('/api/alerts?limit=60')).json();
  $('alerts').replaceChildren(...list.map(alertCard));
}

function logEvent(text) {
  const box = $('events');
  box.prepend(el('div', null, `${new Date().toLocaleTimeString()}  ${text}`));
  while (box.childNodes.length > 80) box.lastChild.remove();
}

function connect() {
  const ws = new WebSocket(`ws://${location.host}/ws`);
  ws.onmessage = (m) => {
    const e = JSON.parse(m.data);
    if (e.type === 'alert_new' || e.type === 'alert_updated') {
      loadAlerts();
      logEvent(`${e.type}: ${e.alert.severity} ${e.alert.title}`);
    } else if (e.type === 'item_gone') {
      loadAlerts();
      logEvent(`item ${e.item_id} gone (${e.how}); lived ${e.lifetime_s ?? '?'} s`);
    } else if (e.type === 'descriptor') {
      logEvent(`pulsus ${e.source_id}: ${e.observation.result} in ${e.observation.seconds}s`);
    } else if (e.type === 'kill_switch') {
      logEvent(`kill switch ${e.engaged ? 'ENGAGED' : 'released'}`);
      refreshStatus();
    } else if (e.type === 'deep_pass') {
      logEvent(`deep lane: ${e.updated}/${e.items} alerts confirmed in ${e.seconds}s · ${e.actors} actors · ${e.links} links`);
    } else if (e.type === 'item_edited') {
      logEvent(`item ${e.item_id} edited at source (new version captured)`);
    }
  };
  ws.onclose = () => setTimeout(connect, 2000);
}

$('killbtn').onclick = () => fetch('/api/kill', { method: 'POST', headers: { ...CLIENT, 'content-type': 'application/json' },
  body: JSON.stringify({ reason: 'operator pressed the kill switch' }) }).then(refreshStatus);
$('resumebtn').onclick = () => fetch('/api/resume', { method: 'POST', headers: CLIENT }).then(refreshStatus);
refreshStatus();
loadAlerts();
connect();
setInterval(refreshStatus, 5000);
