#!/usr/bin/env python3
import argparse
import serial
import time
from controller import Controller
from hexdump import hexdump


def poll_loop(pad):
    while True:
        response = pad.poll_state()
        print(f'state: {response.hex(" ")}')
        time.sleep(0.001)


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

    # set bank to 0
    pad.pak_write(0xa000, b'\x00' * 32)

    data = pad.pak_read(0xc100) + pad.pak_read(0xc120) + pad.pak_read(0xc140)
    hexdump(data)

    # pak off
    pad.pak_write(0xb000, b'\x00' * 32)


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
            present = pad.check_accessory_id(0x80)
            print(f'rumble pak present: {present}')
        elif args.transferpak_test:
            tpak_test(pad)
        else:
            poll_loop(pad)


if __name__ == '__main__':
    main()
