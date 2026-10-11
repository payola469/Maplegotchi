// Offline RGBA8 PNG codec. Stored DEFLATE blocks deliberately avoid encoder-version drift.
import { inflateSync } from 'node:zlib';
export function crc32(data) {
  let n = 0xffffffff;
  for (const b of data) { n ^= b; for (let i = 0; i < 8; i++) n = (n >>> 1) ^ ((n & 1) ? 0xedb88320 : 0); }
  return (n ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const t = Buffer.from(type), out = Buffer.alloc(data.length + 12);
  out.writeUInt32BE(data.length); t.copy(out, 4); data.copy(out, 8);
  out.writeUInt32BE(crc32(Buffer.concat([t, data])), out.length - 4); return out;
}
export function encodePNG({ width, height, pixels }) {
  const raw = Buffer.alloc(height * (width * 4 + 1));
  for (let y = 0; y < height; y++) Buffer.from(pixels).copy(raw, y * (width * 4 + 1) + 1, y * width * 4, (y + 1) * width * 4);
  const blocks = [Buffer.from([0x78, 0x01])];
  for (let i = 0; i < raw.length; i += 65535) {
    const data = raw.subarray(i, i + 65535), h = Buffer.alloc(5);
    h[0] = i + data.length === raw.length ? 1 : 0; h.writeUInt16LE(data.length, 1); h.writeUInt16LE(65535 - data.length, 3); blocks.push(h, data);
  }
  let a = 1, b = 0; for (const v of raw) { a = (a + v) % 65521; b = (b + a) % 65521; }
  const adler = Buffer.alloc(4); adler.writeUInt32BE((b * 65536 + a) >>> 0); blocks.push(adler);
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(width); ihdr.writeUInt32BE(height, 4); ihdr[8] = 8; ihdr[9] = 6;
  return Buffer.concat([Buffer.from('89504e470d0a1a0a', 'hex'), chunk('IHDR', ihdr), chunk('IDAT', Buffer.concat(blocks)), chunk('IEND', Buffer.alloc(0))]);
}
export function decodePNG(bytes) {
  const fail = (m) => { throw new Error(`E2: ${m}`); };
  if (!bytes.subarray(0, 8).equals(Buffer.from('89504e470d0a1a0a', 'hex'))) fail('expected PNG, not a pointer or foreign file');
  let pos = 8, width = 0, height = 0, ended = false, idatEnded = false; const data = [];
  while (pos < bytes.length) {
    if (pos + 12 > bytes.length) fail('truncated chunk');
    const len = bytes.readUInt32BE(pos), type = bytes.toString('ascii', pos + 4, pos + 8), end = pos + 12 + len;
    if (end > bytes.length || crc32(bytes.subarray(pos + 4, end - 4)) !== bytes.readUInt32BE(end - 4)) fail('chunk length/CRC');
    const value = bytes.subarray(pos + 8, end - 4);
    if (type === 'IHDR') {
      if (pos !== 8 || len !== 13) fail('IHDR order/size');
      width = value.readUInt32BE(); height = value.readUInt32BE(4);
      if (!width || !height || width > 2048 || height > 2048) throw new Error('E18: file dimensions exceed 2048');
      if (!value.subarray(8).equals(Buffer.from([8, 6, 0, 0, 0]))) fail('require RGBA8, non-interlaced');
    } else if (type === 'IDAT') { if (!width || idatEnded) fail('IDAT order'); data.push(value); }
    else if (type === 'IEND') { if (len || !data.length || end !== bytes.length) fail('IEND/trailing data'); ended = true; }
    else fail(`forbidden PNG chunk ${type}`);
    if (data.length && type !== 'IDAT') idatEnded = true;
    pos = end;
  }
  if (!ended) fail('missing IEND');
  const stride = width * 4, size = height * (stride + 1);
  let raw; try { raw = inflateSync(Buffer.concat(data), { maxOutputLength: size }); } catch { fail('invalid compressed data'); }
  if (raw.length !== size) fail('pixel byte count');
  const pixels = Buffer.alloc(width * height * 4);
  for (let y = 0; y < height; y++) {
    const f = raw[y * (stride + 1)]; if (f > 4) fail('invalid filter');
    for (let x = 0; x < stride; x++) {
      const i = y * stride + x, a = x >= 4 ? pixels[i - 4] : 0, b = y ? pixels[i - stride] : 0, c = y && x >= 4 ? pixels[i - stride - 4] : 0;
      const p = a + b - c, pa = Math.abs(p - a), pb = Math.abs(p - b), pc = Math.abs(p - c);
      const predictor = [0, a, b, Math.floor((a + b) / 2), pa <= pb && pa <= pc ? a : pb <= pc ? b : c][f];
      pixels[i] = (raw[y * (stride + 1) + x + 1] + predictor) & 255;
    }
  }
  return { width, height, pixels };
}
export function crop(image, x, y, width, height) {
  const pixels = Buffer.alloc(width * height * 4);
  for (let row = 0; row < height; row++) image.pixels.copy(pixels, row * width * 4, ((y + row) * image.width + x) * 4, ((y + row) * image.width + x + width) * 4);
  return { width, height, pixels };
}
