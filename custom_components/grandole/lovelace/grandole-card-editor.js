const EDITOR_STYLES = `
  :host { display: block; }
  .gd-editor { padding: 16px 0; font-size: 14px; color: var(--primary-text-color); }
  .gd-field { margin-bottom: 16px; }
  label { display: block; font-size: 12px; font-weight: 500; color: var(--secondary-text-color); margin-bottom: 5px; text-transform: uppercase; letter-spacing: .04em; }
  input[type="text"], input[type="number"], select {
    width: 100%; box-sizing: border-box; padding: 8px 10px; border-radius: 6px;
    border: 1px solid var(--divider-color, rgba(255,255,255,0.2));
    background: var(--secondary-background-color, #2c2c2e);
    color: var(--primary-text-color, #e5e5ea); font-size: 14px; outline: none;
  }
  input[type="text"]:focus, input[type="number"]:focus, select:focus { border-color: var(--primary-color, #03a9f4); }
  input[type="number"] { width: 80px; }
  .gd-hint { font-size: 11px; color: var(--disabled-text-color, rgba(255,255,255,0.38)); margin-top: 4px; line-height: 1.4; }
  .gd-row-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .gd-section { font-size: 11px; font-weight: 600; color: var(--disabled-text-color); text-transform: uppercase; letter-spacing: .06em; border-top: 1px solid var(--divider-color, rgba(255,255,255,0.1)); padding-top: 14px; margin: 18px 0 10px; }
  pre { font-family: monospace; font-size: 11px; color: var(--secondary-text-color); line-height: 1.8; background: var(--secondary-background-color, rgba(255,255,255,0.05)); padding: 10px 12px; border-radius: 8px; overflow-x: auto; margin: 0; white-space: pre; }
  .gd-suivi-row { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
  .gd-suivi-del { background: none; border: 1px solid var(--divider-color, rgba(255,255,255,0.2)); border-radius: 4px; color: var(--secondary-text-color); cursor: pointer; padding: 4px 8px; font-size: 12px; flex-shrink: 0; }
  .gd-checks { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 6px; }
  .gd-check-label { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 99px; border: 1px solid var(--divider-color, rgba(255,255,255,0.2)); background: var(--secondary-background-color, rgba(255,255,255,0.05)); font-size: 12px; font-weight: 500; cursor: pointer; color: var(--primary-text-color); }
  .gd-check-label input { margin: 0; accent-color: var(--primary-color, #03a9f4); }
`;

const EDITOR_ICON_BUS = `<svg style="width:12px;height:12px;display:inline-block;vertical-align:middle;margin-right:3px" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"><path d="M4 17.5V5.5A2.5 2.5 0 0 1 6.5 3h11A2.5 2.5 0 0 1 20 5.5v12a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 17.5Z"/><path d="M4 11.5h16"/><path d="M12 3v8.5"/><circle cx="7.6" cy="15.2" r=".9" fill="currentColor" stroke="none"/><circle cx="16.4" cy="15.2" r=".9" fill="currentColor" stroke="none"/><path d="M6.2 19v1.2a.9.9 0 0 1-.9.9h-.4a.9.9 0 0 1-.9-.9V19"/><path d="M20 19v1.2a.9.9 0 0 1-.9.9h-.4a.9.9 0 0 1-.9-.9V19"/></svg>`;

function _emit(el, cfg) {
  el.dispatchEvent(new CustomEvent("config-changed", { detail: { config: cfg }, bubbles: true, composed: true }));
}

