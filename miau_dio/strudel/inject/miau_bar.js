// miau-dio footer bar -- single unified toolbar appended to the official
// Strudel REPL. Spans the full window width at the bottom so it reads as
// a native part of the app, not a floating widget.
//
// Left:  animations toggle (always) + project controls (when --at).
// Right: project status line -- name and pattern count.
//
// Idempotent: second install is a no-op. Self-heals if React hydration
// removes the bar.
(function () {
  var BAR_ID = 'miau-bar';
  var KEY_ANIM = 'miau-dio.animations';

  // ---------- animations preference --------------------------------------
  function readAnimPref() {
    try { return localStorage.getItem(KEY_ANIM) !== 'off'; }
    catch (e) { return true; }
  }
  function writeAnimPref(on) {
    try { localStorage.setItem(KEY_ANIM, on ? 'on' : 'off'); } catch (e) {}
  }
  function applyAnim(ed, on) {
    try {
      ed.updateSettings({
        isPatternHighlightingEnabled: on,
        isFlashEnabled: on,
      });
    } catch (e) {}
  }
  function whenEditor(cb, tries) {
    tries = tries || 0;
    var ed = window.strudelMirror;
    if (ed && typeof ed.updateSettings === 'function') { cb(ed); return; }
    if (tries > 60) return;
    setTimeout(function () { whenEditor(cb, tries + 1); }, 100);
  }

  // ---------- project bridge ---------------------------------------------
  function projectInfo() {
    return fetch('/project/info').then(function (r) {
      return r.ok ? r.json() : null;
    }).catch(function () { return null; });
  }
  function savePattern() {
    if (!window.strudelMirror) { alert('editor not ready'); return; }
    var suggested = 'pattern-' + new Date().toISOString().slice(0, 10);
    var name = prompt('save pattern as:', suggested);
    if (!name) return;
    fetch('/project/pattern/' + encodeURIComponent(name), {
      method: 'POST', body: window.strudelMirror.code || '',
    }).then(function (r) {
      if (!r.ok) { alert('save failed: ' + r.status); return; }
      refreshStatus('saved ' + name);
    });
  }
  function loadPattern() {
    projectInfo().then(function (i) {
      if (!i || i.patterns.length === 0) {
        alert('no patterns saved yet'); return;
      }
      var name = prompt('load pattern:\n' + i.patterns.join('\n'));
      if (!name) return;
      fetch('/project/pattern/' + encodeURIComponent(name)).then(function (r) {
        if (!r.ok) { alert('load failed: ' + r.status); return; }
        return r.text();
      }).then(function (body) {
        if (!body || !window.strudelMirror) return;
        window.strudelMirror.setCode(body);
        refreshStatus('loaded ' + name);
      });
    });
  }

  // ---------- state -----------------------------------------------------
  var statusEl = null;
  var projectName = '';
  var patternCount = 0;
  var flashTimer = null;

  function renderStatus(flash) {
    if (!statusEl) return;
    if (!projectName) { statusEl.textContent = ''; return; }
    if (flash) {
      statusEl.textContent = flash;
      if (flashTimer) clearTimeout(flashTimer);
      flashTimer = setTimeout(renderStatus, 1400);
      return;
    }
    statusEl.textContent = projectName + ' \u00b7 ' + patternCount +
      ' pattern' + (patternCount === 1 ? '' : 's');
  }
  function refreshStatus(flash) {
    projectInfo().then(function (i) {
      if (!i) return;
      projectName = i.name;
      patternCount = i.patterns.length;
      renderStatus(flash);
    });
  }

  // ---------- DOM helpers -----------------------------------------------
  function makeButton(label, primary, onClick) {
    var b = document.createElement('button');
    b.type = 'button';
    b.textContent = label;
    b.style.cssText =
      'background:' + (primary ? '#1f6f3f' : '#2a2a2f') + ';' +
      'color:#e6e6ea;border:0;padding:4px 10px;border-radius:3px;' +
      'font:inherit;cursor:pointer';
    b.addEventListener('click', onClick);
    return b;
  }
  function separator() {
    var s = document.createElement('span');
    s.style.cssText =
      'width:1px;height:18px;background:#2a2a2f;margin:0 6px';
    return s;
  }

  // ---------- install ----------------------------------------------------
  function install() {
    if (document.getElementById(BAR_ID)) return;

    var bar = document.createElement('div');
    bar.id = BAR_ID;
    // Full-width footer. Pinned to the bottom edge; no border-radius;
    // only a top border separating it from the editor above.
    bar.style.cssText =
      'position:fixed;left:0;right:0;bottom:0;z-index:9990;' +
      'background:#18181b;color:#e6e6ea;' +
      'padding:6px 12px;box-sizing:border-box;' +
      'font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;' +
      'border-top:1px solid #2a2a2f;' +
      'display:flex;align-items:center;gap:6px';

    // Left group: animations (always).
    var animOn = readAnimPref();
    var animBtn = makeButton('', true, function () {
      animOn = !animOn;
      writeAnimPref(animOn);
      renderAnim();
      whenEditor(function (ed) { applyAnim(ed, animOn); });
    });
    function renderAnim() {
      animBtn.textContent = 'animations: ' + (animOn ? 'on' : 'off');
      animBtn.style.background = animOn ? '#1f6f3f' : '#2a2a2f';
    }
    renderAnim();
    bar.appendChild(animBtn);
    whenEditor(function (ed) { applyAnim(ed, animOn); });

    // Right group: spacer, then project status (always present).
    var spacer = document.createElement('span');
    spacer.style.cssText = 'flex:1';
    bar.appendChild(spacer);

    statusEl = document.createElement('span');
    statusEl.id = 'miau-status';
    statusEl.style.cssText =
      'color:#8a8a93;white-space:nowrap;overflow:hidden;' +
      'text-overflow:ellipsis';
    bar.appendChild(statusEl);

    document.body.appendChild(bar);

    // Project controls appear only when the server has a project bound.
    projectInfo().then(function (i) {
      if (!i) { renderStatus(); return; }
      // Insert "save | load" before the spacer so left/right grouping holds.
      var saveBtn = makeButton('save pattern', false, savePattern);
      var loadBtn = makeButton('load pattern', false, loadPattern);
      bar.insertBefore(separator(), spacer);
      bar.insertBefore(saveBtn, spacer);
      bar.insertBefore(loadBtn, spacer);
      projectName = i.name;
      patternCount = i.patterns.length;
      renderStatus();
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', install);
  } else {
    install();
  }
  // Self-heal if React hydration removes the bar.
  if (document.body && typeof MutationObserver !== 'undefined') {
    new MutationObserver(function () {
      if (!document.getElementById(BAR_ID)) install();
    }).observe(document.body, { childList: true });
  }
})();
