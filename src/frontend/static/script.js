
// Define questionCache as an empty array
let questionCache = [];

// --- UI Logic: Modal Fields Toggle ---
function toggleDbFields() {
    const dbType = document.getElementById('dbSelect').value;
    const sqliteDiv = document.getElementById('sqliteFields');
    const pgDiv = document.getElementById('postgresFields');

    if (dbType === 'SQLITE') {
        sqliteDiv.style.display = 'block';
        pgDiv.style.display = 'none';
    } else {
        sqliteDiv.style.display = 'none';
        pgDiv.style.display = 'block';
    }
}

// --- Logic for Top Row ---
async function initTopRow() {
    // 1) Schema image -> img1
    const img1 = document.getElementById('img1');
    try {
        const resp = await fetch('/schema/image');
        if (!resp.ok) throw new Error('Schema image fetch failed');
        const blob = await resp.blob();
        const url = URL.createObjectURL(blob);
        const ct = resp.headers.get('content-type') || '';
        if (ct) img1.dataset.contentType = ct;
        // store schema blob for downloads
        window.schemaBlob = blob;
        window.schemaContentType = ct;
        // also expose a stable URL for preview/download fallback
        window.schemaImageUrl = url;
        img1.src = url;
        img1.dataset.previewTitle = 'Database Schema';
        img1.classList.add('loaded');
    } catch (err) {
        console.warn('Could not load schema image:', err);
        img1.src = 'https://picsum.photos/seed/schema/600/400';
        img1.classList.add('loaded');
    }

    // 2) Describe -> render as SVG and set to img2
    const table1 = document.getElementById('table1');
    try {
        const resp = await fetch('/describe');
        if (!resp.ok) throw new Error('Describe fetch failed');
        const data = await resp.json();
        const rows = data.rows || [];

        const col_1_rowspans = rows.map(r => r['table']).reduce((acc, e) => acc.set(e, (acc.get(e) || 0) + 1), new Map());

        function colorizeDtype(dtype) {
            const type = String(dtype).toLowerCase();
            if (type.includes('int') || type.includes('numeric'))
                return `<span title="Numeric columns" style="color: green;">${dtype}</span>`;
            else if (type.includes('bool'))
                return `<span title="Boolean columns" style="color: orange;">${dtype}</span>`;
            else if (type.includes('char'))
                return `<span title="Character columns" style="color: blue;">${dtype}</span>`;
            else if (type.includes('datetime'))
                return `<span title="Date and Time columns" style="color: purple;">${dtype}</span>`;
            return `<span title="Other columns">${dtype}</span>`;
        }

        function renderValue(value, column) {
            if (value === null || value === undefined || value === '') {
                return '<span style="opacity: 0.25;">N/A</span>';
            }
            if (!isNaN(value) && !isNaN(parseFloat(value))) {
                return parseFloat(value).toFixed(2);
            }
            value = String(value).trim();
            if (column.toLowerCase() === 'dtype') {
                return colorizeDtype(value);
            }
            if (column.toLowerCase().includes('table') || column.toLowerCase().includes('column')) {
                return `<i>${value}</i>`;
            }
            return String(value);
        }

        function applyIndexStyle(value) {
            return `<i>${value}</i>`;
        }

        const header_col = Object.keys(rows[0] || {});

        const tableHtml = `
                    <div style="max-height: 100%; overflow-y: auto; width: 100%; border: 1px solid #dee2e6; border-radius: 5px;">
                        <table class="table table-striped" style="border-collapse: collapse; width: 100%; border: 1px solid #dee2e6;">
                        <thead style="z-index:2; position: sticky; top: 0; background-color: #f8f9fa; border-bottom: 2px solid #dee2e6;">
                            <tr>${Object.keys(rows[0] || {}).map(key => `<th style="text-align: center; border: 1px solid #dee2e6; padding: 8px; border-bottom: 2px solid #dee2e6;">${key.toUpperCase()}</th>`).join('')}</tr>
                        </thead>
                        <tbody>
                            ${rows.map((row, row_idx) => `
                            <tr>${Object.values(row).map((value, col_idx) => {
            if (col_idx == 0) {
                if (row_idx === 0 || rows[row_idx - 1]['table'] !== row['table']) {
                    const rowspan = col_1_rowspans.get(row['table']) || 1;
                    return `<th rowspan="${rowspan}" style="border: 1px solid #dee2e6; padding: 8px;">${applyIndexStyle(value)}</th>`;
                } else {
                    return ''; // Skip rendering for duplicate rows
                }
            }
            if (col_idx == 1) return `<th style="border: 1px solid #dee2e6; padding: 8px;">${applyIndexStyle(value)}</th>`;
            return `<td style="border: 1px solid #dee2e6; padding: 8px;">${renderValue(value, header_col[col_idx])}</td>`;
        }).join('')}</tr>
                        `).join('')}
                        </tbody>
                        </table>
                    </div>
                    `;
        table1.innerHTML = tableHtml;

        // store describe data for download
        window.describeData = rows;
        window.describeColumns = header_col;

        table1.dataset.previewTitle = 'DB Description';
        table1.classList.add('loaded');
    } catch (err) {
        console.warn('Could not load describe table:', err);
    }

    // Attach preview click handlers after top-row population
    attachPreviewHandlers();
}

