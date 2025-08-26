(function(){
  const id = (n)=>document.getElementById(n);
  const codeBox = id('code-box');
  const copyBtn = id('copy-code');
  const rawLink = id('raw-code-link');
  const downloadBtn = id('download-button');
  const s2pFileInput = id('s2p-file');
  const convertBtn = id('convert-btn');
  const generatedLinks = id('generated-links');
  const status = id('status');

const PY_CODE = `
import numpy as np
import os

def convert_s2p_to_two_dat_files(s2p_path):
    freqs = []
    s11_db = []
    s21_db = []

    with open(s2p_path, 'r') as f:
        for line in f:
            line = line.strip()
            if line.startswith('#') or not line:
                continue  # Ignore commentaires et lignes vides

            parts = line.split()
            if len(parts) < 5:
                continue  # Faut au moins freq, S11, S21

            freq = float(parts[0])
            s11_real, s11_imag = float(parts[1]), float(parts[2])
            s21_real, s21_imag = float(parts[3]), float(parts[4])

            s11_mag = np.abs(complex(s11_real, s11_imag))
            s21_mag = np.abs(complex(s21_real, s21_imag))

            s11_db_val = 20 * np.log10(s11_mag) if s11_mag > 0 else -100
            s21_db_val = 20 * np.log10(s21_mag) if s21_mag > 0 else -100

            freqs.append(freq)
            s11_db.append(s11_db_val)
            s21_db.append(s21_db_val)

    # Préparation des noms de fichiers
    base_name = os.path.splitext(s2p_path)[0]
    s11_path = base_name + "_S11.dat"
    s21_path = base_name + "_S21.dat"

    # Écriture du fichier S11
    with open(s11_path, 'w') as f_s11:
        f_s11.write("# Frequency(Hz)\tS11(dB)")
        for f, s11 in zip(freqs, s11_db):
            f_s11.write(f"{f:.0f}\t{s11:.2f}")

    # Écriture du fichier S21
    with open(s21_path, 'w') as f_s21:
        f_s21.write("# Frequency(Hz)\tS21(dB)")
        for f, s21 in zip(freqs, s21_db):
            f_s21.write(f"{f:.0f}\t{s21:.2f}")

    print(f"✅ Fichiers créés : - {s11_path} - {s21_path}")

# Utilisation
s2p_file = "C:/Users/a942666/OneDrive - ATOS/Bureau/bank_18_24/LFCV-2302+_Plus25DegC.s2p"
convert_s2p_to_two_dat_files(s2p_file)
`;


const s2pInput = document.getElementById('s2p-file');
const label = document.querySelector('label[for="s2p-file"]');
s2pInput.addEventListener('change', ()=>{
  if(s2pInput.files.length){
    label.textContent = s2pInput.files[0].name;
  }else{
    label.textContent = "Choisir .s2p";
  }
});

  codeBox.textContent = PY_CODE;

  copyBtn.addEventListener('click', async ()=>{
    try{
      await navigator.clipboard.writeText(codeBox.textContent);
      copyBtn.textContent = 'Copié ✓';
      setTimeout(()=>copyBtn.textContent='Copier le code',1200);
    }catch(e){ console.error(e);}
  });


  function parseS2P(text){
    const lines = text.split(/\r?\n/);
    const freqs=[], s11=[], s21=[];
    for(let line of lines){
      line = line.trim();
      if(!line || line.startsWith('!')||line.startsWith('#')) continue;
      const p=line.split(/\s+/);
      if(p.length<5) continue;
      const f=Number(p[0]), s11_re=Number(p[1]), s11_im=Number(p[2]), s21_re=Number(p[3]), s21_im=Number(p[4]);
      if([f,s11_re,s11_im,s21_re,s21_im].some(isNaN)) continue;
      freqs.push(f);
      s11.push(20*Math.log10(Math.hypot(s11_re,s11_im)));
      s21.push(20*Math.log10(Math.hypot(s21_re,s21_im)));
    }
    return {freqs,s11,s21};
  }

  function buildDat(freqs, vals, label){
    const lines=['# Frequency(Hz)\t'+label];
    for(let i=0;i<freqs.length;i++) lines.push(`${Math.round(freqs[i])}\t${vals[i].toFixed(2)}`);
    return lines.join('\n');
  }

  function makeDownload(text,name){
    const blob=new Blob([text],{type:'text/plain'});
    const a=document.createElement('a');
    a.href=URL.createObjectURL(blob);
    a.download=name;
    a.textContent='Télécharger '+name;
    a.className='button secondary';
    a.style.display='inline-block';
    a.style.marginRight='8px';
    return a;
  }

  convertBtn.addEventListener('click', ()=>{
    const f = s2pFileInput.files && s2pFileInput.files[0];
    generatedLinks.innerHTML=''; generatedLinks.style.display='none'; status.textContent='';
    if(!f){ status.textContent='Choisis un fichier .s2p avant de convertir.'; return; }
    const reader=new FileReader();
    reader.onload=(ev)=>{
      try{
        const {freqs,s11,s21} = parseS2P(ev.target.result);
        if(!freqs.length){ status.textContent='Aucune donnée valide trouvée.'; return; }
        const base=f.name.replace(/\.s2p$/i,'');
        generatedLinks.appendChild(makeDownload(buildDat(freqs,s11,'S11(dB)'),base+'_S11.dat'));
        generatedLinks.appendChild(makeDownload(buildDat(freqs,s21,'S21(dB)'),base+'_S21.dat'));
        generatedLinks.style.display='block';
        status.textContent=`Conversion OK — ${freqs.length} points générés.`;
      }catch(e){ status.textContent='Erreur : '+e; }
    };
    reader.readAsText(f);
  });
})();
