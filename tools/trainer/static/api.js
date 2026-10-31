// Requests to the training manager. Paths are relative, so they resolve against the page's own address.
export async function api(path,opts){const r=await fetch(path,{cache:'no-store',...opts});const b=await r.json().catch(()=>({}));if(!r.ok)throw new Error(b.error||r.statusText);return b}
export const post=(path,body)=>api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body||{})});
