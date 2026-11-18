import {test,expect} from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

const date='2026-11-15T15:00:00.000000Z';
const orders=[{orderId:'o_pending',status:'PENDING',pickupAddress:'Calle 18 # 5-24',feeMinor:8500},{orderId:'o_active',status:'ASSIGNED',pickupAddress:'Café del Mar',feeMinor:9500}].map(o=>({...o,createdAt:date,updatedAt:date,zoneId:'centro',dropoffAddress:'Carrera 4 # 12-31',version:1}));
async function fixture(page,{role='STORE',theme='light',signedIn=true,profile='enabled'}={}) {
  await page.addInitScript(({role,theme,signedIn})=>{
    localStorage.setItem('flashdelivery:theme:v1',theme);
    if(signedIn)localStorage.setItem('fd.session',JSON.stringify({token:'test',actor:{role,actorId:'actor_private'}}));
  },{role,theme,signedIn});
  const calls=[];
  await page.route('**/api/v1/**',async route=>{
    const request=route.request(),path=new URL(request.url()).pathname.slice(7);calls.push({path,method:request.method()});
    let body;
    if(path==='/auth/dev-login'){const actor={actorId:'actor_private',role:request.postDataJSON().role};body={token:'test',actor};}
    else if(path==='/zones')body={items:[{zoneId:'centro',name:'Centro'}]};
    else if(path==='/stores/me'||path==='/couriers/me'){
      if(profile==='missing')return route.fulfill({status:404,json:{error:{code:'NOT_FOUND',message:'Registra tu perfil'}}});
      body={storeId:'actor_private',courierId:'actor_private',name:role==='COURIER'?'Andrés Pérez':'Café del Mar',zoneId:'centro',enabled:!['waiting','suspended'].includes(profile),approvalStatus:profile==='suspended'?'SUSPENDED':undefined,available:true};
    }else if(path==='/admin/stores'||path==='/admin/couriers')body={items:[],nextCursor:null};
    else if(path==='/stores/me/orders')body={items:orders,nextCursor:null};
    else if(path==='/stores/me/stats')body={deliveredCount:2,totalFeeMinor:19000,source:'cache'};
    else if(path==='/zones/centro/couriers')body={items:[{courierId:'courier_1',expiresInSeconds:60}],nextCursor:null};
    else if(path==='/couriers/me/active')body={order:orders[1]};
    else if(path==='/orders/available')body={items:[orders[0]],nextCursor:null};
    else if(path==='/couriers/me/orders')body={items:[],nextCursor:null};
    else if(path==='/couriers/me/heartbeat')body={expiresInSeconds:60};
    else if(path.endsWith('/location'))body={orderId:'o_active',status:'ASSIGNED',updatedAt:date,location:null,freshness:'UNAVAILABLE'};
    else if(path.startsWith('/tracking/'))body={orderId:'o_active',status:'ASSIGNED',updatedAt:date,events:[{eventType:'CREATED',occurredAt:date},{eventType:'ASSIGNED',occurredAt:date}],nextCursor:null};
    else if(path.endsWith('/events'))body={items:[{eventType:'CREATED',occurredAt:date}],nextCursor:null};
    else if(path.startsWith('/orders/'))body=orders[1];
    else throw new Error('Ruta no simulada: '+path);
    return route.fulfill({json:body});
  });
  return calls;
}
const views={access:{signedIn:false,route:'/'},store:{role:'STORE',route:'/#/comercio'},courier:{role:'COURIER',route:'/#/repartidor'},admin:{role:'ADMIN',route:'/#/admin'},tracking:{role:'STORE',route:'/#/seguimiento/o_active.secret'}};
for(const [view,options] of Object.entries(views))for(const theme of ['light','dark'])for(const width of [360,390,768,1024,1440]){
  test(`${view} ${theme} ${width}: diseño funcional, contraste y sin desbordes`,async({page},info)=>{
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await fixture(page,{...options,theme});await page.setViewportSize({width,height:1000});await page.goto(options.route);
    await expect(page.getByRole('heading',{level:1}).or(page.getByRole('heading',{name:'Tu pedido',exact:true}))).toBeVisible();
    await page.evaluate(()=>document.fonts.ready);
    await expect(page.locator('html')).toHaveAttribute('data-theme',theme);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
    expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze()).violations).toEqual([]);
    if(view==='tracking') {await expect(page.getByRole('navigation',{name:'Navegación de Comercio'})).toHaveCount(0);await expect(page.getByText('actor_private',{exact:true})).toHaveCount(0);}
    expect(errors).toEqual([]);
    await page.screenshot({path:info.outputPath(`${view}-${theme}-${width}.png`),fullPage:true});
  });
}
test('mapa integrado conserva shell, tema y regreso al pedido',async({page})=>{
  await fixture(page,{role:'COURIER'});await page.goto('/#/repartidor');
  await page.getByRole('link',{name:'Compartir ubicación',exact:true}).click();
  await expect(page).toHaveURL(/#\/ubicacion\/o_active$/);
  await expect(page.getByRole('banner')).toHaveCount(1);
  await expect(page.getByRole('combobox',{name:'Apariencia'})).toHaveCount(1);
  await expect(page.getByRole('heading',{name:'Compartir mi ubicación'})).toBeVisible();
  await page.getByRole('combobox',{name:'Apariencia'}).selectOption('dark');
  await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
  await page.getByRole('link',{name:'Volver al pedido'}).click();
  await expect(page.getByRole('heading',{name:'Vamos con la próxima.'})).toBeVisible();
  await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
});
test('menú móvil abre con teclado, navega a sección y permite cerrar sesión',async({page})=>{
  await fixture(page);await page.setViewportSize({width:390,height:844});await page.goto('/#/comercio');
  const menu=page.getByRole('button',{name:'Abrir menú'});await menu.focus();await page.keyboard.press('Enter');
  const drawer=page.getByRole('dialog',{name:'Menú de navegación'});await expect(drawer).toBeVisible();
  await page.keyboard.press('Escape');await expect(drawer).not.toBeVisible();await expect(menu).toBeFocused();
  await page.getByRole('navigation',{name:'Navegación móvil'}).getByRole('link',{name:'Nueva entrega'}).click();
  await expect(page.getByLabel('Recoger en',{exact:true})).toBeInViewport();
  await menu.click();await drawer.getByRole('button',{name:'Cerrar sesión'}).click();
  await expect(page.getByRole('heading',{name:'Todo listo para tu próxima entrega.'})).toBeVisible();
});
for(const profile of ['missing','waiting'])test(`registro y habilitación ${profile} con diseño unificado`,async({page})=>{
  await fixture(page,{profile});await page.goto('/#/comercio');
  await expect(page.getByRole('navigation',{name:'Navegación de Comercio'})).toBeVisible();
  await expect(profile==='missing'?page.getByRole('heading',{name:'Registra tu comercio'}):page.getByText('Tu comercio está pendiente de habilitación.')).toBeVisible();
});
for(const status of [200,503])test(`consulta tardía ${status} no reemplaza el mapa ni reactiva la pantalla anterior`,async({page})=>{
  const calls=await fixture(page,{role:'COURIER'});
  let release;const pending=new Promise(resolve=>{release=resolve;});
  await page.route('**/api/v1/couriers/me/orders',async route=>{await pending;await route.fulfill({status,json:status===200?{items:[],nextCursor:null}:{error:{code:'DEPENDENCY_UNAVAILABLE',message:'Consulta anterior fallida'}}});});
  await page.clock.install();await page.goto('/#/repartidor');
  await page.getByRole('link',{name:'Compartir ubicación',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Compartir mi ubicación'})).toBeVisible();
  release();await page.clock.runFor(6500);
  await expect(page.getByRole('heading',{name:'Compartir mi ubicación'})).toBeVisible();
  expect(calls.filter(call=>call.path==='/couriers/me/active')).toHaveLength(1);
});
test('sesión en memoria permite navegar al mapa y cerrar GPS con almacenamiento bloqueado',async({page})=>{
  await fixture(page,{role:'COURIER',signedIn:false});
  await page.addInitScript(()=>{
    Storage.prototype.getItem=()=>{throw new Error('bloqueado');};Storage.prototype.setItem=()=>{throw new Error('bloqueado');};
    window.__started=0;window.__cleared=0;
    navigator.geolocation.watchPosition=()=>{window.__started++;return 7;};
    navigator.geolocation.clearWatch=()=>window.__cleared++;
  });
  await page.goto('/');await page.getByRole('combobox',{name:'Apariencia'}).selectOption('dark');
  await page.locator('[data-role="COURIER"]').click();
  await page.getByRole('textbox',{name:'Usuario',exact:true}).fill('courier1');
  await page.getByRole('button',{name:'Entrar',exact:true}).click();
  await page.getByRole('link',{name:'Compartir ubicación',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Compartir mi ubicación'})).toBeVisible();
  await page.getByLabel('Fuente').selectOption('BROWSER_GPS');
  await page.getByRole('checkbox').check();await page.getByRole('button',{name:'Activar GPS'}).click();
  expect(await page.evaluate(()=>window.__started)).toBe(1);
  await expect(page.locator('html')).toHaveAttribute('data-theme','dark');
  await page.getByRole('button',{name:'Cerrar sesión'}).click();
  await expect(page.getByRole('heading',{name:'Todo listo para tu próxima entrega.'})).toBeVisible();
  expect(await page.evaluate(()=>window.__cleared)).toBe(1);
});

test('nuevo pedido incluye puntos seleccionados sin inferirlos de la dirección',async({page})=>{
  await fixture(page,{role:'STORE'});
  let payload;
  await page.route('**/api/v1/orders',async route=>{
    payload=route.request().postDataJSON();
    return route.fulfill({status:201,json:{...orders[0],orderId:'o_new',trackingToken:'o_new.secret'}});
  });
  await page.goto('/#/comercio');
  await page.getByLabel('Recoger en',{exact:true}).fill('Dirección textual de recogida');
  await page.getByLabel('Entregar en',{exact:true}).fill('Dirección textual de entrega');
  await page.getByText('Seleccionar puntos en el mapa (opcional)',{exact:true}).click();
  await page.getByRole('button',{name:'Usar puntos de demo de Santa Marta'}).click();
  await page.getByRole('button',{name:'Publicar pedido',exact:true}).click();
  await expect.poll(()=>payload).toBeTruthy();
  expect(payload.pickupLocation).toEqual({latitude:11.237,longitude:-74.201});
  expect(payload.dropoffLocation).toEqual({latitude:11.235,longitude:-74.19});
  expect(payload.pickupAddress).toBe('Dirección textual de recogida');
});

test('selección incompleta de puntos se anuncia al publicar y no se descarta silenciosamente',async({page})=>{
  await fixture(page,{role:'STORE'});
  let payload;
  await page.route('**/api/v1/orders',async route=>{payload=route.request().postDataJSON();return route.fulfill({status:201,json:{...orders[0],trackingToken:'o_pending.secret'}});});
  await page.goto('/#/comercio');
  await page.getByLabel('Recoger en',{exact:true}).fill('Recogida textual');
  await page.getByLabel('Entregar en',{exact:true}).fill('Entrega textual');
  await page.getByText('Seleccionar puntos en el mapa (opcional)',{exact:true}).click();
  await expect(page.locator('#order-points-error')).toBeHidden();
  await page.getByLabel('Latitud de recogida',{exact:true}).fill('11.237');
  await expect(page.locator('#order-points-error')).toBeHidden();
  await page.getByRole('button',{name:'Publicar pedido',exact:true}).click();
  await expect(page.locator('#order-points-error')).toBeFocused();
  await expect(page.locator('#order-points-error')).toHaveText(/Completa las coordenadas de recogida y entrega/);
  expect(payload).toBeUndefined();
  await page.getByRole('button',{name:'Quitar puntos',exact:true}).click();
  await expect(page.locator('#order-points-error')).toBeHidden();
  await page.getByRole('button',{name:'Publicar pedido',exact:true}).click();
  await expect.poll(()=>payload).toBeTruthy();
  expect(payload.pickupLocation).toBeUndefined();expect(payload.dropoffLocation).toBeUndefined();
});

test('la guía de acceso explica sesiones y aprobación sin revelar código configurado',async({page})=>{
  await fixture(page,{signedIn:false});await page.goto('/');
  await page.getByText('Cómo probar la entrega completa',{exact:true}).click();
  await expect(page.getByText(/Dos pestañas del mismo perfil comparten el usuario/)).toBeVisible();
  await expect(page.getByText(/Para probar la aprobación usa usuarios nuevos/)).toBeVisible();
  await expect(page.getByText('admin-local',{exact:true})).toHaveCount(0);
});

for(const theme of ['light','dark'])test(`puntos numéricos accesibles y sin desbordes en móvil: ${theme}`,async({page})=>{
  await fixture(page,{role:'STORE',theme});await page.setViewportSize({width:360,height:900});
  await page.route('https://tile.openstreetmap.org/**',r=>r.abort());
  await page.goto('/#/comercio');
  await page.getByText('Seleccionar puntos en el mapa (opcional)',{exact:true}).click();
  await page.getByLabel('Latitud de recogida',{exact:true}).fill('91');
  await page.getByRole('button',{name:'Quitar puntos',exact:true}).click();
  await expect(page.getByLabel('Latitud de recogida',{exact:true})).toHaveAttribute('aria-invalid','false');
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
  expect((await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa','wcag22aa']).analyze()).violations).toEqual([]);
});

for(const role of ['STORE','COURIER'])test(`perfil suspendido ${role} se distingue de una solicitud pendiente`,async({page})=>{
  await fixture(page,{role,profile:'suspended'});await page.goto(role==='STORE'?'/#/comercio':'/#/repartidor');
  await expect(page.getByRole('heading',{name:'Tu perfil está suspendido'})).toBeVisible();
  await expect(page.getByText(/Contacta al administrador para revisar la decisión/)).toBeVisible();
  await expect(page.getByRole('heading',{name:'Tu registro está en revisión'})).toHaveCount(0);
});
