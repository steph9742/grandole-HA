const VERSION = "1.0.0";

// ── SVG icons ────────────────────────────────────────────────────────────────

const ICON_BUS  = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17.5V5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v12a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5Z"/><path d="M4 11.5h16"/><path d="M12 3v8.5"/><circle cx="7.6" cy="15.2" r=".9" fill="currentColor" stroke="none"/><circle cx="16.4" cy="15.2" r=".9" fill="currentColor" stroke="none"/><path d="M6.2 19v1.2a.9.9 0 0 1-.9.9h-.4a.9.9 0 0 1-.9-.9V19"/><path d="M20 19v1.2a.9.9 0 0 1-.9.9h-.4a.9.9 0 0 1-.9-.9V19"/></svg>`;
const ICON_PERSON = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="7" r="4"/><path d="M4 21v-1a8 8 0 0116 0v1"/></svg>`;
const ICON_WARN = `<svg viewBox="0 0 16 16" fill="none"><path d="M8 2L14.5 14H1.5L8 2Z" stroke="currentColor" stroke-width="1.2"/><path d="M8 7v3" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"/><circle cx="8" cy="12" r=".6" fill="currentColor"/></svg>`;
const ICON_ACCESS = `<svg class="gd-icon-access" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><title>Accessible PMR</title><circle cx="13" cy="4.3" r="1.8"/><path d="M12.7 6.8v5.7h4.3l2.6 5.7"/><path d="M12.7 9.6h3.6"/><path d="M9.9 11.5a5.3 5.3 0 1 0 6.9 7"/></svg>`;
const ICON_TRAIN = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><rect x="5" y="3" width="14" height="14" rx="3"/><path d="M5 10h14"/><circle cx="9" cy="13.5" r=".9" fill="currentColor" stroke="none"/><circle cx="15" cy="13.5" r=".9" fill="currentColor" stroke="none"/><path d="M8 17l-2 4M16 17l2 4M7 21h10"/></svg>`;

function _iconWifi(color) {
  return `<svg class="gd-icon-wifi" style="color:${color}" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-linecap="round" stroke-width="1.7"><title>Temps réel</title><path d="M1.5 6a9 9 0 0113 0" opacity=".3"/><path d="M3.5 8.2a6 6 0 019 0" opacity=".6"/><path d="M5.8 10.4a3 3 0 014.4 0"/><circle cx="8" cy="13" r="1" fill="currentColor" stroke="none"/></svg>`;
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function _esc(str) {
  if (str == null) return "";
  return String(str).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function _sanitizeHtml(raw) {
  if (!raw) return "";
  return String(raw)
    .replace(/<script\b[^<]*(?:(?!<\/script>)<[^<]*)*<\/script\s*>/gi, "")
    .replace(/\s+on\w+\s*=\s*(?:"[^"]*"|'[^']*'|[^\s>]*)/gi, "")
    .replace(/href\s*=\s*(?:"javascript:[^"]*"|'javascript:[^']*')/gi, 'href="#"')
    .replace(/src\s*=\s*(?:"javascript:[^"]*"|'javascript:[^']*')/gi, "");
}

function _capitalize(str) {
  if (!str) return str;
  return String(str).replace(/(^|[ \t\-])([^\s\-])/g, (_, sep, char) => sep + char.toUpperCase());
}

function _hexToRgb(hex) {
  if (!hex) return "128,128,128";
  const h = String(hex).replace("#","");
  if (h.length < 6) return "128,128,128";
  return `${parseInt(h.slice(0,2),16)},${parseInt(h.slice(2,4),16)},${parseInt(h.slice(4,6),16)}`;
}

function _color(hex) {
  if (!hex) return "#888888";
  const h = String(hex).trim();
  return h.startsWith("#") ? h : "#" + h;
}

function _timeSince(isoDate) {
  if (!isoDate) return "";
  const diff = Math.round((Date.now() - new Date(isoDate).getTime()) / 1000);
  if (diff < 5)  return "à l'instant";
  if (diff < 60) return `il y a ${diff}s`;
  return `il y a ${Math.round(diff / 60)} min`;
}

function _haversine(lat1, lng1, lat2, lng2) {
  const R = 6371000;
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLng = (lng2 - lng1) * Math.PI / 180;
  const a = Math.sin(dLat/2)**2
    + Math.cos(lat1*Math.PI/180) * Math.cos(lat2*Math.PI/180) * Math.sin(dLng/2)**2;
  return Math.round(R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1-a)));
}

function _minutes(p) {
  return String(p.temps ?? "").replace(" min", "").trim();
}

function _retardBadge(p) {
  if (p.fiable === false || p.retard == null) return "";
  const r = Number(p.retard);
  if (Math.abs(r) < 60) return "";
  const m = Math.round(r / 60);
  const cls = r > 0 ? "gd-retard gd-retard--plus" : "gd-retard gd-retard--moins";
  const label = r > 0 ? `+${m} min` : `${m} min`;
  const title = r > 0 ? `Retard de ${m} min sur l'horaire ${_esc(p.heureTheorique ?? "")}` : `Avance de ${-m} min sur l'horaire ${_esc(p.heureTheorique ?? "")}`;
  return `<span class="${cls}" title="${title}">${label}</span>`;
}

function _isInfoOnly(m) {
  return m.type === "infotrafic" && m.gravite !== "WARN";
}

function _dateFr(iso, withTime = true) {
  if (!iso) return "";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return "";
  const date = d.toLocaleDateString("fr-FR", { day: "2-digit", month: "2-digit", year: "numeric" });
  if (!withTime) return date;
  return `${date} ${d.toLocaleTimeString("fr-FR", { hour: "2-digit", minute: "2-digit" })}`;
}

function _periode(m) {
  if (m.debut && m.fin) return `du ${_dateFr(m.debut)} au ${_dateFr(m.fin)}`;
  if (m.debut) return `à partir du ${_dateFr(m.debut)}`;
  if (m.fin) return `jusqu'au ${_dateFr(m.fin)}`;
  return "";
}

const ICON_INFO_SMALL = `<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round"><circle cx="8" cy="8" r="6.2"/><path d="M8 7v4M8 5.2h.01"/></svg>`;

// ── Styles ───────────────────────────────────────────────────────────────────

