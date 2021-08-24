def sendall(ser, data):
    n = 0
    while n < len(data):
        n += ser.write(data[n:])
    #print(f'sent {data}')


def sync_recv(ser, verbose=False):
    while True:
        # get number of bytes to receive
        sync_magic1 = ser.read(1)
        if len(sync_magic1) != 1:
            continue
        if sync_magic1 != b'\xaa':
            if verbose:
                print('out of sync')
                print(sync_magic1)
            continue

        sync_magic2 = ser.read(1)
        if len(sync_magic2) != 1 or sync_magic2 != b'\x55':
            if verbose:
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
            response_bytez = b''

        return (bytez, response_bytez)
