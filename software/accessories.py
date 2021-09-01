class Accessory:

    accessory_id = None

    def __init__(self, pad):
        self.pad = pad

    def check_pak(self):
        if self.accessory_id is None:
            raise ValueError('Accessory ID not defined')

        return self.pad.check_accessory_id(self.accessory_id)


class RumblePak(Accessory):

    accessory_id = 0x80

    def __init__(self, pad):
        super().__init__(pad)

    def set_rumble(self, on):
        if on:
            data = b'\x01' * 32
        else:
            data = b'\x00' * 32

        self.pad.pak_write(0xc000, data)