const STYLES = `
  :host {
    --gd-bg:     var(--ha-card-background, var(--card-background-color));
    --gd-row-bg: var(--secondary-background-color, rgba(128,128,128,0.06));
    --gd-border: var(--divider-color, rgba(0,0,0,0.12));
    --gd-r-lg:   var(--ha-card-border-radius, 14px);
    --gd-r-md:   10px;
    --gd-r-sm:   6px;
    --gd-txt:    var(--primary-text-color);
    --gd-txt-2:  var(--secondary-text-color);
    --gd-txt-3:  var(--disabled-text-color);
    --gd-warn:   var(--warning-color, #f59e0b);
    --gd-blue:   var(--info-color, #3b82f6);
    --gd-amber:  var(--warning-color, #f59e0b);
    font-size: 14px;
    display: block;
  }
  @supports (color: color-mix(in srgb, red 50%, blue)) {
    :host {
      --gd-txt-3:  color-mix(in srgb, var(--primary-text-color) 55%, transparent);
      --gd-row-bg: color-mix(in srgb, var(--primary-text-color) 5%, transparent);
    }
  }
  * { box-sizing: border-box; }
  .gd-card {
    background: var(--gd-bg);
    border: 0.5px solid var(--gd-border);
    border-radius: var(--gd-r-lg);
    overflow: hidden;
    font-family: var(--paper-font-body1_-_font-family, system-ui, sans-serif);
    box-shadow: var(--ha-card-box-shadow, none);
  }
  .gd-header { padding:10px 12px; display:flex; align-items:center; gap:8px; border-bottom:0.5px solid var(--gd-border); }
  .gd-header svg { width:18px; height:18px; color:var(--gd-txt-3); flex-shrink:0; }
  .gd-header-title { font-size:13px; font-weight:600; color:var(--gd-txt); flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .gd-header-upd { font-size:10px; color:var(--gd-txt-3); white-space:nowrap; }
  .gd-header-train { display:inline-flex; align-items:center; gap:3px; font-size:10px; color:var(--gd-txt-3); white-space:nowrap; }
  .gd-header-train svg { width:13px; height:13px; }
  .gd-next { margin:10px 10px 6px; border-radius:var(--gd-r-md); overflow:hidden; }
  .gd-next-body { padding:10px 12px 10px; display:flex; align-items:flex-start; justify-content:space-between; gap:8px; }
  .gd-next-left { display:flex; align-items:center; gap:6px; flex-wrap:wrap; flex:1; min-width:0; }
  .gd-next-dest { font-size:12px; color:var(--gd-txt-2); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .gd-next-time { display:flex; align-items:baseline; gap:2px; flex-shrink:0; }
  .gd-next-val { font-size:24px; font-weight:700; color:var(--gd-txt); line-height:1; }
  .gd-next-val--sm { font-size:17px; font-weight:700; color:var(--gd-txt); line-height:1; }
  .gd-next-unit { font-size:11px; color:var(--gd-txt-3); align-self:flex-end; padding-bottom:2px; }
  .gd-next-hour { font-size:10px; color:var(--gd-txt-3); text-align:right; padding:0 12px 6px; font-variant-numeric:tabular-nums; }
  .gd-badge { font-size:11px; font-weight:700; padding:2px 7px; border-radius:var(--gd-r-sm); line-height:1.4; white-space:nowrap; flex-shrink:0; box-shadow:0 0 0 1px color-mix(in srgb, var(--gd-txt) 20%, transparent); }
  .gd-icon-wifi { width:13px; height:13px; flex-shrink:0; }
  .gd-icon-access { width:12px; height:12px; color:var(--gd-blue); flex-shrink:0; }
  .gd-approx { font-size:11px; font-weight:700; color:var(--gd-amber); line-height:1; flex-shrink:0; }
  .gd-retard { font-size:9px; font-weight:700; padding:1px 5px; border-radius:99px; line-height:1.3; white-space:nowrap; flex-shrink:0; }
  .gd-retard--plus { color:#b45309; background:rgba(245,158,11,0.18); }
  .gd-retard--moins { color:#1d4ed8; background:rgba(59,130,246,0.15); }
  .gd-lines { padding:0 10px 10px; display:flex; flex-direction:column; gap:6px; }
  .gd-ligne { border-radius:var(--gd-r-md); overflow:hidden; border:0.5px solid var(--gd-border); }
  .gd-ligne-hd { padding:7px 10px; display:flex; align-items:center; gap:8px; background:var(--gd-row-bg); }
  .gd-ligne-dests { font-size:11px; color:var(--gd-txt-3); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .gd-dir { padding:0; }
  .gd-dir+.gd-dir { border-top:0.5px solid var(--gd-border); }
  .gd-pills { display:flex; gap:5px; flex-wrap:wrap; }
  .gd-pills-follow { padding:2px 10px 8px; }
  .gd-pill { display:inline-flex; align-items:center; gap:4px; padding:5px 9px; border-radius:99px; border:0.5px solid; }
  .gd-pill-time { display:flex; align-items:baseline; gap:2px; }
  .gd-pill-val { font-weight:600; color:var(--gd-txt); font-size:13px; font-variant-numeric:tabular-nums; }
  .gd-pill-unit { font-size:10px; color:var(--gd-txt-3); }
  .gd-pill-hhmm { font-weight:500; color:var(--gd-txt-2); font-size:12px; font-variant-numeric:tabular-nums; }
  .gd-pill-disruption { font-size:11px; font-weight:600; color:#b45309; font-style:italic; }
  .gd-alert { margin:0 10px 6px; padding:8px 10px; font-size:12px; background:rgba(245,158,11,0.10); border:0.5px solid rgba(245,158,11,0.40); border-left:3px solid #d97706; color:var(--gd-txt); display:flex; flex-direction:column; gap:5px; border-radius:var(--gd-r-md); min-width:0; overflow:hidden; }
  .gd-alert-row { display:flex; gap:6px; align-items:flex-start; line-height:1.35; min-width:0; }
  .gd-alert-row svg { width:13px; height:13px; flex-shrink:0; margin-top:1px; color:#d97706; }
  .gd-alert-badge { font-size:10px; font-weight:700; color:var(--gd-txt); background:rgba(245,158,11,0.22); padding:1px 6px; border-radius:99px; white-space:nowrap; flex-shrink:0; max-width:45%; overflow:hidden; text-overflow:ellipsis; }
  .gd-alert-txt { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; overflow-wrap:anywhere; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; }
  .gd-alert-more { font-size:10px; color:var(--gd-txt-3); font-style:italic; padding-left:19px; }
  .gd-alert--info { background:rgba(59,130,246,0.08); border-color:rgba(59,130,246,0.35); border-left-color:#2563eb; }
  .gd-alert--info .gd-alert-row svg { color:#2563eb; }
  .gd-alert--info .gd-alert-badge { background:rgba(59,130,246,0.18); }
  .gd-empty   { padding:20px 14px; font-size:13px; color:var(--gd-txt-3); text-align:center; }
  .gd-unavail { padding:14px; font-size:13px; color:var(--gd-txt-3); }
  .gd-theo { padding:0 12px 8px; font-size:10px; color:var(--gd-txt-3); font-style:italic; display:flex; align-items:center; gap:4px; }
  .gd-prox-stops { padding:10px 10px 10px; display:flex; flex-direction:column; gap:6px; }
  .gd-stop { border-radius:var(--gd-r-md); overflow:hidden; border:0.5px solid var(--gd-border); }
  .gd-stop-hd { padding:7px 10px; display:flex; align-items:center; gap:6px; background:var(--gd-row-bg); border-bottom:0.5px solid var(--gd-border); }
  .gd-stop-name { font-size:12px; font-weight:600; color:var(--gd-txt); flex:1; }
  .gd-stop-dist { font-size:10px; color:var(--gd-txt-3); white-space:nowrap; }
  .gd-stop-pmr { display:inline-flex; align-items:center; }
  .gd-stop-pmr svg { width:13px; height:13px; color:var(--gd-blue); }
  .gd-stop-row { display:flex; align-items:center; gap:8px; padding:6px 10px; border-top:0.5px solid var(--gd-border); }
  .gd-stop-dest { flex:1; font-size:12px; color:var(--gd-txt-2); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .gd-stop-time { font-size:13px; font-weight:600; color:var(--gd-txt); white-space:nowrap; font-variant-numeric:tabular-nums; }
  .gd-next-pos { display:flex; align-items:center; gap:5px; padding:3px 10px 6px; font-size:10px; color:var(--gd-txt-3); }
  .gd-next-pos-dot { width:6px; height:6px; border-radius:50%; flex-shrink:0; }
  .gd-pill-pos { width:5px; height:5px; border-radius:50%; flex-shrink:0; }
`;

// ── Card class ────────────────────────────────────────────────────────────────