// Attach click handlers to images/tables to open preview modal
function attachPreviewHandlers() {
    const ids = ['img1', 'resultImage'];
    ids.forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;

        // Clear any previous handler
        el.onclick = null;

        // Special case: the generated visualization (#resultImage) should only be clickable
        // when it has loaded content (we use the 'loaded' class to indicate this).
        if (id === 'resultImage') {
            if (el.classList && el.classList.contains('loaded') && el.src) {
                el.style.cursor = 'zoom-in';
                el.onclick = () => {
                    const title = el.dataset.previewTitle || el.alt || 'Preview';
                    const src = el.src || el.dataset.src;
                    if (!src) return;
                    const contentType = el.dataset.contentType || null;
                    showPreview(title, src, contentType);
                };
            } else {
                el.style.cursor = 'default';
            }
            return;
        }

        // For other elements (top-row images) make clickable only if they have a src
        const src = el.src || el.dataset.src;
        if (src) {
            el.style.cursor = 'zoom-in';
            el.onclick = () => {
                const title = el.dataset.previewTitle || el.alt || 'Preview';
                const s = el.src || el.dataset.src;
                if (!s) return;
                const contentType = el.dataset.contentType || null;
                showPreview(title, s, contentType);
            };
        } else {
            el.style.cursor = 'default';
        }
    });
}

function showPreview(title, src) {
    console.log('Showing preview for', title, src);
    const modalEl = document.getElementById('previewModal');
    const titleEl = document.getElementById('previewModalTitle');
    const bodyEl = document.getElementById('previewModalBody');
    if (!modalEl || !bodyEl || !titleEl) return;
    titleEl.innerText = title;
    // Clear body
    bodyEl.innerHTML = '';
    // Determine if content is SVG by checking content-type or URL
    const contentType = (bodyEl.dataset.contentType || '') || (document.getElementById('resultImage')?.dataset.contentType || '');
    const isSvg = (typeof contentType === 'string' && contentType.includes('svg')) || (typeof src === 'string' && src.startsWith('data:image/svg+xml')) || (typeof src === 'string' && src.endsWith('.svg'));
    let contentEl;
    if (isSvg) {
        const obj = document.createElement('object');
        obj.type = 'image/svg+xml';
        obj.data = src;
        obj.style.width = '100%';
        obj.style.height = '100%';
        obj.style.display = 'block';
        bodyEl.appendChild(obj);
        contentEl = obj;
    } else {
        const img = document.createElement('img');
        img.src = src;
        img.style.maxWidth = '100%';
        img.style.maxHeight = '100%';
        img.style.objectFit = 'contain';
        img.style.display = 'block';
        bodyEl.appendChild(img);
        contentEl = img;
    }

    // open modal
    try {
        if (window.bootstrap && bootstrap.Modal && typeof bootstrap.Modal.getOrCreateInstance === 'function') {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        } else if (window.bootstrap && bootstrap.Modal) {
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
        } else {
            modalEl.classList.add('show');
            modalEl.style.display = 'block';
            modalEl.removeAttribute('aria-hidden');
            modalEl.setAttribute('aria-modal', 'true');
            document.body.classList.add('modal-open');
            console.warn('Bootstrap not available; opened modal with CSS fallback.');
        }
    } catch (err) {
        console.error('Failed to show preview modal:', err);
    }

    // enable pan & zoom
    enablePanAndZoom(bodyEl, contentEl);
}