function _escAttr(s) { return String(s).replace(/"/g, "&quot;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }

// ── GrandoleCardEditor ────────────────────────────────────────────────────────

class GrandoleCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass   = null;
  }

  setConfig(config) {
    this._config = { ...config };
    this._render();
  }

  set hass(h) {
    if (!this._hass) {
      this._hass = h;
      this._autoFill();
      this._render();
    } else {
      this._hass = h;
    }
  }

  _autoFill() {
    if (!this._hass) return;
    const upd = { ...this._config };
    let changed = false;
    const cardMode = upd.mode ?? "lieu";

    if (!upd.messages_entity && this._hass.states["sensor.grandole_messages"]) {
      upd.messages_entity = "sensor.grandole_messages";
      changed = true;
    }
    if (!upd.entity) {
      const sensors = this._passageSensors(cardMode);
      if (sensors.length === 1) { upd.entity = sensors[0]; changed = true; }
    }
    if (changed) {
      this._config = upd;
      _emit(this, upd);
    }
  }

  _passageSensors(cardMode) {
    if (!this._hass) return [];
    return Object.keys(this._hass.states)
      .filter(id => {
        const s = this._hass.states[id];
        if (!id.startsWith("sensor.grandole_")) return false;
        const gm = s.attributes?.grandole_mode;
        if (!gm) return false;
        if (!cardMode) return gm === "lieu" || gm === "liste" || gm === "proximity";
        return gm === cardMode;
      })
      .sort();
  }

  _suiviSensors() {
    if (!this._hass) return [];
    return Object.keys(this._hass.states)
      .filter(id => {
        const s = this._hass.states[id];
        return id.startsWith("sensor.grandole_") && s.attributes?.grandole_mode === "suivi";
      })
      .sort();
  }

  _lignesDisponibles() {
    const entity = this._hass?.states[this._config?.entity ?? ""];
    const passages = entity?.attributes?.passages ?? [];
    const seen = new Map();
    for (const p of passages) {
      const id = String(p.numLignePublic ?? p.idLigne ?? "");
      if (id && !seen.has(id)) {
        seen.set(id, { id, label: id });
      }
    }
    return [...seen.values()].sort((a, b) => a.label.localeCompare(b.label, undefined, { numeric: true }));
  }

  _render() {
    const cfg     = this._config;
    const mode    = cfg.mode ?? "lieu";
    const isProx  = mode === "proximity";
    const isLieu  = mode === "lieu";
    const grandoleMode = mode === "proximity" ? "proximity" : mode === "liste" ? "liste" : "lieu";
    const sensors = this._passageSensors(grandoleMode);
    const sensorOpts = sensors.map(id => `<option value="${_escAttr(id)}">`).join("");
    const suivis     = this._suiviSensors();
    const suiviOpts  = suivis.map(id => `<option value="${_escAttr(id)}">`).join("");
    const msgOpts    = this._hass?.states["sensor.grandole_messages"]
      ? `<option value="sensor.grandole_messages">`
      : "";

    this.shadowRoot.innerHTML = `<style>${EDITOR_STYLES}</style>
    <datalist id="gd-sensors">${sensorOpts}</datalist>
    <datalist id="gd-suivi-sensors">${suiviOpts}</datalist>
    <datalist id="gd-msg-sensors">${msgOpts}</datalist>
    <div class="gd-editor">

      <div class="gd-field">
        <label>Mode</label>
        <select id="mode">
          <option value="lieu"      ${mode === "lieu"      ? "selected" : ""}>Arrêt fixe : toutes lignes</option>
          <option value="liste"     ${mode === "liste"     ? "selected" : ""}>Ligne spécifique</option>
          <option value="proximity" ${mode === "proximity" ? "selected" : ""}>Arrêts à proximité</option>
        </select>
      </div>

      <div class="gd-field">
        <label>Entité capteur Grandole</label>
        <input id="entity" type="text" list="gd-sensors"
          value="${_escAttr(cfg.entity ?? "")}"
          placeholder="${isProx ? "sensor.grandole_proximite_..." : "sensor.grandole_..."}">
        <div class="gd-hint">${
          sensors.length > 0
            ? `${sensors.length} capteur(s) compatible(s) avec ce mode : cliquez dans le champ pour les suggestions.`
            : `Aucun capteur de type « ${grandoleMode} » trouvé. Créez d'abord une entrée Grandole correspondante.`
        }</div>
      </div>

      <div class="gd-field">
        <label>Entité messages infotrafic <span style="font-weight:400;text-transform:none">(optionnel)</span></label>
        <input id="messages_entity" type="text" list="gd-msg-sensors"
          value="${_escAttr(cfg.messages_entity ?? "")}" placeholder="sensor.grandole_messages">
        <div class="gd-hint">Bandeau infotrafic du site grandole-mobilites.fr et anomalies temps réel sur les lignes affichées.</div>
      </div>

      <div class="gd-field">
        <label>Position des bus <span style="font-weight:400;text-transform:none">(optionnel)</span></label>
        ${(() => {
          const suiviList = Array.isArray(cfg.suivi_entities)
            ? cfg.suivi_entities
            : (cfg.suivi_entity ? [cfg.suivi_entity] : []);
          return [...suiviList, ""].map((val, i) => {
            const isLast = i === suiviList.length;
            return `<div class="gd-suivi-row">
              <input class="gd-suivi-input" type="text" list="gd-suivi-sensors"
                data-idx="${i}" value="${_escAttr(val)}"
                placeholder="sensor.grandole_bus_ligne_1"
                style="flex:1">
              ${!isLast ? `<button class="gd-suivi-del" data-idx="${i}" title="Supprimer">✕</button>` : ""}
            </div>`;
          }).join("");
        })()}
        <div class="gd-hint">Un capteur de suivi par ligne desservant cet arrêt.</div>
      </div>

      <div class="gd-row-2">
        <div class="gd-field">
          <label>Passages</label>
          <input id="max_passages" type="number" min="1" max="5" value="${cfg.max_passages ?? 3}">
          <div class="gd-hint">1 à 5 par direction</div>
        </div>
        ${isProx
          ? `<div class="gd-field"><label>Arrêts proches</label><input id="max_stops" type="number" min="1" max="10" value="${cfg.max_stops ?? 5}"><div class="gd-hint">1 à 10</div></div>`
          : "<div></div>"
        }
      </div>

      ${isLieu ? (() => {
        const lignes = this._lignesDisponibles();
        const filtre = cfg.lignes_filtre ?? [];
        if (!lignes.length) return `
          <div class="gd-section">Filtrer les lignes</div>
          <div class="gd-field">
            <div class="gd-hint">Aucune ligne détectée. Les lignes apparaissent ici une fois l'entité sélectionnée et des passages disponibles dans les 3 prochaines heures.</div>
          </div>`;
        const boxes = lignes.map(l => {
          const checked = filtre.length === 0 || filtre.includes(l.id) ? "checked" : "";
          return `<label class="gd-check-label"><input type="checkbox" class="gd-ligne-cb" data-id="${_escAttr(l.id)}" ${checked}>${EDITOR_ICON_BUS}${_escAttr(l.label)}</label>`;
        }).join("");
        return `
          <div class="gd-section">Filtrer les lignes</div>
          <div class="gd-field">
            <div class="gd-checks">${boxes}</div>
            <div class="gd-hint">Liste limitée aux lignes ayant un passage dans les 3 prochaines heures.</div>
          </div>`;
      })() : ""}

      <div class="gd-section">Présentation</div>
      <div class="gd-row-2">
        <div class="gd-field">
          <label>Bandeau infotrafic</label>
          <select id="show_traffic">
            <option value="if_disrupted" ${(cfg.show_traffic ?? "if_disrupted") === "if_disrupted" ? "selected" : ""}>Si perturbation</option>
            <option value="always"       ${cfg.show_traffic === "always" ? "selected" : ""}>Toujours</option>
            <option value="never"        ${cfg.show_traffic === "never"  ? "selected" : ""}>Jamais</option>
          </select>
        </div>
        <div class="gd-field">
          <label>Heure de passage</label>
          <select id="show_hour">
            <option value="true"  ${(cfg.show_hour ?? true) ? "selected" : ""}>Afficher</option>
            <option value="false" ${cfg.show_hour === false ? "selected" : ""}>Masquer</option>
          </select>
        </div>
      </div>

      <div class="gd-section">Aperçu YAML</div>
      <pre id="yaml-preview">${this._yaml()}</pre>
    </div>`;

    this._listen();
  }

  _listen() {
    const bind = (id, key, fn) => {
      const el = this.shadowRoot.querySelector(`#${id}`);
      if (!el) return;
      el.addEventListener("change", e => this._update(key, fn ? fn(e.target.value) : e.target.value));
    };
    bind("mode",            "mode");
    bind("entity",          "entity");
    bind("messages_entity", "messages_entity");
    bind("show_traffic",    "show_traffic");
    bind("show_hour",       "show_hour", v => v === "false" ? false : undefined);
    bind("max_passages",    "max_passages", v => Math.min(5, Math.max(1, parseInt(v) || 3)));
    bind("max_stops",       "max_stops",    v => Math.min(10, Math.max(1, parseInt(v) || 5)));

    const getSuiviList = () => {
      const inputs = [...this.shadowRoot.querySelectorAll(".gd-suivi-input")];
      return inputs.map(i => i.value.trim()).filter(v => v !== "");
    };
    this.shadowRoot.querySelectorAll(".gd-suivi-input").forEach(inp => {
      inp.addEventListener("change", () => this._update("suivi_entities", getSuiviList()));
    });
    this.shadowRoot.querySelectorAll(".gd-suivi-del").forEach(btn => {
      btn.addEventListener("click", () => {
        const idx = parseInt(btn.dataset.idx);
        const list = getSuiviList();
        list.splice(idx, 1);
        this._update("suivi_entities", list);
        this._render();
      });
    });

    this.shadowRoot.querySelectorAll(".gd-ligne-cb").forEach(cb => {
      cb.addEventListener("change", () => {
        const all = [...this.shadowRoot.querySelectorAll(".gd-ligne-cb")];
        const checked = all.filter(c => c.checked).map(c => c.dataset.id);
        const filtre = checked.length === all.length ? [] : checked;
        this._update("lignes_filtre", filtre.length ? filtre : undefined);
      });
    });
  }

  _update(key, value) {
    const cfg = { ...this._config };
    if (value === "" || value == null || (Array.isArray(value) && value.length === 0)) delete cfg[key]; else cfg[key] = value;
    this._config = cfg;
    const pre = this.shadowRoot.querySelector("#yaml-preview");
    if (pre) pre.textContent = this._yaml();
    if (key === "mode") this._render();
    _emit(this, cfg);
  }

  _yaml() {
    const c = this._config;
    const filtre = Array.isArray(c.lignes_filtre) && c.lignes_filtre.length ? c.lignes_filtre : null;
    return [
      `type: custom:grandole-card`,
      `mode: ${c.mode ?? "lieu"}`,
      c.entity          ? `entity: ${c.entity}`                   : null,
      c.messages_entity ? `messages_entity: ${c.messages_entity}` : null,
      (() => {
        const list = Array.isArray(c.suivi_entities) && c.suivi_entities.length ? c.suivi_entities
                   : c.suivi_entity ? [c.suivi_entity] : [];
        if (!list.length) return null;
        if (list.length === 1) return `suivi_entity: ${list[0]}`;
        return `suivi_entities:\n${list.map(e => `  - ${e}`).join("\n")}`;
      })(),
      filtre            ? `lignes_filtre:\n${filtre.map(l => `  - "${l}"`).join("\n")}` : null,
      `max_passages: ${c.max_passages ?? 3}`,
      c.mode === "proximity" ? `max_stops: ${c.max_stops ?? 5}` : null,
      `show_traffic: ${c.show_traffic ?? "if_disrupted"}`,
      c.show_hour === false ? `show_hour: false` : null,
    ].filter(Boolean).join("\n");
  }
}

