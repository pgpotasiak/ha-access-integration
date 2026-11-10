// "Guest access" sidebar page for the Temporary Access integration.
// Plain web component; talks to Home Assistant through hass.callWS.

const T = {
  pl: {
    title: "Dostęp gości",
    newPanel: "Nowy panel",
    loading: "Wczytywanie…",
    noEntry: "Najpierw dodaj integrację Temporary Access w Ustawienia → Urządzenia i usługi.",
    empty: "Nie masz jeszcze żadnych paneli dla gości.",
    connected: "Połączono z portalem",
    disconnected: "Brak połączenia z portalem",
    active: "Aktywne",
    ended: "Zakończone",
    showEnded: n => `Pokaż zakończone (${n})`,
    hideEnded: "Ukryj zakończone",
    status: { active: "Aktywny", not_started: "Jeszcze nieaktywny", outside_schedule: "Poza godzinami", expired: "Wygasł", revoked: "Unieważniony", locked: "Zablokowany (zły PIN)" },
    until: "Ważny do",
    starts: "Startuje",
    left: "zostało",
    lastAction: "Ostatnio",
    none: "gość jeszcze nic nie robił",
    failedPin: n => `Błędne PIN-y: ${n}`,
    uses: (u, m) => `${u}/${m} użyć`,
    type: { switch: "przełącznik", button: "przycisk", sensor: "odczyt" },
    withState: "z podglądem stanu",
    fShowState: "Pokaż gościowi stan",
    qr: "Kod QR", hideQr: "Ukryj kod QR",
    copyLink: "Kopiuj link", copyPin: "Kopiuj PIN", showPin: "Pokaż PIN",
    copied: "Skopiowano",
    revoke: "Unieważnij", del: "Usuń",
    confirmRevoke: t => `Unieważnić panel „${t}”? Gość od razu straci dostęp.`,
    confirmDelete: t => `Usunąć panel „${t}” razem z historią? Jeśli jest aktywny, zostanie też unieważniony.`,
    portalWarn: "Panel zablokowano w Home Assistancie, ale portal jest teraz nieosiągalny. Spróbuj ponownie później.",
    // form
    formTitle: "Nowy panel dla gościa",
    fTitle: "Tytuł widoczny dla gościa", fTitlePh: "np. Dostęp dla Marka",
    fEntities: "Encje dla gościa", fSearch: "Szukaj encji…", fNoMatch: "Brak pasujących encji.",
    fControls: "Ustawienia kontrolek",
    fName: "Nazwa dla gościa", fType: "Rodzaj", fAction: "Działanie", fPulse: "Impuls (s)", fLimit: "Limit użyć", fLimitPh: "bez limitu",
    actions: { press: "Naciśnij", run: "Uruchom", unlock: "Odblokuj", open: "Otwórz", toggle: "Przełącz", pulse: "Impuls" },
    typeLong: { switch: "Przełącznik (Włącz / Wyłącz)", button: "Przycisk (przytrzymaj)", sensor: "Odczyt (tylko podgląd)" },
    fWhen: "Czas dostępu",
    fStart: "Początek", fStartHint: "puste = od teraz",
    fDuration: "Czas trwania", d: "dni", h: "godz.", m: "min",
    fLimits: "Ograniczenia (opcjonalnie)",
    fDays: "Tylko w dni", days: ["Pn", "Wt", "Śr", "Cz", "Pt", "So", "Nd"],
    fFrom: "Od godziny", fTo: "Do godziny",
    fPin: "PIN", fPinPh: "puste = losowe 4 cyfry",
    fLang: "Język strony gościa",
    create: "Utwórz panel", cancel: "Anuluj", creating: "Tworzenie…",
    errTitle: "Podaj tytuł.", errEntities: "Wybierz co najmniej jedną encję.", errHours: "Podaj obie godziny albo żadnej.",
    errPin: "PIN musi mieć od 4 do 8 cyfr.", errDuration: "Czas trwania musi wynosić co najmniej minutę.",
    created: "Panel gotowy",
    createdHint: "Wyślij gościowi link i PIN dwiema osobnymi wiadomościami albo pokaż mu kod QR.",
    done: "Gotowe",
    link: "Link",
  },
  en: {
    title: "Guest access",
    newPanel: "New panel",
    loading: "Loading…",
    noEntry: "First add the Temporary Access integration in Settings → Devices & services.",
    empty: "You have no guest panels yet.",
    connected: "Connected to the portal",
    disconnected: "Not connected to the portal",
    active: "Active",
    ended: "Ended",
    showEnded: n => `Show ended (${n})`,
    hideEnded: "Hide ended",
    status: { active: "Active", not_started: "Not started", outside_schedule: "Outside hours", expired: "Expired", revoked: "Revoked", locked: "Locked (wrong PIN)" },
    until: "Valid until",
    starts: "Starts",
    left: "left",
    lastAction: "Last",
    none: "the guest has not done anything yet",
    failedPin: n => `Wrong PINs: ${n}`,
    uses: (u, m) => `${u}/${m} uses`,
    type: { switch: "switch", button: "button", sensor: "read-out" },
    withState: "with state",
    fShowState: "Show the state to the guest",
    qr: "QR code", hideQr: "Hide QR code",
    copyLink: "Copy link", copyPin: "Copy PIN", showPin: "Show PIN",
    copied: "Copied",
    revoke: "Revoke", del: "Delete",
    confirmRevoke: t => `Revoke “${t}”? The guest loses access immediately.`,
    confirmDelete: t => `Delete “${t}” and its history? If it is active, it is revoked too.`,
    portalWarn: "The panel is blocked in Home Assistant, but the portal is unreachable right now. Try again later.",
    formTitle: "New guest panel",
    fTitle: "Title shown to the guest", fTitlePh: "e.g. Access for Mark",
    fEntities: "Entities for the guest", fSearch: "Search entities…", fNoMatch: "No matching entities.",
    fControls: "Control settings",
    fName: "Name for the guest", fType: "Kind", fAction: "Action", fPulse: "Pulse (s)", fLimit: "Use limit", fLimitPh: "no limit",
    actions: { press: "Press", run: "Run", unlock: "Unlock", open: "Open", toggle: "Toggle", pulse: "Pulse" },
    typeLong: { switch: "Switch (On / Off)", button: "Button (hold)", sensor: "Read-out (state only)" },
    fWhen: "Access time",
    fStart: "Start", fStartHint: "empty = now",
    fDuration: "Duration", d: "days", h: "hours", m: "min",
    fLimits: "Restrictions (optional)",
    fDays: "Only on days", days: ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"],
    fFrom: "From", fTo: "To",
    fPin: "PIN", fPinPh: "empty = random 4 digits",
    fLang: "Guest page language",
    create: "Create panel", cancel: "Cancel", creating: "Creating…",
    errTitle: "Enter a title.", errEntities: "Choose at least one entity.", errHours: "Set both hours or neither.",
    errPin: "The PIN must have 4 to 8 digits.", errDuration: "Duration must be at least one minute.",
    created: "Panel ready",
    createdHint: "Send the guest the link and the PIN in two separate messages, or show the QR code.",
    done: "Done",
    link: "Link",
  },
};

const DAYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"];
const ENDED = ["expired", "revoked"];

const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);

class TempAccessPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._data = null;
    this._error = null;
    this._view = "list";
    this._qrOpen = new Set();
    this._pinOpen = new Set();
    this._showEnded = false;
    this._form = null;
    this._result = null;
    this._toast = null;
    this._busy = false;
    this._watch = "";
    this.shadowRoot.addEventListener("click", e => this._onClick(e));
    this.shadowRoot.addEventListener("input", e => this._onInput(e));
    this.shadowRoot.addEventListener("change", e => this._onInput(e));
  }

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._load();
      // Periodic refresh: countdowns, connection state, panels added elsewhere.
      this._timer = setInterval(() => { if (this._view === "list") this._load(); }, 30000);
      return;
    }
    // Reload when any of our panel entities changed (status, last guest action, QR image).
    const ids = (this._data?.panels || []).flatMap(p => Object.values(p.entities || {})).filter(Boolean);
    const sig = ids.map(id => id + "=" + (hass.states[id]?.last_updated || "")).join("|");
    if (sig !== this._watch) {
      const firstSig = !this._watch;
      this._watch = sig;
      if (!firstSig) {
        clearTimeout(this._reload);
        this._reload = setTimeout(() => this._load(), 400);
      }
    }
  }

  get hass() { return this._hass; }
  set narrow(n) { this._narrow = n; this._render(); }
  set panel(_p) {}
  set route(_r) {}

  disconnectedCallback() { clearInterval(this._timer); }

  get t() { return T[(this._hass?.language || "en").startsWith("pl") ? "pl" : "en"]; }
  get locale() { return this._hass?.language || "en"; }

  async _load() {
    try {
      this._data = await this._hass.callWS({ type: "temp_access/list" });
      this._error = null;
    } catch (err) {
      this._error = err?.message || String(err);
    }
    if (this._view !== "new") this._render();
  }

  // ---------- formatting ----------

  _date(ts) {
    return new Intl.DateTimeFormat(this.locale, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(ts * 1000));
  }
  _time(iso) {
    return new Intl.DateTimeFormat(this.locale, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
  }
  _left(ts) {
    const m = Math.max(0, Math.floor((ts * 1000 - Date.now()) / 60000));
    const d = Math.floor(m / 1440), h = Math.floor((m % 1440) / 60), mm = m % 60;
    const t = this.t;
    const dayWord = this.t === T.pl ? (d === 1 ? "dzień" : "dni") : (d === 1 ? "day" : "days");
    if (d) return `${d} ${dayWord} ${h} ${t.h}`;
    if (h) return `${h} ${t.h} ${mm} ${t.m}`;
    return `${mm} ${t.m}`;
  }
  _schedule(s) {
    if (!s) return "";
    const parts = [];
    if (s.days) parts.push(s.days.slice().sort((a, b) => DAYS.indexOf(a) - DAYS.indexOf(b)).map(d => this.t.days[DAYS.indexOf(d)]).join(", "));
    if (s.from) parts.push(`${s.from}–${s.to}`);
    return parts.join(" · ");
  }
  _lastAction(la) {
    if (!la) return this.t.none;
    return la.result === "ok" || la.result === "rejected" ? `${this._describe(la)} · ${this._time(la.time)}` : this.t.none;
  }
  _describe(la) {
    const pl = this.t === T.pl;
    const verbs = pl ? { on: "włączył", off: "wyłączył", press: "użył" } : { on: "turned on", off: "turned off", press: "used" };
    if (la.result === "ok") return pl ? `gość ${verbs[la.action] || la.action}: ${la.control}` : `guest ${verbs[la.action] || la.action}: ${la.control}`;
    const reasons = pl
      ? { expired: "dostęp nieaktywny", outside_schedule: "poza godzinami", limit_reached: "limit użyć", not_allowed: "niedozwolone", error: "błąd urządzenia" }
      : { expired: "access not active", outside_schedule: "outside hours", limit_reached: "use limit", not_allowed: "not allowed", error: "device error" };
    return pl ? `odrzucono (${reasons[la.reason] || la.reason}): ${la.control}` : `rejected (${reasons[la.reason] || la.reason}): ${la.control}`;
  }

  // ---------- events ----------

  async _copy(text, key) {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      const ta = document.createElement("textarea");
      ta.value = text; document.body.appendChild(ta); ta.select();
      try { document.execCommand("copy"); } catch {}
      ta.remove();
    }
    this._toast = key;
    this._render();
    setTimeout(() => { if (this._toast === key) { this._toast = null; this._render(); } }, 1800);
  }

  async _onClick(e) {
    const b = e.target.closest("[data-a]");
    if (!b) return;
    const a = b.dataset.a, id = b.dataset.id;
    const p = this._data?.panels.find(x => x.panel_id === id);
    const t = this.t;
    switch (a) {
      case "menu":
        this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true }));
        break;
      case "new":
        this._form = this._emptyForm();
        this._view = "new";
        this._render();
        this.shadowRoot.querySelector("#f-title")?.focus();
        break;
      case "cancel":
      case "done":
        this._view = "list"; this._form = null; this._result = null;
        this._load();
        break;
      case "qr":
        this._qrOpen.has(id) ? this._qrOpen.delete(id) : this._qrOpen.add(id);
        this._render();
        break;
      case "pin":
        this._pinOpen.has(id) ? this._pinOpen.delete(id) : this._pinOpen.add(id);
        this._render();
        break;
      case "copy-link":
        this._copy(b.dataset.v || p.url, `link-${id}`);
        break;
      case "copy-pin":
        this._copy(b.dataset.v || p.pin, `pin-${id}`);
        break;
      case "ended":
        this._showEnded = !this._showEnded;
        this._render();
        break;
      case "revoke":
        if (!confirm(t.confirmRevoke(p.title))) return;
        try { await this._hass.callWS({ type: "temp_access/revoke", panel_id: id }); }
        catch (err) { alert(err?.code === "portal_unreachable" ? t.portalWarn : err?.message || err); }
        this._load();
        break;
      case "delete":
        if (!confirm(t.confirmDelete(p.title))) return;
        try { await this._hass.callWS({ type: "temp_access/delete", panel_id: id }); }
        catch (err) { alert(err?.message || err); }
        setTimeout(() => this._load(), 800);
        break;
      case "pick": {
        const f = this._form;
        const i = f.selected.findIndex(c => c.entity_id === id);
        if (i >= 0) f.selected.splice(i, 1);
        else f.selected.push(this._newControl(id));
        this._render();
        break;
      }
      case "day": {
        const f = this._form;
        f.days.has(id) ? f.days.delete(id) : f.days.add(id);
        this._render();
        break;
      }
      case "create":
        this._create();
        break;
    }
  }

  _onInput(e) {
    const el = e.target;
    if (!this._form || !el.dataset.f) return;
    const f = this._form, key = el.dataset.f;
    if (el.dataset.i !== undefined) {
      const c = f.selected[Number(el.dataset.i)];
      c[key] = el.type === "checkbox" ? el.checked : el.value;
      if (key === "type" || key === "action") this._render();
      return;
    }
    f[key] = el.value;
    if (key === "search") this._renderPicker();
  }

  // ---------- form ----------

  _emptyForm() {
    return {
      title: "", search: "", selected: [], start: "", dd: "1", hh: "0", mm: "0", days: new Set(), from: "", to: "", pin: "",
      lang: this.t === T.pl ? "pl" : "en", error: null,
    };
  }

  _domain(entity_id) { return entity_id.split(".")[0]; }

  _newControl(entity_id) {
    const dom = this._domain(entity_id);
    const actions = this._data.actions[dom] || ["press"];
    const name = (this._hass.states[entity_id]?.attributes.friendly_name || entity_id).slice(0, 40);
    const type = !this._data.control_domains.includes(dom) ? "sensor" : this._data.switch_domains.includes(dom) ? "switch" : "button";
    return { entity_id, name, type, action: actions[0], pulse: "1", limit: "", show: false };
  }

  _candidates() {
    const q = (this._form.search || "").toLowerCase();
    const domains = this._data.domains;
    return Object.values(this._hass.states)
      .filter(s => domains.includes(this._domain(s.entity_id)))
      .filter(s => !q || s.entity_id.toLowerCase().includes(q) || (s.attributes.friendly_name || "").toLowerCase().includes(q))
      .sort((a, b) => (a.attributes.friendly_name || a.entity_id).localeCompare(b.attributes.friendly_name || b.entity_id, this.locale))
      .slice(0, 60);
  }

  async _create() {
    const f = this._form, t = this.t;
    const err = msg => { f.error = msg; this._render(); };
    if (!f.title.trim()) return err(t.errTitle);
    if (!f.selected.length) return err(t.errEntities);
    if (Boolean(f.from) !== Boolean(f.to)) return err(t.errHours);
    if (f.pin && !/^\d{4,8}$/.test(f.pin)) return err(t.errPin);
    const days = Number(f.dd) || 0, hours = Number(f.hh) || 0, minutes = Number(f.mm) || 0;
    if (days * 1440 + hours * 60 + minutes < 1) return err(t.errDuration);

    const data = {
      title: f.title.trim(),
      duration: { days, hours, minutes },
      language: f.lang,
      notify: false,
      controls: f.selected.map(c => {
        const o = { entity_id: c.entity_id, name: (c.name || "").trim() || undefined, type: c.type };
        if (c.type === "button") o.action = c.action;
        if (c.type === "button" && c.action === "pulse" && c.pulse) o.pulse_seconds = Number(c.pulse);
        if (c.limit && c.type !== "sensor") o.max_uses = Number(c.limit);
        if (c.show && c.type !== "sensor") o.show_state = true;
        return o;
      }),
    };
    if (f.start) data.valid_from = f.start;
    if (f.days.size) data.days = DAYS.filter(d => f.days.has(d));
    if (f.from) { data.time_from = f.from; data.time_to = f.to; }
    if (f.pin) data.pin = f.pin;

    this._busy = true; f.error = null; this._render();
    try {
      const res = await this._hass.callWS({ type: "call_service", domain: "temp_access", service: "create_panel", service_data: data, return_response: true });
      this._result = { ...res.response, title: data.title };
      this._view = "created";
    } catch (e2) {
      f.error = e2?.message || String(e2);
    }
    this._busy = false;
    this._render();
    this._load();
  }

  // ---------- rendering ----------

  _render() {
    if (!this._hass) return;
    const t = this.t;
    const conn = this._data?.entries || [];
    const ok = conn.length && conn.every(c => c.connected);
    const header = `
      <header>
        ${this._narrow ? `<button class="icon" data-a="menu" aria-label="Menu"><svg viewBox="0 0 24 24"><path d="M3,6H21V8H3V6M3,11H21V13H3V11M3,16H21V18H3V16Z"/></svg></button>` : ""}
        <h1>${t.title}</h1>
        ${conn.length ? `<span class="conn ${ok ? "ok" : "bad"}" title="${ok ? t.connected : t.disconnected}"><i></i>${this._narrow ? "" : ok ? t.connected : t.disconnected}</span>` : ""}
        ${this._view === "list" && conn.length ? `<button class="primary" data-a="new">+ ${t.newPanel}</button>` : ""}
      </header>`;
    let body;
    if (this._error) body = `<p class="card err">${esc(this._error)}</p>`;
    else if (!this._data) body = `<p class="muted pad">${t.loading}</p>`;
    else if (!conn.length) body = `<p class="card">${t.noEntry}</p>`;
    else if (this._view === "new") body = this._formHtml();
    else if (this._view === "created") body = this._resultHtml();
    else body = this._listHtml();
    this.shadowRoot.innerHTML = `<style>${STYLE}</style>${header}<main>${body}</main>`;
  }

  _listHtml() {
    const t = this.t;
    const panels = this._data.panels;
    if (!panels.length) return `<div class="card empty"><p>${t.empty}</p><button class="primary" data-a="new">+ ${t.newPanel}</button></div>`;
    const active = panels.filter(p => !ENDED.includes(p.status));
    const ended = panels.filter(p => ENDED.includes(p.status));
    let html = active.map(p => this._panelHtml(p)).join("");
    if (!active.length) html += `<p class="muted pad">${t.empty}</p>`;
    if (ended.length) {
      html += `<button class="link" data-a="ended">${this._showEnded ? t.hideEnded : t.showEnded(ended.length)}</button>`;
      if (this._showEnded) html += `<h2>${t.ended}</h2>` + ended.map(p => this._panelHtml(p)).join("");
    }
    return html;
  }

  _panelHtml(p) {
    const t = this.t, id = p.panel_id;
    const endedP = ENDED.includes(p.status);
    const time = p.status === "not_started"
      ? `${t.starts}: <b>${esc(this._date(p.valid_from))}</b>`
      : `${t.until}: <b>${esc(this._date(p.valid_until))}</b>${endedP ? "" : ` · ${t.left} ${esc(this._left(p.valid_until))}`}`;
    const sched = this._schedule(p.schedule);
    const controls = p.controls.map(c => `<li>${esc(c.name)} <span class="muted">· ${t.type[c.type] || c.type}${c.show_state && c.type !== "sensor" ? ` · ${t.withState}` : ""}${c.max_uses ? ` · ${t.uses(c.uses, c.max_uses)}` : ""}</span></li>`).join("");
    const qrState = p.entities.qr && this._hass.states[p.entities.qr];
    const qrOpen = this._qrOpen.has(id) && qrState?.attributes.entity_picture;
    const pinOpen = this._pinOpen.has(id);
    const toast = k => (this._toast === k ? `<span class="toast">${t.copied}</span>` : "");
    return `
      <article class="card ${endedP ? "ended" : ""}">
        <div class="top">
          <h3>${esc(p.title)}</h3>
          <span class="chip s-${p.status}">${t.status[p.status] || p.status}</span>
        </div>
        <p class="meta">${time}${sched ? `<br>${esc(sched)}` : ""}</p>
        <ul class="controls">${controls}</ul>
        <p class="meta last">${t.lastAction}: ${esc(this._lastAction(p.last_action))}${p.failed_pin ? ` · <span class="warn">${t.failedPin(p.failed_pin)}</span>` : ""}</p>
        ${qrOpen ? `<div class="qr"><img src="${esc(qrState.attributes.entity_picture)}" alt="${t.qr}"><span class="muted small">${esc(p.url)}</span></div>` : ""}
        <div class="actions">
          ${endedP ? "" : `
          ${p.entities.qr ? `<button data-a="qr" data-id="${id}">${qrOpen ? t.hideQr : t.qr}</button>` : ""}
          <button data-a="copy-link" data-id="${id}">${t.copyLink}</button>${toast("link-" + id)}
          <button data-a="pin" data-id="${id}" class="pin">PIN: <b>${pinOpen ? esc(p.pin) : "••••"}</b></button>
          <button data-a="copy-pin" data-id="${id}">${t.copyPin}</button>${toast("pin-" + id)}
          <span class="spacer"></span>
          <button data-a="revoke" data-id="${id}" class="danger">${t.revoke}</button>`}
          ${endedP ? `<span class="spacer"></span>` : ""}
          <button data-a="delete" data-id="${id}" class="quiet">${t.del}</button>
        </div>
      </article>`;
  }

  _pickerHtml() {
    const f = this._form, t = this.t;
    const list = this._candidates();
    if (!list.length) return `<p class="muted small pad">${t.fNoMatch}</p>`;
    return list.map(s => {
      const on = f.selected.some(c => c.entity_id === s.entity_id);
      return `<button type="button" class="pick ${on ? "on" : ""}" data-a="pick" data-id="${esc(s.entity_id)}" aria-pressed="${on}">
        <span class="box">${on ? "✓" : ""}</span>
        <span><span class="pname">${esc(s.attributes.friendly_name || s.entity_id)}</span><span class="muted small">${esc(s.entity_id)}</span></span></button>`;
    }).join("");
  }

  _renderPicker() {
    const box = this.shadowRoot.querySelector("#picker");
    if (box) box.innerHTML = this._pickerHtml();
  }

  _formHtml() {
    const f = this._form, t = this.t, d = this._data;
    const ctrl = f.selected.map((c, i) => {
      const dom = this._domain(c.entity_id);
      const actions = d.actions[dom] || ["press"];
      const canSwitch = d.switch_domains.includes(dom);
      const canControl = d.control_domains.includes(dom);
      const canRead = d.read_domains.includes(dom);
      const kinds = [...(canSwitch ? ["switch"] : []), ...(canControl ? ["button"] : []), ...(canRead ? ["sensor"] : [])];
      return `
        <div class="ctrl">
          <div class="ctrl-h"><b>${esc(c.entity_id)}</b><button type="button" class="quiet small" data-a="pick" data-id="${esc(c.entity_id)}">✕</button></div>
          <div class="grid">
            <label>${t.fName}<input data-f="name" data-i="${i}" value="${esc(c.name)}" maxlength="40"></label>
            ${kinds.length > 1 ? `<label>${t.fType}<select data-f="type" data-i="${i}">${kinds.map(o => `<option value="${o}" ${c.type === o ? "selected" : ""}>${t.typeLong[o]}</option>`).join("")}</select></label>` : `<label>${t.fType}<input value="${t.typeLong[c.type]}" disabled></label>`}
            ${c.type === "button" && actions.length > 1 ? `<label>${t.fAction}<select data-f="action" data-i="${i}">${actions.map(o => `<option value="${o}" ${c.action === o ? "selected" : ""}>${t.actions[o]}</option>`).join("")}</select></label>` : ""}
            ${c.type === "button" && c.action === "pulse" ? `<label>${t.fPulse}<input type="number" min="0.2" max="30" step="0.1" data-f="pulse" data-i="${i}" value="${esc(c.pulse)}"></label>` : ""}
            ${c.type !== "sensor" ? `<label>${t.fLimit}<input type="number" min="1" max="1000" step="1" data-f="limit" data-i="${i}" value="${esc(c.limit)}" placeholder="${t.fLimitPh}"></label>` : ""}
          </div>
          ${c.type !== "sensor" && canRead ? `<label class="check"><input type="checkbox" data-f="show" data-i="${i}" ${c.show ? "checked" : ""}> ${t.fShowState}</label>` : ""}
        </div>`;
    }).join("");
    return `
      <section class="card form">
        <h2>${t.formTitle}</h2>
        <label>${t.fTitle}<input id="f-title" data-f="title" value="${esc(f.title)}" maxlength="80" placeholder="${t.fTitlePh}"></label>

        <h3>${t.fEntities}</h3>
        <input class="search" data-f="search" value="${esc(f.search)}" placeholder="${t.fSearch}" type="search">
        <div id="picker" class="picker">${this._pickerHtml()}</div>
        ${f.selected.length ? `<h3>${t.fControls}</h3>${ctrl}` : ""}

        <h3>${t.fWhen}</h3>
        <div class="grid">
          <label>${t.fStart} <span class="muted small">(${t.fStartHint})</span><input type="datetime-local" data-f="start" value="${esc(f.start)}"></label>
          <fieldset><legend>${t.fDuration}</legend>
            <div class="dur">
              <label><input type="number" min="0" max="730" data-f="dd" value="${esc(f.dd)}"> ${t.d}</label>
              <label><input type="number" min="0" max="23" data-f="hh" value="${esc(f.hh)}"> ${t.h}</label>
              <label><input type="number" min="0" max="59" data-f="mm" value="${esc(f.mm)}"> ${t.m}</label>
            </div>
          </fieldset>
        </div>

        <h3>${t.fLimits}</h3>
        <fieldset><legend>${t.fDays}</legend>
          <div class="days">${DAYS.map((dd, i) => `<button type="button" class="day ${f.days.has(dd) ? "on" : ""}" data-a="day" data-id="${dd}" aria-pressed="${f.days.has(dd)}">${t.days[i]}</button>`).join("")}</div>
        </fieldset>
        <div class="grid">
          <label>${t.fFrom}<input type="time" data-f="from" value="${esc(f.from)}"></label>
          <label>${t.fTo}<input type="time" data-f="to" value="${esc(f.to)}"></label>
          <label>${t.fPin}<input inputmode="numeric" maxlength="8" data-f="pin" value="${esc(f.pin)}" placeholder="${t.fPinPh}"></label>
          <label>${t.fLang}<select data-f="lang"><option value="pl" ${f.lang === "pl" ? "selected" : ""}>Polski</option><option value="en" ${f.lang === "en" ? "selected" : ""}>English</option></select></label>
        </div>

        ${f.error ? `<p class="err" role="alert">${esc(f.error)}</p>` : ""}
        <div class="actions end">
          <button data-a="cancel" class="quiet">${t.cancel}</button>
          <button data-a="create" class="primary" ${this._busy ? "disabled" : ""}>${this._busy ? t.creating : t.create}</button>
        </div>
      </section>`;
  }

  _resultHtml() {
    const r = this._result, t = this.t;
    const p = this._data?.panels.find(x => x.panel_id === r.panel_id);
    const qr = p?.entities.qr && this._hass.states[p.entities.qr]?.attributes.entity_picture;
    const toast = k => (this._toast === k ? `<span class="toast">${t.copied}</span>` : "");
    return `
      <section class="card result">
        <h2>${t.created}: ${esc(r.title)}</h2>
        <p class="muted">${t.createdHint}</p>
        <div class="res-grid">
          <div>
            <p class="lbl">${t.link}</p>
            <p class="mono">${esc(r.panel_url)}</p>
            <div class="actions"><button data-a="copy-link" data-id="new" data-v="${esc(r.panel_url)}">${t.copyLink}</button>${toast("link-new")}</div>
            <p class="lbl">PIN</p>
            <p class="mono big">${esc(r.pin)}</p>
            <div class="actions"><button data-a="copy-pin" data-id="new" data-v="${esc(r.pin)}">${t.copyPin}</button>${toast("pin-new")}</div>
          </div>
          ${qr ? `<div class="qr"><img src="${esc(qr)}" alt="${t.qr}"></div>` : `<div class="qr placeholder muted small">${t.loading}</div>`}
        </div>
        <div class="actions end"><button class="primary" data-a="done">${t.done}</button></div>
      </section>`;
  }
}