class GrandoleCard extends HTMLElement {
  static getConfigElement() { return document.createElement("grandole-card-editor"); }
  static getStubConfig() {
    return { entity: "", mode: "lieu", max_passages: 3, show_traffic: "if_disrupted" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._refreshTimer = null;
  }

  setConfig(config) {
    this._config = {
      entity:          config.entity ?? "",
      messages_entity: config.messages_entity ?? "",
      person_entity:   config.person_entity ?? "",
      suivi_entities:  Array.isArray(config.suivi_entities)
                         ? config.suivi_entities
                         : (config.suivi_entity ? [config.suivi_entity] : []),
      mode:            config.mode ?? "lieu",
      max_passages:    Math.min(5, Math.max(1, config.max_passages ?? 3)),
      max_stops:       Math.min(10, Math.max(1, config.max_stops ?? 5)),
      show_traffic:    config.show_traffic ?? "if_disrupted",
      show_hour:       config.show_hour ?? true,
      lignes_filtre:   Array.isArray(config.lignes_filtre) ? config.lignes_filtre : [],
    };
    if (this._hass) this._render();
  }

  set hass(hass) { this._hass = hass; this._render(); }

  connectedCallback()    { this._refreshTimer = setInterval(() => this._render(), 15000); }
  disconnectedCallback() { clearInterval(this._refreshTimer); }
  getCardSize()          { return 3; }

  _render() {
    if (!this._config || !this._hass) return;
    let html;
    if (this._config.mode === "proximity") {
      html = this._config.person_entity
        ? this._renderPersonProximity()
        : this._renderProximity();
    } else {
      html = this._renderLieu();
    }
    const isDark = this._hass?.themes?.darkMode ?? false;
    const darkBg = isDark ? `<style>.gd-card{background:#0f1729!important}</style>` : "";
    this.shadowRoot.innerHTML = `<style>${STYLES}</style>${darkBg}${html}`;
  }

  // ── Header ────────────────────────────────────────────────────────────────

  _header(title, updated, icon = ICON_BUS, extra = "") {
    return `<div class="gd-header">
      ${icon}
      <span class="gd-header-title">${_esc(title)}</span>
      ${extra}
      <span class="gd-header-upd">màj ${_timeSince(updated)}</span>
    </div>`;
  }

  _trainHint(nomArret) {
    if (!/gare/i.test(String(nomArret ?? "")) || !/dole/i.test(String(nomArret ?? ""))) return "";
    return `<span class="gd-header-train" title="Correspondance avec les trains">${ICON_TRAIN}Trains</span>`;
  }

  // ── Position suivi ───────────────────────────────────────────────────────

  _posMap() {
    const entities = this._config.suivi_entities ?? [];
    if (!entities.length) return new Map();
    const map = new Map();
    for (const eid of entities) {
      const e = this._hass?.states[eid];
      for (const bus of e?.attributes?.buses ?? []) {
        if (bus.id == null) continue;
        const key = String(bus.id);
        const prev = map.get(key);
        if (!prev || (bus.dans_sec ?? Infinity) < (prev.dans_sec ?? Infinity)) {
          map.set(key, bus);
        }
      }
    }
    return map;
  }

  // ── Mode lieu ─────────────────────────────────────────────────────────────

  _renderLieu() {
    if (!this._config.entity) {
      return `<div class="gd-card"><div class="gd-empty">Sélectionnez une entité Grandole dans la configuration de la carte.</div></div>`;
    }
    const entity = this._hass.states[this._config.entity];
    if (!entity) return `<div class="gd-card"><div class="gd-unavail">Entité introuvable : ${_esc(this._config.entity)}</div></div>`;

    const attrs    = entity.attributes ?? {};
    const raw      = Array.isArray(attrs.passages) ? attrs.passages : [];
    const filtre   = this._config.lignes_filtre ?? [];
    const all      = filtre.length
      ? raw.filter(p => filtre.includes(String(p.numLignePublic ?? p.idLigne ?? "")))
      : raw;
    const rawTitle = attrs.nom_arret ?? attrs.friendly_name ?? entity.entity_id;
    const title    = _capitalize(rawTitle);

    return `<div class="gd-card">
      ${this._header(title, entity.last_updated, ICON_BUS, this._trainHint(rawTitle))}
      ${this._passagesInner(all, attrs.temps_reel)}
    </div>`;
  }

  _passagesInner(all, tempsReel = true) {
    const lineNums  = [...new Set(all.map(p => String(p.numLignePublic ?? p.idLigne ?? "")))].filter(Boolean);
    const alerts    = this._alerts(lineNums);
    const disrupted = alerts.length > 0;
    const banner    = this._shouldShowTraffic(disrupted) && disrupted ? this._alertBanner(alerts) : "";

    if (all.length === 0) {
      return `${banner}<div class="gd-empty">Aucun passage dans les 3 prochaines heures.</div>`;
    }

    const nextP = all.reduce((a, b) =>
      (a.tempsEnSeconde ?? 999999) <= (b.tempsEnSeconde ?? 999999) ? a : b
    );

    const byLigne = new Map();
    for (const p of all) {
      const k = p.idLigne ?? p.numLignePublic ?? "?";
      if (!byLigne.has(k)) byLigne.set(k, []);
      byLigne.get(k).push(p);
    }

    const posMap     = this._posMap();
    const ligneCards = [...byLigne.values()].map(lp => this._renderLigneCard(lp, nextP, posMap)).join("");
    const theo = tempsReel === false
      ? `<div class="gd-theo"><span class="gd-approx">~</span>Temps réel indisponible ou figé : horaires théoriques.</div>`
      : "";
    return `${banner}<div class="gd-lines">${ligneCards}</div>${theo}`;
  }

  _renderNextBanner(p, posMap = new Map()) {
    const bg  = _color(p.couleurFond);
    const fg  = _color(p.couleurTexte);
    const rgb = _hexToRgb(bg);
    const gpsIcon    = p.fiable === false ? `<span class="gd-approx" title="Horaire théorique">~</span>` : _iconWifi(bg);
    const accessIcon = p.accessibiliteVehicule == 1 ? ICON_ACCESS : "";

    const bus = posMap.get(String(p.numVehicule ?? ""));
    let posHtml = "";
    if (bus) {
      const dot = bus.statut === "a_quai" ? "#22c55e" : "#3b82f6";
      const label = bus.statut === "a_quai"
        ? `À quai : ${_esc(bus.prochain_arret ?? "")}`
        : bus.statut === "depart"
          ? `Au départ de ${_esc(bus.prochain_arret ?? "")}`
          : `${_esc(bus.arret_precedent ?? "")} → ${_esc(bus.prochain_arret ?? "")}`;
      posHtml = `<div class="gd-next-pos"><span class="gd-next-pos-dot" style="background:${dot}"></span>${label}</div>`;
    }
    const prec       = p.precisionDestination ? ` <span style="font-size:10px;opacity:.7">(${_esc(p.precisionDestination)})</span>` : "";
    let timeHtml;
    if (p.typeDeTemps === 0) {
      timeHtml = `<span class="gd-next-val">${_esc(_minutes(p))}</span><span class="gd-next-unit">min</span>`;
    } else if (p.typeDeTemps === 2) {
      timeHtml = `<span class="gd-next-val--sm" style="color:#b45309;font-style:italic">${_esc(p.temps ?? "?")}</span>`;
    } else {
      timeHtml = `<span class="gd-next-val--sm">${_esc(p.temps ?? "?")}</span>`;
    }
    const hour = this._config.show_hour && p.heure ? `<div class="gd-next-hour">${_esc(p.heure)}</div>` : "";
    return `<div class="gd-next" style="background:rgba(${rgb},0.12);border:1px solid rgba(${rgb},0.6)">
      <div class="gd-next-body">
        <div class="gd-next-left">
          <span class="gd-badge" style="background:${bg};color:${fg}">${_esc(p.numLignePublic ?? p.idLigne ?? "?")}</span>
          <span class="gd-next-dest">→ ${_esc(p.destination ?? "?")}${prec}</span>
          ${gpsIcon}${accessIcon}${_retardBadge(p)}
        </div>
        <div class="gd-next-time">${timeHtml}</div>
      </div>
      ${hour}
      ${posHtml}
    </div>`;
  }

  _renderLigneCard(lignePassages, nextP, posMap = new Map()) {
    const first = lignePassages[0];
    const bg  = _color(first.couleurFond);
    const fg  = _color(first.couleurTexte);
    const rgb = _hexToRgb(bg);

    const byDest = new Map();
    for (const p of lignePassages) {
      const d = p.destination ?? "?";
      if (!byDest.has(d)) byDest.set(d, []);
      byDest.get(d).push(p);
    }

    const destsLabel = _esc([...byDest.keys()].join(" · "));

    const dirs = [...byDest.entries()].map(([dest, dps], i) => {
      const borderStyle = i > 0 ? `border-color:rgba(${rgb},0.15)` : "";
      const banner = this._renderNextBanner(dps[0], posMap);
      const follow = dps.slice(1, this._config.max_passages);
      const pillsHtml = follow.length
        ? `<div class="gd-pills gd-pills-follow">${follow.map(p => this._renderPill(p, nextP, posMap)).join("")}</div>`
        : "";
      return `<div class="gd-dir" style="${borderStyle}">${banner}${pillsHtml}</div>`;
    }).join("");

    const modeIco = `<span style="width:13px;height:13px;display:inline-flex;opacity:.5;flex-shrink:0">${ICON_BUS}</span>`;
    return `<div class="gd-ligne" style="border:0.5px solid rgba(${rgb},0.30)">
      <div class="gd-ligne-hd" style="background:rgba(${rgb},0.10)">
        <span class="gd-badge" style="background:${bg};color:${fg}">${_esc(first.numLignePublic ?? first.idLigne ?? "?")}</span>
        ${modeIco}
        <span class="gd-ligne-dests">${destsLabel}</span>
      </div>
      ${dirs}
    </div>`;
  }

  _renderPill(p, nextP, posMap = new Map()) {
    const bg  = _color(p.couleurFond);
    const rgb = _hexToRgb(bg);
    const isNext = p.tempsEnSeconde === nextP.tempsEnSeconde
      && p.idLigne === nextP.idLigne
      && p.destination === nextP.destination;
    const bgA     = isNext ? "0.18" : "0.10";
    const borderA = isNext ? "0.50" : "0.32";
    const gpsIcon    = p.fiable === false ? `<span class="gd-approx" title="Horaire théorique">~</span>` : _iconWifi(bg);
    const accessIcon = p.accessibiliteVehicule == 1 ? ICON_ACCESS : "";

    const bus = posMap.get(String(p.numVehicule ?? ""));
    let posDot = "";
    if (bus) {
      const aQuai    = bus.statut === "a_quai";
      const dotColor = aQuai ? "#22c55e" : "#3b82f6";
      const dotTitle = aQuai ? "Bus à quai" : "Bus localisé, en circulation";
      posDot = `<span class="gd-pill-pos" style="background:${dotColor}" title="${dotTitle}"></span>`;
    }

    let timeHtml;
    if (p.typeDeTemps === 0) {
      timeHtml = `<span class="gd-pill-val">${_esc(_minutes(p))}</span><span class="gd-pill-unit">min</span>`;
    } else if (p.typeDeTemps === 2) {
      timeHtml = `<span class="gd-pill-disruption">${_esc(p.temps ?? "?")}</span>`;
    } else {
      timeHtml = `<span class="gd-pill-hhmm">${_esc(p.temps ?? "?")}</span>`;
    }
    const hour = this._config.show_hour && p.heure ? `<span class="gd-pill-hhmm" style="font-size:10px">${_esc(p.heure)}</span>` : "";
    return `<span class="gd-pill" style="background:rgba(${rgb},${bgA});border-color:rgba(${rgb},${borderA})" title="${_esc(p.destination ?? "")}${p.heure ? " à " + _esc(p.heure) : ""}">
      ${gpsIcon}
      <span class="gd-pill-time">${timeHtml}</span>
      ${hour}${accessIcon}${posDot}
    </span>`;
  }

  // ── Mode proximity (entité sensor) ────────────────────────────────────────

  _renderProximity() {
    const entity = this._hass.states[this._config.entity];
    if (!entity) return `<div class="gd-card"><div class="gd-unavail">Entité introuvable : ${_esc(this._config.entity)}</div></div>`;

    const attrs  = entity.attributes ?? {};
    const arrets   = (Array.isArray(attrs.arrets) ? attrs.arrets : []).slice(0, this._config.max_stops);
    const lineNums  = [...new Set(arrets.flatMap(a =>
      (Array.isArray(a.passages) ? a.passages : []).map(p => String(p.numLignePublic ?? p.idLigne ?? ""))
    ))].filter(Boolean);
    const alerts    = this._alerts(lineNums);
    const disrupted = alerts.length > 0;

    const stops = arrets.length
      ? arrets.map(a => this._renderStop(a)).join("")
      : `<div class="gd-empty">${attrs.person_state == null ? "Position de la personne indisponible." : "Aucun arrêt à moins de 1 km."}</div>`;

    return `<div class="gd-card">
      ${this._header("Arrêts à proximité", entity.last_updated)}
      ${this._shouldShowTraffic(disrupted) && disrupted ? this._alertBanner(alerts) : ""}
      <div class="gd-prox-stops">${stops}</div>
    </div>`;
  }

  // ── Mode proximity (entité personne) ─────────────────────────────────────

  _renderPersonProximity() {
    const personEntity = this._hass.states[this._config.person_entity];
    if (!personEntity) {
      return `<div class="gd-card"><div class="gd-unavail">Entité introuvable : ${_esc(this._config.person_entity)}</div></div>`;
    }

    const lat = personEntity.attributes.latitude;
    const lng = personEntity.attributes.longitude;
    if (!lat || !lng) {
      const name = personEntity.attributes.friendly_name ?? this._config.person_entity;
      return `<div class="gd-card">
        ${this._header(_esc(name), personEntity.last_updated, ICON_PERSON)}
        <div class="gd-empty">Position GPS non disponible pour cette personne.</div>
      </div>`;
    }

    const sensors = Object.entries(this._hass.states)
      .filter(([id, s]) => {
        if (!id.startsWith("sensor.grandole_")) return false;
        if (s.attributes?.grandole_mode !== "lieu") return false;
        const passages = s.attributes?.passages;
        return Array.isArray(passages) && passages.length > 0 && passages[0].latitude != null;
      })
      .map(([id, s]) => {
        const p0   = s.attributes.passages[0];
        const dist = _haversine(lat, lng, p0.latitude, p0.longitude);
        return { id, state: s, dist };
      })
      .sort((a, b) => a.dist - b.dist)
      .slice(0, this._config.max_stops);

    const personName = _capitalize(personEntity.attributes.friendly_name ?? this._config.person_entity);
    const lineNums   = [...new Set(sensors.flatMap(({ state }) =>
      (Array.isArray(state.attributes.passages) ? state.attributes.passages : [])
        .map(p => String(p.numLignePublic ?? p.idLigne ?? ""))
    ))].filter(Boolean);
    const alerts     = this._alerts(lineNums);
    const disrupted  = alerts.length > 0;

    if (sensors.length === 0) {
      return `<div class="gd-card">
        ${this._header(personName, personEntity.last_updated, ICON_PERSON)}
        <div class="gd-empty">Aucun capteur Grandole configuré ou aucun arrêt à proximité.</div>
      </div>`;
    }

    const stops = sensors.map(({ state, dist }) => {
      const passages = (Array.isArray(state.attributes.passages) ? state.attributes.passages : [])
        .slice(0, this._config.max_passages);
      const nom = _capitalize(state.attributes.nom_arret ?? state.attributes.friendly_name ?? "Arrêt");
      return this._renderStop({ nom, distance: dist, passages });
    }).join("");

    return `<div class="gd-card">
      ${this._header(personName, personEntity.last_updated, ICON_PERSON)}
      ${this._shouldShowTraffic(disrupted) && disrupted ? this._alertBanner(alerts) : ""}
      <div class="gd-prox-stops">${stops}</div>
    </div>`;
  }

  // ── Stop block (partagé proximity + person) ───────────────────────────────

  _renderStop(arret) {
    const allPassages = Array.isArray(arret.passages) ? arret.passages : [];
    const dist = arret.distance != null
      ? `<span class="gd-stop-dist">${Math.round(arret.distance)} m</span>` : "";
    const isPmr = allPassages.some(p => p.accessibiliteArret == 1)
      ? `<span class="gd-stop-pmr" title="Arrêt accessible PMR">${ICON_ACCESS}</span>` : "";

    const byLigne = new Map();
    for (const p of allPassages) {
      const k = p.idLigne ?? p.numLignePublic ?? "?";
      if (!byLigne.has(k)) byLigne.set(k, []);
      byLigne.get(k).push(p);
    }

    let rows = "";
    for (const lignePassages of byLigne.values()) {
      const byDest = new Map();
      for (const p of lignePassages) {
        const d = p.destination ?? "?";
        if (!byDest.has(d)) byDest.set(d, []);
        byDest.get(d).push(p);
      }
      for (const dPassages of byDest.values()) {
        const shown = dPassages.slice(0, this._config.max_passages);
        if (!shown.length) continue;
        const first = shown[0];
        const bg  = _color(first.couleurFond);
        const fg  = _color(first.couleurTexte);
        const gps = first.fiable === false
          ? `<span class="gd-approx">~</span>` : _iconWifi(bg);
        const times = shown.map(p => {
          if (p.typeDeTemps === 0) return `${_esc(_minutes(p))} min`;
          if (p.typeDeTemps === 2) return `<span class="gd-pill-disruption">${_esc(p.temps ?? "?")}</span>`;
          return _esc(p.temps ?? "?");
        }).join(" · ");
        rows += `<div class="gd-stop-row">
          <span class="gd-badge" style="background:${bg};color:${fg}">${_esc(first.numLignePublic ?? first.idLigne ?? "?")}</span>
          <span class="gd-stop-dest">${_esc(first.destination ?? "?")}</span>
          ${gps}
          <span class="gd-stop-time">${times}</span>
        </div>`;
      }
    }

    return `<div class="gd-stop">
      <div class="gd-stop-hd">
        <span class="gd-stop-name">${_esc(_capitalize(arret.nom ?? "Arrêt"))}</span>
        ${this._trainHint(arret.nom)}
        ${isPmr}
        ${dist}
      </div>
      ${rows || `<div class="gd-empty" style="padding:10px">Aucun passage.</div>`}
    </div>`;
  }

  // ── Shared ────────────────────────────────────────────────────────────────

  _alertBanner(alerts) {
    const rows = alerts.slice(0, 3).map(m => {
      let titre = m.titre ? _esc(m.titre) : "";
      if (!titre) {
        const raw = String(m.corps ?? m.texte ?? m.message ?? "");
        titre = _esc(raw.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim().slice(0, 120));
      }
      const badge = Array.isArray(m.lignes) && m.lignes.length
        ? `<span class="gd-alert-badge" title="${m.lignes.map(l => _esc(String(l))).join(", ")}">${
            m.lignes.slice(0, 4).map(l => _esc(String(l))).join(" · ")
          }${m.lignes.length > 4 ? ` +${m.lignes.length - 4}` : ""}</span>`
        : "";
      const icon = _isInfoOnly(m) ? ICON_INFO_SMALL : ICON_WARN;
      const avenir = m.etat === "a_venir" ? `<span class="gd-alert-badge">À venir</span>` : "";
      return `<div class="gd-alert-row">${icon}${badge}${avenir}<span class="gd-alert-txt">${titre}</span></div>`;
    }).join("");
    const rest = alerts.length - 3;
    const more = rest > 0
      ? `<div class="gd-alert-more">+${rest} autre${rest > 1 ? "s" : ""} message${rest > 1 ? "s" : ""}</div>`
      : "";
    const infoOnly = alerts.every(_isInfoOnly);
    return `<div class="gd-alert${infoOnly ? " gd-alert--info" : ""}">${rows}${more}</div>`;
  }

  _alerts(lineFilter = null) {
    const e = this._config.messages_entity ? this._hass.states[this._config.messages_entity] : null;
    const msgs = e?.attributes?.messages ?? [];
    if (!lineFilter || lineFilter.length === 0) return msgs;
    return msgs.filter(m => {
      const mLines = Array.isArray(m.lignes) ? m.lignes.map(String) : [];
      return mLines.some(l => lineFilter.includes(l));
    });
  }

  _shouldShowTraffic(disrupted) {
    const m = this._config.show_traffic;
    return m === "always" || (m === "if_disrupted" && disrupted);
  }

}

// ── Recherche card ────────────────────────────────────────────────────────────

const ICON_SEARCH = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="6.5"/><path d="M20 20l-4.2-4.2"/></svg>`;
const ICON_CLEAR  = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg>`;

const RECHERCHE_STYLES = `
  .gd-search-hd { padding:8px 10px; display:flex; align-items:center; gap:8px; border-bottom:0.5px solid var(--gd-border); }
  .gd-search-hd > svg { width:18px; height:18px; color:var(--gd-txt-3); flex-shrink:0; }
  .gd-search-in { flex:1; min-width:0; border:none; outline:none; background:transparent; color:var(--gd-txt); font:inherit; font-size:14px; padding:4px 0; }
  .gd-search-in::placeholder { color:var(--gd-txt-3); }
  .gd-search-clear { display:none; width:22px; height:22px; border:none; background:var(--gd-row-bg); border-radius:50%; color:var(--gd-txt-2); cursor:pointer; padding:4px; flex-shrink:0; }
  .gd-search-clear svg { width:100%; height:100%; display:block; }
  .gd-search-clear.on { display:block; }
  .gd-sugg { display:none; max-height:220px; overflow-y:auto; border-bottom:0.5px solid var(--gd-border); }
  .gd-sugg.on { display:block; }
  .gd-sugg-row { display:flex; align-items:center; gap:8px; padding:8px 12px; font-size:13px; color:var(--gd-txt); cursor:pointer; border-bottom:0.5px solid var(--gd-border); }
  .gd-sugg-row:last-child { border-bottom:none; }
  .gd-sugg-row:hover, .gd-sugg-row.hl { background:var(--gd-row-bg); }
  .gd-sugg-row svg { width:14px; height:14px; color:var(--gd-txt-3); flex-shrink:0; }
  .gd-sugg-name { flex:1; min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .gd-sugg-meta { font-size:10px; color:var(--gd-txt-3); white-space:nowrap; }
  .gd-rs-title { padding:8px 12px 2px; display:flex; align-items:baseline; gap:8px; }
  .gd-rs-name { font-size:13px; font-weight:600; color:var(--gd-txt); flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .gd-rs-err { padding:12px 14px; font-size:12px; color:#dc2626; }
`;

class GrandoleRechercheCard extends GrandoleCard {
  static getConfigElement() { return document.createElement("grandole-recherche-card-editor"); }
  static getStubConfig() {
    return { nb_passages: 3, refresh: 30, show_traffic: "if_disrupted" };
  }