customElements.define("grandole-card-editor", GrandoleCardEditor);

// ── GrandoleEtatCardEditor ────────────────────────────────────────────────────

class GrandoleEtatCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass   = null;
  }

  setConfig(config) { this._config = { ...config }; this._render(); }

  set hass(h) {
    if (!this._hass) {
      this._hass = h;
      this._autoFill();
      this._render();
    } else {
      this._hass = h;
    }
  }

  _autoFill() {
    if (!this._hass) return;
    const upd = { ...this._config };
    let changed = false;
    if (!upd.entity && this._hass.states["sensor.grandole_etat_lignes"]) {
      upd.entity = "sensor.grandole_etat_lignes"; changed = true;
    }
    if (!upd.messages_entity && this._hass.states["sensor.grandole_messages"]) {
      upd.messages_entity = "sensor.grandole_messages"; changed = true;
    }
    if (changed) {
      this._config = upd;
      _emit(this, upd);
    }
  }

  _render() {
    const cfg = this._config;
    this.shadowRoot.innerHTML = `<style>${EDITOR_STYLES}</style>
    <div class="gd-editor">

      <div class="gd-field">
        <label>Entité état des lignes</label>
        <input id="entity" type="text"
          value="${_escAttr(cfg.entity ?? "sensor.grandole_etat_lignes")}"
          placeholder="sensor.grandole_etat_lignes">
        <div class="gd-hint">Créée automatiquement par l'intégration Grandole.</div>
      </div>

      <div class="gd-field">
        <label>Entité messages infotrafic <span style="font-weight:400;text-transform:none">(optionnel)</span></label>
        <input id="messages_entity" type="text"
          value="${_escAttr(cfg.messages_entity ?? "sensor.grandole_messages")}"
          placeholder="sensor.grandole_messages">
      </div>

      <div class="gd-field">
        <label class="gd-check-label"><input id="hide_inactive" type="checkbox" ${cfg.hide_inactive ? "checked" : ""}> Masquer les lignes hors service dans la vue « Toutes »</label>
      </div>

      <div class="gd-section">Aperçu YAML</div>
      <pre>${this._yaml()}</pre>
    </div>`;

    const bind = (id, key) => {
      const el = this.shadowRoot.querySelector(`#${id}`);
      if (!el) return;
      el.addEventListener("change", e => {
        const cfg = { ...this._config };
        const v = e.target.value;
        if (v === "" || v == null) delete cfg[key]; else cfg[key] = v;
        this._config = cfg;
        _emit(this, cfg);
      });
    };
    bind("entity",          "entity");
    bind("messages_entity", "messages_entity");
    const hide = this.shadowRoot.querySelector("#hide_inactive");
    if (hide) hide.addEventListener("change", e => {
      const cfg = { ...this._config };
      if (e.target.checked) cfg.hide_inactive = true; else delete cfg.hide_inactive;
      this._config = cfg;
      _emit(this, cfg);
    });
  }

  _yaml() {
    const c = this._config;
    return [
      `type: custom:grandole-etat-card`,
      `entity: ${c.entity ?? "sensor.grandole_etat_lignes"}`,
      c.messages_entity ? `messages_entity: ${c.messages_entity}` : null,
      c.hide_inactive ? `hide_inactive: true` : null,
    ].filter(Boolean).join("\n");
  }
}

