/* Live & Work Toyama: small enhancements. Every page works without this file. */
(function () {
  var KEY = 'lwt-lang';
  document.addEventListener('click', function (e) {
    var a = e.target.closest && e.target.closest('a[data-lang]');
    if (a) { try { localStorage.setItem(KEY, a.getAttribute('data-lang')); } catch (_) {} }
    // Count clicks to the original job pages (company recruitment page or job site). No personal data.
    var cta = e.target.closest && e.target.closest('a[data-cta]');
    if (cta && typeof window.gtag === 'function') {
      window.gtag('event', 'cta_click', { cta: cta.getAttribute('data-cta'), transport_type: 'beacon' });
    }
    var ap = e.target.closest && e.target.closest('a[data-apply]');
    if (ap && typeof window.gtag === 'function') {
      window.gtag('event', 'apply_click', { link_type: ap.getAttribute('data-apply'), link_domain: ap.hostname, transport_type: 'beacon' });
    }
    var open = document.querySelector('details.lang[open]');
    if (open && !open.contains(e.target)) open.removeAttribute('open');
  });
  document.addEventListener('keydown', function (e) {
    if (e.key !== 'Escape') return;
    var open = document.querySelector('details.lang[open]');
    if (open) { open.removeAttribute('open'); open.querySelector('summary').focus(); }
  });
  var btn = document.querySelector('button[data-copy]');
  if (btn && navigator.clipboard) {
    btn.hidden = false;
    btn.addEventListener('click', function () {
      navigator.clipboard.writeText(btn.getAttribute('data-copy')).then(function () {
        var label = btn.textContent;
        btn.textContent = btn.getAttribute('data-done');
        setTimeout(function () { btn.textContent = label; }, 2000);
      });
    });
  }
})();
