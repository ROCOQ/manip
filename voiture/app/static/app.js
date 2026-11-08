"use strict";

const TABS = { accueil: "Accueil", annonces: "Annonces", chef: "Le chef", profil: "Profil & réglages", equipe: "L'équipe" };
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const store = {
  get(k) { try { return localStorage.getItem(k); } catch { return null; } },
  set(k, v) { try { localStorage.setItem(k, v); } catch { /* stockage indisponible */ } },
  del(k) { try { localStorage.removeItem(k); } catch { /* idem */ } },
};

let token = store.get("voiture-token") || "";
let currentTab = "accueil";
let listingFilter = "";
let pane = "listings";
let dealerFilter = "";
let pollTimer = null;
let lastStatus = null;

// ------------------------------------------------------------------ utilitaires
async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}`, ...(options.headers || {}) },
    body: options.body && typeof options.body !== "string" ? JSON.stringify(options.body) : options.body,
  });
  if (res.status === 401) { showLogin(); throw new Error("Non connecté"); }
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || `Erreur ${res.status}`);
  return data;
}

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

// Mise en forme légère et sûre : échappement d'abord, puis gras, liens, paragraphes.
function rich(text) {
  let html = esc(text);
  html = html.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  html = html.replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
  html = html.replace(/(^|[\s(])(https?:\/\/[^\s<)]+)/g, '$1<a href="$2" target="_blank" rel="noopener">lien</a>');
  return html.split(/\n{2,}/).map((p) => `<p>${p.replace(/\n/g, "<br>")}</p>`).join("");
}

const euros = (n) => (n || n === 0) ? `${Math.round(n).toLocaleString("fr-FR")} €` : "prix ?";
const km = (n) => (n || n === 0) ? `${Math.round(n).toLocaleString("fr-FR")} km` : null;
const when = (iso) => iso ? new Date(iso).toLocaleString("fr-FR", { dateStyle: "medium", timeStyle: "short" }) : "";
const scoreClass = (s) => s == null ? "none" : s >= 75 ? "good" : s >= 50 ? "mid" : "bad";
const isStandalone = () => window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;

function openDialog(html) {
  $("#dialog-body").innerHTML = html;
  $("#dialog").showModal();
}

// ------------------------------------------------------------------ navigation
function showLogin() {
  $$(".view").forEach((v) => (v.hidden = true));
  $("#tabbar").hidden = true;
  $("#login").hidden = false;
  $("#title").textContent = "Chasseur de voiture";
}

function go(tab) {
  if (tab === "concessions") { pane = "dealers"; tab = "annonces"; }
  if (!TABS[tab]) tab = "accueil";
  currentTab = tab;
  $("#login").hidden = true;
  $("#tabbar").hidden = false;
  $$(".view").forEach((v) => (v.hidden = v.id !== `view-${tab}`));
  $$("#tabbar button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
  $("#title").textContent = TABS[tab];
  if (location.hash !== `#${tab}`) history.replaceState(null, "", `#${tab}`);
  ({ accueil: loadHome, annonces: loadListings, chef: loadChat, profil: loadProfile, equipe: loadTeam })[tab]();
}

// ------------------------------------------------------------------ accueil
async function refreshStatus() {
  const s = await api("/api/status");
  lastStatus = s;
  $("#busy").hidden = !s.mission_en_cours;
  return s;
}