const STYLE = `
:host{display:block;min-height:100vh;background:var(--primary-background-color);color:var(--primary-text-color);font-family:var(--paper-font-body1_-_font-family, var(--ha-font-family-body, Roboto, sans-serif))}
header{position:sticky;top:0;z-index:2;display:flex;align-items:center;gap:12px;height:56px;padding:0 16px;background:var(--app-header-background-color);color:var(--app-header-text-color, var(--text-primary-color));border-bottom:var(--app-header-border-bottom, none)}
header h1{flex:1;font-size:20px;font-weight:400;margin:0}

.icon{background:none;border:0;padding:8px;margin-left:-8px;color:inherit;cursor:pointer;border-radius:50%}
.icon svg{width:24px;height:24px;fill:currentColor;display:block}
.conn{display:inline-flex;align-items:center;gap:6px;font-size:13px;opacity:.9}
.conn i{width:9px;height:9px;border-radius:50%;background:var(--success-color,#43a047)}
.conn.bad i{background:var(--error-color,#db4437)}
main{max-width:860px;margin:0 auto;padding:16px 16px 48px}
.card{background:var(--ha-card-background, var(--card-background-color));border-radius:var(--ha-card-border-radius,12px);border:var(--ha-card-border-width,1px) solid var(--ha-card-border-color, var(--divider-color));box-shadow:var(--ha-card-box-shadow,none);padding:16px;margin:0 0 12px}
.card.ended{opacity:.75}
.top{display:flex;align-items:flex-start;gap:12px;justify-content:space-between}
h2{font-size:18px;font-weight:500;margin:4px 0 12px}
h3{font-size:16px;font-weight:500;margin:0}
.form h3{margin:20px 0 8px;font-size:15px}
.chip{flex:none;font-size:12px;font-weight:500;border-radius:999px;padding:3px 10px;background:var(--secondary-background-color);color:var(--secondary-text-color);white-space:nowrap}
.s-active{background:rgba(67,160,71,.16);color:var(--success-color,#2e7d32)}
.s-not_started,.s-outside_schedule{background:rgba(255,152,0,.16);color:var(--warning-color,#e65100)}
.s-locked{background:rgba(219,68,55,.14);color:var(--error-color,#c62828)}
.meta{margin:6px 0 0;color:var(--secondary-text-color);font-size:14px;line-height:1.5}
.meta b{color:var(--primary-text-color);font-weight:500}
.last{margin-top:8px}
.warn{color:var(--error-color)}
.controls{list-style:none;margin:10px 0 0;padding:0;display:flex;flex-wrap:wrap;gap:6px}
.controls li{font-size:14px;background:var(--secondary-background-color);border-radius:8px;padding:4px 10px}
.muted{color:var(--secondary-text-color)}
.small{font-size:12px}
.pad{padding:8px 4px}
.actions{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin-top:14px}
.actions.end{justify-content:flex-end}
.spacer{flex:1}
button{font:inherit;font-size:14px;font-weight:500;color:var(--primary-color);background:transparent;border:1px solid var(--divider-color);border-radius:18px;min-height:36px;padding:0 14px;cursor:pointer}
button:hover{background:rgba(127,127,127,.08)}
button:focus-visible,input:focus-visible,select:focus-visible{outline:2px solid var(--primary-color);outline-offset:2px}
button.primary{background:var(--primary-color);color:var(--text-primary-color,#fff);border-color:transparent}
button.danger{color:var(--error-color)}
button.quiet{border-color:transparent;color:var(--secondary-text-color)}
button.link{border:0;padding:0 4px;min-height:32px;color:var(--primary-color);margin:4px 0 12px}
button:disabled{opacity:.5;cursor:default}
button.pin b{font-family:ui-monospace,monospace;letter-spacing:.1em}
.toast{font-size:12px;color:var(--success-color,#2e7d32)}
.qr{display:flex;flex-direction:column;align-items:center;gap:6px;margin-top:14px}
.qr img{width:220px;height:220px;image-rendering:pixelated;background:#fff;border-radius:8px;padding:6px}
.qr.placeholder{width:220px;height:220px;justify-content:center;border:1px dashed var(--divider-color);border-radius:8px}
.empty{text-align:center;padding:32px 16px}
.empty p{margin:0 0 16px;color:var(--secondary-text-color)}
.err{color:var(--error-color)}
label{display:flex;flex-direction:column;gap:4px;font-size:13px;color:var(--secondary-text-color)}
input,select{font:inherit;font-size:15px;color:var(--primary-text-color);background:var(--secondary-background-color, rgba(127,127,127,.08));border:1px solid var(--divider-color);border-radius:8px;min-height:40px;padding:6px 10px;box-sizing:border-box;width:100%}
input[type=number]{max-width:110px}
.form > label{margin-bottom:4px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:12px;align-items:end}
fieldset{border:0;padding:0;margin:0}
legend{font-size:13px;color:var(--secondary-text-color);padding:0;margin-bottom:4px}
.dur{display:flex;gap:8px}
.dur label{flex-direction:row;align-items:center;gap:6px;font-size:14px;color:var(--primary-text-color)}
.dur input{width:72px}
.days{display:flex;flex-wrap:wrap;gap:6px;margin-bottom:12px}
.day{min-width:44px;padding:0 8px}
.day.on,.pick.on .box{background:var(--primary-color);color:var(--text-primary-color,#fff);border-color:transparent}
.search{margin-bottom:6px}
.picker{max-height:260px;overflow:auto;border:1px solid var(--divider-color);border-radius:8px;padding:4px}
.pick{display:flex;align-items:center;gap:10px;width:100%;border:0;border-radius:6px;text-align:left;padding:6px 8px;min-height:44px;color:var(--primary-text-color)}
.pick .box{flex:none;width:20px;height:20px;border:2px solid var(--divider-color);border-radius:4px;display:grid;place-items:center;font-size:13px}
.pick span span{display:block}
.pname{font-size:14px}
label.check{flex-direction:row;align-items:center;gap:8px;margin-top:10px;font-size:14px;color:var(--primary-text-color)}
label.check input{width:18px;min-height:18px;height:18px;margin:0;accent-color:var(--primary-color)}
.ctrl{border:1px solid var(--divider-color);border-radius:8px;padding:10px 12px;margin-bottom:8px}
.ctrl-h{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;font-size:13px}
.ctrl-h button{min-height:28px;padding:0 8px}
.res-grid{display:flex;flex-wrap:wrap;gap:24px;align-items:flex-start}
.res-grid > div:first-child{flex:1;min-width:240px}
.lbl{margin:12px 0 2px;font-size:13px;color:var(--secondary-text-color)}
.mono{font-family:ui-monospace,monospace;word-break:break-all;margin:0}
.mono.big{font-size:28px;letter-spacing:.15em}
header button.primary{background:rgba(255,255,255,.18);color:var(--app-header-text-color,#fff);border:1px solid rgba(255,255,255,.45)}
header button.primary:hover{background:rgba(255,255,255,.28)}
@media (max-width:600px){main{padding:12px 8px 40px}.card{padding:14px}.actions .spacer{display:none}}
`;

customElements.define("temp-access-panel", TempAccessPanel);
