# Copyright © 2022 Julien Lepiller
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# Small script to generate a NewGRF for town names. NML is a bit too limited
# for my purposes, esp. wrt entropy count. This implementation allows to
# manually set entropy parameters and is directly controllable with Python.
#

import math

class GRF:
    """
    The main class, it is used to generate a NewGRF. To add content, you need to
    add actions to this class.  To do so, add the actions to the `actions`
    variables, like so:

      grf = GRF("file.grf")
      grf.actions.append(some_action)

    and you can generate the GRF with:

      grf.output()

    The GRF will contain the actions in the order they were added, so make sure
    that the first action is a Header (see below).
    """
    def __init__(self, filename):
        self.filename = filename
        self.actions = []

    def output(self):
        with open(self.filename, 'wb') as f:
            b = bytearray()
            for action in self.actions:
                action.output(b)

            header = bytearray([0x00, 0x00, ord("G"), ord("R"), ord("F"), 0x82, 0x0D, 0x0A, 0x1A, 0x0A])
            size = len(b) + 1
            header.append(size & 0xFF)
            header.append((size >> 8) & 0xFF)
            header.append((size >> 16) & 0xFF)
            header.append(size >> 24)
            header.append(0)  # no compression

            header_str = bytes(header)
            f.write(header_str)
            f.write(b)


langs = {'en': 0, 'fr': 3, '': 0x7f}
def output_byte(b, file):
    file.extend(b.to_bytes(1, 'little'))
def output_dword(d, file):
    output_byte(d & 0xff, file)
    output_byte((d >> 8) & 0xff, file)
    output_byte((d >> 16) & 0xff, file)
    output_byte((d >> 24) & 0xff, file)

def output_string(text, file):
    file.extend(b'\xc3\x9e')
    file.extend(bytes(text, 'utf-8'))
    file.extend(b'\x00')
def output_lang_string(lang, text, file):
    output_byte(langs[lang], file)
    output_string(text, file)

class Header:
    """
    Represents header actions, that provide information about your NewGRF.
    """
    def __init__(self, names, descriptions, url, version, minversion, author):
        """
        Create a new Header.  A langdict is a dictionary that associates a
        language tag to a string in that language.

        :param langdict names: The name of this NewGRF
        :param langdict descriptions: The description of this NewGRF
        :param str url: The URL for this NewGRF
        :param int version: The version of this NewGRF
        :param int minversion: The minimal version this NewGRF is compatible with
        :param bytes author: The author tag, as a four-bytes bytes.
        """
        self.names = names
        self.descriptions = descriptions
        self.url = url
        self.version = version
        self.minversion = minversion
        self.author = author

    def output(self, b):
        b.extend(b'\x04\x00\x00\x00\xff\x08\x00\x00\x00')
        file = bytearray()

        file.extend(b'\x14')
        # Enter container INFO, start Text DESC
        for lang in self.descriptions:
            if lang == 'en':
                continue
            file.extend(b'CINFOTDESC')
            output_lang_string(lang, self.descriptions[lang], file)
        # Exit Text DESC
        for lang in self.names:
            if lang == 'en':
                continue
            file.extend(b'TNAME')
            output_lang_string(lang, self.names[lang], file)
        file.extend(b'TURL_')
        output_lang_string('', self.url, file)
        file.extend(b'BVRSN')
        file.extend(b'\x04\x00')
        output_byte(self.version & 0xFF, file)
        output_byte((self.version >> 8) & 0xFF, file)
        output_byte((self.version >> 16) & 0xFF, file)
        output_byte((self.version >> 24) & 0xFF, file)
        file.extend(b'BMINV')
        file.extend(b'\x04\x00')
        output_byte(self.minversion & 0xFF, file)
        output_byte((self.minversion >> 8) & 0xFF, file)
        output_byte((self.minversion >> 16) & 0xFF, file)
        output_byte((self.minversion >> 24) & 0xFF, file)
        file.extend(b'BNPAR\x01\x00\x00')
        file.extend(b'BPALS\x01\x00A')
        file.extend(b'BBLTR\x01\x008')
        # Exit INFO
        file.extend(b'\x00')
        # Exit Action14
        file.extend(b'\x00')

        size = len(file)
        output_dword(size, b)
        b.extend(b'\xff')
        b.extend(file)
        file = bytearray()

        # Action8, for GRFID
        file.extend(b'\x08\x08')
        file.extend(bytes(self.author))
        file.extend(bytes(self.names['en'], 'utf-8'))
        file.extend(b'\x00')
        file.extend(bytes(self.descriptions['en'], 'utf-8'))
        file.extend(b'\x00')

        size = len(file)
        output_dword(size, b)
        b.extend(b'\xff')
        b.extend(file)

