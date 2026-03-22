/**
 * JobMonitor — Dashboard Frontend Logic
 */

const API = '';

// ===== State =====
let activeAgentFilter = '';
let activeDateFilter = '2days';
let currentRole = 'software engineer';
let currentOffset = 0;
const LIMIT = 50;

// Agent label mapping
const AGENT_LABELS = {
    agent1: 'GitHub',
    agent2: 'Adzuna',
    agent3: 'Greenhouse',
};

// ===== Tab Navigation =====
function switchTab(tabName, btn) {
    // Hide all pages
    document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
    // Show target page
    document.getElementById(`page-${tabName}`).classList.remove('hidden');
    // Update nav tab active state
    document.querySelectorAll('.nav-tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
}

// ===== Toast Notifications =====
function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ===== Sources =====
async function loadSources() {
    try {
        const resp = await fetch(`${API}/api/sources`);
        const data = await resp.json();
        renderSources(data.sources || []);
    } catch (e) {
        console.error('Failed to load sources:', e);
    }
}

function renderSources(sources) {
    const count = document.getElementById('sourceCount');
    count.textContent = sources.length;

    // Separate sources by type
    const githubSources = sources.filter(s => s.type === 'github');
    const otherSources = sources.filter(s => s.type !== 'github');

    // Render GitHub sources
    const githubList = document.getElementById('githubSourceList');
    const githubCount = document.getElementById('githubSourceCount');
    if (githubCount) githubCount.textContent = githubSources.length;

    if (githubList) {
        if (githubSources.length === 0) {
            githubList.innerHTML = '<div class="empty-hint">No GitHub sources added yet</div>';
        } else {
            githubList.innerHTML = githubSources.map(s => renderSourceItem(s)).join('');
        }
    }

    // Update agent stats
    updateAgentStats(sources);
}

function renderSourceItem(s) {
    const lastScan = s.last_scanned
        ? new Date(s.last_scanned).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
        : 'Never';
    const isEnabled = s.enabled !== false;
    const jobsFound = s.jobs_found_last_scan || 0;

    return `
        <div class="source-item-extended" data-id="${s.id}">
            <div class="source-info">
                <span class="source-name">${s.name}</span>
                <span class="source-meta">
                    <span>Last scan: ${lastScan}</span>
                    <span>·</span>
                    <span>Jobs: ${jobsFound}</span>
                    ${s.last_error ? `<span style="color: var(--red-500)">· Error</span>` : ''}
                </span>
            </div>
            <div class="source-toggle-container">
                <span class="source-status ${isEnabled ? 'enabled' : 'disabled'}">${isEnabled ? 'Active' : 'Disabled'}</span>
                <div class="toggle-switch ${isEnabled ? 'active' : ''}" onclick="toggleSourceEnabled(${s.id}, ${!isEnabled})"></div>
                <button class="btn btn-danger" onclick="removeSource(${s.id})">Remove</button>
            </div>
        </div>
    `;
}

function updateAgentStats(sources) {
    // GitHub stats
    const githubSources = sources.filter(s => s.type === 'github');
    const githubLastScan = githubSources.length > 0
        ? githubSources.reduce((latest, s) => {
            if (!s.last_scanned) return latest;
            return !latest || new Date(s.last_scanned) > new Date(latest) ? s.last_scanned : latest;
        }, null)
        : null;

    const githubLastScanEl = document.getElementById('githubLastScan');
    if (githubLastScanEl) {
        githubLastScanEl.textContent = githubLastScan
            ? new Date(githubLastScan).toLocaleString('en-US', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })
            : 'Never';
    }
}

