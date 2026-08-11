"""CSS + JS for the dashboard page, kept out of build_dashboard.py.

These are inlined verbatim into the generated HTML (no build step, no CDN), so
they are plain strings rather than f-strings — braces stay unescaped and the JS
below reads like JS. build_dashboard.py substitutes __TOKEN__ placeholders in
PAGE only; nothing here is formatted.

Stage palette (validated with the data-viz six checks against the #161922 panel
surface, dark mode):
  * Applied -> Offer is an ORDINAL ramp — one blue hue, monotone lightness,
    adjacent dL >= 0.06, dim end 2.29:1 on surface. Funnel position is an order,
    not an identity, so it takes a ramp rather than categorical hues.
  * Accepted / Rejected are reserved STATUS colors (good #0ca30c 5.23:1,
    critical #d03b3b 3.65:1). They fail a categorical CVD check against each
    other by design, which is why every node and legend entry is always drawn
    with its name and count — color never carries meaning alone here.
  * Not applied / No response are neutrals, deliberately below the chroma floor
    so they read as absence rather than as a series.
"""

CSS = """
  :root {
    color-scheme: dark;
    --bg: #0f1115; --panel: #161922; --panel-2: #12151c; --line: #23262d;
    --line-2: #2c313c; --ink: #e6e8ec; --ink-2: #cfd3da; --ink-3: #9aa0aa;
    --ink-4: #6b7280; --accent: #2563eb;
    --st-none: #606b82; --st-applied: #1e4fa8; --st-screening: #2f6fdd;
    --st-interview: #4f8ef0; --st-offer: #7fb0f7; --st-accepted: #0ca30c;
    --st-rejected: #d03b3b; --st-ghosted: #6b7280;
  }
  * { box-sizing: border-box; }
  body { font-family: -apple-system, Segoe UI, Roboto, sans-serif; margin: 0;
         background: var(--bg); color: var(--ink); }
  header { padding: 16px 28px 10px; border-bottom: 1px solid var(--line);
           position: sticky; top: 0; background: #0f1115ee; backdrop-filter: blur(8px); z-index: 30; }
  h1 { margin: 0 0 8px; font-size: 18px; }
  .stats { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
  .stat { background: var(--panel); border: 1px solid var(--line); border-radius: 8px;
          padding: 5px 11px; font-size: 13px; }
  .stat b { font-size: 15px; }
  .stat.clickable { cursor: pointer; user-select: none; }
  .stat.clickable:hover { border-color: #3a4150; }
  .stat.clickable.open { background: #1d2433; border-color: var(--accent); }

  /* --- stage strip ------------------------------------------------------ */
  .stages { display: flex; gap: 6px; flex-wrap: wrap; margin-bottom: 10px; }
  .stg { display: flex; align-items: center; gap: 7px; cursor: pointer; user-select: none;
         background: var(--panel); border: 1px solid var(--line); border-radius: 9px;
         padding: 6px 11px 6px 9px; font-size: 12px; color: var(--ink-2); }
  .stg:hover { border-color: #3a4150; }
  .stg.on { border-color: currentColor; background: #1b1f2a; }
  .stg .dot { width: 9px; height: 9px; border-radius: 50%; background: currentColor;
              flex-shrink: 0; }
  .stg .n { font-weight: 700; font-size: 13px; color: var(--ink); }
  .stg .lbl { color: var(--ink-2); }

  /* --- toolbar ---------------------------------------------------------- */
  .tools { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
  #q { flex: 1; min-width: 200px; background: var(--panel); border: 1px solid var(--line-2);
       color: var(--ink); border-radius: 8px; padding: 9px 12px; font-size: 14px; }
  .tbtn { background: #1e222b; border: 1px solid var(--line-2); color: var(--ink-2);
          border-radius: 8px; padding: 8px 12px; font-size: 13px; cursor: pointer; }
  .tbtn:hover { border-color: #3a4150; }
  .tbtn.on { background: var(--accent); color: #fff; border-color: var(--accent); }
  #shown { color: var(--ink-3); font-size: 13px; margin-left: 2px; }

  /* --- dropdown filter bar ---------------------------------------------- */
  .filterbar { display: flex; flex-wrap: wrap; gap: 7px; padding: 10px 28px;
               border-bottom: 1px solid var(--line); background: var(--panel-2);
               position: sticky; top: 0; z-index: 20; }
  .fdd { position: relative; }
  .fddbtn { background: var(--panel); border: 1px solid var(--line-2); color: var(--ink-2);
            border-radius: 8px; padding: 7px 11px; font-size: 12.5px; cursor: pointer;
            display: flex; align-items: center; gap: 6px; white-space: nowrap; }
  .fddbtn:hover { border-color: #3a4150; }
  .fdd.active .fddbtn { border-color: var(--accent); color: #fff; }
  .fddbtn .cnt { background: var(--accent); color: #fff; border-radius: 9px; font-size: 10px;
                 font-weight: 700; padding: 1px 6px; }
  .fddbtn .car { opacity: .5; font-size: 10px; }
  .fddmenu { position: absolute; top: calc(100% + 5px); left: 0; z-index: 40; width: 258px;
             background: #12151c; border: 1px solid var(--line-2); border-radius: 10px;
             box-shadow: 0 12px 34px #000a; padding: 8px; }
  .fddsearch { width: 100%; background: var(--panel); border: 1px solid var(--line-2);
               color: var(--ink); border-radius: 7px; padding: 7px 9px; font-size: 12.5px;
               margin-bottom: 7px; }
  .fddlist { max-height: 264px; overflow-y: auto; display: flex; flex-direction: column; gap: 1px; }
  .fddopt { display: flex; align-items: center; gap: 8px; padding: 6px 7px; border-radius: 6px;
            font-size: 12.5px; color: var(--ink-2); cursor: pointer; }
  .fddopt:hover { background: #1b1f29; }
  .fddopt input { accent-color: var(--accent); margin: 0; cursor: pointer; }
  .fddopt .fct { margin-left: auto; color: var(--ink-4); font-size: 11px; }
  .fddopt.zero { opacity: .38; }
  .fddempty { color: var(--ink-4); font-size: 12px; padding: 8px 7px; }
  .fddfoot { display: flex; justify-content: space-between; margin-top: 7px;
             border-top: 1px solid var(--line); padding-top: 7px; }
  .fddfoot button { background: none; border: none; color: #6ea8fe; font-size: 11.5px;
                    cursor: pointer; padding: 2px 4px; }
  .fddfoot button:hover { text-decoration: underline; }
  .swatch { width: 9px; height: 9px; border-radius: 50%; flex-shrink: 0; }

  /* --- pipeline panel --------------------------------------------------- */
  .pipe { margin: 18px 28px 0; background: var(--panel); border: 1px solid var(--line);
          border-radius: 12px; padding: 14px 16px 6px; max-width: 1400px; }
  .pipe-h { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
  .pipe-h h2 { margin: 0; font-size: 13px; text-transform: uppercase; letter-spacing: .6px;
               color: var(--ink-3); font-weight: 600; }
  .pipe-h .sub { color: var(--ink-4); font-size: 12px; }
  .pipe-h .tbtn { padding: 5px 10px; font-size: 12px; }
  #sankey { width: 100%; display: block; }
  .sk-node { cursor: default; }
  /* Halo so labels stay readable where they sit over a ribbon. */
  .sk-lab, .sk-val { paint-order: stroke fill; stroke: var(--panel); stroke-width: 3.5px;
                     stroke-linejoin: round; }
  .sk-lab { font-size: 11.5px; fill: var(--ink-2); }
  .sk-val { font-size: 11.5px; fill: var(--ink); font-weight: 700; }
  .sk-flow { transition: opacity .12s; }
  .pipe.dim .sk-flow { opacity: .16; }
  .sk-flow.hot { opacity: .85 !important; }
  .pipe-empty { color: var(--ink-3); font-size: 13px; padding: 14px 2px 18px; line-height: 1.55; }
  .pipe-empty b { color: var(--ink-2); }

  /* --- grid + cards ----------------------------------------------------- */
  .wrap { padding: 18px 28px 70px; max-width: 1400px; margin: 0 auto; }
  .grid { display: grid; gap: 14px; grid-template-columns: repeat(auto-fill, minmax(290px, 1fr)); }
  .card { background: var(--panel); border: 1px solid var(--line); border-radius: 12px;
          padding: 14px; display: flex; flex-direction: column; gap: 6px; }
  .card:hover { border-color: #313742; }
  .ctop { display: flex; align-items: center; gap: 8px; }
  .sc { border: 1px solid; border-radius: 6px; padding: 2px 0; width: 40px; text-align: center;
        font-weight: 700; font-size: 14px; }
  .tpill { font-size: 10px; padding: 2px 8px; border-radius: 10px; font-weight: 600; }
  .t-remote { background: #14302a; color: #5bd6ac; }
  .t-hybrid { background: #2c2a16; color: #e0c061; }
  .t-onsite { background: #1c2333; color: #8fb3ff; }
  .t-unspecified { background: #20242e; color: var(--ink-3); }
  .jt { color: var(--ink); font-size: 15px; font-weight: 600; text-decoration: none; line-height: 1.3; }
  .jt:hover { color: #6ea8fe; }
  .new { background: #18351f; color: #51d88a; font-size: 9px; font-weight: 700;
         padding: 1px 6px; border-radius: 10px; }
  .ghost { background: #33261a; color: #e0a86b; font-size: 9px; font-weight: 700;
           padding: 1px 6px; border-radius: 10px; cursor: help; }
  .cco { color: var(--ink-2); font-size: 13px; font-weight: 500; }
  .cloc { color: var(--ink-3); font-size: 12px; }
  .age { color: #8b90a0; }
  .age.stale { color: #d9a15f; }
  .sal { color: #7ec9a3; font-size: 12px; font-weight: 600; }
  .chips { display: flex; flex-wrap: wrap; gap: 5px; margin-top: 2px; }
  .chip { background: #20242e; color: #aab0bc; font-size: 10px; padding: 1px 7px; border-radius: 10px; }
  .chip.lvl { background: #2a2a40; color: #bfc4ff; text-transform: capitalize; }
  .chip.yoe { background: #33262a; color: #e0a2ac; }
  .chip.loc { background: #1c2333; color: #8fb3ff; }
  a.apply { background: var(--accent); color: #fff; text-decoration: none; font-size: 13px;
            font-weight: 600; padding: 8px 0; border-radius: 8px; text-align: center; margin-top: 4px; }
  .crow { display: flex; gap: 6px; }
  .stsel { background: var(--panel-2); border: 1px solid var(--line-2); color: var(--ink-3);
           border-radius: 7px; padding: 5px 8px; font-size: 11px; flex: 1; cursor: pointer; }
  .notebtn { background: var(--panel-2); border: 1px solid var(--line-2); color: var(--ink-3);
             border-radius: 7px; padding: 5px 9px; font-size: 11px; cursor: pointer; }
  .notebtn.has { color: #e0c061; border-color: #4a4326; }
  .notewrap { display: flex; flex-direction: column; gap: 5px; }
  .notewrap textarea { background: var(--panel-2); border: 1px solid var(--line-2); color: var(--ink-2);
                       border-radius: 7px; padding: 7px 8px; font-size: 11.5px; resize: vertical;
                       min-height: 54px; font-family: inherit; }
  .notewrap input[type=date] { background: var(--panel-2); border: 1px solid var(--line-2);
                               color: var(--ink-2); border-radius: 7px; padding: 5px 8px; font-size: 11px; }
  .card[data-status=applied]      { border-color: #24457e; }
  .card[data-status=screening]    { border-color: #2f6fdd66; }
  .card[data-status=interview]    { border-color: #4f8ef088; }
  .card[data-status=offer]        { border-color: #7fb0f7aa; box-shadow: 0 0 0 1px #7fb0f733; }
  .card[data-status=accepted]     { border-color: var(--st-accepted); box-shadow: 0 0 0 1px #0ca30c33; }
  .card[data-status=rejected]     { opacity: .45; border-color: #5c2b2b; }
  .card[data-status=ghosted]      { opacity: .5; }

  /* --- bottom sections -------------------------------------------------- */
  .nomatch { color: var(--ink-3); padding: 30px 0; text-align: center; }
  .section-h { color: var(--ink-3); font-size: 13px; font-weight: 600; text-transform: uppercase;
               letter-spacing: .6px; margin: 30px 0 12px; }
  .empty-co, .failed-co { display: flex; align-items: center; gap: 10px; padding: 10px 14px;
           background: #14161d; border: 1px solid var(--line); border-radius: 9px; margin-bottom: 8px;
           font-size: 13px; }
  .failed-co { border-color: #3a2526; }
  .failed-co .why { color: #d98f8f; }
  .src { color: #8b90a0; font-size: 11px; }
  .failed-co a, .empty-co a { margin-left: auto; color: #6ea8fe; text-decoration: none; font-size: 12px; }
  .coname-sm { font-weight: 600; }
  footer { color: var(--ink-4); font-size: 12px; padding: 0 28px 40px; text-align: center; }
  .hidden { display: none !important; }
  .tip { position: fixed; z-index: 60; background: #0b0d12; border: 1px solid var(--line-2);
         border-radius: 8px; padding: 7px 10px; font-size: 12px; color: var(--ink);
         pointer-events: none; box-shadow: 0 8px 24px #000b; }
"""


