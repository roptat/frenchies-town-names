###############################################################################
##       Frenchies, a NewGRF for generating French-sounding town names       ##
###############################################################################

#
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

from grf.grf import GRF, Header, TownNames, TownName, TownReference, TownString
import re

grf = GRF("frenchies.grf")

## Strings and metadata
DESCRIPTIONS = {
    'en': "The game only provides a limited amount of French city names. \
Other NewGRFs provide city names from a list of existing cities. That's \
boring. This NewGRF provides generated fake French-sounding yet amusing city \
names for all your OpenTTD games!",
    'fr': "Le jeu fournit un nombre limité de ville françaises. Les autres \
NewGRF proposent des noms tirés dans une liste de villes existantes. C’est \
pas drôle. Ce NewGRF propose des noms de villes amusants à consonnance \
française générés aléatoirement pour toutes vos parties d’OpenTTD !",
}
NAME = "Frenchies Town Names v0.1"

grf.actions.append(Header({'en': NAME}, DESCRIPTIONS,
    'https://github.com/roptat/frenchies-town-names', 1, 0, b'Rop\x01'))

#
# NML is usually the format used for writing NewGRFs, but it is too limited
# for town_names and what I want to do here.
# Generating city names that obey French orthography is difficult when you can
# only concatenate randomly-generated name parts. The idea here is to sort of
# pre-generate all possible names, with some misspelled names, and fix them in
# Python. Then, feed the list into the GRF file.
#
# I initially tried to write an NML file with all the possibilities but it took
# ages to load, and now I know it would have failed. Due to format constraints,
# it's not possible to have more than 255 strings per part, and although you
# can refer to other parts in order to increase the number of possibilities,
# the number of parts in a GRF is limited to 128, so you can have at most
# somewhere around 32,000 strings.
#
# Next, I tried to split parts a little, so instead of having a huge list of
# millions of entries, I had a few lists to combine to generate a name (essentially,
# a list would give a city name, another would give extensions).
#
# However, I still had to reduce the number of names because this time, each part
# took too much entropy.
#
# If you don't know, city names in OpenTTD are actually not strings, but a randomly
# chosen 32-bits number. The NML compiler, nmlc, seems to assign a region of this
# number (certain bits) to each part, and refuses to overlap any region.
#
# Yet, some parts would never be generated together, as when a part is used
# to chose between different options, these options can never occur at the same
# time in a generated name, that's the point of chosing one of them. So they can
# perfectly use the same region of the random number.
#
# Also, it kept complaining it needed too much entropy, and even gave bigger
# numbers after I tried to remove some possibilities, which doesn't make any
# sense.
#
# In the end, I came up with this design where I can control precisely which
# bits are used for which parts. Although I agree with nmlc that I need too much
# entropy to generate all possibilities, this is actually *on purpose*. More on
# that later ;)
#


# Well, when you generate names from random parts, they don't always read like
# actual French, so we have to filter or fix them.  This list is a list of
# tuples that contains a regular expression to match an incorrect pattern,
# and an optional replacement string that would be used instead of the incorrect
# pattern.
# We can use \1, \2, etc to refer to matched groups from the regular expression.
#
# Eg. (re.compile("([^Gg])ea([bcdfgjklmnpqrstvwxyz])"), r"\1a\2") means:
# - match any pattern where "ea" appears just before a consonnant, but not after
#   "g" or "G" (because names like "Vigeac" are valid, not "Vigneac", and
#   "Vigneau" is also valid).
# - If the name matches, replace ea with a, and keep the previous and next letters.
# So "Vigneac" matches and is replaced by "Vignac". Much better.