async function addSource() {
    const urlInput = document.getElementById('sourceUrl');
    const typeSelect = document.getElementById('sourceType');
    const url = urlInput.value.trim();

    if (!url) {
        showToast('Please enter a URL', 'error');
        return;
    }

    let type = typeSelect.value;
    if (url.includes('github.com')) {
        type = 'github';
        typeSelect.value = 'github';
    } else if (url.includes('jobs.lever.co') || url.includes('lever.co')) {
        type = 'lever';
        typeSelect.value = 'lever';
    } else if (url.includes('boards.greenhouse.io') || url.includes('greenhouse.io')) {
        type = 'greenhouse';
        typeSelect.value = 'greenhouse';
    }

    try {
        const resp = await fetch(`${API}/api/sources`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, type }),
        });

        if (resp.status === 409) {
            showToast('This source already exists', 'error');
            return;
        }

        if (!resp.ok) throw new Error('Failed to add source');

        urlInput.value = '';
        showToast('Source added!', 'success');
        await loadSources();
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function removeSource(id) {
    if (!confirm('Are you sure you want to remove this source?')) return;
    try {
        await fetch(`${API}/api/sources/${id}`, { method: 'DELETE' });
        showToast('Source removed', 'info');
        await loadSources();
    } catch (e) {
        showToast('Failed to remove source', 'error');
    }
}

async function toggleSourceEnabled(id, enabled) {
    try {
        await fetch(`${API}/api/sources/${id}/toggle`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled }),
        });
        showToast(`Source ${enabled ? 'enabled' : 'disabled'}`, 'success');
        await loadSources();
    } catch (e) {
        showToast('Failed to toggle source', 'error');
    }
}

async function addGithubSource() {
    const urlInput = document.getElementById('githubSourceUrl');
    const url = urlInput.value.trim();

    if (!url) {
        showToast('Please enter a GitHub URL', 'error');
        return;
    }

    if (!url.includes('github.com')) {
        showToast('Please enter a valid GitHub URL', 'error');
        return;
    }

    try {
        const resp = await fetch(`${API}/api/sources`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, type: 'github' }),
        });

        if (resp.status === 409) {
            showToast('This source already exists', 'error');
            return;
        }

        if (!resp.ok) throw new Error('Failed to add source');

        urlInput.value = '';
        showToast('GitHub source added!', 'success');
        await loadSources();
    } catch (e) {
        showToast(`Error: ${e.message}`, 'error');
    }
}

async function hideJob(jobId) {
    try {
        await fetch(`${API}/api/jobs/${jobId}/hide`, { method: 'PUT' });

        // Remove job card from DOM with animation
        const jobCard = document.querySelector(`[data-job-id="${jobId}"]`);
        if (jobCard) {
            jobCard.style.opacity = '0';
            jobCard.style.transform = 'translateX(-20px)';
            setTimeout(() => jobCard.remove(), 200);
        }

        showToast('Job hidden. It will not appear again even if re-fetched.', 'info');
    } catch (e) {
        showToast('Failed to hide job', 'error');
    }
}

// ===== Date Helper =====
function getDateFrom(filter) {
    if (!filter) return '';
    const now = new Date();
    let d;
    switch (filter) {
        case 'today':
            d = new Date(now.getFullYear(), now.getMonth(), now.getDate());
            break;
        case '2days':
            d = new Date(now.getTime() - 2 * 24 * 60 * 60 * 1000);
            break;
        case 'week':
            d = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
            break;
        case 'month':
            d = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);
            break;
        default:
            return '';
    }
    return d.toISOString().slice(0, 10);
}

// ===== Job Updates =====
async function loadUpdates(append = false) {
    try {
        if (!append) currentOffset = 0;

        let url = `${API}/api/updates?limit=${LIMIT}&offset=${currentOffset}`;
        if (activeAgentFilter) {
            url += `&agent_id=${encodeURIComponent(activeAgentFilter)}`;
        }
        const dateFrom = getDateFrom(activeDateFilter);
        if (dateFrom) {
            url += `&date_from=${encodeURIComponent(dateFrom)}`;
        }

        const resp = await fetch(url);
        const data = await resp.json();
        const updates = data.updates || [];

        renderUpdates(updates, append);

        const loadMoreBtn = document.getElementById('loadMoreContainer');
        loadMoreBtn.style.display = updates.length < LIMIT ? 'none' : 'block';
    } catch (e) {
        console.error('Failed to load updates:', e);
        showToast('Failed to load updates', 'error');
    }
}

async function loadMoreUpdates() {
    currentOffset += LIMIT;
    const btn = document.querySelector('#loadMoreContainer button');
    const originalText = btn.innerText;
    btn.innerText = 'Loading...';
    btn.disabled = true;
    await loadUpdates(true);
    btn.innerText = originalText;
    btn.disabled = false;
}

