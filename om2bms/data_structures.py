from typing import Union, List, Tuple, Dict

from om2bms.exceptions import BMSHitSoundException


class OsuMania:
    """Class containing information from .osu file"""

    def __init__(self):
        # general
        self.audio_filename = None
        self.audio_lead_in = None
        self.special_style = None  # o!m scrollkey y/n
        self.sample_set = None
        # metadata
        self.title = None
        self.title_unicode = None
        self.artist = None
        self.artist_unicode = None
        self.creator = None
        self.version = None
        self.source = None
        self.beatmap_id = None
        self.stagebg = None

        self.key_count = None  # originally circle size
        self.od = None

        self.float_bpm = []
        self.timing_points = []
        self.hit_objects = []
        self.sample_objects = []
        self.objects = []
        self.sample_filenames = []
        self.filename_to_sample = {}

        self.noninherited_tp = []

        self.hitsounds = {}
        self.hitsound_names = []

    def parse_float_bpm(self, bpm: float):
        """
        Parse float bpm into (INDEX, BPM)
        """
        for e in self.float_bpm:
            if e[1] == bpm:
                return
        self.float_bpm.append((get_current_hs_count(len(self.float_bpm) + 1), bpm))


class OsuTimingPoint:
    """Contains information for a particular timing point"""
    def __init__(self):
        self.time = None
        self.ms_per_beat = None
        self.meter = None
        self.sample_set = None
        self.sample_index = None
        self.volume = None  # not supported in lr2
        self.inherited = None
        self.kiai_mode = None  # not needed

        self.ms_per_measure = None

        self.sort_type = 0  # for sorting

    def __repr__(self):
        return str(self.time) + "ms at " + str(self.ms_per_beat) + "ms_per_beat"

    def __eq__(self, other):
        return self.ms_per_beat == other.ms_per_beat and self.meter == other.meter and \
               self.sample_set == other.sample_set and self.sample_index == other.sample_index


class SoundEvent:
    """Just to contain build_filename"""
    _hit_sound_key = {
        0: "none",
        1: "normal",
        2: "whistle",
        4: "finish",
        8: "clap"}
    _sample_set_key = {
        1: "normal",
        2: "soft",
        3: "drum"}

    def __init__(self):
        self.index = None

        self.sort_type = 1  # for sorting

    def build_filename(self, custom_index: int, sample_set: int, hitsound: int) -> str:
        """
        filename = {sample set}-hit{sound}{index}.wav
        """
        index = "" if custom_index == 1 else str(custom_index)
        return str(HitSound._sample_set_key[sample_set]) + "-hit" + str(HitSound._hit_sound_key[hitsound]) \
            + index + ".wav"

    def get_info(self):
        """
        For list iterating purposes
        """
        return (self.index, self)


class OsuBGSoundEvent(SoundEvent):
    """
    For when sample plays in the background that is not the audiofile
    """
    def __init__(self, time, filename, sample_num):
        super().__init__()
        self.time = time
        self.filename = filename
        self.index = get_current_hs_count(sample_num)

    def __str__(self):
        return self.filename


class HitSound(SoundEvent):
    """
    hit_sound key
    """
    def __init__(self, hitsound: int, tp: Union[OsuTimingPoint, None], sample_set: int, custom_index:
                 int, filename: str, sample_num: int):
        super().__init__()
        self.timing_point = tp
        self.hitsound = hitsound
        self.sample_set = sample_set
        self.custom_index = custom_index if custom_index != 0 else self.timing_point.sample_index
        self.filename = filename if filename != "" else self.build_filename(self.custom_index, self.sample_set,
                                                                            self.hitsound)
        self.addition_set = self.sample_set  # needed?
        self.index = get_current_hs_count(sample_num)

    def __str__(self):
        return self.filename


class OsuHitObject:
    """
    Hitobject class

    mania_column:
    scroll = 0
    key1 = 1
    key2 = 2
    ...
    key7 = 7
    """
    def __init__(self):
        self.time = None
        self.time_value = None
        self.new_combo = False

        self.hit_sound = None
        self.mania_column = None

        self.timing_point = None

        self.sort_type = 1  # for sorting


class OsuManiaNote(OsuHitObject):
    """Single o!m note"""
    def __init__(self):
        super().__init__()

    def get_type_value(self):
        """
        Returns type value of note
        """
        return 5 if self.new_combo else 1

    def __str__(self):
        return "NOTE: t=" + str(self.time) + "|c=" + str(self.mania_column)

    def __repr__(self):
        return "NOTE: t=" + str(self.time) + "|c=" + str(self.mania_column)


class OsuManiaLongNote(OsuHitObject):
    """o!m noodle"""
    def __init__(self, end_time=None):
        super().__init__()
        self.end_time = end_time

    def get_type_value(self):
        """
        Returns type value of note
        """
        return 132 if self.new_combo else 128

    def __str__(self):
        return "LN: t=" + str(self.time) + "|t2=" + str(self.end_time) + "|c=" + str(self.mania_column)

    def __repr__(self):
        return "LN: t=" + str(self.time) + "|t2=" + str(self.end_time) + "|c=" + str(self.mania_column)