async function loadHome() {
  const [s, listings] = await Promise.all([refreshStatus(), api("/api/listings")]);
  $("#onboarding").hidden = !s.profil_vide;
  const btn = $("#btn-mission");
  if (s.mission_en_cours) {
    $("#mission-status").textContent = `Mission n°${s.mission_en_cours} en cours : les agents cherchent…`;
    btn.disabled = true;
  } else {
    const next = s.prochaine_mission ? `Prochaine recherche automatique : ${when(s.prochaine_mission)}.` : "Recherche automatique désactivée.";
    $("#mission-status").textContent = `${s.nb_annonces} annonce(s) suivie(s). ${s.profil_vide ? "Profil à compléter." : next}`;
    btn.disabled = false;
  }

  const r = s.dernier_rapport;
  $("#report").hidden = !r;
  if (r) {
    $("#report-date").textContent = s.derniere_mission ? `Mission du ${when(s.derniere_mission.fin || s.derniere_mission.debut)}` : "";
    $("#report-resume").innerHTML = rich(r.resume || "");
    $("#report-models").innerHTML = (r.modeles_conseilles || []).map((m) => `<span class="chip">${esc(m)}</span>`).join("");
    const qs = r.questions || [];
    $("#report-questions").innerHTML = qs.length ? `<h3 class="small muted">Le chef aimerait savoir :</h3>` +
      qs.map((q, i) => `<div class="row between" style="margin:6px 0"><span>${esc(q)}</span><button data-question="${i}">Répondre</button></div>`).join("") : "";
    $$("[data-question]").forEach((b) => b.addEventListener("click", () => {
      go("chef");
      const input = $("#chat-input");
      input.value = `À propos de « ${qs[b.dataset.question]} » : `;
      input.focus();
    }));
  }
  const top = listings.filter((l) => l.score != null).slice(0, 3);
  renderListings($("#top-listings"), top.length ? top : listings.slice(0, 3),
    "Aucune annonce pour l'instant. Lancez une recherche !");
  renderNotifCard(s);
  schedulePoll(s.mission_en_cours ? 5000 : 60000);
}

async function renderNotifCard(s) {
  const card = $("#notif-card"), text = $("#notif-text"), btn = $("#btn-notif");
  const supported = "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  card.hidden = false;
  btn.hidden = true;
  if (!supported) {
    const ios = /iPhone|iPad|iPod/.test(navigator.userAgent);
    text.innerHTML = ios && !isStandalone()
      ? "Pour recevoir des alertes sur iPhone : touchez <strong>Partager</strong> puis <strong>Sur l'écran d'accueil</strong>, et ouvrez l'app depuis son icône."
      : "Ce navigateur ne gère pas les notifications. Vous pouvez utiliser ntfy (voir Profil & réglages).";
    return;
  }
  if (Notification.permission === "granted" && s.nb_appareils_notifies > 0) {
    const reg = await navigator.serviceWorker.ready;
    if (await reg.pushManager.getSubscription()) { card.hidden = true; return; }
  }
  if (Notification.permission === "denied") {
    text.textContent = "Les notifications sont bloquées pour cette app. Réactivez-les dans les réglages de l'appareil.";
    return;
  }
  text.textContent = "Soyez prévenu dès que les agents trouvent une bonne affaire, même app fermée.";
  btn.hidden = false;
}

function urlB64ToUint8Array(base64) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

async function enableNotifications() {
  try {
    const permission = await Notification.requestPermission();
    if (permission !== "granted") throw new Error("Permission refusée");
    const { publicKey } = await api("/api/push/vapid");
    const reg = await navigator.serviceWorker.ready;
    let sub = await reg.pushManager.getSubscription();
    if (!sub) sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlB64ToUint8Array(publicKey) });
    await api("/api/push/subscribe", { method: "POST", body: sub.toJSON() });
    $("#notif-text").textContent = "Notifications activées ✓";
    $("#btn-notif").hidden = true;
  } catch (e) {
    $("#notif-text").textContent = `Impossible d'activer les notifications : ${e.message}`;
  }
}

async function startMission() {
  const btn = $("#btn-mission");
  btn.disabled = true;
  try {
    await api("/api/missions", { method: "POST", body: { consigne: "" } });
    await loadHome();
  } catch (e) {
    alert(e.message);
    btn.disabled = false;
  }
}

function schedulePoll(ms) {
  clearTimeout(pollTimer);
  pollTimer = setTimeout(async () => {
    if (document.hidden || !token) return schedulePoll(ms);
    try {
      const wasRunning = lastStatus && lastStatus.mission_en_cours;
      const s = await refreshStatus();
      if (currentTab === "accueil" || (wasRunning && !s.mission_en_cours && currentTab === "annonces")) {
        return go(currentTab);
      }
      schedulePoll(s.mission_en_cours ? 5000 : 60000);
    } catch { schedulePoll(30000); }
  }, ms);
}

