// @vitest-environment jsdom
import React from 'react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {act, fireEvent, render, screen, cleanup, waitFor, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {App} from '../App';
import {AdModal} from '../pages/Ads';
import {StudyModal} from '../pages/Sessions';
import {Results} from '../pages/Results';

const user={id:1,name:'Persona de prueba',role:'owner',email:'prueba@test.cl'};
let requests;
let state;
beforeEach(()=>{
  location.hash='';
  requests=[];
  state={user:null,ads:[],studies:[]};
  global.fetch=vi.fn(async(url,options={})=>{
    const path=String(url).replace('/api','');
    requests.push({path,options});
    let data;
    if(path==='/auth/me')data={user:state.user,csrf:'test-token'};
    else if(path==='/auth/login'){state.user=user;data={user,csrf:'new-token'}}
    else if(path==='/ads'&&options.method==='POST'){data={id:9,...JSON.parse(options.body)};state.ads.push(data)}
    else if(path==='/ads')data=state.ads;
    else if(path==='/ads/9' && options.method==='DELETE')data={};
    else if(path==='/studies/15/calibration/start')data={ok:true};
    else if(path==='/studies'&&options.method==='POST')data={id:15,...JSON.parse(options.body)};
    else if(path==='/studies')data=state.studies;
    else if(path==='/studies/15' && options.method==='DELETE'){
      state.studies=state.studies.filter(s=>s.id!==15);
      data={};
    }
    else if(path==='/studies/15')data=state.studies[0];
    else if(path==='/vision/status')data={enabled:true,mediapipe:true};
    else if(path==='/studies/15/ads' && options.method==='PATCH'){
      const {ad_ids}=JSON.parse(options.body);
      data={...state.studies[0],slots:ad_ids.map((id,position)=>({
        ...state.ads.find(ad=>ad.id===id),ad_id:id,position
      }))};
    }
    else if(path.endsWith('/results'))data={study:{name:'Sin observaciones',slots:[],status:'completed'},ads:[],total_samples:0,valid_samples:0,valid_ratio:0,estimated_seconds:0,warning:'Estimación'};
    else throw new Error('Solicitud inesperada: '+path);
    return {ok:true,json:async()=>data};
  });
});
afterEach(()=>{cleanup();vi.restoreAllMocks();vi.unstubAllGlobals()});

