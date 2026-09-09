#!/usr/bin/env node
/**
 * screenshot_report.js — HTML 日报截图工具
 *
 * 两种模式：
 *
 * 1. 全页截图（默认，用于聊天发图）：
 *    node screenshot_report.js <input.html> <output.png> [--scale 3]
 *
 * 2. 逐图表截图（用于钉钉文档插图）：
 *    node screenshot_report.js <input.html> <output-dir> --charts [--scale 4]
 *    对页面中每个 <canvas> 单独截图，输出 <canvasId>.png（如 moduleChart.png）。
 *
 * 默认 deviceScaleFactor：全页模式 3，--charts 模式 4。
 * 依赖：puppeteer-core（skill 目录已安装）、本地 Chrome。
 */

const path = require("path");
const fs = require("fs");

// ── 解析参数 ──────────────────────────────────────────
const args = process.argv.slice(2);
if (args.length < 2) {
  console.error(
    "Usage:\n" +
      "  Full page:  node screenshot_report.js <input.html> <output.png> [--scale 3]\n" +
      "  Per-chart:  node screenshot_report.js <input.html> <output-dir> --charts [--scale 4]"
  );
  process.exit(1);
}

const inputHtml = path.resolve(args[0]);
const outputPath = path.resolve(args[1]);
const chartsMode = args.includes("--charts");
const scaleIdx = args.indexOf("--scale");
const defaultScale = chartsMode ? 4 : 3;
const scale =
  scaleIdx !== -1 ? parseInt(args[scaleIdx + 1], 10) || defaultScale : defaultScale;

if (!fs.existsSync(inputHtml)) {
  console.error(`Input HTML not found: ${inputHtml}`);
  process.exit(1);
}

if (chartsMode && !fs.existsSync(outputPath)) {
  fs.mkdirSync(outputPath, { recursive: true });
}

// ── canvas ID → 输出文件名映射 ────────────────────────
const CANVAS_FILE_MAP = {
  moduleChart: "module-chart",
  developerChart: "developer-chart",
  trendChart: "trend-chart",
};

// ── Chrome 路径 ────────────────────────────────────────
const CHROME_PATHS = [
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", // macOS
  "/usr/bin/google-chrome", // Linux
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe", // Windows
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
];

function findChrome() {
  for (const p of CHROME_PATHS) {
    if (fs.existsSync(p)) return p;
  }
  if (process.env.CHROME_PATH && fs.existsSync(process.env.CHROME_PATH)) {
    return process.env.CHROME_PATH;
  }
  console.error("Chrome not found. Set CHROME_PATH env or install Chrome.");
  process.exit(1);
}

// ── 主流程 ─────────────────────────────────────────────
(async () => {
  const puppeteer = require(path.join(
    __dirname,
    "..",
    "node_modules",
    "puppeteer-core"
  ));

  const browser = await puppeteer.launch({
    executablePath: findChrome(),
    headless: "new",
    args: [
      "--no-sandbox",
      "--disable-setuid-sandbox",
      "--disable-gpu",
      "--disable-dev-shm-usage",
    ],
  });

  try {
    const page = await browser.newPage();

    // viewport 宽度 920px（略大于表格 max-width 892px），高度设大让内容撑开
    await page.setViewport({ width: 920, height: 2000, deviceScaleFactor: scale });

    // 加载 HTML 文件
    const htmlUrl = `file://${inputHtml}`;
    await page.goto(htmlUrl, { waitUntil: "networkidle0", timeout: 30000 });

    // 等待 Chart.js 动画渲染完成（如有图表）
    await page
      .waitForFunction(
        () => {
          const canvases = document.querySelectorAll("canvas");
          if (canvases.length === 0) return true;
          return Array.from(canvases).every(
            (c) => c.width > 0 && c.height > 0
          );
        },
        { timeout: 10000 }
      )
      .catch(() => {
        // 超时不阻塞，继续截图
      });

    // 额外等待 500ms 确保字体加载 & 布局稳定
    await new Promise((r) => setTimeout(r, 500));

    if (chartsMode) {
      // ── 逐图表截图模式 ──────────────────────────────
      // 获取页面中所有 canvas 元素的 id
      const canvasIds = await page.evaluate(() => {
        return Array.from(document.querySelectorAll("canvas")).map(
          (c) => c.id
        );
      });

      if (canvasIds.length === 0) {
        console.log(
          JSON.stringify({
            success: true,
            mode: "charts",
            charts: [],
            message: "No canvas elements found in the HTML.",
          })
        );
        return;
      }

      const results = [];
      for (const canvasId of canvasIds) {
        const fileName =
          (CANVAS_FILE_MAP[canvasId] || canvasId) + ".png";
        const filePath = path.join(outputPath, fileName);

        const element = await page.$(`#${canvasId}`);
        if (!element) {
          console.error(`Canvas #${canvasId} not found, skipping.`);
          continue;
        }

        await element.screenshot({ path: filePath, type: "png" });

        const stat = fs.statSync(filePath);
        results.push({
          canvasId,
          file: filePath,
          sizeBytes: stat.size,
        });
      }

      console.log(
        JSON.stringify({
          success: true,
          mode: "charts",
          scale,
          charts: results,
          totalCharts: results.length,
        })
      );
    } else {
      // ── 全页截图模式 ──────────────────────────────────
      await page.screenshot({
        path: outputPath,
        fullPage: true,
        type: "png",
      });

      const stat = fs.statSync(outputPath);
      const sizeMB = (stat.size / 1024 / 1024).toFixed(2);
      console.log(
        JSON.stringify({
          success: true,
          mode: "fullpage",
          output: outputPath,
          sizeBytes: stat.size,
          sizeMB: `${sizeMB} MB`,
          scale,
        })
      );
    }
  } finally {
    await browser.close();
  }
})();
