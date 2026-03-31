import fs from "node:fs";
import path from "node:path";

import { expect, test, type Page } from "@playwright/test";

const EMS_PROJECT = process.env.DEMO_EMS_PROJECT || "demo-ems-fotovoltaica";
const WEATHER_PROJECT =
  process.env.DEMO_WEATHER_PROJECT || "demo-monitorizacion-estaciones-meteorologicas";
const SCADA_PROJECT =
  process.env.DEMO_SCADA_PROJECT || "demo-scada-hibrido-solar-bess";
const PPC_PROJECT =
  process.env.DEMO_PPC_PROJECT || "demo-calidad-de-red-y-ppc";
const PREDICTIVE_PROJECT =
  process.env.DEMO_PREDICTIVE_PROJECT || "demo-mantenimiento-predictivo-inversores";
const OT_PROJECT =
  process.env.DEMO_OT_PROJECT || "demo-observabilidad-subestaciones-y-ot";

function artifactPath(fileName: string): string {
  const outputDir = path.join(process.cwd(), "test-results", "screenshots");
  fs.mkdirSync(outputDir, { recursive: true });
  return path.join(outputDir, fileName);
}

async function waitForSubgraph(page: Page, action: () => Promise<unknown>) {
  const responsePromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/graph/subgraph") &&
      response.request().method() === "POST" &&
      response.ok(),
  );
  await action();
  await responsePromise;
  await page.waitForTimeout(700);
}

async function openBrain(page: Page) {
  const facetsPromise = page.waitForResponse(
    (response) => response.url().includes("/api/graph/facets") && response.ok(),
  );
  const subgraphPromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/graph/subgraph") &&
      response.request().method() === "POST" &&
      response.ok(),
  );
  await page.goto("/");
  await facetsPromise;
  await subgraphPromise;
  await expect(page.getByText("Cerebro navegable")).toBeVisible();
  await expect(page.locator(".brain-canvas")).toBeVisible();
}

async function configureWorkspace(
  page: Page,
  options: {
    project: string;
    scope: "project" | "bridged" | "global";
    nodes?: string;
    edges?: string;
  },
) {
  const dock = page.locator(".brain-dock");
  const fields = dock.locator(".dock-grid > .brain-field");

  await fields.nth(0).locator("select").selectOption(options.project);
  await fields.nth(2).locator("select").selectOption(options.scope);
  if (options.nodes) {
    await fields.nth(7).locator("input").fill(options.nodes);
  }
  if (options.edges) {
    await fields.nth(8).locator("input").fill(options.edges);
  }
  await waitForSubgraph(page, async () => {
    await dock.getByRole("button", { name: /Actualizar ahora/i }).click();
  });
}

test("captura una vista global del cerebro demo", async ({ page }) => {
  await openBrain(page);
  await configureWorkspace(page, {
    project: EMS_PROJECT,
    scope: "global",
    nodes: "80",
    edges: "200",
  });

  const projectsCluster = page.locator(".dock-clusters").getByText("Proyectos vivos").locator("..");
  await expect(projectsCluster.getByRole("button", { name: EMS_PROJECT })).toBeVisible();
  await expect(projectsCluster.getByRole("button", { name: WEATHER_PROJECT })).toBeVisible();
  await expect(projectsCluster.getByRole("button", { name: SCADA_PROJECT })).toBeVisible();
  await expect(projectsCluster.getByRole("button", { name: PPC_PROJECT })).toBeVisible();
  await expect(projectsCluster.getByRole("button", { name: PREDICTIVE_PROJECT })).toBeVisible();
  await expect(projectsCluster.getByRole("button", { name: OT_PROJECT })).toBeVisible();

  await page.screenshot({ path: artifactPath("brain-overview.png"), fullPage: true });
});

test("filtra el cerebro al proyecto EMS fotovoltaico", async ({ page }) => {
  await openBrain(page);
  await configureWorkspace(page, {
    project: EMS_PROJECT,
    scope: "project",
    nodes: "24",
    edges: "72",
  });

  await expect(page.locator(".brain-regions .brain-region__label")).toHaveCount(1);
  await expect(page.locator(".brain-regions .brain-region__label").first()).toContainText(EMS_PROJECT);

  await page.screenshot({ path: artifactPath("brain-ems-filtered.png"), fullPage: true });
});

test("pone en foco una metodología compartida y abre su detalle", async ({ page }) => {
  await openBrain(page);
  await configureWorkspace(page, {
    project: EMS_PROJECT,
    scope: "bridged",
    nodes: "48",
    edges: "120",
  });

  const methodologyCard = page
    .locator(".memory-card")
    .filter({ hasText: EMS_PROJECT })
    .filter({ hasText: "Metodología común" })
    .first();

  await expect(methodologyCard).toBeVisible();
  await methodologyCard.click();

  const drawer = page.locator(".brain-drawer");
  await expect(drawer).toBeVisible();
  await expect(drawer).toContainText(EMS_PROJECT);
  await expect(drawer).toContainText(/Metodología común de monitorización/i);
  await expect(drawer).toContainText(WEATHER_PROJECT);

  await page.screenshot({ path: artifactPath("brain-shared-methodology-focus.png"), fullPage: true });
});

test("salta desde el drawer a una conexión relacionada", async ({ page }) => {
  await openBrain(page);
  await configureWorkspace(page, {
    project: EMS_PROJECT,
    scope: "bridged",
    nodes: "48",
    edges: "120",
  });

  const methodologyCard = page
    .locator(".memory-card")
    .filter({ hasText: EMS_PROJECT })
    .filter({ hasText: "Metodología común" })
    .first();
  await methodologyCard.click();

  const drawer = page.locator(".brain-drawer");
  await expect(drawer).toBeVisible();
  const currentProjectPill = drawer.locator(".drawer-pill").first();
  await expect(currentProjectPill).toContainText(EMS_PROJECT);

  const relationRow = drawer.locator(".relation-row").first();
  await expect(relationRow).toBeVisible();

  const subgraphPromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/graph/subgraph") &&
      response.request().method() === "POST" &&
      response.ok(),
  );
  const detailPromise = page.waitForResponse(
    (response) =>
      response.url().includes("/api/memories/") &&
      response.request().method() === "GET" &&
      response.ok(),
  );
  await relationRow.click();
  await subgraphPromise;
  await detailPromise;
  await page.waitForTimeout(700);

  await expect(drawer.locator(".drawer-pill").first()).not.toContainText(EMS_PROJECT);
  await page.screenshot({ path: artifactPath("brain-neuron-drawer.png"), fullPage: true });
});
