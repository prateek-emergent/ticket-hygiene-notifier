// `yarn start` in the preview pod: serve the prebuilt dashboard UI on $PORT (default 3000), with the
// single-page-app fallback. /api is routed to the backend (port 8001) before it reaches this server.
const http = require("http");
const fs = require("fs");
const path = require("path");

const root = path.join(__dirname, "prebuilt");
const types = { ".html": "text/html; charset=utf-8", ".js": "text/javascript", ".css": "text/css",
  ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon", ".woff2": "font/woff2", ".json": "application/json" };

http.createServer((req, res) => {
  const urlPath = decodeURIComponent((req.url || "/").split("?")[0]);
  let file = path.normalize(path.join(root, urlPath));
  if (!file.startsWith(root) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    file = path.join(root, "index.html");
  }
  res.writeHead(200, { "Content-Type": types[path.extname(file)] || "application/octet-stream" });
  fs.createReadStream(file).pipe(res);
}).listen(Number(process.env.PORT) || 3000, "0.0.0.0", () => console.log("dashboard UI on port", Number(process.env.PORT) || 3000));