  constructor() {
    super();
    this._arret = "";
    this._data = null;
    this._loadedAt = null;
    this._error = "";
    this._loading = false;
    this._sugg = [];
    this._hl = -1;
    this._debounce = null;
    this._shellBuilt = false;
    this._restored = false;
  }

  setConfig(config) {
    this._config = {
      messages_entity: config.messages_entity ?? "",
      suivi_entities:  Array.isArray(config.suivi_entities) ? config.suivi_entities : [],
      nb_passages:     Math.min(5, Math.max(1, Number(config.nb_passages ?? 3))),
      refresh:         Math.min(300, Math.max(10, Number(config.refresh ?? 30))),
      show_traffic:    config.show_traffic ?? "if_disrupted",
      show_hour:       config.show_hour ?? true,
      arret:           config.arret ?? "",
      placeholder:     config.placeholder ?? "Rechercher un arrêt…",
      remember:        config.remember ?? true,
      lignes_filtre:   [],
      max_passages:    5,
    };
    this._shellBuilt = false;
    this._restartTimer();
    if (this._hass) this._render();
  }

  connectedCallback()    { this._restartTimer(); }
  disconnectedCallback() { clearInterval(this._refreshTimer); this._refreshTimer = null; }
  getCardSize()          { return 4; }

  _restartTimer() {
    clearInterval(this._refreshTimer);
    const ms = (this._config?.refresh ?? 30) * 1000;
    this._refreshTimer = setInterval(() => {
      if (this._arret) this._loadHoraires();
      else this._renderResults();
    }, ms);
  }