// Show HTML content (table) in preview modal
function showPreviewHtml(title, html) {
    const modalEl = document.getElementById('previewModal');
    const titleEl = document.getElementById('previewModalTitle');
    const bodyEl = document.getElementById('previewModalBody');
    if (!modalEl || !bodyEl || !titleEl) return;
    titleEl.innerText = title;
    bodyEl.innerHTML = '';
    const wrapper = document.createElement('div');
    wrapper.style.width = '100%';
    wrapper.style.height = '100%';
    wrapper.style.overflow = 'auto';
    wrapper.innerHTML = html;
    bodyEl.appendChild(wrapper);

    try {
        if (window.bootstrap && bootstrap.Modal && typeof bootstrap.Modal.getOrCreateInstance === 'function') {
            const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
            modal.show();
        } else if (window.bootstrap && bootstrap.Modal) {
            const modal = new bootstrap.Modal(modalEl);
            modal.show();
        } else {
            modalEl.classList.add('show');
            modalEl.style.display = 'block';
            modalEl.removeAttribute('aria-hidden');
            modalEl.setAttribute('aria-modal', 'true');
            document.body.classList.add('modal-open');
        }
    } catch (err) {
        console.error('Failed to show preview modal:', err);
    }
}


// Pan & Zoom helpers
let _panZoomCleanup = null;
function enablePanAndZoom(container, content) {
    // cleanup previous
    if (_panZoomCleanup) {
        try { _panZoomCleanup(); } catch (e) { }
        _panZoomCleanup = null;
    }

    // Create a wrapper that will receive transforms
    const wrapper = document.createElement('div');
    wrapper.style.width = '100%';
    wrapper.style.height = '100%';
    wrapper.style.overflow = 'hidden';
    // wrapper.style.display = 'flex';
    // wrapper.style.alignItems = 'center';
    // wrapper.style.justifyContent = 'center';
    wrapper.style.position = 'relative';

    // move content into the wrapper and center it
    // Use relative positioning so flexbox can center the element,
    // and set transform-origin to the element center for natural zooming.
    content.style.position = 'absolute';
    content.style.left = '50%';
    content.style.top = '50%';

    content.style.transformOrigin = '50% 50%';

    wrapper.appendChild(content);
    container.appendChild(wrapper);

    // state
    let scale = 1;
    let translate = { x: 0, y: 0 };
    let dragging = false;
    let last = { x: 0, y: 0 };


    function applyTransform() {
        content.style.transform = `translate(calc(-50% + ${translate.x}px), calc(-50% + ${translate.y}px)) scale(${scale})`;
    }

    function toLocalCoords(evt) {
        const rect = wrapper.getBoundingClientRect();
        return { x: evt.clientX - rect.left, y: evt.clientY - rect.top };
    }
    function onWheel(e) {
        e.preventDefault();
        const delta = -e.deltaY; // wheel up -> zoom in
        const zoomFactor = Math.exp(delta * 0.0015);
        // Choose reference point: mouse position or center, based on preview modal setting
        const mouse = toLocalCoords(e);

        const s2 = Math.max(0.2, Math.min(6, scale * zoomFactor));
        // keep the point under cursor stationary
        const t = translate;
        const newTx = t.x + (1 - s2 / scale) * (mouse.x - wrapper.offsetWidth / 2 - t.x);
        const newTy = t.y + (1 - s2 / scale) * (mouse.y - wrapper.offsetHeight / 2 - t.y);
        scale = s2;
        translate.x = newTx;
        translate.y = newTy;
        applyTransform();
    }

    function onMouseDown(e) {
        e.preventDefault();
        dragging = true;
        last = { x: e.clientX, y: e.clientY };
        wrapper.style.cursor = 'grabbing';
    }

    function onMouseMove(e) {
        if (!dragging) return;
        const dx = e.clientX - last.x;
        const dy = e.clientY - last.y;
        last = { x: e.clientX, y: e.clientY };
        translate.x += dx;
        translate.y += dy;
        applyTransform();
    }

    function onMouseUp() {
        dragging = false;
        wrapper.style.cursor = 'default';
    }

    function onDblClick() {
        // reset
        scale = 1;
        translate = { x: 0, y: 0 };
        applyTransform();
    }

    // attach
    wrapper.addEventListener('wheel', onWheel, { passive: false });
    wrapper.addEventListener('mousedown', onMouseDown);
    window.addEventListener('mousemove', onMouseMove);
    window.addEventListener('mouseup', onMouseUp);
    wrapper.addEventListener('dblclick', onDblClick);

    // initial transform
    applyTransform();

    // expose a reset function so UI can recentre the preview
    try {
        window._previewPanZoomReset = () => {
            try {
                scale = 1;
                translate = { x: 0, y: 0 };
                applyTransform();
                // ensure wrapper cursor resets
                wrapper.style.cursor = 'default';
            } catch (e) { console.warn('Failed to reset preview pan/zoom', e); }
        };
    } catch (e) { /* ignore */ }

    // cleanup function
    _panZoomCleanup = () => {
        try { wrapper.removeEventListener('wheel', onWheel); } catch (e) { }
        try { wrapper.removeEventListener('mousedown', onMouseDown); } catch (e) { }
        try { window.removeEventListener('mousemove', onMouseMove); } catch (e) { }
        try { window.removeEventListener('mouseup', onMouseUp); } catch (e) { }
        try { wrapper.removeEventListener('dblclick', onDblClick); } catch (e) { }
        // unwrap content back to original container
        try {
            container.removeChild(wrapper);
            content.style.position = '';
            content.style.left = '';
            content.style.top = '';
            content.style.transformOrigin = '';
            content.style.transform = '';
            container.appendChild(content);
        } catch (e) { }
        _panZoomCleanup = null;
        // remove exposed reset function if present
        try { if (window._previewPanZoomReset) delete window._previewPanZoomReset; } catch (e) { }
    };
}