// ------------------------------------------------------------------ annonces
async function loadListings() {
  $$(".switch button").forEach((b) => b.classList.toggle("active", b.dataset.pane === pane));
  $("#pane-listings").hidden = pane !== "listings";
  $("#pane-dealers").hidden = pane !== "dealers";
  $("#title").textContent = pane === "dealers" ? "Concessions" : TABS.annonces;
  if (pane === "dealers") return loadDealers();
  $$("[data-filter]").forEach((b) => b.classList.toggle("active", b.dataset.filter === listingFilter));
  const q = listingFilter ? `?statut=${encodeURIComponent(listingFilter)}` : "";
  const listings = await api(`/api/listings${q}`);
  renderListings($("#listings"), listings, listingFilter === "favori"
    ? "Pas encore de favori. Touchez ❤️ sur une annonce pour la garder."
    : "Aucune annonce ici pour l'instant.");
}

function list(title, items) {
  return items && items.length ? `<strong>${esc(title)}</strong><ul>${items.map((i) => `<li>${esc(i)}</li>`).join("")}</ul>` : "";
}

function renderListings(root, listings, emptyText) {
  if (!listings.length) { root.innerHTML = `<p class="empty">${esc(emptyText)}</p>`; return; }
  root.innerHTML = listings.map((l) => {
    const a = l.analyse || {};
    const meta = [l.annee, km(l.km), l.energie, l.boite, l.localisation].filter(Boolean).map(esc).join(" · ");
    const extra = [
      a.prix_juste_estime ? `<p>💶 Juste prix estimé : <strong>${euros(a.prix_juste_estime)}</strong></p>` : "",
      a.cout_annuel_estime ? `<p>🧮 Coût annuel estimé : <strong>${euros(a.cout_annuel_estime)}</strong></p>` : "",
      a.risque ? `<p>🕵️ Risque : ${esc(a.risque)}</p>` : "",
      list("Points forts", a.points_forts), list("Points faibles", a.points_faibles),
      a.conseil ? `<p>👉 <strong>${esc(a.conseil)}</strong></p>` : "",
      l.feedback ? `<p class="muted">Votre avis : ${esc(l.feedback)}</p>` : "",
    ].join("");
    const safeImg = /^https:\/\//.test(l.image_url || "") ? `<img src="${esc(l.image_url)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.remove()">` : "";
    const safeUrl = /^https?:\/\//.test(l.url) ? l.url : "#";
    return `<article class="card listing" data-id="${l.id}">
      ${safeImg}
      <div>
        <h3>${esc(l.titre || "Annonce")}${l.statut === "favori" ? " ❤️" : ""}</h3>
        <span class="price">${euros(l.prix)}</span><span class="tag">${esc(l.source || "")}</span>${l.vendeur ? `<span class="tag">${esc(l.vendeur)}</span>` : ""}
      </div>
      <div class="score ${scoreClass(l.score)}" title="Score du chef">${l.score ?? "–"}</div>
      <div class="meta">${meta}</div>
      ${l.verdict ? `<p class="verdict">${esc(l.verdict)}</p>` : ""}
      ${extra ? `<details><summary>Analyse de l'équipe</summary>${extra}</details>` : ""}
      <div class="actions">
        <a class="primary" href="${esc(safeUrl)}" target="_blank" rel="noopener">Voir l'annonce</a>
        <button data-act="favori">${l.statut === "favori" ? "★ Favori" : "❤️"}</button>
        <button data-act="rejetee">👎</button>
      </div>
    </article>`;
  }).join("");
  $$(".listing [data-act]", root).forEach((b) => b.addEventListener("click", async () => {
    const card = b.closest(".listing");
    const statut = b.dataset.act;
    const question = statut === "rejetee" ? "Pourquoi cette annonce ne vous plaît pas ? (le chef s'en souviendra)" : "Qu'est-ce qui vous plaît ? (facultatif)";
    const feedback = prompt(question);
    if (feedback === null) return;
    try {
      await api(`/api/listings/${card.dataset.id}/status`, { method: "POST", body: { statut, feedback: feedback || null } });
      go(currentTab);
    } catch (e) { alert(e.message); }
  }));
}

// ------------------------------------------------------------------ concessions
function stars(note, nb) {
  if (note == null) return "";
  return `<span class="stars">★ ${String(note).replace(".", ",")}</span>${nb ? ` <span class="muted small">(${nb} avis)</span>` : ""}`;
}

async function loadDealers() {
  $$("[data-dfilter]").forEach((b) => b.classList.toggle("active", b.dataset.dfilter === dealerFilter));
  const q = dealerFilter ? `?statut=${encodeURIComponent(dealerFilter)}` : "";
  const data = await api(`/api/dealers${q}`);
  const btn = $("#btn-dealers"), status = $("#dealer-status");
  btn.disabled = data.recherche_en_cours;
  if (data.recherche_en_cours) {
    status.textContent = "Le repéreur cherche les concessions de votre secteur… (1 à 3 minutes)";
  } else if (data.derniere_recherche) {
    const d = data.derniere_recherche;
    status.textContent = d.erreur ? `Dernière recherche en échec : ${d.synthese || ""}`
      : `${d.nouvelles} nouvelle(s) concession(s) à la dernière recherche. ${d.synthese || ""}`;
  }
  renderDealers(data.concessions);
  if (data.recherche_en_cours) {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(() => currentTab === "annonces" && pane === "dealers" && loadDealers(), 5000);
  }
}

function renderDealers(dealers) {
  const root = $("#dealers");
  if (!dealers.length) {
    root.innerHTML = `<p class="empty">${dealerFilter ? "Aucune concession ici." : "Aucune concession pour l'instant : touchez « Trouver les concessions » ou ajoutez-en une."}</p>`;
    return;
  }
  const safe = (u) => (/^https?:\/\//.test(u || "") ? u : null);
  root.innerHTML = dealers.map((d) => {
    const place = [d.adresse, d.ville].filter(Boolean).join(", ");
    const maps = `https://maps.apple.com/?q=${encodeURIComponent([d.nom, d.adresse, d.ville].filter(Boolean).join(" "))}`;
    const tel = (d.telephone || "").replace(/[^+\d]/g, "");
    const links = [
      tel ? `<a class="primary" href="tel:${esc(tel)}">📞 Appeler</a>` : "",
      safe(d.url_stock) ? `<a href="${esc(d.url_stock)}" target="_blank" rel="noopener">🚗 Stock</a>` : "",
      safe(d.site) ? `<a href="${esc(d.site)}" target="_blank" rel="noopener">🌐 Site</a>` : "",
      `<a href="${esc(maps)}" target="_blank" rel="noopener">🗺️ Itinéraire</a>`,
    ].join("");
    const follow = d.statut === "suivie"
      ? `<button data-dact="nouvelle">★ Suivie</button>`
      : d.statut === "ignoree" ? `<button data-dact="nouvelle">↩︎ Rétablir</button>` : `<button data-dact="suivie">☆ Suivre</button>`;
    const second = d.statut !== "ignoree" ? `<button data-dact="ignoree">👎 Écarter</button>` : `<button data-dact="delete">🗑️ Supprimer</button>`;
    return `<article class="card dealer" data-id="${d.id}">
      <h3>${esc(d.nom)}${d.statut === "suivie" ? " ⭐" : ""}</h3>
      <div class="meta">${[d.type, d.distance_km != null ? `${Math.round(d.distance_km)} km` : null].filter(Boolean).map(esc).join(" · ")} ${stars(d.note_avis, d.nb_avis)}</div>
      ${place ? `<div class="meta">${esc(place)}</div>` : ""}
      ${(d.marques || []).length ? `<div class="chips">${d.marques.map((m) => `<span class="chip">${esc(m)}</span>`).join("")}</div>` : ""}
      ${d.commentaire ? `<p class="small">${esc(d.commentaire)}</p>` : ""}
      ${d.notes_utilisateur ? `<p class="small muted">Votre note : ${esc(d.notes_utilisateur)}</p>` : ""}
      <div class="actions">${links}</div>
      <div class="actions">${follow}${second}</div>
    </article>`;
  }).join("");
  $$("[data-dact]", root).forEach((b) => b.addEventListener("click", async () => {
    const id = b.closest(".dealer").dataset.id;
    try {
      if (b.dataset.dact === "delete") {
        if (!confirm("Supprimer définitivement cette concession ?")) return;
        await api(`/api/dealers/${id}`, { method: "DELETE" });
      } else {
        let notes = null;
        if (b.dataset.dact === "ignoree") {
          notes = prompt("Pourquoi l'écarter ? (le chef s'en souviendra)");
          if (notes === null) return;
        }
        await api(`/api/dealers/${id}/status`, { method: "POST", body: { statut: b.dataset.dact, notes: notes || null } });
      }
      loadDealers();
    } catch (e) { alert(e.message); }
  }));
}

