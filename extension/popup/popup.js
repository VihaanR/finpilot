function formatRupees(paise) {
  if (paise == null) return "—";
  return "₹" + Math.round(paise / 100).toLocaleString("en-IN");
}

function renderBudget(budget) {
  const status = document.getElementById("status");
  const figures = document.getElementById("budget-figures");
  if (!budget || budget.error) {
    status.textContent = budget?.error
      ? "Couldn't reach FinPilot — check the API setting below."
      : "No data yet.";
    figures.hidden = true;
    return;
  }
  status.textContent = "";
  figures.hidden = false;
  document.getElementById("discretionary").textContent = formatRupees(budget.discretionary_paise);
  document.getElementById("safe-daily").textContent = formatRupees(budget.safe_daily_paise) + " / day";
  document.getElementById("as-of").textContent = budget.as_of || "—";
}

function renderCooldowns(cooldowns) {
  const list = document.getElementById("cooldown-list");
  list.innerHTML = "";
  if (!cooldowns || cooldowns.length === 0) {
    const li = document.createElement("li");
    li.id = "cooldown-empty";
    li.textContent = "None yet.";
    list.append(li);
    return;
  }
  for (const c of cooldowns.slice(-5).reverse()) {
    const li = document.createElement("li");
    const when = new Date(c.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" });
    li.textContent = `${when} — ${formatRupees(c.cart_paise)} on ${c.site}`;
    list.append(li);
  }
}

async function load() {
  const { budget, cooldowns, apiBase } = await chrome.storage.local.get([
    "budget",
    "cooldowns",
    "apiBase",
  ]);
  renderBudget(budget);
  renderCooldowns(cooldowns);
  document.getElementById("api-select").value =
    apiBase || "https://finpilot-w4ki.onrender.com";
}

document.getElementById("refresh").addEventListener("click", async () => {
  document.getElementById("status").textContent = "Refreshing…";
  await chrome.runtime.sendMessage({ type: "refresh-budget" });
  load();
});

document.getElementById("api-select").addEventListener("change", async (e) => {
  await chrome.storage.local.set({ apiBase: e.target.value });
  await chrome.runtime.sendMessage({ type: "refresh-budget" });
  load();
});

load();