forbiddenPatterns = [
    (re.compile("([^Gg])ea([bcdfgjklmnpqrstvwxyz])"), r"\1a\2"),
    (re.compile("e([iée])"), r"\1"),
    (re.compile("ncc"), r"nc"),
    (re.compile("tn"), r"ten"),
    (re.compile("un([^aeiou])"), r"u\1"),
    (re.compile("ss([bcdfgjklmnpqrstvwxz])"), r"sse\1"),
    (re.compile("gn([bcdfgjklmnpqrstvwxyz])"), r"gnan\1"),
    (re.compile("nnn"), r"nn"),
    (re.compile("([^u])nsch"), r"\1nch"),
    (re.compile("n([bp])"), r"m\1"),
    (re.compile("oirs"), r"ois"),
    (re.compile("nm"), r"m"),
    (re.compile("er[bcdfgjklmnpqrstvwxz]([bcdfgjklmnpqrstvwxz])"), r"ert\1"),
    (re.compile("aé"), r"ané"),

    (re.compile("r[bcdfgjklmnpqrsvwxz][bcdfgjklmnpqrstvwxz]"), None),
    (re.compile("dv"), None),
    (re.compile("eau[aeiou]"), None),
    (re.compile("lln"), None),
    (re.compile("[ou]sn"), None),
    (re.compile("[^a]isn"), None),
    (re.compile("y[yi]"), None),
    (re.compile("ngn"), None),
    (re.compile("sgn"), None),
    (re.compile("dn"), None),
    (re.compile("nen[aeiouéèê]"), None),
    (re.compile("lh[bcdfgjklmnpqrstvwxz]"), None),
    (re.compile("ér[bcdfgjklmnpqrstvwxz]"), None),
    (re.compile("u[aeiouéèê]"), None),
    (re.compile("z[^aeiouéèêô]"), None),
    (re.compile("nch"), None),
]
def isAllowed(name):
    for (pattern, replacement) in forbiddenPatterns:
        if len(pattern.findall(name)) > 0:
            if replacement is None:
                return None
            name = pattern.sub(replacement, name)
    return name

# These classes contain a name and possible variants, with information on gender,
# number and origin. We don't want to mix different genders, different number
# or terms from different parts of France.
class Name:
    def __init__(self, name, gender=None, number=1, origin=None):
        self.name = name
        self.gender = gender
        self.number = number
        self.origin = origin

    def copy(self):
        return Name(self.name, self.gender, self.number, self.origin)

    def getFor(self, gender=None, number=None):
        return self.name

    def combine(self, nex):
        gender = self.gender
        if gender is None:
            gender = nex.gender
        if nex.gender is not None and nex.gender != gender:
            return None

        number = self.number
        if number is None:
            number = nex.number
        if nex.number is not None and nex.number != number:
            return None

        origin = self.origin
        if origin is None:
            origin = nex.origin
        if nex.origin is not None and nex.origin != origin:
            return None

        return Name(self.getFor(gender, number) + nex.getFor(gender, number), gender, number)
        

class MultiName(Name):
    def __init__(self, ms, mp, fs, fp):
        self.ms = ms
        self.mp = mp
        self.fs = fs
        self.fp = fp
        self.gender = None
        self.number = None
        self.origin = None

    def getFor(self, gender=None, number=None):
        if gender is None:
            gender = 'm'
        if number is None:
            number = 1

        if gender == 'm':
            return self.ms if number == 1 else self.mp
        else:
            return self.fs if number == 1 else self.fp

# Given multiple lists of Names, returns a new list of Names where all possible
# combinations have been generated, unless incompatible.
# For instance
# combine([Name("un", gender='m'), Name("une", gender='f')],
#   [Name(" pastèque", gender='f'), Name(" orange", gender='f'), Name(" fruit", gender='m')])
# Gives
#   [Name("un fruit", gender='m'), Name("une pastèque", gender='f'), Name("une orange", gender='f')]
def combine(*lst):
    if len(lst) == 0:
        return []
    if len(lst) == 1:
        return lst[0]
    l = lst[0]
    combined = combine(*lst[1:])
    r = []
    for s1 in l:
        for c in combined:
            s = s1.combine(c)
            if s is not None:
                r.append(s)
    return r

# Now we are ready to create our town_names.