async function searchDealers() {
  try {
    await api("/api/dealers/search", { method: "POST", body: { consigne: "" } });
  } catch (e) { alert(e.message); }
  loadDealers();
}

async function addDealer(e) {
  e.preventDefault();
  const f = e.target, body = {};
  for (const el of f.elements) {
    if (!el.name) continue;
    body[el.name] = el.dataset.csv !== undefined ? el.value.split(",").map((x) => x.trim()).filter(Boolean) : (el.value.trim() || null);
  }
  try {
    await api("/api/dealers", { method: "POST", body });
    f.reset();
    $("#dealer-add").open = false;
    dealerFilter = "";
    loadDealers();
  } catch (err) { alert(err.message); }
}

// ------------------------------------------------------------------ chat
async function loadChat() {
  const { messages, occupe } = await api("/api/chat");
  const log = $("#chat-log");
  const intro = messages.length ? "" : `<div class="bubble assistant">${rich("Bonjour ! Je suis le chef de votre équipe de recherche. Dites-moi ce que vous cherchez — budget, usage, envies — et je m'occupe du reste. Vous pouvez aussi me demander par exemple : **« La Clio 5 hybride est-elle fiable ? »**")}</div>`;
  log.innerHTML = intro + messages.map((m) => `<div class="bubble ${m.role === "user" ? "user" : "assistant"}">${m.role === "user" ? esc(m.content).replace(/\n/g, "<br>") : rich(m.content)}</div>`).join("")
    + (occupe ? `<div class="bubble assistant typing">Le chef réfléchit et consulte son équipe…</div>` : "");
  $("#chat-form button").disabled = occupe;
  window.scrollTo(0, document.body.scrollHeight);
  if (occupe) {
    clearTimeout(pollTimer);
    pollTimer = setTimeout(() => currentTab === "chef" && loadChat(), 2500);
  }
}

