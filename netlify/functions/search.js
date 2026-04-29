const fs = require("fs");
const path = require("path");

let KB_SECTIONS = null;

function loadKB() {
  if (KB_SECTIONS) return;

  // Netlify bundles included_files alongside the function in Lambda (/var/task)
  const candidates = [
    path.join(__dirname, "knowledge-base.md"),
    path.join("/var/task", "knowledge-base.md"),
    path.join(process.cwd(), "knowledge-base.md"),
  ];

  let text = null;
  for (const p of candidates) {
    try { text = fs.readFileSync(p, "utf8"); break; } catch (_) {}
  }

  if (!text) throw new Error("Knowledge base file not found.");
  KB_SECTIONS = parseSections(text);
}

function parseSections(text) {
  const sections = [];
  let curH = "", curL = [];
  for (const line of text.split("\n")) {
    if (line.startsWith("## ")) {
      if (curL.length) sections.push([curH, curL.join("\n")]);
      curH = line;
      curL = [line];
    } else {
      curL.push(line);
    }
  }
  if (curL.length) sections.push([curH, curL.join("\n")]);
  return sections;
}

const NUMERIC_KW = new Set([
  "number", "numbers", "how many", "how much", "percent", "%",
  "mw", "kw", "kg", "bar", "rpm", "second", "seconds",
  "stat", "stats", "figure", "figures", "data", "metric",
]);

function searchKB(query) {
  loadKB();
  const ql = query.toLowerCase();
  const qw = new Set(ql.match(/\w+/g) || []);

  let knSection = null;
  const scored = KB_SECTIONS.map(([h, body]) => {
    if (h.toLowerCase().includes("key numbers")) knSection = body;
    const score = [...qw].filter((w) => body.toLowerCase().includes(w)).length;
    return [score, body];
  });

  scored.sort((a, b) => b[0] - a[0]);
  const top3 = scored.slice(0, 3).filter(([s]) => s > 0).map(([, b]) => b);

  const isNumeric =
    [...qw].some((w) => NUMERIC_KW.has(w)) ||
    [...NUMERIC_KW].some((k) => ql.includes(k));

  if (isNumeric && knSection && !top3.includes(knSection)) top3.push(knSection);

  return top3.length ? top3.join("\n\n---\n\n") : "No relevant sections found.";
}

exports.handler = async (event) => {
  const query = event.queryStringParameters?.query || "";
  if (!query) {
    return {
      statusCode: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ result: "No query provided." }),
    };
  }
  try {
    return {
      statusCode: 200,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ result: searchKB(query) }),
    };
  } catch (e) {
    return {
      statusCode: 500,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ error: e.message }),
    };
  }
};
