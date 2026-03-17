/* ═══════════════════════════════════════════════════════════════
   LocalFileHandler — Dashboard SPA
   Single-file vanilla JS. No framework, no build step.
   ═══════════════════════════════════════════════════════════════ */

'use strict';

// ══════════════════════════════════════════════════════════════
// 1. STATE
// ══════════════════════════════════════════════════════════════
const S = {
  currentPath: '.',
  entries:     [],
  history:     [],
  config:      {},
  treeData:    { '.': [] },         // path → [entries]
  treeOpen:    new Set(['.']),
  dragging:    null,                // path being dragged
  pendingDelete: null,              // path awaiting confirm
  serverOk:    false,
  countdown:   30,
  sidebarOpen: true,
  historyOpen: true,
  sortKey:     'name',
  searchDebounce: null,
  selected:    new Set(),           // paths of selected items (bulk mode)
  selectMode:  false,               // whether click-to-select mode is active
};

// ══════════════════════════════════════════════════════════════
// 2. API LAYER  (all calls go through POST /invoke)
// ══════════════════════════════════════════════════════════════
let _reqId = 1;
async function invoke(tool, payload) {
  const body = JSON.stringify({ id: String(_reqId++), tool, payload });
  const r = await fetch('/invoke', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body,
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

const api = {
  list:     (path = '.', recursive = false) => invoke('listcontentstool',  { path, recursive }),
  create:   (name, type, content = '')      => invoke('createfiletool',    { name, type, content }),
  mkdir:    (name)                          => invoke('createdirtool',      { name }),
  rename:   (path, new_name)               => invoke('renametool',         { path, new_name }),
  move:     (source, destination)          => invoke('movetool',           { source, destination }),
  del:      (path)                         => invoke('deletetool',         { path, confirm: true }),
  search:   (query, type = '', searchPath = '.') =>
                                              invoke('searchtool',         { query, type, path: searchPath }),
  organize: (path, dry_run = true)         => invoke('organizetool',       { path, dry_run }),
  info:     (path)                         => invoke('infotool',           { path }),
  history:  (limit = 15)                   => invoke('historytool',        { limit }),
  undo:     (steps = 1)                    => invoke('undotool',           { steps }),
  config:   (action, values)               => invoke('configtool',         { action, ...(values ? { values } : {}) }),
  preview:  (name, type = 'txt')           => invoke('previewtool',        { name, type }),
  nlcmd:    (command)                      => invoke('nlcommandtool',      { command }),
  suggest:  (path = '.')                   => invoke('suggestionstool',    { path }),
  dupes:    (path = '.', mode = 'all')     => invoke('duplicatestool',     { path, mode }),
  categorize:(path, apply = false)         => invoke('smartcategorizetool',{ path, apply }),
};

// ══════════════════════════════════════════════════════════════
// 3. UTILITIES
// ══════════════════════════════════════════════════════════════
const FILE_ICONS = {
  dir:  '📁',
  md:   '📝', txt: '📄', pdf: '📄', doc: '📄', docx: '📄',
  py:   '🐍', js: '📜', ts: '📜', html: '🌐', css: '🎨',
  json: '📋', yaml: '📋', yml: '📋', toml: '📋', xml: '📋',
  csv:  '📊', xls: '📊', xlsx: '📊', ods: '📊',
  jpg:  '🖼', jpeg: '🖼', png: '🖼', gif: '🖼', svg: '🖼', webp: '🖼',
  mp4:  '🎬', avi: '🎬', mkv: '🎬', mov: '🎬',
  mp3:  '🎵', wav: '🎵', flac: '🎵', ogg: '🎵',
  zip:  '📦', tar: '📦', gz: '📦', rar: '📦',
};
const icon = (entry) => {
  if (entry.type === 'directory') return FILE_ICONS.dir;
  const ext = (entry.extension || '').replace('.', '');
  return FILE_ICONS[ext] || '📄';
};

const fmtSize = (b) => {
  if (b == null) return '';
  if (b < 1024) return `${b} B`;
  if (b < 1048576) return `${(b / 1024).toFixed(1)} KB`;
  return `${(b / 1048576).toFixed(1)} MB`;
};

const fmtTime = (iso) => {
  if (!iso) return '';
  const d = new Date(iso);
  const now = new Date();
  const diffMs = now - d;
  if (diffMs < 60000)    return 'just now';
  if (diffMs < 3600000)  return `${Math.floor(diffMs / 60000)}m ago`;
  if (diffMs < 86400000) return `${Math.floor(diffMs / 3600000)}h ago`;
  return d.toLocaleDateString();
};

const toolLabel = (tool) => ({
  createfiletool:      '+ File',
  createdirtool:       '+ Folder',
  renametool:          '✏ Rename',
  movetool:            '→ Move',
  deletetool:          '🗑 Delete',
  organizetool:        '⚡ Organize',
  undotool:            '↩ Undo',
  nlcommandtool:       '🤖 NL Command',
  suggestionstool:     '💡 Suggestions',
  duplicatestool:      '🔍 Duplicates',
  smartcategorizetool: '🏷 Categorize',
})[tool] || tool;

function el(tag, cls, inner = '') {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (inner) e.innerHTML = inner;
  return e;
}

function toast(msg, type = 'info', duration = 3500) {
  const t = el('div', `toast ${type}`, msg);
  document.getElementById('toast-container').prepend(t);
  setTimeout(() => { t.style.opacity = '0'; setTimeout(() => t.remove(), 300); }, duration);
}

function setLoading(flag) {
  document.getElementById('btn-refresh').disabled = flag;
}

// ══════════════════════════════════════════════════════════════
// 4. BREADCRUMB
// ══════════════════════════════════════════════════════════════
function renderBreadcrumb() {
  const bc = document.getElementById('breadcrumb');
  bc.innerHTML = '';
  const parts = S.currentPath === '.' ? [] : S.currentPath.split('/');

  const rootItem = el('span', 'breadcrumb-item' + (parts.length === 0 ? ' current' : ''), 'workspace');
  rootItem.onclick = () => navigate('.');
  bc.appendChild(rootItem);

  parts.forEach((part, i) => {
    bc.appendChild(el('span', 'breadcrumb-sep', '/'));
    const fullPath = parts.slice(0, i + 1).join('/');
    const isCurrent = i === parts.length - 1;
    const item = el('span', 'breadcrumb-item' + (isCurrent ? ' current' : ''), part);
    if (!isCurrent) item.onclick = () => navigate(fullPath);
    bc.appendChild(item);
  });
}

// ══════════════════════════════════════════════════════════════
// 5. TREE VIEW (left sidebar)
// ══════════════════════════════════════════════════════════════
async function loadTree(path = '.') {
  const r = await api.list(path);
  if (r.status !== 'success') return;
  S.treeData[path] = r.result.entries.filter(e => e.type === 'directory');
  renderTree();
}

function renderTree() {
  const container = document.getElementById('tree-view');
  container.innerHTML = '';
  renderTreeNode(container, '.', 0);
}

function renderTreeNode(container, path, depth) {
  const entries = S.treeData[path] || [];
  entries.forEach(entry => {
    const fullPath = path === '.' ? entry.name : `${path}/${entry.name}`;
    const hasChildren = S.treeData[fullPath] !== undefined;
    const isOpen = S.treeOpen.has(fullPath);
    const isActive = S.currentPath === fullPath;

    const node = el('div', `tree-node${isActive ? ' active' : ''}`,
      `<span class="tree-toggle ${isOpen ? 'open' : ''}">▶</span>` +
      `<span class="tree-node-icon">📁</span>` +
      `<span class="tree-node-name">${entry.name}</span>`
    );
    node.style.paddingLeft = `${12 + depth * 14}px`;
    node.dataset.path = fullPath;

    // Click: navigate
    node.onclick = () => navigate(fullPath);

    // Toggle expand
    node.querySelector('.tree-toggle').onclick = async (e) => {
      e.stopPropagation();
      if (isOpen) {
        S.treeOpen.delete(fullPath);
      } else {
        S.treeOpen.add(fullPath);
        if (!S.treeData[fullPath]) await loadTree(fullPath);
      }
      renderTree();
    };

    // Drag-and-drop: as drop target
    node.ondragover = (e) => { e.preventDefault(); node.classList.add('drop-target'); };
    node.ondragleave = () => node.classList.remove('drop-target');
    node.ondrop = async (e) => {
      e.preventDefault();
      node.classList.remove('drop-target');
      await executeDrop(fullPath + '/');
    };

    container.appendChild(node);

    if (isOpen) {
      const childWrap = el('div', 'tree-children');
      renderTreeNode(childWrap, fullPath, depth + 1);
      container.appendChild(childWrap);
    }
  });
}

// ══════════════════════════════════════════════════════════════
// 6. FILE GRID (main content)
// ══════════════════════════════════════════════════════════════
async function navigate(path) {
  S.currentPath = path;
  await loadCurrentDir();
}

async function loadCurrentDir() {
  setLoading(true);
  try {
    const r = await api.list(S.currentPath);
    if (r.status !== 'success') { toast(r.error, 'error'); return; }
    S.entries = r.result.entries;
    renderBreadcrumb();
    renderFileGrid();
    // Ensure tree shows this path's subdirs
    if (!S.treeData[S.currentPath]) await loadTree(S.currentPath);
    else renderTree();
    S.serverOk = true;
    document.getElementById('server-dot').classList.remove('offline');
  } catch {
    S.serverOk = false;
    document.getElementById('server-dot').classList.add('offline');
    toast('Server unreachable', 'error');
  } finally {
    setLoading(false);
  }
}

function sortedEntries() {
  const dirs  = S.entries.filter(e => e.type === 'directory');
  const files = S.entries.filter(e => e.type === 'file');
  const sorter = {
    'name':     (a, b) => a.name.localeCompare(b.name),
    'name-desc':(a, b) => b.name.localeCompare(a.name),
    'modified': (a, b) => (b.modified || '').localeCompare(a.modified || ''),
    'size':     (a, b) => (b.size || 0) - (a.size || 0),
    'type':     (a, b) => (a.extension || '').localeCompare(b.extension || ''),
  }[S.sortKey] || ((a,b) => a.name.localeCompare(b.name));
  return [...dirs.sort(sorter), ...files.sort(sorter)];
}

function renderFileGrid() {
  const grid    = document.getElementById('file-grid');
  const empty   = document.getElementById('empty-state');
  grid.innerHTML = '';

  const entries = sortedEntries();
  empty.hidden  = entries.length > 0;

  entries.forEach(entry => {
    const isDir = entry.type === 'directory';
    const path  = S.currentPath === '.' ? entry.name : `${S.currentPath}/${entry.name}`;

    const card = el('div', `file-card${isDir ? ' dir-card' : ''}${S.selected.has(path) ? ' selected' : ''}`,
      `<div class="card-check">✓</div>
       <div class="file-icon">${icon(entry)}</div>
       <div class="file-name-row">
         <span class="file-name" title="${entry.name}">${entry.name}</span>
       </div>
       <div class="file-meta">
         ${entry.size != null ? `<span>${fmtSize(entry.size)}</span>` : ''}
         <span>${fmtTime(entry.modified)}</span>
       </div>
       <div class="file-actions">
         <button class="file-action-btn" title="Rename" data-action="rename" data-path="${path}">✏</button>
         <button class="file-action-btn" title="Info"   data-action="info"   data-path="${path}">ℹ</button>
         <button class="file-action-btn danger" title="Delete" data-action="delete" data-path="${path}">🗑</button>
       </div>`
    );
    card.dataset.path = path;

    // Navigate on click (directories) — Ctrl/Meta+click or selectMode → toggle selection
    card.onclick = (e) => {
      if (e.target.closest('.file-action-btn')) return;
      if (e.target.closest('.file-name-input')) return;
      if (S.selectMode || e.ctrlKey || e.metaKey) { toggleSelect(path); return; }
      if (isDir) navigate(path);
    };

    // Double-click on name → inline rename
    card.querySelector('.file-name').ondblclick = (e) => {
      e.stopPropagation();
      startInlineRename(card, entry, path);
    };

    // Action buttons
    card.querySelectorAll('.file-action-btn').forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const action = btn.dataset.action;
        if (action === 'rename') startInlineRename(card, entry, path);
        if (action === 'info')   showInfo(path);
        if (action === 'delete') askDelete(path);
      };
    });

    // Drag source (files and dirs can be moved)
    card.setAttribute('draggable', 'true');
    card.ondragstart = (e) => {
      S.dragging = path;
      e.dataTransfer.effectAllowed = 'move';
      card.style.opacity = '.5';
    };
    card.ondragend = () => { card.style.opacity = ''; S.dragging = null; };

    // Drop target (directories only)
    if (isDir) {
      card.ondragover = (e) => { e.preventDefault(); card.classList.add('drag-over'); };
      card.ondragleave = () => card.classList.remove('drag-over');
      card.ondrop = async (e) => {
        e.preventDefault();
        card.classList.remove('drag-over');
        await executeDrop(path + '/');
      };
    }

    grid.appendChild(card);
  });
}