customElements.define("grandole-etat-card-editor", GrandoleEtatCardEditor);

// ── GrandoleSuiviCardEditor ───────────────────────────────────────────────────

class GrandoleSuiviCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass   = null;
  }

  setConfig(config) { this._config = { ...config }; this._render(); }

  set hass(h) {
    if (!this._hass) {
      this._hass = h;
      this._autoFill();
      this._render();
    } else {
      this._hass = h;
    }
  }

  _autoFill() {
    if (!this._hass) return;
    const upd = { ...this._config };
    if (!upd.entity) {
      const sensors = this._suiviSensors();
      if (sensors.length === 1) { upd.entity = sensors[0]; }
    }
    if (upd.entity !== this._config.entity) {
      this._config = upd;
      _emit(this, upd);
    }
  }

  _suiviSensors() {
    if (!this._hass) return [];
    return Object.keys(this._hass.states)
      .filter(id => {
        const s = this._hass.states[id];
        return id.startsWith("sensor.grandole_") && s.attributes?.grandole_mode === "suivi";
      })
      .sort();
  }

  _render() {
    const cfg     = this._config;
    const sensors = this._suiviSensors();
    const opts    = sensors.map(id => `<option value="${_escAttr(id)}">`).join("");

    this.shadowRoot.innerHTML = `<style>${EDITOR_STYLES}</style>
    <datalist id="gd-suivi-sensors">${opts}</datalist>
    <div class="gd-editor">
      <div class="gd-field">
        <label>Entité capteur de suivi</label>
        <input id="entity" type="text" list="gd-suivi-sensors"
          value="${_escAttr(cfg.entity ?? "")}" placeholder="sensor.grandole_bus_ligne_1">
        <div class="gd-hint">${
          sensors.length > 0
            ? `${sensors.length} capteur(s) de suivi disponible(s).`
            : "Créez une entrée « Positions des véhicules » dans l'intégration Grandole."
        }</div>
      </div>
      <div class="gd-section">Aperçu YAML</div>
      <pre>${this._yaml()}</pre>
    </div>`;

    const el = this.shadowRoot.querySelector("#entity");
    if (el) el.addEventListener("change", e => {
      const c = { ...this._config };
      const v = e.target.value;
      if (v) c.entity = v; else delete c.entity;
      this._config = c;
      _emit(this, c);
    });
  }

  _yaml() {
    const c = this._config;
    return [`type: custom:grandole-suivi-card`, c.entity ? `entity: ${c.entity}` : null]
      .filter(Boolean).join("\n");
  }
}

