#!/usr/bin/env python3
import argparse
import serial
import time
from controller import Controller
from hexdump import hexdump
from gb_cart import GBHeader


def poll_loop(pad):
    while True:
        response = pad.poll_state()
        print(f'state: {response.hex(" ")}')
        time.sleep(0.001)


def rumble_test(pad):
    present = pad.check_accessory_id(0x80)
    print(f'rumble pak present: {present}')

    if present:
        pad.pak_write(0xc000, b'\x01' * 32)
        time.sleep(1.0)
        pad.pak_write(0xc000, b'\x00' * 32)


def tpak_read(pad, address):
    # Read from GB cart address using Transfer Pak
    # with auto (tpak) bank switching
    if address > 0xffff:
        raise ValueError('address not 16-bit')
    elif address & 0x1f != 0:
        # TODO allow arbitrary address
        raise ValueError('address must be multiple of 32')

    # TODO count of bytes to read

    # set bank to 0-3
    bank = address // 0x4000
    pad.pak_write(0xa000, bytes([bank]) * 32)

    return pad.pak_read(0xc000 + (address % 0x4000))


def tpak_test(pad):
    present = pad.check_accessory_id(0x84)
    print(f'transfer pak present: {present}')

    if not present:
        return

    # cart access mode
    check_mode = pad.pak_read(0xb000)
    print(f'check mode: {check_mode.hex()}')

    if check_mode[31] != 0x80:
        return

    # set access mode to 1
    pad.pak_write(0xb000, b'\x01' * 32)

    data = tpak_read(pad, 0x100) + \
        tpak_read(pad, 0x120) + \
        tpak_read(pad, 0x140)
    data = data[:80]

    print('ROM header:')
    hexdump(data)

    # access mode 0 (cart off)
    pad.pak_write(0xb000, b'\x00' * 32)

    gb_header = GBHeader(data)
    print(gb_header.__dict__)

    # hash the logo data
    logo_check = gb_header.verify_logo(verbose=True)
    print(f'logo check pass: {logo_check}')

    # check header checksum
    header_check = gb_header.verify_header()
    print(f'header check pass: {header_check}')


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
    mode_group.add_argument('--rumble-test', action='store_true',
                            default=False)
    mode_group.add_argument('--transferpak-test', action='store_true',
                            default=False)
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
        elif args.rumble_test:
            rumble_test(pad)
        elif args.transferpak_test:
            tpak_test(pad)
        else:
            poll_loop(pad)


if __name__ == '__main__':
    main()
