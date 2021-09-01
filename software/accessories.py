class Accessory:

    accessory_id = None

    def __init__(self, pad):
        self.pad = pad

    def check_pak(self):
        if self.accessory_id is None:
            raise ValueError('Accessory ID not defined')

        return self.pad.check_accessory_id(self.accessory_id)


class RumblePak(Accessory):

    accessory_id = 0x80

    def __init__(self, pad):
        super().__init__(pad)

    def set_rumble(self, on):
        if on:
            data = b'\x01' * 32
        else:
            data = b'\x00' * 32

        self.pad.pak_write(0xc000, data)


class TransferPak(Accessory):

    accessory_id = 0x84

    def __init__(self, pad, verbose=False):
        super().__init__(pad)
        self.verbose = verbose

        self.last_bank = None

    def translate_cart_addr(self, address):
        # Transfer Pak uses range 0xc000 - 0xffff for cart
        # read and write, which splits the overall 16-bit address
        # space of the cart into 4 banks of 0x4000 bytes

        bank, tpak_addr = divmod(address, 0x4000)
        tpak_addr += 0xc000
        return bank, tpak_addr

    def cart_present(self):
        """Check if cartridge is present"""

        check_mode = self.pad.pak_read(0xb000)
        if self.verbose:
            print(f'check mode: {check_mode.hex()}')

        return check_mode[31] == 0x80

    def cart_enable(self, enable):
        """Enable/power cartridge"""
        if enable:
            data = b'\x01' * 32
        else:
            data = b'\x00' * 32

        # set access mode
        self.pad.pak_write(0xb000, data)

    def switch_bank(self, bank):
        if self.last_bank != bank:
            if self.verbose:
                print(f'switching to address bank {bank}')

            self.last_bank = bank
            self.pad.pak_write(0xa000, bytes([bank]) * 32)
        elif self.verbose:
            print(f'skip redundant bank switch to bank {bank}')

    def cart_read(self, address):
        """Read from GB cart address"""

        if address < 0 or address > 0xffff:
            raise ValueError('address out of range')
        elif address & 0x1f != 0:
            # TODO allow arbitrary address
            raise ValueError('address must be multiple of 32')

        # TODO count of bytes to read

        # automatic Transfer Pak bank switching
        bank, tpak_addr = self.translate_cart_addr(address)

        # Switch bank and read data
        self.switch_bank(bank)
        return self.pad.pak_read(tpak_addr)

    def cart_write(self, address, data):
        """Write to GB cart address"""

        if address < 0 or address > 0xffff:
            raise ValueError('address out of range')
        elif address & 0x1f != 0:
            # TODO allow arbitrary address
            raise ValueError('address must be multiple of 32')
        elif len(data) != 32:
            raise ValueError('data must be 32 bytes')

        # automatic Transfer Pak bank switching
        bank, tpak_addr = self.translate_cart_addr(address)

        # Switch bank and write data
        self.switch_bank(bank)
        return self.pad.pak_write(tpak_addr, data)
