function headers(){ const t = localStorage.getItem('TSM_ADMIN_TOKEN')||''; const h={'Content-Type':'application/json','Accept':'application/json'}; if(t) h['Authorization']='Bearer '+t; return h; }
function j(o){try{return JSON.stringify(o,null,2)}catch(e){return String(o)}}

async function refresh(){
  const r = await fetch('/admin/state', {headers: headers()});
  const stateDiv = document.getElementById('state');
  if(!r.ok){ stateDiv.textContent='(unauthorized)'; return; }
  const st = await r.json();
  stateDiv.textContent = j({version:st.version, profiles:Object.keys(st.profiles||{})});
  const profSel = document.getElementById('profile');
  if (profSel){
    profSel.innerHTML = '';
    const profileDescriptions = {
      'tester': 'tester (basic security level)',
      'reviewer': 'reviewer (moderate security level)',
      'developer': 'developer (full security level)',
      'architect': 'architect (admin security level)'
    };
    Object.keys(st.profiles||{}).forEach(name=>{
      const opt = document.createElement('option');
      opt.value=name;
      opt.textContent=profileDescriptions[name] || name;
      profSel.appendChild(opt);
    });
  }
  const tb = document.querySelector('#rules tbody'); tb.innerHTML='';
  (st.rules||[]).forEach(rule=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${rule.id}</td><td>${rule.type}</td><td>${rule.path||rule.scopeRoot||''}</td><td>${(rule.patterns||[]).join(', ')}</td><td>${rule.expiresAt||''}</td><td><button data-id="${rule.id}">remove</button></td>`;
    tr.querySelector('button').onclick = async (ev)=>{
      const id = ev.target.getAttribute('data-id');
      const rr = await fetch('/admin/allowlist/remove', {method:'POST', headers: headers(), body: JSON.stringify({id})});
      await rr.json(); refresh();
    };
    tb.appendChild(tr);
  });
  const tob = document.querySelector('#overlays tbody'); tob.innerHTML='';
  (st.overlays||[]).forEach(o=>{
    const tr = document.createElement('tr');
    tr.innerHTML = `<td>${o.sessionId}</td><td>${o.profile}</td><td>${o.expiresAt||''}</td>`;
    tob.appendChild(tr);
  });
}

async function addRule(ev){ ev.preventDefault();
  const type = document.getElementById('type').value;
  const path = document.getElementById('path').value.trim();
  const scopeRoot = document.getElementById('scopeRoot').value.trim();
  const patterns = (document.getElementById('patterns').value||'').split(',').map(s=>s.trim()).filter(Boolean);
  const flagsAllowed = (document.getElementById('flagsAllowed').value||'').split(',').map(s=>s.trim()).filter(Boolean);
  const ttlSec = parseInt(document.getElementById('ttlSec').value||'0')||null;
  const label = document.getElementById('label').value||null;
  const note = document.getElementById('note').value||null;
  const body = {type, path, scopeRoot, patterns, flagsAllowed, ttlSec, label, note};
  const r = await fetch('/admin/allowlist/add', {method:'POST', headers: headers(), body: JSON.stringify(body)});
  const out = await r.json();
  document.getElementById('addOut').textContent = j(out);
  if (out.ok) refresh();
}

async function assignProfile(ev){ ev.preventDefault();
  const sessionId = document.getElementById('sessId').value.trim();
  const profile = document.getElementById('profile').value;
  const ttlSec = parseInt(document.getElementById('sessTtl').value||'0')||3600;
  const r = await fetch('/admin/session/profile', {method:'POST', headers: headers(), body: JSON.stringify({sessionId, profile, ttlSec})});
  const out = await r.json();
  document.getElementById('profileOut').textContent = j(out);
  if (out.ok) refresh();
}

async function loadAudit(){
  const r = await fetch('/admin/audit/tail', {headers: headers()});
  if(!r.ok){ document.getElementById('audit').textContent='(no audit)'; return; }
  const jx = await r.json();
  document.getElementById('audit').textContent = (jx.lines||[]).map(l=>j(l)).join('\n');
}

document.addEventListener('DOMContentLoaded', refresh);

