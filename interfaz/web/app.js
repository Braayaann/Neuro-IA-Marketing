// Coordenadas CSS: nunca multiplicar la mirada por DPR. DPR solo mejora el raster.
const $=id=>document.getElementById(id);
const token=document.querySelector('meta[name=session-token]').content;
const cliente=sessionStorage.getItem('ocular-cliente')||crypto.randomUUID();
sessionStorage.setItem('ocular-cliente',cliente);
let estado=null, objetivoEnviado=null, mouse=null, mouseDentro=false, busy=false;
let heatBitmap=null, ultimoHeat='', heatBusy=false, reporteAnterior=null;
let modoDibujado=null;
let dibujoEnviado=null,comparacionAnterior=null;
let errorHasta=0,ultimoError='';
function mostrarError(e){ultimoError=e.message;errorHasta=Date.now()+6000;$('mensaje').textContent=ultimoError;}
const canvas=$('heatmap-canvas'), ctx=canvas.getContext('2d');
$('camara').value=new URLSearchParams(location.search).get('camara')||0;

function geometria(){
  const v=window.visualViewport, rects={};
  for(const id of ['moda','tecnologia','naturaleza','titulo']){
    const r=$(id).getBoundingClientRect(); rects[id]=[r.x,r.y,r.width,r.height];
  }
  return {w:innerWidth,h:innerHeight,dpr:devicePixelRatio,screenX,screenY,outerW:outerWidth,outerH:outerHeight,
    scrollX,scrollY,scale:v?.scale||1,offsetX:v?.offsetLeft||0,offsetY:v?.offsetTop||0,rects};
}
function contexto(){return {cliente,geometria:geometria(),visible:!document.hidden&&document.hasFocus()};}
async function api(ruta,datos={}){
  const response=await fetch('/api/'+ruta,{method:'POST',headers:{'Content-Type':'application/json','X-Session-Token':token},body:JSON.stringify({...contexto(),...datos})});
  const data=await response.json();
  if(!response.ok)throw new Error(data.error||'Error de comunicación');
  return data;
}
async function accion(nombre,datos={}){
  try{estado=await api('comando',{accion:nombre,camara:Number($('camara').value),...datos});errorHasta=0;pintarEstado();return true;}
  catch(e){mostrarError(e);return false;}
}
for(const boton of document.querySelectorAll('[data-action]'))boton.onclick=()=>accion(boton.dataset.action);
$('clear-btn').onclick=()=>accion('limpiar');
$('modo').onchange=()=>{mouse=null;mouseDentro=false;accion('modo',{modo:$('modo').value});};
$('ver-diagnostico').onclick=()=>{$('diagnostico').hidden=!$('diagnostico').hidden;};
$('cerrar-diagnostico').onclick=()=>{$('diagnostico').hidden=true;};
$('usar-modelo').onclick=()=>accion('seleccionar_modelo',{modelo:$('modelo-elegido').value});
$('calor-visible').onchange=()=>{canvas.hidden=!$('calor-visible').checked;};
document.addEventListener('mousemove',e=>{mouse=[e.clientX/(innerWidth-1),e.clientY/(innerHeight-1)];mouseDentro=true;});
document.addEventListener('mouseleave',()=>{mouseDentro=false;});
window.addEventListener('blur',()=>{mouseDentro=false;mouse=null;api('estado').catch(()=>{});});
document.addEventListener('visibilitychange',()=>api('estado').catch(()=>{}));
window.addEventListener('resize',()=>{redimensionar();ultimoHeat='';});
function redimensionar(){
  canvas.width=Math.round(innerWidth*devicePixelRatio);canvas.height=Math.round(innerHeight*devicePixelRatio);
  ctx.setTransform(devicePixelRatio,0,0,devicePixelRatio,0,0);
  dibujarHeat();
}
function normalizadaACSS(p){return [p[0]*(innerWidth-1),p[1]*(innerHeight-1)];}
function colocarPunto(elemento,p){const [x,y]=normalizadaACSS(p);elemento.style.left=`${x}px`;elemento.style.top=`${y}px`;}
function dibujarHeat(){if(estado?.estado==='dibujo')return;ctx.clearRect(0,0,innerWidth,innerHeight);if(heatBitmap)ctx.drawImage(heatBitmap,0,0,innerWidth,innerHeight);}
async function actualizarHeat(forzar=false){
  const firma=JSON.stringify([estado?.modo,estado?.seleccion,estado?.mapa_revision,geometria()]);
  if(estado?.estado==='dibujo'||heatBusy||(!forzar&&firma===ultimoHeat))return;
  heatBusy=true;
  const modo=estado?.modo;
  const modelo=estado?.seleccion;
  try{
    const r=await fetch('/api/mapa.png?modo='+encodeURIComponent(modo||'ocular')+'&modelo='+encodeURIComponent(modelo||'R'),{headers:{'X-Session-Token':token}});
    if(!r.ok||r.status===204)return;
    const bitmap=await createImageBitmap(await r.blob());
    if(modo!==estado?.modo||modelo!==estado?.seleccion||estado?.estado==='dibujo'){bitmap.close();return;}
    heatBitmap?.close();heatBitmap=bitmap;ultimoHeat=firma;dibujarHeat();
  }finally{heatBusy=false;}
}
$('guardar').onclick=async()=>{
  try{
    if(!await accion('guardar'))return;
    const modo=estado.modo;
    const r=await fetch('/api/mapa.png?modo='+modo+'&modelo='+estado.seleccion,{headers:{'X-Session-Token':token}});
    if(!r.ok)throw new Error('No se pudo descargar el mapa');
    const url=URL.createObjectURL(await r.blob()), enlace=document.createElement('a');
    enlace.href=url;enlace.download=`mapa-${modo}-${estado.seleccion}-${Date.now()}.png`;enlace.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
  }catch(e){$('mensaje').textContent=e.message;}
};
function pintarEstado(){
  const s=estado;if(!s)return;
  const claveMapa=s.modo+':'+s.seleccion;
  if(modoDibujado!==claveMapa){heatBitmap?.close();heatBitmap=null;ultimoHeat='';modoDibujado=claveMapa;dibujarHeat();}
  document.body.classList.toggle('ocular',s.modo==='ocular');$('modo').value=s.modo;
  $('mensaje').textContent=Date.now()<errorHasta?ultimoError:s.mensaje;
  $('estado-corto').textContent=`${s.modo==='mouse'?'DEMO MOUSE':'OCULAR'} · ${s.camara?'Cámara conectada':'Cámara desconectada'} · ${s.rostro?'Rostro detectado':'Sin rostro'} · ${s.fps.toFixed(1)} FPS · ${s.segundos.toFixed(1)} s`;
  const enFase=['esperando_punto','capturando','ajustando','reintento'].includes(s.estado);
  const comprobando=s.estado==='dibujo';
  document.body.classList.toggle('comprobando',comprobando);
  for(const b of document.querySelectorAll('[data-action]')){
    const a=b.dataset.action;
    b.disabled=(a==='camara_iniciar'&&s.camara)||(a==='camara_detener'&&!s.camara)||
      (a==='calibrar'&&(!s.camara||s.modo!=='ocular'||enFase||comprobando))||
      (a==='validar'&&(!s.calibracion||!s.camara||s.modo!=='ocular'||enFase||comprobando))||
      (a==='comprobar_dibujo'&&(enFase||comprobando))||
      (a==='demo'&&(s.modo!=='mouse'||s.demo_activo))||
      (a==='seguir'&&(!s.validacion?.cumple_criterios||s.modo!=='ocular'||s.estado!=='reposo'));
  }
  $('fase').hidden=!enFase;$('repetir-punto').hidden=s.estado!=='reintento';
  if(enFase||comprobando)$('diagnostico').hidden=true;
  const puedeElegir=!!s.comparacion?.reportes?.A&&s.estado==='reposo';
  $('modelo-elegido').disabled=!puedeElegir;$('usar-modelo').disabled=!puedeElegir;
  $('fase-titulo').textContent=s.objetivo?.fase==='validar'?'Validación independiente':'Calibración ocular';
  $('fase-progreso').textContent=s.objetivo?`Punto ${s.objetivo.indice+1}/${s.objetivo.total} · ${s.objetivo.n} muestras · ${s.objetivo.restante===null?'Preparando':s.objetivo.restante.toFixed(1)+' s'}`:s.mensaje;
  $('objetivo').hidden=!s.objetivo;
  if(s.objetivo){
    const o=s.objetivo;colocarPunto($('objetivo'),o.punto);
    if(s.estado==='esperando_punto'&&objetivoEnviado!==o.nonce){
      objetivoEnviado=o.nonce;
      // Confirmar posición medida después de dos oportunidades reales de pintado.
      requestAnimationFrame(()=>requestAnimationFrame(async()=>{
        if(estado?.objetivo?.nonce!==o.nonce)return;
        const r=$('objetivo').getBoundingClientRect();
        try{estado=await api('objetivo',{nonce:o.nonce,x:r.x+r.width/2,y:r.y+r.height/2});}
        catch(e){objetivoEnviado=null;$('mensaje').textContent=e.message;}
      }));
    }
  }
  const punto=s.gaze?.suave;
  $('mirada').hidden=!$('punto-visible').checked||!punto||s.estado!=='seguimiento';
  if(punto)colocarPunto($('mirada'),punto);
  if(s.prueba_dibujo){
    $('mirada').hidden=false;colocarPunto($('mirada'),s.prueba_dibujo.normalizado);
    if(dibujoEnviado!==s.prueba_dibujo.nonce)comprobarDibujo(s.prueba_dibujo);
  }else if(dibujoEnviado){dibujoEnviado=null;ultimoHeat='';dibujarHeat();canvas.hidden=!$('calor-visible').checked;}
  const rd=s.reporte_dibujo;
  $('dibujo-informe').textContent=rd?`Dibujo ${rd.cumple?'correcto':'con error'}: máximo DOM ${rd.max_error_dom_px.toFixed(3)} px; Canvas ${rd.max_error_canvas_px.toFixed(3)} px CSS. No mide precisión ocular.`:'Dibujo: pendiente de comprobación.';
  $('estado-detalle').textContent=`Cámara: ${s.camara?'conectada':'desconectada'}\nRostro: ${s.rostro?'detectado':'no detectado'}\nCalibración: ${s.calibracion?'completada':'pendiente'}\nSeguimiento: ${s.estado==='seguimiento'?'activo':'detenido'}\nFiltro: ${s.motivo}\nDetección: ${s.deteccion_ms.toFixed(1)} ms\nEstimación: ${s.estimacion_ms.toFixed(2)} ms\nPitch: ${s.pitch?.toFixed(1)??'—'}°\nAperturas: ${s.aperturas.map(v=>v.toFixed(3)).join(' / ')}\n`+
    (s.calibracion?`Modelo: ${s.calibracion.variables}, grado ${s.calibracion.grado}\nError CV por objetivo: ${s.calibracion.error_cv.toFixed(3)} unidades normalizadas (NO validación)`:'');
  $('preview').hidden=!s.preview;if(s.preview&&!$('diagnostico').hidden)$('preview').src='data:image/jpeg;base64,'+s.preview;
  $('estado-detalle').textContent+=`\nModelo activo: ${s.seleccion}\nYaw / pitch / roll: ${s.pose?s.pose.map(v=>v.toFixed(2)+'°').join(' / '):'—'}`;
  const firmaAB=JSON.stringify([s.comparacion,s.seleccion]);
  if(firmaAB!==comparacionAnterior){comparacionAnterior=firmaAB;mostrarComparacion(s.comparacion,s.seleccion);}
  const firma=JSON.stringify(s.validacion);
  if(firma!==reporteAnterior){reporteAnterior=firma;mostrarValidacion(s.validacion);}
}
function mostrarValidacion(v){
  const c=$('validacion-grafico'),p=c.getContext('2d');p.clearRect(0,0,c.width,c.height);
  $('tabla-validacion').replaceChildren();
  if(!v){$('resumen-validacion').textContent='Validación pendiente. No hay precisión medida.';return;}
  $('resumen-validacion').innerHTML=`<strong class="${v.cumple_criterios?'bien':'mal'}">${v.cumple_criterios?'Cumple criterios exploratorios':'Resultado insuficiente: recalibrar'}</strong><br>Error: ${v.error_px.toFixed(1)} px CSS (${(v.error_normalizado_diagonal*100).toFixed(1)} % de la diagonal)<br>Horizontal: ${v.error_horizontal_px.toFixed(1)} px · Vertical: ${v.error_vertical_px.toFixed(1)} px<br>Regiones: ${(v.acierto_regiones*100).toFixed(1)} % · Válidas: ${v.muestras_validas}/${v.intentos}<br>Dispersión: ${v.estabilidad_rms_px.toFixed(1)} px · Guardas rechazarían: ${v.guardas_rechazarian}`;
  const nota=document.createElement('p');nota.textContent=`Sesgo vertical medio: ${v.sesgo_y_px?.toFixed(1)??'—'} px. Negativo = por encima del objetivo. ${v.sesgo_diagnostico?.texto||''}`;$('resumen-validacion').append(nota);
  const tabla=document.createElement('table');tabla.innerHTML='<thead><tr><th>Zona / punto</th><th>Total px</th><th>X px</th><th>Y px</th><th>Sesgo Y</th><th>N</th></tr></thead>';
  const cuerpo=document.createElement('tbody');
  for(const [zona,z] of Object.entries(v.por_zona))agregarFila(zona,z,z.muestras);
  for(const z of v.por_punto)agregarFila('P'+z.punto+' '+z.zona,z,z.n);
  function agregarFila(nombre,z,n){const tr=document.createElement('tr');for(const valor of [nombre,z.error_px.toFixed(1),z.error_horizontal_px.toFixed(1),z.error_vertical_px.toFixed(1),z.sesgo_y_px.toFixed(1),n]){const td=document.createElement('td');td.textContent=valor;tr.append(td);}cuerpo.append(tr);}
  tabla.append(cuerpo);$('tabla-validacion').append(tabla);
  p.strokeStyle='#334155';for(let i=1;i<3;i++){p.beginPath();p.moveTo(i*c.width/3,0);p.lineTo(i*c.width/3,c.height);p.moveTo(0,i*c.height/3);p.lineTo(c.width,i*c.height/3);p.stroke();}
  for(const z of v.por_punto){const [x,y]=z.objetivo,[u,w]=z.estimado;p.strokeStyle='#fda4af';p.beginPath();p.moveTo(x*c.width,y*c.height);p.lineTo(u*c.width,w*c.height);p.stroke();for(const [a,b,color] of [[x,y,'white'],[u,w,'#22d3ee']]){p.fillStyle=color;p.beginPath();p.arc(a*c.width,b*c.height,4,0,7);p.fill();}}
}
function mostrarComparacion(c,activo){
  const box=$('comparacion-ab');box.replaceChildren();if(!c){box.textContent='Comparación A/B pendiente.';return;}
  const intro=document.createElement('p');intro.textContent=`Activo: ${activo}. ${c.pose_calibracion.aviso} Desviación yaw/pitch/roll: ${c.pose_calibracion.std_deg.map(v=>v.toFixed(2)).join(' / ')}°.`;box.append(intro);
  if(!c.reportes.A){box.append(document.createTextNode('Modelos ajustados; falta validación independiente.'));return;}
  const tabla=document.createElement('table');tabla.innerHTML='<thead><tr><th>Modelo</th><th>Total</th><th>X</th><th>Y</th><th>Sesgo Y</th><th>RMS</th></tr></thead>';
  const cuerpo=document.createElement('tbody');
  for(const id of ['R','A','B']){
    const r=c.reportes[id],tr=document.createElement('tr');
    for(const valor of [id==='R'?'Referencia':id,r.error_px,r.error_horizontal_px,r.error_vertical_px,r.sesgo_y_px,r.estabilidad_rms_px]){const td=document.createElement('td');td.textContent=typeof valor==='number'?valor.toFixed(1):valor;tr.append(td);}cuerpo.append(tr);
    for(const [zona,z] of Object.entries(r.por_zona)){const fila=document.createElement('tr');for(const v of ['↳ '+zona,z.error_px,z.error_horizontal_px,z.error_vertical_px,z.sesgo_y_px,z.estabilidad_rms_px]){const td=document.createElement('td');td.textContent=typeof v==='number'?v.toFixed(1):v;fila.append(td);}cuerpo.append(fila);}
  }
  tabla.append(cuerpo);box.append(tabla);const fin=document.createElement('p');fin.textContent=`Valores en px CSS. Sugerencia: ${c.recomendado||'recalibrar'}. ${c.conclusion}`;box.append(fin);
}
function comprobarDibujo(o){
  dibujoEnviado=o.nonce;canvas.hidden=false;
  ctx.clearRect(0,0,innerWidth,innerHeight);
  const [x,y]=normalizadaACSS(o.normalizado);
  ctx.fillStyle='#00ffff';ctx.beginPath();ctx.arc(x,y,4,0,2*Math.PI);ctx.fill();
  requestAnimationFrame(()=>requestAnimationFrame(async()=>{
    if(estado?.prueba_dibujo?.nonce!==o.nonce)return;
    try{
      const dom=$('mirada').getBoundingClientRect(),r=canvas.getBoundingClientRect();
      const radio=Math.ceil(6*devicePixelRatio),cx=x*devicePixelRatio,cy=y*devicePixelRatio;
      const ix=Math.max(0,Math.floor(cx)-radio),iy=Math.max(0,Math.floor(cy)-radio);
      const w=Math.min(canvas.width-ix,2*radio+2),h=Math.min(canvas.height-iy,2*radio+2);
      const pixels=ctx.getImageData(ix,iy,w,h).data;let peso=0,sx=0,sy=0;
      for(let j=0;j<h;j++)for(let i=0;i<w;i++){const a=pixels[(j*w+i)*4+3];peso+=a;sx+=(ix+i+.5)*a;sy+=(iy+j+.5)*a;}
      if(!peso)throw new Error('No se encontró el punto en Canvas');
      estado=await api('dibujo',{nonce:o.nonce,dom:[dom.x+dom.width/2,dom.y+dom.height/2],
        canvas:[r.x+sx/peso/canvas.width*r.width,r.y+sy/peso/canvas.height*r.height]});
      pintarEstado();
    }catch(e){mostrarError(e);dibujoEnviado=null;}
  }));
}
async function poll(){
  if(busy)return;busy=true;
  try{estado=await api(estado?.modo==='mouse'?'mouse':'estado',estado?.modo==='mouse'?{punto:mouseDentro?mouse:null}:{});pintarEstado();}
  catch(e){$('mensaje').textContent=e.message;}
  finally{busy=false;}
}
redimensionar();poll();setInterval(poll,80);setInterval(()=>actualizarHeat().catch(e=>{$('mensaje').textContent=e.message;}),300);