# French town names can be split into three categories.
# - "Saint": many cities are dedicated to a local saint. The city name is composed
#   of a main part, that is the name of a saint such as "Saint-Jean" and an
#   extension (we'll see that in a bit).
# - "Anthro": the majority of cities were named after someone, such as the
#   person who lived there, a famous person, etc. Usually, adding a suffix to
#   the person's name was enough to create a city name. After some time, the
#   name evolved to the current form where it is a bit hard to recognize the
#   initial name.
# - "Germanic": cities that were founded after the roman empire used a slightly
#   different method for naming cities. Many cities were named after a characteristic,
#   a geographical, political or economical feature. That's how we get cities
#   like "Neufchâtel", litteral "Newcastle" :)
#
# To distinguish two cities that have the same name, some cities have an extension.
# In this GRF, "saint" cities always have an extension, although that is not
# always the case in reality, but it is the vast majority of them.
#
# An extension is often composed of a preposition ("en", "sur", "de", "sous", etc.)
# and another main part, that is either a geographical feature, or another name.
#
# In this GRF, I generate extensions from a small list of common extensions
# such as "sur-mer", "sous-bois", etc. In addition, three extensions add more
# possibilities:
# - "de": followed by another city's or location's name. Here, this is generated
#   in the same way as city names, but from different random bits, so it doesn't
#   generate the same name ;). I call this a *toponym*.
# - "en": followed by the name of the bigger region. Here, this is generated in
#   the same way as city names, but with different suffixes to have some variety
#   and make the names a bit more believable. I call this a *regionym* (that one
#   is a made-up word).
# - "sur": followed by the name of a river. Here, this is generated from two
#   parts, with a very low number of possibilities. It's probably something to
#   improve later. I call this an *hydronym*.
#
# To select an extension, I first select whether an extension will be used (one in 32
# chance), then I choose in a list of common extensions and of "de", "en" and "sur"
# extensions. Note that because of ortography rules, the "de" rule is actually
# split between "de" and "d’".
#
# Here is a representation of how we get entropy for the various parts
# 
#  0  1  2  3  4  5  6  7  8  9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31
# `----´`-------------------´                                       `-------------|--------------´
#    |    saint                                                        prefix      prefix-or-not
#    |  `----------------´
#    |    |   `-------------------------------´
#    |    anthro-start    anthro-end
#    |  `-------------------------------´
#    |    germanic
#  saint-anthro-or-germanic
#                                              `-------------------´
#                                                 hydronym
#                `-------------------------------------------------´
#                        toponym
#                      `-------------------------------------------´
#                             regionym
#
# So, the first two bits are used to select which pattern the city name will
# follow. Since there are two bits for three patterns, I currently bias the choice
# in favor of "anthro" by giving it a bigger weight. I think these names are better :)
#
# For saint, we simply chose from a small list of common names, using the next available
# bits.
# 
# For germanic names, we use the same technique: this code generates valid names
# and we select one amongst them, using the next available bits.
#
# For anthro, the name is split between the start (up to the first consonnant
# cluster) and the end (starting with a vowell cluster). We want to avoid generating
# very close names, like "Ablanay", "Ablané", "Ablany", "Ablanet", etc. It would
# make cities hard to distinguish and difficult to play with (even though very
# close city names are not that rare in France).
# 
# The main reason for these close names seem to be that I have a lot of suffixes
# that means we can generate the same beginning *a lot*. To prevent that, the
# idea is to *purposefully* re-use entropy bits from the start. I told you we
# would talk about that soon :).
#
# Consider the choice of the start: given the current state, you have one in
# 2⁶=64 possibilities. Once you have chosen a start though, you need to chose
# an end. When chosing from the end, consider that the bits of entropy you
# chose give you an index in the table of all possible ends. By overlapping
# some of the bits, you make the fixed for a given start (since the start was
# already chosen). So, with the 5 lowest bits fixed, you can now only chose
# one in 32 possibilities. Since there are about a little less than 30 suffixes
# to chose from, this means that you will chose an end that contains a suffix,
# and skip over 32 end, meaning all other suffixes that are attached to the same
# middle part.
#
# In the end, a given start will never be able to chose more than 1/32 of possible
# ends, but each end can be chosen from at least one start, which brings a lot
# of variety, while diminishing the number of very similar and hard to distinguish
# names.
#
# For extensions, we want to use fresh bits, so the repartition remains similar
# independent from the main name of the city. We use 5 bits to give 1/32 chance
# to select an extension. Next, the actual extension is chosen also from 5 bits,
# between some common extensions and a few custom extensions.
#
# Given a custom extension, we add either an hydronym, a toponym or a regionym.
# These cannot reuse bits from the extension part, because selecting "sur" (or any
# other extension) requires a very specific pattern of bits that would no longer
# be random, so we wouldn't be able to generate more than a few names, even though
# we have so many possibilities in theory. That's because this time, we only generate
# them for a specific pattern of bits, not for all patterns like with anthro start.
#
# So, we need to use fresh bits for hydronyms, toponyms and regionyms. Unfortunately,
# we cannot fit all these in fresh bits, and we have to cheat a little by reusing
# *unintentionnaly* bits from the previous parts. This means that a city name can
# only be followed by the generic extensions, or by a limited number of custom
# extensions, even though again, all extensions can be chosen, just not with any
# city name. This means that a city name can only be followed by the generic
# extensions, or by a limited number of custom extensions, even though again,
# all extensions can be chosen, just not with any city name.


