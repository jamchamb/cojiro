import hashlib
import struct


class GBHeader:

    def __init__(self, data):
        unpacked = struct.unpack(
            '>4s'  # entry point
            '48s'  # logo
            '11s'  # title
            '4s'   # manufacturer code
            'B'    # CGB flag
            '2s'   # new licensee code
            'B'    # SGB flag
            'B'    # cartridge type
            'B'    # ROM size
            'B'    # RAM size
            'B'    # region code
            'B'    # old licensee code
            'B'    # mask ROM version number
            'B'    # header checksum
            'H',    # global checksum
            data
        )

        self._raw_data = data

        self.entry_code = unpacked[0]
        self.logo_data = unpacked[1]

        # title could be full 16 bytes
        self.title = unpacked[2]
        self.manufacturer_code = unpacked[3]
        self.cgb_flag = unpacked[4]

        # full 16 byte title region
        self.title_max = data[52:68]

        if self.cgb_flag not in [0x80, 0xc0]:
            self.title += self.manufacturer_code + bytes([self.cgb_flag])
            self.manufacturer_code = None
            self.cgb_flag = None

        self.new_licensee_code = unpacked[5]  # may be part of title
        self.sgb_flag = unpacked[6]
        self.cartridge_type = unpacked[7]
        self._rom_size = unpacked[8]
        self._ram_size = unpacked[9]
        self.region_code = unpacked[10]
        self.old_licensee_code = unpacked[11]
        self.mask_rom_ver = unpacked[12]
        self.header_checksum = unpacked[13]
        self.global_checksum = unpacked[14]

    def title_guess(self):
        return self.title_max.split(b'\x00')[0]

    def verify_logo(self, verbose=False):
        md5 = hashlib.md5()
        md5.update(self.logo_data)
        logo_hash = md5.hexdigest()

        if verbose:
            print(f'logo MD5 hash: {logo_hash}')

        return logo_hash == "8661ce8a0ebede95e8a131a0aa1717f6"

    def verify_header(self, verbose=False):
        hdr_chk = 0
        for b in self._raw_data[0x34:0x4d]:
            hdr_chk = (hdr_chk + ~b) & 0xff

        if verbose:
            print(f'calculated header checksum: {hdr_chk}')

        return hdr_chk == self.header_checksum

    def get_rom_size(self):
        """Return ROM size in bytes"""
        if self._rom_size > 8:
            raise ValueError('ROM size code unknown')

        return 0x8000 << self._rom_size

    def get_ram_size(self):
        if self._ram_size > 5:
            raise ValueError('RAM size code unknown')

        if self._ram_size < 2:
            return 0
        elif self._ram_size == 2:
            return 0x2000
        elif self._ram_size == 3:
            return 0x2000 * 4
        elif self._ram_size == 4:
            return 0x2000 * 16
        elif self._ram_size == 5:
            return 0x2000 * 8

    def get_mbc_type(self):
        if self.cartridge_type in [0x0, 0x8, 0x9]:
            return 'NO_MBC'
        elif self.cartridge_type in range(0x1, 0x3 + 1):
            return 'MBC1'
        elif self.cartridge_type in range(0x5, 0x6 + 1):
            return 'MBC2'
        elif self.cartridge_type in range(0xb, 0xd + 1):
            return 'MMM01'
        elif self.cartridge_type in range(0xf, 0x13 + 1):
            return 'MBC3'
        elif self.cartridge_type in range(0x19, 0x1e + 1):
            return 'MBC5'
        elif self.cartridge_type == 0x20:
            return 'MBC6'
        elif self.cartridge_type == 0x22:
            return 'MBC7'

        return None
