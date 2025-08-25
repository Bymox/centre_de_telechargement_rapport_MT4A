// assets/main.js - lit window.DOWNLOADS et rend les cards
document.addEventListener('DOMContentLoaded', () => {
  const items = window.DOWNLOADS || [];
  const searchInput = document.getElementById('search');
  const categories = ['algorithme','bibliographie','autre'];
  const ids = categories.reduce((acc,id)=>{ acc[id]=document.getElementById(id); return acc; },{});

  function escapeHtml(s){ return String(s || '').replace(/[&<>"']/g, t => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[t]); }
  function humanSize(bytes){ if (bytes === undefined || bytes === null) return '—'; const u=['B','KB','MB','GB']; let i=0; let v=Number(bytes); if (Number.isNaN(v)) return '—'; while(v>=1024 && i<u.length-1){ v/=1024; i++; } return v.toFixed(v<10 && i>0 ? 1 : 0)+' '+u[i]; }

  function makeCard(it){
    const el = document.createElement('div');
    el.className = 'card';
    const filename = String(it.filename || '').trim();
    const hrefFile = encodeURI('files/' + filename);
    const lower = filename.toLowerCase();
    const isPdf = filename.toLowerCase().endsWith('.pdf');
    const isZip = filename.toLowerCase().endsWith('.zip');

    // For algorithme: viewer reads window.DOWNLOADS and shows inline code (code_py / code_yaml)
    let openHref = hrefFile;
    const category = ((it.category || '') + '').toString().toLowerCase().trim();
    if (category === 'algorithme'){
      openHref = 'viewer.html?title=' + encodeURIComponent(it.title || filename);
    }

    // build action buttons conditionally
    // download button (always shown if there's a filename)
    const downloadBtn = filename ? `<a class="button" href="${hrefFile}" ${isPdf || isZip ? 'download' : ''}>Télécharger</a>` : '';

    // open button: not for bibliographie (keeps previous behavior)
    const openBtn = (category === 'bibliographie')
      ? ''
      : `<a class="button secondary" href="${openHref}">Ouvrir</a>`;

    // version web button: only if it.versionweb est présent
    const webBtn = (it.versionweb && String(it.versionweb).trim().length)
      ? `<a class="button secondary" href="${it.versionweb}" target="_blank" rel="noopener">🔗Web</a>`
      : '';

    const actions = `
      ${downloadBtn}
      ${openBtn}
      ${webBtn}
    `;

    el.innerHTML = `
      <div class="head">
        <h3>${escapeHtml(it.title || filename)}</h3>
        <span class="badge">${escapeHtml(it.version || '')}</span>
      </div>
      <div class="meta">
        <span>${escapeHtml(filename)}</span>
        <span>${escapeHtml(humanSize(it.size_bytes))}</span>
        <span>${escapeHtml(it.date || '')}</span>
      </div>
      <div class="desc">${escapeHtml(it.description || '')}</div>
      <div class="actions">${actions}</div>
    `;

    // click on card (outside links) — ouvre le "openHref" dans le même onglet
    el.addEventListener('click', (ev) => {
      if (ev.target.tagName.toLowerCase() === 'a' || ev.target.closest('a')) return;
      window.location.href = openHref; // Ouvre dans le même onglet
    });

    return el;
  }


  function render(filtered){
    const grouped = { algorithme: [], bibliographie: [], autre: [] };
    filtered.forEach(it => {
      let cat = (it.category || 'autre').toString().toLowerCase().trim();
      if (cat === 'algorithm' || cat === 'algo') cat = 'algorithme';
      if (cat === 'biblio') cat = 'bibliographie';
      const key = categories.includes(cat) ? cat : 'autre';
      grouped[key].push(it);
    });

    categories.forEach(cat => {
      const container = ids[cat];
      container.innerHTML = '';
      const list = grouped[cat];
      if(!list.length) container.innerHTML = '<div class="empty-note">Aucun fichier dans cette catégorie.</div>';
      else list.forEach(it => container.appendChild(makeCard(it)));
    });
  }

  function filterItems(q){
    if(!q) return items;
    q = q.toLowerCase();
    return items.filter(it => {
      const hay = ((it.title||'') + ' ' + (it.filename||'') + ' ' + (it.description||'')).toLowerCase();
      return hay.includes(q);
    });
  }

  searchInput.addEventListener('input', () => render(filterItems(searchInput.value)));
  render(filterItems(''));
});