function renderDescribeAsText(rows) {
    if (!rows || rows.length === 0) return 'No description available';
    // Show first N rows for compactness
    const max = 10;
    const keys = Object.keys(rows[0]);
    const header = keys.join(' | ');
    const lines = [header, '-'.repeat(header.length)];
    rows.slice(0, max).forEach(r => {
        lines.push(keys.map(k => String(r[k])).join(' | '));
    });
    if (rows.length > max) lines.push(`... ${rows.length - max} more rows`);
    return lines.join('\n');
}

function makeSvgFromText(text, width = 600, height = 400) {
    const lines = text.split('\n');
    const lineHeight = 14;
    const fontSize = 12;
    const padding = 8;
    const svgLines = lines.map((ln, i) => `
        <tspan x="${padding}" y="${padding + (i + 1) * lineHeight}">${escapeXml(ln)}</tspan>`).join('');

    return `<?xml version="1.0" encoding="UTF-8"?>\n<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}">\n  <rect width="100%" height="100%" fill="#ffffff"/>\n  <text font-family="monospace" font-size="${fontSize}" fill="#111">${svgLines}\n  </text>\n</svg>`;
}

function escapeXml(unsafe) {
    return unsafe.replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&apos', '\"': '&quot;' }[c]));
}

// --- Logic for Bottom Row ---
function handleSend() {
    const textarea = document.getElementById('promptInput');
    const resultLoader = document.getElementById('resultLoader');
    const resultImg = document.getElementById('resultImage');
    const statusText = document.getElementById('statusText');
    const outputBadge = document.getElementById('outputBadge');

    const textValue = textarea.value.trim();
    if (!textValue) {
        alert('Please enter some text first.');
        return;
    }

    // UI: loading
    statusText.innerText = 'Sending request...';
    // disable result header controls while loading / until a result is available
    try { setResultControlsEnabled(false); } catch (e) { }
    resultLoader.style.display = 'block';
    resultImg.classList.remove('loaded');
    outputBadge.className = 'badge bg-warning bg-opacity-10 text-warning status-badge';
    outputBadge.innerText = 'Processing';



    fetch('/question', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: textValue }),
    })
        .then(async resp => {
            if (!resp.ok) {
                const txt = await resp.text().catch(() => resp.statusText);
                throw new Error(txt || `Server returned ${resp.status}`);
            }
            const data = await resp.json();

            // Store dataframe for later use
            try {
                window.latestDf = data.df || null;
            } catch (e) {
                window.latestDf = null;
            }

            const resultTable = data.df || null; // "df": {"columns": columns, "rows": records},
            const shouldPlot = Boolean(data.should_plot); // not used here directly, but as what to show preference

            const imageUrl = data.image_url;
            if (!imageUrl) throw new Error('No image URL returned from server');

            // Set image src to the static URL returned by the server
            resultImg.src = imageUrl;
            resultImg.dataset.previewTitle = 'Generated Visualization';
            // Simple content-type hint based on extension
            if (imageUrl.endsWith('.svg')) resultImg.dataset.contentType = 'image/svg+xml';
            else if (imageUrl.endsWith('.pdf')) resultImg.dataset.contentType = 'application/pdf';
            else resultImg.dataset.contentType = 'image/png';

            resultImg.onload = () => {
                resultLoader.style.display = 'none';
                resultImg.classList.add('loaded');
                attachPreviewHandlers();
            };

            // Render table if present
            try {
                const container = document.getElementById('resultTableContainer');
                if (container && resultTable && Array.isArray(resultTable.rows)) {
                    container.innerHTML = renderResultTableHtml(resultTable);
                    // add click to open preview of table
                    container.style.cursor = 'zoom-in';
                    container.onclick = () => {
                        showPreviewHtml('Result Table', renderResultTableHtml(resultTable));
                    };
                }
            } catch (e) {
                console.warn('Failed to render result table:', e);
            }

            console.log(shouldPlot)

            // Decide initial view based on shouldPlot and available table
            try {
                const hasTable = resultTable && Array.isArray(resultTable.rows) && resultTable.rows.length > 0;
                const initialView = shouldPlot && imageUrl ? 'image' : hasTable ? 'table' : 'image';
                if (initialView === 'table') {
                    // if showing table, hide image loader immediately
                    try { resultLoader.style.display = 'none'; } catch (e) { }
                }
                setResultView(initialView);
            } catch (e) {
                console.warn('Failed to set initial result view:', e);
                setResultView('image');
            }

            // enable result header controls now that we have a result (image or table)
            try { setResultControlsEnabled(true); } catch (e) { }

            statusText.innerText = 'Data updated successfully.';
            outputBadge.className = 'badge bg-success bg-opacity-10 text-success status-badge';
            outputBadge.innerText = 'Updated';
        })
        .catch(err => {
            console.error('Question request failed:', err);
            let message = err.message || 'Unknown error';
            statusText.innerText = `Error: ${message}`;
            outputBadge.className = 'badge bg-danger status-badge';
            outputBadge.innerText = 'Error';
        });
}