customElements.define("grandole-suivi-card-editor", GrandoleSuiviCardEditor);

// ── GrandoleRechercheCardEditor ───────────────────────────────────────────────

class GrandoleRechercheCardEditor extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config = {};
    this._hass   = null;
  }

  setConfig(config) { this._config = { ...config }; this._render(); }

  set hass(h) {
    if (!this._hass) {
      this._hass = h;
      this._autoFill();
      this._render();
    } else {
      this._hass = h;
    }
  }

  _autoFill() {
    if (!this._hass) return;
    if (!this._config.messages_entity && this._hass.states["sensor.grandole_messages"]) {
      const upd = { ...this._config, messages_entity: "sensor.grandole_messages" };
      this._config = upd;
      _emit(this, upd);
    }
  }

  _render() {
    const cfg = this._config;
    const sel = (v, cur) => v === cur ? "selected" : "";
    const traffic = cfg.show_traffic ?? "if_disrupted";
    this.shadowRoot.innerHTML = `<style>${EDITOR_STYLES}</style>
    <div class="gd-editor">

      <div class="gd-field">
        <label>Arrêt prédéfini <span style="font-weight:400;text-transform:none">(optionnel)</span></label>
        <input id="arret" type="text" value="${_escAttr(cfg.arret ?? "")}" placeholder="ex. Dole Gare">
        <div class="gd-hint">Laissez vide pour laisser l'utilisateur chercher l'arrêt de son choix.</div>
      </div>

      <div class="gd-field">
        <label>Passages par ligne et direction</label>
        <input id="nb_passages" type="number" min="1" max="5" value="${Number(cfg.nb_passages ?? 3)}">
      </div>

      <div class="gd-field">
        <label>Rafraîchissement (secondes)</label>
        <input id="refresh" type="number" min="10" max="300" step="5" value="${Number(cfg.refresh ?? 30)}">
        <div class="gd-hint">Les horaires ne sont recalculés que lorsqu'un arrêt est affiché.</div>
      </div>

      <div class="gd-field">
        <label>Bandeau infotrafic</label>
        <select id="show_traffic">
          <option value="if_disrupted" ${sel("if_disrupted", traffic)}>Si perturbation</option>
          <option value="always" ${sel("always", traffic)}>Toujours</option>
          <option value="never" ${sel("never", traffic)}>Jamais</option>
        </select>
      </div>

      <div class="gd-field">
        <label>Entité messages infotrafic <span style="font-weight:400;text-transform:none">(optionnel)</span></label>
        <input id="messages_entity" type="text" value="${_escAttr(cfg.messages_entity ?? "")}" placeholder="sensor.grandole_messages">
      </div>

      <div class="gd-field">
        <label class="gd-check-label"><input id="remember" type="checkbox" ${(cfg.remember ?? true) ? "checked" : ""}> Mémoriser le dernier arrêt consulté (navigateur)</label>
      </div>

      <div class="gd-section">Aperçu YAML</div>
      <pre>${this._yaml()}</pre>
    </div>`;

    const emit = (cfg) => {
      this._config = cfg;
      _emit(this, cfg);
      const pre = this.shadowRoot.querySelector("pre");
      if (pre) pre.textContent = this._yaml();
    };
    const bindText = (id, key, numeric = false) => {
      const el = this.shadowRoot.querySelector(`#${id}`);
      if (!el) return;
      el.addEventListener("change", e => {
        const cfg = { ...this._config };
        const v = e.target.value;
        if (v === "" || v == null) delete cfg[key];
        else cfg[key] = numeric ? Number(v) : v;
        emit(cfg);
      });
    };
    bindText("arret",           "arret");
    bindText("nb_passages",     "nb_passages", true);
    bindText("refresh",         "refresh", true);
    bindText("show_traffic",    "show_traffic");
    bindText("messages_entity", "messages_entity");
    const rem = this.shadowRoot.querySelector("#remember");
    if (rem) rem.addEventListener("change", e => {
      const cfg = { ...this._config };
      if (e.target.checked) delete cfg.remember; else cfg.remember = false;
      emit(cfg);
    });
  }

  _yaml() {
    const c = this._config;
    return [
      `type: custom:grandole-recherche-card`,
      c.arret ? `arret: ${c.arret}` : null,
      c.nb_passages != null ? `nb_passages: ${c.nb_passages}` : null,
      c.refresh != null ? `refresh: ${c.refresh}` : null,
      c.show_traffic ? `show_traffic: ${c.show_traffic}` : null,
      c.messages_entity ? `messages_entity: ${c.messages_entity}` : null,
      c.remember === false ? `remember: false` : null,
    ].filter(Boolean).join("\n");
  }
}

customElements.define("grandole-recherche-card-editor", GrandoleRechercheCardEditor);
