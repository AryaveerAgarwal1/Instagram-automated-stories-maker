/* s45 Content Factory - local review app
   Every mutation goes through the backend, which runs the same validator and the
   same approval gate as the CLI. Nothing here can bypass a rule. */

const S = {
  state: null,
  view: 'stories',
  slug: null,
  frame: 1,
  bust: Date.now(),
};

const $  = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

/* ------------------------------------------------------------------ api */
async function api(path, opts = {}) {
  const r = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...opts,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
  });
  if (!r.ok) {
    let detail = r.statusText;
    try { detail = (await r.json()).detail || detail; } catch (e) {}
    throw new Error(detail);
  }
  return r.json();
}

function toast(msg, kind = '') {
  const el = document.createElement('div');
  el.className = 'toast ' + kind;
  el.textContent = msg;
  $('#toasts').appendChild(el);
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .4s'; }, 5200);
  setTimeout(() => el.remove(), 5700);
}

function setConn(ok, text) {
  $('#connDot').className = 'dot ' + (ok ? 'ok' : 'bad');
  $('#connText').textContent = text;
}

/* ------------------------------------------------------------------ load */
async function load(keepFrame = true) {
  try {
    S.state = await api('/api/state');
    setConn(true, 'connected');
  } catch (e) {
    setConn(false, 'offline');
    toast('Cannot reach the backend. Is run.py still running?\n' + e.message, 'bad');
    return;
  }
  S.bust = Date.now();
  const slugs = S.state.sequences.map(s => s.slug);
  if (!S.slug || !slugs.includes(S.slug)) { S.slug = slugs[0] || null; S.frame = 1; }
  if (!keepFrame) S.frame = 1;
  $('#accountHandle').textContent = seq()?.config?.profile?.handle || '@s45';
  renderHardStop();
  renderAll();
}

const seq = () => S.state?.sequences.find(s => s.slug === S.slug) || null;
const frameOf = (q) => (seq()?.config?.frames || []).find(f => f.n === q) || null;

/* ------------------------------------------------------------------ chrome */
function renderHardStop() {
  const el = $('#hardstopBadge');
  const ib = S.state.identity_block;
  if (!ib.ready) {
    el.className = 'hardstop on';
    el.textContent = 'IDENTITY BLOCK HARD STOP\n' + ib.reason;
  } else if (S.state.entity_status_pending) {
    el.className = 'hardstop warn';
    el.textContent = 'entity_status TBD_BY_COUNSEL\nQ1 and Q2 unanswered';
  } else {
    el.className = 'hardstop';
  }
}

function setView(v) {
  S.view = v;
  $$('.navitem').forEach(b => b.classList.toggle('active', b.dataset.view === v));
  $$('.view').forEach(s => s.classList.toggle('active', s.dataset.view === v));
  $('#viewTitle').textContent = {
    stories: 'Stories', pipeline: 'Pipeline', library: 'Asset library',
    analytics: 'Analytics', compliance: 'Policy & brand',
  }[v];
  renderAll();
}

function renderAll() {
  if (!S.state) return;
  renderSeqList();
  renderIdeas();
  renderStage();
  renderEditor();
  if (S.view === 'pipeline') renderPipeline();
  if (S.view === 'library') renderLibrary();
  if (S.view === 'analytics') renderAnalytics();
  if (S.view === 'compliance') renderCompliance();
}

/* ------------------------------------------------------------------ list */
function stateChip(s) {
  const m = {
    draft:          ['grey',  'draft'],
    rendered:       ['blue',  'rendered'],
    approval_stale: ['red',   'approval stale'],
    approved:       ['green', 'approved'],
    published:      ['green', 'published'],
    broken:         ['red',   'broken'],
  }[s.state] || ['grey', s.state];
  return `<span class="chip ${m[0]}">${m[1]}</span>`;
}

function renderSeqList() {
  const box = $('#seqList');
  $('#seqCount').textContent = S.state.sequences.length;
  if (!S.state.sequences.length) {
    box.innerHTML = '<div class="empty">no sequences yet</div>'; return;
  }
  box.innerHTML = S.state.sequences.map(s => `
    <div class="seqcard ${s.slug === S.slug ? 'sel' : ''}" data-slug="${esc(s.slug)}">
      <div class="t">${esc(s.config?.highlight_title ? s.slug : s.slug)}</div>
      <div class="m">
        <span>${s.frame_count} frames</span><span>&middot;</span>
        <span>${esc(s.type || '?')}</span>
        ${stateChip(s)}
        ${s.error_count ? `<span class="chip red">${s.error_count} error${s.error_count > 1 ? 's' : ''}</span>` : ''}
        ${s.hand_post_only?.length ? '<span class="chip amber">hand-post</span>' : ''}
      </div>
    </div>`).join('');
  $$('.seqcard', box).forEach(c => c.onclick = () => {
    S.slug = c.dataset.slug; S.frame = 1; renderAll();
  });
}