  _storageKey() { return "grandole-recherche-last"; }

  _render() {
    if (!this._config || !this._hass) return;
    if (!this._shellBuilt) this._buildShell();
    if (!this._restored) {
      this._restored = true;
      let initial = this._config.arret;
      if (!initial && this._config.remember) {
        try { initial = localStorage.getItem(this._storageKey()) || ""; } catch (e) { initial = ""; }
      }
      if (initial) this._select(initial, false);
    }
    this._renderResults();
  }

  _buildShell() {
    const isDark = this._hass?.themes?.darkMode ?? false;
    const darkBg = isDark ? `<style>.gd-card{background:#0f1729!important}</style>` : "";
    this.shadowRoot.innerHTML = `<style>${STYLES}${RECHERCHE_STYLES}</style>${darkBg}
    <div class="gd-card">
      <div class="gd-search-hd">
        ${ICON_SEARCH}
        <input class="gd-search-in" type="text" autocomplete="off" spellcheck="false"
               placeholder="${_esc(this._config.placeholder)}" value="${_esc(this._arret)}">
        <button class="gd-search-clear${this._arret ? " on" : ""}" title="Effacer">${ICON_CLEAR}</button>
      </div>
      <div class="gd-sugg"></div>
      <div class="gd-results"></div>
    </div>`;
    this._shellBuilt = true;

    const input = this.shadowRoot.querySelector(".gd-search-in");
    const clear = this.shadowRoot.querySelector(".gd-search-clear");
    const sugg  = this.shadowRoot.querySelector(".gd-sugg");

    input.addEventListener("input", () => {
      clear.classList.toggle("on", input.value.length > 0);
      clearTimeout(this._debounce);
      const q = input.value.trim();
      if (q.length < 2) { this._sugg = []; this._renderSugg(); return; }
      this._debounce = setTimeout(() => this._search(q), 300);
    });
    input.addEventListener("keydown", e => {
      if (e.key === "ArrowDown") { e.preventDefault(); this._hl = Math.min(this._sugg.length - 1, this._hl + 1); this._renderSugg(); }
      else if (e.key === "ArrowUp") { e.preventDefault(); this._hl = Math.max(-1, this._hl - 1); this._renderSugg(); }
      else if (e.key === "Enter") {
        e.preventDefault();
        const pick = this._sugg[this._hl >= 0 ? this._hl : 0];
        if (pick) this._select(pick.nom);
        else if (input.value.trim()) this._select(input.value.trim());
      }
      else if (e.key === "Escape") { this._sugg = []; this._renderSugg(); }
    });
    input.addEventListener("focus", () => { if (this._sugg.length) sugg.classList.add("on"); });
    clear.addEventListener("click", () => {
      input.value = ""; clear.classList.remove("on");
      this._sugg = []; this._renderSugg();
      this._arret = ""; this._data = null; this._error = ""; this._loadedAt = null;
      try { if (this._config.remember) localStorage.removeItem(this._storageKey()); } catch (e) {}
      this._renderResults();
      input.focus();
    });
    sugg.addEventListener("click", e => {
      const row = e.target.closest(".gd-sugg-row");
      if (row?.dataset.nom) this._select(row.dataset.nom);
    });
  }

  async _callService(service, data) {
    const res = await this._hass.callWS({
      type: "call_service", domain: "grandole", service,
      service_data: data, return_response: true,
    });
    return res?.response ?? res;
  }

  async _search(q) {
    try {
      const resp = await this._callService("chercher_arret", { recherche: q, limite: 8 });
      const input = this.shadowRoot.querySelector(".gd-search-in");
      if (input && input.value.trim() !== q) return;
      this._sugg = Array.isArray(resp?.arrets) ? resp.arrets : [];
      this._hl = -1;
      this._renderSugg();
    } catch (err) {
      this._sugg = [];
      this._renderSugg();
      this._error = `Recherche impossible : ${err?.message ?? err}`;
      this._renderResults();
    }
  }

  _renderSugg() {
    const sugg = this.shadowRoot.querySelector(".gd-sugg");
    if (!sugg) return;
    if (!this._sugg.length) { sugg.classList.remove("on"); sugg.innerHTML = ""; return; }
    sugg.innerHTML = this._sugg.map((a, i) => {
      const lignes = Array.isArray(a.lignes) ? a.lignes.slice(0, 5).join(" · ") : "";
      const meta = [
        lignes,
        a.quais > 1 ? `${a.quais} quais` : "",
        a.accessible ? "PMR" : "",
      ].filter(Boolean).join(" · ");
      return `<div class="gd-sugg-row${i === this._hl ? " hl" : ""}" data-nom="${_esc(a.nom)}">
        ${ICON_BUS}<span class="gd-sugg-name">${_esc(a.nom)}</span>
        ${meta ? `<span class="gd-sugg-meta">${_esc(meta)}</span>` : ""}
      </div>`;
    }).join("");
    sugg.classList.add("on");
  }

  _select(nom, persist = true) {
    this._arret = nom;
    this._sugg = []; this._hl = -1;
    this._renderSugg();
    const input = this.shadowRoot.querySelector(".gd-search-in");
    const clear = this.shadowRoot.querySelector(".gd-search-clear");
    if (input) { input.value = nom; input.blur(); }
    if (clear) clear.classList.add("on");
    if (persist && this._config.remember) {
      try { localStorage.setItem(this._storageKey(), nom); } catch (e) {}
    }
    this._data = null; this._error = ""; this._loadedAt = null;
    this._renderResults();
    this._loadHoraires();
  }

  async _loadHoraires() {
    if (!this._arret || this._loading || !this._hass) return;
    this._loading = true;
    const wanted = this._arret;
    try {
      const resp = await this._callService("get_horaires", { nom: wanted, nb: this._config.nb_passages });
      if (this._arret !== wanted) return;
      this._data = resp;
      this._error = "";
      this._loadedAt = new Date().toISOString();
    } catch (err) {
      if (this._arret !== wanted) return;
      this._error = `Horaires indisponibles : ${err?.message ?? err}`;
    } finally {
      this._loading = false;
      this._renderResults();
    }
  }