# OK, I promise, this is the end of the long paragraphs. Oh I wish more code
# was as well documented as this one :)


# These names are taken from actual data found in the official list of towns
# provided by Insee in "Code Officiel Géographique" from January 2022.
# You can get the CSV from https://www.insee.fr/fr/information/6051727
#
# I extracted all city names that start with "SAINT" and sorted them by order
# of frequency. In the list below, "Saint-*" appear at least 50 times in the
# list. "Sainte-*" appear at least 5 times.
saints = TownName(2, 'saints', None, [[
    TownString("Saint-Ouen"),
    TownString("Saint-Sulpice"),
    TownString("Saint-Cyr"),
    TownString("Saint-Christophe"),
    TownString("Saint-Sauveur"),
    TownString("Saint-Bonnet"),
    TownString("Saint-Rémy"),
    TownString("Saint-Vincent"),
    TownString("Saint-Denis"),
    TownString("Saint-Léger"),
    TownString("Saint-Maurice"),
    TownString("Saint-Michel"),
    TownString("Saint-Paul"),
    TownString("Saint-Aubin"),
    TownString("Saint-Andre"),
    TownString("Saint-Etienne"),
    TownString("Saint-Georges"),
    TownString("Saint-Hilaire"),
    TownString("Saint-Julien"),
    TownString("Saint-Laurent"),
    TownString("Saint-Germain"),
    TownString("Saint-Pierre"),
    TownString("Saint-Jean"),
    TownString("Saint-Martin"),

    TownString("Sainte-Suzanne"),
    TownString("Sainte-Cécile"),
    TownString("Sainte-Marguerite"),
    TownString("Sainte-Geneviève"),
    TownString("Sainte-Hélene"),
    TownString("Sainte-Radegonde"),
    TownString("Sainte-Anne"),
    TownString("Sainte-Eulalie"),
    TownString("Sainte-Gemme"),
    TownString("Sainte-Foy"),
    TownString("Sainte-Croix"),
    TownString("Sainte-Colombe"),
    TownString("Sainte-Marie"),
]])

# Here, hydronyms. Those are easy, just 8 starts and 8 ends, combined together
# and modified to follow French orthography. The starts are common roots that
# all mean something like "river".
hydronyms = combine([
    Name("Ad"),
    Name("Aul"),
    Name("Hyer"),
    Name("Hér"),
    Name("Dur"),
    Name("Dor"),
    Name("Ill"),
    Name("Ell"),
    Name("Roann"),
], [
    Name("ne"),
    Name("es"),
    Name("ance"),
    Name("ondine"),
    Name("ault"),
    Name("on"),
    Name("ez"),
    Name("ard"),
    Name("et"),
])

# In the end, we use 5 bits to chose a suffix or not, and 5 more to chose the
# suffix. Since the name variants don't require the same amount of bits, we place
# the suffix choice at the end, so it gets enough fresh bits. Since only one
# combination can lead to using hydronyms, we use bits that are just below the
# suffix bits (some are fresh)
# hydronyms take 7 bits, so 32-5-5-7 -> 15.
hydronyms = [isAllowed(s.getFor()) for s in hydronyms]
hydronyms = TownName(15, 'hydronyms', None,
        [[TownString(s) for s in filter(lambda s: s is not None, hydronyms)]])