function renderIdeas() {
  const box = $('#ideaList');
  const ideas = S.state.ideas.filter(i => i.status !== 'done');
  $('#ideaCount').textContent = ideas.length;
  if (!ideas.length) { box.innerHTML = '<div class="empty">queue is empty</div>'; return; }
  box.innerHTML = ideas.map(i => `
    <div class="ideacard">
      <div class="t">${esc(i.title)}</div>
      <div class="r">
        <span class="chip">${esc(i.type)}</span>
        <span class="chip ${i.status === 'building' ? 'blue' : 'grey'}">${esc(i.status)}</span>
        <button class="btn sm" data-build="${esc(i.id)}" style="margin-left:auto">Build</button>
        <button class="btn sm" data-done="${esc(i.id)}">Done</button>
      </div>
    </div>`).join('');
  $$('[data-done]', box).forEach(b => b.onclick = async () => {
    await api('/api/ideas/' + b.dataset.done, { method: 'PATCH', body: { status: 'done' } });
    load();
  });
  $$('[data-build]', box).forEach(b => b.onclick = () => {
    const idea = S.state.ideas.find(i => i.id === b.dataset.build);
    newSequenceModal(idea);
  });
}

/* ------------------------------------------------------------------ stage */
function renderStage() {
  const s = seq();
  if (!s) {
    $('#seqTitle').textContent = 'No sequence selected';
    $('#seqMeta').innerHTML = ''; $('#filmstrip').innerHTML = '';
    $('#frameImg').style.display = 'none'; $('#phoneEmpty').style.display = 'grid';
    return;
  }
  $('#seqTitle').textContent = s.slug;

  const ap = s.approval;
  $('#seqMeta').innerHTML = [
    `<span>${esc(s.type)}</span>`, '<span>&middot;</span>',
    `<span>highlight "${esc(s.config.highlight_title || '-')}"</span>`,
    '<span>&middot;</span>',
    `<span>${esc(s.config.scope_attestation || 'NO ATTESTATION')}</span>`,
    stateChip(s),
    s.error_count ? `<span class="chip red">${s.error_count} errors</span>` : '',
    s.warning_count ? `<span class="chip amber">${s.warning_count} warnings</span>` : '',
    ap ? `<span class="chip green">by ${esc(ap.approver)}</span>` : '',
  ].join(' ');

  $('#approveBtn').textContent = s.approval ? 'Revoke approval' : 'Approve';
  $('#approveBtn').className = 'btn ' + (s.approval ? 'ghost danger' : 'ghost');

  // filmstrip
  const rendered = new Set(s.rendered_frames || []);
  $('#filmstrip').innerHTML = (s.config.frames || []).map(f => {
    const name = `frame_${f.n}.png`;
    const hand = (s.hand_post_only || []).includes(f.n);
    const has = rendered.has(name);
    return `<div class="thumb ${f.n === S.frame ? 'sel' : ''}" data-n="${f.n}">
      ${has ? `<img src="/api/frame/${s.slug}/${name}?w=150&t=${S.bust}" alt="">`
            : '<div class="missing">not<br>rendered</div>'}
      <span class="n">${f.n}</span>
      ${f.continues ? '<span class="b">CONT</span>' : ''}
      ${hand ? '<span class="b hand">HAND</span>' : ''}
    </div>`;
  }).join('');
  $$('#filmstrip .thumb').forEach(t => t.onclick = () => {
    S.frame = +t.dataset.n; renderStage(); renderEditor();
  });

  // preview
  const name = `frame_${S.frame}.png`;
  const img = $('#frameImg');
  if (rendered.has(name)) {
    img.src = `/api/frame/${s.slug}/${name}?t=${S.bust}`;
    img.style.display = 'block'; $('#phoneEmpty').style.display = 'none';
  } else {
    img.style.display = 'none'; $('#phoneEmpty').style.display = 'grid';
  }
}