// ── Inline rename ────────────────────────────────────────────
function startInlineRename(card, entry, path) {
  const nameSpan = card.querySelector('.file-name');
  const baseName = entry.name.replace(/\.[^.]+$/, '');   // strip extension for display

  const input = el('input', 'file-name-input');
  input.value = baseName;
  nameSpan.replaceWith(input);
  input.focus();
  input.select();

  const commit = async () => {
    const newName = input.value.trim();
    input.replaceWith(nameSpan);
    if (!newName || newName === baseName) { renderFileGrid(); return; }
    const r = await api.rename(path, newName);
    if (r.status === 'success') {
      toast(`Renamed → ${r.result.new_path}`, 'success');
      await refresh();
    } else {
      toast(r.error, 'error');
      renderFileGrid();
    }
  };

  input.onblur  = commit;
  input.onkeydown = (e) => {
    if (e.key === 'Enter')  commit();
    if (e.key === 'Escape') { input.replaceWith(nameSpan); renderFileGrid(); }
  };
}

// ── Drag-and-drop move ───────────────────────────────────────
async function executeDrop(destinationDir) {
  if (!S.dragging) return;
  if (S.dragging === destinationDir.replace(/\/$/, '')) return;
  const r = await api.move(S.dragging, destinationDir);
  if (r.status === 'success') {
    toast(`Moved → ${r.result.new_path}`, 'success');
    await refresh();
  } else {
    toast(r.error, 'error');
  }
}

