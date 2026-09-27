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
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') set(false); });
    window.matchMedia('(min-width: 961px)').addEventListener('change', function (m) { if (m.matches) set(false); });
  }

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