/* ------------------------------------------------------------------ editor */
function renderEditor() {
  const s = seq(); const box = $('#editor');
  if (!s) { box.innerHTML = '<div class="empty">-</div>'; $('#frameBadge').textContent = '-'; return; }
  const f = frameOf(S.frame);
  if (!f) { box.innerHTML = '<div class="empty">no such frame</div>'; return; }
  $('#frameBadge').textContent = `frame ${f.n} / ${s.config.frames.length}`;

  const cont = !!f.continues;
  const bg = f.background || {};
  const issues = (s.issues || []).filter(i =>
    i.where.startsWith(`frame ${f.n}`) || i.where === 'config' || i.where.startsWith('config'));

  const roles = ['hook', 'read', 'argument', 'mechanism', 'evidence', 'counter', 'context',
                 'detail', 'learned', 'implication', 'bridge', 'cta', 'optional'];

  box.innerHTML = `
    ${issues.length ? issues.map(i => `
      <div class="issue ${i.level}">
        <span class="rule">${esc(i.rule)}</span> &middot; ${esc(i.where)}<br>${esc(i.message)}
        ${i.span ? `<span class="span">&raquo; ${esc(i.span)}</span>` : ''}
      </div>`).join('') : ''}

    <div class="fld">
      <label>Role</label>
      <select id="eRole">${roles.map(r =>
        `<option ${f.role === r ? 'selected' : ''}>${r}</option>`).join('')}</select>
    </div>

    ${f.n === 1 ? `<div class="note">Frame 1 carries the identity block. Fixed position,
      fixed size, rendered from policy.json. Not overridable here - that is the point.</div>` : `
    <label class="check">
      <input type="checkbox" id="eCont" ${cont ? 'checked' : ''}>
      <span>Continues previous frame (same photo, earlier text dimmed)</span>
    </label>`}

    <div class="fld">
      <label>Text position <span class="v">${cont ? 'inherited' : ''}</span></label>
      <select id="ePos" ${cont ? 'disabled' : ''}>
        ${['top', 'center', 'bottom'].map(p =>
          `<option ${(f.text_position || 'top') === p ? 'selected' : ''}>${p}</option>`).join('')}
      </select>
    </div>

    <div class="fld">
      <label>Background ${cont ? '<span class="v">inherited from previous</span>' : ''}</label>
      <select id="eBgType" ${cont ? 'disabled' : ''}>
        <option value="field" ${bg.type !== 'note' ? 'selected' : ''}>field - teal, quiet</option>
        <option value="note" ${bg.type === 'note' ? 'selected' : ''}>note - teal + kicker</option>
      </select>
      <p class="hint">Every frame is drawn from <code>config/brand.json</code>. There is no
      photo library and nothing to upload; <code>note</code> adds the capital-markets-note
      kicker, <code>field</code> leaves it off.</p>
    </div>

    ${panelSummary(f)}

    <div class="editor-sec">
      <h4>Text blocks <button class="btn sm" id="eAddBlock">+ Block</button></h4>
      ${(f.blocks || []).map((b, i) => blockCard(b, i)).join('')}
    </div>

    <div class="editor-sec">
      <h4>Evidence &amp; furniture</h4>
      <div class="fld">
        <label>Source line <span class="v">required by any statistic</span></label>
        <input type="text" id="eSource" value="${esc(f.source_line || '')}"
               placeholder="Name the source. A number without a source does not render.">
      </div>
      <div class="fld">
        <label>Artifact <span class="v">assets/artifacts only</span></label>
        <select id="eArtifact">
          <option value="">none</option>
          ${S.state.artifacts.map(a => `<option value="${esc(a.name)}"
            ${f.artifact === a.name ? 'selected' : ''}>${esc(a.name)}</option>`).join('')}
        </select>
      </div>
      ${f.artifact ? `<div class="fld"><label>Artifact position</label>
        <select id="eArtPos">${['lower', 'center', 'upper'].map(p =>
          `<option ${(f.artifact_pos || 'lower') === p ? 'selected' : ''}>${p}</option>`).join('')}
        </select></div>` : ''}
      <div class="fld">
        <label>Sticker <span class="v">checklist only, never pixels</span></label>
        <select id="eStickerKind">
          <option value="" ${!f.sticker ? 'selected' : ''}>none</option>
          <option value="poll" ${f.sticker?.kind === 'poll' ? 'selected' : ''}>poll</option>
          <option value="link" ${f.sticker?.kind === 'link' ? 'selected' : ''}>link</option>
        </select>
      </div>
      ${f.sticker ? `<div class="fld"><label>Sticker text / destination</label>
        <input type="text" id="eStickerText"
               value="${esc(f.sticker.text || f.sticker.destination || '')}"></div>` : ''}
    </div>

    <div class="editor-actions">
      <button class="btn primary" id="eSave">Save &amp; re-render</button>
      <button class="btn ghost" id="eSaveOnly">Save</button>
    </div>`;

  wireEditor(f);
}

function blockCard(b, i) {
  const hl = (b.highlights || [])[0] || {};
  return `<div class="blockcard" data-bi="${i}">
    <textarea data-k="text">${esc(b.text || '')}</textarea>
    <div class="row">
      <select data-k="size">
        ${['big', 'med', 'small'].map(s =>
          `<option ${(b.size || (i === 0 ? 'big' : 'med')) === s ? 'selected' : ''}>${s}</option>`).join('')}
      </select>
      <button class="btn sm" data-del="${i}">&times;</button>
    </div>
    <div class="row">
      <input type="text" data-k="hltext" value="${esc(hl.text || '')}"
             placeholder="highlight - 1 to 4 words, exact substring">
      <select data-k="hlstyle" style="max-width:110px">
        ${['underline', 'text', 'strike'].map(s =>
          `<option ${(hl.style || 'underline') === s ? 'selected' : ''}>${s}</option>`).join('')}
      </select>
    </div>
  </div>`;
}

