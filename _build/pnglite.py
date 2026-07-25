"""Минимальный PNG reader/writer на stdlib: 8-бит RGB/RGBA, без интерлейса."""
import struct, zlib


def read(path):
    data = open(path, 'rb').read()
    assert data[:8] == b'\x89PNG\r\n\x1a\n', 'не PNG'
    pos, idat, w = 8, [], None
    while pos < len(data):
        ln, typ = struct.unpack('>I4s', data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + ln]
        pos += 12 + ln
        if typ == b'IHDR':
            w, h, depth, color, comp, filt, inter = struct.unpack('>IIBBBBB', body)
            assert depth == 8 and inter == 0 and color in (2, 6), (depth, color, inter)
            ch = 3 if color == 2 else 4
        elif typ == b'IDAT':
            idat.append(body)
        elif typ == b'IEND':
            break
    raw = zlib.decompress(b''.join(idat))
    stride = w * ch
    out = bytearray(h * stride)
    prev = bytearray(stride)
    p = 0
    for y in range(h):
        ft = raw[p]; p += 1
        line = bytearray(raw[p:p + stride]); p += stride
        if ft == 1:
            for i in range(ch, stride):
                line[i] = (line[i] + line[i - ch]) & 255
        elif ft == 2:
            for i in range(stride):
                line[i] = (line[i] + prev[i]) & 255
        elif ft == 3:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                line[i] = (line[i] + ((a + prev[i]) >> 1)) & 255
        elif ft == 4:
            for i in range(stride):
                a = line[i - ch] if i >= ch else 0
                c = prev[i - ch] if i >= ch else 0
                b = prev[i]
                pa, pb, pc = abs(b - c), abs(a - c), abs(a + b - 2 * c)
                pr = a if (pa <= pb and pa <= pc) else (b if pb <= pc else c)
                line[i] = (line[i] + pr) & 255
        out[y * stride:(y + 1) * stride] = line
        prev = line
    return {'w': w, 'h': h, 'ch': ch, 'px': out}


def write(path, img):
    w, h, ch, px = img['w'], img['h'], img['ch'], img['px']
    stride = w * ch
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        raw += px[y * stride:(y + 1) * stride]
    color = 2 if ch == 3 else 6

    def chunk(typ, body):
        return struct.pack('>I', len(body)) + typ + body + struct.pack('>I', zlib.crc32(typ + body) & 0xffffffff)

    out = b'\x89PNG\r\n\x1a\n'
    out += chunk(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, color, 0, 0, 0))
    out += chunk(b'IDAT', zlib.compress(bytes(raw), 9))
    out += chunk(b'IEND', b'')
    open(path, 'wb').write(out)


def crop(img, x, y, w, h):
    ch, sw = img['ch'], img['w'] * img['ch']
    px = img['px']
    out = bytearray()
    for row in range(y, y + h):
        s = row * sw + x * ch
        out += px[s:s + w * ch]
    return {'w': w, 'h': h, 'ch': ch, 'px': out}


def to_rgba(img):
    if img['ch'] == 4:
        return img
    px, out = img['px'], bytearray()
    for i in range(0, len(px), 3):
        out += px[i:i + 3] + b'\xff'
    return {'w': img['w'], 'h': img['h'], 'ch': 4, 'px': out}


def pixel(img, x, y):
    ch = img['ch']
    i = (y * img['w'] + x) * ch
    return tuple(img['px'][i:i + ch])


def resize(img, tw, th):
    """Уменьшение усреднением по блоку — на прозрачности считаем premultiplied."""
    w, h, ch, px = img['w'], img['h'], img['ch'], img['px']
    out = bytearray(tw * th * ch)
    for ty in range(th):
        y0, y1 = ty * h // th, max(ty * h // th + 1, (ty + 1) * h // th)
        for tx in range(tw):
            x0, x1 = tx * w // tw, max(tx * w // tw + 1, (tx + 1) * w // tw)
            acc = [0.0] * ch
            alpha = 0.0
            n = 0
            for y in range(y0, y1):
                base = y * w * ch
                for x in range(x0, x1):
                    i = base + x * ch
                    a = px[i + 3] / 255 if ch == 4 else 1.0
                    for c in range(3):
                        acc[c] += px[i + c] * a
                    alpha += a
                    n += 1
            d = (ty * tw + tx) * ch
            if alpha > 0:
                for c in range(3):
                    out[d + c] = min(255, round(acc[c] / alpha))
            if ch == 4:
                out[d + 3] = round(alpha / n * 255)
    return {'w': tw, 'h': th, 'ch': ch, 'px': out}