async function sendChat(e) {
  e.preventDefault();
  const input = $("#chat-input");
  const message = input.value.trim();
  if (!message) return;
  input.value = "";
  input.style.height = "";
  try {
    await api("/api/chat", { method: "POST", body: { message } });
  } catch (err) { alert(err.message); input.value = message; }
  loadChat();
}

// ------------------------------------------------------------------ profil & réglages
async function loadProfile() {
  const [profile, settings, agents, memory] = await Promise.all([
    api("/api/profile"), api("/api/settings"), api("/api/agents"), api("/api/memory"),
  ]);
  const form = $("#profile-form");
  for (const el of form.elements) {
    if (!el.name) continue;
    const v = profile[el.name];
    if (el.type === "checkbox") el.checked = !!v;
    else if (el.dataset.csv !== undefined) el.value = (v || []).join(", ");
    else el.value = v ?? "";
  }
  $$("[data-list]", form).forEach((box) => {
    const values = profile[box.dataset.list] || [];
    $$("input", box).forEach((i) => (i.checked = values.includes(i.value)));
  });

  const sf = $("#settings-form");
  sf.recherche_auto.checked = !!settings.recherche_auto;
  sf.frequence_heures.value = String(settings.frequence_heures);
  sf.seuil_notification.value = settings.seuil_notification;
  $("#seuil-out").textContent = settings.seuil_notification;
  sf.ntfy_topic.value = settings.ntfy_topic || "";
  $("#agent-checks").innerHTML = agents.filter((a) => a.key !== "chef").map((a) =>
    `<label><input type="checkbox" value="${esc(a.key)}" ${settings.agents_actifs.includes(a.key) ? "checked" : ""} ${a.key === "annonces" ? "disabled" : ""}> ${esc(a.emoji)} ${esc(a.nom)}</label>`).join("");

  $("#memory-list").innerHTML = memory.length ? memory.map((m) =>
    `<li><span>${esc(m.note)}</span><button data-mem="${m.id}" aria-label="Oublier">✕</button></li>`).join("")
    : `<li class="muted">Rien pour l'instant : discutez avec le chef ou notez vos annonces.</li>`;
  $$("[data-mem]").forEach((b) => b.addEventListener("click", async () => {
    await api(`/api/memory/${b.dataset.mem}`, { method: "DELETE" });
    loadProfile();
  }));
}