  _renderResults() {
    const box = this.shadowRoot.querySelector(".gd-results");
    if (!box) return;
    if (!this._arret) {
      box.innerHTML = `<div class="gd-empty">Tapez le nom d'un arrêt pour afficher ses prochains passages.</div>`;
      return;
    }
    if (this._error && !this._data) {
      box.innerHTML = `<div class="gd-rs-err">${_esc(this._error)}</div>`;
      return;
    }
    if (!this._data) {
      box.innerHTML = `<div class="gd-empty">Chargement des horaires…</div>`;
      return;
    }
    const all = Array.isArray(this._data.passages) ? this._data.passages : [];
    const nom = _capitalize(this._data.nom ?? this._arret);
    box.innerHTML = `
      <div class="gd-rs-title">
        <span class="gd-rs-name">${_esc(nom)}</span>
        ${this._trainHint(nom)}
        <span class="gd-header-upd">màj ${_timeSince(this._loadedAt)}</span>
      </div>
      ${this._passagesInner(all, this._data.temps_reel)}`;
  }
}

// ── Etat card ─────────────────────────────────────────────────────────────────

const ETAT_SEV = { 0:0, 1:1, 2:2, 3:-1, 4:3, 5:4, 6:5 };
const ETAT_DOT = { 0:"#9e9e9e", 1:"#22c55e", 2:"#3b82f6", 3:"#9e9e9e", 4:"#9e9e9e", 5:"#f97316", 6:"#ef4444" };
const ETAT_COL = { 0:"#757575", 1:"#16a34a", 2:"#2563eb", 3:"#757575", 4:"#616161", 5:"#ea580c", 6:"#dc2626" };
const _isDisrupted = (etat) => (etat ?? 1) >= 5;

const ICON_CHECK = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6L9 17l-5-5"/></svg>`;
const ICON_INFO  = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>`;

const ETAT_STYLES = `
  :host {
    --gd-bg:     var(--ha-card-background, var(--card-background-color));
    --gd-border: var(--divider-color, rgba(0,0,0,0.12));
    --gd-r-lg:   var(--ha-card-border-radius, 14px);
    --gd-r-md:   10px;
    --gd-r-sm:   6px;
    --gd-txt:    var(--primary-text-color);
    --gd-txt-2:  var(--secondary-text-color);
    --gd-txt-3:  var(--disabled-text-color);
    --gd-blue:   var(--info-color, #3b82f6);
    font-size: 14px; display: block;
  }
  @supports (color: color-mix(in srgb, red 50%, blue)) {
    :host { --gd-txt-3: color-mix(in srgb, var(--primary-text-color) 55%, transparent); }
  }
  * { box-sizing: border-box; }
  .gd-card { background:var(--gd-bg); border:0.5px solid var(--gd-border); border-radius:var(--gd-r-lg); overflow:hidden; font-family:var(--paper-font-body1_-_font-family,system-ui,sans-serif); box-shadow:var(--ha-card-box-shadow,none); }
  .gd-header { padding:10px 12px; display:flex; align-items:center; gap:8px; border-bottom:0.5px solid var(--gd-border); }
  .gd-header svg { width:18px; height:18px; flex-shrink:0; }
  .gd-header-title { font-size:13px; font-weight:600; color:var(--gd-txt); flex:1; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .gd-header-upd { font-size:10px; color:var(--gd-txt-3); white-space:nowrap; }
  .gd-normal-banner { display:flex; align-items:center; gap:10px; padding:12px 14px; background:rgba(34,197,94,0.08); border-bottom:0.5px solid rgba(34,197,94,0.20); }
  .gd-normal-banner svg { width:20px; height:20px; color:#22c55e; flex-shrink:0; }
  .gd-normal-txt { font-size:13px; font-weight:600; color:#16a34a; }
  .gd-normal-sub { font-size:11px; color:var(--gd-txt-3); margin-top:1px; }
  .gd-filters { padding:7px 10px; display:flex; flex-wrap:wrap; gap:5px; border-bottom:0.5px solid var(--gd-border); }
  .gd-chip { font-size:11px; font-weight:500; padding:3px 9px; border-radius:99px; border:0.5px solid var(--gd-border); background:transparent; color:var(--gd-txt-2); cursor:pointer; white-space:nowrap; font-family:inherit; display:inline-flex; align-items:center; gap:5px; }
  .gd-chip.active { color:var(--gd-txt); background:var(--secondary-background-color,rgba(128,128,128,0.12)); border-color:var(--gd-txt-3); font-weight:600; }
  .gd-chip-dot { width:7px; height:7px; border-radius:50%; flex-shrink:0; }
  .gd-section { font-size:10px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; color:var(--gd-txt-3); padding:8px 12px 4px; border-top:0.5px solid var(--gd-border); }
  .gd-section:first-of-type { border-top:none; }
  .gd-messages { padding:4px 10px 8px; display:flex; flex-direction:column; gap:6px; }
  .gd-msg { padding:8px 10px; border-radius:var(--gd-r-md); background:rgba(245,158,11,0.08); border:0.5px solid rgba(245,158,11,0.22); cursor:default; }
  .gd-msg--info { background:rgba(59,130,246,0.07); border-color:rgba(59,130,246,0.22); }
  .gd-msg-head { display:flex; align-items:flex-start; gap:8px; }
  .gd-msg-head svg { width:13px; height:13px; flex-shrink:0; margin-top:2px; color:#b45309; }
  .gd-msg--info .gd-msg-head svg { color:#2563eb; }
  .gd-msg-tags { display:flex; flex-wrap:wrap; gap:4px; margin-top:4px; }
  .gd-msg-tag { font-size:9px; font-weight:600; padding:1px 6px; border-radius:99px; background:var(--secondary-background-color,rgba(128,128,128,0.12)); color:var(--gd-txt-2); white-space:nowrap; }
  .gd-msg-tag--avenir { background:rgba(59,130,246,0.15); color:#1d4ed8; }
  .gd-msg-periode { font-size:10px; color:var(--gd-txt-3); margin-top:3px; }
  .gd-msg-meta { flex:1; min-width:0; }
  .gd-msg-titre { font-size:12px; font-weight:600; color:var(--gd-txt); }
  .gd-msg-lignes { font-size:10px; color:var(--gd-txt-3); margin-top:2px; }
  .gd-msg-corps { font-size:11px; color:var(--gd-txt-2); margin-top:6px; line-height:1.5; }
  .gd-msg-corps p { margin:0 0 4px; }
  .gd-msg-corps strong { color:var(--gd-txt); }
  .gd-msg-corps a { color:var(--gd-blue,#3b82f6); }
  .gd-msg-corps.clamp { max-height:5em; overflow:hidden; position:relative; }
  .gd-msg-corps.clamp::after { content:""; position:absolute; bottom:0; left:0; right:0; height:2.2em; background:linear-gradient(transparent, var(--gd-bg,#fff)); pointer-events:none; }
  .gd-msg-toggle { font-size:10px; color:var(--gd-blue); margin-top:4px; cursor:pointer; user-select:none; }
  .gd-lignes { padding:4px 10px 6px; }
  .gd-ligne-row { display:flex; align-items:center; gap:8px; padding:6px 0; border-bottom:0.5px solid var(--gd-border); }
  .gd-ligne-row:last-child { border-bottom:none; }
  .gd-dot { width:8px; height:8px; border-radius:50%; flex-shrink:0; }
  .gd-badge { font-size:11px; font-weight:700; padding:2px 7px; border-radius:var(--gd-r-sm); line-height:1.4; white-space:nowrap; flex-shrink:0; min-width:28px; text-align:center; box-shadow:0 0 0 1px color-mix(in srgb, var(--gd-txt) 20%, transparent); }
  .gd-ligne-meta { flex:1; min-width:0; }
  .gd-ligne-nom { font-size:12px; color:var(--gd-txt-2); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
  .gd-ligne-sub { font-size:10px; color:var(--gd-txt-3); overflow:hidden; text-overflow:ellipsis; white-space:nowrap; margin-top:1px; }
  .gd-etat-lbl { font-size:10px; font-weight:600; white-space:nowrap; padding:2px 6px; border-radius:4px; }
  .gd-empty { padding:16px 12px; font-size:13px; color:var(--gd-txt-3); text-align:center; }
`;

function _ligneSub(l) {
  const parts = [];
  if (l.etat === 3) {
    parts.push(l.prochain_depart ? `Prochain départ à ${l.prochain_depart}` : (l.courses_jour ? "Service terminé" : "Pas de service aujourd'hui"));
    if (l.infotrafic_a_venir) parts.push(`${l.infotrafic_a_venir} info${l.infotrafic_a_venir > 1 ? "s" : ""} trafic à venir`);
    return parts.join(" · ");
  }
  if (l.infotrafic_en_cours) parts.push(`${l.infotrafic_en_cours} info${l.infotrafic_en_cours > 1 ? "s" : ""} trafic`);
  if (l.infotrafic_a_venir) parts.push(`${l.infotrafic_a_venir} à venir`);
  if (l.courses_en_cours) parts.push(`${l.courses_en_cours} course${l.courses_en_cours > 1 ? "s" : ""} en cours`);
  if (l.vehicules_localises) parts.push(`${l.vehicules_localises} bus localisé${l.vehicules_localises > 1 ? "s" : ""}`);
  if (l.retard_max != null && l.retard_max >= 60) parts.push(`retard max ${Math.round(l.retard_max / 60)} min`);
  if (l.courses_annulees) parts.push(`${l.courses_annulees} course${l.courses_annulees > 1 ? "s" : ""} annulée${l.courses_annulees > 1 ? "s" : ""}`);
  if (l.arrets_non_desservis) parts.push(`${l.arrets_non_desservis} arrêt${l.arrets_non_desservis > 1 ? "s" : ""} non desservi${l.arrets_non_desservis > 1 ? "s" : ""}`);
  if (!parts.length && l.prochain_depart) parts.push(`Prochain départ à ${l.prochain_depart}`);
  return parts.join(" · ");
}

class GrandoleEtatCard extends HTMLElement {
  static getConfigElement() { return document.createElement("grandole-etat-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.grandole_etat_lignes", messages_entity: "sensor.grandole_messages" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._filter = "disrupted";
    this._expandedMsgs = new Set();
    this._refreshTimer = null;
  }

  setConfig(config) {
    this._config = {
      entity:          config.entity ?? "sensor.grandole_etat_lignes",
      messages_entity: config.messages_entity ?? "",
      hide_inactive:   config.hide_inactive ?? false,
    };
    if (this._hass) this._render();
  }

  set hass(hass) { this._hass = hass; this._render(); }
  connectedCallback()    { this._refreshTimer = setInterval(() => this._render(), 30000); }
  disconnectedCallback() { clearInterval(this._refreshTimer); }
  getCardSize()          { return 4; }

  _render() {
    if (!this._config || !this._hass) return;

    const etatEntity = this._hass.states[this._config.entity];
    if (!etatEntity) {
      this.shadowRoot.innerHTML = `<style>${ETAT_STYLES}</style><div class="gd-card"><div class="gd-empty">Entité introuvable : ${_esc(this._config.entity)}</div></div>`;
      return;
    }

    const lignes    = etatEntity.attributes?.lignes ?? [];
    const msgEntity = this._config.messages_entity ? this._hass.states[this._config.messages_entity] : null;
    const messages  = msgEntity?.attributes?.messages ?? [];
    const disrupted = lignes.filter(l => _isDisrupted(l.etat));
    const active    = lignes.filter(l => (l.etat ?? 1) !== 3);
    const infos     = lignes.filter(l => (l.etat ?? 1) === 2);
    const planned   = lignes.filter(l => (l.etat ?? 1) === 4);
    const nbDisr    = disrupted.length;
    const nbActive  = active.length;
    const nbInfo    = infos.length;
    const nbPlan    = planned.length;
    const vehicules = lignes.reduce((s, l) => s + (l.vehicules_localises ?? 0), 0);

    if (nbDisr === 0 && this._filter === "disrupted") this._filter = "all";
    if (nbInfo === 0 && this._filter === "info") this._filter = "all";
    if (nbPlan === 0 && this._filter === "planned") this._filter = "all";

    let shownLignes, shownMsgs;
    if (this._filter === "all") {
      shownLignes = [...lignes].sort((a, b) => {
        const sa = ETAT_SEV[a.etat ?? 1] ?? 0;
        const sb = ETAT_SEV[b.etat ?? 1] ?? 0;
        if (sa !== sb) return sb - sa;
        return 0;
      });
      if (this._config.hide_inactive) shownLignes = shownLignes.filter(l => (l.etat ?? 1) !== 3);
      shownMsgs = messages;
    } else if (this._filter === "disrupted") {
      shownLignes = disrupted;
      const nums  = new Set(disrupted.map(l => String(l.num ?? "")));
      shownMsgs   = messages.filter(m => (m.lignes ?? []).some(l => nums.has(String(l))));
    } else if (this._filter === "active") {
      shownLignes = active;
      shownMsgs   = messages;
    } else if (this._filter === "info" || this._filter === "planned") {
      shownLignes = this._filter === "info" ? infos : planned;
      const nums  = new Set(shownLignes.map(l => String(l.num ?? "")));
      shownMsgs   = messages.filter(m => (m.lignes ?? []).some(l => nums.has(String(l))));
    } else {
      shownLignes = lignes.filter(l => String(l.num) === this._filter);
      shownMsgs   = messages.filter(m => (m.lignes ?? []).map(String).includes(this._filter));
    }

    const chips = [{ k: "all", label: `Toutes (${lignes.length})` }];
    if (nbActive > 0 && nbActive < lignes.length) chips.push({ k: "active", label: `En service (${nbActive})`, dot: ETAT_DOT[1] });
    if (nbInfo > 0) chips.push({ k: "info", label: `Infos (${nbInfo})`, dot: ETAT_DOT[2] });
    if (nbPlan > 0) chips.push({ k: "planned", label: `Prévues (${nbPlan})`, dot: ETAT_DOT[4] });
    if (nbDisr > 0) {
      chips.unshift({ k: "disrupted", label: `⚠ Perturbées (${nbDisr})` });
      disrupted.slice(0, 8).forEach(l => chips.push({
        k: String(l.num ?? ""), label: String(l.num ?? "?"),
        dot: ETAT_DOT[l.etat ?? 1] ?? "#888",
      }));
    }
    const chipsHtml = chips.map(c =>
      `<button class="gd-chip${this._filter === c.k ? " active" : ""}" data-filter="${_esc(c.k)}">${
        c.dot ? `<span class="gd-chip-dot" style="background:${c.dot}"></span>` : ""
      }${_esc(c.label)}</button>`
    ).join("");

    const normalSub = nbActive > 0
      ? `${nbActive} ligne${nbActive > 1 ? "s" : ""} en service${vehicules ? ` · ${vehicules} bus localisé${vehicules > 1 ? "s" : ""}` : ""}`
      : "Aucune ligne en service actuellement";
    const normalBanner = nbDisr === 0
      ? `<div class="gd-normal-banner">${ICON_CHECK}
           <div>
             <div class="gd-normal-txt">${nbInfo > 0 || nbPlan > 0 ? "Aucune perturbation en cours" : nbActive > 0 ? "Tout est normal" : "Réseau au repos"}</div>
             <div class="gd-normal-sub">${normalSub}</div>
           </div>
         </div>`
      : "";

    let msgsHtml = "";
    if (shownMsgs.length) {
      const items = shownMsgs.map((m, i) => {
        const ls = (Array.isArray(m.lignes) ? m.lignes : [])
          .map(l => _esc(String(l))).join(" · ");
        const corps = m.corps ?? m.texte ?? m.description ?? "";
        const expanded = this._expandedMsgs.has(i);
        const corpsHtml = corps
          ? `<div class="gd-msg-corps${expanded ? "" : " clamp"}">${_sanitizeHtml(corps)}</div>
             <div class="gd-msg-toggle" data-idx="${i}">${expanded ? "▲ Moins" : "▼ Voir plus"}</div>`
          : "";
        const tags = [
          ...(Array.isArray(m.causes) ? m.causes : []).map(c => `<span class="gd-msg-tag">${_esc(c)}</span>`),
          m.etat === "a_venir" ? `<span class="gd-msg-tag gd-msg-tag--avenir">À venir</span>` : "",
          m.type === "annulation" ? `<span class="gd-msg-tag">Temps réel</span>` : "",
          m.type === "retard" ? `<span class="gd-msg-tag">Temps réel</span>` : "",
          m.type === "arret_non_desservi" ? `<span class="gd-msg-tag">Temps réel</span>` : "",
        ].filter(Boolean).join("");
        const periode = _periode(m);
        const info = _isInfoOnly(m);
        return `<div class="gd-msg${info ? " gd-msg--info" : ""}">
          <div class="gd-msg-head">${info ? ICON_INFO_SMALL : ICON_WARN}
            <div class="gd-msg-meta">
              <div class="gd-msg-titre">${_esc(m.titre ?? "Perturbation")}</div>
              ${ls ? `<div class="gd-msg-lignes">Ligne${ls.includes("·") ? "s" : ""} ${ls}${m.sens && m.sens !== "Tous les sens" ? ` · ${_esc(m.sens)}` : ""}</div>` : ""}
              ${tags ? `<div class="gd-msg-tags">${tags}</div>` : ""}
              ${periode ? `<div class="gd-msg-periode">${_esc(periode)}${m.mise_a_jour ? ` · ${_esc(m.mise_a_jour)}` : ""}</div>` : ""}
            </div>
          </div>
          ${corpsHtml}
        </div>`;
      }).join("");
      msgsHtml = `<div class="gd-section">Messages (${shownMsgs.length})</div><div class="gd-messages">${items}</div>`;
    }

    const lignesHtml = shownLignes.length
      ? shownLignes.map(l => {
          const etat = l.etat ?? 1;
          const dot  = ETAT_DOT[etat] ?? "#888";
          const col  = ETAT_COL[etat] ?? "#888";
          const rgb  = _hexToRgb(dot);
          const bg   = _color(l.couleur_fond);
          const fg   = _color(l.couleur_texte);
          const sub  = _ligneSub(l);
          const dim  = etat === 3 ? "opacity:.6" : "";
          return `<div class="gd-ligne-row" style="${dim}">
            <span class="gd-dot" style="background:${dot}"></span>
            <span class="gd-badge" style="background:${bg};color:${fg}">${_esc(String(l.num ?? "?"))}</span>
            <div class="gd-ligne-meta">
              <div class="gd-ligne-nom">${_esc(l.nom ?? "")}</div>
              ${sub ? `<div class="gd-ligne-sub">${_esc(sub)}</div>` : ""}
            </div>
            ${etat !== 1 ? `<span class="gd-etat-lbl" style="color:${col};background:rgba(${rgb},0.10)">${_esc(l.etat_label ?? "")}</span>` : ""}
          </div>`;
        }).join("")
      : `<div class="gd-empty">Aucune ligne à afficher.</div>`;

    const worstEtat = disrupted.length
      ? Math.max(...disrupted.map(l => l.etat ?? 1))
      : 1;
    const headerIconColor = ETAT_DOT[worstEtat] ?? "#22c55e";

    this.shadowRoot.innerHTML = `<style>${ETAT_STYLES}</style>
    <div class="gd-card">
      <div class="gd-header">
        <span style="display:contents;color:${headerIconColor}">${ICON_INFO}</span>
        <span class="gd-header-title">${nbDisr > 0 ? `${nbDisr} ligne${nbDisr > 1 ? "s" : ""} perturbée${nbDisr > 1 ? "s" : ""}` : "État du réseau"}</span>
        <span class="gd-header-upd">màj ${_timeSince(etatEntity.last_updated)}</span>
      </div>
      ${normalBanner}
      <div class="gd-filters">${chipsHtml}</div>
      ${msgsHtml}
      <div class="gd-lignes">${lignesHtml}</div>
    </div>`;

    this.shadowRoot.querySelectorAll(".gd-chip[data-filter]").forEach(el => {
      el.addEventListener("click", () => { this._filter = el.dataset.filter; this._render(); });
    });

    this.shadowRoot.querySelectorAll(".gd-msg-toggle[data-idx]").forEach(el => {
      el.addEventListener("click", () => {
        const i = parseInt(el.dataset.idx, 10);
        if (this._expandedMsgs.has(i)) this._expandedMsgs.delete(i);
        else this._expandedMsgs.add(i);
        this._render();
      });
    });
  }
}

// ── Suivi positions card ──────────────────────────────────────────────────────

const SUIVI_STYLES = `
  :host {
    --gd-bg:     var(--ha-card-background, var(--card-background-color));
    --gd-border: var(--divider-color, rgba(0,0,0,0.12));
    --gd-r-lg:   var(--ha-card-border-radius, 14px);
    --gd-r-md:   10px;
    --gd-r-sm:   6px;
    --gd-txt:    var(--primary-text-color);
    --gd-txt-2:  var(--secondary-text-color);
    --gd-txt-3:  var(--disabled-text-color);
    --gd-amber:  var(--warning-color, #f59e0b);
    font-size: 14px; display: block;
  }
  @supports (color: color-mix(in srgb, red 50%, blue)) {
    :host { --gd-txt-3: color-mix(in srgb, var(--primary-text-color) 55%, transparent); }
  }
  * { box-sizing: border-box; }
  .gd-card { background:var(--gd-bg); border:0.5px solid var(--gd-border); border-radius:var(--gd-r-lg); overflow:hidden; font-family:var(--paper-font-body1_-_font-family,system-ui,sans-serif); box-shadow:var(--ha-card-box-shadow,none); }
  .gd-header { padding:10px 12px; display:flex; align-items:center; gap:8px; border-bottom:0.5px solid var(--gd-border); }
  .gd-header svg { width:18px; height:18px; color:var(--gd-txt-3); flex-shrink:0; }
  .gd-header-title { font-size:13px; font-weight:600; color:var(--gd-txt); flex:1; display:flex; align-items:center; gap:8px; min-width:0; }
  .gd-header-sub { font-size:11px; color:var(--gd-txt-3); white-space:nowrap; }
  .gd-badge { font-size:11px; font-weight:700; padding:2px 7px; border-radius:var(--gd-r-sm); line-height:1.4; white-space:nowrap; flex-shrink:0; box-shadow:0 0 0 1px color-mix(in srgb, var(--gd-txt) 20%, transparent); }
  .gd-filters { padding:6px 10px; display:flex; gap:5px; border-bottom:0.5px solid var(--gd-border); }
  .gd-chip { font-size:11px; font-weight:500; padding:3px 9px; border-radius:99px; border:0.5px solid var(--gd-border); background:transparent; color:var(--gd-txt-2); cursor:pointer; white-space:nowrap; font-family:inherit; display:inline-flex; align-items:center; gap:5px; }
  .gd-chip.active { color:var(--gd-txt); background:var(--secondary-background-color,rgba(128,128,128,0.12)); border-color:var(--gd-txt-3); font-weight:600; }
  .gd-buses { padding:4px 10px 8px; display:flex; flex-direction:column; gap:4px; }
  .gd-bus { display:flex; align-items:center; gap:8px; padding:7px 8px; border-radius:var(--gd-r-md); background:var(--secondary-background-color, rgba(128,128,128,0.05)); }
  .gd-bus-arrow { font-size:13px; flex-shrink:0; }
  .gd-bus-pos { flex:1; min-width:0; }
  .gd-bus-terminus { font-size:10px; color:var(--gd-txt-3); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; display:flex; align-items:center; gap:5px; }
  .gd-bus-location { font-size:12px; color:var(--gd-txt); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .gd-bus-location b { font-weight:600; }
  .gd-bus-quai { font-size:11px; color:var(--gd-txt-2); font-style:italic; }
  .gd-bus-time { font-size:14px; font-weight:700; color:var(--gd-txt); white-space:nowrap; font-variant-numeric:tabular-nums; flex-shrink:0; }
  .gd-bus-time-unit { font-size:10px; font-weight:400; color:var(--gd-txt-3); }
  .gd-bus-gps { width:12px; height:12px; flex-shrink:0; }
  .gd-approx { font-size:11px; font-weight:700; color:var(--gd-amber); line-height:1; flex-shrink:0; }
  .gd-retard { font-size:9px; font-weight:700; padding:1px 5px; border-radius:99px; line-height:1.3; white-space:nowrap; }
  .gd-retard--plus { color:#b45309; background:rgba(245,158,11,0.18); }
  .gd-retard--moins { color:#1d4ed8; background:rgba(59,130,246,0.15); }
  .gd-empty { padding:20px 14px; font-size:13px; color:var(--gd-txt-3); text-align:center; }
  .gd-unavail { padding:14px; font-size:13px; color:var(--gd-txt-3); }
`;

const ICON_CLOCK = `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 3"/></svg>`;
const ICON_GPS = `<svg class="gd-bus-gps" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><title>Position GPS</title><path d="M12 21s-6-5.3-6-11a6 6 0 0 1 12 0c0 5.7-6 11-6 11Z"/><circle cx="12" cy="10" r="2.2"/></svg>`;

class GrandoleSuiviCard extends HTMLElement {
  static getConfigElement() { return document.createElement("grandole-suivi-card-editor"); }
  static getStubConfig() {
    return { entity: "sensor.grandole_bus_ligne_1" };
  }

  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._filter = "all";
    this._refreshTimer = null;
  }

  setConfig(config) {
    this._config = { entity: config.entity ?? "" };
    if (this._hass) this._render();
  }

  set hass(hass) { this._hass = hass; this._render(); }
  connectedCallback()    { this._refreshTimer = setInterval(() => this._render(), 10000); }
  disconnectedCallback() { clearInterval(this._refreshTimer); }
  getCardSize()          { return 4; }

  _render() {
    if (!this._config || !this._hass) return;

    if (!this._config.entity) {
      this.shadowRoot.innerHTML = `<style>${SUIVI_STYLES}</style><div class="gd-card"><div class="gd-empty">Sélectionnez un capteur de suivi de ligne.</div></div>`;
      return;
    }

    const entity = this._hass.states[this._config.entity];
    if (!entity) {
      this.shadowRoot.innerHTML = `<style>${SUIVI_STYLES}</style><div class="gd-card"><div class="gd-unavail">Entité introuvable : ${_esc(this._config.entity)}</div></div>`;
      return;
    }

    const attrs    = entity.attributes ?? {};
    const numLigne = attrs.num_ligne ?? "?";
    const allBuses = Array.isArray(attrs.buses) ? attrs.buses : [];
    const bg = _color(attrs.couleurFond ?? "#D82080");
    const fg = _color(attrs.couleurTexte ?? "#FFFFFF");

    const hasAller  = allBuses.some(b => b.sens === "aller");
    const hasRetour = allBuses.some(b => b.sens === "retour");

    let shown = allBuses;
    if (this._filter === "aller"  && hasAller)  shown = allBuses.filter(b => b.sens === "aller");
    if (this._filter === "retour" && hasRetour) shown = allBuses.filter(b => b.sens === "retour");

    const chips = [{ k: "all", label: `Tous (${allBuses.length})` }];
    if (hasAller)  chips.push({ k: "aller",  label: "→ Aller" });
    if (hasRetour) chips.push({ k: "retour", label: "← Retour" });
    const chipsHtml = chips.map(c =>
      `<button class="gd-chip${this._filter === c.k ? " active" : ""}" data-f="${_esc(c.k)}">${_esc(c.label)}</button>`
    ).join("");

    const busRows = shown.length ? shown.map(b => {
      const arrow   = b.sens === "retour" ? "←" : "→";
      const sec     = b.dans_sec;
      const mins    = sec == null ? null : Math.floor(sec / 60);
      const timeHtml = sec == null
        ? `<span class="gd-bus-time" style="color:var(--gd-txt-3)">?</span>`
        : b.statut === "a_quai"
          ? `<span class="gd-bus-time" style="color:#22c55e">À quai</span>`
          : mins < 1
            ? `<span class="gd-bus-time">&lt; 1<span class="gd-bus-time-unit"> min</span></span>`
            : `<span class="gd-bus-time">${mins}<span class="gd-bus-time-unit"> min</span></span>`;

      let locationHtml;
      if (!b.prochain_arret) {
        locationHtml = `<div class="gd-bus-location">Position GPS sans course associée</div>`;
      } else if (b.statut === "a_quai") {
        locationHtml = `<div class="gd-bus-quai">À quai : ${_esc(b.prochain_arret ?? "")}</div>`;
      } else if (b.statut === "depart") {
        locationHtml = `<div class="gd-bus-location">Au départ de <b>${_esc(b.prochain_arret)}</b></div>`;
      } else {
        locationHtml = `<div class="gd-bus-location">${_esc(b.arret_precedent ?? "")} <b>→</b> ${_esc(b.prochain_arret)}</div>`;
      }

      const gps = b.gps === false
        ? `<span class="gd-approx" title="Position estimée d'après les horaires">~</span>`
        : `<span style="color:#22c55e;display:inline-flex" title="Position GPS il y a ${b.age ?? 0} s">${ICON_GPS}</span>`;
      let retard = "";
      if (b.retard != null && Math.abs(b.retard) >= 60) {
        const m = Math.round(b.retard / 60);
        retard = `<span class="gd-retard ${b.retard > 0 ? "gd-retard--plus" : "gd-retard--moins"}">${b.retard > 0 ? "+" : ""}${m} min</span>`;
      }
      const label = b.id != null && !String(b.id).startsWith("course-") ? `<span>Bus ${_esc(b.id)}</span>` : "";

      return `<div class="gd-bus">
        <span class="gd-bus-arrow">${arrow}</span>
        <div class="gd-bus-pos">
          <div class="gd-bus-terminus">${gps}${label}${label ? "<span>·</span>" : ""}<span>${_esc(b.terminus ?? "")}</span>${retard}</div>
          ${locationHtml}
        </div>
        ${timeHtml}
      </div>`;
    }).join("")
    : `<div class="gd-empty">${attrs.temps_reel === false ? "Temps réel indisponible ou figé : aucune position récente." : "Aucun bus en circulation."}</div>`;

    const nb = allBuses.length;
    const headerSub = `màj ${_timeSince(entity.last_updated)}`;

    this.shadowRoot.innerHTML = `<style>${SUIVI_STYLES}</style>
    <div class="gd-card">
      <div class="gd-header">${ICON_CLOCK}
        <span class="gd-header-title"><span class="gd-badge" style="background:${bg};color:${fg}">${_esc(numLigne)}</span><span style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${_esc(attrs.nom_ligne ?? `Ligne ${numLigne}`)}</span><span style="font-size:11px;font-weight:400;color:var(--gd-txt-3);white-space:nowrap">${nb} bus</span></span>
        <span class="gd-header-sub">${headerSub}</span>
      </div>
      ${chips.length > 1 ? `<div class="gd-filters">${chipsHtml}</div>` : ""}
      <div class="gd-buses">${busRows}</div>
    </div>`;

    this.shadowRoot.querySelectorAll(".gd-chip[data-f]").forEach(el => {
      el.addEventListener("click", () => { this._filter = el.dataset.f; this._render(); });
    });
  }
}

// ── Registration ──────────────────────────────────────────────────────────────

customElements.define("grandole-card", GrandoleCard);
customElements.define("grandole-etat-card", GrandoleEtatCard);
customElements.define("grandole-suivi-card", GrandoleSuiviCard);
customElements.define("grandole-recherche-card", GrandoleRechercheCard);

window.customCards = window.customCards ?? [];
window.customCards.push({
  type:        "grandole-recherche-card",
  name:        "Grandole Recherche d'arrêt",
  description: "Recherche dynamique d'un arrêt Grandole Mobilités et affichage de ses prochains passages, sans capteur.",
  preview:     false,
});
window.customCards.push({
  type:        "grandole-card",
  name:        "Grandole Mobilités",
  description: "Prochains passages du réseau Grandole Mobilités (Grand Dole).",
  preview:     false,
});
window.customCards.push({
  type:        "grandole-etat-card",
  name:        "Grandole État du Réseau",
  description: "Infotrafic, état des lignes, retards et courses annulées du réseau Grandole Mobilités.",
  preview:     false,
});
window.customCards.push({
  type:        "grandole-suivi-card",
  name:        "Grandole Positions Bus",
  description: "Positions en temps réel des bus d'une ligne Grandole Mobilités.",
  preview:     false,
});

console.info(
  `%c GRANDOLE-CARD %c v${VERSION} `,
  "color:#fff;background:#D82080;font-weight:700;padding:2px 4px;border-radius:3px 0 0 3px",
  "color:#D82080;background:#1c1c1e;font-weight:400;padding:2px 4px;border-radius:0 3px 3px 0",
);