function collectFrame(f) {
  const g = (id) => $('#' + id);
  const out = { ...f };
  out.role = g('eRole').value;

  const contEl = g('eCont');
  const cont = contEl ? contEl.checked : !!f.continues;
  if (f.n === 1) { delete out.continues; } else if (cont) { out.continues = true; } else { delete out.continues; }

  if (cont) {
    delete out.background; delete out.text_position;
  } else {
    out.text_position = g('ePos').value;
    out.background = { type: g('eBgType').value === 'note' ? 'note' : 'field' };
  }

  out.blocks = $$('#editor .blockcard').map((c, i) => {
    const t = $('[data-k=text]', c).value;
    const blk = { text: t };
    const size = $('[data-k=size]', c).value;
    if (!(i === 0 && size === 'big')) blk.size = size;
    const hlt = $('[data-k=hltext]', c).value.trim();
    if (hlt) blk.highlights = [{ text: hlt, style: $('[data-k=hlstyle]', c).value }];
    return blk;
  });

  out.source_line = $('#eSource').value.trim() || null;
  out.artifact = $('#eArtifact').value || null;
  out.artifact_pos = out.artifact ? ($('#eArtPos')?.value || f.artifact_pos || 'lower') : null;

  const sk = $('#eStickerKind').value;
  if (!sk) out.sticker = null;
  else {
    const txt = $('#eStickerText')?.value || '';
    out.sticker = sk === 'link' ? { kind: 'link', destination: txt, text: txt }
                                : { kind: 'poll', text: txt };
  }
  return out;
}

/* A read-only summary of the drawn components on a frame. These are edited in
   config.json, not here - a metric row and a chart are data, and data that can be
   nudged with a slider in a review app is data nobody checks against its source. */
function panelSummary(f) {
  const rows = [];
  if (f.eyebrow) rows.push(['eyebrow', esc(f.eyebrow)]);
  if (f.metrics) rows.push(['metrics', f.metrics.map(m =>
    `${esc(m.label)} ${esc(m.value)}${m.delta ? ` (${esc(m.delta)}, ${esc(m.direction || '?')})` : ''}`
  ).join('<br>')]);
  if (f.chart) rows.push(['chart', `${esc(f.chart.type)} &middot; ${esc(f.chart.title || 'untitled')}
    &middot; ${(f.chart.series || []).length} series &times; ${(f.chart.labels || []).length} points
    ${f.chart.source ? `<br><span style="color:var(--text-3)">${esc(f.chart.source)}</span>` : ''}`]);
  if (f.bullets) rows.push(['bullets', `${f.bullets.length} rows`]);
  if (f.signal) rows.push(['signal', esc(f.signal)]);
  if (!rows.length) return '';
  return `<div class="editor-sec">
    <h4>Drawn panels</h4>
    <div class="kv">${rows.map(([k, v]) => `<div class="k">${k}</div><div class="v">${v}</div>`).join('')}</div>
    <p class="hint">Edit these in <code>config.json</code>, then re-render. A chart carries the
    same weight as a sentence and gets checked against its source the same way.</p>
  </div>`;
}

function wireEditor(f) {
  const cont = $('#eCont'); if (cont) cont.onchange = () => saveFrame(f, false, true);
  const bt = $('#eBgType'); if (bt) bt.onchange = () => saveFrame(f, false, true);
  const art = $('#eArtifact'); if (art) art.onchange = () => saveFrame(f, false, true);
  const sk = $('#eStickerKind'); if (sk) sk.onchange = () => saveFrame(f, false, true);

  $$('#editor [data-del]').forEach(b => b.onclick = () => {
    const f2 = collectFrame(f);
    f2.blocks.splice(+b.dataset.del, 1);
    if (!f2.blocks.length) f2.blocks = [{ text: '' }];
    writeFrame(f2).then(() => load());
  });
  $('#eAddBlock').onclick = () => {
    const f2 = collectFrame(f);
    if (f2.blocks.length >= 3) return toast('1 to 3 blocks per frame.', 'bad');
    f2.blocks.push({ text: '', size: 'med' });
    writeFrame(f2).then(() => load());
  };
  $('#eSave').onclick = () => saveFrame(f, true);
  $('#eSaveOnly').onclick = () => saveFrame(f, false);
}

async function writeFrame(newFrame) {
  const s = seq();
  const cfg = JSON.parse(JSON.stringify(s.config));
  cfg.frames = cfg.frames.map(x => x.n === newFrame.n ? newFrame : x);
  return api(`/api/sequences/${s.slug}/config`, { method: 'PUT', body: { config: cfg } });
}

async function saveFrame(f, alsoRender, quiet) {
  try {
    await writeFrame(collectFrame(f));
    if (alsoRender) {
      const r = await api(`/api/sequences/${S.slug}/render`, { method: 'POST', body: { frame: f.n } });
      if (!r.ok) toast(r.error, 'bad');
      else toast(`Rendered ${r.render.frames.join(', ')}`, 'ok');
    } else if (!quiet) toast('Saved.', 'ok');
    await load();
  } catch (e) { toast(e.message, 'bad'); }
}

/* ------------------------------------------------------------------ actions */
async function renderAllFrames() {
  try {
    const r = await api(`/api/sequences/${S.slug}/render`, { method: 'POST', body: {} });
    if (!r.ok) toast(r.error, 'bad');
    else {
      toast(`Rendered ${r.render.frames.length} frames.` +
            (r.render.warnings.length ? '\n' + r.render.warnings.join('\n') : ''), 'ok');
    }
    await load();
  } catch (e) { toast(e.message, 'bad'); }
}

async function showPostOrder() {
  try {
    const r = await api(`/api/sequences/${S.slug}/post-order`);
    modal('post-order.md', `<pre>${esc(r.markdown)}</pre>`, '');
  } catch (e) { toast('Render first - ' + e.message, 'bad'); }
}

