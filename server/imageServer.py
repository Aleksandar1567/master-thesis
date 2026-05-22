from http.server import BaseHTTPRequestHandler, HTTPServer
import os
import struct
import json

UPLOAD_DIR = "images_train"
PORT = 8000

IMAGE_WIDTH = 256
IMAGE_HEIGHT = 288
IMAGE_DEPTH = 8


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
    """Convert 4-bit per pixel raw data to 8-bit grayscale BMP bytes"""
    bmp_bytes = assembleBMPHeader(width, height, 8, includePalette=True)
    
    total_pixels = width * height
    bmp_pixels = bytearray()
    
    for byteVal in raw_data:
        highPixel = (byteVal >> 4) & 0x0F
        lowPixel = byteVal & 0x0F
        bmp_pixels.append(highPixel * 17)
        bmp_pixels.append(lowPixel * 17)
    
    bmp_pixels = bmp_pixels[:total_pixels]  # trim to exact pixel count
    bmp_bytes += bmp_pixels
    return bmp_bytes


class FingerprintHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_type = self.headers.get('Content-Type')
        if content_type != 'application/octet-stream':
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'Content-Type not supported\n')
            return

        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)

        os.makedirs(UPLOAD_DIR, exist_ok=True)

        # Determine new file name based on existing files
        existing_files = [f for f in os.listdir(UPLOAD_DIR) if f.endswith(".bmp")]
        existing_indices = []

        for f in existing_files:
            try:
                idx = int(f.split('_')[1].split('.')[0])
                existing_indices.append(idx)
            except:
                pass

        existing_indices.sort()

        # Find the smallest missing index
        new_index = 0
        for idx in existing_indices:
            if idx == new_index:
                new_index += 1
            else:
                break  # found the gap

        bmp_file_path = os.path.join(UPLOAD_DIR, f'image_{new_index}.bmp')

        try:
            bmp_bytes = raw_to_bmp(post_data, IMAGE_WIDTH, IMAGE_HEIGHT)
            with open(bmp_file_path, 'wb') as f:
                f.write(bmp_bytes)
            print(f"[Saved BMP: {bmp_file_path}]")
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(f"Saved BMP: {bmp_file_path}".encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(f"Error: {str(e)}".encode('utf-8'))

    def do_GET(self):
        if self.path.startswith("/images/"):
            filename = os.path.basename(self.path)
            file_path = os.path.join(UPLOAD_DIR, filename)
            if os.path.isfile(file_path):
                self.send_response(200)
                self.send_header("Content-Type", "image/bmp")
                self.end_headers()
                with open(file_path, "rb") as f:
                    self.wfile.write(f.read())
            else:
                self.send_response(404)
                self.end_headers()
                self.wfile.write(b'File not found\n')
        elif self.path == "/images/list":
            files = os.listdir(UPLOAD_DIR)
            bmp_files = [f for f in files if f.endswith(".bmp")]
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(bmp_files).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'Not Found\n')


def run():
    server_address = ('', PORT)
    httpd = HTTPServer(server_address, FingerprintHandler)
    print(f"Serving on port {PORT}")
    httpd.serve_forever()


if __name__ == '__main__':
    run()
