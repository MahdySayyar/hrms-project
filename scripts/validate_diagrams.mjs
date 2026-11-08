// Parse project Mermaid sources without browser or UI automation.
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dependencyRoot = path.join(root, "artifacts", "diagram-validator", "node_modules");
const { JSDOM } = await import(pathToFileURL(path.join(dependencyRoot, "jsdom", "lib", "api.js")));
const dom = new JSDOM("<!doctype html><html><body></body></html>");
globalThis.window = dom.window;
globalThis.document = dom.window.document;
const { default: mermaid } = await import(pathToFileURL(path.join(dependencyRoot, "mermaid", "dist", "mermaid.esm.mjs")));
mermaid.initialize({ startOnLoad: false, securityLevel: "strict" });
async function files(directory, suffix) {
  const result = [];
  for (const item of await fs.readdir(directory, { withFileTypes: true })) {
    const current = path.join(directory, item.name);
    if (item.isDirectory()) result.push(...await files(current, suffix));
    else if (item.name.endsWith(suffix)) result.push(current);
  }
  return result;
}
const results = [];
for (const file of await files(path.join(root, "models"), ".mmd")) {
  try {
    await mermaid.parse(await fs.readFile(file, "utf8"));
    results.push({ path: path.relative(root, file).replaceAll("\\", "/"), passed: true });
  } catch (error) {
    results.push({ path: path.relative(root, file).replaceAll("\\", "/"), passed: false, error: String(error.message) });
  }
}
const backticks = String.fromCharCode(96).repeat(3);
for (const file of [path.join(root, "README.md"), ...await files(path.join(root, "docs"), ".md")]) {
  const content = await fs.readFile(file, "utf8");
  const pattern = new RegExp(backticks + "mermaid\\s*\\n([\\s\\S]*?)" + backticks, "g");
  let index = 0;
  for (const match of content.matchAll(pattern)) {
    index += 1;
    try {
      await mermaid.parse(match[1]);
      results.push({ path: path.relative(root, file).replaceAll("\\", "/") + ":diagram-" + index, passed: true });
    } catch (error) {
      results.push({ path: path.relative(root, file).replaceAll("\\", "/") + ":diagram-" + index, passed: false, error: String(error.message) });
    }
  }
}
const arg = process.argv.indexOf("--output");
if (arg >= 0) {
  const output = path.resolve(root, process.argv[arg + 1]);
  if (!output.startsWith(root + path.sep)) throw new Error("Output must remain in this project.");
  try { await fs.access(output); throw new Error("Evidence already exists; choose a new output."); }
  catch (error) { if (error.code !== "ENOENT") throw error; }
  await fs.mkdir(path.dirname(output), { recursive: true });
  await fs.writeFile(output, JSON.stringify({
    tool: "Mermaid syntax parser only; no visual rendering or browser interaction",
    recorded_at: new Date().toISOString(), all_passed: results.every(r => r.passed), checks: results,
  }, null, 2) + "\n", "utf8");
}
for (const result of results.filter(r => !r.passed)) console.log(JSON.stringify(result));
console.log("Parsed " + results.length + " Mermaid sources/embedded diagrams; failures=" + results.filter(r => !r.passed).length);
process.exitCode = results.every(r => r.passed) ? 0 : 1;
