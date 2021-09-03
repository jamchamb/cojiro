from .accessory import Accessory
from gb_cart import GBHeader
from tqdm import tqdm

GB_ROM_BANK_SZ = 0x4000
GB_RAM_BANK_SZ = 0x2000


class TransferPak(Accessory):

    accessory_id = 0x84

    def __init__(self, pad, verbose=False):
        super().__init__(pad)
        self.verbose = verbose

        self.gb_header = None
        self.cart_powered = False

        self.last_tpak_bank = None

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
            self.cart_powered = True
        else:
            data = b'\x00' * 32
            self.cart_powered = False

        # set access mode
        self.pad.pak_write(0xb000, data)

    def cart_enable_ram(self, enable):
        """Enable read/write to external RAM"""
        if self.gb_header.get_ram_size() == 0:
            raise Exception('Cartridge has no RAM')

        if enable:
            data = b'\x0a' * 32
        else:
            data = b'\x00' * 32

        self.cart_write(0, data)

    def switch_tpak_bank(self, bank):
        if self.last_tpak_bank != bank:
            if self.verbose:
                print(f'switching to address bank {bank}')

            self.last_tpak_bank = bank
            self.pad.pak_write(0xa000, bytes([bank]) * 32)
        elif self.verbose:
            print(f'skip redundant bank switch to bank {bank}')

    def cart_read(self, address):
        """Read from GB cart address"""
        if not self.cart_powered:
            raise Exception('cart not powered on')

        if address < 0 or address > 0xffff:
            raise ValueError('address out of range')
        elif address & 0x1f != 0:
            # TODO allow arbitrary address
            raise ValueError('address must be multiple of 32')

        # TODO count of bytes to read

        # automatic Transfer Pak bank switching
        tpak_bank, tpak_addr = self.translate_cart_addr(address)

        # Switch bank and read data
        self.switch_tpak_bank(tpak_bank)
        return self.pad.pak_read(tpak_addr)

    def cart_write(self, address, data):
        """Write to GB cart address"""

        if not self.cart_powered:
            raise Exception('cart not powered on')

        if address < 0 or address > 0xffff:
            raise ValueError('address out of range')
        elif address & 0x1f != 0:
            # TODO allow arbitrary address
            raise ValueError('address must be multiple of 32')
        elif len(data) != 32:
            raise ValueError('data must be 32 bytes')

        # automatic Transfer Pak bank switching
        tpak_bank, tpak_addr = self.translate_cart_addr(address)

        # Switch bank and write data
        self.switch_tpak_bank(tpak_bank)
        return self.pad.pak_write(tpak_addr, data)

    def load_rom_header(self, verify=True):
        data = self.cart_read(0x100) + \
            self.cart_read(0x120) + \
            self.cart_read(0x140)
        data = data[:80]
        gb_header = GBHeader(data)

        if verify and not gb_header.verify_logo():
            if self.verbose:
                print('Boot logo check failed')
            return False

        if verify and not gb_header.verify_header():
            if self.verbose:
                print('Header checksum failed')
            return False

        self.gb_header = gb_header
        return True

    def switch_rom_bank(self, rom_bank):
        if rom_bank < 0:
            raise ValueError('ROM bank must be positive')

        mbc_type = self.gb_header.get_mbc_type()

        if mbc_type == 'NO_MBC':
            if rom_bank > 1:
                raise ValueError('No MBC, only banks 0 and 1 allowed')
        elif mbc_type == 'MBC1':
            # There's a lot of special case handling for banks 0x20/0x40/0x60.
            # It would probably be better to implement MBC classes to abstract
            # out bank reads instead of just bank switching.
            if rom_bank > 0x1f:
                raise NotImplementedError('MBC1 handling 0x20, 0x40, 0x60 not implemented')

            # Select simple ROM banking mode
            self.cart_write(0x6000, b'\x00' * 32)

            # Low 5 bits
            low_n = rom_bank & 0x1f
            self.cart_write(0x2000, low_n.to_bytes(1, 'big') * 32)
        elif mbc_type == 'MBC3':
            # 7 bit ROM bank number
            low_n = rom_bank & 0x7f
            self.cart_write(0x2000, low_n.to_bytes(1, 'big') * 32)
        elif mbc_type == 'MBC5':
            # Low 8 bits of ROM bank number
            low_n = rom_bank & 0xff
            self.cart_write(0x2000, low_n.to_bytes(1, 'big') * 32)

            # High bit of ROM bank number
            high_n = (rom_bank >> 8) & 1
            self.cart_write(0x3000, high_n.to_bytes(1, 'big') * 32)
        else:
            raise NotImplementedError('Unsupported MBC type {mbc_type}')

    def read_rom_bank(self, rom_bank, progress=None):
        """Read full ROM bank from cartridge"""

        if rom_bank == 0:
            # Bank 0 always at 0000-3fff
            chunks = []
            for addr in range(0x0000, 0x4000, 32):
                chunks.append(self.cart_read(addr))
                if progress is not None:
                    progress.update(32)
            return b''.join(chunks)
        else:
            # Switched banks at 4000-7fff
            # (TODO: except special cases for MBC1)
            self.switch_rom_bank(rom_bank)

            chunks = []
            for addr in range(0x4000, 0x8000, 32):
                chunks.append(self.cart_read(addr))
                if progress is not None:
                    progress.update(32)
            return b''.join(chunks)

    def switch_ram_bank(self, ram_bank):
        mbc_type = self.gb_header.get_mbc_type()

        if mbc_type == 'NO_MBC':
            if ram_bank != 0:
                raise ValueError('Only one RAM bank with no MBC')
        elif mbc_type == 'MBC1':
            # Select RAM banking mode
            self.cart_write(0x6000, b'\x01' * 32)

            # Set 2 bit RAM bank number
            ram_bank &= 3
            self.cart_write(0x4000, ram_bank.to_bytes(1, 'big') * 32)
        elif mbc_type == 'MBC3':
            # Set 2 bit RAM bank number
            ram_bank &= 3
            self.cart_write(0x4000, ram_bank.to_bytes(1, 'big') * 32)
        elif mbc_type == 'MBC5':
            self.cart_write(0x4000, ram_bank.to_bytes(1, 'big') * 32)
        else:
            raise NotImplementedError()

    def read_ram_bank(self, ram_bank, progress=None):
        """Read full RAM bank from cartridge"""

        self.switch_ram_bank(ram_bank)

        chunks = []
        for addr in range(0xa000, 0xc000, 32):
            chunks.append(self.cart_read(addr))
            if progress is not None:
                progress.update(32)

        return b''.join(chunks)

    def dump_rom(self, rom_filename):
        """Dump cartridge ROM banks to file"""

        rom_size = self.gb_header.get_rom_size()
        if rom_size == 0:
            print('No ROM banks to dump')
            return

        # Check MBC type is supported
        try:
            self.switch_rom_bank(1)
        except NotImplementedError:
            print('ROM bank switching for MBC type not implemented')
            return
        except Exception:
            # Skip cart power exception
            pass

        rom_file = open(rom_filename, 'wb')
        n_rom_banks = rom_size // GB_ROM_BANK_SZ
        print(f'Dumping {n_rom_banks} ROM banks to {rom_filename}...')

        # progress bar
        progress = tqdm(total=rom_size)

        self.cart_enable(True)
        for rom_bank in range(n_rom_banks):
            bank_data = self.read_rom_bank(rom_bank, progress=progress)
            rom_file.write(bank_data)
        self.cart_enable(False)

        progress.close()
        rom_file.close()

    def dump_ram(self, ram_filename):
        """Dump cartridge RAM banks to file"""

        ram_size = self.gb_header.get_ram_size()
        if ram_size == 0:
            print('No RAM to dump')
            return

        # Check MBC type is supported
        try:
            self.switch_ram_bank(0)
        except NotImplementedError:
            print('RAM bank switching for MBC type not implemented')
            return
        except Exception:
            # Skip cart power exception
            pass

        ram_file = open(ram_filename, 'wb')
        n_ram_banks = ram_size // GB_RAM_BANK_SZ
        print(f'Dumping {n_ram_banks} RAM banks to {ram_filename}...')

        # progress bar
        progress = tqdm(total=ram_size)

        self.cart_enable(True)
        self.cart_enable_ram(True)

        for ram_bank in range(n_ram_banks):
            ram_data = self.read_ram_bank(ram_bank, progress=progress)
            ram_file.write(ram_data)

        self.cart_enable_ram(False)
        self.cart_enable(False)

        progress.close()
        ram_file.close()
