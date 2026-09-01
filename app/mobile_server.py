"""Servidor local para tomar pedidos desde celulares y tabletas."""
from __future__ import annotations

import json
import socket
import threading
import secrets
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

from app.database.database import (
    actualizar_estado_cocina, crear_pedido_movil, entregar_unidad_comanda,
    obtener_comandas_cocina, obtener_detalle_comanda_cocina,
    obtener_productos, obtener_resumen_mesas,
    autenticar_empleado, obtener_empleados, registrar_auditoria,
    obtener_resumen_hoy, obtener_resumen_semana_actual,
    obtener_comparacion_semanal, obtener_comparativo_ventas_diarias,
    obtener_resumen_metodos_hoy, obtener_top_productos_hoy,
    obtener_etiquetas_cuentas_pedido,
    registrar_cliente,
)


PORT = 8765
_server = None
_thread = None
_sessions = {}
_sessions_lock = threading.Lock()
SESSION_SECONDS = 12 * 60 * 60


CLUB_HTML = r'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Club La Esquina</title><style>
*{box-sizing:border-box}body{margin:0;background:#f5f3ed;font-family:Arial,sans-serif;color:#242424}.wrap{max-width:520px;margin:auto;padding:22px 16px}.card{background:#fff;border-radius:18px;padding:24px;box-shadow:0 5px 20px #bbb}h1{text-align:center;margin:0;color:#202020}h1 span{display:block;color:#d4a900;font-size:18px;margin-top:5px}p{text-align:center;line-height:1.4}.benefit{background:#fff3bd;border-radius:10px;padding:12px;font-weight:bold}label{display:block;font-weight:bold;margin-top:14px}input{width:100%;padding:14px;margin-top:5px;border:1px solid #aaa;border-radius:9px;font-size:17px}.check{display:flex;gap:9px;align-items:flex-start;font-weight:normal}.check input{width:auto;margin-top:3px}button{width:100%;margin-top:20px;padding:15px;border:0;border-radius:10px;background:#27ae60;color:#fff;font-size:18px;font-weight:bold}button:disabled{background:#999}.message{padding:12px;margin-top:14px;border-radius:9px;text-align:center;display:none}.ok{display:block;background:#dff5e7;color:#145c2f}.error{display:block;background:#fde1df;color:#8a1d16}small{display:block;color:#666;margin-top:12px;text-align:center;line-height:1.35}
</style></head><body><main class="wrap"><div class="card"><h1>CLUB LA ESQUINA<span>Gracias por visitarnos</span></h1><p class="benefit">Acumula 1 punto por cada $10 de compra. Cada punto vale $0.50 para pagar.</p><form id="form"><label>Nombre<input id="nombre" maxlength="80" autocomplete="name" required></label><label>WhatsApp<input id="telefono" type="tel" inputmode="numeric" maxlength="15" autocomplete="tel" placeholder="10 dígitos" required></label><label>Cumpleaños (opcional)<input id="cumpleanos" type="date"></label><label>Correo (opcional)<input id="email" type="email" maxlength="120" autocomplete="email"></label><label class="check"><input id="acepta" type="checkbox"><span>Acepto recibir promociones de La Esquina por WhatsApp o correo.</span></label><button id="send">UNIRME AL CLUB</button></form><div id="message" class="message"></div><small>Tus datos se usarán únicamente para el programa de lealtad y promociones que autorices. Puedes pedir que dejemos de utilizarlos.</small></div></main><script>
form.onsubmit=async e=>{e.preventDefault();send.disabled=true;message.className='message';try{const r=await fetch('/api/club/registro',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({nombre:nombre.value,telefono:telefono.value,cumpleanos:cumpleanos.value,email:email.value,acepta_promociones:acepta.checked})}),d=await r.json();if(!r.ok)throw Error(d.error||'No se pudo registrar');form.style.display='none';message.className='message ok';message.textContent=`¡Bienvenido(a), ${d.nombre}! Ya eres parte del Club La Esquina. Tienes ${d.puntos} puntos.`}catch(x){message.className='message error';message.textContent=x.message;send.disabled=false}}
</script></body></html>'''


def _create_session(empleado):
    token = secrets.token_urlsafe(32)
    with _sessions_lock:
        _sessions[token] = (empleado, time.time() + SESSION_SECONDS)
    return token


def _session_from_header(handler, roles=None):
    header = handler.headers.get("Authorization", "")
    token = header[7:] if header.startswith("Bearer ") else ""
    with _sessions_lock:
        item = _sessions.get(token)
        if not item or item[1] < time.time():
            _sessions.pop(token, None)
            return None
        empleado = item[0]
    if roles and empleado["rol"] not in roles:
        return None
    return empleado


MOBILE_HTML = r'''<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1">
<title>La Esquina · Meseros</title>
<style>
:root{--yellow:#f2c94c;--green:#27ae60;--dark:#202020;--soft:#f5f3ed}
*{box-sizing:border-box}body{margin:0;font-family:Arial,sans-serif;background:var(--soft);color:#222}
header{position:sticky;top:0;z-index:3;background:var(--dark);color:#fff;padding:12px 14px;display:flex;justify-content:space-between;align-items:center}
header b{font-size:19px}header span{font-size:12px;color:#ddd}.wrap{padding:12px;max-width:900px;margin:auto}
.datos{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:12px}.datos input,.datos select,textarea{width:100%;font-size:17px;padding:12px;border:1px solid #bbb;border-radius:9px;background:#fff}
.account{display:none;margin:-3px 0 12px;padding:11px 13px;border-radius:9px;background:#fff4c7;border:1px solid #e3c14f;color:#56470d;font-size:14px;font-weight:bold}.account.open{display:block}.account strong{display:block;font-size:17px;margin-bottom:3px}
.seating{background:#fff;border-radius:12px;padding:12px;margin-bottom:12px;box-shadow:0 2px 7px #ccc}.seating h2{font-size:17px;margin:0 0 4px}.seating p{font-size:13px;color:#666;margin:0 0 10px}.table-map{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;align-items:center}.seat,.shared-seat{border:2px solid #d6d6d6;border-radius:50%;background:#fafafa;min-height:64px;padding:5px;font-weight:bold;font-size:13px;color:#333}.seat.active,.shared-seat.active{border-color:#a77d00;background:var(--yellow);box-shadow:0 0 0 3px #f8e8a4}.shared-seat{grid-column:2/4;border-radius:12px;background:#fff5ca}.dining-table{grid-column:2/4;grid-row:2/4;min-height:82px;border-radius:36px;background:#3b332d;color:#fff;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;box-shadow:inset 0 0 0 5px #766556}.dining-table b{font-size:16px}.dining-table small{color:#eadcae;margin-top:3px}.seat[data-seat="5"]{grid-column:4;grid-row:2}.seat[data-seat="6"]{grid-column:4;grid-row:3}.seat[data-seat="7"]{grid-column:3;grid-row:4}.seat[data-seat="8"]{grid-column:2;grid-row:4}.seat[data-seat="1"]{grid-column:1;grid-row:2}.seat[data-seat="2"]{grid-column:1;grid-row:3}.seat[data-seat="3"]{grid-column:2;grid-row:1}.seat[data-seat="4"]{grid-column:3;grid-row:1}.seat.hidden{display:none}
.search{width:100%;font-size:17px;padding:12px;border:1px solid #bbb;border-radius:9px;margin-bottom:10px}
.products{display:grid;grid-template-columns:repeat(2,1fr);gap:9px}.product{border:0;border-radius:10px;background:var(--yellow);min-height:76px;padding:8px;font-size:15px;font-weight:bold;box-shadow:0 2px 5px #bbb}.product small{display:block;margin-top:5px;font-size:15px}
.cart{background:#fff;border-radius:12px;padding:12px;margin:14px 0 100px;box-shadow:0 2px 7px #ccc}.cart h2{font-size:18px;margin:0 0 8px}.line{display:grid;grid-template-columns:1fr auto;gap:8px;align-items:center;padding:9px 0;border-bottom:1px solid #eee}.qty{display:flex;align-items:center;gap:8px}.qty button{width:38px;height:38px;border:0;border-radius:8px;font-size:22px}.empty{color:#777;text-align:center;padding:18px}
.bottom{position:fixed;bottom:0;left:0;right:0;background:#fff;padding:9px 12px;box-shadow:0 -2px 8px #aaa;display:flex;align-items:center;gap:10px}.total{font-size:20px;font-weight:bold;min-width:110px}.send{flex:1;border:0;border-radius:10px;background:var(--green);color:#fff;font-size:18px;font-weight:bold;padding:15px}.send:disabled{background:#aaa}
.message{display:none;position:fixed;inset:0;background:#0009;z-index:8;align-items:center;justify-content:center;padding:20px}.message div{background:#fff;border-radius:14px;padding:25px;text-align:center;max-width:400px}.message button{padding:12px 30px;background:var(--yellow);border:0;border-radius:8px;font-weight:bold}
.login{position:fixed;inset:0;background:var(--dark);z-index:20;display:flex;align-items:center;justify-content:center;padding:20px}.loginbox{background:#fff;border-radius:14px;padding:24px;width:min(420px,100%);text-align:center}.loginbox select,.loginbox input,.loginbox button{width:100%;padding:13px;margin:6px 0;font-size:17px;border-radius:8px}.loginbox button{border:0;background:var(--green);color:#fff;font-weight:bold}
@media(min-width:650px){.products{grid-template-columns:repeat(4,1fr)}}
</style>
</head>
<body>
<div id="login" class="login"><div class="loginbox"><h2>Acceso de meseros</h2><select id="employeeSelect"></select><input id="employeePin" type="password" inputmode="numeric" maxlength="8" placeholder="PIN"><button onclick="doLogin()">ENTRAR</button><p id="loginError"></p></div></div>
<header><b>LA ESQUINA · MESEROS</b><span>Pedido local</span></header>
<main class="wrap">
  <section class="datos">
    <select id="mesa"><option value="">Selecciona mesa</option></select>
    <input id="mesero" placeholder="Mesero" readonly>
  </section>
  <section class="datos">
    <select id="numeroCuentas"><option value="1">1 comensal</option><option value="2">2 comensales</option><option value="3">3 comensales</option><option value="4">4 comensales</option><option value="5">5 comensales</option><option value="6">6 comensales</option><option value="7">7 comensales</option><option value="8">8 comensales</option></select>
    <select id="cuentaActual"><option value="1">Agregar a Cuenta 1</option></select>
  </section>
  <section class="seating">
    <h2>¿Quién está ordenando?</h2><p>Toca un lugar y después agrega sus productos.</p>
    <div id="tableMap" class="table-map">
      <button class="seat active" data-seat="1">Comensal 1</button><button class="seat" data-seat="2">Comensal 2</button>
      <button class="seat" data-seat="3">Comensal 3</button><button class="seat" data-seat="4">Comensal 4</button>
      <div class="dining-table"><b id="tableName">MESA</b><small id="selectedDiner">Ordena: Comensal 1</small></div>
      <button class="seat" data-seat="5">Comensal 5</button><button class="seat" data-seat="6">Comensal 6</button>
      <button class="seat" data-seat="7">Comensal 7</button><button class="seat" data-seat="8">Comensal 8</button>
      <button id="sharedSeat" class="shared-seat">Compartido entre todos</button>
    </div>
  </section>
  <div id="accountInfo" class="account"></div>
  <input id="search" class="search" placeholder="Buscar producto…">
  <section id="products" class="products"></section>
  <section class="cart">
    <h2>Pedido actual</h2><div id="lines" class="empty">Todavía no hay productos</div>
    <textarea id="notes" rows="2" placeholder="Notas: sin cebolla, término, alergias…"></textarea>
  </section>
</main>
<div class="bottom"><div id="total" class="total">$0.00</div><button id="send" class="send" disabled>ENVIAR PEDIDO</button></div>
<div id="message" class="message"><div><h2 id="msgTitle"></h2><p id="msgText"></p><button onclick="closeMessage()">Aceptar</button></div></div>
<script>
const state={products:[],cart:{},token:'',employee:null,accounts:{}};
const money=n=>new Intl.NumberFormat('es-MX',{style:'currency',currency:'MXN'}).format(n);
for(let i=1;i<=20;i++){const o=document.createElement('option');o.value=`Mesa ${i}`;o.textContent=`Mesa ${i}`;mesa.appendChild(o)}const barra=document.createElement('option');barra.value='Barra';barra.textContent='Barra';mesa.appendChild(barra);
async function loadEmployees(){try{const r=await fetch('/api/empleados?tipo=mesero'),data=await r.json();employeeSelect.replaceChildren(...data.map(e=>{const o=document.createElement('option');o.value=e.id;o.textContent=e.nombre;return o}))}catch(e){loginError.textContent='No se pudieron leer los empleados'}}
async function doLogin(){loginError.textContent='';try{const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({empleado_id:Number(employeeSelect.value),pin:employeePin.value,tipo:'mesero'})}),data=await r.json();if(!r.ok)throw Error(data.error||'PIN incorrecto');state.token=data.token;state.employee=data.empleado;mesero.value=data.empleado.nombre;login.style.display='none';await loadTables()}catch(e){loginError.textContent=e.message;employeePin.value=''}}
async function loadTables(){try{const selected=mesa.value,r=await fetch('/api/mesas',{cache:'no-store',headers:{'Authorization':'Bearer '+state.token}});if(r.status===401){login.style.display='flex';return}if(!r.ok)throw Error();const data=await r.json();state.accounts=Object.fromEntries(data.filter(x=>x.ocupada).map(x=>[x.mesa,x]));[...mesa.options].forEach(o=>{if(!o.value)return;const a=state.accounts[o.value];o.textContent=a?`${o.value} · Cuenta ${money(a.total)}`:o.value});mesa.value=selected;showAccount()}catch(e){showMessage('Sin conexión','No se pudo consultar el estado de las mesas.')}}
function showAccount(){const a=state.accounts[mesa.value];if(!a){accountInfo.className='account';accountInfo.textContent='';return}accountInfo.className='account open';accountInfo.replaceChildren();const title=document.createElement('strong'),detail=document.createElement('span');title.textContent=`Cuenta abierta · ${money(a.total)}`;detail.textContent=`${a.pedidos} pedido${a.pedidos===1?'':'s'} pendiente${a.pedidos===1?'':'s'}. Lo nuevo se agregará a esta cuenta.`;accountInfo.append(title,detail)}
async function load(){try{const r=await fetch('/api/productos');if(!r.ok)throw Error();state.products=await r.json();renderProducts()}catch(e){showMessage('Sin conexión','No se pudo leer el menú. Verifica la computadora principal.')}}
function renderProducts(){const q=search.value.toLowerCase().trim();products.replaceChildren();state.products.filter(p=>p.nombre.toLowerCase().includes(q)).forEach(p=>{const b=document.createElement('button'),price=document.createElement('small');b.className='product';b.textContent=p.nombre;price.textContent=money(p.precio);b.appendChild(price);b.onclick=()=>add(p.id);products.appendChild(b)})}
function selectDiner(target){cuentaActual.value=target;document.querySelectorAll('.seat,.shared-seat').forEach(x=>x.classList.remove('active'));if(target==='shared'){sharedSeat.classList.add('active');selectedDiner.textContent='Ordena: Compartido entre todos'}else{const seat=document.querySelector(`.seat[data-seat="${target}"]`);if(seat)seat.classList.add('active');selectedDiner.textContent=`Ordena: Comensal ${target}`}}
function renderSeating(){const n=Number(numeroCuentas.value);document.querySelectorAll('.seat').forEach(x=>x.classList.toggle('hidden',Number(x.dataset.seat)>n));sharedSeat.style.display=n>1?'block':'none';tableName.textContent=mesa.value||'MESA';const valid=cuentaActual.value==='shared'?n>1:Number(cuentaActual.value)<=n;selectDiner(valid?cuentaActual.value:'1')}
function rebuildAccounts(){const n=Number(numeroCuentas.value),old=cuentaActual.value;cuentaActual.replaceChildren();for(let i=1;i<=n;i++){const o=document.createElement('option');o.value=String(i);o.textContent=`Agregar a Comensal ${i}`;cuentaActual.appendChild(o)}if(n>1){const s=document.createElement('option');s.value='shared';s.textContent='Compartido entre todos';cuentaActual.appendChild(s)}cuentaActual.value=[...cuentaActual.options].some(o=>o.value===old)?old:'1';renderSeating()}
function add(id){const target=cuentaActual.value,n=Number(numeroCuentas.value),key=`${id}:${target}`;if(!state.cart[key])state.cart[key]={producto_id:id,cantidad:0,cuenta_numero:target==='shared'?0:Number(target),cuentas_compartidas:target==='shared'?Array.from({length:n},(_,i)=>i+1):[]};state.cart[key].cantidad++;renderCart()}
function change(key,d){state.cart[key].cantidad+=d;if(state.cart[key].cantidad<=0)delete state.cart[key];renderCart()}
function renderCart(){const keys=Object.keys(state.cart);if(!keys.length){lines.className='empty';lines.textContent='Todavía no hay productos';total.textContent='$0.00';send.disabled=true;return}lines.className='';let sum=0;lines.replaceChildren();keys.forEach(key=>{const item=state.cart[key],p=state.products.find(x=>x.id==item.producto_id),q=item.cantidad;if(!p)return;sum+=p.precio*q;const d=document.createElement('div'),info=document.createElement('div'),name=document.createElement('b'),br=document.createElement('br'),subtotal=document.createElement('small'),account=document.createElement('small'),controls=document.createElement('div'),minus=document.createElement('button'),quantity=document.createElement('b'),plus=document.createElement('button');d.className='line';name.textContent=p.nombre;subtotal.textContent=money(p.precio*q);account.textContent=item.cuentas_compartidas.length?' · Compartido':` · Comensal ${item.cuenta_numero}`;info.append(name,br,subtotal,account);controls.className='qty';minus.textContent='−';minus.onclick=()=>change(key,-1);quantity.textContent=q;plus.textContent='+';plus.onclick=()=>change(key,1);controls.append(minus,quantity,plus);d.append(info,controls);lines.appendChild(d)});total.textContent=money(sum);send.disabled=false}
search.oninput=renderProducts;
mesa.onchange=()=>{showAccount();renderSeating()};
cuentaActual.onchange=()=>selectDiner(cuentaActual.value);
document.querySelectorAll('.seat').forEach(x=>x.onclick=()=>selectDiner(x.dataset.seat));sharedSeat.onclick=()=>selectDiner('shared');
numeroCuentas.onchange=()=>{if(Object.keys(state.cart).length){showMessage('Pedido en curso','El número de cuentas no puede cambiar después de agregar productos. Vacía el pedido primero.');numeroCuentas.value=String(Math.max(1,...Object.values(state.cart).flatMap(x=>x.cuentas_compartidas.length?x.cuentas_compartidas:[x.cuenta_numero])))}rebuildAccounts()};
send.onclick=async()=>{if(!mesa.value)return showMessage('Falta la mesa','Selecciona el número de mesa.');send.disabled=true;const selected=mesa.value,existing=Boolean(state.accounts[selected]),body={mesa:selected,notas:notes.value.trim(),items:Object.values(state.cart)};try{const r=await fetch('/api/pedidos',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+state.token},body:JSON.stringify(body)});const data=await r.json();if(r.status===401){login.style.display='flex';throw Error('La sesión terminó. Ingresa nuevamente.')}if(!r.ok)throw Error(data.error||'No se pudo enviar');showMessage(existing?'Productos agregados a la cuenta':`Pedido #${data.pedido_id} enviado`,`${selected} · Pedido ${money(data.total)} · Cuenta acumulada ${money(data.cuenta_total)}.`);state.cart={};notes.value='';renderCart();await loadTables()}catch(e){showMessage('No se envió',e.message);send.disabled=false}}
function showMessage(t,x){msgTitle.textContent=t;msgText.textContent=x;message.style.display='flex'}function closeMessage(){message.style.display='none'}
rebuildAccounts();loadEmployees();load();
</script>
</body></html>'''


KITCHEN_HTML = r'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>La Esquina · Cocina</title>
<style>
:root{--dark:#202020;--yellow:#f2c94c;--blue:#3498db;--green:#27ae60;--red:#c0392b;--bg:#ececec}
*{box-sizing:border-box}body{margin:0;background:var(--bg);font-family:Arial,sans-serif;color:#222}
header{position:sticky;top:0;z-index:5;background:var(--dark);color:#fff;padding:13px 18px;display:flex;justify-content:space-between;align-items:center;box-shadow:0 2px 8px #777}header b{font-size:22px}header span{font-size:13px}.board{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px;padding:12px}.empty{grid-column:1/-1;text-align:center;background:#fff;padding:50px;border-radius:12px;color:#666;font-size:20px}
.ticket{background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 3px 10px #bbb;border-top:8px solid var(--yellow)}.ticket.Preparando{border-color:var(--blue)}.ticket.Listo{border-color:var(--green)}
.login{position:fixed;inset:0;background:var(--dark);z-index:20;display:flex;align-items:center;justify-content:center;padding:20px}.loginbox{background:#fff;border-radius:14px;padding:24px;width:min(420px,100%);text-align:center}.loginbox select,.loginbox input,.loginbox button{width:100%;padding:13px;margin:6px 0;font-size:17px;border-radius:8px}.loginbox button{border:0;background:var(--green);color:#fff;font-weight:bold}
.head{display:flex;justify-content:space-between;padding:12px 14px 5px}.mesa{font-size:23px;font-weight:bold}.time{font-weight:bold;color:#555}.meta{padding:0 14px 10px;color:#555;font-size:14px}.items{border-top:1px solid #ddd;border-bottom:1px solid #ddd;padding:8px 14px}.item{display:grid;grid-template-columns:42px 1fr auto;gap:7px;align-items:center;padding:7px 0;font-size:18px;border-bottom:1px solid #eee}.item:last-child{border-bottom:0}.item.delivered{color:#777;text-decoration:line-through}.qty{font-weight:bold}.deliver-item{border:0;border-radius:7px;background:#ff6f00;color:white;padding:9px 10px;font-size:13px;font-weight:bold}.deliver-item:disabled{background:#bbb}.notes{margin:10px 14px;padding:9px;background:#fff3cd;border:1px solid #e7c755;border-radius:7px;font-weight:bold}.status{padding:9px 14px;font-weight:bold}.actions{display:grid;grid-template-columns:repeat(3,1fr);gap:7px;padding:0 12px 12px}.actions button{border:0;border-radius:8px;padding:12px 5px;font-weight:bold;color:#fff;font-size:14px}.prep{background:var(--blue)}.ready{background:var(--green)}.done{background:#ff6f00 !important; color:white !important;}.flash{animation:flash 1s 3}@keyframes flash{50%{background:#fff3a0}}
@media(max-width:600px){header b{font-size:18px}.board{grid-template-columns:1fr}}
</style></head><body><div id="login" class="login"><div class="loginbox"><h2>Acceso de cocina</h2><select id="employeeSelect"></select><input id="employeePin" type="password" inputmode="numeric" maxlength="8" placeholder="PIN"><button onclick="doLogin()">ENTRAR</button><p id="loginError"></p></div></div>
<header><b>LA ESQUINA · COCINA</b><span id="clock">Actualizando…</span></header><main id="board" class="board"></main>
<script>
let known=new Set(),token='';function esc(x){return String(x??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
async function loadEmployees(){try{const r=await fetch('/api/empleados?tipo=cocina'),data=await r.json();employeeSelect.replaceChildren(...data.map(e=>{const o=document.createElement('option');o.value=e.id;o.textContent=e.nombre;return o}))}catch(e){loginError.textContent='No se pudieron leer los empleados'}}
async function doLogin(){loginError.textContent='';try{const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({empleado_id:Number(employeeSelect.value),pin:employeePin.value,tipo:'cocina'})}),data=await r.json();if(!r.ok)throw Error(data.error||'PIN incorrecto');token=data.token;login.style.display='none';load()}catch(e){loginError.textContent=e.message;employeePin.value=''}}
async function load(){if(!token)return;try{const r=await fetch('/api/cocina',{cache:'no-store',headers:{'Authorization':'Bearer '+token}});if(r.status===401){login.style.display='flex';token='';return}const data=await r.json();render(data);clock.textContent='Actualizado '+new Date().toLocaleTimeString('es-MX',{hour:'2-digit',minute:'2-digit',second:'2-digit'})}catch(e){clock.textContent='Sin conexión'}}
function render(data){if(!data.length){board.innerHTML='<div class="empty">No hay comandas pendientes</div>';known=new Set();return}const incoming=new Set(data.map(x=>x.id));board.innerHTML='';data.forEach(o=>{const t=document.createElement('article');t.className=`ticket ${o.estado_cocina}${known.has(o.id)?'':' flash'}`;const items=o.items.map(i=>{const pending=i.cantidad-i.entregada,done=pending===0;return `<div class="item ${done?'delivered':''}"><span class="qty">${done?'✓':pending+'x'}</span><span>${esc(i.producto)} <small>${esc(i.cuenta||'')}</small>${i.entregada?` <small>(${i.entregada}/${i.cantidad})</small>`:''}</span><button class="deliver-item" ${done?'disabled':''} onclick="deliverItem(${o.id},${i.detalle_id})">${done?'ENTREGADO':'ENTREGAR 1'}</button></div>`}).join('');t.innerHTML=`<div class="head"><span class="mesa">${esc(o.mesa)}</span><span class="time">${esc(o.hora)}</span></div><div class="meta">Pedido #${o.id} · ${esc(o.mesero)}</div><div class="items">${items}</div>${o.notas?`<div class="notes">NOTA: ${esc(o.notas)}</div>`:''}<div class="status">Estado: ${esc(o.estado_cocina)}</div><div class="actions"><button class="prep" onclick="status(${o.id},'Preparando')">PREPARANDO</button><button class="ready" onclick="status(${o.id},'Listo')">LISTO</button><button class="done" onclick="status(${o.id},'Entregado')">ENTREGAR TODO</button></div>`;board.appendChild(t)});known=incoming}
async function status(id,estado){await fetch('/api/cocina/estado',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify({pedido_id:id,estado_cocina:estado})});load()}
async function deliverItem(pedidoId,detalleId){const r=await fetch('/api/cocina/item',{method:'POST',headers:{'Content-Type':'application/json','Authorization':'Bearer '+token},body:JSON.stringify({pedido_id:pedidoId,detalle_id:detalleId})});if(r.status===401){login.style.display='flex';token='';return}load()}
loadEmployees();setInterval(load,3000);
</script></body></html>'''


OWNER_HTML = r'''<!doctype html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>La Esquina · Propietario</title><style>
:root{--dark:#20231f;--gold:#e0b52c;--gray:#9ba198;--green:#26965b;--bg:#f2f3ef}*{box-sizing:border-box}body{margin:0;background:var(--bg);font-family:Arial,sans-serif;color:#252924}header{position:sticky;top:0;z-index:3;background:var(--dark);color:#fff;padding:15px 16px}header b{font-size:20px}header small{display:block;color:#cfd2cd;margin-top:3px}.wrap{max-width:980px;margin:auto;padding:12px}.cards{display:grid;grid-template-columns:repeat(2,1fr);gap:9px}.card,.panel{background:#fff;border:1px solid #d9ddd5;border-radius:12px;padding:13px}.card small{color:#70766d;font-weight:bold}.card strong{display:block;font-size:25px;margin-top:7px}.panel{margin-top:11px}.panel h2{font-size:17px;margin:0 0 12px}.legend{display:flex;gap:18px;font-size:12px;margin-bottom:10px}.dot{display:inline-block;width:11px;height:11px;border-radius:3px;margin-right:5px}.chart{height:220px;display:flex;gap:5px;align-items:flex-end;border-bottom:1px solid #ccd0ca;padding:12px 3px 0}.day{height:100%;flex:1;display:flex;align-items:flex-end;justify-content:center;gap:2px;position:relative;padding-bottom:25px}.bar{width:38%;min-height:1px;border-radius:4px 4px 0 0}.day label{position:absolute;bottom:3px;font-size:11px;font-weight:bold}.rows .row{display:grid;grid-template-columns:1fr auto;gap:8px;padding:9px 0;border-bottom:1px solid #eceee9}.rows .row:last-child{border:0}.account{color:#8d5c00}.login{position:fixed;inset:0;background:var(--dark);z-index:20;display:flex;align-items:center;justify-content:center;padding:20px}.loginbox{background:#fff;border-radius:14px;padding:24px;width:min(420px,100%);text-align:center}.loginbox select,.loginbox input,.loginbox button{width:100%;padding:13px;margin:6px 0;font-size:17px;border-radius:8px}.loginbox button{border:0;background:var(--green);color:#fff;font-weight:bold}.updated{text-align:center;color:#6e746b;font-size:12px;padding:14px}@media(min-width:700px){.cards{grid-template-columns:repeat(4,1fr)}.columns{display:grid;grid-template-columns:1fr 1fr;gap:11px}}
</style></head><body>
<div id="login" class="login"><div class="loginbox"><h2>Acceso del propietario</h2><select id="employeeSelect"></select><input id="employeePin" type="password" inputmode="numeric" maxlength="8" placeholder="PIN de administrador"><button onclick="doLogin()">ENTRAR</button><p id="loginError"></p></div></div>
<header><b>LA ESQUINA · DASHBOARD</b><small>Consulta privada · solo lectura</small></header><main class="wrap"><section id="cards" class="cards"></section><section class="panel"><h2>Comparativo semanal por día</h2><div class="legend"><span><i class="dot" style="background:var(--gold)"></i>Actual</span><span><i class="dot" style="background:var(--gray)"></i>Anterior</span></div><div id="chart" class="chart"></div></section><div class="columns"><section class="panel"><h2>Formas de pago · Hoy</h2><div id="payments" class="rows"></div></section><section class="panel"><h2>Productos más vendidos · Hoy</h2><div id="products" class="rows"></div></section></div><section class="panel"><h2>Cuentas activas</h2><div id="accounts" class="rows"></div></section><div id="updated" class="updated"></div></main>
<script>
let token='';const money=n=>new Intl.NumberFormat('es-MX',{style:'currency',currency:'MXN'}).format(Number(n||0));
async function loadEmployees(){try{const r=await fetch('/api/empleados?tipo=propietario'),data=await r.json();employeeSelect.replaceChildren(...data.map(e=>{const o=document.createElement('option');o.value=e.id;o.textContent=e.nombre;return o}))}catch(e){loginError.textContent='No se pudieron leer los administradores'}}
async function doLogin(){loginError.textContent='';try{const r=await fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({empleado_id:Number(employeeSelect.value),pin:employeePin.value,tipo:'propietario'})}),data=await r.json();if(!r.ok)throw Error(data.error||'PIN incorrecto');token=data.token;login.style.display='none';load()}catch(e){loginError.textContent=e.message;employeePin.value=''}}
function row(parent,left,right,cls=''){const d=document.createElement('div'),a=document.createElement('span'),b=document.createElement('b');d.className='row '+cls;a.textContent=left;b.textContent=right;d.append(a,b);parent.appendChild(d)}
function card(title,value){const d=document.createElement('div'),s=document.createElement('small'),b=document.createElement('strong');d.className='card';s.textContent=title;b.textContent=value;d.append(s,b);cards.appendChild(d)}
function render(d){cards.replaceChildren();card('VENTA HOY',money(d.hoy.venta_total));card('TICKETS',d.hoy.tickets);card('PERSONAS',d.hoy.personas);card('VENTA SEMANAL',money(d.semana.venta_total));chart.replaceChildren();const mx=Math.max(1,...d.dias.flatMap(x=>[x.actual,x.anterior]));d.dias.forEach(x=>{const day=document.createElement('div'),old=document.createElement('div'),now=document.createElement('div'),label=document.createElement('label');day.className='day';old.className='bar';now.className='bar';old.style.background='var(--gray)';now.style.background='var(--gold)';old.style.height=(x.anterior/mx*100)+'%';now.style.height=(x.actual/mx*100)+'%';old.title=money(x.anterior);now.title=money(x.actual);label.textContent=x.nombre;day.append(old,now,label);chart.appendChild(day)});payments.replaceChildren();Object.entries(d.metodos).forEach(([m,v])=>row(payments,m,money(v.total)));products.replaceChildren();d.productos.forEach(x=>row(products,`${x.nombre} · ${x.unidades} u.`,money(x.ingreso)));accounts.replaceChildren();if(!d.cuentas.length)row(accounts,'No hay cuentas abiertas','');d.cuentas.forEach(x=>row(accounts,`${x.mesa} · ${x.pedidos} pedido(s)`,money(x.total),'account'));updated.textContent='Actualizado '+new Date().toLocaleTimeString('es-MX')}
async function load(){if(!token)return;try{const r=await fetch('/api/propietario',{cache:'no-store',headers:{Authorization:'Bearer '+token}});if(r.status===401){token='';login.style.display='flex';return}if(!r.ok)throw Error();render(await r.json())}catch(e){updated.textContent='Sin conexión con la caja'}}loadEmployees();setInterval(load,30000);
</script></body></html>'''


def _json_bytes(data):
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


class MobileHandler(BaseHTTPRequestHandler):
    server_version = "LaEsquinaLocal/1.0"

    def log_message(self, _format, *_args):
        return

    def _send(self, status, content, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        if path == "/":
            self._send(200, MOBILE_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/cocina":
            self._send(200, KITCHEN_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/propietario":
            self._send(200, OWNER_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/club":
            self._send(200, CLUB_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/productos":
            productos = [
                {"id": p[0], "nombre": p[1], "precio": p[2], "categoria": p[3]}
                for p in obtener_productos(solo_activos=True)
            ]
            self._send(200, _json_bytes(productos), "application/json; charset=utf-8")
            return
        if path == "/api/empleados":
            tipo = parse_qs(parsed.query).get("tipo", ["mesero"])[0]
            if tipo not in ("mesero", "cocina", "propietario"):
                self._send(400, _json_bytes({"error": "Tipo de acceso no válido"}),
                           "application/json; charset=utf-8")
                return
            if tipo == "mesero":
                roles = ("Mesero", "Administrador", "Caja")
            elif tipo == "cocina":
                roles = ("Cocina", "Administrador")
            else:
                roles = ("Administrador",)
            empleados = [
                {"id": e[0], "nombre": e[1], "rol": e[2]}
                for e in obtener_empleados(True) if e[2] in roles
            ]
            self._send(200, _json_bytes(empleados), "application/json; charset=utf-8")
            return
        if path == "/api/mesas":
            if not _session_from_header(self, ("Mesero", "Administrador", "Caja")):
                self._send(401, _json_bytes({"error": "Acceso denegado"}),
                           "application/json; charset=utf-8")
                return
            self._send(200, _json_bytes(obtener_resumen_mesas()),
                       "application/json; charset=utf-8")
            return
        if path == "/api/cocina":
            if not _session_from_header(self, ("Cocina", "Administrador")):
                self._send(401, _json_bytes({"error": "Acceso denegado"}), "application/json")
                return
            comandas = []
            for pedido in obtener_comandas_cocina():
                (pedido_id, fecha, mesa, mesero, notas, total,
                 estado, estado_cocina, actualizado) = pedido
                detalles = obtener_detalle_comanda_cocina(pedido_id)
                etiquetas_cuentas = obtener_etiquetas_cuentas_pedido(pedido_id)
                comandas.append({
                    "id": pedido_id, "fecha": fecha, "hora": fecha[11:16],
                    "mesa": mesa, "mesero": mesero, "notas": notas,
                    "total": total, "estado": estado,
                    "estado_cocina": estado_cocina,
                    "actualizado": actualizado,
                    "items": [
                        {
                            "detalle_id": d[0], "producto_id": d[1],
                            "producto": d[2], "cantidad": d[3],
                            "entregada": d[4], "precio": d[5],
                            "cuenta": etiquetas_cuentas.get(d[1], ""),
                        }
                        for d in detalles
                    ],
                })
            self._send(200, _json_bytes(comandas), "application/json; charset=utf-8")
            return
        if path == "/api/propietario":
            empleado = _session_from_header(self, ("Administrador",))
            if empleado is None:
                self._send(401, _json_bytes({"error": "Acceso denegado"}),
                           "application/json; charset=utf-8")
                return
            productos = [
                {"nombre": p[0], "unidades": p[1], "ingreso": p[2]}
                for p in obtener_top_productos_hoy()
            ]
            cuentas = [m for m in obtener_resumen_mesas() if m["ocupada"]]
            self._send(200, _json_bytes({
                "hoy": obtener_resumen_hoy(),
                "semana": obtener_resumen_semana_actual(),
                "comparacion": obtener_comparacion_semanal(),
                "dias": obtener_comparativo_ventas_diarias(),
                "metodos": obtener_resumen_metodos_hoy(),
                "productos": productos,
                "cuentas": cuentas,
            }), "application/json; charset=utf-8")
            return
        self._send(404, _json_bytes({"error": "No encontrado"}), "application/json")

    def do_POST(self):
        path = urlparse(self.path).path
        if path not in (
            "/api/login", "/api/pedidos", "/api/cocina/estado",
            "/api/cocina/item",
            "/api/club/registro",
        ):
            self._send(404, _json_bytes({"error": "No encontrado"}), "application/json")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 100000:
                raise ValueError("Pedido no valido.")
            data = json.loads(self.rfile.read(length).decode("utf-8"))
            if path == "/api/club/registro":
                cliente = registrar_cliente(
                    data.get("nombre", ""), data.get("telefono", ""),
                    data.get("cumpleanos", ""), data.get("email", ""),
                    bool(data.get("acepta_promociones", False)),
                )
                self._send(201, _json_bytes({
                    "ok": True, "nombre": cliente["nombre"],
                    "puntos": cliente["puntos"],
                }), "application/json; charset=utf-8")
            elif path == "/api/login":
                tipo = data.get("tipo", "")
                if tipo not in ("mesero", "cocina", "propietario"):
                    raise ValueError("Tipo de acceso no válido.")
                if tipo == "mesero":
                    roles = ("Mesero", "Administrador", "Caja")
                elif tipo == "cocina":
                    roles = ("Cocina", "Administrador")
                else:
                    roles = ("Administrador",)
                empleado = autenticar_empleado(
                    data.get("empleado_id"), data.get("pin", ""), roles
                )
                if empleado is None:
                    self._send(401, _json_bytes({"error": "PIN incorrecto o sin permiso"}), "application/json")
                    return
                token = _create_session(empleado)
                registrar_auditoria(empleado, "Iniciar sesión", "Web", None, tipo)
                self._send(200, _json_bytes({"token": token, "empleado": empleado}),
                           "application/json; charset=utf-8")
            elif path == "/api/pedidos":
                empleado = _session_from_header(
                    self, ("Mesero", "Administrador", "Caja")
                )
                if empleado is None:
                    self._send(401, _json_bytes({"error": "Sesión no válida"}), "application/json")
                    return
                pedido_id, total = crear_pedido_movil(
                    data.get("mesa", ""), empleado["nombre"],
                    data.get("items", []), data.get("notas", ""),
                    empleado["id"],
                )
                registrar_auditoria(
                    empleado, "Enviar", "Pedido", pedido_id,
                    f"{data.get('mesa', '')} - ${total:.2f}",
                )
                mesa_actual = next(
                    (m for m in obtener_resumen_mesas()
                     if m["mesa"] == str(data.get("mesa", "")).strip()),
                    None,
                )
                cuenta_total = mesa_actual["total"] if mesa_actual else total
                self._send(201, _json_bytes({
                    "pedido_id": pedido_id, "total": total,
                    "cuenta_total": cuenta_total,
                }),
                           "application/json; charset=utf-8")
            elif path == "/api/cocina/estado":
                empleado = _session_from_header(
                    self, ("Cocina", "Administrador")
                )
                if empleado is None:
                    self._send(401, _json_bytes({"error": "Sesión no válida"}), "application/json")
                    return
                actualizar_estado_cocina(
                    data.get("pedido_id"), data.get("estado_cocina", "")
                )
                registrar_auditoria(
                    empleado, "Cambiar estado", "Comanda",
                    data.get("pedido_id"), data.get("estado_cocina", ""),
                )
                self._send(200, _json_bytes({"ok": True}),
                           "application/json; charset=utf-8")
            else:
                empleado = _session_from_header(
                    self, ("Cocina", "Administrador")
                )
                if empleado is None:
                    self._send(401, _json_bytes({"error": "Sesión no válida"}),
                               "application/json; charset=utf-8")
                    return
                completado = entregar_unidad_comanda(
                    data.get("pedido_id"), data.get("detalle_id")
                )
                registrar_auditoria(
                    empleado, "Entregar platillo", "Comanda",
                    data.get("pedido_id"),
                    f"Detalle #{data.get('detalle_id')}",
                )
                self._send(200, _json_bytes({
                    "ok": True, "completado": completado,
                }), "application/json; charset=utf-8")
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._send(400, _json_bytes({"error": str(error)}),
                       "application/json; charset=utf-8")
        except Exception:
            self._send(500, _json_bytes({"error": "Error interno del servidor"}),
                       "application/json; charset=utf-8")


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def local_ip():
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        address = sock.getsockname()[0]
        sock.close()
        return address
    except OSError:
        return "127.0.0.1"


def mobile_url():
    return f"http://{local_ip()}:{PORT}"


def club_url():
    return f"{mobile_url()}/club"


def start_mobile_server():
    global _server, _thread
    if _thread and _thread.is_alive():
        return mobile_url()
    _server = ReusableThreadingHTTPServer(("0.0.0.0", PORT), MobileHandler)
    _thread = threading.Thread(target=_server.serve_forever, daemon=True)
    _thread.start()
    return mobile_url()
