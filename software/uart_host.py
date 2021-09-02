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

    # Check for Transfer Pak
    present = tpak.check_pak()
    print(f'transfer pak present: {present}')

    if not present:
        return

    # Check for a cartridge
    cart_present = tpak.cart_present()
    if not cart_present:
        print('no cart present')
        return

    # Power cartridge and read ROM header
    tpak.cart_enable(True)
    if tpak.load_rom_header():
        gb_header = tpak.gb_header
    else:
        gb_header = None
    tpak.cart_enable(False)

    if gb_header is None:
        print('failed to get valid ROM header')
        return

    print('ROM header:')
    hexdump(gb_header._raw_data)

    print(f'Raw title: {gb_header.title_guess()}')
    print(f'MBC type: {gb_header.get_mbc_type()}')
    print(f'ROM size: {gb_header.get_rom_size():#x} bytes')
    print(f'RAM size: {gb_header.get_ram_size():#x} bytes')

    if verbose:
        print(gb_header.__dict__)

    if rom_filename is not None:
        tpak.dump_rom(rom_filename)

    if ram_filename is not None:
        tpak.dump_ram(ram_filename)


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
