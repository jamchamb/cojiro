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

        self.entry_code = unpacked[0]
        self.logo_data = unpacked[1]

        # title could be full 16 bytes
        self.title = unpacked[2]
        self.manufacturer_code = unpacked[3]
        self.cgb_flag = unpacked[4]

        if self.cgb_flag not in [0x80, 0xc0]:
            self.title += self.manufacturer_code + bytes([self.cgb_flag])
            self.manufacturer_code = None
            self.cgb_flag = None

        self.new_licensee_code = unpacked[5]  # may be part of title
        self.sgb_flag = unpacked[6]
        self.cartridge_type = unpacked[7]
        self.rom_size = unpacked[8]
        self.ram_size = unpacked[9]
        self.region_code = unpacked[10]
        self.old_licensee_code = unpacked[11]
        self.mask_rom_ver = unpacked[12]
        self.header_checksum = unpacked[13]
        self.global_checksum = unpacked[14]
