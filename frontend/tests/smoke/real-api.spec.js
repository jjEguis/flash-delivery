import { test, expect } from "@playwright/test";
import { randomUUID } from "node:crypto";

test("frontend, proxy y API reales: health, zonas y login hasta formulario de alta", async ({ page }) => {
  const errors = [];
  page.on("pageerror", error => errors.push(error.message));
  const health = await page.request.get("/api/v1/health");
  expect(health.status()).toBe(200);
  const zones = await page.request.get("/api/v1/zones");
  expect(zones.status()).toBe(200);
  expect((await zones.json()).items.length).toBeGreaterThan(0);
  await page.goto("/");
  await page.locator('[data-role="COURIER"]').click();
  await page.getByLabel("Usuario", { exact: true }).fill("SPEC07_" + randomUUID().replaceAll("-", ""));
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Registra tu perfil de repartidor" })).toBeVisible();
  await expect(page.locator("#zone option")).not.toHaveCount(0);
  // No se envía el formulario: no se crean perfiles, pedidos ni asignaciones.
  expect(errors).toEqual([]);
});