function approveModal() {
  const s = seq();
  if (s.approval) {
    modal('Revoke approval', `<p style="color:var(--text-2);line-height:1.7">
      Approved by <b>${esc(s.approval.approver)}</b> at ${esc(s.approval.approved_at)}.<br>
      Revoking deletes approval.json. The sequence becomes unpublishable again.</p>`,
      `<button class="btn danger" id="mRevoke">Revoke</button>`);
    $('#mRevoke').onclick = async () => {
      await api(`/api/sequences/${S.slug}/approve`, { method: 'DELETE' });
      closeModal(); toast('Approval revoked.', 'ok'); load();
    };
    return;
  }
  const approvers = S.state.policy.approvers || [];
  modal('Approve ' + s.slug, `
    <p style="color:var(--text-2);line-height:1.7;margin-top:0">
      This writes <code>approval.json</code> with the SHA-256 of every frame PNG.
      <code>schedule.py</code> recomputes those hashes before pushing - any frame changed
      after approval invalidates it. Approval is per sequence, not per week.</p>
    <div class="fld"><label>Approver</label>
      <select id="mApprover">${approvers.map(a => `<option>${esc(a)}</option>`).join('')}</select></div>
    <div class="fld"><label>Note</label>
      <input type="text" id="mNote" placeholder="what you checked"></div>`,
    `<button class="btn primary" id="mApprove">Sign off</button>`);
  $('#mApprove').onclick = async () => {
    try {
      await api(`/api/sequences/${S.slug}/approve`, {
        method: 'POST', body: { approver: $('#mApprover').value, note: $('#mNote').value } });
      closeModal(); toast('Approved.', 'ok'); load();
    } catch (e) { toast(e.message, 'bad'); }
  };
}

function scheduleModal() {
  const s = seq();
  const hand = s.hand_post_only || [];
  modal('Schedule ' + s.slug, `
    <p style="color:var(--text-2);line-height:1.7;margin-top:0">
      All frames go out as <b>one story post carrying the images in order</b>, never N
      separate posts.${hand.length ? ` Frame(s) <b>${hand.join(', ')}</b> need a native
      sticker or link, so this sequence is hand-post only.` : ''}</p>`,
    `<button class="btn ghost" id="mDry">Dry run</button>
     ${hand.length ? '<button class="btn primary" id="mHand">Mark hand-posted</button>'
                   : '<button class="btn primary" id="mPub">Publish</button>'}
     <button class="btn ghost" id="mArch">Archive</button>`);

  const go = async (mode) => {
    try {
      const r = await api(`/api/sequences/${S.slug}/schedule`, { method: 'POST', body: { mode } });
      toast(r.message, r.ok ? 'ok' : 'bad');
      if (r.ok && mode !== 'dry-run') closeModal();
      load();
    } catch (e) { toast(e.message, 'bad'); }
  };
  $('#mDry').onclick = () => go('dry-run');
  if ($('#mHand')) $('#mHand').onclick = () => go('hand-posted');
  if ($('#mPub')) $('#mPub').onclick = () => go('publish');
  $('#mArch').onclick = async () => {
    const r = await api(`/api/sequences/${S.slug}/archive`, { method: 'POST' });
    toast(r.message, r.ok ? 'ok' : 'bad'); load();
  };
}

function newSequenceModal(idea) {
  const suggested = idea
    ? idea.title.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 46)
    : '';
  modal('New sequence', `
    <div class="fld"><label>Slug (kebab-case)</label>
      <input type="text" id="mSlug" value="${esc(suggested)}" placeholder="the-topic-in-a-line"></div>
    <div class="fld"><label>Type</label>
      <select id="mType">${['thesis', 'private_markets', 'build', 'cta'].map(t =>
        `<option ${idea?.type === t ? 'selected' : ''}>${t}</option>`).join('')}</select></div>
    <div class="fld"><label>Highlight</label>
      <select id="mHl">${['How we think', 'Private markets', 'Building s45', 'Join us'].map(h =>
        `<option>${h}</option>`).join('')}</select></div>
    <p style="color:var(--text-3);font-size:11.5px;line-height:1.7">
      Six frames are scaffolded with the right roles for the type and
      <code>scope_attestation</code> already set. At most one <code>cta</code> a week.</p>`,
    `<button class="btn primary" id="mCreate">Create</button>`);
  $('#mCreate').onclick = async () => {
    try {
      const r = await api('/api/sequences', { method: 'POST', body: {
        slug: $('#mSlug').value, type: $('#mType').value,
        highlight_title: $('#mHl').value, from_idea: idea?.id || null } });
      closeModal(); S.slug = r.slug; S.frame = 1; setView('stories'); await load(false);
      toast('Created. Write the beats, then render.', 'ok');
    } catch (e) { toast(e.message, 'bad'); }
  };
}