function getRandomDiceIcon(exclude = []) {
    const diceIcons = ['fa-dice-one', 'fa-dice-two', 'fa-dice-three', 'fa-dice-four', 'fa-dice-five', 'fa-dice-six'];
    const possibleIcons = diceIcons.filter(icon => !exclude.includes(icon));
    if (possibleIcons.length === 0) return null;
    const r = Math.floor(Math.random() * possibleIcons.length);
    return possibleIcons[r];
}

// Initialize on Load
document.addEventListener('DOMContentLoaded', () => {
    initTopRow();
    const generateBtn = document.getElementById('generateBtn');
    // disable generate until there's text
    if (generateBtn) generateBtn.setAttribute('disabled', 'disabled');

    // Ctrl+Enter (and Cmd+Enter) to send request from textarea
    const textarea = document.getElementById('promptInput');
    if (textarea) {
        // Ensure the prompt input is empty on initial page load
        textarea.value = '';

        const updateGenerateState = () => {
            try {
                if (!generateBtn) return;
                if (textarea.value && textarea.value.trim().length > 0) generateBtn.removeAttribute('disabled');
                else generateBtn.setAttribute('disabled', 'disabled');
            } catch (e) { }
        };

        textarea.addEventListener('input', updateGenerateState);
        textarea.addEventListener('keydown', (e) => {
            // e.ctrlKey for Ctrl, e.metaKey for Command (Mac)
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                handleSend();
            }
        });
        // set initial state
        updateGenerateState();
    }

    // Random question button handler (populate textarea)
    const randomBtn = document.getElementById('randomQuestionBtn');
    if (randomBtn) {
        randomBtn.addEventListener('click', async () => {
            const icon = randomBtn.querySelector('i');
            // loaderInterval must be declared outside try so finally can clear it
            let loaderInterval = null;
            try {
                // provide immediate feedback: cycle dice icons every 100ms
                if (icon) {
                    // ensure no other dice classes remain
                    Array.from(icon.classList).forEach(c => { if (c.startsWith('fa-dice')) icon.classList.remove(c); });
                    // set initial random dice icon
                    icon.classList.add(getRandomDiceIcon());
                    // pick a random face every 100ms (remove previous dice-* classes first)
                    loaderInterval = setInterval(() => {
                        Array.from(icon.classList).forEach(c => { if (c.startsWith('fa-dice')) icon.classList.remove(c); });
                        icon.classList.add(getRandomDiceIcon());
                    }, 100);
                }
                randomBtn.disabled = true;

                // Use cached questions from `questionCache`, fetch batch if empty
                if (questionCache.length === 0) {
                    const resp = await fetch('/random-questions?count=10');
                    if (!resp.ok) throw new Error('Failed to fetch questions');
                    const res = await resp.json();
                    const list = res.questions || [];
                    if (Array.isArray(list) && list.length > 0) {
                        questionCache.push(...list.map(q => (typeof q === 'string') ? q : (q.text || '')));
                    } else {
                        throw new Error('No questions received');
                    }
                }

                // pop one question from cache and set input
                if (questionCache.length > 0) {
                    const q = questionCache.shift();
                    const ta = document.getElementById('promptInput');
                    if (ta) {
                        ta.value = q;
                        ta.focus();
                        // ensure generate button enabled for new value
                        const ev = new Event('input', { bubbles: true });
                        ta.dispatchEvent(ev);
                    }
                    const statusText = document.getElementById('statusText');
                    if (statusText) statusText.innerText = 'Random question loaded';
                }
            } catch (err) {
                console.error(err);
                alert('Could not fetch random questions: ' + (err.message || err));
            } finally {
                randomBtn.disabled = false;
                // stop loader and reset icon to a single die face (fa-dice-one)
                try { if (loaderInterval) clearInterval(loaderInterval); } catch (e) { }
                if (icon) {
                    Array.from(icon.classList).forEach(c => { if (c.startsWith('fa-dice')) icon.classList.remove(c); });
                    // reset to single die face
                    icon.classList.add('fa-dice-one');
                }
            }
        });
    }

    // Recenter preview button handler
    const recenterBtn = document.getElementById('recenterPreviewBtn');
    if (recenterBtn) {
        recenterBtn.addEventListener('click', () => {
            if (typeof window._previewPanZoomReset === 'function') {
                window._previewPanZoomReset();
            } else {
                console.warn('Recenter requested but preview pan/zoom not active');
            }
        });
    }

    // Show settings modal on app start (keeps behavior separate from save handler)
    // const settingsModalEl = document.getElementById('settingsModal');
    // if (settingsModalEl) {
    //     try {
    //         const settingsModal = new bootstrap.Modal(settingsModalEl);
    //         settingsModal.show();
    //         const googleKeyInput = document.getElementById('googleApiKey');
    //         if (googleKeyInput) setTimeout(() => googleKeyInput.focus(), 200);
    //     } catch (err) {
    //         console.warn('Could not show settings modal on start:', err);
    //     }
    // }
});

