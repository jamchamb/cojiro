#!/usr/bin/env python3
import argparse
import serial
from uart_util import sync_recv
from crc_util import extract_addr

# Recognized JoyBus commands
CMD_INFO_RESET = 0xff
CMD_INFO = 0x00
CMD_STATE = 0x01
CMD_PAK_READ = 0x02
CMD_PAK_WRITE = 0x03


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('port', type=str)
    parser.add_argument('-b', '--baudrate', type=int, default=1500000)
    parser.add_argument('-v', '--verbose', action='store_true', default=False)
    args = parser.parse_args()

    with serial.Serial(args.port, args.baudrate) as ser:
        print(ser.name)
        ser.reset_input_buffer()
        ser.reset_output_buffer()

        while True:
            bytez, response_bytez = sync_recv(ser, args.verbose)

            cmd = bytez[0]
            if args.verbose and cmd != CMD_STATE:
                print(f'cmd {cmd:02x}')
                print(bytez.hex())

            if cmd in [CMD_INFO, CMD_INFO_RESET, CMD_STATE]:
                # state cmd is spammy
                pass
            elif cmd == CMD_PAK_READ:
                address, crc = extract_addr(bytez[1:3])
                print(f'read cmd: {address:04x} (addr CRC-5 {crc:02x})')
                print(f'  response: {response_bytez.hex()}')
            elif cmd == CMD_PAK_WRITE:
                address, crc = extract_addr(bytez[1:3])
                data = bytez[3:]
                print(f'write cmd: {address:04x} (addr CRC-5 {crc:02x})')
                print(f'  {data.hex()}')
                print(f'  response: {response_bytez.hex()}')
            else:
                print(f'unknown cmd {cmd:02x}')


if __name__ == '__main__':
    main()