function queueIdeaModal() {
  modal('Queue idea', `
    <div class="fld"><label>Topic</label>
      <input type="text" id="mTitle" placeholder="one line, the read you want to argue"></div>
    <div class="fld"><label>Type</label>
      <select id="mIType">${['thesis', 'private_markets', 'build', 'cta'].map(t =>
        `<option>${t}</option>`).join('')}</select></div>
    <div class="fld"><label>Note</label>
      <input type="text" id="mINote" placeholder="the angle, or what evidence you have"></div>`,
    `<button class="btn primary" id="mQueue">Queue</button>`);
  $('#mQueue').onclick = async () => {
    await api('/api/ideas', { method: 'POST', body: {
      title: $('#mTitle').value, type: $('#mIType').value, note: $('#mINote').value } });
    closeModal(); load();
  };
}

/* ------------------------------------------------------------------ pipeline */
function renderPipeline() {
  const cols = [
    ['draft', 'Draft', 'config written, nothing rendered'],
    ['rendered', 'Rendered', 'pixels exist, no sign-off'],
    ['approval_stale', 'Approval stale', 'frames changed after sign-off'],
    ['approved', 'Approved', 'schedule.py will accept this'],
    ['published', 'Published', 'archive it now'],
  ];
  const week = S.state.week_issues || [];
  $('#pipeline').innerHTML = cols.map(([k, title, sub]) => {
    const items = S.state.sequences.filter(s => s.state === k);
    return `<div class="pipecol">
      <h3>${title}<span class="count">${items.length}</span></h3>
      <div class="sub">${sub}</div>
      ${items.map(s => `<div class="seqcard" data-slug="${esc(s.slug)}" style="margin-bottom:8px">
        <div class="t">${esc(s.slug)}</div>
        <div class="m"><span>${s.frame_count} frames</span>
          <span class="chip">${esc(s.type)}</span>
          ${s.error_count ? `<span class="chip red">${s.error_count} err</span>` : ''}
          ${(s.hand_post_only || []).length ? '<span class="chip amber">hand</span>' : ''}</div>
      </div>`).join('') || '<div class="empty">-</div>'}
    </div>`;
  }).join('') + (week.length ? `
    <div style="grid-column:1/-1" class="block">
      <h3>Batch check</h3>
      ${week.map(i => `<div class="issue ${i.level}">
        <span class="rule">${esc(i.rule)}</span> &middot; ${esc(i.where)}<br>${esc(i.message)}
        ${i.span ? `<span class="span">&raquo; ${esc(i.span)}</span>` : ''}</div>`).join('')}
    </div>` : '');
  $$('#pipeline .seqcard').forEach(c => c.onclick = () => {
    S.slug = c.dataset.slug; S.frame = 1; setView('stories');
  });
}

/* ------------------------------------------------------------------ library */
function renderLibrary() {
  const art = S.state.artifacts, b = S.state.brand;
  $('#library').innerHTML = `
    <div class="block">
      <h3>Frame styles <span style="color:var(--text-3);font-weight:400">drawn, not photographed</span></h3>
      <p>There is no background library. Every frame is drawn from
      <code>config/brand.json</code>, which means a frame reproduces from its config and
      that one file - no photo to archive, no asset cooldown to police, and no stale
      image quietly changing what a published frame looked like.</p>
      <div class="kv" style="margin-top:14px">
        <div class="k">field</div>
        <div class="v">Teal, graph-paper grid, corner vignette, the small mark at the
          foot. The quiet default.</div>
        <div class="k">note</div>
        <div class="v">The same field plus the S45 lockup and the
          <code>${esc(b.field.kicker_text)}</code> kicker. Use it on frame 1 and on any
          frame carrying metrics.</div>
        <div class="k">panels</div>
        <div class="v">eyebrow &middot; metric row (max 3) &middot; bar or line chart
          &middot; WHAT CHANGED list (max 8) &middot; signal box. Set them per frame in
          <code>config.json</code>.</div>
        <div class="k">charts</div>
        <div class="v">Values live in the config and are drawn offline. Nothing is fetched
          at render time - a frame that phoned out for data could not be re-rendered
          identically months later.</div>
      </div>
    </div>
    <div class="block">
      <h3>Artifacts <span style="color:var(--text-3);font-weight:400">${art.length} files</span></h3>
      <p>Redacted before they enter the folder; originals stored somewhere else entirely.
      The renderer will only composite filenames from <code>assets/artifacts/</code> - that
      restriction is the structural block on a client screenshot ever reaching a frame.</p>
      <div class="grid" style="margin-top:16px">
        ${art.map(a => `<div class="asset art">
          <img loading="lazy" src="/api/asset/artifacts/${encodeURIComponent(a.name)}?w=300" alt="">
          <div class="meta"><div class="nm">${esc(a.name)}</div>
          <div class="ds">${esc(a.description)}</div></div></div>`).join('')}
      </div>
    </div>`;
}

