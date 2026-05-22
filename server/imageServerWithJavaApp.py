from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import struct
import json
import requests
import base64
import numpy as np
import csv
from datetime import datetime

#UPLOAD_DIR = "images"
TEMPLATE_DIR = "templates"
LOG_FILE = "fingerprint_log.csv"
PORT = 8000

IMAGE_WIDTH = 256
IMAGE_HEIGHT = 288
IMAGE_DEPTH = 8


# === BMP Konverzija ===
def assembleBMPHeader(width, height, depth, includePalette=True):
    bmpHeader = struct.Struct("<2s3L LLl2H6L")
    bmpPaletteEntry = struct.Struct("4B")

    byteWidth = ((depth * width + 31) // 32) * 4
    numColours = 2**depth
    bmpPaletteSize = bmpPaletteEntry.size * numColours
    imageSize = byteWidth * height

    if includePalette:
        fileSize = bmpHeader.size + bmpPaletteSize + imageSize
        rasterOffset = bmpHeader.size + bmpPaletteSize
    else:
        fileSize = bmpHeader.size + imageSize
        rasterOffset = bmpHeader.size

    BMP_INFOHEADER_SZ = 40
    TYPICAL_PIXELS_PER_METER = 2835

    bmpHeaderBytes = bmpHeader.pack(
        b"BM", fileSize, 0, rasterOffset, BMP_INFOHEADER_SZ,
        width, -height, 1, depth, 0, imageSize,
        TYPICAL_PIXELS_PER_METER, TYPICAL_PIXELS_PER_METER, 0, 0
    )

    if includePalette:
        bmpPaletteBytes = b''.join([bmpPaletteEntry.pack(i, i, i, i) for i in range(numColours)])
        return bmpHeaderBytes + bmpPaletteBytes
    return bmpHeaderBytes


def raw_to_bmp(raw_data, width, height):
    bmp_bytes = assembleBMPHeader(width, height, 8, includePalette=True)

    total_pixels = width * height
    bmp_pixels = bytearray()

    for byteVal in raw_data:
        highPixel = (byteVal >> 4) & 0x0F
        lowPixel = byteVal & 0x0F
        bmp_pixels.append(highPixel * 17)
        bmp_pixels.append(lowPixel * 17)

    bmp_pixels = bmp_pixels[:total_pixels]
    bmp_bytes += bmp_pixels

    return bmp_bytes, np.array(bmp_pixels, dtype=np.uint8)


# === REST API za Java matcher ===
def create_template_from_bmp(bmp_bytes):
    resp = requests.post(
        "http://localhost:8080/fingerprint/template",
        data=bmp_bytes,
        headers={"Content-Type": "application/octet-stream"}
    )
    resp.raise_for_status()
    return resp.content


def compare_templates(t1, t2):
    resp = requests.post(
        "http://localhost:8080/fingerprint/match",
        json={
            "probe": base64.b64encode(t1).decode(),
            "candidate": base64.b64encode(t2).decode()
        }
    )
    resp.raise_for_status()
    return resp.json()


# === Log u CSV sa IP adresom ===
def log_result(timestamp, variance, template_file, score, match, client_ip):
    """
    Loguje svaki otisak u CSV fajl sa informacijom o IP adresi klijenta.
    """
    file_exists = os.path.isfile(LOG_FILE)
    with open(LOG_FILE, mode="a", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        if not file_exists:
            writer.writerow(["timestamp", "variance", "template_file", "score", "match", "client_ip"])
        writer.writerow([timestamp, variance, template_file, score, match, client_ip])


# === HTTP Handler ===
class FingerprintHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        client_ip = self.client_address[0]  # IP klijenta koji šalje otisak
        #print(f"Request from IP: {client_ip}")
        content_type = self.headers.get('Content-Type')
        if content_type != 'application/octet-stream':
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Content-Type not supported\n')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        # os.makedirs(UPLOAD_DIR, exist_ok=True)
        os.makedirs(TEMPLATE_DIR, exist_ok=True)

        # Pretvori u BMP + numpy
        bmp_bytes, bmp_pixels = raw_to_bmp(post_data, IMAGE_WIDTH, IMAGE_HEIGHT)

        # Varijansa
        variance = float(np.var(bmp_pixels))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        print(f"\n=== Novi otisak primljen ===")
        print(f"Vreme: {timestamp}")
        print(f"Varijansa: {variance:.2f}")

        # Template
        try:
            new_template = create_template_from_bmp(bmp_bytes)
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error generating template: {str(e)}".encode('utf-8'))
            return

        # Poredi sa postojećim
        duplicate_found = False
        best_score = -1
        best_match = None
        best_template = None

        for fname in os.listdir(TEMPLATE_DIR):
            if not fname.endswith(".dat"):
                continue
            with open(os.path.join(TEMPLATE_DIR, fname), "rb") as f:
                existing_template = f.read()
            result = compare_templates(new_template, existing_template)
            score = result.get("score", -1)
            match = result.get("match")

            print(f" → Poređenje sa {fname}: score={score:.2f}, match={match}")

            if score > best_score:
                best_score = score
                best_match = match
                best_template = fname

            if match:
                duplicate_found = True
                break

        if duplicate_found:
            print(f"[Rezultat] DUPLIKAT (score={best_score:.2f}, varijansa={variance:.2f})")
            #log_result(timestamp, variance, "duplicate", best_score, best_match)
            log_result(timestamp, variance, "duplicate", best_score, best_match, client_ip)

            self.send_response(200)
            self.end_headers()
            #self.wfile.write(
            #    f"Duplicate fingerprint - not saved. Var={variance:.2f}, BestScore={best_score:.2f}".encode('utf-8')
            #)
            self.wfile.write(f"Person has already voted".encode('utf-8'))
        else:
            # Sačuvaj BMP
            #bmp_index = len([f for f in os.listdir(UPLOAD_DIR) if f.endswith(".bmp")])
            #bmp_file_path = os.path.join(UPLOAD_DIR, f"finger_{bmp_index}.bmp")
            #with open(bmp_file_path, "wb") as f:
            #    f.write(bmp_bytes)

            # Sačuvaj template
            tmpl_index = len([f for f in os.listdir(TEMPLATE_DIR) if f.endswith(".dat")])
            tmpl_file_path = os.path.join(TEMPLATE_DIR, f"template_{tmpl_index}.dat")
            with open(tmpl_file_path, "wb") as f:
                f.write(new_template)

            print(f"[Rezultat] NOVI OTISAK (sačuvan kao {tmpl_file_path}, varijansa={variance:.2f})")
            #log_result(timestamp, variance, tmpl_file_path, best_score, best_match)
            log_result(timestamp, variance, tmpl_file_path, best_score, best_match, client_ip)
            self.send_response(200)
            self.end_headers()
            #self.wfile.write(
            #    f"New fingerprint saved. Var={variance:.2f}".encode('utf-8')
            #)
            self.wfile.write(f"New person voted".encode('utf-8'))


    #def do_GET(self):
    #   if self.path.startswith("/images/"):
    #        filename = os.path.basename(self.path)
    #        file_path = os.path.join(UPLOAD_DIR, filename)
    #        if os.path.isfile(file_path):
    #            self.send_response(200)
    #            self.send_header("Content-Type", "image/bmp")
    #            self.end_headers()
    #            with open(file_path, "rb") as f:
    #                self.wfile.write(f.read())
    #        else:
    #            self.send_response(404)
    #            self.end_headers()
    #            self.wfile.write(b'File not found\n')
    #    elif self.path == "/images/list":
    #        files = os.listdir(UPLOAD_DIR)
    #        bmp_files = [f for f in files if f.endswith(".bmp")]
    #        self.send_response(200)
    #        self.send_header("Content-Type", "application/json")
    #        self.end_headers()
    #        self.wfile.write(json.dumps(bmp_files).encode('utf-8'))
    #    else:
    #        self.send_response(404)
    #        self.end_headers()
    #        self.wfile.write(b'Not Found\n')


# === Start servera ===
def run():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, FingerprintHandler)
    print(f"Serving on port {PORT}")
    httpd.serve_forever()


if __name__ == '__main__':
    run()
