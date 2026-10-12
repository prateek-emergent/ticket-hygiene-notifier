// The dashboard UI is built from dashboard/web (Vite) into dashboard/static, then mirrored into
// frontend/prebuilt by `npm run build` there. On the platform only frontend/ is available, so the
// "build" here just copies prebuilt/ to build/, which nginx serves.
const fs = require("fs");
const path = require("path");

const src = path.join(__dirname, "prebuilt");
const out = path.join(__dirname, "build");
if (!fs.existsSync(path.join(src, "index.html"))) {
  console.error("frontend/prebuilt/index.html is missing: run `npm run build` in dashboard/web first");
  process.exit(1);
}
fs.rmSync(out, { recursive: true, force: true });
fs.cpSync(src, out, { recursive: true });
console.log("copied the prebuilt dashboard UI to frontend/build");