// Drop onto the main area = move to current dir
async function handleDropOnMain(e) {
  e.preventDefault();
  await executeDrop(S.currentPath === '.' ? './' : S.currentPath + '/');
}
window.handleDropOnMain = handleDropOnMain;

// ══════════════════════════════════════════════════════════════
// 7. HISTORY PANEL
// ══════════════════════════════════════════════════════════════
async function loadHistory() {
  const r = await api.history(15);
  if (r.status !== 'success') return;
  S.history = r.result.operations;
  renderHistory();
}

function renderHistory() {
  const list = document.getElementById('history-list');
  if (!S.history.length) {
    list.innerHTML = '<div class="history-empty">No operations yet</div>';
    return;
  }
  list.innerHTML = S.history.map(op => {
    const detail = op.result?.path || op.result?.new_path || op.result?.deleted || '';
    return `<div class="history-item">
      <div>
        <span class="history-tool">${toolLabel(op.tool)}</span>
        <span class="history-time"> · ${fmtTime(op.timestamp)}</span>
        <span class="${op.status === 'success' ? 'history-status-ok' : 'history-status-err'}">
          ${op.status === 'success' ? '' : ' ✗'}
        </span>
        ${op.undone ? '<span style="color:var(--text-faint)"> (undone)</span>' : ''}
      </div>
      ${detail ? `<div class="history-detail" title="${detail}">${detail}</div>` : ''}
    </div>`;
  }).join('');
}

document.getElementById('btn-undo').onclick = async () => {
  const r = await api.undo(1);
  if (r.status === 'success' && r.result.undone_count > 0) {
    toast('Operation undone', 'success');
    await refresh();
  } else {
    toast(r.error || 'Nothing to undo', 'error');
  }
};

// ══════════════════════════════════════════════════════════════
// 8. MODALS
// ══════════════════════════════════════════════════════════════
function showModal(id) {
  const overlay = document.getElementById('modal-overlay');
  overlay.hidden = false;
  // Hide all modals first, then show the target
  overlay.querySelectorAll('.modal').forEach(m => m.hidden = true);
  document.getElementById(id).hidden = false;
}
function hideModal() {
  document.getElementById('modal-overlay').hidden = true;
}

