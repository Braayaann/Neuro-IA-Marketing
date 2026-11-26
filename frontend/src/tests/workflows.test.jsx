// @vitest-environment jsdom
import React from 'react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {render, screen, cleanup, waitFor, within} from '@testing-library/react';
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
    else if(path==='/studies'&&options.method==='POST')data={id:15,...JSON.parse(options.body)};
    else if(path==='/studies')data=state.studies;
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
    state.studies=[{id:15,name:'Prueba',status:'draft',slots:[{...state.ads[0],ad_id:1,position:0}]}];
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