// --- Result view toggle functionality ---
// state: 'image' or 'table'
window.resultView = 'image';

// Enable/disable result-related header controls (download current, download all, toggle view)
function setResultControlsEnabled(enabled) {
    try {
        const ids = ['downloadResultCurrentBtn', 'downloadResultAllBtn', 'toggleViewBtn'];
        ids.forEach(id => {
            const el = document.getElementById(id);
            if (!el) return;
            if (enabled) el.removeAttribute('disabled'); else el.setAttribute('disabled', 'disabled');
        });
    } catch (e) { console.warn('Failed to set result controls state', e); }
}

function setResultView(view) {
    const img = document.getElementById('resultImage');
    const tableCont = document.getElementById('resultTableContainer');
    const icon = document.getElementById('toggleViewIcon');
    if (!img || !tableCont || !icon) return;
    if (view === 'table') {
        img.style.display = 'none';
        tableCont.style.display = 'block';
        icon.className = 'fas fa-image';
        window.resultView = 'table';
    } else {
        img.style.display = '';
        tableCont.style.display = 'none';
        icon.className = 'fas fa-table';
        window.resultView = 'image';
    }
}

function toggleResultView() {
    setResultView(window.resultView === 'image' ? 'table' : 'image');
}

// Render a DataFrame-shaped object (columns + rows) into HTML table matching statistics style
function renderResultTableHtml(dfObj) {
    if (!dfObj || !Array.isArray(dfObj.rows) || !Array.isArray(dfObj.columns)) return '<div>No data</div>';
    const cols = dfObj.columns;
    const rows = dfObj.rows;
    const headerHtml = `<tr>${cols.map(c => `<th style="text-align: center; border: 1px solid #dee2e6; padding: 8px;">${String(c).toUpperCase()}</th>`).join('')}</tr>`;
    const bodyHtml = rows.map(r => `<tr>${cols.map(c => `<td style="border: 1px solid #dee2e6; padding: 8px;">${escapeHtml(String(r[c] === undefined || r[c] === null ? '' : r[c]))}</td>`).join('')}</tr>`).join('');
    return `
        <div style="max-height:100%; overflow:auto; width:100%; border:1px solid #dee2e6; border-radius:5px;">
            <table class="table table-striped" style="border-collapse: collapse; width: 100%; border: 1px solid #dee2e6;">
                <thead style="z-index:2; position: sticky; top: 0; background-color: #f8f9fa; border-bottom: 2px solid #dee2e6;">${headerHtml}</thead>
                <tbody>${bodyHtml}</tbody>
            </table>
        </div>
    `;
}