// Close buttons
document.querySelectorAll('.modal-close, [data-action="cancel"]').forEach(btn => {
  btn.onclick = hideModal;
});
document.getElementById('modal-overlay').onclick = (e) => {
  if (e.target === document.getElementById('modal-overlay')) hideModal();
};

// ── Create File modal ────────────────────────────────────────
let _previewDebounce = null;
function debouncePreview() {
  clearTimeout(_previewDebounce);
  _previewDebounce = setTimeout(updateFilePreview, 350);
}
async function updateFilePreview() {
  const name = document.getElementById('input-file-name').value.trim();
  const type = document.getElementById('input-file-type').value;
  const pathEl = document.getElementById('file-preview-path');
  if (!name) { pathEl.textContent = '—'; return; }
  try {
    const r = await api.preview(name, type);
    pathEl.textContent = r.status === 'success' ? r.result.preview : '—';
  } catch { pathEl.textContent = '—'; }
}

document.getElementById('btn-new-file').onclick = () => {
  document.getElementById('input-file-name').value = '';
  document.getElementById('input-file-content').value = '';
  document.getElementById('file-preview-path').textContent = '—';
  showModal('modal-create-file');
  document.getElementById('input-file-name').focus();
};
document.getElementById('input-file-name').oninput = debouncePreview;
document.getElementById('input-file-type').onchange = debouncePreview;

document.getElementById('btn-create-file-submit').onclick = async () => {
  const name    = document.getElementById('input-file-name').value.trim();
  const type    = document.getElementById('input-file-type').value;
  const content = document.getElementById('input-file-content').value;
  if (!name) { toast('Enter a file name', 'error'); return; }
  const r = await api.create(name, type, content);
  if (r.status === 'success') {
    toast(`Created ${r.result.path}`, 'success');
    hideModal();
    await refresh();
  } else {
    toast(r.error, 'error');
  }
};

// ── Create Dir modal ─────────────────────────────────────────
let _dirPreviewDebounce = null;
async function updateDirPreview() {
  const name  = document.getElementById('input-dir-name').value.trim();
  const pathEl = document.getElementById('dir-preview-path');
  if (!name) { pathEl.textContent = '—'; return; }
  try {
    const r = await api.preview(name, '');   // empty type = directory
    pathEl.textContent = r.status === 'success' ? r.result.preview : '—';
  } catch { pathEl.textContent = '—'; }
}

document.getElementById('btn-new-dir').onclick = () => {
  document.getElementById('input-dir-name').value = '';
  document.getElementById('dir-preview-path').textContent = '—';
  showModal('modal-create-dir');
  document.getElementById('input-dir-name').focus();
};
document.getElementById('input-dir-name').oninput = () => {
  clearTimeout(_dirPreviewDebounce);
  _dirPreviewDebounce = setTimeout(updateDirPreview, 350);
};
document.getElementById('btn-create-dir-submit').onclick = async () => {
  const name = document.getElementById('input-dir-name').value.trim();
  if (!name) { toast('Enter a folder name', 'error'); return; }
  const r = await api.mkdir(name);
  if (r.status === 'success') {
    toast(`Created ${r.result.path}`, 'success');
    hideModal();
    await refresh();
  } else {
    toast(r.error, 'error');
  }
};

// ── Delete modal ─────────────────────────────────────────────
function askDelete(path) {
  S.pendingDelete = path;
  document.getElementById('delete-message').textContent =
    `Delete "${path.split('/').pop()}"?`;
  showModal('modal-delete');
}
document.getElementById('btn-delete-confirm').onclick = async () => {
  if (!S.pendingDelete) return;
  const r = await api.del(S.pendingDelete);
  if (r.status === 'success') {
    toast(`Deleted ${S.pendingDelete}`, 'success');
    S.pendingDelete = null;
    hideModal();
    await refresh();
  } else {
    toast(r.error, 'error');
  }
};

// ── File Info modal ──────────────────────────────────────────
async function showInfo(path) {
  const r = await api.info(path);
  if (r.status !== 'success') { toast(r.error, 'error'); return; }
  const d = r.result;
  const rows = [
    ['Name',        d.name],
    ['Type',        d.type],
    ['Path',        d.path],
    ['Size',        d.size_human || '—'],
    ['MIME',        d.mime_type || '—'],
    ['Modified',    d.modified ? new Date(d.modified).toLocaleString() : '—'],
    ['Created',     d.created  ? new Date(d.created).toLocaleString()  : '—'],
    ['Permissions', d.permissions || '—'],
    ['MD5',         d.md5 || '—'],
  ].filter(([, v]) => v && v !== '—');

  const dl = document.getElementById('info-list');
  dl.innerHTML = rows.map(([k, v]) =>
    `<dt>${k}</dt><dd>${v}</dd>`
  ).join('');
  showModal('modal-info');
}

// ── Organize modal ───────────────────────────────────────────
document.getElementById('btn-organize').onclick = async () => {
  const r = await api.organize(S.currentPath, true);   // dry-run first
  if (r.status !== 'success') { toast(r.error, 'error'); return; }
  const moves = r.result.moves || [];
  const desc  = document.getElementById('organize-description');
  const list  = document.getElementById('organize-preview-list');
  desc.textContent = moves.length
    ? `${moves.length} file(s) will be reorganized in "${S.currentPath}"`
    : 'All files are already compliant — nothing to do.';
  list.innerHTML = moves.length
    ? moves.map(m => `<div class="organize-row">
        <span class="organize-from">${m.from}</span>
        <span class="organize-arr">→</span>
        <span class="organize-to">${m.to}</span>
      </div>`).join('')
    : '<div class="organize-empty">✓ Everything is in order</div>';
  document.getElementById('btn-organize-confirm').disabled = moves.length === 0;
  showModal('modal-organize');
};
document.getElementById('btn-organize-confirm').onclick = async () => {
  const r = await api.organize(S.currentPath, false);
  if (r.status === 'success') {
    toast(`Organized ${r.result.executed} file(s)`, 'success');
    hideModal();
    await refresh();
  } else {
    toast(r.error, 'error');
  }
};