#
# Town Names generation
#

class TownReference:
    """
    A reference to another town_name structure, by ID, with optional bias
    """
    def __init__(self, ref, proba = 1):
        self.ref = ref
        self.proba = proba
    def copy(self):
        return TownReference(self.ref, self.proba)

class TownString:
    """
    A text with optional bias
    """
    def __init__(self, text, proba = 1):
        self.text = text
        self.proba = proba
    def copy(self):
        return TownString(self.text, self.proba)

class TownName:
    """
    A town_name structure.
    """
    def __init__(self, entropyStart, ID, name, content):
        """
        Create a town_name structure.  Content is a list of parts that will be
        combined.  Each part is a list of TownString or TownReference objects.
        The game will chose one of these per part and combine them to form
        a town name (or a part of a town name).


        :param int entropyStart: A number between 0 and 31, first bit of entropy used to generate this part
        :param str ID: An identifier for this part
        :param str name: A name that will appear in the game's menu, or None
        :param list content: A list of parts, that are combined in order.
        """
        self.ID = ID
        self.content = content
        self.entropyStart = entropyStart
        self.name = name

    def output(self, b, IDs):
        file = bytearray()

        file.extend(b'\x0F')
        output_byte(IDs[self.ID] + (0x80 if self.name is not None else 0), file)
        if self.name is not None:
            for lang in self.name:
                output_lang_string(lang, self.name[lang], file)
            file.extend(b'\x00')
        output_byte(len(self.content), file)

        # write parts
        for part in self.content:
            sum_entropy = 0
            for entry in part:
                sum_entropy += entry.proba

            output_byte(len(part), file)
            output_byte(self.entropyStart, file)
            output_byte(math.ceil(math.log2(sum_entropy)), file)
            for entry in part:
                if isinstance(entry, TownReference):
                    output_byte(0x80 | entry.proba, file)
                    output_byte(IDs[entry.ref], file)
                else:
                    output_byte(entry.proba, file)
                    output_string(entry.text, file)

        size = len(file)
        output_dword(size, b)
        b.extend(b'\xff')
        b.extend(file)

    def copy(self):
        content = []
        for part in self.content:
            newpart = []
            for entry in part:
                newpart.append(entry.copy())
            content.append(newpart)
        return TownName(self.entropyStart, self.ID, self.name, content)
        
class TownNames:
    """
    An action that contains multiple town names.  This is the type you need to
    give GRF to generate a NewGRF with town names.

      grf.actions.append(TownNames([town1, town2, town3])
    """
    def __init__(self, entries):
        self.entries = entries
        self.townNameIDS = {}
        self.lastTownNameID = 0

    def output(self, file):
        entries = []
        for entry in self.entries:
            entries.extend(TownNames.divideTownNames(entry))

        for entry in entries:
            self.townNameIDS[entry.ID] = self.lastTownNameID
            self.lastTownNameID += 1
            entry.output(file, self.townNameIDS)

    def divideTownNames(entry):
        ID = entry.ID
        content = entry.content
        entropy = entry.entropyStart
        name = entry.name

        newTownNames = []
        newContent = []

        for part in content:
            maxEntropy = math.ceil(math.log2(len(part)))
            newPart = []

            max = 255
            while len(part) > max and max > 1:
                howMany = min(len(part), 255)
                newPart.append(TownReference(ID + "__" + str(255-max), howMany))
                newName = TownNames.divideTownNames(TownName(entropy+maxEntropy-8, ID+"__"+str(255-max), None, [part[:howMany]]))
                newTownNames.extend(newName)
                part = part[255:]
                max -= 1
            newPart.extend(part)
            newContent.append(newPart)
        newTownNames.append(TownName(entropy, ID, name, newContent))

        return newTownNames

class Blank:
    def __init__(self):
        pass

    def output(self, file):
        file.extend(b'\x00\x00\x00\x00\x00\x00\x00\x00')