function renderUpdates(updates, append) {
    const feed = document.getElementById('updatesFeed');
    const countEl = document.getElementById('updateCount');

    if (!append && updates.length === 0) {
        countEl.textContent = '0 jobs';
        feed.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">
                    <svg width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z"/></svg>
                </div>
                <h3>No jobs yet</h3>
                <p>Go to <strong>Settings</strong> to add sources, then run a scan.</p>
            </div>
        `;
        document.getElementById('loadMoreContainer').style.display = 'none';
        return;
    }

    if (!append) {
        countEl.textContent = `${updates.length}${updates.length === LIMIT ? '+' : ''} jobs`;
    }

    const html = updates.map(u => {
        const postedDate = u.date_posted
            ? new Date(u.date_posted + 'T00:00:00').toLocaleDateString()
            : '';

        const agentId = u.agent_id || '';
        const agentLabel = AGENT_LABELS[agentId] || 'Unknown';
        const agentClass = agentId === 'agent1' ? 'github'
            : agentId === 'agent2' ? 'adzuna'
                : agentId === 'agent3' ? 'greenhouse' : '';

        // Get company initial for logo
        const companyInitial = (u.company || u.title || '?').charAt(0).toUpperCase();

        return `
            <div class="job-card" data-job-id="${u.id}">
                <div class="job-card-header">
                    <div class="job-card-main">
                        <div class="job-logo">${companyInitial}</div>
                        <div class="job-info">
                            <div class="job-title">
                                <a href="${u.url || '#'}" target="_blank" rel="noopener">${u.title}</a>
                            </div>
                            ${u.company ? `<div class="job-company"><span class="job-company-highlight">${u.company}</span></div>` : ''}
                            <div class="job-meta">
                                ${u.location ? `<span class="job-tag">${u.location}</span>` : ''}
                                ${postedDate ? `<span class="job-tag">${postedDate}</span>` : ''}
                            </div>
                        </div>
                    </div>
                </div>
                ${u.description ? `<div class="job-desc">${u.description}</div>` : ''}
                <div class="job-footer">
                    <div class="job-footer-left">
                        <span class="source-label ${agentClass}">${agentLabel}</span>
                        ${u.source_name ? `<span>·</span><span>${u.source_name}</span>` : ''}
                    </div>
                    <div class="job-footer-right">
                        <div class="job-actions">
                            <button class="btn-icon hidden-btn" onclick="hideJob(${u.id})" title="Hide this job">
                                <svg fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24">
                                    <path d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21"/>
                                </svg>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
    }).join('');

    if (append) {
        feed.insertAdjacentHTML('beforeend', html);
    } else {
        feed.innerHTML = html;
    }
}