async function saveProfile(e) {
  e.preventDefault();
  const form = e.target, patch = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    if (el.type === "checkbox") patch[el.name] = el.checked;
    else if (el.dataset.csv !== undefined) patch[el.name] = el.value.split(",").map((s) => s.trim()).filter(Boolean);
    else if (el.type === "number") patch[el.name] = el.value === "" ? null : Number(el.value);
    else patch[el.name] = el.value;
  }
  $$("[data-list]", form).forEach((box) => {
    patch[box.dataset.list] = $$("input:checked", box).map((i) => i.value);
  });
  await api("/api/profile", { method: "PUT", body: patch });
  flash("#profile-saved");
}

async function saveSettings(e) {
  e.preventDefault();
  const f = e.target;
  await api("/api/settings", { method: "PUT", body: {
    recherche_auto: f.recherche_auto.checked,
    frequence_heures: Number(f.frequence_heures.value),
    seuil_notification: Number(f.seuil_notification.value),
    ntfy_topic: f.ntfy_topic.value.trim(),
    agents_actifs: ["annonces", ...$$("#agent-checks input:checked").map((i) => i.value).filter((k) => k !== "annonces")],
  } });
  flash("#settings-saved");
}

function flash(sel) {
  const el = $(sel);
  el.hidden = false;
  setTimeout(() => (el.hidden = true), 2500);
}

// ------------------------------------------------------------------ équipe & missions
async function loadTeam() {
  const [agents, missions] = await Promise.all([api("/api/agents"), api("/api/missions")]);
  $("#team").innerHTML = agents.map((a) => `<div class="card agent"><div class="emoji">${esc(a.emoji)}</div><div><h3>${esc(a.nom)}</h3><p>${esc(a.role)}</p></div></div>`).join("");
  const labels = { terminee: "terminée", echec: "échec", interrompue: "interrompue", en_cours: "en cours…" };
  $("#missions").innerHTML = missions.length ? missions.map((m) => `
    <div class="card mission" data-run="${m.id}">
      <div class="row"><strong>Mission n°${m.id} <span class="muted small">(${esc(m.declencheur)})</span></strong>
      <span class="status-${esc(m.statut)}">${esc(labels[m.statut] || m.statut)}</span></div>
      <p class="muted small">${when(m.debut)} · ${m.etapes} étape(s) · ${Math.round((m.tokens_entree + m.tokens_sortie) / 1000)} k jetons</p>
      ${m.resume ? `<p class="small">${esc(m.resume.replace(/\*\*/g, "").slice(0, 180))}${m.resume.length > 180 ? "…" : ""}</p>` : ""}
      ${m.erreur ? `<p class="error small">${esc(m.erreur)}</p>` : ""}
    </div>`).join("") : `<p class="empty">Aucune mission pour l'instant.</p>`;
  $$("[data-run]").forEach((c) => c.addEventListener("click", () => showMission(c.dataset.run)));
}

