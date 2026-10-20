// State
let currentConfigs = [];
let activeConfig = null;
let activeJobId = null;
let eventSource = null;

// Initialize on page load
document.addEventListener("DOMContentLoaded", () => {
    loadConfigurations();
    checkBrowserStatus();
    setInterval(checkBrowserStatus, 3000);
});

// Load available site configurations
async function loadConfigurations() {
    try {
        const res = await fetch("/api/configs");
        if (!res.ok) throw new Error("Failed to load configs");
        currentConfigs = await res.json();

        const select = document.getElementById("config-select");
        select.innerHTML = "";

        currentConfigs.forEach((cfg, idx) => {
            const opt = document.createElement("option");
            opt.value = cfg.name;
            opt.textContent = cfg.title ? `${cfg.title} (${cfg.name})` : cfg.name;
            select.appendChild(opt);
        });

        if (currentConfigs.length > 0) {
            select.selectedIndex = 0;
            onConfigSelected();
        }
    } catch (err) {
        console.error("Config load error:", err);
    }
}

// When user switches config
function onConfigSelected() {
    const name = document.getElementById("config-select").value;
    activeConfig = currentConfigs.find(c => c.name === name);
    if (!activeConfig) return;

    document.getElementById("active-config-badge").textContent = `Config: ${activeConfig.name}`;
    document.getElementById("site-url").value = activeConfig.url || "";
    
    // Refresh existing attachment rows' target options
    updateAllAttachmentTargets();
}

// Browser Status
async function checkBrowserStatus() {
    try {
        const res = await fetch("/api/browser/status");
        if (!res.ok) return;
        const data = await res.json();

        const dot = document.getElementById("browser-dot");
        const text = document.getElementById("browser-status-text");
        const btnHeadless = document.getElementById("mode-headless");
        const btnHeaded = document.getElementById("mode-headed");

        if (data.is_active) {
            dot.className = "status-dot active";
            text.textContent = `Active (${data.active_pages_count} pages)`;
        } else {
            dot.className = "status-dot";
            text.textContent = "Idle / Ready";
        }

        if (data.headless) {
            btnHeadless.classList.add("active");
            btnHeaded.classList.remove("active");
        } else {
            btnHeaded.classList.add("active");
            btnHeadless.classList.remove("active");
        }
    } catch (e) {
        // quiet fail on network blip
    }
}

async function setBrowserMode(headless) {
    try {
        await fetch("/api/browser/mode", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ headless })
        });
        checkBrowserStatus();
    } catch (e) {
        alert("Failed to switch browser mode: " + e.message);
    }
}

// Attachments Management
function addAttachmentRow() {
    const container = document.getElementById("attachments-list");
    const row = document.createElement("div");
    row.className = "attachment-row";

    // File input
    const fileInput = document.createElement("input");
    fileInput.type = "file";
    fileInput.className = "file-input-custom";

    // Target dropdown
    const targetSelect = document.createElement("select");
    targetSelect.className = "target-select";
    populateTargetOptions(targetSelect);

    // Remove button
    const removeBtn = document.createElement("button");
    removeBtn.type = "button";
    removeBtn.className = "btn-icon-remove";
    removeBtn.innerHTML = "✖";
    removeBtn.title = "Remove Attachment";
    removeBtn.onclick = () => row.remove();

    row.appendChild(fileInput);
    row.appendChild(targetSelect);
    row.appendChild(removeBtn);
    container.appendChild(row);
}

function populateTargetOptions(selectElement) {
    selectElement.innerHTML = "";
    if (activeConfig && activeConfig.attachments && activeConfig.attachments.length > 0) {
        activeConfig.attachments.forEach(att => {
            const opt = document.createElement("option");
            opt.value = att.name;
            opt.textContent = `${att.name} (${att.selector})`;
            selectElement.appendChild(opt);
        });
    } else {
        const opt = document.createElement("option");
        opt.value = "file1";
        opt.textContent = "file1 (Default)";
        selectElement.appendChild(opt);
    }
}

function updateAllAttachmentTargets() {
    const selects = document.querySelectorAll(".target-select");
    selects.forEach(sel => {
        const prevVal = sel.value;
        populateTargetOptions(sel);
        if (prevVal) sel.value = prevVal;
    });
}