// ===== Scan =====
async function triggerScan() {
    const btn = document.getElementById('scanBtn');
    const dot = document.querySelector('.status-dot');
    const statusText = document.getElementById('statusText');

    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Scanning...';
    dot.classList.add('scanning');
    statusText.textContent = 'Scanning...';

    try {
        const resp = await fetch(`${API}/api/scan`, { method: 'POST' });
        if (resp.status === 409) {
            showToast('A scan is already in progress', 'info');
            return;
        }
        const data = await resp.json();
        const results = data.results || [];
        const totalNew = results.reduce((sum, r) => sum + (r.new_jobs || 0), 0);
        const totalFound = results.reduce((sum, r) => sum + (r.jobs_found || 0), 0);

        showToast(`Scan complete! Found ${totalFound} jobs (${totalNew} new)`, 'success');
        await loadUpdates();
        await loadSources();
        await loadStatus();
    } catch (e) {
        showToast(`Scan error: ${e.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Scan GitHub Sources';
        dot.classList.remove('scanning');
        statusText.textContent = 'Idle';
    }
}

// ===== Status =====
async function loadStatus() {
    try {
        const resp = await fetch(`${API}/api/status`);
        const data = await resp.json();

        const lastScanEl = document.getElementById('lastScan');
        const intervalEl = document.getElementById('scanInterval');

        lastScanEl.textContent = data.last_scan_at
            ? `Last scan: ${new Date(data.last_scan_at).toLocaleString()}`
            : 'Last scan: Never';
        intervalEl.textContent = `Interval: ${data.interval_minutes} min`;

        if (data.is_running) {
            document.querySelector('.status-dot').classList.add('scanning');
            document.getElementById('statusText').textContent = 'Scanning...';
        }
    } catch (e) {
        console.error('Failed to load status:', e);
    }
}

// ===== Chat =====
async function sendChat() {
    const input = document.getElementById('chatInput');
    const messages = document.getElementById('chatMessages');
    const message = input.value.trim();

    if (!message) return;

    const userMsg = document.createElement('div');
    userMsg.className = 'chat-bubble user';
    userMsg.textContent = message;
    messages.appendChild(userMsg);
    input.value = '';
    messages.scrollTop = messages.scrollHeight;

    const loadingMsg = document.createElement('div');
    loadingMsg.className = 'chat-bubble assistant';
    loadingMsg.innerHTML = '<span class="spinner"></span> Thinking...';
    messages.appendChild(loadingMsg);
    messages.scrollTop = messages.scrollHeight;

    try {
        const resp = await fetch(`${API}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message }),
        });
        const data = await resp.json();
        loadingMsg.textContent = data.response;
    } catch (e) {
        loadingMsg.textContent = 'Sorry, I encountered an error. Please try again.';
    }
    messages.scrollTop = messages.scrollHeight;
}

