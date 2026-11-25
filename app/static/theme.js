'use strict';

(() => {
  const key = 'caifa.interface.theme';
  const choices = new Set(['celadon', 'indigo', 'sand', 'mono']);
  const load = () => {
    try { return localStorage.getItem(key); } catch { return null; }
  };
  function apply(value) {
    const theme = choices.has(value) ? value : 'celadon';
    document.documentElement.dataset.theme = theme;
    document.querySelectorAll('[data-theme-select]').forEach(select => { select.value = theme; });
  }
  apply(load());
  document.addEventListener('DOMContentLoaded', () => apply(document.documentElement.dataset.theme));
  document.addEventListener('change', ({target}) => {
    if (!target.matches('[data-theme-select]')) return;
    apply(target.value);
    try { localStorage.setItem(key, document.documentElement.dataset.theme); } catch { /* Current page still updates. */ }
  });
  window.addEventListener('storage', event => {
    if (event.key === key || event.key === null) apply(event.newValue);
  });
})();