async function showMission(id) {
  const run = await api(`/api/missions/${id}`);
  const agents = Object.fromEntries((await api("/api/agents")).map((a) => [a.key, a]));
  const steps = run.journal.map((s) => {
    const a = agents[s.agent] || { emoji: "•", nom: s.agent };
    const r = s.rapport || {};
    return `<div class="step"><strong>${esc(a.emoji)} ${esc(a.nom)}</strong> <span class="muted small">${s.duree_s ? `${s.duree_s} s` : ""}</span>
      <p class="small"><em>${esc(s.consigne)}</em></p>
      ${r.erreur ? `<p class="error">${esc(r.erreur)}</p>` : ""}
      ${r.synthese || r.resume ? `<div class="prose small">${rich(r.synthese || r.resume)}</div>` : ""}
      <details><summary class="small">Rapport complet</summary><pre>${esc(JSON.stringify(r, null, 2))}</pre></details></div>`;
  }).join("");
  openDialog(`<h2>Mission n°${run.id}</h2><p class="muted small">${when(run.debut)} → ${when(run.fin)}</p>${steps || "<p>Pas encore d'étape.</p>"}`);
}

// ------------------------------------------------------------------ démarrage
function bind() {
  $("#login-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    token = $("#login-token").value.trim();
    try {
      await api("/api/status");
      store.set("voiture-token", token);
      $("#login-error").hidden = true;
      go("accueil");
    } catch (err) {
      $("#login-error").textContent = err.message === "Non connecté" ? "Mot de passe incorrect." : err.message;
      $("#login-error").hidden = false;
    }
  });
  $$("#tabbar button").forEach((b) => b.addEventListener("click", () => go(b.dataset.tab)));
  $$("[data-go]").forEach((b) => b.addEventListener("click", () => {
    go(b.dataset.go);
    if (b.dataset.prefill) { $("#chat-input").value = b.dataset.prefill; $("#chat-input").focus(); }
  }));
  $$("[data-filter]").forEach((b) => b.addEventListener("click", () => { listingFilter = b.dataset.filter; loadListings(); }));
  $$("[data-pane]").forEach((b) => b.addEventListener("click", () => { pane = b.dataset.pane; loadListings(); }));
  $$("[data-dfilter]").forEach((b) => b.addEventListener("click", () => { dealerFilter = b.dataset.dfilter; loadDealers(); }));
  $("#btn-dealers").addEventListener("click", searchDealers);
  $("#dealer-form").addEventListener("submit", addDealer);
  $("#btn-mission").addEventListener("click", startMission);
  $("#btn-notif").addEventListener("click", enableNotifications);
  $("#chat-form").addEventListener("submit", sendChat);
  $("#chat-input").addEventListener("input", (e) => { e.target.style.height = ""; e.target.style.height = `${e.target.scrollHeight}px`; });
  $("#chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !/iPhone|iPad|Android/.test(navigator.userAgent)) { e.preventDefault(); $("#chat-form").requestSubmit(); }
  });
  $("#profile-form").addEventListener("submit", (e) => saveProfile(e).catch((err) => alert(err.message)));
  $("#settings-form").addEventListener("submit", (e) => saveSettings(e).catch((err) => alert(err.message)));
  $("#settings-form").seuil_notification.addEventListener("input", (e) => ($("#seuil-out").textContent = e.target.value));
  $("#btn-test-notif").addEventListener("click", async () => {
    try {
      const r = await api("/api/push/test", { method: "POST" });
      alert(`Envoyé : ${r.web_push} appareil(s) en Web Push${r.ntfy ? " + ntfy" : ""}.`);
    } catch (e) { alert(e.message); }
  });
  $("#memory-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    await api("/api/memory", { method: "POST", body: { note: $("#memory-input").value } });
    $("#memory-input").value = "";
    loadProfile();
  });
  $("#btn-logout").addEventListener("click", () => { store.del("voiture-token"); token = ""; showLogin(); });
  document.addEventListener("visibilitychange", () => { if (!document.hidden && token && currentTab !== "profil") go(currentTab); });
  window.addEventListener("hashchange", () => token && go(location.hash.slice(1)));
}

bind();
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
if (token) go(location.hash.slice(1) || "accueil"); else showLogin();