// ===== ATS Scan (Greenhouse) =====
async function triggerAtsScan() {
    const btn = document.getElementById('atsScanBtn');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Scanning...';
    showToast('Starting Greenhouse scan across companies...', 'info');

    try {
        const resp = await fetch(`${API}/api/ats-scan`, { method: 'POST' });
        const data = await resp.json();

        if (data.status === 'error') {
            showToast(`Greenhouse Scan: ${data.error}`, 'error');
        } else {
            showToast(
                `Greenhouse scan complete! Scanned ${data.scanned} companies, found ${data.total_jobs} jobs (${data.new_jobs} new)`,
                'success'
            );
            loadUpdates();
        }
    } catch (e) {
        showToast(`Greenhouse scan error: ${e.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Scan Greenhouse';
    }
}

// ===== Search (Adzuna) =====
async function searchJobs() {
    const queryInput = document.getElementById('searchQuery');
    const locationInput = document.getElementById('searchLocation');
    const query = queryInput.value.trim();

    if (!query) {
        showToast('Please enter a search query', 'error');
        return;
    }

    const btn = document.getElementById('searchBtn');
    const hint = document.getElementById('searchHint');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner"></span> Searching...';
    hint.textContent = 'Querying job search APIs...';

    try {
        const body = {
            query,
            location: locationInput.value.trim() || null,
            date_posted: document.getElementById('datePosted').value,
            remote_only: document.getElementById('remoteOnly').checked,
            employment_type: document.getElementById('employmentType').value || null,
            country: 'us',
        };

        const resp = await fetch(`${API}/api/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        const data = await resp.json();

        if (data.errors && data.errors.length > 0) {
            data.errors.forEach(err => showToast(err, 'error'));
        }

        const jsearchCount = data.sources?.jsearch || 0;
        const adzunaCount = data.sources?.adzuna || 0;
        showToast(
            `Found ${data.total} jobs (JSearch: ${jsearchCount}, Adzuna: ${adzunaCount}, ${data.new_jobs} new)`,
            data.status === 'success' ? 'success' : 'info'
        );

        renderSearchResults(data.jobs || [], query);
    } catch (e) {
        showToast(`Search error: ${e.message}`, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = 'Search';
        hint.textContent = 'Searches across LinkedIn, Indeed, Glassdoor & more';
    }
}

function renderSearchResults(jobs, query) {
    // Switch to Jobs tab to show results
    const jobsTab = document.querySelector('.nav-tab[data-tab="jobs"]');
    switchTab('jobs', jobsTab);

    const feed = document.getElementById('updatesFeed');
    const countEl = document.getElementById('updateCount');
    countEl.textContent = `${jobs.length} result${jobs.length !== 1 ? 's' : ''}`;

    if (jobs.length === 0) {
        feed.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">
                    <svg width="48" height="48" fill="none" stroke="currentColor" stroke-width="1.5" viewBox="0 0 24 24"><path d="M21 21l-4.35-4.35M11 19a8 8 0 100-16 8 8 0 000 16z"/></svg>
                </div>
                <h3>No results for "${query}"</h3>
                <p>Try different keywords or broaden your search filters.</p>
            </div>
        `;
        return;
    }

    feed.innerHTML = jobs.map(job => {
        const linkHtml = job.url
            ? `<a href="${job.url}" target="_blank" rel="noopener">${job.title}</a>`
            : job.title;

        const sourceLabel = job.source_api === 'jsearch' ? 'JSearch' : 'Adzuna';
        const sourceClass = 'adzuna';

        // Get company initial for logo
        const companyInitial = (job.company || job.title || '?').charAt(0).toUpperCase();

        return `
            <div class="job-card">
                <div class="job-card-header">
                    <div class="job-card-main">
                        <div class="job-logo">${companyInitial}</div>
                        <div class="job-info">
                            <div class="job-title">${linkHtml}</div>
                            ${job.company ? `<div class="job-company"><span class="job-company-highlight">${job.company}</span></div>` : ''}
                            <div class="job-meta">
                                ${job.location ? `<span class="job-tag">${job.location}</span>` : ''}
                                ${job.salary ? `<span class="job-tag salary">${job.salary}</span>` : ''}
                                ${job.is_remote ? '<span class="job-tag remote">Remote</span>' : ''}
                                ${job.employment_type ? `<span class="job-tag">${job.employment_type}</span>` : ''}
                            </div>
                        </div>
                    </div>
                </div>
                ${job.description ? `<div class="job-desc">${job.description}</div>` : ''}
                <div class="job-footer">
                    <div class="job-footer-left">
                        <span class="source-label ${sourceClass}">${sourceLabel}</span>
                        ${job.source_site ? `<span>·</span><span>via ${job.source_site}</span>` : ''}
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// ===== Agent Filter Tabs =====
function setAgentFilter(btn, agentId) {
    activeAgentFilter = agentId;
    document.querySelectorAll('.source-tab').forEach(t => t.classList.remove('active'));
    btn.classList.add('active');
    loadUpdates();
}

function onFilterChange() {
    activeDateFilter = document.getElementById('dateFilter').value;
    loadUpdates();
}

// ===== Settings =====
async function loadSettings() {
    try {
        const resp = await fetch(`${API}/api/settings`);
        const data = await resp.json();
        currentRole = data.search_role || 'software engineer';
        document.getElementById('searchRoleSetting').value = currentRole;
        const searchInput = document.getElementById('searchQuery');
        if (searchInput && !searchInput.value.trim()) {
            searchInput.value = currentRole;
        }
    } catch (e) {
        console.error('Failed to load settings:', e);
    }
}

async function saveSettings() {
    const roleInput = document.getElementById('searchRoleSetting');
    const role = roleInput.value.trim();
    if (!role) {
        showToast('Please enter a role', 'error');
        return;
    }
    try {
        const resp = await fetch(`${API}/api/settings`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ search_role: role }),
        });
        const data = await resp.json();
        currentRole = data.settings.search_role;
        const searchInput = document.getElementById('searchQuery');
        if (searchInput) searchInput.value = currentRole;
        showToast('Settings saved!', 'success');
        document.getElementById('settingsHint').textContent = `Current: "${currentRole}"`;
    } catch (e) {
        showToast('Failed to save settings', 'error');
    }
}

// ===== Resume Agent =====
async function handleResumeUpload() {
    const fileInput = document.getElementById('resumeFileInput');
    const file = fileInput.files[0];
    const hint = document.getElementById('uploadHint');

    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.pdf')) {
        showToast('Only PDF files are supported', 'error');
        return;
    }

    hint.textContent = 'Uploading and parsing resume...';
    hint.style.color = '#666';

    try {
        const formData = new FormData();
        formData.append('file', file);

        const resp = await fetch(`${API}/api/resume/upload`, {
            method: 'POST',
            body: formData,
        });

        if (!resp.ok) {
            const error = await resp.json();
            throw new Error(error.detail || 'Upload failed');
        }

        const data = await resp.json();
        showToast(data.message, 'success');
        hint.textContent = 'Resume parsed successfully!';
        hint.style.color = 'green';

        // Display the parsed resume
        renderResume(data.data);

        // Clear file input
        fileInput.value = '';

        // Show resume data section
        document.getElementById('resumeDataSection').style.display = 'block';
    } catch (e) {
        showToast(`Upload error: ${e.message}`, 'error');
        hint.textContent = `Error: ${e.message}`;
        hint.style.color = 'red';
    }
}

