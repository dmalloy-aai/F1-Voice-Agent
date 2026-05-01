const fs = require("fs");
const path = require("path");

let KB_SECTIONS = null;

function loadKB() {
  if (KB_SECTIONS) return;
  const text = fs.readFileSync(path.join(process.cwd(), "knowledge-base.md"), "utf8");
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

module.exports = (req, res) => {
  const query = req.query?.query || "";
  if (!query) return res.json({ result: "No query provided." });
  try {
    res.json({ result: searchKB(query) });
  } catch (e) {
    res.status(500).json({ error: e.message });
  }
};
