const https = require("https");

const ALLOWED_HOSTS = [
  "pit-lane-pete.vercel.app",
  "www.assemblyai.com",
  "localhost",
  "127.0.0.1",
];

module.exports = (req, res) => {
  // Block requests not originating from an allowed host
  const origin = req.headers.origin || req.headers.referer || "";
  if (!ALLOWED_HOSTS.some((host) => origin.includes(host))) {
    return res.status(403).json({ error: "Forbidden" });
  }

  const apiKey = process.env.ASSEMBLYAI_API_KEY;
  if (!apiKey) {
    return res.status(401).json({ error: "ASSEMBLYAI_API_KEY not configured on server." });
  }

  const options = {
    hostname: "agents.assemblyai.com",
    path: "/v1/token?expires_in_seconds=300&max_session_duration_seconds=3600",
    method: "GET",
    headers: { Authorization: `Bearer ${apiKey}` },
  };

  const req2 = https.request(options, (r) => {
    let data = "";
    r.on("data", (chunk) => (data += chunk));
    r.on("end", () => {
      res.status(r.statusCode).setHeader("Content-Type", "application/json").end(data);
    });
  });

  req2.on("error", (e) => res.status(500).json({ error: e.message }));
  req2.end();
};