describe('Flujos principales del frontend',()=>{
  it('confirma el anuncio antes de eliminarlo del catálogo', async()=>{
    state.user=user;
    state.ads=[{id:9,title:'Cartel',active:true}];
    location.hash='ads';
    const u=userEvent.setup();
    render(<App/>);
    await u.click(await screen.findByRole('button',{name:'Eliminar Cartel'}));
    expect(screen.getByRole('dialog').textContent).toContain('«Cartel»');
    await u.click(screen.getByRole('button',{name:'Cancelar'}));
    expect(requests.some(r=>r.options.method==='DELETE')).toBe(false);
    await u.click(screen.getByRole('button',{name:'Eliminar Cartel'}));
    await u.click(screen.getByRole('button',{name:'Eliminar anuncio'}));
    expect(screen.queryByText('Cartel')).toBeNull();
    expect(requests.filter(r=>r.path==='/ads/9'&&r.options.method==='DELETE')).toHaveLength(1);
  });

  it('calibra contra el área visible y vuelve a preparación si se pierde la cámara',async()=>{
    state.user=user;
    state.studies=[{id:15,name:'Prueba',status:'draft',slots:[{id:1,position:0}]}];
    location.hash='exhibit/15';
    const track=Object.assign(new EventTarget(),{readyState:'live',getSettings:()=>({}),stop:vi.fn()});
    const stream={active:true,getVideoTracks:()=>[track],getTracks:()=>[track]};
    Object.defineProperty(navigator,'mediaDevices',{configurable:true,value:{
      getUserMedia:async()=>stream, enumerateDevices:async()=>[]
    }});
    vi.spyOn(HTMLElement.prototype,'getBoundingClientRect').mockReturnValue({width:1084,height:427});
    try {
      const {container}=render(<App/>);
      await userEvent.click(await screen.findByRole('button',{name:'Conectar cámara'}));
      fireEvent.loadedData(container.querySelector('.capturevideo'));
      await userEvent.click(screen.getByRole('button',{name:/Calibrar mirada/}));
      await waitFor(()=>expect(requests.some(r=>r.path.endsWith('/calibration/start'))).toBe(true));
      expect(JSON.parse(requests.find(r=>r.path.endsWith('/calibration/start')).options.body)).toMatchObject({
        width:1084,height:427
      });
      act(()=>track.dispatchEvent(new Event('ended')));
      expect(screen.getByRole('button',{name:'Reconectar cámara'})).toBeTruthy();
      expect(screen.getByRole('button',{name:'Iniciar exhibición'}).disabled).toBe(true);
    } finally {delete navigator.mediaDevices;}
  });
  it('mantiene el tema elegido al entrar, navegar y volver a abrir el portal', async()=>{
    const u=userEvent.setup();
    localStorage.removeItem('neuroia.theme');
    const first=render(<App/>);
    await u.click(await screen.findByRole('button',{name:'Oscuro'}));
    expect(document.documentElement.dataset.theme).toBe('dark');
    first.unmount();
    state.user=user;
    render(<App/>);
    expect((await screen.findByRole('button',{name:'Oscuro'})).getAttribute('aria-pressed')).toBe('true');
    await u.click(screen.getByRole('button',{name:'Sesiones'}));
    expect(document.documentElement.dataset.theme).toBe('dark');
    await u.click(screen.getByRole('button',{name:'Claro'}));
    expect(localStorage.getItem('neuroia.theme')).toBe('light');
    expect(document.documentElement.dataset.theme).toBe('light');
  });
  it('filtra por estado, permite cancelar y elimina de ambos listados al confirmar',async()=>{
    const u=userEvent.setup();
    state.user=user;
    const study={id:15,owner_id:1,name:'Campaña A',status:'completed',created_at:'2026-01-01',slots:[]};
    state.studies=[study,{...study,id:16,name:'Otra cuenta',owner_id:2,status:'cancelled'},
      {...study,id:17,name:'Captura en curso',status:'running'}];
    location.hash='sessions';
    render(<App/>);
    await screen.findByText('Campaña A');
    expect(screen.getAllByRole('button',{name:'Eliminar sesión'})).toHaveLength(1);
    const filter=screen.getByLabelText('Filtrar por estado');
    await u.selectOptions(filter,'cancelled');
    expect(screen.getByText('Otra cuenta')).toBeTruthy();
    expect(screen.queryByText('Campaña A')).toBeNull();
    await u.selectOptions(filter,'completed');
    await u.click(screen.getByRole('button',{name:'Eliminar sesión'}));
    const dialog=screen.getByRole('dialog',{name:'Eliminar sesión'});
    expect(dialog.textContent).toContain('«Campaña A»');
    expect(dialog.textContent).toContain('sus resultados');
    await u.click(within(dialog).getByRole('button',{name:'Cancelar'}));
    expect(requests.some(r=>r.options.method==='DELETE')).toBe(false);
    expect(screen.getByText('Campaña A')).toBeTruthy();
    await u.click(screen.getByRole('button',{name:'Eliminar sesión'}));
    await u.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Eliminar sesión'}));
    expect(screen.queryByText('Campaña A')).toBeNull();
    await u.click(screen.getByRole('button',{name:'Resultados'}));
    expect(screen.getByText('Otra cuenta')).toBeTruthy();
    expect(screen.queryByText('Campaña A')).toBeNull();
    expect(requests.filter(r=>r.options.method==='DELETE')).toHaveLength(1);
  });
  it('permite ingresar y muestra el espacio del dueño sin cuentas de administrador',async()=>{
    const u=userEvent.setup();render(<App/>);
    await u.type(await screen.findByLabelText('Correo electrónico'),'prueba@test.cl');
    await u.type(screen.getByLabelText('Contraseña'),'Password12345');
    await u.click(screen.getByRole('button',{name:/Entrar a mi espacio/}));
    expect(await screen.findByRole('heading',{name:'Una mirada a tu espacio.'})).toBeTruthy();
    expect(screen.queryByRole('button',{name:'Cuentas'})).toBeNull();
    const login=requests.find(r=>r.path==='/auth/login');
    expect(login.options.headers['X-CSRF-Token']).toBe('test-token');
  });

  it('guarda el anuncio y devuelve el control al listado',async()=>{
    const saved=vi.fn(),u=userEvent.setup();render(<AdModal saved={saved} onClose={()=>{}}/>);
    await u.type(screen.getByLabelText('Título del anuncio'),'Mi anuncio');
    await u.type(screen.getByLabelText('Descripción'),'Mensaje de prueba');
    await u.click(screen.getByRole('button',{name:'Guardar anuncio'}));
    await waitFor(()=>expect(saved).toHaveBeenCalledOnce());
    const body=JSON.parse(requests.find(r=>r.path==='/ads').options.body);
    expect(body).toEqual({title:'Mi anuncio',description:'Mensaje de prueba',color:'#c7f36b',active:true});
  });

  it('conserva el orden de anuncios y el modo seleccionado al crear una sesión',async()=>{
    const u=userEvent.setup(),created=vi.fn();
    render(<StudyModal ads={[{id:1,title:'Primero',color:'#ffffff'},{id:2,title:'Segundo',color:'#ffffff'}]} created={created} onClose={()=>{}}/>);
    await u.type(screen.getByLabelText('Nombre de la sesión'),'Sesión de prueba');
    await u.click(screen.getByRole('button',{name:/Segundo/}));
    await u.click(screen.getByRole('button',{name:/Primero/}));
    await u.click(screen.getByLabelText('Analizar también expresiones faciales con RMN'));
    await u.click(screen.getByRole('button',{name:'Continuar'}));
    await waitFor(()=>expect(created).toHaveBeenCalledOnce());
    expect(created.mock.calls[0][0].ad_ids).toEqual([2,1]);
    expect(created.mock.calls[0][0].with_emotions).toBe(false);
  });

  it('muestra el archivo antes del guardado y recupera la imagen anterior al descartar un reemplazo dañado',async()=>{
    const u=userEvent.setup();
    const revoke=vi.fn();
    vi.stubGlobal('URL',class extends URL {
      static createObjectURL(file){return 'blob:'+file.name}
      static revokeObjectURL=revoke;
    });
    vi.stubGlobal('Image',class {
      naturalWidth=400;
      naturalHeight=800;
      set src(url){if(url.endsWith('rota.jpg')) this.onerror(); else this.onload()}
    });
    render(<AdModal ad={{id:3,title:'Original',image_url:'/original.jpg'}} onClose={()=>{}} saved={()=>{}}/>);
    const input=screen.getByLabelText(/Reemplazar imagen/);
    await u.upload(input,new File(['foto'],'retrato.jpg',{type:'image/jpeg'}));
    expect(screen.getByText('retrato.jpg')).toBeTruthy();
    expect(screen.getByAltText('Vista previa de la imagen seleccionada').src).toBe('blob:retrato.jpg');
    await u.upload(input,new File(['dañada'],'rota.jpg',{type:'image/jpeg'}));
    expect(screen.getByRole('alert').textContent).toMatch(/dañada/);
    expect(screen.getByAltText('Imagen actual del anuncio').src).toContain('/original.jpg');
    expect(screen.getByRole('button',{name:'Guardar anuncio'}).disabled).toBe(true);
    await u.click(screen.getByRole('button',{name:'Descartar archivo'}));
    expect(screen.getByRole('button',{name:'Guardar anuncio'}).disabled).toBe(false);
    expect(revoke).toHaveBeenCalledWith('blob:retrato.jpg');
    expect(requests).toHaveLength(0);
  });

  it('explica los requisitos para iniciar y reserva Cerrar sesión para la cuenta', async()=>{
    state.user=user;
    state.studies=[{id:15,name:'Preparación',status:'draft',slots:[],calibrated:false}];
    location.hash='exhibit/15';
    render(<App/>);
    const start=await screen.findByRole('button',{name:'Iniciar exhibición'});
    expect(start.disabled).toBe(true);
    const reasons=within(screen.getByRole('list',{name:'Pendiente para iniciar'}));
    expect(reasons.getAllByRole('listitem')).toHaveLength(3);
    expect(screen.getByRole('button',{name:'Cancelar preparación'})).toBeTruthy();
    expect(screen.queryByRole('button',{name:'Cerrar sesión'})).toBeNull();
  });

  it('permite sustituir anuncios desde preparación y actualiza la vista conjunta en la misma sesión',async()=>{
    const u=userEvent.setup();
    state.user=user;
    state.ads=[{id:1,title:'Retrato',image_url:'/retrato.jpg',active:true},
      {id:2,title:'Paisaje',image_url:'/paisaje.jpg',active:true},
      {id:3,title:'Texto',active:true}];
    state.studies=[{id:15,owner_id:1,name:'Prueba',status:'draft',slots:[{...state.ads[0],ad_id:1,position:0}]}];
    location.hash='exhibit/15';
    render(<App/>);
    await u.click(await screen.findByRole('button',{name:'Modificar anuncios'}));
    const dialog=within(screen.getByRole('dialog'));
    const paisaje=dialog.getByRole('button',{name:'Paisaje'});
    expect(paisaje.querySelector('img').src).toContain('/paisaje.jpg');
    expect(dialog.getByRole('button',{name:'Texto'}).querySelector('img')).toBeNull();
    await u.click(paisaje);
    const preview=dialog.getByLabelText('Vista previa de la distribución');
    expect([...preview.querySelectorAll('img')].map(img=>img.alt)).toEqual(['Retrato','Paisaje']);
    await u.click(dialog.getByRole('button',{name:/^Retrato/}));
    expect([...preview.querySelectorAll('img')].map(img=>img.alt)).toEqual(['Paisaje']);
    await u.click(dialog.getByRole('button',{name:'Guardar selección'}));
    await waitFor(()=>expect(screen.queryByRole('dialog')).toBeNull());
    expect(screen.getByAltText('Paisaje')).toBeTruthy();
    expect(location.hash).toBe('#exhibit/15');
    expect(JSON.parse(requests.find(r=>r.path==='/studies/15/ads').options.body)).toEqual({ad_ids:[2]});
  });

  it('explica la ausencia de resultados sin mostrar métricas inventadas',async()=>{
    render(<Results id={1} go={()=>{}}/>);
    expect(await screen.findByRole('heading',{name:'Esta sesión no tiene observaciones'})).toBeTruthy();
    expect(screen.queryByText('Mapa de mirada estimada')).toBeNull();
  });
});