// ── Config modal ─────────────────────────────────────────────
let _configSnapshot = {};
document.getElementById('btn-config-open').onclick = async () => {
  const r = await api.config('get');
  if (r.status !== 'success') { toast(r.error, 'error'); return; }
  _configSnapshot = r.result.naming;
  renderConfigForm(r.result.naming);
  showModal('modal-config');
};

function renderConfigForm(naming) {
  const fields = [
    { key: 'date_prefix',          label: 'Date prefix', desc: 'Prepend YYYY-MM-DD to new filenames' },
    { key: 'auto_categorize',      label: 'Auto-categorize', desc: 'Sort files into type subfolders (documents/, images/, …)' },
    { key: 'normalize_extensions', label: 'Normalize extensions', desc: 'Unify .JPEG → .jpg, .HTM → .html, etc.' },
  ];
  const strFields = [
    { key: 'date_format', label: 'Date format', desc: 'strftime format for date prefix' },
  ];
  document.getElementById('config-form').innerHTML =
    fields.map(f => `
      <div class="config-row">
        <div>
          <div class="config-label">${f.label}</div>
          <div class="config-desc">${f.desc}</div>
        </div>
        <label class="toggle">
          <input type="checkbox" data-key="${f.key}" ${naming[f.key] ? 'checked' : ''}>
          <span class="toggle-track"></span>
        </label>
      </div>`).join('') +
    strFields.map(f => `
      <div class="config-row">
        <div>
          <div class="config-label">${f.label}</div>
          <div class="config-desc">${f.desc}</div>
        </div>
        <input type="text" class="form-input" style="width:120px" data-key="${f.key}" value="${naming[f.key] || ''}">
      </div>`).join('');
}

document.getElementById('btn-config-save').onclick = async () => {
  const values = {};
  document.querySelectorAll('#config-form [data-key]').forEach(el => {
    values[el.dataset.key] = el.type === 'checkbox' ? el.checked : el.value;
  });
  const r = await api.config('set', values);
  if (r.status === 'success') {
    toast('Configuration saved', 'success');
    hideModal();
  } else {
    toast(r.error, 'error');
  }
};
document.getElementById('btn-config-reset').onclick = async () => {
  const r = await api.config('reset');
  if (r.status === 'success') {
    renderConfigForm(r.result.current);
    toast('Reset to defaults', 'info');
  }
};

// ══════════════════════════════════════════════════════════════
// 9. SEARCH
// ══════════════════════════════════════════════════════════════
document.getElementById('btn-search-toggle').onclick = openSearch;
document.getElementById('btn-search-close').onclick = closeSearch;

function openSearch() {
  document.getElementById('search-overlay').hidden = false;
  document.getElementById('search-input').focus();
}
function closeSearch() {
  document.getElementById('search-overlay').hidden = true;
  document.getElementById('search-input').value = '';
  document.getElementById('search-results').innerHTML = '';
}

document.getElementById('search-input').oninput = () => {
  clearTimeout(S.searchDebounce);
  S.searchDebounce = setTimeout(runSearch, 300);
};
document.getElementById('search-type-filter').onchange = runSearch;

async function runSearch() {
  const query = document.getElementById('search-input').value.trim();
  const type  = document.getElementById('search-type-filter').value;
  const results = document.getElementById('search-results');
  if (!query) { results.innerHTML = ''; return; }

  results.innerHTML = '<div class="search-loading"><div class="spinner"></div></div>';
  const r = await api.search(query, type);
  if (r.status !== 'success') { results.innerHTML = `<div class="search-empty">${r.error}</div>`; return; }

  if (!r.result.results.length) {
    results.innerHTML = '<div class="search-empty">No files found</div>';
    return;
  }
  results.innerHTML = r.result.results.map(f => {
    const fakeEntry = { type: 'file', extension: f.extension };
    return `<div class="search-result-item" data-path="${f.path}">
      <span class="search-result-icon">${icon(fakeEntry)}</span>
      <div class="search-result-info">
        <div class="search-result-name">${f.name}</div>
        <div class="search-result-path">${f.path}</div>
      </div>
      <span class="search-result-size">${fmtSize(f.size)}</span>
    </div>`;
  }).join('');

  // Click a result → navigate to its parent directory
  results.querySelectorAll('.search-result-item').forEach(item => {
    item.onclick = () => {
      const path = item.dataset.path;
      const dir  = path.includes('/') ? path.substring(0, path.lastIndexOf('/')) : '.';
      closeSearch();
      navigate(dir);
    };
  });
}

// Keyboard shortcut: Ctrl+K to open search
document.addEventListener('keydown', (e) => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') { e.preventDefault(); openSearch(); }
  if (e.key === 'Escape') {
    if (!document.getElementById('search-overlay').hidden) { closeSearch(); return; }
    if (!document.getElementById('modal-overlay').hidden)  { hideModal(); }
  }
});