// Submit Job
async function submitAutomationJob() {
    const configName = document.getElementById("config-select").value;
    const url = document.getElementById("site-url").value.trim();
    const prompt = document.getElementById("prompt-input").value.trim();

    if (!url) {
        alert("Please enter a Website URL.");
        return;
    }
    if (!prompt) {
        alert("Please enter a message or prompt.");
        return;
    }

    const btnSubmit = document.getElementById("btn-submit-job");
    btnSubmit.disabled = true;

    // Build FormData
    const formData = new FormData();
    formData.append("config_name", configName);
    formData.append("url", url);
    formData.append("prompt", prompt);

    // Gather attachments and their targets
    const attachmentRows = document.querySelectorAll(".attachment-row");
    const targets = [];
    attachmentRows.forEach(row => {
        const fileInput = row.querySelector("input[type='file']");
        const targetSelect = row.querySelector(".target-select");
        if (fileInput.files && fileInput.files.length > 0) {
            formData.append("files", fileInput.files[0]);
            targets.push(targetSelect.value);
        }
    });
    formData.append("targets", JSON.stringify(targets));

    resetExecutionUI();
    appendLog("[System]", "Submission", "Submitting automation job to queue...", "INFO");

    try {
        const res = await fetch("/api/jobs", {
            method: "POST",
            body: formData
        });

        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Job creation failed");
        }

        const data = await res.json();
        activeJobId = data.job_id;
        document.getElementById("job-id-display").textContent = `Job ID: ${activeJobId.slice(0, 8)}...`;
        
        // Start streaming logs & status
        listenToJobStream(activeJobId);

    } catch (err) {
        alert("Failed to start job: " + err.message);
        appendLog("[System]", "Error", err.message, "ERROR");
        btnSubmit.disabled = false;
    }
}

// SSE Job Streaming
function listenToJobStream(jobId) {
    if (eventSource) {
        eventSource.close();
    }

    eventSource = new EventSource(`/api/jobs/${jobId}/stream`);

    eventSource.onmessage = (event) => {
        try {
            const job = JSON.parse(event.data);
            updateJobUI(job);
        } catch (e) {
            console.error("SSE parse error", e);
        }
    };

    eventSource.onerror = () => {
        // Fallback polling if SSE disconnects
        eventSource.close();
        pollJobStatus(jobId);
    };
}

async function pollJobStatus(jobId) {
    const interval = setInterval(async () => {
        try {
            const res = await fetch(`/api/jobs/${jobId}`);
            if (!res.ok) {
                clearInterval(interval);
                return;
            }
            const job = await res.json();
            updateJobUI(job);

            if (["completed", "failed", "cancelled"].includes(job.status)) {
                clearInterval(interval);
            }
        } catch (e) {
            clearInterval(interval);
        }
    }, 1500);
}

// Update UI based on Job State
function updateJobUI(job) {
    updateStepper(job.status);

    // Auth required banner
    const authBanner = document.getElementById("auth-alert-banner");
    if (job.status === "login_required") {
        authBanner.classList.add("visible");
    } else {
        authBanner.classList.remove("visible");
    }

    // Refresh logs
    if (job.logs) {
        renderLogs(job.logs);
    }

    // Extracted response
    if (job.response_text) {
        document.getElementById("response-box").textContent = job.response_text;
    } else if (job.error) {
        document.getElementById("response-box").innerHTML = `<span style="color:var(--danger)">Error: ${escapeHtml(job.error)}</span>`;
    }

    // Screenshot
    if (job.screenshot_url) {
        const container = document.getElementById("screenshot-container");
        const img = document.getElementById("screenshot-img");
        const link = document.getElementById("screenshot-link");
        container.style.display = "block";
        img.src = job.screenshot_url + "?t=" + Date.now();
        link.href = job.screenshot_url;
    }

    // Re-enable button on terminal status
    if (["completed", "failed", "cancelled"].includes(job.status)) {
        document.getElementById("btn-submit-job").disabled = false;
    }
}

function updateStepper(status) {
    const steps = ["queued", "starting", "navigating", "uploading", "sending", "waiting_response", "completed"];
    const currentIdx = steps.indexOf(status);

    steps.forEach((step, idx) => {
        const el = document.getElementById(`step-${step}`);
        if (!el) return;
        el.className = "step-item";
        if (idx < currentIdx) {
            el.classList.add("completed");
        } else if (idx === currentIdx) {
            el.classList.add("active");
        }
    });

    if (status === "completed") {
        document.getElementById("step-completed").classList.add("completed");
    }
}

function renderLogs(logs) {
    const terminal = document.getElementById("log-terminal");
    terminal.innerHTML = "";
    logs.forEach(log => {
        const line = document.createElement("div");
        line.className = "log-line";
        
        const timePart = log.timestamp ? log.timestamp.split("T")[1].slice(0, 8) : "";
        line.innerHTML = `
            <span class="log-time">[${timePart}]</span>
            <span class="log-step">${escapeHtml(log.step)}:</span>
            <span class="log-msg ${log.level}">${escapeHtml(log.message)}</span>
        `;
        terminal.appendChild(line);
    });
    terminal.scrollTop = terminal.scrollHeight;
}