/* ------------------------------------------------------------------ analytics */
function renderAnalytics() {
  const seqs = S.state.sequences;
  const byType = t => seqs.filter(s => s.type === t).length;
  const cta = byType('cta'), nonAsk = seqs.length - cta;
  const ratio = cta ? (nonAsk / cta) : nonAsk;
  const errs = seqs.reduce((a, s) => a + (s.error_count || 0), 0);
  const charted = seqs.filter(s => (s.config?.frames || []).some(f => f.chart)).length;
  const paneled = seqs.filter(s => (s.config?.frames || [])
    .some(f => f.metrics || f.bullets || f.signal)).length;
  const published = seqs.filter(s => s.state === 'published').length;
  const approved = seqs.filter(s => s.state === 'approved').length;

  const card = (k, v, s, cls = '') =>
    `<div class="card"><div class="k">${k}</div><div class="v ${cls}">${v}</div>
     <div class="s">${s}</div></div>`;

  $('#analytics').innerHTML = `
    <div class="cards">
      ${card('Sequences', seqs.length, `${byType('thesis')} thesis &middot;
        ${byType('private_markets')} private markets &middot; ${byType('build')} build &middot;
        ${cta} cta`)}
      ${card('Ask rhythm', cta ? `${ratio.toFixed(1)}:1` : 'no ask',
        'Target is 4 non-ask sequences for every 1 ask. An advisory firm that asks constantly reads as a brokerage pitch.',
        ratio >= 4 || !cta ? 'ok' : 'warn')}
      ${card('Validation errors', errs, errs ? 'Nothing with an error will render.'
        : 'Every config passes the scan.', errs ? 'bad' : 'ok')}
      ${card('Evidence frames', `${charted}/${seqs.length}`,
        `${paneled} carry a metric row, list or signal box. A chart is the strongest move
         available and it dulls with repetition - if every sequence has one, none of them
         land.`, charted && charted < seqs.length ? 'ok' : 'warn')}
      ${card('Awaiting approval', seqs.filter(s =>
        ['rendered', 'approval_stale'].includes(s.state)).length,
        'A rendered sequence is not publishable until a named human signs off on the exact pixels.')}
      ${card('Approved / published', `${approved} / ${published}`,
        'Archive each one immediately after publishing.')}
    </div>

    <div class="block">
      <h3>Cadence</h3>
      <p>One sequence a day, 5 to 7 frames, is the sane reading of "five a day". Five
      <i>sequences</i> a day - 25 to 35 frames - is a bad idea anywhere and worse here:
      completion collapses well before frame 25, and an advisory firm producing that volume
      reads as retail promotion.</p>
      <p>At one sequence a day the binding constraint is not the code, not Claude and no
      longer a photo library. It is topic supply and, for anything charted, verified
      numbers. There ${S.state.ideas.filter(i => i.status === 'queued').length === 1
        ? 'is' : 'are'}
      <b>${S.state.ideas.filter(i => i.status === 'queued').length}</b> topics queued.
      Before daily posting, write thirty.</p>
      <div class="bar"><i style="width:${Math.min(100,
        S.state.ideas.filter(i => i.status === 'queued').length / 30 * 100)}%"></i></div>
      <p style="font-size:11px;color:var(--text-3)">topic queue,
        ${S.state.ideas.filter(i => i.status === 'queued').length} of 30</p>
    </div>

    <div class="block">
      <h3>What this does not measure</h3>
      <p>Reach, completion, replies. Instagram is not an origination channel for s45 and
      this system does not pretend otherwise - mandates come from warm intros, promoter and
      founder networks, PE/VC relationships, and inbound to a named person. The objective is
      credibility and talent. The metric that matters is whether a founder landing on the
      profile in month four can read six months of thinking on demand, which is a question
      about Highlights, not about impressions.</p>
    </div>`;
}

