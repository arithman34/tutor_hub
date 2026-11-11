// Copies browser JS from node_modules into static/vendor/ so Django serves
// pinned, self-hosted copies instead of loading them from a CDN.
//
// Each file's source map comes too: the minified files end with a
// sourceMappingURL comment, and WhiteNoise's manifest storage fails
// collectstatic if that referenced file is missing.
import { copyFileSync, mkdirSync } from "node:fs";
import { basename } from "node:path";

const files = [
  "node_modules/flowbite/dist/flowbite.min.js",
  "node_modules/chart.js/dist/chart.umd.min.js",
];

mkdirSync("static/vendor", { recursive: true });
for (const file of files) {
  for (const from of [file, `${file}.map`]) {
    const to = `static/vendor/${basename(from)}`;
    copyFileSync(from, to);
    console.log(`${from} -> ${to}`);
  }
}
