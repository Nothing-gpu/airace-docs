// airaceGP docs: the mobile menu and copy buttons. Nothing else.
(function () {
  var btn = document.getElementById('nav-toggle');
  var side = document.getElementById('side');
  if (btn && side) {
    var set = function (open) {
      side.classList.toggle('open', open);
      btn.setAttribute('aria-expanded', String(open));
      btn.textContent = open ? 'Close' : 'Menu';
      document.body.classList.toggle('menu-open', open);
    };
    btn.addEventListener('click', function () { set(!side.classList.contains('open')); });
    side.addEventListener('click', function (e) { if (e.target.closest('a')) set(false); });
    document.addEventListener('keydown', function (e) {
      if (e.key !== 'Escape' || !side.classList.contains('open')) return;
      set(false); btn.focus();                       // focus goes back to the button that opened it
    });
    // Tabbing out of the open menu closes it, so focus never lands on content hidden underneath
    side.addEventListener('focusout', function (e) {
      var to = e.relatedTarget;
      if (to && side.classList.contains('open') && !side.contains(to) && to !== btn) set(false);
    });
    window.matchMedia('(min-width: 961px)').addEventListener('change', function (m) { if (m.matches) set(false); });
  }

  // Regions that scroll sideways (wide tables, long code lines) must be reachable with the keyboard
  // (WCAG 2.1.1): give them a tab stop and a name, only while they actually scroll.
  function scrollers() {
    document.querySelectorAll('.table-wrap, .code pre').forEach(function (el) {
      var scrolls = el.scrollWidth > el.clientWidth + 1;
      if (scrolls && !el.hasAttribute('tabindex')) {
        var code = el.closest('.code'), head = code && code.querySelector('.code-head');
        var label = head ? (head.firstChild && head.firstChild.textContent || '').trim() : '';
        el.setAttribute('tabindex', '0');
        el.setAttribute('role', 'region');
        el.setAttribute('aria-label', (label ? label + ', ' : (code ? 'Code, ' : 'Table, ')) + 'scrolls sideways');
      } else if (!scrolls && el.getAttribute('tabindex') === '0') {
        el.removeAttribute('tabindex'); el.removeAttribute('role'); el.removeAttribute('aria-label');
      }
    });
  }
  scrollers();
  window.addEventListener('resize', scrollers);

  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) return navigator.clipboard.writeText(text);
    return new Promise(function (resolve, reject) {
      var ta = document.createElement('textarea');
      ta.value = text; ta.setAttribute('readonly', '');
      ta.style.position = 'fixed'; ta.style.opacity = '0';
      document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy') ? resolve() : reject(); } catch (err) { reject(err); }
      document.body.removeChild(ta);
    });
  }
  document.querySelectorAll('.code').forEach(function (block) {
    var head = block.querySelector('.code-head');
    var pre = block.querySelector('pre');
    if (!head || !pre) return;
    var b = document.createElement('button');
    b.type = 'button'; b.className = 'copy'; b.textContent = 'Copy';
    b.setAttribute('aria-label', 'Copy ' + (head.textContent.trim() || 'code') + ' to clipboard');
    b.addEventListener('click', function () {
      // Lines marked .c are comments for the reader, not commands to paste.
      var clone = pre.cloneNode(true);
      clone.querySelectorAll('.c').forEach(function (c) { c.remove(); });
      var text = clone.textContent.replace(/\n{2,}/g, '\n').trim() + '\n';
      copyText(text).then(function () {
        b.textContent = 'Copied'; b.classList.add('done');
        setTimeout(function () { b.textContent = 'Copy'; b.classList.remove('done'); }, 1600);
      }, function () { b.textContent = 'Select + Ctrl+C'; });
    });
    head.appendChild(b);
  });
})();