class BMSMeasure:
    """
    Contains info for all lines in the same measure
    """
    _hit_sounds = True

    def __init__(self, measure_number: str):
        self.measure_number = measure_number
        self.lines = []

    def __str__(self):
        """
        Returns in format XXXYY:NN
        """
        ret = ""
        for line in self.lines:
            ret += ("#" + str(self.measure_number) + str(line.channel) + ":" + str(line.data) + "\n")
        return str(ret)

    def create_data_line(self, channel: str, bits: int,
                         locations: List[Tuple[List[int], Union[OsuHitObject, OsuBGSoundEvent, str]]]):
        """
        Wrapper for creating data_line
        """
        chars = {}
        locations_ = []
        for e in locations:
            locations_.append(e[0])
            if isinstance(e[1], OsuHitObject):
                if e[1].hit_sound is not None and BMSMeasure._hit_sounds:
                    chars[e[0]] = e[1].hit_sound.index
                    if chars[e[0]] == "":
                        chars[e[0]] = "ZZ"
                else:
                    chars[e[0]] = "ZZ"
            elif isinstance(e[1], OsuBGSoundEvent):
                chars[e[0]] = e[1].index
            else:
                chars[e[0]] = e[1]
        self.lines.append(BMSMainDataLine(channel, bits, chars, locations_, self.measure_number))

    def create_measure_length_change(self, num_of_beats):
        """
        Channel 2 measure length change
        """
        # beats_over_four = float(num_of_beats / 4)
        self.lines.append(BMSMainDataLine("02", 1, {0: str(num_of_beats)}, [0], self.measure_number))

    def create_bpm_change_line(self, bpm: int):
        """
        Channel 3 bpm change (ints only), 01 - FF(255)
        """
        self.lines.append(BMSMainDataLine("03", 1, {0: str(hex(bpm))[2:4].upper().zfill(2)}, [0], self.measure_number))

    def create_bpm_extended_change_line(self, bpm: Union[int, float], float_bpm_arr):
        """
        Channel 8 bpm change. Takes real number.
        """
        tup = (None, None)
        for e in float_bpm_arr:
            if e[1] == bpm:
                tup = e
        self.lines.append(BMSMainDataLine("08", 1, {0: str(tup[0])}, [0], self.measure_number))


class BMSMainDataLine:
    """
    Single line within the
    """
    def __init__(self, channel: str, bits: int, chars: Dict[int, str], locations: List[int], measure_number: str):
        self.channel = channel
        self.data = self._build_data(bits, chars, locations)
        self.measure_number = measure_number

    def _build_data(self, bits: int, chars: Dict[int, str], locations: List[int]) -> str:
        """
        Builds the components of line
        """
        ret = ""
        location_index = 0
        for i in range(bits):
            if i == locations[location_index]:
                ret += chars[i]
                if not location_index >= len(locations) - 1:
                    location_index += 1
            else:
                ret += "00"
        return ret

    def __str__(self):
        """
        Returns in format XXXYY:NN
        """
        ret = "#" + str(self.measure_number) + str(self.channel) + ":" + str(self.data) + "\n"
        return str(ret)


def get_current_hs_count(sample_num: int) -> str:
    """
    Returns the HitSound instance's base36 hitsound identifier.
    """
    def base36encode(number, alphabet='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ') -> str:
        """Converts an integer to a base36 string.
        Adapted from Wikipedia.
        """
        base36 = ''
        if 0 <= number < len(alphabet):
            return alphabet[number]
        while number != 0:
            number, i = divmod(number, len(alphabet))
            base36 = alphabet[i] + base36
        return base36

    ret = base36encode(sample_num)
    if len(ret) == 1:
        ret = "0" + ret
    elif len(ret) > 2 or ret == "ZZ":
        # raise BMSHitSoundException("Too many hitsounds.")
        print("Too many hitsounds - continuing")
        return ""
    return ret


def calculate_bpm(timing_point: OsuTimingPoint) -> Union[int, float]:
    """
    Calculates bpm and rounds if decimals 1-4 are 0 or 9
    """
    def get_nth_decimal(number, n):
        """
        Returns nth decimal of number
        """
        return int(number * (10 ** n)) % 10

    bpm_float = 1 / ((timing_point.ms_per_beat / 1000) / 60)
    ncount = count = 0
    for i in range(1, 5):
        if get_nth_decimal(bpm_float, i) == 0:
            count += 1
        elif get_nth_decimal(bpm_float, i) == 9:
            ncount += 1
    if count == 4:
        return int(bpm_float)
    elif ncount == 4:
        return round(bpm_float)
    else:
        return int(bpm_float * (10 ** 4)) / 10000
