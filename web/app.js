const state = {
  jobId: null,
  variants: [],
  status: "all",
  year: "all",
  query: "",
  pollingTimer: null,
  currentUrl: "",
};

const $ = (selector) => document.querySelector(selector);
const form = $("#scrapeForm");
const urlInput = $("#urlInput");
const scrapeBtn = $("#scrapeBtn");
const progressCard = $("#progressCard");
const progressBar = $("#progressBar");
const progressNumber = $("#progressNumber");
const progressKicker = $("#progressKicker");
const progressTitle = $("#progressTitle");
const progressMessage = $("#progressMessage");
const errorBox = $("#errorBox");
const errorText = $("#errorText");
const results = $("#results");
const variantBody = $("#variantBody");
const tableEmpty = $("#tableEmpty");
const toast = $("#toast");

function showToast(message, isError = false) {
  toast.textContent = message;
  toast.classList.toggle("error", isError);
  toast.classList.add("show");
  window.clearTimeout(showToast.timer);
  showToast.timer = window.setTimeout(() => toast.classList.remove("show"), 2600);
}

function setBusy(busy) {
  scrapeBtn.disabled = busy;
  scrapeBtn.classList.toggle("loading", busy);
  scrapeBtn.querySelector("span").textContent = busy ? "抓取中" : "开始抓取";
}

function updateSteps(progress, completed = false) {
  let active = 0;
  if (completed || progress >= 100) active = 5;
  else if (progress >= 92) active = 4;
  else if (progress >= 78) active = 3;
  else if (progress >= 12) active = 2;
  else if (progress >= 5) active = 1;

  document.querySelectorAll(".step").forEach((node) => {
    const index = Number(node.dataset.step);
    node.classList.toggle("active", !completed && index === active);
    node.classList.toggle("done", completed || index < active);
  });
}

function updateProgress(job) {
  const value = Math.max(0, Math.min(100, Number(job.progress || 0)));
  progressBar.style.width = `${value}%`;
  progressNumber.innerHTML = `${value}<span>%</span>`;
  progressMessage.textContent = job.message || "正在处理，请稍候";
  if (job.status === "completed") {
    progressKicker.textContent = "抓取完成";
    progressTitle.textContent = "配置数据已经整理好了";
  } else if (job.message && job.message.includes("缓存")) {
    progressKicker.textContent = "读取本地缓存";
    progressTitle.textContent = "正在恢复上次抓取结果";
  } else {
    progressKicker.textContent = "正在连接汽车之家";
    progressTitle.textContent = "正在读取车系数据";
  }
  updateSteps(value, job.status === "completed");
}

function resetForNewJob() {
  window.clearTimeout(state.pollingTimer);
  state.jobId = null;
  state.variants = [];
  state.status = "all";
  state.year = "all";
  state.query = "";
  errorBox.classList.add("hidden");
  results.classList.add("hidden");
  progressCard.classList.remove("hidden");
  progressBar.style.width = "0%";
  progressNumber.innerHTML = "0<span>%</span>";
  progressMessage.textContent = "首次抓取可能需要 10–30 秒，请保持页面打开。";
  progressKicker.textContent = "正在连接汽车之家";
  progressTitle.textContent = "正在读取车系数据";
  updateSteps(0, false);
  $("#searchInput").value = "";
  $("#yearFilter").innerHTML = '<option value="all">全部年款</option>';
}

