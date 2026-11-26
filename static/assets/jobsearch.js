/* Live & Work Toyama: job search (runs in the browser; no data is sent anywhere). */
(function () {
  var C = window.JOBSEARCH; if (!C) return;
  var L = C.L, lang = C.lang, form = document.getElementById('jobsearch');
  var out = document.getElementById('jresults'), cnt = document.getElementById('jcount'), more = document.getElementById('jmore');
  var KEY = 'lwt-saved-jobs', PAGE = 30, shown = 0, list = [], all = [];
  function saved() { try { return JSON.parse(localStorage.getItem(KEY) || '[]'); } catch (e) { return []; } }
  function setSaved(a) { try { localStorage.setItem(KEY, JSON.stringify(a)); } catch (e) {} }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"]/g, function (c) { return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[c]; }); }
  function f(k, o) { var s = L[k] || k; for (var x in o) s = s.split('{' + x + '}').join(o[x]); return s; }
  function yen(n) { return '¥' + Number(n).toLocaleString('en-US'); }
  function title(j) {
    if (typeof j.t === 'object') return j.t[lang] || j.t.en || j.t.ja;
    if (lang === 'ja' || lang === 'easy') return j.t;
    return f('job_auto_title', {cat: L['job_cat_' + j.c], emp: L['emp_' + j.m], city: L['region_' + j.r]});
  }
  function pay(j) {
    var p = j.p || {}; if (!p.min && !p.max) return L.pay_unknown;
    var x = p.min && p.max && p.min !== p.max ? f('pay_range', {a: yen(p.min), b: yen(p.max)}) : (p.min === p.max ? yen(p.min) : f('pay_from', {a: yen(p.min || p.max)}));
    return f('pay_' + (p.per || 'month'), {x: x});
  }
  function fmtDate(s) { return s ? s.replace(/-/g, '/') : ''; }
  function card(j) {
    var sv = saved().indexOf(j.id) >= 0;
    var tags = [L['job_cat_' + j.c], L['region_' + j.r], L['emp_' + j.m]];
    if (j.ft) tags.push(L.job_foreign_text);
    var h = '<article class="card job">' + tags.map(function (t) { return '<span class="tag">' + esc(t) + '</span>'; }).join('');
    h += '<h3>' + esc(title(j)) + '</h3>';
    if (typeof j.t !== 'object' && lang !== 'ja' && lang !== 'easy') h += '<p class="note" lang="ja" style="margin:0">' + esc(j.t) + '</p>';
    var rows = [];
    rows.push([L.job_employer, j.es ? '<a href="/' + lang + '/employers/' + esc(j.es) + '/" lang="ja">' + esc(j.e) + '</a>' : esc(j.e)]);
    rows.push([L.job_pay, esc(pay(j))]);
    if (j.h) rows.push([L.job_hours, esc(j.h)]);
    if (j.q && j.q.length) rows.push([L.job_requires, esc(j.q.map(function (q) { return L['q_' + q]; }).join(', '))]);
    if (j.jl) rows.push([L.job_japanese, esc(f('jlpt_fmt', {lv: j.jl}))]);
    if (j.hol) rows.push([L.job_holidays, esc(f('holidays_fmt', {n: j.hol}))]);
    if (j.b) rows.push([L.job_bonus, esc(f('bonus_fmt', {n: j.b}))]);
    if (j.hs) rows.push([L.job_housing, esc(L.housing_single)]);
    if (j.pub) rows.push([L.job_posted, esc(fmtDate(j.pub)) + (j.hw ? ' · ' + esc(f('job_hw_no', {no: j.hw})) : '')]);
    h += '<dl>' + rows.map(function (r) { return '<dt>' + esc(r[0]) + '</dt><dd>' + r[1] + '</dd>'; }).join('') + '</dl><div class="btns">';
    if (j.o) h += '<a class="btn sm" data-apply="official" href="' + esc(j.o) + '" target="_blank" rel="noopener nofollow">' + esc(L.job_apply_official) + '</a><a class="btn sm ghost" data-apply="source" href="' + esc(j.u) + '" target="_blank" rel="noopener nofollow">' + esc(L.job_apply_source) + '</a>';
    else h += '<a class="btn sm" data-apply="source" href="' + esc(j.u) + '" target="_blank" rel="noopener nofollow">' + esc(L.job_apply) + '</a>';
    h += '<p class="vnote">' + esc(L.visa_check) + ' <a href="/' + C.lang + '/guides/changing-jobs/">' + esc(L.visa_check_link) + '</a></p>';
    h += '<button type="button" class="btn sm ghost save" data-id="' + esc(j.id) + '" aria-pressed="' + sv + '">' + (sv ? '★ ' + esc(L.saved) : '☆ ' + esc(L.save)) + '</button></div></article>';
    return h;
  }
  function monthly(j) { var p = j.p || {}; if (p.per === 'month') return p.max || p.min || 0; if (p.per === 'year') return (p.max || p.min || 0) / 12; return 0; }
  function apply() {
    var q = new FormData(form), get = function (k) { return q.get(k) || ''; };
    var kw = get('kw').trim().toLowerCase(), cat = get('cat'), emp = get('emp'), city = get('city'), pmin = +get('pay') || 0;
    var sv = saved(), week = new Date(Date.now() - 7 * 864e5).toISOString().slice(0, 10);
    list = all.filter(function (j) {
      if (cat && j.c !== cat) return false;
      if (emp && j.m !== emp) return false;
      if (city && j.r !== city) return false;
      if (pmin && monthly(j) < pmin) return false;
      if (get('housing') && !j.hs) return false;
      if (get('nolicense') && (j.q || []).some(function (x) { return /^license/.test(x); })) return false;
      if (get('noqual') && (j.q || []).some(function (x) { return x !== 'pc'; })) return false;
      if (get('hol120') && !(j.hol >= 120)) return false;
      if (get('bonus') && !j.b) return false;
      if (get('foreign') && !j.ft) return false;
      if (get('official') && !j.o) return false;
      if (get('new') && !(j.pub && j.pub >= week)) return false;
      if (get('saved') && sv.indexOf(j.id) < 0) return false;
      if (kw) {
        var hay = (typeof j.t === 'object' ? Object.keys(j.t).map(function (k) { return j.t[k]; }).join(' ') : j.t) + ' ' + j.e + ' ' + (L['job_cat_' + j.c] || '') + ' ' + (L['region_' + j.r] || '');
        if (hay.toLowerCase().indexOf(kw) < 0) return false;
      }
      return true;
    });
    var s = get('sort');
    list.sort(function (a, b) {
      if (a.k !== b.k) return a.k === 'c' ? -1 : 1;
      if (s === 'pay') return monthly(b) - monthly(a);
      if (s === 'hol') return (b.hol || 0) - (a.hol || 0);
      return (b.pub || '').localeCompare(a.pub || '');
    });
    shown = 0; out.innerHTML = '';
    cnt.textContent = list.length ? f('results_n', {n: list.length}) : L.no_results;
    page();
    var params = new URLSearchParams();
    q.forEach(function (v, k) { if (v) params.set(k, v); });
    history.replaceState(null, '', location.pathname + (params.toString() ? '?' + params : ''));
  }
  function page() {
    out.insertAdjacentHTML('beforeend', list.slice(shown, shown + PAGE).map(card).join(''));
    shown += PAGE; more.hidden = shown >= list.length;
  }
  function restore() {
    var p = new URLSearchParams(location.search);
    p.forEach(function (v, k) { var el = form.elements[k]; if (!el) return; if (el.type === 'checkbox') el.checked = true; else el.value = v; });
  }
  form.addEventListener('input', apply);
  form.addEventListener('change', apply);
  form.addEventListener('submit', function (e) { e.preventDefault(); apply(); });
  form.addEventListener('reset', function () { setTimeout(apply, 0); });
  more.addEventListener('click', page);
  out.addEventListener('click', function (e) {
    var b = e.target.closest('button.save'); if (!b) return;
    var id = b.getAttribute('data-id'), a = saved(), i = a.indexOf(id);
    if (i >= 0) a.splice(i, 1); else a.push(id);
    setSaved(a);
    var on = i < 0; b.setAttribute('aria-pressed', on); b.textContent = on ? '★ ' + L.saved : '☆ ' + L.save;
  });
  cnt.textContent = '…';
  fetch(C.data).then(function (r) { return r.json(); }).then(function (d) { all = d; restore(); apply(); });
})();