/* ------------------------------------------------------------------ compliance */
function renderCompliance() {
  const p = S.state.policy, ib = S.state.identity_block, b = S.state.brand;
  $('#compliance').innerHTML = `
    <div class="block">
      <h3>Identity block</h3>
      <p>SEBI's February 2026 circular, effective 1 May 2026, requires regulated entities and
      their agents to display their SEBI-registered name and registration number on social
      media handle home pages and at the beginning of securities-market-related content,
      including in closed groups. Rendered onto frame 1 of every sequence from
      <code>policy.json</code>, at a fixed position and size. There is no config field for it
      and no way to switch it off - the point of fixing it is that it cannot be quietly
      shrunk on a frame someone wants to look cleaner.</p>
      <div class="idpreview">
        ${ib.lines.map((l, i) => `<div class="l${i + 1}">${esc(l)}</div>`).join('')
          || '<div class="l1" style="color:#f0a294">not set - renderer will refuse</div>'}
      </div>
      <div class="taglist">
        <span class="chip ${ib.ready ? 'green' : 'red'}">${ib.ready ? 'ready' : 'HARD STOP'}</span>
        <span class="chip ${S.state.entity_status_pending ? 'amber' : 'green'}">
          entity_status ${esc(p.entity_status)}</span>
      </div>
      ${!ib.ready ? `<p style="color:#f0a294">${esc(ib.reason)}</p>` : ''}
      <p style="font-size:11.5px">Also on the Instagram bio - budget the characters early.
      Also at the top of any WhatsApp broadcast; do not treat WhatsApp as the informal channel.</p>
    </div>

    <div class="block">
      <h3>Scope and proof</h3>
      <p>s45 talks about private markets only. That is not a stylistic preference; it is the
      boundary that keeps a promotional story frame from being read as a recommendation.
      Every config must carry <code>scope_attestation: private_markets_only</code>, and every
      block, source line and ask string is scanned against the terms and patterns below. A hit
      is a hard failure quoting the offending span.</p>
      <div class="kv">
        <div class="k">listed_security_commentary</div><div class="v">${p.listed_security_commentary_allowed ? 'allowed' : 'refused'}</div>
        <div class="k">client_proof</div><div class="v">${p.client_proof_allowed ? 'allowed' : 'refused'}</div>
        <div class="k">testimonials</div><div class="v">${p.testimonials_allowed ? 'allowed' : 'refused'}</div>
        <div class="k">keyword_ctas</div><div class="v">${p.keyword_ctas_allowed ? 'allowed' : 'refused'}</div>
        <div class="k">creator_collaborations</div><div class="v">${p.creator_collaborations_allowed ? 'allowed' : 'refused'}</div>
        <div class="k">asset cooldown</div><div class="v">${p.asset_cooldown_days} days</div>
        <div class="k">retention</div><div class="v">${p.retention_days} days</div>
        <div class="k">approvers</div><div class="v">${(p.approvers || []).map(esc).join(', ')}</div>
      </div>
      <div class="taglist">${(p.banned_terms || []).map(t =>
        `<span class="chip red">${esc(t)}</span>`).join('')}</div>
      <div class="taglist">${(p.banned_patterns || []).map(t =>
        `<span class="chip red">${esc(t)}</span>`).join('')}</div>
      <p style="font-size:11.5px;color:var(--text-3)">Maintain the pattern list as counsel
      advises; treat it as a floor, not a guarantee. This file is not legal advice.</p>
    </div>

    <div class="block">
      <h3>Disclosure lines</h3>
      <p>Baked into the pixels so they survive scheduling. Fixed size and contrast, never at a
      size or contrast that reads as hidden.</p>
      <div class="kv">
        <div class="k">statistic</div><div class="v">${esc(p.disclosure_lines.statistic)}</div>
        <div class="k">cta</div><div class="v">${esc(p.disclosure_lines.cta)}</div>
      </div>
    </div>

    <div class="block">
      <h3>Brand</h3>
      <div class="kv">
        <div class="k">canvas</div><div class="v">${b.canvas.width} x ${b.canvas.height}</div>
        <div class="k">accent</div><div class="v">rgb(${b.colors.accent.join(', ')})
          <span style="display:inline-block;width:34px;height:11px;border-radius:3px;
          background:rgb(${b.colors.accent.join(',')});vertical-align:middle;margin-left:8px"></span></div>
        <div class="k">type scale</div><div class="v">${Object.entries(b.type_scale)
          .map(([k, v]) => `${k} ${v}`).join(' &middot; ')}</div>
        <div class="k">field</div><div class="v">teal rgb(${b.colors.field_base.slice(0, 3).join(', ')})
          <span style="display:inline-block;width:34px;height:11px;border-radius:3px;
          background:rgb(${b.colors.field_base.slice(0, 3).join(',')});vertical-align:middle;
          margin-left:8px"></span> - grid every ${b.field.grid_spacing}px</div>
        <div class="k">identity block</div><div class="v">${b.identity_block.position}
          at ${b.identity_block.x},${b.identity_block.y} - not overridable</div>
      </div>
      <p style="font-size:11.5px;color:var(--text-3)">Edit <code>config/brand.json</code> and
      <code>config/policy.json</code> directly, then re-render. You are setting taste once.</p>
    </div>`;
}

/* ------------------------------------------------------------------ modal */
function modal(title, body, foot) {
  $('#modalTitle').textContent = title;
  $('#modalBody').innerHTML = body;
  $('#modalFoot').innerHTML = (foot || '') +
    '<button class="btn ghost" id="mCancel">Close</button>';
  $('#modalBack').classList.add('on');
  $('#mCancel').onclick = closeModal;
}
const closeModal = () => $('#modalBack').classList.remove('on');

/* ------------------------------------------------------------------ boot */
$('#nav').onclick = (e) => {
  const b = e.target.closest('.navitem'); if (b) setView(b.dataset.view);
};
$$('[data-view-jump]').forEach(b => b.onclick = () => setView(b.dataset.viewJump));
$('#newSeqBtn').onclick = () => newSequenceModal(null);
$('#queueIdeaBtn').onclick = queueIdeaModal;
$('#renderAllBtn').onclick = renderAllFrames;
$('#postOrderBtn').onclick = showPostOrder;
$('#approveBtn').onclick = approveModal;
$('#scheduleBtn').onclick = scheduleModal;
$('#modalClose').onclick = closeModal;
$('#modalBack').onclick = (e) => { if (e.target.id === 'modalBack') closeModal(); };
document.addEventListener('keydown', (e) => {
  if (e.key === 'Escape') closeModal();
  if (e.target.matches('input, textarea, select')) return;
  const s = seq(); if (!s) return;
  if (e.key === 'ArrowRight') { S.frame = Math.min(s.config.frames.length, S.frame + 1); renderStage(); renderEditor(); }
  if (e.key === 'ArrowLeft')  { S.frame = Math.max(1, S.frame - 1); renderStage(); renderEditor(); }
});

load();
