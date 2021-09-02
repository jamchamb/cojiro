class Accessory:

    accessory_id = None

    def __init__(self, pad):
        self.pad = pad

    def check_pak(self):
        if self.accessory_id is None:
            raise ValueError('Accessory ID not defined')

        return self.pad.check_accessory_id(self.accessory_id)