# Here we are, anthro names. First, common starts, up to the first consonnant cluster
# In all actual city names, those are followed by a vowel.  Those are separated
# by consonnant start and vowel start, so we can distinguish them later when we
# have to chose between "-de-" or "-d’" extensions.

anthro_start_C = [
    "Qu",
    "Bl",
    "Cl",
    "Pr",
    "Cr",
    "Pl",
    "Fr",
    "Gr",
    "Tr",
    "J",
    "Br",
    "T",
    "D",
    "H",
    "N",
    "F",
    "G",
    "R",
    "P",
    "Ch",
    "S",
    "L",
    "C",
    "V",
    "B",
    "M",
]
anthro_start_V = [
    "Arc",
    "Alb",
    "Ang",
    "Ann",
    "Al",
    "Ar",
    "Etr",
    "Ech",
    "Ess",
    "And",
    "Arr",
    "Est",
    "Aur",
    "Or",
    "Am",
    "Esp",
    "Arg",
    "Ec",
    "Esc",
    "Ét",
    "Ép",
    "All",
    "Aub",
    "Av",
]

anthro_start = []
anthro_start.extend(anthro_start_V)
anthro_start.extend(anthro_start_C)

# We make that a town_name.
anthro_start = TownName(4, 'anthro_start', None, [[TownString(s) for s in anthro_start]])

# *-acum is a very common latin suffix that designate a place where people live.
# It evolved through time, and here are the most frequent derivatives nowadays.
acum_end = [
    Name("ac"),
    Name("at"),
    Name("ay"),
    Name("é"),
    Name("ey"),
    Name("y"),
    Name("as"),
    Name("eux"),
    Name("ies"),
    Name("iers"),
    Name("ez"),
]

# Other latin suffixes were used, and also evolved. Here are some of the most
# frequent endings.
latin_end = [
    Name("euil"),
    Name("ols"),
    Name("ouls"),
    Name("an"),
    Name("oc"),
    Name("elles"),
    Name("che"),
]
latin_end.extend(acum_end)

# After the roman empire Francs brought new suffixes. Some are very specific
# to north-east of France and too recognizable for a generic "French" name.
# Trying to keep only those that do not sound too distinctive.
pure_germanic_end = [
    Name("inges"),
    Name("anges"),
    Name("ingue"),
    Name("ans"),
]
germanic_end = []
germanic_end.extend(pure_germanic_end)
germanic_end.extend(acum_end)

# Now this is fun: Francs also used generic names as suffixes. These can be
# used with anthro.
# Well, the first ones like "ville" and "court" are actually latin suffixes
# that didn't evolve too much, so they didn't give too many different forms
# today.
germanic_end_name = [
    Name("ville"),
    Name("villers"),
    Name("villiers"),
    Name("court"),
    Name("bourg", gender='m'),
# The rest is a bit random, but fun to have. It's usually a building or
# geographical feature.
    Name("chaume", gender='f'),
    Name("roc", gender='m'),
    Name("fontaine", gender='f'),
    Name("chapelle", gender='f'),
    Name("église", gender='f'),
    Name("château", gender='m', origin='oil'),
    Name("bois", gender='m'),
    Name("ménil", gender='m'),
    Name("mesnil", gender='m'),
    Name("moulin", gender='m'),
    Name("maison", gender='f'),
    Name("mont", gender='m'),
    Name("val", gender='m'),
    Name("vaux", gender='m'),
    Name("four", gender='m'),
]

# So possible ending after an anthroponym
anthroponym_end = []
anthroponym_end.extend(latin_end)
anthroponym_end.extend(pure_germanic_end)
anthroponym_end.extend(germanic_end_name)

# For regionyms, we chose other suffixes.
regionym_end = [
    Name("on"),
    Name("eure"),
    Name("is"),
    Name("ière"),
    Name("al"),
    Name("calm"),
    Name("anque"),
    Name("et"),
    Name("ois"),
]