JS = """
const CNAMES = __CNAMES__;
const STAGES = __STAGES__;            // [[key, label, cssvar], ...] in funnel order
const PROGRESSION = __PROGRESSION__;  // stage keys that form the main path
const EXITS = __EXITS__;              // terminal stages branching off the path
const FACET_DEFS = __FACET_DEFS__;    // [[field, label], ...]
const STALE_BUCKETS = __STALE_BUCKETS__;
const RUN_DATE = "__DATE__";

const LSKEY = 'jobscope.apps';
const VIEWKEY = 'jobscope.view';

const q = document.getElementById('q');
const grid = document.getElementById('grid');
const cards = [...document.querySelectorAll('.card')];
const shown = document.getElementById('shown');
const noMatch = document.getElementById('noMatch');
const sortSel = document.getElementById('sortSel');
const tip = document.getElementById('tip');

let APPS = Object.assign({}, __APPS__, JSON.parse(localStorage.getItem(LSKEY) || '{}'));
const facets = {};
FACET_DEFS.forEach(([f]) => facets[f] = new Set());
let newOnly = false, freshOnly = true, ghostOnly = false, pipeAll = true;

const saveApps = () => localStorage.setItem(LSKEY, JSON.stringify(APPS));
const stageLabel = k => (STAGES.find(s => s[0] === k) || [k, k])[1];
const stageVar = k => (STAGES.find(s => s[0] === k) || [k, k, '--st-none'])[2];

/* ---------------------------------------------------------------- state */

function entry(id) {
  let e = APPS[id];
  if (!e) { e = APPS[id] = { status: 'none', history: [] }; }
  if (!e.history) e.history = [];
  return e;
}

function setStatus(card, status, stamp) {
  const id = card.dataset.id, e = entry(id);
  const prev = e.status || 'none';
  e.status = status;
  card.dataset.status = status;
  const sel = card.querySelector('.stsel');
  if (sel) sel.value = status;
  if (stamp && prev !== status) {
    const today = new Date().toISOString().slice(0, 10);
    if (!e.history.length && prev !== 'none') e.history.push({ stage: prev, date: today });
    e.history.push({ stage: status, date: today });
    if (status === 'applied' && !e.applied_date) e.applied_date = today;
  }
  e.title = card.dataset.title;
  e.company = CNAMES[card.dataset.company] || '';
  e.url = card.dataset.url;
  if (status === 'none' && !(e.note || '').trim() && e.history.length < 2) delete APPS[id];
}

function statusOf(card) { return (APPS[card.dataset.id] || {}).status || 'none'; }

/* --------------------------------------------------------------- filter */

function vals(card, f) {
  if (f === 'state') return card.dataset.state.split(' ').filter(Boolean);
  if (f === 'status') return [statusOf(card)];
  return [card.dataset[f]];
}

function passes(card, skip) {
  const term = q.value.trim().toLowerCase();
  if (term && !card.dataset.search.includes(term)) return false;
  if (newOnly && card.dataset.new !== '1') return false;
  if (ghostOnly && card.dataset.ghost !== '1') return false;
  if (freshOnly && STALE_BUCKETS.includes(card.dataset.age)) return false;
  for (const f in facets) {
    if (f === skip || !facets[f].size) continue;
    if (!vals(card, f).some(v => facets[f].has(v))) return false;
  }
  return true;
}

/* ------------------------------------------------------------ dropdowns */

function optionsFor(field) {
  const counts = new Map();
  cards.forEach(c => {
    if (!passes(c, field)) return;
    vals(c, field).forEach(v => counts.set(v, (counts.get(v) || 0) + 1));
  });
  const all = new Set([...counts.keys()]);
  facets[field].forEach(v => all.add(v));      // keep a chosen value visible at 0
  const dd = document.querySelector(`.fdd[data-facet="${field}"]`);
  const order = JSON.parse(dd.dataset.order || '[]');
  const label = JSON.parse(dd.dataset.labels || '{}');
  const list = [...all].sort((a, b) => {
    const ia = order.indexOf(a), ib = order.indexOf(b);
    if (ia !== -1 || ib !== -1) return (ia === -1 ? 99 : ia) - (ib === -1 ? 99 : ib);
    return (counts.get(b) || 0) - (counts.get(a) || 0) || String(a).localeCompare(String(b));
  });
  return list.map(v => ({ v, label: label[v] || CNAMES[v] || v, n: counts.get(v) || 0 }));
}

function renderMenu(dd) {
  const field = dd.dataset.facet;
  const term = (dd.querySelector('.fddsearch').value || '').trim().toLowerCase();
  const list = dd.querySelector('.fddlist');
  const opts = optionsFor(field).filter(o => !term || o.label.toLowerCase().includes(term));
  if (!opts.length) { list.innerHTML = '<div class="fddempty">No match.</div>'; return; }
  list.innerHTML = opts.map(o => {
    const on = facets[field].has(o.v);
    const sw = field === 'status'
      ? `<span class="swatch" style="background:var(${stageVar(o.v)})"></span>` : '';
    return `<label class="fddopt${o.n ? '' : ' zero'}">`
      + `<input type="checkbox" value="${o.v}"${on ? ' checked' : ''}>${sw}`
      + `<span>${o.label}</span><span class="fct">${o.n}</span></label>`;
  }).join('');
}

function syncFacetButtons() {
  document.querySelectorAll('.fdd').forEach(dd => {
    const f = dd.dataset.facet, n = facets[f].size;
    dd.classList.toggle('active', n > 0);
    const badge = dd.querySelector('.cnt');
    badge.textContent = n; badge.classList.toggle('hidden', !n);
  });
}

function closeMenus(except) {
  document.querySelectorAll('.fddmenu').forEach(m => {
    if (m.parentElement !== except) m.classList.add('hidden');
  });
}

document.querySelectorAll('.fdd').forEach(dd => {
  const menu = dd.querySelector('.fddmenu');
  dd.querySelector('.fddbtn').addEventListener('click', e => {
    e.stopPropagation();
    const wasOpen = !menu.classList.contains('hidden');
    closeMenus(dd);
    if (wasOpen) { menu.classList.add('hidden'); return; }
    renderMenu(dd); menu.classList.remove('hidden');
    dd.querySelector('.fddsearch').focus();
  });
  menu.addEventListener('click', e => e.stopPropagation());
  dd.querySelector('.fddsearch').addEventListener('input', () => renderMenu(dd));
  dd.querySelector('.fddlist').addEventListener('change', e => {
    const cb = e.target.closest('input[type=checkbox]'); if (!cb) return;
    const f = dd.dataset.facet;
    if (cb.checked) facets[f].add(cb.value); else facets[f].delete(cb.value);
    apply(); renderMenu(dd);
  });
  dd.querySelector('.fdd-all').addEventListener('click', () => {
    optionsFor(dd.dataset.facet).forEach(o => { if (o.n) facets[dd.dataset.facet].add(o.v); });
    apply(); renderMenu(dd);
  });
  dd.querySelector('.fdd-none').addEventListener('click', () => {
    facets[dd.dataset.facet].clear(); apply(); renderMenu(dd);
  });
});
document.addEventListener('click', () => closeMenus(null));

/* --------------------------------------------------------------- sankey */

/* The funnel starts at Applied — "Not applied" is a pool, not a flow, and
   including it dwarfs every real stage. Each exit (Rejected / No response)
   gets its OWN node in the column just after the stage it branched from, so
   drop-off reads as a short branch off the spine rather than one long ribbon
   crossing the whole chart. */
function buildFlows() {
  const track = PROGRESSION.filter(s => s !== 'none');
  const reached = {}, flows = new Map();
  track.forEach(k => reached[k] = 0);
  let applied = 0;
  // Default scope is EVERY application: a role you applied to shouldn't fall out
  // of your own pipeline just because the posting aged past the freshness filter.
  const scope = pipeAll ? cards : cards.filter(c => passes(c, 'status'));
  scope.forEach(c => {
    const e = APPS[c.dataset.id];
    if (!e) return;
    const hist = (e.history && e.history.length ? e.history.map(h => h.stage) : [e.status])
      .filter(s => s && s !== 'none');
    if (!hist.length) return;
    const path = hist.filter((s, i) => i === 0 || s !== hist[i - 1]);
    if (!path.includes('applied')) path.unshift('applied');
    applied++;
    new Set(path.filter(s => track.includes(s))).forEach(s => reached[s]++);
    for (let i = 0; i < path.length - 1; i++) {
      flows.set(path[i] + '>' + path[i + 1], (flows.get(path[i] + '>' + path[i + 1]) || 0) + 1);
    }
  });
  return { reached, flows, applied, track };
}

function drawSankey() {
  const svg = document.getElementById('sankey');
  const empty = document.getElementById('pipeEmpty');
  const { reached, flows, applied, track } = buildFlows();
  if (!applied) { svg.classList.add('hidden'); empty.classList.remove('hidden'); return; }
  svg.classList.remove('hidden'); empty.classList.add('hidden');

  // Node instances: progression nodes at their stage column, one exit node per
  // (stage, exit) pair placed one column further right.
  const colOf = {}; track.forEach((k, i) => colOf[k] = i);
  const nodes = {};
  track.forEach(k => { if (reached[k]) nodes[k] = { v: reached[k], stage: k, col: colOf[k] }; });
  flows.forEach((v, key) => {
    const [a, b] = key.split('>');
    if (!EXITS.includes(b) || colOf[a] === undefined) return;
    nodes[b + '@' + a] = { v, stage: b, col: colOf[a] + 1 };
  });

  const byCol = {};
  Object.entries(nodes).forEach(([id, n]) => (byCol[n.col] = byCol[n.col] || []).push(id));
  const colIdx = Object.keys(byCol).map(Number).sort((a, b) => a - b);
  const maxSum = Math.max(...colIdx.map(c => byCol[c].reduce((a, id) => a + nodes[id].v, 0)));

  const W = svg.clientWidth || 1100, colW = 14, gap = 5, labelW = 118;
  const H = Math.max(200, Math.min(400, maxSum * 22 + 40));
  const padT = 14, padB = 20, plot = H - padT - padB;
  const unit = plot / Math.max(maxSum, 1);
  const span = Math.max(1, colIdx[colIdx.length - 1]);
  const xOf = c => 6 + (c / span) * (W - colW - labelW - 12);

  const pos = {};
  colIdx.forEach(c => {
    // Spine node first, drop-offs stacked beneath it.
    const ids = byCol[c].sort((a, b) => (EXITS.includes(nodes[a].stage) ? 1 : 0)
                                      - (EXITS.includes(nodes[b].stage) ? 1 : 0));
    let y = padT;
    ids.forEach(id => {
      const h = Math.max(4, nodes[id].v * unit);
      pos[id] = { x: xOf(c), y, h, inY: y, outY: y };
      y += h + gap;
    });
  });

  const ribbons = [];
  flows.forEach((v, key) => {
    const [a, b] = key.split('>');
    const target = EXITS.includes(b) ? b + '@' + a : b;
    if (pos[a] && pos[target]) ribbons.push({ a, target, b, v });
  });
  ribbons.sort((x, y) => nodes[x.target].col - nodes[y.target].col || y.v - x.v);

  let out = '';
  ribbons.forEach(f => {
    const s = pos[f.a], t = pos[f.target];
    const th = Math.max(2, f.v * unit);
    const y0 = s.outY, y1 = t.inY;
    s.outY += th; t.inY += th;
    const x0 = s.x + colW, x1 = t.x, mx = (x0 + x1) / 2;
    const d = `M${x0},${y0} C${mx},${y0} ${mx},${y1} ${x1},${y1} `
            + `L${x1},${y1 + th} C${mx},${y1 + th} ${mx},${y0 + th} ${x0},${y0 + th} Z`;
    out += `<path class="sk-flow" d="${d}" fill="var(${stageVar(f.a)})" opacity=".38"`
        + ` data-tip="${stageLabel(f.a)} &rarr; ${stageLabel(f.b)}: ${f.v}"></path>`;
  });

  Object.entries(pos).forEach(([id, p]) => {
    const n = nodes[id];
    out += `<rect class="sk-node" x="${p.x}" y="${p.y}" width="${colW}" height="${p.h}"`
        + ` rx="3" fill="var(${stageVar(n.stage)})"`
        + ` data-tip="${stageLabel(n.stage)}: ${n.v}"></rect>`;
    const ty = p.y + p.h / 2;
    out += `<text class="sk-val" x="${p.x + colW + 8}" y="${ty - 1}">${n.v}</text>`
        + `<text class="sk-lab" x="${p.x + colW + 8}" y="${ty + 12}">${stageLabel(n.stage)}</text>`;
  });

  svg.setAttribute('viewBox', `0 0 ${W} ${H}`);
  svg.setAttribute('height', H);
  svg.innerHTML = out;
}

/* ---------------------------------------------------------------- apply */

function apply() {
  let n = 0;
  cards.forEach(card => {
    const show = passes(card, null);
    card.classList.toggle('hidden', !show);
    if (show) n++;
  });
  const vis = cards.filter(c => !c.classList.contains('hidden'));
  document.getElementById('stRoles').textContent = vis.length;
  document.getElementById('stNew').textContent = vis.filter(c => c.dataset.new === '1').length;
  document.getElementById('stCompanies').textContent = new Set(vis.map(c => c.dataset.company)).size;
  document.getElementById('stGhost').textContent = vis.filter(c => c.dataset.ghost === '1').length;
  shown.textContent = n + ' / ' + cards.length + ' shown';
  noMatch.classList.toggle('hidden', n !== 0);

  const counts = {};
  STAGES.forEach(([k]) => counts[k] = 0);
  cards.filter(c => passes(c, 'status')).forEach(c => counts[statusOf(c)]++);
  document.querySelectorAll('.stg').forEach(el => {
    const k = el.dataset.stage;
    el.querySelector('.n').textContent = counts[k] || 0;
    el.classList.toggle('on', facets.status.has(k));
  });
  document.getElementById('stPipeline').textContent =
    Object.entries(counts).filter(([k]) => k !== 'none' && k !== 'rejected' && k !== 'ghosted')
      .reduce((a, [, v]) => a + v, 0);

  syncFacetButtons();
  drawSankey();
  saveView();
}

function sortGrid() {
  const m = sortSel.value;
  cards.slice().sort((a, b) => {
    if (m === 'company') return a.dataset.comp.localeCompare(b.dataset.comp) || b.dataset.score - a.dataset.score;
    if (m === 'new') return (b.dataset.new - a.dataset.new) || b.dataset.score - a.dataset.score;
    if (m === 'age') return (a.dataset.days - b.dataset.days) || b.dataset.score - a.dataset.score;
    return (b.dataset.score - a.dataset.score) || a.dataset.comp.localeCompare(b.dataset.comp);
  }).forEach(c => grid.appendChild(c));
}

/* ------------------------------------------------------------ view state */

function saveView() {
  const v = { q: q.value, sort: sortSel.value, newOnly, freshOnly, ghostOnly, f: {} };
  for (const k in facets) if (facets[k].size) v.f[k] = [...facets[k]];
  localStorage.setItem(VIEWKEY, JSON.stringify(v));
  const hash = new URLSearchParams();
  if (v.q) hash.set('q', v.q);
  if (v.sort !== 'score') hash.set('sort', v.sort);
  if (!freshOnly) hash.set('fresh', '0');
  if (newOnly) hash.set('new', '1');
  if (ghostOnly) hash.set('ghost', '1');
  for (const k in v.f) hash.set(k, v.f[k].join('~'));
  const s = hash.toString();
  history.replaceState(null, '', s ? '#' + s : location.pathname);
}

function loadView() {
  let v = null;
  if (location.hash.length > 1) {
    const p = new URLSearchParams(location.hash.slice(1));
    v = { q: p.get('q') || '', sort: p.get('sort') || 'score', newOnly: p.get('new') === '1',
          ghostOnly: p.get('ghost') === '1', freshOnly: p.get('fresh') !== '0', f: {} };
    for (const k in facets) if (p.get(k)) v.f[k] = p.get(k).split('~');
  } else {
    try { v = JSON.parse(localStorage.getItem(VIEWKEY) || 'null'); } catch (e) { v = null; }
  }
  if (!v) return;
  q.value = v.q || '';
  sortSel.value = v.sort || 'score';
  newOnly = !!v.newOnly; ghostOnly = !!v.ghostOnly;
  freshOnly = v.freshOnly !== false;
  for (const k in (v.f || {})) if (facets[k]) v.f[k].forEach(x => facets[k].add(x));
  document.getElementById('newBtn').classList.toggle('on', newOnly);
  document.getElementById('ghostBtn').classList.toggle('on', ghostOnly);
  document.getElementById('freshBtn').classList.toggle('on', freshOnly);
}

/* -------------------------------------------------------------- wiring */

q.addEventListener('input', apply);
sortSel.addEventListener('change', () => { sortGrid(); saveView(); });
document.getElementById('newBtn').addEventListener('click', e => {
  newOnly = !newOnly; e.target.classList.toggle('on', newOnly); apply();
});
document.getElementById('freshBtn').addEventListener('click', e => {
  freshOnly = !freshOnly; e.target.classList.toggle('on', freshOnly); apply();
});
document.getElementById('ghostBtn').addEventListener('click', e => {
  ghostOnly = !ghostOnly; e.target.classList.toggle('on', ghostOnly); apply();
});
document.getElementById('clrBtn').addEventListener('click', () => {
  for (const f in facets) facets[f].clear();
  newOnly = ghostOnly = false; freshOnly = false;
  ['newBtn', 'ghostBtn', 'freshBtn'].forEach(id => document.getElementById(id).classList.remove('on'));
  q.value = ''; apply();
});
document.querySelectorAll('.stg').forEach(el => el.addEventListener('click', () => {
  const k = el.dataset.stage;
  if (facets.status.has(k)) facets.status.delete(k); else facets.status.add(k);
  apply();
}));
document.getElementById('expBtn').addEventListener('click', () => {
  const blob = new Blob([JSON.stringify(APPS, null, 2)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob); a.download = 'applications.json'; a.click();
  URL.revokeObjectURL(a.href);
});

grid.addEventListener('change', e => {
  const card = e.target.closest('.card'); if (!card) return;
  if (e.target.classList.contains('stsel')) { setStatus(card, e.target.value, true); saveApps(); apply(); }
  if (e.target.classList.contains('napp')) { entry(card.dataset.id).applied_date = e.target.value; saveApps(); }
});
grid.addEventListener('input', e => {
  if (!e.target.classList.contains('ntext')) return;
  const card = e.target.closest('.card');
  entry(card.dataset.id).note = e.target.value;
  card.querySelector('.notebtn').classList.toggle('has', !!e.target.value.trim());
  saveApps();
});
grid.addEventListener('click', e => {
  const btn = e.target.closest('.notebtn'); if (!btn) return;
  btn.closest('.card').querySelector('.notewrap').classList.toggle('hidden');
});

const pipe = document.querySelector('.pipe');
document.getElementById('sankey').addEventListener('mouseover', e => {
  const el = e.target.closest('[data-tip]'); if (!el) return;
  pipe.classList.add('dim'); el.classList.add('hot');
  tip.innerHTML = el.dataset.tip; tip.classList.remove('hidden');
});
document.getElementById('sankey').addEventListener('mousemove', e => {
  tip.style.left = Math.min(e.clientX + 14, innerWidth - tip.offsetWidth - 8) + 'px';
  tip.style.top = (e.clientY + 16) + 'px';
});
document.getElementById('sankey').addEventListener('mouseout', e => {
  const el = e.target.closest('[data-tip]'); if (el) el.classList.remove('hot');
  pipe.classList.remove('dim'); tip.classList.add('hidden');
});
document.getElementById('pipeToggle').addEventListener('click', e => {
  const body = document.getElementById('pipeBody');
  body.classList.toggle('hidden');
  e.target.textContent = body.classList.contains('hidden') ? 'Show' : 'Hide';
});
document.getElementById('pipeScope').addEventListener('click', e => {
  pipeAll = !pipeAll;
  e.target.textContent = pipeAll ? 'All applications' : 'Current filter';
  document.getElementById('pipeSub').textContent = pipeAll
    ? 'every role you have tracked, ignoring filters'
    : 'only roles matching the filters above';
  drawSankey();
});
addEventListener('resize', drawSankey);

cards.forEach(c => {
  const e = APPS[c.dataset.id];
  if (e && e.status && e.status !== 'none') setStatus(c, e.status, false);
  if (e && e.note) {
    c.querySelector('.ntext').value = e.note;
    c.querySelector('.notebtn').classList.add('has');
  }
  if (e && e.applied_date) c.querySelector('.napp').value = e.applied_date;
});
loadView();
sortGrid();
apply();
"""
