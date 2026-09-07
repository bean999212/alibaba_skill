#!/usr/bin/env node
/**
 * screenshot_report.js — 对 HTML 日报做全页高清截图
 *
 * Usage:
 *   node screenshot_report.js <input.html> <output.png> [--scale 3]
 *
 * 默认 deviceScaleFactor=3（聊天发图足够清晰，文件体积适中）。
 * 依赖：puppeteer-core（skill 目录已安装）、本地 Chrome。
 */

const path = require("path");
const fs = require("fs");

// ── 解析参数 ──────────────────────────────────────────
const args = process.argv.slice(2);
if (args.length < 2) {
  console.error("Usage: node screenshot_report.js <input.html> <output.png> [--scale N]");
  process.exit(1);
}

const inputHtml = path.resolve(args[0]);
const outputPng = path.resolve(args[1]);
const scaleIdx = args.indexOf("--scale");
const scale = scaleIdx !== -1 ? parseInt(args[scaleIdx + 1], 10) || 3 : 3;

if (!fs.existsSync(inputHtml)) {
  console.error(`Input HTML not found: ${inputHtml}`);
  process.exit(1);
}

// ── Chrome 路径 ────────────────────────────────────────
const CHROME_PATHS = [
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",       // macOS
  "/usr/bin/google-chrome",                                              // Linux
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",         // Windows
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
];

function findChrome() {
  for (const p of CHROME_PATHS) {
    if (fs.existsSync(p)) return p;
  }
  // fallback: 环境变量
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
    await page.waitForFunction(
      () => {
        const canvases = document.querySelectorAll("canvas");
        if (canvases.length === 0) return true;
        // Chart.js 渲染完后 canvas 会有实际像素内容
        return Array.from(canvases).every((c) => c.width > 0 && c.height > 0);
      },
      { timeout: 10000 }
    ).catch(() => {
      // 超时不阻塞，继续截图
    });

    // 额外等待 500ms 确保字体加载 & 布局稳定
    await new Promise((r) => setTimeout(r, 500));

    // 全页截图
    await page.screenshot({
      path: outputPng,
      fullPage: true,
      type: "png",
    });

    const stat = fs.statSync(outputPng);
    const sizeMB = (stat.size / 1024 / 1024).toFixed(2);
    console.log(
      JSON.stringify({
        success: true,
        output: outputPng,
        sizeBytes: stat.size,
        sizeMB: `${sizeMB} MB`,
        scale,
      })
    );
  } finally {
    await browser.close();
  }
})();