# Now real end is composed of vowels, consonants, suffix.
anthro_end = combine([
    Name("i"),
    Name("a"),
    Name("e"),
    Name("au"),
    Name("ai"),
    Name("oi"),
], [
    Name("rn"),
    Name("rs"),
    Name("ns"),
    Name("lh"),
    Name("n"),
    Name("z"),
    Name("ll"),
    Name("ss"),
    Name("r"),
    Name("gn"),
], anthroponym_end)

# Same for regionyms, but with different suffixes
regionym_end = combine([
    Name("i"),
    Name("a"),
    Name("e"),
    Name("au"),
    Name("ai"),
    Name("oi"),
], [
    Name("rn"),
    Name("rs"),
    Name("ns"),
    Name("lh"),
    Name("n"),
    Name("ll"),
    Name("ss"),
    Name("r"),
    Name("gn"),
], regionym_end)

# This is not pretty, we convert a list of Names to a list of TownStrings inside
# a TownName.
anthro_end = [isAllowed(s.getFor()) for s in anthro_end]
anthro_end = TownName(2, 'anthro_end', None,
        [[TownString(s) for s in filter(lambda s: s is not None, anthro_end)]])
anthroponyms = TownName(0, 'anthroponyms', None, [[
    TownReference('anthro_start')
], [
    TownReference('anthro_end')
]])

# Copy most of that to generate the same structure, but at a different location
# in the random number
regionym_end = [isAllowed(s.getFor()) for s in regionym_end]
regionym_end = TownName(13, 'regionym_end', None,
        [[TownString(s) for s in filter(lambda s: s is not None, regionym_end)]])
regionym_start = anthro_start.copy()
regionym_start.entropyStart = 7
regionym_start.ID = 'regionym_start'
regionyms = TownName(0, 'regionyms', None, [[
    TownReference('regionym_start')
], [
    TownReference('regionym_end')
]])

# Use two different TownNames for toponyms that start with a consonnant or a vowel
# so we can use one or the other, depending on whether we select "-de-" or "-d’".
toponym_C_start = TownName(5, 'toponym_C_start', None, [[TownString(s) for s in anthro_start_C]])
toponym_V_start = TownName(5, 'toponym_V_start', None, [[TownString(s) for s in anthro_start_V]])
toponym_end = anthro_end.copy()
toponym_end.entropyStart = 11
toponym_end.ID = 'toponym_end'
toponyms_C = TownName(0, 'toponyms-C', None, [[
    TownReference('toponym_C_start')
], [
    TownReference('toponym_end')
]])
toponyms_V = TownName(0, 'toponyms-V', None, [[
    TownReference('toponym_V_start')
], [
    TownReference('toponym_end')
]])

# Germanic names are very distinguishable, as they use very transparent words,
# usually a name and an adjective, in any order.
germanic_start_name = [
    Name("Bourg", gender='m'),
    Name("Château", gender='m', origin='oil'),
    Name("Chapelle", gender='f'),
    Name("Font", gender='f'),
    Name("Fontaine", gender='f'),
    Name("Ménil", gender='m'),
    Name("Mesnil", gender='m'),
    Name("Pont", gender='m'),
    Name("Mont", gender='m'),
    Name("Montagne", gender='f'),
    Name("Castel", gender='m', origin='oc'),
    Name("Casta", gender='m', origin='oc'),
    Name("Ville", gender='f'),
    Name("Aigue", gender='f'),
    Name("Église", gender='f'),
    Name("Roche", gender='m'),
    Name("Roque", gender='m'),
    Name("Roc", gender='m'),
    Name("Val", gender='m'),
    Name("Vau", gender='m'),
]

germanic_start_adjective = [
    Name("Belle", gender='f'),
    Name("Bel", gender='m'),
    Name("Beau", gender='m'),
    Name("Blanche", gender='f'),
    Name("Blanc", gender='m'),
    Name("Perse"),
    Name("Neu"),
    Name("Neuf", gender='m'),
    Name("Chau", gender='m'),
    Name("Chaude", gender='f'),
    Name("Vive", gender='f'),
    Name("Vif", gender='m'),
    Name("Entre"),
]

