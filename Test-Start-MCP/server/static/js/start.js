let es=null; let esLogs=null;
function headers(){
  const t = localStorage.getItem('TSM_TOKEN') || '';
  const h = {'Content-Type':'application/json','Accept':'application/json'};
  if (t) h['Authorization'] = 'Bearer '+t; return h;
}
function j(o){ try { return JSON.stringify(o, null, 2) } catch(e){ return String(o) } }
function parseArgs(s){
  if (!s) return [];
  const t = s.trim();
  if (t.startsWith('[')) { try { return JSON.parse(t) } catch(e){ return [] } }
  return t.split(',').map(x=>x.trim()).filter(Boolean);
}
async function loadAllowed(){
  const r = await fetch('/actions/list_allowed', {method:'POST', headers: headers(), body: '{}'});
  document.getElementById('allowedOut').textContent = j(await r.json());
}
async function runScript(){
  const path = document.getElementById('sp').value;
  const args = parseArgs(document.getElementById('sa').value);
  const timeout_ms = parseInt(document.getElementById('st').value||'0')||null;
  const body = { path, args, timeout_ms };
  const r = await fetch('/actions/run_script', {method:'POST', headers: headers(), body: JSON.stringify(body)});
  document.getElementById('runOut').textContent = j(await r.json());
}
function startStream(){
  stopStream();
  const path = document.getElementById('ssp').value;
  const args = document.getElementById('ssa').value;
  const timeout_ms = parseInt(document.getElementById('sst').value||'0')||null;
  const q = new URLSearchParams();
  q.set('path', path);
  if (args) q.set('args', args);
  if (timeout_ms) q.set('timeout_ms', String(timeout_ms));
  const url = '/sse/run_script_stream?' + q.toString();
  const out = document.getElementById('streamOut');
  out.textContent = '';
  es = new EventSource(url);
  es.onmessage = (ev)=>{ out.textContent += ev.data + "\n" };
  es.addEventListener('stdout', ev=>{ out.textContent += '[stdout] '+ev.data+"\n" });
  es.addEventListener('stderr', ev=>{ out.textContent += '[stderr] '+ev.data+"\n" });
  es.addEventListener('end', ev=>{ out.textContent += '[end] '+ev.data+"\n" });
  es.addEventListener('error', ev=>{ out.textContent += '[error] '+ev.data+"\n" });
}
function stopStream(){ if (es){ es.close(); es=null; } }
function openLogs(){
  closeLogs();
  const out = document.getElementById('logsOut'); out.textContent='';
  esLogs = new EventSource('/sse/logs_stream');
  esLogs.addEventListener('log', ev=>{ out.textContent += ev.data+"\n" });
  esLogs.onmessage = (ev)=>{ out.textContent += ev.data+"\n" };
  esLogs.addEventListener('info', ev=>{ out.textContent += '[info] '+ev.data+"\n" });
  esLogs.addEventListener('error', ev=>{ out.textContent += '[error] '+ev.data+"\n" });
}
function closeLogs(){ if (esLogs){ esLogs.close(); esLogs=null; } }
async function getStats(){
  const r = await fetch('/actions/get_stats', {method:'POST', headers: headers(), body: '{}'});
  document.getElementById('statsOut').textContent = j(await r.json());
}
async function health(){
  const r = await fetch('/healthz');
  document.getElementById('healthOut').textContent = j(await r.json());
}