// ══════════════════════════════════════════════════════════════
// 10. SIDEBAR / HISTORY PANEL TOGGLES
// ══════════════════════════════════════════════════════════════
document.getElementById('btn-sidebar-toggle').onclick = () => {
  const sidebar = document.getElementById('sidebar');
  if (window.innerWidth <= 900) {
    sidebar.classList.toggle('mobile-open');
  } else {
    sidebar.classList.toggle('collapsed');
    const layout = document.getElementById('app-layout');
    const cols   = getComputedStyle(layout).gridTemplateColumns.split(' ');
    layout.style.gridTemplateColumns = sidebar.classList.contains('collapsed')
      ? `0 ${cols[1]} ${cols[2]}`
      : `220px ${cols[1]} ${cols[2]}`;
  }
};

document.getElementById('btn-history-toggle').onclick = () => {
  const panel = document.getElementById('history-panel');
  if (window.innerWidth <= 900) {
    panel.classList.toggle('mobile-open');
  } else {
    panel.classList.toggle('collapsed');
    const layout = document.getElementById('app-layout');
    const cols   = getComputedStyle(layout).gridTemplateColumns.split(' ');
    layout.style.gridTemplateColumns = panel.classList.contains('collapsed')
      ? `${cols[0]} ${cols[1]} 0`
      : `${cols[0]} ${cols[1]} 260px`;
  }
};

// ══════════════════════════════════════════════════════════════
// 11. THEME TOGGLE
// ══════════════════════════════════════════════════════════════
document.getElementById('btn-theme').onclick = () => {
  const html = document.documentElement;
  const isDark = html.dataset.theme === 'dark';
  html.dataset.theme = isDark ? 'light' : 'dark';
  document.getElementById('btn-theme').textContent = isDark ? '🌙' : '☀️';
  localStorage.setItem('lfh-theme', html.dataset.theme);
};
// Restore saved theme
const savedTheme = localStorage.getItem('lfh-theme');
if (savedTheme) {
  document.documentElement.dataset.theme = savedTheme;
  document.getElementById('btn-theme').textContent = savedTheme === 'dark' ? '🌙' : '☀️';
}

// ══════════════════════════════════════════════════════════════
// 12. SORT
// ══════════════════════════════════════════════════════════════
document.getElementById('sort-select').onchange = (e) => {
  S.sortKey = e.target.value;
  renderFileGrid();
};

// ══════════════════════════════════════════════════════════════
// 13. REFRESH  (manual + auto-polling fallback)
// ══════════════════════════════════════════════════════════════
async function refresh() {
  await Promise.all([loadCurrentDir(), loadHistory()]);
}

document.getElementById('btn-refresh').onclick = async () => {
  await refresh();
  // Reset countdown only when in polling mode
  if (_pollIntervalId) {
    S.countdown = 30;
    const cdEl = document.getElementById('refresh-countdown');
    if (cdEl) cdEl.textContent = '30';
  }
};

let _pollIntervalId = null;

function _startPolling() {
  if (_pollIntervalId) return;   // already running
  S.countdown = 30;
  const cdEl = document.getElementById('refresh-countdown');
  if (cdEl) cdEl.textContent = '30';
  _pollIntervalId = setInterval(async () => {
    S.countdown--;
    const countdownEl = document.getElementById('refresh-countdown');
    if (countdownEl) countdownEl.textContent = S.countdown;
    if (S.countdown <= 0) {
      S.countdown = 30;
      await refresh();
    }
  }, 1000);
}

// ══════════════════════════════════════════════════════════════
// 14. WEBSOCKET  — real-time server-push replaces polling
// ══════════════════════════════════════════════════════════════
let _ws            = null;
let _wsRetryDelay  = 1000;
let _wsRetryTimer  = null;
let _wsPingTimer   = null;

function wsConnect() {
  clearTimeout(_wsRetryTimer);
  const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
  try {
    _ws = new WebSocket(`${proto}//${location.host}/ws`);
  } catch {
    _wsScheduleRetry();
    return;
  }

  _ws.onopen = () => {
    _wsRetryDelay = 1000;         // reset back-off on successful connect
    _wsSetLiveMode(true);
    _wsPingTimer = setInterval(() => {
      if (_ws?.readyState === WebSocket.OPEN) _ws.send('ping');
    }, 20000);
  };

  _ws.onmessage = (e) => {
    try {
      const ev = JSON.parse(e.data);
      if (ev.type === 'refresh') refresh();
    } catch { /* pong / non-JSON messages are fine */ }
  };

  _ws.onclose = () => {
    clearInterval(_wsPingTimer);
    _wsSetLiveMode(false);
    _wsScheduleRetry();
  };

  _ws.onerror = () => _ws?.close();
}

function _wsScheduleRetry() {
  _wsRetryTimer  = setTimeout(wsConnect, Math.min(_wsRetryDelay, 30000));
  _wsRetryDelay  = Math.min(_wsRetryDelay * 2, 30000);
}

function _wsSetLiveMode(live) {
  const dot  = document.getElementById('server-dot');
  const cdEl = document.getElementById('refresh-countdown');
  if (live) {
    dot.classList.add('ws-live');
    dot.title = 'Live — real-time updates active';
    if (cdEl) cdEl.textContent = 'LIVE';
    // Stop the polling fallback
    clearInterval(_pollIntervalId);
    _pollIntervalId = null;
  } else {
    dot.classList.remove('ws-live');
    dot.title = 'Server status (polling fallback)';
    _startPolling();    // fall back to 30 s countdown
  }
}

