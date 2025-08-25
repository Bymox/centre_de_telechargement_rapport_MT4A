// assets/viewer.js - lecture locale de window.DOWNLOADS + scroll horizontal via molette
(function(){
  function id(n){ return document.getElementById(n); }
  function escapeHtml(s){ return String(s||'').replace(/[&<>"']/g, t => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[t]); }
  function params(){ return Object.fromEntries(new URLSearchParams(location.search)); }

  const p = params();
  const downloads = window.DOWNLOADS || [];
  const info = id('info');
  const errEl = id('error');
  const codeBox = id('code-box');
  const yamlBox = id('yaml-box');
  const copyCodeBtn = id('copy-code');
  const copyYamlBtn = id('copy-yaml');
  const rawCodeLink = id('raw-code-link');
  const rawYamlLink = id('raw-yaml-link');
  const codeTitle = id('code-title');
  const yamlTitle = id('yaml-title');

  function showError(msg){
    errEl.innerHTML = `<div class="error">${escapeHtml(msg)}</div>`;
    info.textContent = '';
  }

  if(!p.title && !p.file){
    info.textContent = 'Paramètre manquant. Appeler viewer.html?title=Nom%20du%20module ou ?file=nom.zip';
    return;
  }

  function norm(s){
    if(!s) return '';
    return s.toString().normalize('NFKC').toLowerCase().trim().replace(/\s+/g,' ');
  }

  function findEntry(){
    if(!downloads || !downloads.length) return null;
    if(p.title){
      // try multiple strategies (exact, decoded, normalized, partial)
      let entry = downloads.find(d => (d.title || '') === p.title);
      if(entry) return entry;
      try {
        const dec = decodeURIComponent(p.title);
        entry = downloads.find(d => (d.title || '') === dec);
        if(entry) return entry;
      } catch(e){}
      const n = norm(p.title);
      entry = downloads.find(d => norm(d.title) === n);
      if(entry) return entry;
      entry = downloads.find(d => norm(d.title).includes(n));
      if(entry) return entry;
    }

    if(p.file){
      let entry = downloads.find(d => (d.filename || '') === p.file || (d.filename || '') === decodeURIComponent(p.file));
      if(entry) return entry;
      const nf = norm(p.file);
      entry = downloads.find(d => norm(d.filename) === nf || norm(d.filename).includes(nf));
      if(entry) return entry;
    }

    if(p.file){
      const nf = norm(p.file);
      let entry = downloads.find(d => (d.code_path && norm(d.code_path).includes(nf)) || (d.yaml_path && norm(d.yaml_path).includes(nf)));
      if(entry) return entry;
    }

    return null;
  }

  const entry = findEntry();

  console.debug('viewer params:', p);
  console.debug('downloads titles:', downloads.map(d => d.title || d.filename));
  console.debug('matched entry:', entry);

  if(!entry){
    const list = downloads.map(d => `• title="${d.title || ''}"  filename="${d.filename || ''}"`).join('\n');
    showError('Aucune entrée correspondante dans downloads.js pour ce title/file. Titres disponibles listés ci-dessous.');
    info.textContent = 'Titres disponibles (console) — copier un title exact ou utiliser ?file=...';
    console.warn('Aucune entrée correspondante — liste des entrées:\n' + list);
    errEl.insertAdjacentHTML('beforeend', `<pre style="margin-top:8px;color:#ffdede;background:#1b0f0f;padding:8px;border-radius:6px">${escapeHtml(list)}</pre>`);
    return;
  }

  // populate
  codeTitle.textContent = (entry.title || 'Code Python');
  yamlTitle.textContent = (entry.title ? (entry.title + ' — YAML') : 'YAML / Config');
  info.textContent = `Affichage local depuis downloads.js — ${entry.title || entry.filename}`;

  if(entry.code_py){
    codeBox.textContent = entry.code_py;
    rawCodeLink.href = entry.code_path ? entry.code_path : '#';
  } else if(entry.code_path){
    codeBox.textContent = `Pas de code embarqué (code_py absent). Chemin brut : ${entry.code_path}`;
    rawCodeLink.href = entry.code_path;
  } else {
    codeBox.textContent = 'Aucun code python embarqué ni path fourni.';
    rawCodeLink.href = '#';
  }

  if(entry.code_yaml){
    yamlBox.textContent = entry.code_yaml;
    rawYamlLink.href = entry.yaml_path ? entry.yaml_path : '#';
  } else if(entry.yaml_path){
    yamlBox.textContent = `Pas de YAML embarqué (code_yaml absent). Chemin brut : ${entry.yaml_path}`;
    rawYamlLink.href = entry.yaml_path;
  } else {
    yamlBox.textContent = 'Aucun YAML embarqué ni path fourni.';
    rawYamlLink.href = '#';
  }

  // --- horizontal scrolling with mouse wheel on code boxes ---
  // convert vertical wheel to horizontal scroll when hovering a code box.
function attachHorizontalWheel(el) {
  el.addEventListener('wheel', function(e) {
    // Défilement horizontal UNIQUEMENT si Shift est enfoncé
    if (e.shiftKey) {
      if (el.scrollWidth > el.clientWidth) {
        el.scrollLeft += e.deltaY;
        e.preventDefault();
      }
    }
    // Sinon, défilement vertical normal (comportement par défaut)
  }, { passive: false });
}


  // Attach to both code and yaml boxes
  attachHorizontalWheel(codeBox);
  attachHorizontalWheel(yamlBox);

  // allow keyboard arrows: left/right scrolls horizontally when focused
  codeBox.addEventListener('keydown', (e) => {
    if(e.key === 'ArrowRight') { codeBox.scrollLeft += 40; e.preventDefault(); }
    if(e.key === 'ArrowLeft')  { codeBox.scrollLeft -= 40; e.preventDefault(); }
  });
  yamlBox.addEventListener('keydown', (e) => {
    if(e.key === 'ArrowRight') { yamlBox.scrollLeft += 40; e.preventDefault(); }
    if(e.key === 'ArrowLeft')  { yamlBox.scrollLeft -= 40; e.preventDefault(); }
  });

  // copy buttons behavior
  copyCodeBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(codeBox.textContent || '');
      copyCodeBtn.textContent = 'Copié ✓';
      setTimeout(()=> copyCodeBtn.textContent = 'Copier le code', 1200);
    } catch(e){
      showError('Impossible de copier dans le presse-papier : ' + String(e));
    }
  });
  copyYamlBtn.addEventListener('click', async () => {
    try {
      await navigator.clipboard.writeText(yamlBox.textContent || '');
      copyYamlBtn.textContent = 'Copié ✓';
      setTimeout(()=> copyYamlBtn.textContent = 'Copier le YAML', 1200);
    } catch(e){
      showError('Impossible de copier dans le presse-papier : ' + String(e));
    }
  });

})();
