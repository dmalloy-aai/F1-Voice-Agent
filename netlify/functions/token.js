const https = require("https");

exports.handler = async () => {
  const apiKey = process.env.ASSEMBLYAI_API_KEY;
  if (!apiKey) {
    return {
      statusCode: 401,
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ error: "ASSEMBLYAI_API_KEY not configured on server." }),
    };
  }

  return new Promise((resolve) => {
    const path =
      "/v1/token?expires_in_seconds=300&max_session_duration_seconds=3600";
    const options = {
      hostname: "agents.assemblyai.com",
      path,
      method: "GET",
      headers: { Authorization: `Bearer ${apiKey}` },
    };

    const req = https.request(options, (res) => {
      let data = "";
      res.on("data", (chunk) => (data += chunk));
      res.on("end", () => {
        resolve({
          statusCode: res.statusCode,
          headers: { "Content-Type": "application/json" },
          body: data,
        });
      });
    });

    req.on("error", (e) => {
      resolve({
        statusCode: 500,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ error: e.message }),
      });
    });

    req.end();
  });
};
