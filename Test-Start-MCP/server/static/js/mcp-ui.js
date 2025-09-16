function headers(){
  const t = localStorage.getItem('TSM_TOKEN') || '';
  const h = {'Content-Type':'application/json','Accept':'application/json'};
  if (t) h['Authorization'] = 'Bearer '+t;
  return h;
}
function j(o){ try { return JSON.stringify(o, null, 2) } catch(e){ return String(o) } }

async function initMcp(){
  const p = document.getElementById('proto').value || '2025-06-18';
  const body = { jsonrpc:'2.0', id:1, method:'initialize', params:{ protocolVersion:p, capabilities:{}, clientInfo:{ name:'mcp-ui', version:'1' } } };
  const r = await fetch('/mcp', { method:'POST', headers: headers(), body: JSON.stringify(body) });
  document.getElementById('initOut').textContent = j(await r.json());
}
async function listTools(){
  const body = [
    { jsonrpc:'2.0', id:1, method:'initialize', params:{ protocolVersion:'2025-06-18', capabilities:{}, clientInfo:{ name:'mcp-ui', version:'1' } } },
    { jsonrpc:'2.0', id:2, method:'tools/list' }
  ];
  const r = await fetch('/mcp', { method:'POST', headers: headers(), body: JSON.stringify(body) });
  document.getElementById('toolsOut').textContent = j(await r.json());
}
async function callTool(){
  let args = {};
  try { args = JSON.parse(document.getElementById('targs').value || '{}'); } catch(e){ alert('Invalid JSON for arguments'); return; }
  const name = document.getElementById('tname').value || '';
  const body = { jsonrpc:'2.0', id:3, method:'tools/call', params:{ name, arguments: args } };
  const r = await fetch('/mcp', { method:'POST', headers: headers(), body: JSON.stringify(body) });
  document.getElementById('callOut').textContent = j(await r.json());
}

