(() => {
  'use strict';

  const rawEl = document.getElementById('corpus-data');
  if (!rawEl) return;
  // Compact tuple format: [id, title, views, yyyymm, catCode, isLegacy, author, intro]
  // catCode: 0=ARTICLE, 1=WIKI, 2=FAQ
  const DATA = JSON.parse(rawEl.textContent);
  const CAT_LABEL = ['', '专栏', '问答'];
  const PAGE_SIZE = 80;

  const qEl = document.getElementById('q');
  const yrEl = document.getElementById('fYear');
  const catEl = document.getElementById('fCat');
  const sortEl = document.getElementById('fSort');
  const fcEl = document.getElementById('fc');
  const tbody = document.getElementById('idxBody');
  const prevBtn = document.getElementById('prevPage');
  const nextBtn = document.getElementById('nextPage');
  const pageInfo = document.getElementById('pageInfo');

  // Populate years
  const years = [...new Set(DATA.map(d => d[3].slice(0, 4)).filter(Boolean))].sort().reverse();
  years.forEach(y => {
    const o = document.createElement('option');
    o.value = y;
    o.textContent = y + ' 年';
    yrEl.appendChild(o);
  });

  // Precompute lowercase searchable text (title + author + intro)
  const LOWER = DATA.map(d => ((d[1] || '') + ' ' + (d[6] || '') + ' ' + (d[7] || '')).toLowerCase());

  let filtered = DATA.map((_, i) => i);
  let page = 1;

  function esc(s) {
    return s.replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  }

  function applyFilter() {
    const terms = (qEl.value || '').trim().toLowerCase().split(/\s+/).filter(Boolean);
    const y = yrEl.value;
    const c = catEl.value;
    const out = [];
    for (let i = 0; i < DATA.length; i++) {
      const d = DATA[i];
      if (y && !d[3].startsWith(y)) continue;
      if (c === 'LEGACY' && !d[5]) continue;
      if (c === 'NEW' && d[5]) continue;
      if (c === 'WIKI' && d[4] !== 1) continue;
      if (c === 'FAQ' && d[4] !== 2) continue;
      if (terms.length) {
        const hay = LOWER[i];
        let ok = true;
        for (let k = 0; k < terms.length; k++) {
          if (!hay.includes(terms[k])) { ok = false; break; }
        }
        if (!ok) continue;
      }
      out.push(i);
    }

    const s = sortEl.value;
    if (s === 'views') out.sort((a, b) => DATA[b][2] - DATA[a][2]);
    else if (s === 'newest') out.sort((a, b) => (DATA[b][3] > DATA[a][3] ? 1 : DATA[b][3] < DATA[a][3] ? -1 : DATA[b][0] - DATA[a][0]));
    else if (s === 'oldest') out.sort((a, b) => (DATA[a][3] > DATA[b][3] ? 1 : DATA[a][3] < DATA[b][3] ? -1 : DATA[a][0] - DATA[b][0]));

    filtered = out;
    page = 1;
    render();
  }

  function render() {
    const total = filtered.length;
    const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));
    if (page > pages) page = pages;
    const start = (page - 1) * PAGE_SIZE;
    const end = Math.min(total, start + PAGE_SIZE);

    fcEl.textContent = `命中 ${total.toLocaleString()} / ${DATA.length.toLocaleString()} 帖`;
    pageInfo.textContent = `${page} / ${pages}`;
    prevBtn.disabled = page <= 1;
    nextBtn.disabled = page >= pages;

    if (!total) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align:center;padding:32px;color:var(--muted)">没有匹配的帖子，试试减少或更换关键词</td></tr>';
      return;
    }

    const html = [];
    for (let i = start; i < end; i++) {
      const [id, title, views, ym, catCode, isLeg] = DATA[filtered[i]];
      const badge = CAT_LABEL[catCode]
        ? `<span class="cc">${CAT_LABEL[catCode]}</span>`
        : (isLeg ? '<span class="cc" style="opacity:.65">远古</span>' : '');
      html.push(
        `<tr>` +
        `<td class="n">${esc(ym)}</td>` +
        `<td class="ti"><a href="https://bbs.robomaster.com/article/${id}" target="_blank" rel="noopener">${esc(title)}</a>${badge}</td>` +
        `<td class="n">${views.toLocaleString()}</td>` +
        `<td class="lk"><a href="https://bbs.robomaster.com/article/${id}" target="_blank" rel="noopener">${id}</a></td>` +
        `</tr>`
      );
    }
    tbody.innerHTML = html.join('');
  }

  let tm = null;
  qEl.addEventListener('input', () => { clearTimeout(tm); tm = setTimeout(applyFilter, 90); });
  yrEl.addEventListener('change', applyFilter);
  catEl.addEventListener('change', applyFilter);
  sortEl.addEventListener('change', applyFilter);
  prevBtn.addEventListener('click', () => { if (page > 1) { page--; render(); window.scrollTo({ top: 0, behavior: 'smooth' }); } });
  nextBtn.addEventListener('click', () => { page++; render(); window.scrollTo({ top: 0, behavior: 'smooth' }); });

  applyFilter();
})();
