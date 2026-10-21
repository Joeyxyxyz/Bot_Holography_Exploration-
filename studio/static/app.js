"use strict";
// Holo Studio page. Talks only to its own server (token in the <meta> tag); builds every piece of text with
// textContent, never innerHTML.
(() => {
  const TOKEN = document.querySelector('meta[name="holo-token"]').content;
  const $ = (id) => document.getElementById(id);

  const store = {
    get(k, d) {
      try { const v = localStorage.getItem("holo." + k); return v === null ? d : JSON.parse(v); } catch { return d; }
    },
    set(k, v) { try { localStorage.setItem("holo." + k, JSON.stringify(v)); } catch { /* private mode */ } },
  };

  const DEFAULTS = { seconds: 30, speed: 1, brightness: 1, size: 1, mode: "ab", L: 30 };
  let CAT = null;                       // catalogue from the server
  let STATE = null;                     // last state snapshot
  let current = null;                   // selected scene id
  let view = store.get("view", "simulated");
  const settings = Object.assign({}, DEFAULTS, store.get("settings", {}));
  let playlist = store.get("playlist", []);
  let myJob = null;                     // id of the job this page started (closing the page stops only that job)
  let wasBusy = false;
  let infoDismissed = false;

  async function api(path, body, extra) {
    const opt = body === undefined
      ? { headers: { "X-Holo-Token": TOKEN } }
      : Object.assign({ method: "POST", headers: { "X-Holo-Token": TOKEN, "Content-Type": "application/json" },
                        body: JSON.stringify(body) }, extra || {});
    try {
      const r = await fetch(path, opt);
      let data = {};
      try { data = await r.json(); } catch { /* empty body */ }
      return { ok: r.ok, status: r.status, data };
    } catch (e) {
      return { ok: false, status: 0, data: { error: "The studio is not reachable. Is it still running?" } };
    }
  }

  const el = (tag, cls, text) => {
    const e = document.createElement(tag);
    if (cls) e.className = cls;
    if (text !== undefined) e.textContent = text;
    return e;
  };
  const fmtS = (s) => {
    s = Math.max(0, Math.round(s || 0));
    return s >= 60 ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")} min` : `${s} s`;
  };
  const clamp = (v, lo, hi, d) => (typeof v === "number" && isFinite(v) ? Math.min(hi, Math.max(lo, v)) : d);

  // ------------------------------------------------------------- banner and announcements
  let bannerIsError = false;
  function banner(msg, isError) {
    const b = $("banner");
    bannerIsError = !!(msg && isError);
    b.classList.toggle("error", bannerIsError);
    if (!msg) { b.hidden = true; return; }
    b.querySelector(".msg").textContent = msg;
    b.hidden = false;
  }
  function infoBanner() {                // the standing note in preview-only mode
    if (STATE && !STATE.hardware && !bannerIsError && !infoDismissed) {
      banner("Preview only: this studio was started with DLP_NO_HARDWARE=1. Scenes preview and simulate here; playing on the projector is off.");
    }
  }
  function announce(text) { $("announce").textContent = text; }

  // ------------------------------------------------------------- catalogue and scene list
  function sanitizeSettings() {
    const lim = CAT.limits;
    settings.seconds = clamp(settings.seconds, 5, Math.min(300, lim.seconds[1]), DEFAULTS.seconds);
    for (const k of ["speed", "brightness", "size", "L"]) settings[k] = clamp(settings[k], lim[k][0], lim[k][1], DEFAULTS[k]);
    if (settings.mode !== "ab" && settings.mode !== "b") settings.mode = "ab";
    store.set("settings", settings);
  }

  function sanitizePlaylist() {
    const lim = CAT.limits;
    playlist = (Array.isArray(playlist) ? playlist : [])
      .filter((it) => it && CAT.scenes[it.scene])
      .slice(0, CAT.max_playlist_items)
      .map((it) => ({
        scene: it.scene,
        seconds: clamp(it.seconds, lim.seconds[0], lim.seconds[1], 20),
        speed: clamp(it.speed, lim.speed[0], lim.speed[1], 1),
        brightness: clamp(it.brightness, lim.brightness[0], lim.brightness[1], 1),
        size: clamp(it.size, lim.size[0], lim.size[1], 1),
        mode: it.mode === "b" ? "b" : "ab",
        L: clamp(it.L, lim.L[0], lim.L[1], 30),
      }));
  }

  async function loadCatalog() {
    const r = await api("/api/catalog");
    if (!r.ok) { banner(r.data.error || "Could not load the scenes.", true); return; }
    CAT = r.data;
    sanitizeSettings();
    sanitizePlaylist();
    bindControls();
    const g = $("groups");
    g.textContent = "";
    for (const grp of CAT.groups) {
      const box = el("div", "group");
      box.append(el("h3", "", grp.title), el("p", "blurb", grp.blurb));
      for (const id of grp.scenes) {
        const sc = CAT.scenes[id];
        const b = el("button", "scene-btn");
        b.type = "button";
        b.dataset.scene = id;
        b.append(el("span", "t", sc.title));
        if (sc.favourite) b.append(el("span", "badge fav", "★"));
        if (sc.camera) b.append(el("span", "badge", "camera"));
        b.title = sc.description;
        b.setAttribute("aria-label", `${sc.title}${sc.favourite ? ", favourite" : ""}${sc.camera ? ", has a camera capture" : ""}`);
        b.addEventListener("click", () => select(id));
        box.append(b);
      }
      g.append(box);
    }
    $("grid-seconds").min = CAT.grid_seconds[0];
    $("grid-seconds").max = CAT.grid_seconds[1];
    const saved = store.get("scene", "ribbon");
    select(CAT.scenes[saved] ? saved : "ribbon");
    renderPlaylist(true);
  }

  function select(id) {
    current = id;
    store.set("scene", id);
    const sc = CAT.scenes[id];
    for (const b of document.querySelectorAll(".scene-btn")) {
      b.setAttribute("aria-current", b.dataset.scene === id ? "true" : "false");
    }
    $("scene-title").textContent = sc.title;
    $("scene-desc").textContent = sc.description;
    const tags = $("scene-tags");
    tags.textContent = "";
    if (sc.favourite) tags.append(el("span", "tag fav", "★ looked best by eye"));
    tags.append(el("span", "tag", `loop ${sc.period_s} s`));
    if (sc.needs_warp) tags.append(el("span", "tag warn", "needs the case unmoved since 2026-10-05"));
    if (sc.needs_fit) tags.append(el("span", "tag warn", "depends on the case fit"));
    $("size-ctl").hidden = !sc.size_knob;
    $("tab-camera").hidden = !sc.camera;
    $("canvas").setAttribute("aria-label", `Animated preview of ${sc.title}`);
    anim.data = null;                                          // never show the previous scene under the spinner
    $("viewer-note").textContent = "";
    if (view === "camera" && !sc.camera) setView("simulated", false);
    requestPreview();
  }

  // ------------------------------------------------------------- previews
  const anim = { data: null, img: null, start: performance.now() };
  let previewSeq = 0;
  let previewDebounce = null;

  function setView(v, fetch = true) {
    view = v;
    store.set("view", v);
    for (const t of document.querySelectorAll('[role="tab"]')) {
      const on = t.dataset.view === v;
      t.setAttribute("aria-selected", on ? "true" : "false");
      t.tabIndex = on ? 0 : -1;
      if (on) $("viewer").setAttribute("aria-labelledby", t.id);
    }
    if (fetch) requestPreview();
  }

  function viewerMsg(text, spin) {
    const m = $("viewer-msg");
    if (!text) { m.hidden = true; return; }
    m.querySelector(".txt").textContent = text;
    m.querySelector(".spinner").hidden = !spin;
    m.hidden = false;
  }

  function previewQuery() {
    return new URLSearchParams({ scene: current, mode: settings.mode, brightness: settings.brightness,
                                 size: settings.size, L: settings.L }).toString();
  }

  async function requestPreview() {
    if (!current) return;
    const seq = ++previewSeq;
    const cam = $("camera-img");
    const canvas = $("canvas");
    if (view === "camera") {
      anim.data = null;
      canvas.hidden = true;
      cam.hidden = false;
      cam.src = `/figures/${encodeURIComponent(current)}`;
      viewerMsg("");
      $("viewer-note").textContent = "Real stop-motion capture from the bench camera (16 frames held one at a time, "
        + "brightness-stretched), 2026-10-05.";
      return;
    }
    cam.hidden = true;
    canvas.hidden = false;
    const kind = view;
    const path = kind === "pattern" ? "/api/preview" : "/api/simulate";
    for (;;) {
      const r = await api(`${path}?${previewQuery()}`);
      if (seq !== previewSeq) return;                         // a newer request took over
      if (r.status === 202) {
        const pct = Math.round(100 * (r.data.progress || 0));
        viewerMsg(kind === "pattern" ? `Drawing the mirror pattern… ${pct}%`
                                     : `Simulating the light in the case… ${pct}%`, true);
        await new Promise((res) => setTimeout(res, 500));
        if (seq !== previewSeq) return;
        continue;
      }
      if (!r.ok) { viewerMsg(r.data.error || "Preview failed.", false); return; }
      const img = new Image();
      img.onload = () => {
        if (seq !== previewSeq) return;
        anim.data = r.data;
        anim.img = img;
        const L = r.data.layout;
        canvas.width = L.w;
        canvas.height = L.h;
        viewerMsg(r.data.kind === "pattern" && !r.data.lit
          ? "Nothing lit at this brightness: the projector cannot show light this dim. Raise the brightness." : "");
        $("viewer-note").textContent = r.data.kind === "pattern"
          ? "What the mirrors send (blue only), drawn in true proportions. Each lit mirror becomes a ray of glowing light in the liquid."
          : r.data.note;
        // queue the other view in the background so switching tabs is quick
        api(`${kind === "pattern" ? "/api/simulate" : "/api/preview"}?${previewQuery()}`);
      };
      img.src = r.data.sprite;
      return;
    }
  }

  function drawTile(ctx, k, alpha) {
    const L = anim.data.layout;
    const c = k % L.count;
    const sx = (c % L.cols) * L.w;
    const sy = Math.floor(c / L.cols) * L.h;
    ctx.globalAlpha = alpha;
    ctx.drawImage(anim.img, sx, sy, L.w, L.h, 0, 0, L.w, L.h);
    ctx.globalAlpha = 1;
  }

  function overlay(ctx) {
    const d = anim.data;
    const canvas = ctx.canvas;
    const scale = canvas.clientWidth ? canvas.width / canvas.clientWidth : 1;     // keep labels ~13 px on screen
    ctx.font = `600 ${Math.round(13 * Math.max(1, scale))}px system-ui, sans-serif`;
    ctx.textBaseline = "top";
    if (d.kind === "pattern") {
      ctx.setLineDash([4, 6]);
      ctx.strokeStyle = "rgba(255,255,255,0.22)";
      ctx.fillStyle = "rgba(255,255,255,0.6)";
      for (const g of d.guides) {
        for (const x of [g.x0, g.x1]) {
          ctx.beginPath(); ctx.moveTo(x + 0.5, 0); ctx.lineTo(x + 0.5, d.layout.h); ctx.stroke();
        }
        const w = ctx.measureText(g.label).width;
        ctx.fillText(g.label, (g.x0 + g.x1) / 2 - w / 2, 6);
      }
      ctx.setLineDash([]);
    } else {
      ctx.fillStyle = "rgba(255,255,255,0.65)";
      for (const v of d.views) ctx.fillText(v.label, v.x0 + 8, 8);
    }
  }

  function frame(now) {
    const canvas = $("canvas");
    if (!canvas.hidden) {
      const ctx = canvas.getContext("2d");
      if (anim.data && anim.img) {
        const L = anim.data.layout;
        const loop = Math.max(0.05, anim.data.loop_s / settings.speed);
        const pos = (((now - anim.start) / 1000) % loop) / loop * L.count;
        const k = Math.floor(pos);
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, L.w, L.h);
        drawTile(ctx, k, 1);
        if (L.count > 1) drawTile(ctx, k + 1, pos - k);    // cross-fade: smooth motion from few frames
        overlay(ctx);
      } else {
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, canvas.width, canvas.height);
      }
    }
    requestAnimationFrame(frame);
  }

  // ------------------------------------------------------------- controls
  const outputs = {
    seconds: (v) => fmtS(v),
    speed: (v) => `${(+v).toFixed(2).replace(/0$/, "")}×`,
    brightness: (v) => `${Math.round(v * 100)} %`,
    size: (v) => `${Math.round(v * 100)} %`,
    L: (v) => `${v} mm`,
  };

  let bound = false;
  function bindControls() {
    if (bound) return;
    bound = true;
    for (const k of Object.keys(outputs)) {
      const inp = $(k);
      inp.value = settings[k];
      $(`${k}-out`).textContent = outputs[k](settings[k]);
      inp.addEventListener("input", () => {
        settings[k] = parseFloat(inp.value);
        $(`${k}-out`).textContent = outputs[k](settings[k]);
        store.set("settings", settings);
        if (k === "brightness" || k === "size" || k === "L") {
          clearTimeout(previewDebounce);
          previewDebounce = setTimeout(requestPreview, 350);
        }
      });
    }
    for (const r of document.querySelectorAll('input[name="mode"]')) {
      r.checked = r.value === settings.mode;
      r.addEventListener("change", () => {
        settings.mode = r.value;
        store.set("settings", settings);
        requestPreview();
      });
    }
    const tabs = [...document.querySelectorAll('[role="tab"]')];
    for (const t of tabs) {
      t.addEventListener("click", () => setView(t.dataset.view));
      t.addEventListener("keydown", (e) => {                    // arrow keys move between visible tabs
        if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
        const vis = tabs.filter((x) => !x.hidden);
        const i = vis.indexOf(t) + (e.key === "ArrowRight" ? 1 : -1);
        const next = vis[(i + vis.length) % vis.length];
        next.focus();
        setView(next.dataset.view);
        e.preventDefault();
      });
    }
    setView(view === "camera" ? "simulated" : view, false);
    $("play").addEventListener("click", play);
    $("add").addEventListener("click", addToPlaylist);
    $("pl-play").addEventListener("click", playPlaylist);
    $("pl-clear").addEventListener("click", () => { playlist = []; banner(""); infoBanner(); renderPlaylist(true); });
    $("pl-demo").addEventListener("click", loadDemo);
    $("grid").addEventListener("click", showGrid);
    $("grid-seconds").addEventListener("input", updateButtons);
  }

  // STOP, Esc and closing the page work from the first moment, even if the scene list failed to load
  function bindSafety() {
    $("stop").addEventListener("click", stop);
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && !e.repeat) { e.preventDefault(); stop(); }
    });
    window.addEventListener("pagehide", () => {               // closing or reloading the page stops its job
      if (myJob && STATE && STATE.busy && STATE.job === myJob) api("/api/stop", { job: myJob }, { keepalive: true });
    });
    $("banner").querySelector(".close").addEventListener("click", () => {
      if (!bannerIsError) infoDismissed = true;               // the preview-only note stays closed
      banner("");
      infoBanner();
    });
    document.addEventListener("visibilitychange", () => {
      if (!document.hidden) api("/api/check-rig", {}).then(poll);
    });
  }

  // ------------------------------------------------------------- actions
  function sceneBody(extra) {
    return Object.assign({ scene: current, seconds: settings.seconds, speed: settings.speed,
                           brightness: settings.brightness, size: settings.size, mode: settings.mode,
                           L: settings.L }, extra || {});
  }

  async function post(path, body, what) {
    banner("");
    const r = await api(path, body);
    if (!r.ok) banner(r.data.error || `Could not ${what}.`, true);
    else { myJob = r.data.job || null; wasBusy = true; }
    infoBanner();
    poll();
    return r;
  }

  const play = () => post("/api/play", sceneBody(), "start playing");

  function gridSeconds() {
    const v = parseFloat($("grid-seconds").value);
    const [lo, hi] = CAT ? CAT.grid_seconds : [5, 600];
    return isFinite(v) && v >= lo && v <= hi ? v : null;
  }
  function showGrid() {
    const s = gridSeconds();
    if (s === null) return;
    post("/api/grid", { seconds: s }, "show the grid");
  }

  async function stop() {
    $("status").textContent = lastStatus = "Stopping…";
    const r = await api("/api/stop", {});
    if (!r.ok) banner(r.data.error || "Could not reach the studio to stop. Press Ctrl+C in its console.", true);
    poll();
  }

  // ------------------------------------------------------------- playlist
  function addToPlaylist() {
    if (!current || !CAT) return;
    if (playlist.length >= CAT.max_playlist_items) { banner("The playlist is full.", true); return; }
    playlist.push(sceneBody());
    renderPlaylist(true);
  }

  function loadDemo() {
    playlist = CAT.demo.map((id) => ({ scene: id, seconds: 20, speed: 1, brightness: 1, size: 1, mode: "ab", L: 30 }));
    banner(""); infoBanner();
    renderPlaylist(true);
  }

  function playPlaylist() {
    if (!playlist.length) return;
    post("/api/playlist", { items: playlist }, "start the playlist");
  }

  const playlistTotal = () => playlist.reduce((a, it) => a + it.seconds, 0);
  let playlistSig = "";
  function renderPlaylist(force) {
    const now = STATE && STATE.now && STATE.now.kind === "playlist" ? STATE.now.index : 0;
    const sig = JSON.stringify([playlist, now]);
    if (!force && sig === playlistSig) return;                // keep focus on the list between polls
    playlistSig = sig;
    store.set("playlist", playlist);
    const ol = $("playlist");
    ol.textContent = "";
    playlist.forEach((it, i) => {
      const sc = CAT && CAT.scenes[it.scene];
      const title = sc ? sc.title : it.scene;
      const li = el("li", i + 1 === now ? "now" : "");
      li.append(el("span", "", title), el("span", "meta", ` · ${fmtS(it.seconds)}`
        + (it.speed !== 1 ? ` · ${it.speed}×` : "") + (it.mode === "b" ? " · face B" : "")));
      const x = el("button", "", "✕");
      x.type = "button";
      x.title = "Remove";
      x.setAttribute("aria-label", `Remove ${title} from the playlist`);
      x.addEventListener("click", () => { playlist.splice(i, 1); renderPlaylist(true); });
      li.append(x);
      ol.append(li);
    });
    $("pl-empty").hidden = playlist.length > 0;
    const total = playlistTotal();
    const max = CAT ? CAT.max_playlist_s : 1800;
    $("pl-total").textContent = playlist.length
      ? `${playlist.length} scene${playlist.length > 1 ? "s" : ""}, ${fmtS(total)} in total`
        + (total > max ? ` (over the ${fmtS(max)} limit: remove some)` : "") : "";
    updateButtons();
  }

  // ------------------------------------------------------------- state
  function statusOf(s) {
    if (!s) return ["Connecting…", ""];
    const n = s.now || {};
    const part = n.count > 1 ? ` (${n.index}/${n.count})` : "";
    switch (s.activity) {
      case "queued": return [`Starting ${n.title || ""}${part}…`, "live"];
      case "preparing": return [`Preparing ${n.title}${part} · ${Math.round(100 * (n.render || 0))}%`, "live"];
      case "playing": return [`Playing ${n.title}${part} · ${fmtS(n.elapsed)} of ${fmtS(n.seconds)}`, "live"];
      case "holding": return [`Showing the grid · ${fmtS(n.elapsed)} of ${fmtS(n.seconds)}`, "live"];
      default: break;
    }
    if (!s.hardware) return ["Preview only · projector off", "off"];
    if (s.rig.free === false) return ["Projector in use by another program", "busy"];
    return ["Ready", "ok"];
  }

  function updateButtons() {
    const s = STATE;
    const live = !!(s && s.hardware);
    const busy = !!(s && s.busy);
    const max = CAT ? CAT.max_playlist_s : 1800;
    $("play").disabled = !live || busy;
    $("grid").disabled = !live || busy || gridSeconds() === null;
    $("pl-play").disabled = !live || busy || !playlist.length || playlistTotal() > max;
    $("grid-hint").textContent = gridSeconds() === null && CAT
      ? `Hold for ${CAT.grid_seconds[0]}–${CAT.grid_seconds[1]} s.` : "";
    $("play-hint").textContent = !s ? "" : !s.hardware
      ? "Preview only: this studio cannot drive the projector."
      : busy ? "Something is playing. Press STOP (or Esc) first."
      : s.rig.free === false ? `The projector and camera are in use by another program (${s.rig.holder}). Wait for it to finish.`
      : "Plays on the projector. Its window opens on the projector's screen; STOP or Esc ends it.";
  }

  let lastStatus = "";
  let lastActivity = "";
  function renderState() {
    const s = STATE;
    const [text, cls] = statusOf(s);
    const st = $("status");
    if (text !== lastStatus) { st.textContent = text; lastStatus = text; }
    st.className = `status ${cls}`;
    if (s && s.activity !== lastActivity) {                     // announce changes, not every tick
      const n = s.now || {};
      const what = { queued: `Starting ${n.title || ""}`, preparing: `Preparing ${n.title || ""}`,
                     playing: `Playing ${n.title || ""}`, holding: "Showing the grid",
                     idle: s.last ? `${LAST[s.last.status] || s.last.status}` : "Ready" }[s.activity];
      if (lastActivity) announce(what || "");
      lastActivity = s.activity;
    }
    const pr = $("progress");
    const n = (s && s.now) || {};
    if (s && (s.activity === "preparing" || s.activity === "playing" || s.activity === "holding")) {
      const f = s.activity === "preparing" ? (n.render || 0) : Math.min(1, (n.elapsed || 0) / (n.seconds || 1));
      pr.hidden = false;
      pr.querySelector(".bar").style.width = `${Math.round(100 * f)}%`;
      pr.querySelector(".ptext").textContent = s.activity === "preparing" ? "preparing frames"
        : `${n.fps ? "target " + n.fps + " fps · " : ""}${n.dropped || 0} late frames`;
    } else {
      pr.hidden = true;
    }
    infoBanner();
    renderLast(s && s.last);
    renderLog(s ? s.log : []);
    renderPlaylist(false);
    updateButtons();
  }

  const LAST = { done: "Finished", stopped: "Stopped", busy: "Projector busy", refused: "Refused by a safety check",
                 error: "Error" };

  let lastSig = "";
  function renderLast(last) {
    const sig = JSON.stringify(last || null);
    if (sig === lastSig) return;
    lastSig = sig;
    const box = $("last");
    box.textContent = "";
    if (!last) { box.append(el("p", "muted", "Nothing played yet.")); return; }
    const head = el("div", "item");
    head.append(el("span", `st ${last.status}`, LAST[last.status] || last.status), el("span", "muted", ` at ${last.t}`));
    box.append(head);
    if (last.message) box.append(el("div", "item", last.message));
    for (const r of last.results || []) {
      box.append(el("div", "item",
        `${r.title}: ${r.achieved_fps} fps, ${r.dropped} late frame${r.dropped === 1 ? "" : "s"}, ${r.seconds} s`));
    }
  }

  let logSig = "";
  function renderLog(log) {
    const sig = log.length ? `${log.length}:${log[log.length - 1].t}:${log[log.length - 1].msg}` : "";
    if (sig === logSig) return;
    logSig = sig;
    const ol = $("log");
    ol.textContent = "";
    for (const e of [...log].reverse()) ol.append(el("li", "", `${e.t}  ${e.msg}`));
  }

  let pollTimer = null;
  let polling = false;
  async function poll() {
    clearTimeout(pollTimer);
    if (polling) { pollTimer = setTimeout(poll, 150); return; }   // one request in flight at a time
    polling = true;
    const r = await api("/api/state");
    polling = false;
    if (r.ok) {
      STATE = r.data;
      if (myJob && STATE.job !== myJob) myJob = null;           // our job ended (or was never seen running)
      if (wasBusy && !STATE.busy) api("/api/check-rig", {});    // a job just ended: refresh the rig status
      wasBusy = STATE.busy;
      renderState();
    } else {
      const st = $("status");
      st.textContent = lastStatus = r.status === 403 ? "Session expired: reload the page" : "Studio not reachable";
      st.className = "status busy";
    }
    clearTimeout(pollTimer);
    pollTimer = setTimeout(poll, STATE && STATE.busy ? 400 : 2000);
  }

  // ------------------------------------------------------------- start
  bindSafety();
  requestAnimationFrame(frame);
  poll();
  loadCatalog().then(() => api("/api/check-rig", {})).then(poll);
})();
