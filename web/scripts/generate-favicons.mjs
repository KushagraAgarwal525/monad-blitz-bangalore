import { readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import sharp from "sharp";
import pngToIco from "png-to-ico";

const __dirname = dirname(fileURLToPath(import.meta.url));
const appDir = join(__dirname, "..", "src", "app");
const svg = readFileSync(join(appDir, "icon.svg"));

const sizes = [16, 32, 48];
const pngBuffers = await Promise.all(
  sizes.map((size) => sharp(svg).resize(size, size).png().toBuffer())
);

writeFileSync(join(appDir, "favicon.ico"), await pngToIco(pngBuffers));
await sharp(svg).resize(180, 180).png().toFile(join(appDir, "apple-icon.png"));

console.log("Generated favicon.ico and apple-icon.png");
