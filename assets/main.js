(function(){
  const items = window.DOWNLOADS || [];
  const searchInput = document.getElementById('search');
  const tabs = Array.from(document.querySelectorAll('.tab'));
  const categories = ['algorithme','bibliographie','autre'];
  const ids = categories.reduce((acc,id)=>{ acc[id]=document.getElementById(id); return acc; },{});

  function escapeHtml(s){ return String(s || '').replace(/[&<>"']/g, t => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[t]); }
  function humanSize(bytes){ if (bytes === undefined || bytes === null) return '—'; const u=['B','KB','MB','GB']; let i=0; let v=Number(bytes); if (Number.isNaN(v)) return '—'; while(v>=1024 && i<u.length-1){ v/=1024; i++; } return v.toFixed(v<10 && i>0 ? 1 : 0)+' '+u[i]; }

  function makeCard(it){
    const el = document.createElement('article');
    el.className = 'card';
    el.setAttribute('tabindex','0');
    const filename = String(it.filename || '').trim();
    const hrefFile = encodeURI('files/' + filename);
    const lower = filename.toLowerCase();
    const isPdf = lower.endsWith('.pdf');
    const isZip = lower.endsWith('.zip');

    let openHref = hrefFile;
    const category = ((it.category || '') + '').toString().toLowerCase().trim();
    if (category === 'algorithme'){
      openHref = 'viewer.html?title=' + encodeURIComponent(it.title || filename);
    }

    const downloadBtn = filename ? `<a class="button" href="${hrefFile}" ${isPdf || isZip ? 'download' : ''}>Télécharger</a>` : '';
    const openBtn = (category === 'bibliographie')
      ? ''
      : `<a class="button secondary" href="${openHref}">Ouvrir</a>`;
    const webBtn = (it.versionweb && String(it.versionweb).trim().length)
      ? `<a class="button secondary" href="${it.versionweb}" target="_blank" rel="noopener">🔗Web</a>`
      : '';

    const actions = `${downloadBtn}${openBtn}${webBtn}`;

    el.innerHTML = `
      <div class="head">
        <h3>${escapeHtml(it.title || filename)}</h3>
        <span class="badge">${escapeHtml(it.version || '')}</span>
      </div>
      <div class="meta">
        <span title="Nom du fichier">${escapeHtml(filename)}</span>
        <span title="Taille">${escapeHtml(humanSize(it.size_bytes))}</span>
        <span title="Date">${escapeHtml(it.date || '')}</span>
      </div>
      <div class="desc">${escapeHtml(it.description || '')}</div>
      <div class="actions">${actions}</div>
    `;

    el.addEventListener('click', (ev) => {
      if (ev.target.tagName.toLowerCase() === 'a' || ev.target.closest('a')) return;
      window.location.href = openHref;
    });
    el.addEventListener('keydown', (ev)=>{
      if(ev.key === 'Enter' || ev.key === ' ') { ev.preventDefault(); el.click(); }
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
      document.getElementById('count-'+(cat==='bibliographie'?'bib':cat.slice(0,3))).textContent = list.length ? `${list.length} fichiers` : '0 fichiers';
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

  function debounce(fn, ms){ let t; return (...a)=>{ clearTimeout(t); t = setTimeout(()=>fn.apply(this,a), ms); }; }

  const doSearch = () => render(filterItems(searchInput.value));
  searchInput.addEventListener('input', debounce(doSearch, 150));

  tabs.forEach(tb => tb.addEventListener('click', ()=>{
    tabs.forEach(t=>{ t.classList.remove('active'); t.setAttribute('aria-selected','false'); });
    tb.classList.add('active'); tb.setAttribute('aria-selected','true');
    const cat = tb.getAttribute('data-cat');
    if(cat === 'all'){
      document.querySelectorAll('main section').forEach(s=>s.style.display='block');
    } else {
      document.querySelectorAll('main section').forEach(s=>s.style.display='none');
      const sectionId = (cat === 'bibliographie') ? 'bibliographie' : cat;
      document.getElementById(sectionId).closest('section').style.display = 'block';
    }
  }));

  render(items);
})();
