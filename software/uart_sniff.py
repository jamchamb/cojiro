#!/usr/bin/env python3
import argparse
from pylibftdi import (Device, INTERFACE_B)


def sendall(ser, data):
    n = 0
    while n < len(data):
        n += ser.write(data[n:])
    #print(f'sent {data}')


def extract_addr(packed):
    address = (packed[0] << 3) | (packed[1] >> 5)
    address *= 32
    crc = packed[1] & 0x1f
    return address, crc


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('port', type=str)
    parser.add_argument('-b', '--baudrate', type=int, default=1500000)
    parser.add_argument('-v', '--verbose', action='store_true', default=False)
    args = parser.parse_args()

    with Device(interface_select=INTERFACE_B) as ser:
        ser.baudrate = args.baudrate
        if ser.baudrate != args.baudrate:
            raise Exception('baud rate failed')

        print(args.port)

        ser.flush_input()

        while True:
            # get number of bytes to receive
            sync_magic1 = ser.read(1)
            if len(sync_magic1) != 1:
                continue
            if sync_magic1 != b'\xaa':
                if args.verbose:
                    print('out of sync')
                    print(sync_magic1)
                continue

            sync_magic2 = ser.read(1)
            if len(sync_magic2) != 1 or sync_magic2 != b'\x55':
                if args.verbose:
                    print('out of sync 2')
                    print(sync_magic2)
                continue

            byte_count = ser.read(1)
            if len(byte_count) != 1:
                print('error: no command length received')
            byte_count = ord(byte_count)

            response_byte_count = ser.read(1)
            if len(response_byte_count) != 1:
                print('error: no response length received')
                continue
            response_byte_count = ord(response_byte_count)

            bytez = ser.read(byte_count)
            if len(bytez) == 0:
                continue

            if response_byte_count > 0:
                response_bytez = ser.read(response_byte_count)
            else:
                response_bytez = None

            if args.verbose:
                print(f'rcving {byte_count} command bytes, {response_byte_count} response bytes')

            cmd = bytez[0]
            if args.verbose and cmd != 1:
                print(f'cmd {cmd:02x}')
                print(bytez.hex())

            if cmd in [0, 1, 0xff]:
                pass
            elif cmd == 2:
                address, crc = extract_addr(bytez[1:3])
                print(f'read cmd: {address:04x} (addr CRC-5 {crc:02x})')
                print(f'  response: {response_bytez.hex()}')
            elif cmd == 3:
                address, crc = extract_addr(bytez[1:3])
                data = bytez[3:]
                print(f'write cmd: {address:04x} (addr CRC-5 {crc:02x})')
                print(f'  {data.hex()}')
                print(f'  response: {response_bytez.hex()}')
            else:
                print(f'unknown cmd {cmd:02x}')


if __name__ == '__main__':
    main()