// ══════════════════════════════════════════════════════════════
// 15. BULK SELECTION  (Ctrl+click or Select-mode button)
// ══════════════════════════════════════════════════════════════
function toggleSelect(path) {
  if (S.selected.has(path)) S.selected.delete(path);
  else S.selected.add(path);
  // Update the specific card's visual without a full re-render
  const card = document.querySelector(`.file-card[data-path="${CSS.escape(path)}"]`);
  if (card) card.classList.toggle('selected', S.selected.has(path));
  _renderBulkBar();
}

function _renderBulkBar() {
  const bar   = document.getElementById('bulk-bar');
  const count = S.selected.size;
  bar.hidden  = count === 0;
  document.getElementById('bulk-count').textContent =
    `${count} item${count !== 1 ? 's' : ''} selected`;
}

function _clearSelection() {
  S.selected.clear();
  S.selectMode = false;
  document.getElementById('btn-select-mode').classList.remove('active');
  document.querySelectorAll('.file-card.selected').forEach(c => c.classList.remove('selected'));
  _renderBulkBar();
}

// Select-mode toggle button
document.getElementById('btn-select-mode').onclick = () => {
  S.selectMode = !S.selectMode;
  document.getElementById('btn-select-mode').classList.toggle('active', S.selectMode);
  if (!S.selectMode) _clearSelection();
};

// Deselect all
document.getElementById('btn-bulk-deselect').onclick = _clearSelection;

// ── Bulk delete ───────────────────────────────────────────────
document.getElementById('btn-bulk-delete').onclick = () => {
  const count = S.selected.size;
  document.getElementById('bulk-delete-message').textContent =
    `Delete ${count} item${count !== 1 ? 's' : ''}?`;
  showModal('modal-bulk-delete');
};

document.getElementById('btn-bulk-delete-confirm').onclick = async () => {
  const paths = [...S.selected];
  let failed = 0;
  for (const p of paths) {
    const r = await api.del(p);
    if (r.status !== 'success') failed++;
  }
  hideModal();
  _clearSelection();
  if (failed) toast(`${failed} deletion(s) failed`, 'error');
  else toast(`Deleted ${paths.length} item(s)`, 'success');
  await refresh();
};

// ── Bulk move ─────────────────────────────────────────────────
document.getElementById('btn-bulk-move').onclick = () => {
  const count = S.selected.size;
  document.getElementById('bulk-move-description').textContent =
    `Move ${count} item${count !== 1 ? 's' : ''} to:`;
  document.getElementById('bulk-move-dest').value = '';
  // Populate destination suggestions from tree data
  const suggestions = document.getElementById('bulk-move-suggestions');
  suggestions.innerHTML = Object.keys(S.treeData)
    .filter(p => p !== '.')
    .map(p => `<option value="${p + '/'}">`)
    .join('');
  showModal('modal-bulk-move');
};

document.getElementById('btn-bulk-move-confirm').onclick = async () => {
  const dest = document.getElementById('bulk-move-dest').value.trim();
  if (!dest) { toast('Enter a destination folder', 'error'); return; }
  const destDir = dest.endsWith('/') ? dest : dest + '/';
  const paths = [...S.selected];
  let failed = 0;
  for (const p of paths) {
    const r = await api.move(p, destDir);
    if (r.status !== 'success') failed++;
  }
  hideModal();
  _clearSelection();
  if (failed) toast(`${failed} move(s) failed`, 'error');
  else toast(`Moved ${paths.length} item(s)`, 'success');
  await refresh();
};

// ══════════════════════════════════════════════════════════════
// 16. AI COMMAND PANEL
// ══════════════════════════════════════════════════════════════
(function () {
  const panel       = document.getElementById('ai-panel');
  const input       = document.getElementById('ai-input');
  const resultBox   = document.getElementById('ai-result');
  const explanation = document.getElementById('ai-explanation');
  const resolvedCode= document.getElementById('ai-resolved-code');
  const warning     = document.getElementById('ai-warning');
  const errorBox    = document.getElementById('ai-error');
  const loading     = document.getElementById('ai-loading');

  // Pending resolved command (set after NL parse, cleared after execute/discard)
  let _pending = null;

  function _resetResult() {
    resultBox.hidden  = true;
    errorBox.hidden   = true;
    loading.hidden    = true;
    warning.hidden    = true;
    _pending          = null;
  }

  function _showPanel() {
    panel.classList.add('open');
    input.focus();
  }

  function _hidePanel() {
    panel.classList.remove('open');
    input.value = '';
    _resetResult();
  }

  // Open / close
  document.getElementById('btn-ai-open').onclick  = _showPanel;
  document.getElementById('btn-ai-close').onclick = _hidePanel;

  // Send command
  async function _sendCommand() {
    const cmd = input.value.trim();
    if (!cmd) return;

    _resetResult();
    loading.hidden = false;

    let r;
    try {
      r = await invoke('nlcommandtool', { command: cmd });
    } catch (err) {
      loading.hidden = true;
      errorBox.hidden = false;
      errorBox.textContent = `Network error: ${err.message}`;
      return;
    }

    loading.hidden = true;

    if (r.status !== 'success') {
      errorBox.hidden = false;
      errorBox.textContent = r.error || 'AI backend unavailable or could not parse command.';
      return;
    }

    const res = r.result;
    _pending = { tool: res.tool, payload: res.payload };

    explanation.textContent = res.explanation || '';
    resolvedCode.textContent = `${res.tool}  ${JSON.stringify(res.payload)}`;
    warning.hidden = !res.requires_confirmation;
    resultBox.hidden = false;
  }

  document.getElementById('btn-ai-send').onclick = _sendCommand;
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); _sendCommand(); }
    if (e.key === 'Escape') _hidePanel();
  });

  // Execute resolved command
  document.getElementById('btn-ai-execute').onclick = async () => {
    if (!_pending) return;
    const { tool, payload } = _pending;
    _resetResult();
    loading.hidden = false;

    let r;
    try {
      r = await invoke(tool, payload);
    } catch (err) {
      loading.hidden = true;
      errorBox.hidden = false;
      errorBox.textContent = `Execution error: ${err.message}`;
      return;
    }

    loading.hidden = true;

    if (r.status === 'success') {
      toast('Command executed successfully', 'success');
      _hidePanel();
      await refresh();
    } else {
      errorBox.hidden = false;
      errorBox.textContent = r.error || 'Command failed.';
    }
  };

  // Discard
  document.getElementById('btn-ai-discard').onclick = () => {
    _resetResult();
    input.value = '';
    input.focus();
  };
})();