async function loadResume() {
    try {
        const resp = await fetch(`${API}/api/resume`);
        if (resp.status === 404) {
            // No resume uploaded yet
            document.getElementById('resumeDataSection').style.display = 'none';
            return;
        }

        const data = await resp.json();
        renderResume(data.data);
        document.getElementById('resumeDataSection').style.display = 'block';
    } catch (e) {
        console.error('Failed to load resume:', e);
        document.getElementById('resumeDataSection').style.display = 'none';
    }
}

function renderResume(data) {
    // Personal Info
    const personalInfo = data.personal_info || {};
    document.getElementById('personalInfo').innerHTML = `
        <h4 class="resume-section-title">Personal Information</h4>
        <div class="resume-field-grid">
            ${personalInfo.name ? `<div class="resume-field"><strong>Name:</strong> ${personalInfo.name}</div>` : ''}
            ${personalInfo.email ? `<div class="resume-field"><strong>Email:</strong> <a href="mailto:${personalInfo.email}">${personalInfo.email}</a></div>` : ''}
            ${personalInfo.phone ? `<div class="resume-field"><strong>Phone:</strong> ${personalInfo.phone}</div>` : ''}
            ${personalInfo.location ? `<div class="resume-field"><strong>Location:</strong> ${personalInfo.location}</div>` : ''}
            ${personalInfo.linkedin ? `<div class="resume-field"><strong>LinkedIn:</strong> <a href="${personalInfo.linkedin}" target="_blank">${personalInfo.linkedin}</a></div>` : ''}
            ${personalInfo.github ? `<div class="resume-field"><strong>GitHub:</strong> <a href="${personalInfo.github}" target="_blank">${personalInfo.github}</a></div>` : ''}
            ${personalInfo.website ? `<div class="resume-field"><strong>Website:</strong> <a href="${personalInfo.website}" target="_blank">${personalInfo.website}</a></div>` : ''}
        </div>
    `;

    // Education
    const education = data.education || [];
    if (education.length > 0) {
        document.getElementById('education').innerHTML = `
            <h4 class="resume-section-title">Education</h4>
            ${education.map(edu => `
                <div class="resume-item">
                    <div class="resume-item-header">
                        <strong>${edu.degree}${edu.field ? ` in ${edu.field}` : ''}</strong>
                        <span>${edu.start_date || ''} - ${edu.end_date || ''}</span>
                    </div>
                    <div>${edu.school}${edu.location ? `, ${edu.location}` : ''}</div>
                    ${edu.gpa ? `<div>GPA: ${edu.gpa}</div>` : ''}
                    ${edu.coursework && edu.coursework.length > 0 ? `<div><em>Coursework:</em> ${edu.coursework.join(', ')}</div>` : ''}
                    ${edu.achievements && edu.achievements.length > 0 ? `<div><em>Achievements:</em> ${edu.achievements.join(', ')}</div>` : ''}
                </div>
            `).join('')}
        `;
    } else {
        document.getElementById('education').innerHTML = '';
    }

    // Experience
    const experience = data.experience || [];
    if (experience.length > 0) {
        document.getElementById('experience').innerHTML = `
            <h4 class="resume-section-title">Experience</h4>
            ${experience.map(exp => `
                <div class="resume-item">
                    <div class="resume-item-header">
                        <strong>${exp.title}</strong>
                        <span>${exp.start_date || ''} - ${exp.end_date || ''}</span>
                    </div>
                    <div>${exp.company}${exp.location ? `, ${exp.location}` : ''}</div>
                    ${exp.highlights && exp.highlights.length > 0 ? `
                        <ul class="resume-list">
                            ${exp.highlights.map(h => `<li>${h}</li>`).join('')}
                        </ul>
                    ` : ''}
                </div>
            `).join('')}
        `;
    } else {
        document.getElementById('experience').innerHTML = '';
    }

    // Skills
    const skills = data.skills || {};
    const hasSkills = Object.values(skills).some(arr => arr && arr.length > 0);
    if (hasSkills) {
        document.getElementById('skills').innerHTML = `
            <h4 class="resume-section-title">Skills</h4>
            <div class="resume-skills">
                ${skills.languages && skills.languages.length > 0 ? `<div><strong>Languages:</strong> ${skills.languages.join(', ')}</div>` : ''}
                ${skills.frameworks && skills.frameworks.length > 0 ? `<div><strong>Frameworks:</strong> ${skills.frameworks.join(', ')}</div>` : ''}
                ${skills.tools && skills.tools.length > 0 ? `<div><strong>Tools:</strong> ${skills.tools.join(', ')}</div>` : ''}
                ${skills.other && skills.other.length > 0 ? `<div><strong>Other:</strong> ${skills.other.join(', ')}</div>` : ''}
            </div>
        `;
    } else {
        document.getElementById('skills').innerHTML = '';
    }

    // Projects
    const projects = data.projects || [];
    if (projects.length > 0) {
        document.getElementById('projects').innerHTML = `
            <h4 class="resume-section-title">Projects</h4>
            ${projects.map(proj => `
                <div class="resume-item">
                    <div class="resume-item-header">
                        <strong>${proj.name}</strong>
                        ${proj.url ? `<a href="${proj.url}" target="_blank">View Project →</a>` : ''}
                    </div>
                    ${proj.highlights && proj.highlights.length > 0 ? `
                        <ul class="resume-highlights">
                            ${proj.highlights.map(h => `<li>${h}</li>`).join('')}
                        </ul>
                    ` : ''}
                    ${proj.technologies && proj.technologies.length > 0 ? `<div class="resume-tech-tags">${proj.technologies.map(t => `<span class="tech-tag">${t}</span>`).join('')}</div>` : ''}
                </div>
            `).join('')}
        `;
    } else {
        document.getElementById('projects').innerHTML = '';
    }

    // Certifications
    const certifications = data.certifications || [];
    if (certifications.length > 0) {
        document.getElementById('certifications').innerHTML = `
            <h4 class="resume-section-title">Certifications</h4>
            ${certifications.map(cert => `
                <div class="resume-item">
                    <div class="resume-item-header">
                        <strong>${cert.name}</strong>
                        ${cert.date ? `<span>${cert.date}</span>` : ''}
                    </div>
                    ${cert.issuer ? `<div>${cert.issuer}</div>` : ''}
                </div>
            `).join('')}
        `;
    } else {
        document.getElementById('certifications').innerHTML = '';
    }
}

async function deleteResume() {
    if (!confirm('Are you sure you want to delete your resume? This cannot be undone.')) {
        return;
    }

    try {
        const resp = await fetch(`${API}/api/resume`, {
            method: 'DELETE',
        });

        if (!resp.ok) {
            throw new Error('Failed to delete resume');
        }

        showToast('Resume deleted successfully', 'success');
        document.getElementById('resumeDataSection').style.display = 'none';
        document.getElementById('uploadHint').textContent = '';
    } catch (e) {
        showToast(`Delete error: ${e.message}`, 'error');
    }
}

// ===== Auto-refresh =====
let refreshInterval;

function startAutoRefresh() {
    refreshInterval = setInterval(() => {
        loadUpdates();
        loadStatus();
    }, 30000);
}

// ===== Init =====
async function init() {
    document.getElementById('dateFilter').value = activeDateFilter;
    await Promise.all([loadSettings(), loadSources(), loadUpdates(), loadStatus(), loadResume()]);
    startAutoRefresh();
}

document.addEventListener('DOMContentLoaded', init);