async function startJob(forceRefresh = false) {
  const url = (urlInput.value || "").trim();
  if (!url) {
    showToast("请先粘贴汽车之家车系网址", true);
    urlInput.focus();
    return;
  }
  state.currentUrl = url;
  sessionStorage.setItem("autohome_url", url);
  resetForNewJob();
  setBusy(true);
  progressCard.scrollIntoView({ behavior: "smooth", block: "center" });

  try {
    const response = await fetch("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, force_refresh: forceRefresh }),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(data.error || "创建抓取任务失败");
    state.jobId = data.job_id;
    sessionStorage.setItem("autohome_job_id", data.job_id);
    pollJob();
  } catch (error) {
    showError(error.message || "创建任务失败");
  }
}

function showError(message) {
  window.clearTimeout(state.pollingTimer);
  setBusy(false);
  progressCard.classList.remove("hidden");
  errorBox.classList.remove("hidden");
  errorText.textContent = message;
  progressKicker.textContent = "处理未完成";
  progressTitle.textContent = "抓取遇到问题";
  progressMessage.textContent = "可以检查网址、网络连接后重新尝试。";
  updateSteps(0, false);
}

async function pollJob() {
  if (!state.jobId) return;
  try {
    const response = await fetch(`/api/jobs/${state.jobId}`);
    const job = await response.json();
    if (!response.ok) throw new Error(job.error || "任务状态读取失败");
    updateProgress(job);
    if (job.status === "completed") {
      setBusy(false);
      renderResults(job);
      return;
    }
    if (job.status === "error") {
      showError(job.error || job.message || "抓取失败");
      return;
    }
    state.pollingTimer = window.setTimeout(pollJob, 850);
  } catch (error) {
    showError(error.message || "任务状态读取失败");
  }
}

function chip(text, className) {
  const span = document.createElement("span");
  span.className = className;
  span.textContent = text;
  return span;
}

function renderResults(job) {
  state.variants = job.variants || [];
  state.status = "all";
  state.year = "all";
  state.query = "";

  $("#seriesTitle").textContent = `${job.series_name || "车型"} · 全量配置`;
  const fetched = (job.completed_at || "").replace("T", " ");
  const years = job.years || [];
  const yearRange = years.length ? `${years[years.length - 1]}–${years[0]} 款` : "暂无年款";
  $("#seriesMeta").textContent = `抓取时间 ${fetched} · ${yearRange} · 共 ${state.variants.length} 个车款`;
  $("#onsaleStat").textContent = job.stats?.onsale ?? 0;
  $("#stopsaleStat").textContent = job.stats?.stopsale ?? 0;
  $("#yearStat").textContent = job.stats?.years ?? 0;
  $("#paramStat").textContent = job.stats?.params ?? 0;
  $("#allCount").textContent = state.variants.length;
  $("#onsaleCount").textContent = job.stats?.onsale ?? 0;
  $("#stopsaleCount").textContent = job.stats?.stopsale ?? 0;

  const yearSelect = $("#yearFilter");
  yearSelect.innerHTML = '<option value="all">全部年款</option>';
  years.forEach((year) => {
    const option = document.createElement("option");
    option.value = String(year);
    option.textContent = `${year} 款`;
    yearSelect.appendChild(option);
  });

  const warning = $("#warningNotice");
  if (job.warnings && job.warnings.length) {
    warning.textContent = `部分年款读取失败：${job.warnings.join("；")}`;
    warning.classList.remove("hidden");
  } else {
    warning.classList.add("hidden");
  }

  progressCard.classList.add("hidden");
  results.classList.remove("hidden");
  document.querySelectorAll("#statusTabs button").forEach((button) => {
    button.classList.toggle("active", button.dataset.status === "all");
  });
  renderVariantRows();
  results.scrollIntoView({ behavior: "smooth", block: "start" });
}

function filteredVariants() {
  return state.variants.filter((variant) => {
    if (state.status === "20" && ![20, 30].includes(variant.status)) return false;
    if (state.status === "40" && variant.status !== 40) return false;
    if (state.year !== "all" && String(variant.year) !== state.year) return false;
    if (state.query) {
      const haystack = `${variant.specname || ""} ${variant.full_name || ""}`.toLowerCase();
      if (!haystack.includes(state.query.toLowerCase())) return false;
    }
    return true;
  });
}

function renderVariantRows() {
  const rows = filteredVariants();
  variantBody.replaceChildren();
  const fragment = document.createDocumentFragment();
  rows.forEach((variant) => {
    const tr = document.createElement("tr");
    const yearCell = document.createElement("td");
    yearCell.appendChild(chip(`${variant.year}款`, "year-chip"));
    tr.appendChild(yearCell);

    const statusCell = document.createElement("td");
    statusCell.appendChild(
      chip(variant.status_label, `status-chip ${variant.status === 20 ? "onsale" : "stopsale"}`)
    );
    tr.appendChild(statusCell);

    const nameCell = document.createElement("td");
    nameCell.textContent = variant.specname || variant.full_name || "-";
    tr.appendChild(nameCell);

    const guideCell = document.createElement("td");
    const guide = document.createElement("span");
    guide.className = variant.guide_price && variant.guide_price !== "暂无报价" ? "price-main" : "price-muted";
    guide.textContent = variant.guide_price || "-";
    guideCell.appendChild(guide);
    tr.appendChild(guideCell);

    const discountCell = document.createElement("td");
    discountCell.textContent = variant.discount || "-";
    tr.appendChild(discountCell);

    const priceTypeCell = document.createElement("td");
    priceTypeCell.textContent = variant.price_type || "-";
    tr.appendChild(priceTypeCell);
    fragment.appendChild(tr);
  });
  variantBody.appendChild(fragment);
  tableEmpty.classList.toggle("hidden", rows.length !== 0);
  $("#tableCount").textContent = `共 ${rows.length} 个车款`;
}

form.addEventListener("submit", (event) => {
  event.preventDefault();
  startJob(false);
});

document.querySelectorAll("[data-example]").forEach((button) => {
  button.addEventListener("click", () => {
    urlInput.value = button.dataset.example;
    urlInput.focus();
  });
});

document.querySelectorAll("#statusTabs button").forEach((button) => {
  button.addEventListener("click", () => {
    state.status = button.dataset.status;
    document.querySelectorAll("#statusTabs button").forEach((node) => {
      node.classList.toggle("active", node === button);
    });
    renderVariantRows();
  });
});

$("#yearFilter").addEventListener("change", (event) => {
  state.year = event.target.value;
  renderVariantRows();
});

$("#searchInput").addEventListener("input", (event) => {
  state.query = event.target.value.trim();
  renderVariantRows();
});

$("#exportBtn").addEventListener("click", () => {
  if (!state.jobId) return;
  showToast("正在生成 Excel，文件较大时可能需要几秒");
  window.location.href = `/api/jobs/${state.jobId}/export`;
});

$("#openFolderBtn").addEventListener("click", async () => {
  try {
    const response = await fetch("/api/open-export-folder", { method: "POST" });
    if (!response.ok) throw new Error();
    showToast("已打开导出文件夹");
  } catch {
    showToast("无法打开导出文件夹", true);
  }
});

$("#retryBtn").addEventListener("click", () => startJob(true));
$("#refreshBtn").addEventListener("click", () => startJob(true));

$("#shutdownBtn").addEventListener("click", async () => {
  if (!window.confirm("确定要退出汽车之家配置采集器吗？退出后当前页面将停止服务。")) return;
  try {
    await fetch("/api/shutdown", { method: "POST" });
  } catch (_) {}
  document.body.innerHTML = `
    <div style="min-height:100vh;display:grid;place-items:center;background:#f4f8fc;color:#2b435c;font-family:'PingFang SC','Microsoft YaHei',sans-serif">
      <div style="text-align:center">
        <div style="font-size:22px;font-weight:700;margin-bottom:8px">程序已退出</div>
        <div style="font-size:13px;color:#8292a4">现在可以关闭这个页面了</div>
      </div>
    </div>`;
});

async function restoreSession() {
  const jobId = sessionStorage.getItem("autohome_job_id");
  const savedUrl = sessionStorage.getItem("autohome_url");
  if (savedUrl) urlInput.value = savedUrl;
  if (!jobId) return;
  state.jobId = jobId;
  state.currentUrl = savedUrl || "";
  setBusy(true);
  progressCard.classList.remove("hidden");
  try {
    const response = await fetch(`/api/jobs/${jobId}`);
    if (!response.ok) {
      sessionStorage.removeItem("autohome_job_id");
      state.jobId = null;
      setBusy(false);
      progressCard.classList.add("hidden");
      return;
    }
    const job = await response.json();
    updateProgress(job);
    if (job.status === "completed") {
      setBusy(false);
      renderResults(job);
    } else if (job.status === "error") {
      showError(job.error || job.message);
    } else {
      pollJob();
    }
  } catch {
    setBusy(false);
    progressCard.classList.add("hidden");
  }
}

async function loadAppVersion() {
  try {
    const response = await fetch("/api/app-info", { cache: "no-store" });
    const info = await response.json();
    $("#appVersion").textContent = `v${info.version} · 数据来自公开页面，仅供参考`;
  } catch (_) {
    $("#appVersion").textContent = "数据来自公开页面，仅供参考";
  }
}

if (window.__DEMO_JOB__) {
  urlInput.value = "https://www.autohome.com.cn/config/series/8241.html";
  renderResults(window.__DEMO_JOB__);
} else {
  restoreSession();
}
loadAppVersion();
