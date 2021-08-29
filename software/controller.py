import struct
from uart_util import send_cmd
from crc_util import (data_crc_lookup, pack_addr)

# Recognized JoyBus commands
CMD_INFO_RESET = 0xff
CMD_INFO = 0x00
CMD_STATE = 0x01
CMD_PAK_READ = 0x02
CMD_PAK_WRITE = 0x03


class BadCRCException(Exception):
    pass


class Controller:

    def __init__(self, ser, verbose=False):
        self.ser = ser
        self.verbose = verbose

    def send_cmd(self, cmd):
        return send_cmd(self.ser, cmd, self.verbose)

    def pak_read(self, address):
        """read a 32 byte chunk from controller pak"""
        packed_addr = pack_addr(address)
        cmd = struct.pack(
            '>B2s',
            CMD_PAK_READ,
            packed_addr)
        response = self.send_cmd(cmd)

        # Check response length
        if len(response) != 33:
            raise Exception(f'invalid response length {len(response)}')

        crc_received = response[-1]
        chunk = response[:32]
        crc_calculated = data_crc_lookup(chunk)

        if crc_received != crc_calculated:
            raise BadCRCException(
                f'CRC mismatched (received {crc_received:02x}, '
                f'calculated {crc_calculated:02x}')

        if self.verbose:
            print(f'{address:04x} good CRC {crc_calculated:02x}')

        return chunk

    def pak_write(self, address, data):
        if len(data) != 32:
            raise ValueError('data buffer must be 32 bytes')

        packed_addr = pack_addr(address)

        cmd = struct.pack(
            '>B2s32s',
            CMD_PAK_WRITE,
            packed_addr,
            data)

        return self.send_cmd(cmd)

    def check_accessory_id(self, accessory_id):
        """Check if this type of accessory is connected"""
        self.pak_write(0x8000, b'\xfe' * 32)
        reset_response = self.pak_read(0x8000)

        if self.verbose:
            print(f'accessory reset response: {reset_response.hex()}')

        acc_id_byte = accessory_id.to_bytes(1, 'big')
        self.pak_write(0x8000, acc_id_byte * 32)
        response = self.pak_read(0x8000)

        if self.verbose:
            print(f'accessory ID check: {response.hex()}')

        if response[31] == accessory_id:
            return True

        return False

    def pad_query(self, reset=False):
        if reset:
            cmd_id = CMD_INFO_RESET
        else:
            cmd_id = CMD_INFO

        cmd = struct.pack('>B', cmd_id)

        response_bytez = self.send_cmd(cmd)

        pad_type, joyport_status = struct.unpack('<HB', response_bytez)
        return (pad_type, joyport_status)

    def poll_state(self):
        # Poll button state
        cmd = struct.pack('>B', CMD_STATE)
        response = self.send_cmd(cmd)
        return response

    def dump_cpak(self, cpak_filename):
        pad_type, joyport_status = self.pad_query(reset=True)

        if joyport_status == 3:
            print('pak just inserted(?), please retry')
            return
        elif joyport_status != 1:
            print('no pak detected')
            return

        print(f'dump controller pak to {cpak_filename}...')

        test_file = open(cpak_filename, 'wb')

        for i in range(0, 0x8000, 32):
            retry = False

            # read a 32 byte chunk from controller pak
            try:
                chunk = self.pak_read(i)
            except BadCRCException:
                retry = True

            if retry:
                print(f'retrying address {i:04x}')
                i -= 32
            else:
                test_file.write(chunk)
                print(f'{i:04x}: {chunk.hex()}')

        test_file.close()