function appendLog(time, step, message, level) {
    const terminal = document.getElementById("log-terminal");
    const line = document.createElement("div");
    line.className = "log-line";
    line.innerHTML = `
        <span class="log-time">${time}</span>
        <span class="log-step">${step}:</span>
        <span class="log-msg ${level}">${escapeHtml(message)}</span>
    `;
    terminal.appendChild(line);
    terminal.scrollTop = terminal.scrollHeight;
}

function clearLogs() {
    document.getElementById("log-terminal").innerHTML = "";
}

function resetExecutionUI() {
    document.getElementById("response-box").innerHTML = '<div class="response-empty">Executing workflow...</div>';
    document.getElementById("screenshot-container").style.display = "none";
    document.getElementById("auth-alert-banner").classList.remove("visible");
    updateStepper("queued");
}

// Resume Paused Job
async function resumeActiveJob() {
    if (!activeJobId) return;
    try {
        await fetch(`/api/jobs/${activeJobId}/resume`, { method: "POST" });
        document.getElementById("auth-alert-banner").classList.remove("visible");
        appendLog("[System]", "Resume", "Sent resume signal to worker.", "SUCCESS");
    } catch (e) {
        alert("Failed to resume job: " + e.message);
    }
}

// Copy & Download Response
function copyResponse() {
    const text = document.getElementById("response-box").textContent;
    if (!text || text.includes("will appear here") || text.includes("Executing workflow")) return;
    navigator.clipboard.writeText(text).then(() => alert("Response copied to clipboard!"));
}

function downloadResponse() {
    const text = document.getElementById("response-box").textContent;
    if (!text) return;
    const blob = new Blob([text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `response_${activeJobId ? activeJobId.slice(0, 8) : "text"}.txt`;
    a.click();
    URL.revokeObjectURL(url);
}

// Modals
function openLoginModal() {
    const input = document.getElementById("modal-login-url");
    if (activeConfig) {
        if (activeConfig.name === "gemini") {
            input.value = "https://gemini.google.com/app";
        } else if (activeConfig.auth && activeConfig.auth.login_url) {
            input.value = activeConfig.auth.login_url;
        } else if (activeConfig.url) {
            input.value = activeConfig.url;
        }
    }
    document.getElementById("modal-login").classList.add("open");
}
function closeLoginModal() {
    document.getElementById("modal-login").classList.remove("open");
}

async function triggerInteractiveLogin() {
    const url = document.getElementById("modal-login-url").value.trim();
    if (!url) return;
    try {
        const res = await fetch("/api/browser/login", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url })
        });
        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.detail || "Failed to launch browser");
        }
        alert(data.message || "Browser opened! Please log in.");
        closeLoginModal();
        checkBrowserStatus();
    } catch (e) {
        alert("Error launching login: " + e.message);
    }
}

function openRecorderModal() {
    document.getElementById("modal-recorder").classList.add("open");
}
function closeRecorderModal() {
    document.getElementById("modal-recorder").classList.remove("open");
}

async function startRecordingSession() {
    const url = document.getElementById("recorder-url").value.trim();
    if (!url) {
        alert("Please enter target URL");
        return;
    }
    try {
        const res = await fetch("/api/recorder/start", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url, headed: true })
        });
        const data = await res.json();
        alert("Recording browser opened! Interact with the site then click 'Generate YAML'.");
    } catch (e) {
        alert("Error starting recorder: " + e.message);
    }
}

async function generateConfigFromRecording() {
    const configName = document.getElementById("recorder-config-name").value.trim();
    if (!configName) {
        alert("Please provide a name for the new configuration.");
        return;
    }
    try {
        const res = await fetch("/api/recorder/generate-config", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ config_name: configName })
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Failed to generate");
        }
        const cfg = await res.json();
        alert(`Configuration '${cfg.name}' generated and saved!`);
        closeRecorderModal();
        await loadConfigurations();
    } catch (e) {
        alert("Failed to generate configuration: " + e.message);
    }
}

// Config Editor
async function openConfigEditorModal() {
    const name = document.getElementById("config-select").value;
    if (!name) return;
    try {
        const res = await fetch(`/api/configs/${name}`);
        const cfg = await res.json();
        document.getElementById("config-yaml-editor").value = JSON.stringify(cfg, null, 2);
        document.getElementById("modal-config-editor").classList.add("open");
    } catch (e) {
        alert("Error fetching config: " + e.message);
    }
}

function closeConfigEditorModal() {
    document.getElementById("modal-config-editor").classList.remove("open");
}

async function saveEditedConfig() {
    try {
        const raw = document.getElementById("config-yaml-editor").value;
        const parsed = JSON.parse(raw);
        const res = await fetch("/api/configs", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(parsed)
        });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || "Save failed");
        }
        alert("Configuration saved successfully!");
        closeConfigEditorModal();
        await loadConfigurations();
    } catch (e) {
        alert("Error saving config: " + e.message);
    }
}

function escapeHtml(str) {
    if (!str) return "";
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