// ══════════════════════════════════════════════════════════════
// 17. VOICE / PUSH-TO-TALK
// ══════════════════════════════════════════════════════════════
(function () {
  const micBtn    = document.getElementById('btn-mic');
  const voiceBar  = document.getElementById('voice-bar');
  const voiceStat = document.getElementById('voice-status');
  const cancelBtn = document.getElementById('btn-voice-cancel');

  let _recorder   = null;   // MediaRecorder instance
  let _chunks     = [];     // recorded audio chunks
  let _recording  = false;
  let _stream     = null;   // MediaStream (held to stop tracks)

  // ── Helpers ─────────────────────────────────────────────────
  function _setRecording(on) {
    _recording = on;
    micBtn.classList.toggle('recording', on);
    voiceBar.classList.toggle('open', on);
  }

  async function _startRecording() {
    if (_recording) return;
    try {
      _stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch {
      toast('Microphone access denied', 'error');
      return;
    }

    _chunks = [];
    // Prefer PCM-friendly format; fallback to whatever browser supports
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=pcm')
      ? 'audio/webm;codecs=pcm'
      : MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : '';

    _recorder = mimeType ? new MediaRecorder(_stream, { mimeType }) : new MediaRecorder(_stream);
    _recorder.ondataavailable = e => { if (e.data.size > 0) _chunks.push(e.data); };
    _recorder.onstop = _onStop;
    _recorder.start();
    _setRecording(true);
    voiceStat.textContent = 'Listening…  release to transcribe';
  }

  function _stopRecording() {
    if (!_recording || !_recorder) return;
    _recorder.stop();
    _stream.getTracks().forEach(t => t.stop());
    _stream = null;
    _setRecording(false);
  }

  async function _onStop() {
    const blob = new Blob(_chunks, { type: _recorder.mimeType || 'audio/webm' });
    _chunks = [];

    // Convert blob → ArrayBuffer → base64
    const arrayBuf = await blob.arrayBuffer();
    const uint8    = new Uint8Array(arrayBuf);
    const b64      = btoa(String.fromCharCode(...uint8));

    voiceStat.textContent = 'Transcribing…';
    voiceBar.classList.add('open');

    let r;
    try {
      r = await invoke('voicetool', { audio: b64, sample_rate: 16000 });
    } catch (err) {
      toast(`Voice error: ${err.message}`, 'error');
      voiceBar.classList.remove('open');
      return;
    }

    voiceBar.classList.remove('open');

    if (r.status !== 'success') {
      toast(r.error || 'STT backend unavailable — set STT_BACKEND to enable voice', 'error', 5000);
      return;
    }

    const transcript = (r.result.transcript || '').trim();
    if (!transcript) {
      toast('No speech detected', 'info');
      return;
    }

    // Populate the AI command input and trigger the NL pipeline
    const aiInput = document.getElementById('ai-input');
    const aiPanel = document.getElementById('ai-panel');
    aiInput.value = transcript;
    aiPanel.classList.add('open');
    aiInput.focus();

    // Auto-send to NL pipeline
    document.getElementById('btn-ai-send').click();

    toast(`🎤 "${transcript}"`, 'success', 4000);
  }

  // ── Cancel ──────────────────────────────────────────────────
  function _cancel() {
    if (!_recording) return;
    _recorder.ondataavailable = null;
    _recorder.onstop = null;
    _recorder.stop();
    if (_stream) { _stream.getTracks().forEach(t => t.stop()); _stream = null; }
    _chunks = [];
    _setRecording(false);
  }

  cancelBtn.onclick = _cancel;

  // ── Mouse: click to start / click again to stop ──────────────
  micBtn.addEventListener('click', () => {
    if (_recording) _stopRecording();
    else            _startRecording();
  });

  // ── Keyboard: hold Space to record (only when not typing) ───
  document.addEventListener('keydown', (e) => {
    if (e.code !== 'Space') return;
    if (e.repeat) return;
    // Don't intercept Space when focus is in a text input/textarea
    const tag = document.activeElement?.tagName;
    if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return;
    e.preventDefault();
    _startRecording();
  });

  document.addEventListener('keyup', (e) => {
    if (e.code === 'Space') _stopRecording();
  });

  // ── Escape cancels ───────────────────────────────────────────
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && _recording) { e.preventDefault(); _cancel(); }
  });
})();

// ══════════════════════════════════════════════════════════════
// 18. INIT
// ══════════════════════════════════════════════════════════════
(async () => {
  try {
    // Load workspace root tree
    await loadTree('.');
    // Load initial directory listing + history together
    await Promise.all([loadCurrentDir(), loadHistory()]);
  } catch {
    toast('Could not connect to LocalFileHandler server', 'error', 8000);
    document.getElementById('server-dot').classList.add('offline');
  }
  // Start polling fallback immediately; WS will replace it when connected
  _startPolling();
  wsConnect();
})();