function escapeHtml(s) {
    return s.replace(/[&<>'"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&apos', '"': '&quot' }[c]));
}

// attach toggle handler after DOM ready
document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('toggleViewBtn');
    if (btn) {
        btn.addEventListener('click', () => {
            // Only toggle if we have data
            const df = window.latestDf;
            if (!df || !Array.isArray(df.rows) || df.rows.length === 0) return;
            toggleResultView();
        });
    }
    // ensure initial state
    setResultView('image');
});

// --- Save Settings Handler: refresh top row, clear input, reset bottom image ---
(function attachSaveSettingsHandler() {
    const saveBtn = document.getElementById('saveSettingsBtn');
    if (!saveBtn) return;

    saveBtn.addEventListener('click', async () => {
        const dbType = document.getElementById('dbSelect').value;
        const sqlitePath = document.getElementById('sqlitePath').value;
        const pgHost = document.getElementById('pgHost').value;
        const pgLogin = document.getElementById('pgLogin').value;
        const pgPassword = document.getElementById('pgPassword').value;

        const payload = {
            db_path: dbType === 'SQLITE' ? sqlitePath || 'data/chinook.db' : pgHost,
            db_type: dbType === 'SQLITE' ? 'sqlite' : 'postgres',
        };

        try {
            const resp = await fetch('/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            if (!resp.ok) throw new Error('Settings update failed');
            // Refresh top row to reflect new DB
            initTopRow();

            // Clear input textarea
            const textarea = document.getElementById('promptInput');
            if (textarea) textarea.value = '';

            // Reset result image and UI
            const resultImg = document.getElementById('resultImage');
            const statusText = document.getElementById('statusText');
            const outputBadge = document.getElementById('outputBadge');
            if (resultImg) {
                resultImg.classList.remove('loaded');
                resultImg.src = 'data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=';
                resultImg.alt = 'No image';
            }
            if (statusText) statusText.innerText = 'Ready to send';
            if (outputBadge) {
                outputBadge.className = 'badge bg-secondary bg-opacity-10 text-secondary status-badge';
                outputBadge.innerText = 'Waiting';
            }
            // no result available after settings change
            try { setResultControlsEnabled(false); } catch (e) { }
        } catch (err) {
            console.error('Failed to save settings', err);
            alert('Failed to save settings: ' + err.message);
        }
    });
})();

// --- Download helpers and handlers ---
function downloadBlobObject(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'download.bin';
    document.body.appendChild(a);
    a.click();
    setTimeout(() => {
        try { document.body.removeChild(a); } catch (e) { }
        try { URL.revokeObjectURL(url); } catch (e) { }
    }, 150);
}

async function downloadBlobFromUrl(url, filename) {
    try {
        const resp = await fetch(url);
        if (!resp.ok) throw new Error('Failed to fetch file');
        const blob = await resp.blob();
        downloadBlobObject(blob, filename);
    } catch (err) {
        console.error('Download failed', err);
        alert('Download failed: ' + (err.message || err));
    }
}

function arrayToCsv(rows, columns) {
    if (!Array.isArray(rows) || rows.length === 0) return '';
    const cols = columns && Array.isArray(columns) && columns.length ? columns : Object.keys(rows[0]);
    const escape = (v) => {
        if (v === null || v === undefined) return '';
        const s = String(v);
        if (s.includes(',') || s.includes('"') || s.includes('\n')) return '"' + s.replace(/"/g, '""') + '"';
        return s;
    };
    const header = cols.join(',');
    const lines = rows.map(r => cols.map(c => escape(r[c])).join(','));
    return [header, ...lines].join('\n');
}

async function downloadSchema() {
    // Prefer stored blob from initTopRow
    try {
        if (window.schemaBlob) {
            const ext = (window.schemaContentType && window.schemaContentType.includes('svg')) ? 'svg' : 'png';
            downloadBlobObject(window.schemaBlob, `schema.${ext}`);
            return;
        }
        // fallback: fetch from endpoint
        await downloadBlobFromUrl('/schema/image', 'schema.png');
    } catch (err) {
        console.error(err);
        alert('Could not download schema: ' + (err.message || err));
    }
}

function downloadDescribeCsv() {
    try {
        const rows = window.describeData || [];
        const cols = window.describeColumns || (rows.length ? Object.keys(rows[0]) : []);
        const csv = arrayToCsv(rows, cols);
        if (!csv) { alert('No describe data available'); return; }
        const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
        downloadBlobObject(blob, 'db_description.csv');
    } catch (err) {
        console.error('Failed to download describe CSV', err);
        alert('Failed to download describe CSV: ' + (err.message || err));
    }
}

async function downloadResultCurrent() {
    try {
        if (window.resultView === 'image') {
            const img = document.getElementById('resultImage');
            if (!img || !img.src) { alert('No image available'); return; }
            // try to fetch image and download
            const url = img.src;
            // derive extension
            const ext = (img.dataset.contentType && img.dataset.contentType.includes('svg')) ? 'svg' : url.split('.').pop().split('?')[0] || 'png';
            await downloadBlobFromUrl(url, `result.${ext}`);
        } else {
            // table view
            const df = window.latestDf;
            if (!df || !Array.isArray(df.rows)) { alert('No table data available'); return; }
            const csv = arrayToCsv(df.rows, df.columns);
            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            downloadBlobObject(blob, 'result_table.csv');
        }
    } catch (err) {
        console.error('Failed to download current result', err);
        alert('Failed to download: ' + (err.message || err));
    }
}

async function downloadResultAll() {
    try {
        // trigger image download if present
        const img = document.getElementById('resultImage');
        if (img && img.src) {
            const url = img.src;
            const ext = (img.dataset.contentType && img.dataset.contentType.includes('svg')) ? 'svg' : url.split('.').pop().split('?')[0] || 'png';
            // don't await so both downloads can start quickly, but await to catch errors separately
            downloadBlobFromUrl(url, `result_image.${ext}`).catch(e => console.warn('Image download failed', e));
        }

        // trigger table download if present
        const df = window.latestDf;
        if (df && Array.isArray(df.rows) && df.rows.length > 0) {
            const csv = arrayToCsv(df.rows, df.columns);
            const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
            downloadBlobObject(blob, 'result_table.csv');
        }
        if ((!img || !img.src) && (!df || !Array.isArray(df.rows) || df.rows.length === 0)) {
            alert('No image or table data available to download');
        }
    } catch (err) {
        console.error('Failed to download all results', err);
        alert('Failed to download all: ' + (err.message || err));
    }
}

// attach download buttons after DOM ready
document.addEventListener('DOMContentLoaded', () => {
    const sbtn = document.getElementById('downloadSchemaBtn');
    if (sbtn) sbtn.addEventListener('click', downloadSchema);

    const dbtn = document.getElementById('downloadDescribeCsvBtn');
    if (dbtn) dbtn.addEventListener('click', downloadDescribeCsv);

    const rcur = document.getElementById('downloadResultCurrentBtn');
    if (rcur) rcur.addEventListener('click', downloadResultCurrent);

    const rall = document.getElementById('downloadResultAllBtn');
    if (rall) rall.addEventListener('click', downloadResultAll);
    // ensure result controls are disabled until a result is available
    try { setResultControlsEnabled(false); } catch (e) { }
});
