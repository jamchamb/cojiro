#!/usr/bin/env python3
import argparse
import serial
import time
from accessories import RumblePak, TransferPak
from controller import Controller
from hexdump import hexdump
from gb_cart import GBHeader
from tqdm import tqdm


def poll_loop(pad):
    while True:
        response = pad.poll_state()
        print(f'state: {response.hex(" ")}')
        time.sleep(0.001)


def rumble_test(pad):
    rpak = RumblePak(pad)
    present = rpak.check_pak()
    print(f'rumble pak present: {present}')

    if present:
        rpak.set_rumble(True)
        time.sleep(0.5)
        rpak.set_rumble(False)


def tpak_test(pad, rom_filename=None, ram_filename=None, verbose=False):
    tpak = TransferPak(pad, verbose)
    present = tpak.check_pak()
    print(f'transfer pak present: {present}')

    if not present:
        return

    # cart access mode
    cart_present = tpak.cart_present()
    if not cart_present:
        print('no cart present')
        return

    # set access mode to 1
    tpak.cart_enable(True)

    data = tpak.cart_read(0x100) + \
        tpak.cart_read(0x120) + \
        tpak.cart_read(0x140)
    data = data[:80]

    tpak.cart_enable(False)

    print('ROM header:')
    hexdump(data)

    gb_header = GBHeader(data)
    print(f'Raw title: {gb_header.title_guess()}')

    # hash the logo data
    logo_check = gb_header.verify_logo()
    print(f'logo check pass: {logo_check}')

    # check header checksum
    header_check = gb_header.verify_header()
    print(f'header check pass: {header_check}')

    print(f'ROM size: {gb_header.get_rom_size():#x} bytes')
    print(f'RAM size: {gb_header.get_ram_size():#x} bytes')

    if verbose:
        print(gb_header.__dict__)

    if rom_filename is not None:
        tpak_dump_rom(tpak, gb_header, rom_filename)

    if ram_filename is not None:
        tpak_dump_ram(tpak, gb_header, ram_filename)


def tpak_dump_rom(tpak, gb_header, rom_filename):
    # Only implemented MBC5 for now
    if gb_header.cartridge_type < 0x19 or gb_header.cartridge_type > 0x1e:
        print('ROM dumping is only implemented for MBC5 here')
        return

    rom_file = open(rom_filename, 'wb')

    n_rom_banks = gb_header.get_rom_size() // 0x4000
    print(f'Dumping {n_rom_banks} ROM banks to {rom_filename}...')

    # progress bar
    progress = tqdm(total=gb_header.get_rom_size())

    tpak.cart_enable(True)
    for rom_bank in range(n_rom_banks):
        # Low 8 bits of ROM bank number
        low_n = rom_bank & 0xff
        tpak.cart_write(0x2000, low_n.to_bytes(1, 'big') * 32)

        # High bit of ROM bank number
        high_n = (rom_bank >> 8) & 1
        tpak.cart_write(0x3000, high_n.to_bytes(1, 'big') * 32)

        # Switched banks at 4000-7fff, MBC5 can switch in bank 0 too
        for addr in range(0x4000, 0x8000, 32):
            chunk = tpak.cart_read(addr)
            rom_file.write(chunk)
            progress.update(32)

    tpak.cart_enable(False)
    progress.close()
    rom_file.close()


def tpak_dump_ram(tpak, gb_header, ram_filename):
    # Only implemented MBC5 for now
    if gb_header.cartridge_type < 0x19 or gb_header.cartridge_type > 0x1e:
        print('ROM dumping is only implemented for MBC5 here')
        return

    # Dump RAM banks
    ram_file = open(ram_filename, 'wb')

    n_ram_banks = gb_header.get_ram_size() // 0x2000
    print(f'Dumping {n_ram_banks} RAM banks to {ram_filename}...')

    progress = tqdm(total=gb_header.get_ram_size())

    tpak.cart_enable(True)

    # Enable RAM
    tpak.cart_write(0, b'\x0a' * 32)

    for ram_bank in range(n_ram_banks):
        # Set RAM bank number
        tpak.cart_write(0x4000, ram_bank.to_bytes(1, 'big') * 32)

        for addr in range(0xa000, 0xc000, 32):
            chunk = tpak.cart_read(addr)
            ram_file.write(chunk)
            progress.update(32)

    # Disable RAM
    tpak.cart_write(0, b'\x00' * 32)

    tpak.cart_enable(False)
    progress.close()
    ram_file.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('port', type=str)
    parser.add_argument('-b', '--baudrate', type=int,
                        default=1500000)
    parser.add_argument('-v', '--verbose', action='store_true',
                        default=False)
    # mutually exclusive options below
    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument('--dump-cpak', type=str, default=None,
                            help='file to dump cpak memory to')
    mode_group.add_argument('--test-rpak', action='store_true',
                            default=False, help='Test Rumble Pak')
    mode_group.add_argument('--test-tpak', action='store_true',
                            default=False, help='Test Transfer Pak')
    mode_group.add_argument('--dump-tpak-rom', type=str,
                            default=None, help='file to dump ROM to')
    mode_group.add_argument('--dump-tpak-ram', type=str,
                            default=None, help='file to dump RAM to')
    args = parser.parse_args()

    with serial.Serial(args.port, args.baudrate) as ser:
        print(f'Using port: {ser.name}')
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        pad = Controller(ser, args.verbose)

        # Send info/reset
        pad_type, joyport_status = pad.pad_query(reset=True)

        print(f'Pad type: {pad_type:04x}, joyport status: {joyport_status:02x}')

        if args.dump_cpak is not None:
            pad.dump_cpak(args.dump_cpak)
        elif args.test_rpak:
            rumble_test(pad)
        elif args.test_tpak:
            tpak_test(pad, verbose=args.verbose)
        elif args.dump_tpak_rom:
            tpak_test(pad, rom_filename=args.dump_tpak_rom,
                      verbose=args.verbose)
        elif args.dump_tpak_ram:
            tpak_test(pad, ram_filename=args.dump_tpak_ram,
                      verbose=args.verbose)
        else:
            poll_loop(pad)


if __name__ == '__main__':
    main()
