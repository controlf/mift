"""
    (c) Yogesh Khatri 2020, MIT License - modifications made: Mike Bangham 2021
    This library converts ios created KTX files to PNG. These are 
    textures in KTX format, with raw texture  data in compressed ATSC
    format using a block size of 4x4, which is further compressed with
    LZFSE compression.
    iOS created KTX files use Adaptive Scalable Texture Compression 
    (ASTC) as the compressed texture format. Note that a KTX file
    can contain other formats too like PVR and several other 
    variations of ASTC which can't be read by this code. Here we
    only focus on ASTC 4x4, which is the default on iOS. Some apps 
    ship with KTX files that are not of the same type and can't be
    parsed with this code.
    Dependencies
    ------------
    pillow, pyliblzfse, astc_decomp
    Install deps via pip:
      pip3 install pyliblzfse astc_decomp pillow
    Usage
    -----
    python3 ios_ktx2png.py SAMPLE.KTX
    Output will be in the same folder, called SAMPLE.KTX.png
    See main 
"""

import astc_decomp 
import liblzfse
import os
import struct
import sys
import logging

from PIL import Image

version = 1.0


class KTXReader:
    def __init__(self):
        # KTX header fields
        self.identifier = b''  # b"«KTX 11»\r\n\x1A\x0A"
        self.endianness = ''
        self.glType = 0
        self.glTypeSize = 0
        self.glFormat = 0
        self.glInternalFormat = 0
        self.glBaseInternalFormat = 0
        self.pixelWidth = 0
        self.pixelHeight = 0
        self.pixelDepth = 0
        self.numberOfArrayElements = 0
        self.numberOfFaces = 0
        self.numberOfMipmapLevels = 0
        self.bytesOfKeyValueData = 0
        self.is_aapl_file = False
        self.aapl_data_pos = 0
        self.aapl_data_size = 0
        self.aapl_is_compressed = False

    def validate_header(self, f):
        f.seek(0)
        header = f.read(0x40)
        if len(header) < 0x40:
            logging.error("{} - File too small or can't read".format(f))
            return False

        self.identifier = header[0:12]
        self.endianness = header[12:16]
        if self.endianness == bytes.fromhex('01020304'):
            endianness = '<'
        else:
            endianness = '>'
        if self.identifier[0:7] == b'\xabKTX 11':
            self.glType,\
            self.glTypeSize, \
            self.glFormat, \
            self.glInternalFormat, \
            self.glBaseInternalFormat, \
            self.pixelWidth, \
            self.pixelHeight, \
            self.pixelDepth, \
            self.numberOfArrayElements, \
            self.numberOfFaces, \
            self.numberOfMipmapLevels, \
            self.bytesOfKeyValueData = \
                struct.unpack(endianness + '12I', header[16:64])
            return True
        elif self.identifier[0:4] == b'\xabKTX':  # different version
            logging.error("{} - Unknown KTX version".format(f))
        elif self.identifier[0:8] == b'AAPL\x0D\x0A\x1A\x0A':  # Not KTX, but similar!!
            self.is_aapl_file = True
            return self.parse_aapl_file(f)
        else:
            logging.error("{} - Not a KTX file".format(f))
        return False

    def parse_aapl_file(self, f):
        ret = False
        next_header_pos = 8
        f.seek(next_header_pos)
        data = f.read(8)
        while data:
            item_size = struct.unpack('<I', data[0:4])[0]
            item_identifier = data[4:8]
            if item_identifier == b'HEAD':
                item_data = f.read(item_size)
                # read metadata here...
                _, _, _, _, \
                self.glInternalFormat, \
                self.glBaseInternalFormat, \
                self.pixelWidth, \
                self.pixelHeight, \
                self.pixelDepth, \
                self.numberOfArrayElements, \
                self.numberOfFaces = \
                    struct.unpack('<11I', item_data[0:44])
                ret = True
            elif item_identifier == b'LZFS':
                self.aapl_data_pos = f.tell() + 4
                self.aapl_data_size = item_size - 4
                self.aapl_is_compressed = True
            elif item_identifier == b'astc':
                self.aapl_data_pos = f.tell() + 4
                self.aapl_data_size = item_size - 4
            next_header_pos += 8 + item_size
            f.seek(next_header_pos)
            data = f.read(8)
        return ret

    def get_uncompressed_texture_data(self, f):
        if self.glInternalFormat == 0x93B0:
            if self.is_aapl_file:
                f.seek(self.aapl_data_pos)
                data = f.read(self.aapl_data_size)
                if self.aapl_is_compressed:
                    decompressed = liblzfse.decompress(data)
                    return decompressed
                else:
                    return data
            else:
                f.seek(0x40)
                k_v_data = f.read(self.bytesOfKeyValueData)
                compressed = True if k_v_data.find(b'Compression_APPLE') >= 0 else False
                f.seek(0x40 + self.bytesOfKeyValueData)
                data = f.read()
                if compressed:
                    if data[12:15] == b'bvx':
                        decompressed = liblzfse.decompress(data[12:])
                        return decompressed
                    else:
                        raise ValueError('Unsupported compression, not lzfse!')
                else:
                    return data[4:]  # first 4 bytes is size (which is practically rest of file)
        else:
            raise ValueError('Unsupported Format')

    def convert_to_png(self, f, save_to_path):
        if self.validate_header(f):
            data = self.get_uncompressed_texture_data(f)
            dec_img = Image.frombytes('RGBA', (self.pixelWidth, self.pixelHeight), data, 'astc', (4, 4, False))
            dec_img.save(save_to_path, "PNG")
            return True
        return False

    def save_uncompressed_texture(self, f, save_to_path):
        if self.validate_header(f):
            data = self.get_uncompressed_texture_data(f)
            f = open(save_to_path, 'wb')
            f.write(data)
            f.close()
            return True
        return False