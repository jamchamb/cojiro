#!/usr/bin/env python3
import argparse
import serial
import time
from accessories import RumblePak, TransferPak
from controller import Controller
from hexdump import hexdump
from gb_cart import GBHeader


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


def tpak_test(pad):
    tpak = TransferPak(pad, verbose=True)
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

    print('ROM header:')
    hexdump(data)

    tpak.cart_enable(False)

    gb_header = GBHeader(data)
    print(gb_header.__dict__)

    # hash the logo data
    logo_check = gb_header.verify_logo()
    print(f'logo check pass: {logo_check}')

    # check header checksum
    header_check = gb_header.verify_header()
    print(f'header check pass: {header_check}')

    print(f'ROM size: {gb_header.get_rom_size():#x} bytes')
    print(f'RAM size: {gb_header.get_ram_size():#x} bytes')


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
    args = parser.parse_args()

    with serial.Serial(args.port, args.baudrate) as ser:
        print(ser.name)
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
            tpak_test(pad)
        else:
            poll_loop(pad)


if __name__ == '__main__':
    main()
