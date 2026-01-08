
(() => {
  const container = document.getElementById("paper-container");
  const overlay = document.getElementById("lasso-overlay");
  const savedOverlay = document.getElementById("saved-overlay");
  const modal = document.getElementById("meta-modal");
  const form = document.getElementById("meta-form");
  const cancel = document.getElementById("cancel-meta");
  const btnAIDraw = document.getElementById("btn-ai-draw");
  const btnAIAuto = document.getElementById("btn-ai-draw-auto");
  const btnGadzira = document.getElementById("btn-gadzira");
  const contentClose = document.getElementById('content-close');
  const conditionalFields = Array.from(form?.querySelectorAll('.conditional-field') || []);
  const boxesList = document.getElementById('boxes-list');
  if (btnAIAuto && !btnAIAuto.dataset.originalLabel) {
    btnAIAuto.dataset.originalLabel = btnAIAuto.textContent?.trim() || 'Auto Draw All';
  }

  let startX = 0, startY = 0, rectEl = null, dragging = false;
  let lastBox = null;

  // --- Debug helper ---
  const DBG = (...args) => { try { console.log('[LASSO]', ...args); } catch (_) { } };
  DBG('init', { hasContainer: !!container, hasOverlay: !!overlay });

  // --- Lightweight notifications & spinner ---
  function ensureToastHost() {
    let host = document.getElementById('toast-host');
    if (!host) {
      host = document.createElement('div');
      host.id = 'toast-host';
      Object.assign(host.style, {
        position: 'fixed', right: '16px', bottom: '16px', zIndex: 9999,
        display: 'grid', gap: '8px', maxWidth: '360px'
      });
      document.body.appendChild(host);
    }
    return host;
  }
  function toast(msg, type = 'info', timeoutMs = 3000) {
    const host = ensureToastHost();
    const el = document.createElement('div');
    const bg = type === 'error' ? '#fee2e2' : (type === 'success' ? '#dcfce7' : '#eff6ff');
    const fg = type === 'error' ? '#991b1b' : (type === 'success' ? '#065f46' : '#1e3a8a');
    Object.assign(el.style, {
      background: bg, color: fg, border: '1px solid rgba(0,0,0,.08)',
      borderRadius: '8px', padding: '10px 12px', boxShadow: '0 2px 8px rgba(0,0,0,.15)',
      fontSize: '14px', lineHeight: '1.3',
    });
    el.textContent = String(msg || '');
    host.appendChild(el);
    setTimeout(() => { el.remove(); }, timeoutMs);
  }
  function ensureSpinner() {
    let sp = document.getElementById('ai-spinner');
    if (!sp) {
      sp = document.createElement('div'); sp.id = 'ai-spinner';
      Object.assign(sp.style, {
        position: 'fixed', inset: 0, background: 'rgba(15,23,42,.25)',
        display: 'none', alignItems: 'center', justifyContent: 'center', zIndex: 9998
      });
      const card = document.createElement('div');
      Object.assign(card.style, {
        background: '#fff', borderRadius: '10px', padding: '14px 16px',
        display: 'flex', alignItems: 'center', gap: '10px', border: '1px solid #e5e7eb',
        boxShadow: '0 8px 24px rgba(0,0,0,.25)'
      });
      const dot = document.createElement('div');
      Object.assign(dot.style, {
        width: '12px', height: '12px', borderRadius: '999px', background: '#2563eb',
        animation: 'ai-bounce 0.9s infinite alternate'
      });
      const txt = document.createElement('div'); txt.id = 'ai-spinner-text'; txt.textContent = 'Processing...';
      Object.assign(txt.style, { fontSize: '14px', color: '#111827' });
      const style = document.createElement('style');
      style.textContent = '@keyframes ai-bounce { from { transform: translateY(0) } to { transform: translateY(-6px) } }';
      card.appendChild(dot); card.appendChild(txt); sp.appendChild(card); document.body.appendChild(style); document.body.appendChild(sp);
    }
    return sp;
  }
  function showSpinner(text) {
    const sp = ensureSpinner();
    const txt = document.getElementById('ai-spinner-text');
    if (txt && text) txt.textContent = text;
    sp.style.display = 'flex';
  }
  function hideSpinner() {
    const sp = ensureSpinner();
    sp.style.display = 'none';
  }


  const escapeHtml = (value = '') => String(value)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

  function formatSummary(dataset) {
    const parts = [`Q: ${dataset.qn || 'n/a'}`];
    if (dataset.parentNumber) {
      parts.push(`Parent: ${dataset.parentNumber}`);
    }
    parts.push(`Marks: ${dataset.marks || 'n/a'}`);
    return parts.map(escapeHtml).join(' &bull; ');
  }

  function renderMetaHtml(dataset, created) {
    const x = Math.round(parseFloat(dataset.x ?? '0') || 0);
    const y = Math.round(parseFloat(dataset.y ?? '0') || 0);
    const w = Math.round(parseFloat(dataset.w ?? '0') || 0);
    const h = Math.round(parseFloat(dataset.h ?? '0') || 0);
    const parts = [`<div class="kv">x=${x}, y=${y}, w=${w}, h=${h}</div>`];
    if (dataset.parentNumber) {
      parts.push(`<div class="kv">Parent: ${escapeHtml(dataset.parentNumber)}</div>`);
    }
    if (dataset.headerLabel) {
      parts.push(`<div class="kv">Header: ${escapeHtml(dataset.headerLabel)}</div>`);
    }
    if (dataset.caseLabel) {
      parts.push(`<div class="kv">Case study: ${escapeHtml(dataset.caseLabel)}</div>`);
    }
    const sourceCreated = created || dataset.createdAt || '';
    if (sourceCreated) {
      let display = sourceCreated;
      try {
        const d = new Date(sourceCreated);
        if (!Number.isNaN(d.getTime())) {
          display = d.toLocaleString();
        }
      } catch (_) { }
      parts.push(`<div class="kv">${escapeHtml(display)}</div>`);
    }
    return parts.join('');
  }

  function applyBoxDataset(element, payload) {
    if (!element || !payload) return;
    const ds = element.dataset;
    ds.x = String(payload.x ?? ds.x ?? 0);
    ds.y = String(payload.y ?? ds.y ?? 0);
    ds.w = String(payload.w ?? ds.w ?? 0);
    ds.h = String(payload.h ?? ds.h ?? 0);
    ds.qn = payload.question_number || ds.qn || '';
    ds.marks = payload.marks || ds.marks || '';
    ds.qtype = payload.qtype || ds.qtype || '';
    ds.parentNumber = payload.parent_number || ds.parentNumber || '';
    ds.headerLabel = payload.header_label || ds.headerLabel || '';
    ds.caseLabel = payload.case_study_label || ds.caseLabel || '';
    ds.content = payload.content || ds.content || '';
    ds.ctype = payload.content_type || ds.ctype || '';
    ds.createdAt = payload.created_at || ds.createdAt || '';

    const summary = element.querySelector('summary .kv');
    if (summary) {
      summary.innerHTML = formatSummary(ds);
    }
    const meta = element.querySelector('.box-meta');
    if (meta) {
      meta.innerHTML = renderMetaHtml(ds, payload.created_at);
    }
  }

  function setAIDrawMode(mode) {
    if (!btnAIDraw) return;
    if (mode === 'resume') {
      btnAIDraw.dataset.mode = 'resume';
      btnAIDraw.textContent = 'Continue AI Suggestions';
    } else {
      btnAIDraw.dataset.mode = 'fetch';
      btnAIDraw.textContent = 'Draw Blocks with AI';
    }
  }

  setAIDrawMode('fetch');

  function notifyAIStrategy(strategy) {
    const mode = (strategy || '').toLowerCase();
    if (mode === 'gemini') {
      toast('Using Gemini to suggest blocks', 'info', 2300);
    } else if (mode === 'ollama') {
      toast('Using local LLM suggestions', 'info', 2300);
    } else if (mode === 'gadzira') {
      toast('Using Gadzira heuristics', 'info', 2300);
    } else if (mode) {
      toast(`AI mode: ${mode}`, 'info', 2300);
    } else {
      toast('AI unavailable - using heuristics', 'warning', 2800);
    }
  }

  function setAutoDrawButtonState(state) {
    if (!btnAIAuto) return;
    if (state === 'fetch') {
      btnAIAuto.disabled = true;
      btnAIAuto.textContent = 'Fetching AI...';
      btnAIAuto.dataset.state = 'fetch';
    } else if (state === 'run') {
      btnAIAuto.disabled = true;
      btnAIAuto.textContent = 'Auto Drawing...';
      btnAIAuto.dataset.state = 'run';
    } else {
      btnAIAuto.disabled = false;
      btnAIAuto.textContent = btnAIAuto.dataset.originalLabel || 'Auto Draw All';
      delete btnAIAuto.dataset.state;
    }
  }

  function finishAutoDraw(success, messageOverride) {
    const total = window.__aiTotal || 0;
    const saved = window.__autoDrawAllSaved || 0;
    const msg = messageOverride || (success ? `Auto draw complete (${saved}/${total} saved)` : '');
    if (msg) {
      toast(msg, success ? 'success' : 'info', success ? 2600 : 2300);
    }
    window.__autoDrawAllActive = false;
    window.__autoDrawAllSaved = 0;
    setAutoDrawButtonState('idle');
    if (btnAIDraw) btnAIDraw.disabled = false;
    setLLMStatus(false, 'Idle');
    if (window.__captureAllActive) {
      try {
        window.dispatchEvent(
          new CustomEvent('capture-all-finished', { detail: { success: !!success, saved, total } })
        );
        const btnCapture = document.getElementById('btn-capture-all');
        if (btnCapture) {
          btnCapture.disabled = false;
          btnCapture.textContent = btnCapture.dataset.originalLabel || 'Capture All';
          delete btnCapture.dataset.state;
        }
      } catch (_) { }
      window.__captureAllActive = false;
    }
  }

  function maybeAdvanceAISuggestions() {
    if (window.__aiQueue && window.__aiQueue.length) {
      setAIDrawMode('resume');
      setTimeout(() => processNextAIDraw(), 120);
    } else {
      window.__aiCurrent = null;
      window.__aiPaused = false;
      setLLMStatus(false, 'Idle');
      setAIDrawMode('fetch');
    }
  }

  window.__aiQueue = window.__aiQueue || [];
  window.__aiCurrent = window.__aiCurrent || null;
  window.__aiPaused = window.__aiPaused || false;
  window.__autoDrawAllActive = window.__autoDrawAllActive || false;
  window.__autoDrawAllSaved = window.__autoDrawAllSaved || 0;
  window.__captureAllActive = window.__captureAllActive || false;
  const AUTO_DRAW_DELAY_MS = 500;

  // --- LLM status button ---
  const llmStatus = document.getElementById('llm-status');
  function setLLMStatus(running, text) {
    if (!llmStatus) return;
    const label = `LLM: ${text || (running ? 'Running...' : 'Idle')}`;
    llmStatus.textContent = label;
    llmStatus.style.color = '#fff';
    llmStatus.style.transition = 'background .2s ease';
    llmStatus.style.background = running ? '#2563eb' : '#111';
  }
  try {
    document.getElementById('mbalaka-classify-form')?.addEventListener('submit', () => setLLMStatus(true, 'Classifying'));
  } catch (_) { }

  // Autoclassify buttons: show status/spinner until navigation
  try {
    const ac = document.getElementById('btn-autoclassify');
    const aci = document.getElementById('btn-autoclassify-instr');
    const onAClick = () => { setLLMStatus(true, 'Classifying'); showSpinner('Classifying...'); };
    ac?.addEventListener('click', onAClick);
    aci?.addEventListener('click', onAClick);
  } catch (_) { }

  const toLocal = (clientX, clientY) => {
    const r = container.getBoundingClientRect();
    return { x: clientX - r.left + container.scrollLeft, y: clientY - r.top + container.scrollTop };
  };

  // Enable pointer events on overlay so drawing works
  if (overlay) {
    overlay.style.pointerEvents = 'auto';
  }

  // Safety check: only add event listeners if container exists
  if (!container) {
    DBG('WARNING: paper-container not found, drawing disabled');
  }

  container?.addEventListener("mousedown", (e) => {
    if (e.button !== 0) return;
    dragging = true;
    const { x, y } = toLocal(e.clientX, e.clientY);
    startX = x; startY = y;
    rectEl = document.createElement("div");
    rectEl.className = "selection-rect";
    overlay.appendChild(rectEl);
    Object.assign(rectEl.style, { left: `${x}px`, top: `${y}px`, width: `0px`, height: `0px` });
  });

  container?.addEventListener("mousemove", (e) => {
    if (!dragging || !rectEl) return;
    const { x, y } = toLocal(e.clientX, e.clientY);
    const left = Math.min(startX, x);
    const top = Math.min(startY, y);
    const w = Math.abs(x - startX);
    const h = Math.abs(y - startY);
    Object.assign(rectEl.style, { left: `${left}px`, top: `${top}px`, width: `${w}px`, height: `${h}px` });
  });

  function updateConditionalFields(value) {
    conditionalFields.forEach((el) => {
      const target = el.dataset.visible;
      if (target && target === value) {
        el.style.display = 'block';
      } else {
        el.style.display = 'none';
      }
    });
  }

  try {
    form?.qtype?.addEventListener('change', () => updateConditionalFields(form.qtype.value));
  } catch (_) { }

  const removeAutoNote = () => {
    if (!modal) return;
    const existing = modal.querySelector('.auto-mode-note');
    if (existing) existing.style.display = 'none';
  };

  const ensureAutoNote = () => {
    if (!modal || !window.__autoDrawAllActive) {
      removeAutoNote();
      return null;
    }
    let note = modal.querySelector('.auto-mode-note');
    if (!note) {
      note = document.createElement('div');
      note.className = 'auto-mode-note';
      Object.assign(note.style, {
        marginBottom: '0.5rem',
        padding: '0.4rem 0.6rem',
        borderRadius: '0.3rem',
        background: '#eef2ff',
        color: '#1e3a8a',
        fontSize: '0.88rem',
        fontWeight: '600',
        border: '1px solid #c7d2fe'
      });
      const parent = modal.querySelector('#meta-form');
      parent?.insertBefore(note, parent.firstChild);
    }
    note.textContent = 'Auto-saving suggestion...';
    note.style.display = 'block';
    return note;
  };

  const openModal = (box, meta) => {
    modal.classList.remove("hidden");
    if (window.__autoDrawAllActive) {
      ensureAutoNote();
    } else {
      removeAutoNote();
    }
    if (typeof form.reset === 'function') {
      form.reset();
    }
    form.x.value = box.x;
    form.y.value = box.y;
    form.w.value = box.w;
    form.h.value = box.h;
    if (meta) {
      if (meta.question_number !== undefined) form.question_number.value = meta.question_number || '';
      if (meta.marks !== undefined) form.marks.value = meta.marks || '';
      if (meta.qtype) form.qtype.value = meta.qtype;
      if (meta.parent_number !== undefined) form.parent_number.value = meta.parent_number || '';
      if (meta.header_label !== undefined) form.header_label.value = meta.header_label || '';
      if (meta.case_study_label !== undefined) form.case_study_label.value = meta.case_study_label || '';
    } else {
      form.question_number.value = form.question_number.value || '';
      form.marks.value = form.marks.value || '';
      form.parent_number.value = '';
      form.header_label.value = '';
      form.case_study_label.value = '';
    }
    updateConditionalFields(form.qtype.value);
    const qtypeValue = (form.qtype?.value || '').toLowerCase();
    if (qtypeValue === 'cover_page' || qtypeValue === 'instruction') {
      form.question_number.value = '0';
      form.marks.value = '0';
      if (form.parent_number) form.parent_number.value = '';
    }
    lastBox = box;
    // Focus first field for quicker entry
    try {
      form.querySelector('#question_number')?.focus();
    } catch (_) { }

    // Add simple resize handles to the current selection rect, if present
    try {
      const rect = overlay.querySelector('.selection-rect');
      if (!rect) return;
      overlay.style.pointerEvents = 'auto';
      rect.style.position = 'absolute';
      rect.style.boxSizing = 'border-box';
      // Clear old handles
      rect.querySelectorAll('.resize-h').forEach(el => el.remove());
      const dirs = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'];
      dirs.forEach(dir => {
        const h = document.createElement('div');
        h.className = `resize-h resize-${dir}`;
        Object.assign(h.style, {
          position: 'absolute', width: '10px', height: '10px', background: '#2563eb',
          borderRadius: '50%', cursor: dir + '-resize',
        });
        const pos = (d) => {
          const r = rect.getBoundingClientRect();
          const p = { left: 0, top: 0 };
          if (d.includes('n')) p.top = -5; else if (d.includes('s')) p.top = rect.offsetHeight - 5;
          if (d.includes('w')) p.left = -5; else if (d.includes('e')) p.left = rect.offsetWidth - 5;
          if (d === 'n') p.left = rect.offsetWidth / 2 - 5;
          if (d === 's') p.left = rect.offsetWidth / 2 - 5;
          if (d === 'w') p.top = rect.offsetHeight / 2 - 5;
          if (d === 'e') p.top = rect.offsetHeight / 2 - 5;
          return p;
        };
        const p = pos(dir);
        h.style.left = `${p.left}px`; h.style.top = `${p.top}px`;
        rect.appendChild(h);
        h.addEventListener('mousedown', (ev) => {
          ev.preventDefault(); ev.stopPropagation();
          const start = { x: ev.clientX, y: ev.clientY };
          const startRect = rect.getBoundingClientRect();
          const cont = container.getBoundingClientRect();
          const orig = {
            left: parseFloat(rect.style.left),
            top: parseFloat(rect.style.top),
            width: parseFloat(rect.style.width),
            height: parseFloat(rect.style.height),
          };
          const onMove = (e2) => {
            const dx = e2.clientX - start.x; const dy = e2.clientY - start.y;
            let left = orig.left, top = orig.top, width = orig.width, height = orig.height;
            if (dir.includes('e')) width = Math.max(1, orig.width + dx);
            if (dir.includes('s')) height = Math.max(1, orig.height + dy);
            if (dir.includes('w')) { left = orig.left + dx; width = Math.max(1, orig.width - dx); }
            if (dir.includes('n')) { top = orig.top + dy; height = Math.max(1, orig.height - dy); }
            Object.assign(rect.style, { left: `${left}px`, top: `${top}px`, width: `${width}px`, height: `${height}px` });
          };
          const onUp = () => {
            window.removeEventListener('mousemove', onMove);
            window.removeEventListener('mouseup', onUp);
            // Sync form values to rect
            const c = container.getBoundingClientRect();
            const r = rect.getBoundingClientRect();
            form.x.value = r.left - c.left + container.scrollLeft;
            form.y.value = r.top - c.top + container.scrollTop;
            form.w.value = r.width; form.h.value = r.height;
          };
          window.addEventListener('mousemove', onMove);
          window.addEventListener('mouseup', onUp);
        });
      });
    } catch (_) { }
    if (window.__autoDrawAllActive) {
      setTimeout(() => {
        try {
          form?.requestSubmit();
        } catch (_) {
          form?.dispatchEvent(new Event('submit', { cancelable: true, bubbles: true }));
        }
      }, AUTO_DRAW_DELAY_MS);
    }
  };

  container?.addEventListener("mouseup", (e) => {
    if (!dragging || !rectEl) return;
    dragging = false;
    const r = rectEl.getBoundingClientRect();
    const c = container.getBoundingClientRect();
    const x = r.left - c.left + container.scrollLeft;
    const y = r.top - c.top + container.scrollTop;
    const w = r.width;
    const h = r.height;

    // Animate a little pop
    rectEl.style.transition = "transform .12s ease";
    rectEl.style.transform = "scale(1.01)";

    // Open metadata modal
    openModal({ x, y, w, h });
  });

  cancel?.addEventListener("click", () => {
    modal.classList.add("hidden");
    // cleanup
    [...overlay.querySelectorAll(".selection-rect")].forEach(el => el.remove());
    if (window.__autoDrawAllActive) {
      window.__aiQueue = [];
      window.__aiCurrent = null;
      window.__aiPaused = false;
      finishAutoDraw(false, 'Auto draw cancelled');
      return;
    }
    // Keep overlay interactive for future drawing
    if (window.__aiCurrent) {
      window.__aiQueue = window.__aiQueue || [];
      window.__aiQueue.unshift(window.__aiCurrent);
      window.__aiCurrent = null;
      window.__aiPaused = true;
      toast('AI suggestions paused. Click "Continue AI Suggestions" to resume.', 'info', 2500);
      setAIDrawMode(window.__aiQueue.length ? 'resume' : 'fetch');
      setLLMStatus(false, window.__aiQueue.length ? 'Paused' : 'Idle');
    }
  });

  // Snapshot preview helpers
  const previewModal = document.getElementById("preview-modal");
  const previewViewport = document.getElementById("preview-viewport");
  const previewScene = document.getElementById("preview-scene");
  const btnClose = document.getElementById("preview-close");
  const btnZoomIn = document.getElementById("preview-zoom-in");
  const btnZoomOut = document.getElementById("preview-zoom-out");
  let previewScale = 1;

  function applyPreviewTransform() {
    if (!previewScene) return;
    previewScene.style.transformOrigin = '0 0';
    previewScene.style.transform = `scale(${previewScale})`;
  }

  const showSnapshot = (box) => {
    // Compose a cropped scene from intersecting blocks, like copy/paste of selection
    previewScene.innerHTML = "";
    previewScene.style.position = 'relative';
    previewScene.style.width = `${Math.max(1, box.w)}px`;
    previewScene.style.height = `${Math.max(1, box.h)}px`;

    const base = container.getBoundingClientRect();
    const toLocal = (el) => {
      const r = el.getBoundingClientRect();
      return {
        x: r.left - base.left + container.scrollLeft,
        y: r.top - base.top + container.scrollTop,
        w: r.width,
        h: r.height,
      };
    };

    const nodes = Array.from(container.querySelectorAll('.block'));
    for (const el of nodes) {
      const r = toLocal(el);
      const ix = Math.max(r.x, box.x);
      const iy = Math.max(r.y, box.y);
      const iw = Math.min(r.x + r.w, box.x + box.w) - ix;
      const ih = Math.min(r.y + r.h, box.y + box.h) - iy;
      if (iw <= 1 || ih <= 1) continue;

      const wrapper = document.createElement('div');
      wrapper.style.position = 'absolute';
      wrapper.style.left = `${ix - box.x}px`;
      wrapper.style.top = `${iy - box.y}px`;
      wrapper.style.width = `${iw}px`;
      wrapper.style.height = `${ih}px`;
      wrapper.style.overflow = 'hidden';

      const clone = el.cloneNode(true);
      clone.style.position = 'absolute';
      clone.style.left = `${-(ix - r.x)}px`;
      clone.style.top = `${-(iy - r.y)}px`;
      clone.style.width = `${r.w}px`;
      clone.style.height = `${r.h}px`;
      clone.style.pointerEvents = 'none';
      clone.querySelector?.('#lasso-overlay')?.remove?.();

      wrapper.appendChild(clone);
      previewScene.appendChild(wrapper);
    }

    // Selection boundary highlight
    const hl = document.createElement('div');
    hl.style.position = 'absolute';
    hl.style.left = '0px';
    hl.style.top = '0px';
    hl.style.right = '0px';
    hl.style.bottom = '0px';
    hl.style.border = '2px solid #10b981';
    hl.style.pointerEvents = 'none';
    previewScene.appendChild(hl);

    // Fit to viewport (FILL: cover-style scaling)
    const vw = previewViewport.clientWidth;
    const vh = previewViewport.clientHeight;
    const sx = box.w ? (vw / box.w) : 1;
    const sy = box.h ? (vh / box.h) : 1;
    // Use Math.max to FILL (cover). This can crop, but fills the view.
    previewScale = Math.max(0.05, Math.max(sx, sy));
    applyPreviewTransform();

    previewModal.classList.add('open');
  };

  btnClose?.addEventListener('click', () => previewModal.classList.remove('open'));
  previewModal?.addEventListener('click', (e) => {
    if (e.target === previewModal) previewModal.classList.remove('open');
  });
  btnZoomIn?.addEventListener('click', () => { previewScale *= 1.2; applyPreviewTransform(); });
  btnZoomOut?.addEventListener('click', () => { previewScale /= 1.2; applyPreviewTransform(); });

  // Delegate click for snapshot/content view buttons
  document.getElementById('boxes-list')?.addEventListener('click', async (e) => {
    const targetBtn = e.target.closest('button');
    if (!targetBtn) return;
    const node = targetBtn.closest('.box-item');
    if (!node) return;
    e.preventDefault();
    e.stopPropagation();
    if (targetBtn.classList.contains('resize-box')) {
      // Manual resize mode without opening modal
      const x = parseFloat(node.dataset.x), y = parseFloat(node.dataset.y);
      const w = parseFloat(node.dataset.w), h = parseFloat(node.dataset.h);
      // Clear any previous rects
      [...overlay.querySelectorAll('.selection-rect')].forEach(el => el.remove());
      overlay.style.pointerEvents = 'auto';
      const rect = document.createElement('div');
      rect.className = 'selection-rect';
      overlay.appendChild(rect);
      Object.assign(rect.style, { left: `${x}px`, top: `${y}px`, width: `${w}px`, height: `${h}px` });

      // Add resize handles (same logic used for modal)
      try {
        rect.style.position = 'absolute';
        rect.style.boxSizing = 'border-box';
        rect.querySelectorAll('.resize-h').forEach(el => el.remove());
        const dirs = ['nw', 'n', 'ne', 'e', 'se', 's', 'sw', 'w'];
        dirs.forEach(dir => {
          const hdl = document.createElement('div');
          hdl.className = `resize-h resize-${dir}`;
          Object.assign(hdl.style, {
            position: 'absolute', width: '10px', height: '10px', background: '#2563eb',
            borderRadius: '50%', cursor: dir + '-resize',
          });
          const pos = (d) => {
            const p = { left: 0, top: 0 };
            if (d.includes('n')) p.top = -5; else if (d.includes('s')) p.top = rect.offsetHeight - 5;
            if (d.includes('w')) p.left = -5; else if (d.includes('e')) p.left = rect.offsetWidth - 5;
            if (d === 'n') p.left = rect.offsetWidth / 2 - 5;
            if (d === 's') p.left = rect.offsetWidth / 2 - 5;
            if (d === 'w') p.top = rect.offsetHeight / 2 - 5;
            if (d === 'e') p.top = rect.offsetHeight / 2 - 5;
            return p;
          };
          const p = pos(dir);
          hdl.style.left = `${p.left}px`; hdl.style.top = `${p.top}px`;
          rect.appendChild(hdl);
          hdl.addEventListener('mousedown', (ev) => {
            ev.preventDefault(); ev.stopPropagation();
            const start = { x: ev.clientX, y: ev.clientY };
            const orig = {
              left: parseFloat(rect.style.left), top: parseFloat(rect.style.top),
              width: parseFloat(rect.style.width), height: parseFloat(rect.style.height)
            };
            const onMove = (e2) => {
              const dx = e2.clientX - start.x; const dy = e2.clientY - start.y;
              let left = orig.left, top = orig.top, width = orig.width, height = orig.height;
              if (dir.includes('e')) width = Math.max(1, orig.width + dx);
              if (dir.includes('s')) height = Math.max(1, orig.height + dy);
              if (dir.includes('w')) { left = orig.left + dx; width = Math.max(1, orig.width - dx); }
              if (dir.includes('n')) { top = orig.top + dy; height = Math.max(1, orig.height - dy); }
              Object.assign(rect.style, { left: `${left}px`, top: `${top}px`, width: `${width}px`, height: `${height}px` });
            };
            const onUp = () => { window.removeEventListener('mousemove', onMove); window.removeEventListener('mouseup', onUp); };
            window.addEventListener('mousemove', onMove);
            window.addEventListener('mouseup', onUp);
          });
        });
      } catch (_) { }

      // Floating controls for saving/canceling resize
      const toolbar = document.createElement('div');
      Object.assign(toolbar.style, {
        position: 'absolute', left: `${x + w - 140}px`, top: `${Math.max(0, y - 34)}px`,
        background: '#fff', border: '1px solid #e5e7eb', borderRadius: '8px', padding: '6px 8px',
        display: 'flex', gap: '6px', zIndex: 30, boxShadow: '0 4px 12px rgba(0,0,0,.15)'
      });
      const btnApply = document.createElement('button'); btnApply.className = 'btn-icon'; btnApply.textContent = 'Apply';
      const btnCancel = document.createElement('button'); btnCancel.className = 'btn-icon'; btnCancel.textContent = 'Cancel';
      toolbar.appendChild(btnApply); toolbar.appendChild(btnCancel); overlay.appendChild(toolbar);

      const cleanup = () => { rect.remove(); toolbar.remove(); };
      btnCancel.addEventListener('click', cleanup);
      btnApply.addEventListener('click', async () => {
        try {
          const c = container.getBoundingClientRect();
          const r = rect.getBoundingClientRect();
          const nx = r.left - c.left + container.scrollLeft;
          const ny = r.top - c.top + container.scrollTop;
          const nw = r.width; const nh = r.height;
          const url = node.dataset.updateUrl; if (!url) { toast('Missing update URL', 'error'); return; }
          const fd = new FormData();
          fd.append('x', String(nx)); fd.append('y', String(ny)); fd.append('w', String(nw)); fd.append('h', String(nh));
          const csrf = document.querySelector('input[name=csrfmiddlewaretoken]')?.value;
          const resp = await fetch(url, { method: 'POST', body: fd, credentials: 'same-origin', headers: csrf ? { 'X-CSRFToken': csrf } : {} });
          if (!resp.ok) throw new Error('Update failed');
          const data = await resp.json().catch(() => ({ ok: true, box: {} }));
          // Update node datasets
          node.dataset.x = String(nx); node.dataset.y = String(ny); node.dataset.w = String(nw); node.dataset.h = String(nh);
          const kvMeta = node.querySelector('.box-meta .kv'); if (kvMeta) kvMeta.textContent = `x=${Math.round(nx)}, y=${Math.round(ny)}, w=${Math.round(nw)}, h=${Math.round(nh)}`;
          toast('Box resized', 'success', 1500);
          try { renderSavedHighlights(); } catch (_) { }
        } catch (err) {
          console.error('Resize apply error', err);
          toast('Failed to resize box', 'error');
        } finally { cleanup(); }
      });
      return;
    }
    if (targetBtn.classList.contains('view-snapshot')) {
      try {
        const url = node.dataset.jsonUrl;
        if (url) {
          const resp = await fetch(url, { credentials: 'same-origin' });
          const data = await resp.json().catch(() => null);
          if (data && data.ok && data.box) {
            const b = data.box;
            node.dataset.x = String(b.x); node.dataset.y = String(b.y);
            node.dataset.w = String(b.w); node.dataset.h = String(b.h);
          }
        }
      } catch (_) { }
      const box = {
        x: parseFloat(node.dataset.x),
        y: parseFloat(node.dataset.y),
        w: parseFloat(node.dataset.w),
        h: parseFloat(node.dataset.h),
      };
      showSnapshot(box);
      return;
    }
    if (targetBtn.classList.contains('view-content')) {
      try {
        const url = node.dataset.jsonUrl;
        if (url) {
          const resp = await fetch(url, { credentials: 'same-origin' });
          const dt = await resp.json().catch(() => null);
          if (dt && dt.ok && dt.box) {
            const b = dt.box;
            node.dataset.x = String(b.x); node.dataset.y = String(b.y);
            node.dataset.w = String(b.w); node.dataset.h = String(b.h);
            if (b.content) {
              try {
                JSON.parse(b.content);
                node.dataset.content = b.content;
              } catch (_) { /* ignore parse errors */ }
            }
            // flash rectangle
            const flash = document.createElement('div'); flash.className = 'selection-rect'; overlay.appendChild(flash);
            Object.assign(flash.style, { left: `${b.x}px`, top: `${b.y}px`, width: `${b.w}px`, height: `${b.h}px`, opacity: '0' });
            requestAnimationFrame(() => { flash.style.transition = 'opacity .25s ease'; flash.style.opacity = '1'; });
            setTimeout(() => flash.style.opacity = '0', 450);
            setTimeout(() => flash.remove(), 800);
          }
        }
      } catch (_) { }
      try {
        const payload = node.dataset.content ? JSON.parse(node.dataset.content) : { items: [] };
        const body = document.getElementById('content-body');
        const modal = document.getElementById('content-modal');
        if (!body || !modal) return;
        body.innerHTML = '';
        (payload.items || []).forEach(item => {
          if (item.type === 'text') {
            const p = document.createElement('p');
            p.textContent = item.text || '';
            body.appendChild(p);
          } else if (item.type === 'table') {
            const div = document.createElement('div');
            div.className = 'block-table';
            div.innerHTML = item.html || '';
            body.appendChild(div);
          } else if (item.type === 'image') {
            (item.images || []).forEach(src => {
              const img = document.createElement('img');
              img.src = src;
              img.className = 'block-image';
              body.appendChild(img);
            });
          }
        });
        modal.classList.remove('hidden');
        window.__currentBoxNode = node;
        document.getElementById('content-close')?.addEventListener('click', () => modal.classList.add('hidden'), { once: true });
        document.getElementById('content-ok')?.addEventListener('click', () => modal.classList.add('hidden'), { once: true });
        modal.addEventListener('click', (ev) => { if (ev.target === modal) modal.classList.add('hidden'); }, { once: true });
      } catch (_) { }
    }
  });

  contentClose?.addEventListener('click', () => {
    document.getElementById('content-modal')?.classList.add('hidden');
  });

  form?.addEventListener("submit", async (e) => {
    e.preventDefault();
    const qtypeValue = (form.qtype?.value || '').toLowerCase();
    if (qtypeValue === 'cover_page') {
      const existingCovers = Array.from(document.querySelectorAll('.box-item'))
        .filter(node => node.dataset && (node.dataset.qtype || '').toLowerCase() === 'cover_page' && node.dataset.id);
      let editingId = null;
      if (/\/boxes\/\d+\/update\/$/.test(form.action || '') && window.__currentBoxNode) {
        editingId = window.__currentBoxNode.dataset?.id || null;
      }
      const hasOtherCover = existingCovers.some(node => node.dataset.id !== editingId);
      if (hasOtherCover) {
        toast('Only one cover page can be saved for this paper.', 'error');
        return;
      }
    }

    // Before submitting, collect intersecting content into JSON
    try {
      const blocks = Array.from(container.querySelectorAll('.block'));
      const contentItems = [];
      const sel = lastBox || { x: parseFloat(form.x.value), y: parseFloat(form.y.value), w: parseFloat(form.w.value), h: parseFloat(form.h.value) };
      const cRect = container.getBoundingClientRect();
      const intersects = (r) => {
        const ix = Math.max(r.left - cRect.left + container.scrollLeft, sel.x);
        const iy = Math.max(r.top - cRect.top + container.scrollTop, sel.y);
        const iw = Math.min(r.left - cRect.left + container.scrollLeft + r.width, sel.x + sel.w) - ix;
        const ih = Math.min(r.top - cRect.top + container.scrollTop + r.height, sel.y + sel.h) - iy;
        return iw > 1 && ih > 1;
      };
      for (const b of blocks) {
        const br = b.getBoundingClientRect();
        if (!intersects(br)) continue;
        const type = b.dataset.type || 'paragraph';
        if (type === 'image') {
          const imgs = Array.from(b.querySelectorAll('img')).map(img => img.getAttribute('src'));
          if (imgs.length) contentItems.push({ type: 'image', images: imgs });
        } else if (type === 'table') {
          const html = b.querySelector('.block-table')?.innerHTML || '';
          if (html.trim()) contentItems.push({ type: 'table', html });
        } else {
          const text = b.querySelector('.block-text')?.innerText || '';
          if (text.trim()) contentItems.push({ type: 'text', text });
          // also capture any inline images within non-image block
          const imgs = Array.from(b.querySelectorAll('img')).map(img => img.getAttribute('src'));
          if (imgs.length) contentItems.push({ type: 'image', images: imgs });
        }
      }
      const contentType = contentItems.length === 1 ? contentItems[0].type : (contentItems.length ? 'mixed' : 'none');
      form.content_json.value = JSON.stringify({ items: contentItems });
      form.content_type.value = contentType;
    } catch (_) { }

    const fd = new FormData(form);
    const csrf = fd.get('csrfmiddlewaretoken');
    const resp = await fetch(form.action, { method: "POST", body: fd, credentials: 'same-origin', headers: csrf ? { 'X-CSRFToken': csrf } : {} });
    if (resp.ok) {
      const data = await resp.json().catch(() => ({ ok: true }));
      modal.classList.add("hidden");
      // Clean up selection rect but keep overlay interactive
      [...overlay.querySelectorAll(".selection-rect")].forEach(el => el.remove());
      // keep the last rect as a locked box (pointer-events none already)
      // You could also render saved boxes back from server in paper_view.
      try {
        const list = document.getElementById("boxes-list");
        if (list && data && data.box) {
          // If updating, update in-place and return
          if (/\/boxes\/\d+\/update\/$/.test(form.action || '')) {
            const node = list.querySelector(`.box-item[data-id="${data.box.id}"]`);
            if (node) {
              applyBoxDataset(node, data.box);
            }
            if (form.__originalAction) form.action = form.__originalAction;
            return;
          }
          // Remove placeholder if present
          if (list.children.length === 1 && list.firstElementChild?.dataset?.id === undefined) {
            list.firstElementChild.remove();
          }

          // Build a new <details> node for the created box
          const b = data.box;
          const details = document.createElement("details");
          details.className = "box-item";
          details.dataset.id = String(b.id || '');

          // pre-populate all datasets so helpers can render correctly
          details.dataset.x = String(b.x || 0);
          details.dataset.y = String(b.y || 0);
          details.dataset.w = String(b.w || 0);
          details.dataset.h = String(b.h || 0);
          details.dataset.qn = b.question_number || '';
          details.dataset.marks = b.marks || '';
          details.dataset.qtype = b.qtype || '';
          details.dataset.parentNumber = b.parent_number || '';
          details.dataset.headerLabel = b.header_label || '';
          details.dataset.caseLabel = b.case_study_label || '';
          details.dataset.content = b.content || form.content_json.value || '';
          details.dataset.ctype = b.content_type || form.content_type.value || '';
          details.dataset.createdAt = b.created_at || '';

          const baseMatch = location.pathname.match(/^(.*paper\/\d+\/)/);
          const basePath = baseMatch ? baseMatch[1] : '';
          const updateUrl = basePath ? `${basePath}boxes/${b.id}/update/` : '';
          const deleteUrl = basePath ? `${basePath}boxes/${b.id}/delete/` : '';
          const jsonUrl = basePath ? `${basePath}boxes/${b.id}/json/` : '';
          details.dataset.updateUrl = updateUrl;
          details.dataset.deleteUrl = deleteUrl;
          details.dataset.jsonUrl = jsonUrl;

          const qtype = details.dataset.qtype || "(type)";
          const qn = details.dataset.qn || "n/a";
          const mk = details.dataset.marks || "n/a";
          const xywh = `x=${Math.round(+details.dataset.x)}, y=${Math.round(+details.dataset.y)}, w=${Math.round(+details.dataset.w)}, h=${Math.round(+details.dataset.h)}`;
          const created = details.dataset.createdAt ? new Date(details.dataset.createdAt).toLocaleString() : "";

          details.innerHTML = `
            <summary>
              <span class="title">${qtype}</span>
              <span class="kv">Q: ${qn} &bull; Marks: ${mk}</span>
              <span class="actions">
                <button type="button" class="btn-icon view-content" title="View captured content" aria-label="View content">Content</button>
                <button type="button" class="btn-icon view-snapshot" title="View snapshot" aria-label="View snapshot">Snap</button>
                <button type="button" class="btn-icon edit-box" title="Edit this box" aria-label="Edit">Edit</button>
                <button type="button" class="btn-icon resize-box" title="Resize this box" aria-label="Resize">Resize</button>
                <button type="button" class="btn-icon delete-box" title="Delete this box" aria-label="Delete">Delete</button>
                <span class="chev">›</span>
              </span>
            </summary>
            <div class="box-meta">
              <div class="kv">${xywh}</div>
              ${created ? `<div class="kv">${created}</div>` : ''}
            </div>
          `;

          // ensure summary/metadata reflect any optional parent/header/case labels
          applyBoxDataset(details, b);

          list.prepend(details);
          details.open = true;
          if (window.__autoDrawAllActive) {
            window.__autoDrawAllSaved = (window.__autoDrawAllSaved || 0) + 1;
          }
          try { renderSavedHighlights(); } catch (_) { }
        }
      } catch (_) { }
      // If we are processing an AI queue, proceed to next and notify
      try {
        if (window.__aiQueue && window.__aiQueue.length) {
          toast('Saved. Moving to next suggestion...', 'success', 1200);
          processNextAIDraw();
        } else if (typeof window.__aiTotal === 'number') {
          if (window.__autoDrawAllActive) {
            finishAutoDraw(true);
          } else {
            toast('AI drawing complete', 'success', 2000);
          }
        }
      } catch (_) { }
    } else {
      alert("Failed to save box");
      if (window.__autoDrawAllActive) {
        finishAutoDraw(false, 'Auto draw stopped (save failed)');
      }
    }
  });

  function renderSavedHighlights() {
    if (!savedOverlay) return;
    savedOverlay.innerHTML = '';
    document.querySelectorAll('.box-item').forEach(node => {
      if ((node.dataset.qtype || '').toLowerCase() !== 'question_header') return;
      const x = parseFloat(node.dataset.x) || 0, y = parseFloat(node.dataset.y) || 0, w = parseFloat(node.dataset.w) || 0, h = parseFloat(node.dataset.h) || 0;
      const el = document.createElement('div'); el.className = 'saved-highlight';
      Object.assign(el.style, { left: `${x}px`, top: `${y}px`, width: `${w}px`, height: `${h}px` });
      savedOverlay.appendChild(el);
    });
  }
  try { renderSavedHighlights(); } catch (_) { }

  boxesList?.addEventListener('click', async (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (!target.classList.contains('delete-box')) return;
    event.preventDefault();
    const node = target.closest('.box-item');
    if (!node) return;
    const url = node.dataset.deleteUrl || (node.dataset.updateUrl ? node.dataset.updateUrl.replace('/update/', '/delete/') : '');
    if (!url) {
      toast('Delete endpoint missing for this box.', 'error');
      return;
    }
    if (!confirm('Delete this box?')) return;
    const csrf = document.querySelector('input[name=csrfmiddlewaretoken]')?.value;
    const resp = await fetch(url, { method: 'POST', credentials: 'same-origin', headers: csrf ? { 'X-CSRFToken': csrf } : {} });
    if (resp.ok) {
      node.remove();
      renderSavedHighlights();
      toast('Box deleted.', 'success', 1800);
    } else {
      toast('Failed to delete box.', 'error');
    }
  });

  // AI Draw Blocks flow
  const unionRectOfBlocks = (ids) => {
    const base = container.getBoundingClientRect();
    let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity, found = 0;
    ids.forEach(id => {
      const el = container.querySelector(`.block[data-id="${id}"]`);
      if (!el) return;
      const r = el.getBoundingClientRect();
      const x = r.left - base.left + container.scrollLeft;
      const y = r.top - base.top + container.scrollTop;
      const w = r.width; const h = r.height;
      minX = Math.min(minX, x); minY = Math.min(minY, y);
      maxX = Math.max(maxX, x + w); maxY = Math.max(maxY, y + h);
      found++;
    });
    if (!found) return null;
    return { x: minX, y: minY, w: Math.max(1, maxX - minX), h: Math.max(1, maxY - minY) };
  };

  const processNextAIDraw = () => {
    if (!window.__aiQueue || !window.__aiQueue.length) {
      window.__aiCurrent = null;
      setLLMStatus(false, 'Idle');
      setAIDrawMode('fetch');
      if (window.__autoDrawAllActive) {
        finishAutoDraw(true);
      }
      return;
    }
    window.__aiPaused = false;
    setAIDrawMode('resume');
    const next = window.__aiQueue.shift();
    window.__aiCurrent = next;
    // Remove prior rects
    [...overlay.querySelectorAll('.selection-rect')].forEach(el => el.remove());
    DBG('[AI DRAW] Next suggestion:', next);
    const rect = unionRectOfBlocks(next.block_ids || []);
    if (!rect) return processNextAIDraw();
    const rectEl2 = document.createElement('div');
    rectEl2.className = 'selection-rect';
    overlay.appendChild(rectEl2);
    Object.assign(rectEl2.style, { left: `${rect.x}px`, top: `${rect.y}px`, width: `${rect.w}px`, height: `${rect.h}px` });
    try {
      // Bring into view if outside
      const cRect = container.getBoundingClientRect();
      const curBottom = rect.y + rect.h;
      if (rect.y < container.scrollTop || curBottom > container.scrollTop + cRect.height) {
        container.scrollTo({ top: Math.max(0, rect.y - 40), behavior: 'smooth' });
      }
    } catch (_) { }
    try {
      window.__aiIndex = (window.__aiIndex || 0) + 1;
      const total = window.__aiTotal || 0;
      toast(`Suggestion ${window.__aiIndex}/${total}: review and save`, 'info', 2500);
      setLLMStatus(true, `Drawing ${window.__aiIndex}/${total}`);
    } catch (_) { }
    openModal(rect, {
      question_number: next.question_number,
      marks: next.marks,
      qtype: next.qtype,
      parent_number: next.parent_number,
      header_label: next.header_label,
      case_study_label: next.case_study_label,
    });
  };

  window.examExtractorQueueSuggestions = (items, options = {}) => {
    const label = options.label || 'Suggestions';
    const normalizedItems = Array.isArray(items)
      ? items
          .map((item) => ({
            block_ids: Array.from(new Set(item.block_ids || [])).filter(Boolean),
            question_number: item.question_number || '',
            marks: item.marks || '',
            qtype: item.qtype || 'question',
            parent_number: item.parent_number || '',
            header_label: item.header_label || '',
            case_study_label: item.case_study_label || '',
          }))
          .filter((entry) => entry.block_ids.length)
      : [];

    if (!normalizedItems.length) {
      toast(options.emptyMessage || 'No segments found to draw.', 'warning', 2600);
      return false;
    }

    const autoRun = options.auto === true;
    if (autoRun) {
      window.__autoDrawAllActive = true;
      window.__autoDrawAllSaved = 0;
    } else {
      window.__autoDrawAllActive = false;
      window.__autoDrawAllSaved = 0;
    }
    window.__aiQueue = normalizedItems;
    window.__aiTotal = normalizedItems.length;
    window.__aiIndex = 0;
    window.__aiSource = label;

    toast(`${label}: ${window.__aiTotal} suggestion(s) ready`, 'success', 2200);
    setLLMStatus(true, `${label}`);
    processNextAIDraw();
    return true;
  };

  btnAIDraw?.addEventListener('click', async (e) => {
    const api = btnAIDraw.getAttribute('data-api');
    if (!api) return;
    DBG('[AI DRAW] Clicked. Endpoint:', api);
    btnAIDraw.disabled = true; btnAIDraw.textContent = 'Drawing...';
    showSpinner('Fetching AI suggestions...');
    setLLMStatus(true, 'Fetching suggestions');
    try {
      const resp = await fetch(api, { credentials: 'same-origin' });
      if (!resp.ok) {
        const txt = await resp.text().catch(() => '');
        DBG('[AI DRAW] HTTP error', resp.status, txt?.slice?.(0, 300));
        throw new Error(`HTTP ${resp.status}`);
      }
      let data = null;
      try { data = await resp.json(); } catch (_) { data = null; }
      if (!data || !data.ok) throw new Error('AI draw failed');
      window.__aiQueue = Array.from(data.items || []);
      notifyAIStrategy(data.strategy);
      window.__aiTotal = window.__aiQueue.length;
      window.__aiIndex = 0;
      hideSpinner();
      if (!window.__aiTotal) {
        toast('No AI suggestions found', 'error');
        setLLMStatus(false, 'Idle');
        return;
      }
      toast(`Loaded ${window.__aiTotal} AI suggestion(s)`, 'success');
      processNextAIDraw();
    } catch (err) {
      hideSpinner();
      DBG('AI draw error:', err);
      toast('Failed to fetch AI block suggestions', 'error');
      setLLMStatus(false, 'Error');
    } finally {
      btnAIDraw.disabled = false; btnAIDraw.textContent = 'Draw Blocks with AI';
    }
  });

  btnAIAuto?.addEventListener('click', async () => {
    const api = btnAIAuto.getAttribute('data-api') || btnAIDraw?.getAttribute('data-api');
    if (!api || btnAIAuto.dataset.state === 'fetch' || btnAIAuto.dataset.state === 'run') return;
    DBG('[AI DRAW AUTO] Clicked. Endpoint:', api);
    setAutoDrawButtonState('fetch');
    if (btnAIDraw) btnAIDraw.disabled = true;
    showSpinner('Fetching AI suggestions...');
    setLLMStatus(true, 'Fetching suggestions');
    let autoStarted = false;
    try {
      const resp = await fetch(api, { credentials: 'same-origin' });
      if (!resp.ok) {
        const txt = await resp.text().catch(() => '');
        DBG('[AI DRAW AUTO] HTTP error', resp.status, txt?.slice?.(0, 300));
        throw new Error(`HTTP ${resp.status}`);
      }
      let data = null;
      try { data = await resp.json(); } catch (_) { data = null; }
      if (!data || !data.ok) throw new Error('AI draw failed');
      window.__aiQueue = Array.from(data.items || []);
      notifyAIStrategy(data.strategy);
      window.__aiTotal = window.__aiQueue.length;
      window.__aiIndex = 0;
      hideSpinner();
      if (!window.__aiTotal) {
        finishAutoDraw(false, 'No suggestions to auto draw');
        return;
      }
      autoStarted = true;
      window.__autoDrawAllActive = true;
      window.__autoDrawAllSaved = 0;
      setAutoDrawButtonState('run');
      setLLMStatus(true, 'Auto drawing');
      toast(`Auto mode queued ${window.__aiTotal} suggestion(s)`, 'info', 2500);
      processNextAIDraw();
    } catch (err) {
      hideSpinner();
      DBG('AI auto draw error:', err);
      toast('Failed to fetch AI block suggestions', 'error');
      finishAutoDraw(false);
    } finally {
      if (!autoStarted && !window.__autoDrawAllActive) {
        setAutoDrawButtonState('idle');
        if (btnAIDraw) btnAIDraw.disabled = false;
      }
    }
  });

  btnGadzira?.addEventListener('click', async () => {
    const api = btnGadzira.getAttribute('data-api');
    if (!api) return;
    if (!btnGadzira.dataset.originalLabel) {
      btnGadzira.dataset.originalLabel = btnGadzira.textContent?.trim() || 'Gadzira';
    }
    btnGadzira.disabled = true;
    btnGadzira.textContent = 'Running Gadzira...';
    showSpinner('Running Gadzira heuristics...');
    setLLMStatus(true, 'Gadzira');
    try {
      const resp = await fetch(api, { credentials: 'same-origin' });
      if (!resp.ok) {
        const txt = await resp.text().catch(() => '');
        throw new Error(`HTTP ${resp.status}: ${txt.slice(0, 200)}`);
      }
      let data = null;
      try { data = await resp.json(); } catch (_) { data = null; }
      if (!data || !data.ok) throw new Error('Gadzira failed');
      window.__aiQueue = Array.from(data.items || []);
      notifyAIStrategy(data.strategy || 'gadzira');
      window.__aiTotal = window.__aiQueue.length;
      window.__aiIndex = 0;
      hideSpinner();
      if (!window.__aiTotal) {
        toast('No Gadzira suggestions found', 'error');
        setLLMStatus(false, 'Idle');
        return;
      }
      toast(`Loaded ${window.__aiTotal} Gadzira suggestion(s)`, 'success');
      processNextAIDraw();
    } catch (err) {
      hideSpinner();
      toast('Failed to run Gadzira', 'error');
      setLLMStatus(false, 'Error');
      DBG('Gadzira error:', err);
    } finally {
      btnGadzira.disabled = false;
      btnGadzira.textContent = btnGadzira.dataset.originalLabel || 'Gadzira';
    }
  });
})();
