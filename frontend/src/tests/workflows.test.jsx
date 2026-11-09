// @vitest-environment jsdom
import React from 'react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {render, screen, cleanup, waitFor} from '@testing-library/react';
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
    else if(path.endsWith('/results'))data={study:{name:'Sin observaciones',slots:[],status:'completed'},ads:[],total_samples:0,valid_samples:0,valid_ratio:0,estimated_seconds:0,warning:'Estimación'};
    else throw new Error('Solicitud inesperada: '+path);
    return {ok:true,json:async()=>data};
  });
});
afterEach(()=>{cleanup();vi.restoreAllMocks()});

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

  it('explica la ausencia de resultados sin mostrar métricas inventadas',async()=>{
    render(<Results id={1} go={()=>{}}/>);
    expect(await screen.findByRole('heading',{name:'Esta sesión no tiene observaciones'})).toBeTruthy();
    expect(screen.queryByText('Mapa de mirada estimada')).toBeNull();
  });
});