germanic_end_adjective = [
    Name("nau", origin='oc'),
    Name("belle", gender='f'),
    Name("bel", gender='m'),
    Name("beau", gender='m'),
    Name("blanche", gender='f'),
    Name("blanc", gender='m'),
    Name("perse"),
    Name("neu", origin='oil'),
    Name("neuf", gender='m', origin='oil'),
    Name("chau", gender='m'),
    Name("chaude", gender='f'),
    Name("vive", gender='f'),
    Name("vif", gender='m'),
    Name("val", gender='m'),
    Name("vaux", gender='m'),
    Name("fort", gender='m'),
    Name("forte", gender='f'),
    Name("franc", gender='m'),
    Name("franche", gender='f'),
]

# We already defined germanic_start_adjective sooner, remember, since we use
# them as suffixes also for anthro.

germanic = []
germanic.extend(combine(germanic_start_name, germanic_end_adjective))
germanic.extend(combine(germanic_start_adjective, germanic_end_name))
germanic.extend(combine(germanic_start_name, germanic_end))
# Germanic names don't respect any order, they can put someone's name *after*
# the suffix :p
# Unfortunately, this means we need to generate a new list because upper case
# letters. Work for later.
#germanic.extend(combine(germanic_start_name, anthroponyms))

germanic = [isAllowed(s.getFor()) for s in germanic]
germanic = TownName(2, 'germanic', None,
        [[TownString(s) for s in filter(lambda s: s is not None, germanic)]])

# Common extensions and custom extensions
extensions = TownName(22, 'extension', None, [[
    TownString("-sur-Mer"),
    TownString("-sous-Bois"),
    TownString("-les-Lacs"),
    TownString("-le-Lac"),
    TownString("-le-Petit"),
    TownString("-le-Grand"),
    TownString("-le-Haut"),
    TownString("-le-Bas"),
    TownString("-la-Rivière"),
    TownString("-la-Forêt"),
    TownString("-le-Vieux"),
    TownString("-la-Ville"),
    TownString("-les-Thermes"),
    TownString("-les-Bains"),
    TownString("-le-Duc"),
    TownString("-le-Comte"),
    TownReference('extensions_en'),
    TownReference('extensions_de'),
    TownReference('extensions_d'),
    TownReference('extensions_sur'),
]])
extensions_sur = TownName(0, 'extensions_sur', None, [[
    TownString("-sur-")
], [
    TownReference('hydronyms')
]])
extensions_en = TownName(0, 'extensions_en', None, [[
    TownString("-en-")
], [
    TownReference('regionyms')
]])
extensions_de = TownName(0, 'extensions_de', None, [[
    TownString("-de-")
], [
    TownReference('toponyms-C')
]])
extensions_d = TownName(0, 'extensions_d', None, [[
    TownString("-d’")
], [
    TownReference('toponyms-V')
]])
maybe_extension = TownName(27, 'maybe-extension', None, [[
    TownString("", 31),
    TownReference('extension')
]])

saint = TownName(0, 'saint', None, [[
    TownReference('saints')
], [
    TownReference('extension')
]])

anthro = TownName(0, 'anthro', None, [[
    TownReference('anthroponyms')
], [
    TownReference('maybe-extension')
]])

germanic_names = TownName(0, 'germanic-name', None, [[
    TownReference('germanic')
], [
    TownReference('maybe-extension')
]])


cities = TownName(0, 'frenchies', {'en': 'Frenchies'}, [[
    TownReference('saint'),
    TownReference('anthro', 2),
    TownReference('germanic-name'),
]])

grf.actions.append(TownNames([saints, hydronyms, germanic,
    anthro_start, anthro_end, anthroponyms,
    toponym_C_start, toponym_V_start, toponym_end, toponyms_C, toponyms_V,
    regionym_start, regionym_end, regionyms,
    extensions_en, extensions_de, extensions_d, extensions_sur, extensions, maybe_extension,
    saint, anthro, germanic_names, cities]))

grf.output()
