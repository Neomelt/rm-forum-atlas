(() => {
  'use strict';

  /* ---------- 1. Faction Switcher (金色十年 / 红方 / 蓝方) ---------- */
  const FACTIONS = {
    gold: { hex: '#F0B93A', rgb: [240, 185, 58], core: '#FFF5D1' },
    red:  { hex: '#F0444C', rgb: [240, 68, 76],  core: '#FFD6D8' },
    blue: { hex: '#3B9EFF', rgb: [59, 158, 255], core: '#D6ECFF' }
  };
  let curFaction = localStorage.getItem('rm_faction') || 'gold';
  if (!FACTIONS[curFaction]) curFaction = 'gold';

  function applyFaction(f) {
    curFaction = f;
    document.documentElement.setAttribute('data-faction', f);
    localStorage.setItem('rm_faction', f);
    document.querySelectorAll('.fbtn').forEach(b => b.classList.toggle('on', b.dataset.f === f));
  }
  applyFaction(curFaction);
  document.querySelectorAll('.fbtn').forEach(b => {
    b.addEventListener('click', () => applyFaction(b.dataset.f));
  });

  /* ---------- 2. Scroll Energy Bar, Background Dimming & Beyblade Top ---------- */
  const energyFill = document.getElementById('energyFill');
  const topBtn = document.getElementById('beybladeTop');
  function onScroll() {
    const y = window.scrollY;
    const h = document.documentElement.scrollHeight - window.innerHeight;
    const pct = h > 0 ? Math.min(100, Math.max(0, (y / h) * 100)) : 0;
    if (energyFill) energyFill.style.width = pct.toFixed(1) + '%';
    if (topBtn) topBtn.classList.toggle('show', y > 360);
    document.body.classList.toggle('scrolled', y > 180);
  }
  window.addEventListener('scroll', onScroll, { passive: true });
  onScroll();

  if (topBtn) {
    topBtn.addEventListener('click', () => {
      topBtn.classList.add('spinning');
      window.scrollTo({ top: 0, behavior: 'smooth' });
      setTimeout(() => topBtn.classList.remove('spinning'), 800);
    });
  }

  /* ---------- 3. Primary Workspace View Switcher ---------- */
  const vtabs = [...document.querySelectorAll('.vtab')];
  const vpanels = [...document.querySelectorAll('.view-panel')];
  function switchView(name, updateHash) {
    if (!vpanels.some(p => p.dataset.view === name)) return;
    vtabs.forEach(t => t.classList.toggle('on', t.dataset.view === name));
    vpanels.forEach(p => p.classList.toggle('on', p.dataset.view === name));
    if (updateHash) history.replaceState(null, '', '#' + name);
  }
  if (vtabs.length) {
    vtabs.forEach(t => t.addEventListener('click', () => switchView(t.dataset.view, true)));
    const initHash = location.hash.replace('#', '');
    if (initHash) switchView(initHash, false);
  }

  /* ---------- 4. Sub-tabs (Rankings & Legacy Eras) ---------- */
  document.querySelectorAll('[data-subgroup]').forEach(group => {
    const name = group.dataset.subgroup;
    const btns = group.querySelectorAll('.sub-btn');
    btns.forEach(btn => {
      btn.addEventListener('click', () => {
        btns.forEach(b => b.classList.remove('on'));
        btn.classList.add('on');
        const key = btn.dataset.sub;
        document.querySelectorAll(`[data-subpanel="${name}"]`).forEach(p => {
          p.classList.toggle('on', p.dataset.key === key);
        });
      });
    });
  });

  /* ---------- 5. Catalog Sidebar + Real-time Search ---------- */
  const catApp = document.getElementById('catalogApp');
  if (catApp) {
    const sideBtns = [...catApp.querySelectorAll('.cat-side-btn')];
    const entries = [...catApp.querySelectorAll('.entry')];
    const qInput = document.getElementById('catSearch');
    const countEl = document.getElementById('catCount');
    const emptyEl = document.getElementById('catEmpty');
    let curCat = 'ALL';

    function runFilter() {
      const terms = (qInput.value || '').trim().toLowerCase().split(/\s+/).filter(Boolean);
      let shown = 0;
      entries.forEach(el => {
        const okCat = curCat === 'ALL' || el.dataset.cat === curCat;
        const okQ = !terms.length || terms.every(w => el.dataset.hay.includes(w));
        const ok = okCat && okQ;
        el.style.display = ok ? '' : 'none';
        if (ok) shown++;
      });
      if (countEl) countEl.textContent = `${shown} / ${entries.length} 项`;
      if (emptyEl) emptyEl.style.display = shown ? 'none' : 'block';
    }

    sideBtns.forEach(b => {
      b.addEventListener('click', () => {
        sideBtns.forEach(x => x.classList.remove('on'));
        b.classList.add('on');
        curCat = b.dataset.cat;
        runFilter();
      });
    });
    let tm = null;
    qInput.addEventListener('input', () => { clearTimeout(tm); tm = setTimeout(runFilter, 70); });
  }

  /* ---------- 6. SVG Chart Hover Tooltip ---------- */
  const tip = document.getElementById('hudTip');
  if (tip) {
    document.querySelectorAll('.hit[data-tip]').forEach(el => {
      el.addEventListener('mouseenter', e => {
        tip.innerHTML = el.dataset.tip;
        tip.classList.add('show');
        tip.style.left = e.clientX + 'px';
        tip.style.top = e.clientY + 'px';
      });
      el.addEventListener('mousemove', e => {
        tip.style.left = e.clientX + 'px';
        tip.style.top = e.clientY + 'px';
      });
      el.addEventListener('mouseleave', () => tip.classList.remove('show'));
    });
  }

  /* ---------- 7. High-Fidelity RoboMaster Big Rune Canvas ---------- */
  const canvas = document.getElementById('runeCanvas');
  if (canvas) {
    const ctx = canvas.getContext('2d');
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const hudSpd = document.getElementById('runeSpd');
    const hudHit = document.getElementById('runeHit');

    const DPR = Math.min(window.devicePixelRatio || 1, 2);
    const SIZE = 360;
    canvas.width = SIZE * DPR;
    canvas.height = SIZE * DPR;
    ctx.scale(DPR, DPR);

    const CX = SIZE / 2, CY = SIZE / 2;
    const ARM_LEN = 122;
    const TARGET_R = 31;

    // Official RM big rune sinusoidal angular velocity
    const A = 0.88, W0 = 1.92, B = 2.09 - A;
    let angle = -Math.PI / 2;
    let t = 0;
    let lastTs = performance.now();

    let blades = [0, 0, 0, 0, 0];
    let hitCount = 0;
    // 5-blade activation blink state: 3 blinks at ~2.5Hz (0.4s per cycle) + 0.5s hold
    let blinkTimer = 0;
    const BLINK_CYCLES = 3;
    const BLINK_PERIOD = 0.4; // 2.5 Hz
    const BLINK_TOTAL = BLINK_CYCLES * BLINK_PERIOD + 0.5;
    let hitPop = null;
    let mouse = { x: CX, y: CY, inside: false };

    function refillPending() {
      let activePending = blades.filter(s => s === 1).length;
      while (activePending < 2) {
        const unlit = blades.map((s, i) => s === 0 ? i : -1).filter(i => i >= 0);
        if (!unlit.length) break;
        const pick = unlit[Math.floor(Math.random() * unlit.length)];
        blades[pick] = 1;
        activePending++;
      }
    }

    function resetRune() {
      blades = [0, 0, 0, 0, 0];
      hitCount = 0;
      refillPending();
      if (hudHit) hudHit.textContent = '0/5';
    }
    resetRune();

    function getTargetPos(idx) {
      const a = angle + idx * (Math.PI * 2 / 5);
      return { x: CX + Math.cos(a) * ARM_LEN, y: CY + Math.sin(a) * ARM_LEN };
    }

    canvas.addEventListener('mouseenter', () => { mouse.inside = true; });
    canvas.addEventListener('mouseleave', () => { mouse.inside = false; });
    canvas.addEventListener('mousemove', e => {
      const r = canvas.getBoundingClientRect();
      mouse.x = (e.clientX - r.left) * (SIZE / r.width);
      mouse.y = (e.clientY - r.top) * (SIZE / r.height);
    });
    canvas.addEventListener('click', e => {
      if (blinkTimer > 0) return;
      const r = canvas.getBoundingClientRect();
      const mx = (e.clientX - r.left) * (SIZE / r.width);
      const my = (e.clientY - r.top) * (SIZE / r.height);
      let bestIdx = -1, bestDist = Infinity, bestPos = null;
      for (let i = 0; i < 5; i++) {
        if (blades[i] !== 1) continue;
        const tp = getTargetPos(i);
        const dist = Math.hypot(mx - tp.x, my - tp.y);
        if (dist <= TARGET_R * 1.2 && dist < bestDist) {
          bestIdx = i; bestDist = dist; bestPos = tp;
        }
      }
      if (bestIdx >= 0) {
        const ring = Math.max(1, Math.min(10, Math.round(10 - (bestDist / TARGET_R) * 8)));
        blades[bestIdx] = 2;
        hitCount++;
        hitPop = { x: bestPos.x, y: bestPos.y, text: ring + ' 环', alpha: 1.0 };
        if (hitCount >= 5) {
          blinkTimer = BLINK_TOTAL;
          if (hudHit) hudHit.textContent = '5/5 已激活';
        } else {
          if (hudHit) hudHit.textContent = hitCount + '/5';
          refillPending();
        }
      }
    });

    function drawBlade(idx, state, col, nowSec) {
      const a = angle + idx * (Math.PI * 2 / 5);
      const [cr, cg, cb] = col.rgb;
      ctx.save();
      ctx.translate(CX, CY);
      ctx.rotate(a);

      ctx.beginPath();
      ctx.moveTo(25, -9);
      ctx.lineTo(ARM_LEN - 25, -14);
      ctx.lineTo(ARM_LEN - 25, 14);
      ctx.lineTo(25, 9);
      ctx.closePath();
      ctx.fillStyle = 'rgba(10,12,17,0.88)';
      ctx.fill();
      ctx.strokeStyle = state > 0 ? `rgba(${cr},${cg},${cb},0.48)` : 'rgba(255,255,255,0.10)';
      ctx.lineWidth = 1.1;
      ctx.stroke();

      if (state === 1) {
        const flow = (nowSec * 1.15) % 1;
        for (let k = 0; k < 5; k++) {
          const p = ((k / 5) + flow) % 1;
          const x = 30 + p * (ARM_LEN - 62);
          const alpha = Math.sin(p * Math.PI) * 0.95;
          ctx.save();
          ctx.strokeStyle = `rgba(${cr},${cg},${cb},${alpha.toFixed(2)})`;
          ctx.shadowColor = col.hex;
          ctx.shadowBlur = 10;
          ctx.lineWidth = 2.4;
          ctx.beginPath();
          ctx.moveTo(x - 5, -5.5);
          ctx.lineTo(x + 2, 0);
          ctx.lineTo(x - 5, 5.5);
          ctx.stroke();
          ctx.strokeStyle = `rgba(255,255,255,${(alpha * 0.7).toFixed(2)})`;
          ctx.lineWidth = 1;
          ctx.stroke();
          ctx.restore();
        }
      } else if (state === 2) {
        ctx.save();
        ctx.shadowColor = col.hex;
        ctx.shadowBlur = 14;
        ctx.strokeStyle = col.hex;
        ctx.lineWidth = 3.8;
        ctx.beginPath();
        ctx.moveTo(30, 0);
        ctx.lineTo(ARM_LEN - 32, 0);
        ctx.stroke();
        ctx.strokeStyle = col.core;
        ctx.lineWidth = 1.5;
        ctx.stroke();
        ctx.restore();
      } else {
        ctx.strokeStyle = 'rgba(255,255,255,0.06)';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(32, 0);
        ctx.lineTo(ARM_LEN - 34, 0);
        ctx.stroke();
      }

      ctx.translate(ARM_LEN, 0);
      ctx.beginPath();
      for (let i = 0; i < 8; i++) {
        const ang = (i * Math.PI / 4) + Math.PI / 8;
        const rr = TARGET_R + 3.5;
        const px = Math.cos(ang) * rr, py = Math.sin(ang) * rr;
        i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
      }
      ctx.closePath();
      ctx.fillStyle = 'rgba(9,11,16,0.92)';
      ctx.fill();
      ctx.lineWidth = state > 0 ? 2 : 1;
      ctx.strokeStyle = state > 0 ? col.hex : 'rgba(255,255,255,0.14)';
      if (state > 0) {
        ctx.save();
        ctx.shadowColor = col.hex;
        ctx.shadowBlur = state === 2 ? 18 : 11 + 4 * Math.sin(nowSec * 7);
        ctx.stroke();
        ctx.restore();
      } else {
        ctx.stroke();
      }

      [25, 19, 13, 7.5, 3].forEach((rad, ri) => {
        ctx.beginPath();
        ctx.arc(0, 0, rad, 0, Math.PI * 2);
        if (state === 2) {
          ctx.strokeStyle = ri % 2 === 0 ? col.hex : col.core;
          ctx.lineWidth = ri === 4 ? 2.2 : 1.3;
        } else if (state === 1) {
          ctx.strokeStyle = ri === 0 || ri === 4
            ? col.hex
            : `rgba(${cr},${cg},${cb},${(0.32 + 0.24 * Math.sin(nowSec * 6 - ri)).toFixed(2)})`;
          ctx.lineWidth = ri === 0 ? 1.8 : 1.1;
        } else {
          ctx.strokeStyle = 'rgba(255,255,255,0.08)';
          ctx.lineWidth = 1;
        }
        ctx.stroke();
      });
      ctx.restore();
    }

    function drawCenterR(col, nowSec) {
      const [cr, cg, cb] = col.rgb;
      ctx.save();
      ctx.translate(CX, CY);
      ctx.beginPath();
      ctx.arc(0, 0, 24, 0, Math.PI * 2);
      ctx.fillStyle = '#080A0F';
      ctx.fill();
      ctx.lineWidth = 1.8;
      ctx.strokeStyle = `rgba(${cr},${cg},${cb},0.65)`;
      ctx.shadowColor = col.hex;
      ctx.shadowBlur = 12 + 4 * Math.sin(nowSec * 3);
      ctx.stroke();

      ctx.shadowBlur = 10;
      ctx.fillStyle = col.core;
      ctx.font = '900 20px "Noto Sans SC", sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText('R', 0, 1);
      ctx.restore();
    }

    function drawReticle(tp, col) {
      const box = TARGET_R + 9;
      ctx.save();
      ctx.translate(tp.x, tp.y);
      ctx.strokeStyle = col.core;
      ctx.lineWidth = 1.5;
      ctx.shadowColor = col.hex;
      ctx.shadowBlur = 8;
      const L = 9;
      [[-1,-1],[1,-1],[1,1],[-1,1]].forEach(([sx, sy]) => {
        ctx.beginPath();
        ctx.moveTo(sx * box, sy * (box - L));
        ctx.lineTo(sx * box, sy * box);
        ctx.lineTo(sx * (box - L), sy * box);
        ctx.stroke();
      });
      ctx.restore();
    }

    function frame(ts) {
      const dt = Math.min(0.05, (ts - lastTs) / 1000);
      lastTs = ts;
      const nowSec = ts / 1000;
      const col = FACTIONS[curFaction];

      let omega = 0.35;
      if (!reduced) {
        t += dt;
        omega = A * Math.sin(W0 * t) + B;
        angle += omega * 0.40 * dt;
      }
      if (hudSpd && Math.floor(ts / 140) !== Math.floor((ts - dt * 1000) / 140)) {
        hudSpd.textContent = omega.toFixed(2) + ' rad/s';
      }

      ctx.clearRect(0, 0, SIZE, SIZE);
      const [cr, cg, cb] = col.rgb;

      // Determine whether blades are visible during 3-blink celebration
      let blinkOn = true;
      if (blinkTimer > 0) {
        const elapsed = BLINK_TOTAL - blinkTimer;
        if (elapsed < BLINK_CYCLES * BLINK_PERIOD) {
          blinkOn = (elapsed % BLINK_PERIOD) < (BLINK_PERIOD * 0.52);
        } else {
          blinkOn = true;
        }
        blinkTimer -= dt;
        if (blinkTimer <= 0) {
          blinkTimer = 0;
          resetRune();
        }
      }

      const grad = ctx.createRadialGradient(CX, CY, 10, CX, CY, 165);
      const bgGlow = blinkTimer > 0 ? (blinkOn ? 0.26 : 0.03) : 0.09;
      grad.addColorStop(0, `rgba(${cr},${cg},${cb},${bgGlow})`);
      grad.addColorStop(1, 'rgba(0,0,0,0)');
      ctx.fillStyle = grad;
      ctx.fillRect(0, 0, SIZE, SIZE);

      for (let i = 0; i < 5; i++) {
        const st = blinkTimer > 0 ? (blinkOn ? 2 : 0) : blades[i];
        drawBlade(i, st, col, nowSec);
      }
      drawCenterR(col, nowSec);
      if (blinkTimer === 0 && mouse.inside) {
        let nearest = null, minDist = Infinity;
        for (let i = 0; i < 5; i++) {
          if (blades[i] !== 1) continue;
          const tp = getTargetPos(i);
          const d = Math.hypot(mouse.x - tp.x, mouse.y - tp.y);
          if (d < minDist) { minDist = d; nearest = tp; }
        }
        if (nearest) drawReticle(nearest, col);
      }

      if (hitPop) {
        ctx.save();
        ctx.fillStyle = `rgba(255,255,255,${hitPop.alpha.toFixed(2)})`;
        ctx.shadowColor = col.hex;
        ctx.shadowBlur = 10;
        ctx.font = '700 13px "Noto Sans SC", sans-serif';
        ctx.textAlign = 'center';
        ctx.fillText(hitPop.text, hitPop.x, hitPop.y - (1 - hitPop.alpha) * 24);
        ctx.restore();
        hitPop.alpha -= dt * 1.4;
        if (hitPop.alpha <= 0) hitPop = null;
      }
      requestAnimationFrame(frame);
    }
    requestAnimationFrame(frame);
  }
})();
