import {test,expect} from '@playwright/test';
import {execFileSync} from 'node:child_process';
import {readFileSync,writeFileSync,mkdtempSync,rmdirSync,mkdirSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join,resolve} from 'node:path';

test('registro → aprobación administrativa → pedido → ambos recorridos → entrega por UI real',async({browser})=>{
  test.setTimeout(240000);
  const directory=mkdtempSync(join(tmpdir(),'flashdelivery-journey-')),fixture=join(directory,'fixture.json');
  const python=process.env.GEO_PYTHON || resolve('../.venv/bin/python');
  const run=operation=>execFileSync(python,['-m','scripts.geo_fixture',operation,fixture],{cwd:resolve('../app'),stdio:'pipe'});
  run('journey');
  const data=JSON.parse(readFileSync(fixture,'utf8')),contexts=[],captures=[];
  const persist=()=>writeFileSync(fixture,JSON.stringify(data),{mode:0o600});
  async function pageFor(actor) {
    const context=await browser.newContext();contexts.push(context);
    const page=await context.newPage();
    page.on('response',response=>{
      captures.push((async()=>{
        const request=response.request(),path=new URL(response.url()).pathname;
        if (request.method()!=='POST' || !response.ok()) return;
        const operation=path==='/api/v1/orders'?'orders.create.v1':path.match(/^\/api\/v1\/orders\/[^/]+\/(accept|pickup|deliver)$/)?.[1];
        if (!operation) return;
        const key=await request.headerValue('idempotency-key');
        if (key) data.created.requests.push([actor,operation==='orders.create.v1'?operation:`dispatch.${operation}.v1`,key]);
        if (operation==='orders.create.v1') {
          const order=await response.json();data.created.orders.push(order.orderId);
        }
        persist();
      })().catch(()=>{}));
    });
    return page;
  }
  async function login(page,role,user) {
    await page.goto('/');await page.locator(`[data-role="${role}"]`).click();
    await page.getByRole('textbox',{name:'Usuario',exact:true}).fill(user);
    if (role==='ADMIN') await page.getByLabel('Código de administrador',{exact:true}).fill(data.adminCode);
    await page.getByRole('button',{name:'Entrar',exact:true}).click();
  }
  async function register(page,name) {
    await page.getByLabel('Nombre',{exact:true}).fill(name);
    await page.getByLabel('Zona',{exact:true}).selectOption(data.zone);
    await page.getByRole('button',{name:'Registrar',exact:true}).click();
    await expect(page.getByRole('heading',{name:'Tu registro está en revisión'})).toBeVisible();
  }
  async function enable(admin,kind,id) {
    const form=admin.locator(`[data-enable="${kind}"]`);
    await form.getByLabel('Identificador',{exact:true}).fill(id);
    await form.getByRole('button',{name:'Habilitar',exact:true}).click();
    await expect(form.locator('[data-out]')).toContainText('habilitado');
  }
  try {
    const store=await pageFor(data.actors.STORE),courier=await pageFor(data.actors.COURIER),admin=await pageFor('admin');
    await login(store,'STORE',data.actors.STORE);await register(store,'Comercio de prueba guiada');
    await expect(store.getByLabel('Identificador para el administrador')).toHaveValue(data.actors.STORE);
    await login(courier,'COURIER',data.actors.COURIER);await register(courier,'Repartidor de prueba guiada');
    await expect(courier.getByLabel('Identificador para el administrador')).toHaveValue(data.actors.COURIER);
    await login(admin,'ADMIN','admin');
    await enable(admin,'store',data.actors.STORE);await enable(admin,'courier',data.actors.COURIER);
    await store.getByRole('button',{name:'Ya me habilitaron, actualizar'}).click();
    await expect(store.getByRole('heading',{name:'Tu operación, al día.'})).toBeVisible();
    await store.getByLabel('Recoger en',{exact:true}).fill('Recogida para prueba guiada');
    await store.getByLabel('Entregar en',{exact:true}).fill('Destino para prueba guiada');
    await store.getByText('Seleccionar puntos en el mapa (opcional)',{exact:true}).click();
    // Tramos cortos de Santa Marta para ejercitar ambas fases sin esperar varios minutos.
    for (const [label,value] of [['Latitud de recogida','11.2437'],['Longitud de recogida','-74.2105'],['Latitud de entrega','11.243'],['Longitud de entrega','-74.2095']]) await store.getByLabel(label,{exact:true}).fill(value);
    const created=store.waitForResponse(r=>new URL(r.url()).pathname==='/api/v1/orders' && r.request().method()==='POST' && r.status()===201);
    await store.getByRole('button',{name:'Publicar pedido',exact:true}).click();
    const order=await (await created).json();
    if (!data.created.orders.includes(order.orderId)) data.created.orders.push(order.orderId);persist();
    await courier.getByRole('button',{name:'Ya me habilitaron, actualizar'}).click();
    await expect(courier.getByRole('heading',{name:'Vamos con la próxima.'})).toBeVisible();
    await courier.getByRole('checkbox',{name:'Disponible',exact:true}).check();
    await courier.locator(`[data-accept="${order.orderId}"]`).click({timeout:15000});
    await courier.getByRole('link',{name:'Compartir ubicación',exact:true}).click();
    await expect(courier.getByRole('button',{name:'Iniciar simulación'})).toBeDisabled();
    await courier.getByRole('button',{name:'Usar inicio de demo en Santa Marta'}).click();
    await courier.getByLabel('Velocidad de demo (m/s)').fill('25');
    await courier.getByRole('checkbox').check();await courier.getByRole('button',{name:'Iniciar simulación'}).click();
    const recipient=await pageFor(null);await recipient.goto('/#/mapa/'+encodeURIComponent(order.trackingToken));
    await expect(recipient.getByText(/Modo simulación/)).toBeVisible({timeout:15000});
    await expect(courier.getByText(/Llegaste al punto de recogida/)).toBeVisible({timeout:90000});
    await expect(courier.locator('.geo-card-heading').getByText('Asignada',{exact:true})).toBeVisible();
    await courier.getByRole('button',{name:'Marcar recogido',exact:true}).click();
    await expect(courier.getByText('Pedido recogido. Inicia el recorrido a entrega desde tu última posición compartida.')).toBeVisible();
    await expect(courier.getByLabel('Velocidad de demo (m/s)')).toHaveValue('25');
    await expect(courier.getByRole('button',{name:'Usar inicio de demo en Santa Marta'})).toBeDisabled();
    await courier.getByRole('button',{name:'Iniciar simulación'}).click();
    await expect(courier.getByText(/Llegaste al punto de entrega/)).toBeVisible({timeout:90000});
    await expect(recipient.locator('.geo-card-heading').getByText('Recogida',{exact:true})).toBeVisible({timeout:10000});
    if (process.env.GEO_EVIDENCE_DIR) {
      mkdirSync(process.env.GEO_EVIDENCE_DIR,{recursive:true});
      await courier.setViewportSize({width:390,height:1000});
      await courier.evaluate(()=>document.activeElement?.blur());
      await courier.locator('.geo-next-step').scrollIntoViewIfNeeded();
      await courier.screenshot({path:join(process.env.GEO_EVIDENCE_DIR,'demo-repartidor-entrega-390.png')});
    }
    await courier.getByRole('button',{name:'Marcar entregado',exact:true}).click();
    await expect(courier.locator('.geo-card-heading').getByText('Entregada',{exact:true})).toBeVisible();
    await expect(recipient.locator('.geo-card-heading').getByText('Entregada',{exact:true})).toBeVisible({timeout:12000});
    await expect(recipient.getByText('Aún no hay ubicación compartida')).toBeVisible();
  } finally {
    await Promise.allSettled(contexts.map(context=>context.close()));
    await Promise.allSettled(captures);persist();run('cleanup');rmdirSync(directory);
  }
});
