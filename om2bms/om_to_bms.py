import codecs
import os

from typing import Union, List, Tuple, Dict
from fractions import Fraction
from math import gcd
from functools import reduce

# import om2bms.image_resizer
from om2bms.data_structures import OsuMania
from om2bms.data_structures import OsuTimingPoint
from om2bms.data_structures import OsuManiaNote
from om2bms.data_structures import OsuManiaLongNote
from om2bms.data_structures import OsuBGSoundEvent
from om2bms.data_structures import BMSMeasure
from om2bms.data_structures import calculate_bpm
from om2bms.osu import OsuBeatmapReader
from om2bms.exceptions import OsuGameTypeException
from om2bms.exceptions import OsuParseException
from om2bms.exceptions import BMSMaxMeasuresException


class OsuManiaToBMSParser:
    """
    Where the magic happens.
    """
    _ms_to_inverse_note_values = {}
    _mania_note_to_channel = {
        0: 16,
        1: 11,
        2: 12,
        3: 13,
        4: 14,
        5: 15,
        6: 18,
        7: 19
    }
    _mania_ln_to_channel = {
        0: 56,
        1: 51,
        2: 52,
        3: 53,
        4: 54,
        5: 55,
        6: 58,
        7: 59
    }
    _convertion_options = {}
    _out_file = None

    def __init__(self, in_file, out_dir, filename):
        self.reset()
        self.bg_filename = None
        try:
            self.beatmap = OsuBeatmapReader(in_file)
        except OsuGameTypeException:
            return
        except OsuParseException as e:
            print(e)
            return
        print("\tConverting " + filename)

        self.beatmap = self.beatmap.get_parsed_beatmap()

        bms_filename = self.beatmap.title + " " + self.beatmap.version + ".bms"
        output = os.path.join(out_dir, bms_filename)
        OsuManiaToBMSParser._out_file = codecs.open(output, "w", "shiftjis", errors="replace")

        self.write_buffer(self.create_header())
        music_start_param = self.music_start_time(self.beatmap)
        self.get_next_measure(music_start_param[0], music_start_param[1], self.beatmap)

        OsuManiaToBMSParser._out_file.close()

        file = os.path.dirname(in_file)
        if OsuManiaToBMSParser._convertion_options["BG"] and self.beatmap.stagebg is not None and \
                os.path.isfile(os.path.join(file, self.beatmap.stagebg)):
            # om2bms.image_resizer.black_background_thumbnail(os.path.join(file, self.beatmap.stagebg))
            self.bg_filename = os.path.join(file, self.beatmap.stagebg)

    def get_bg(self):
        """
        Returns bg filename
        """
        return self.bg_filename

    def reset(self):
        """
        Resets class variables
        """
        OsuManiaToBMSParser._out_file = None
        OsuBeatmapReader._latest_tp_index = 0
        OsuBeatmapReader._latest_noninherited_tp_index = 0
        OsuBeatmapReader._sample_index = 1
        BMSMeasure._hit_sounds = OsuManiaToBMSParser._convertion_options["HITSOUND"]

    def write_buffer(self, buffer: Union[BMSMeasure, List[str]]):
        """
        Writes to file. \n between each element in buffer if list
        """
        if buffer is None:
            return
        elif isinstance(buffer, BMSMeasure):
            for line in buffer.lines:
                OsuManiaToBMSParser._out_file.write(str(line))
        else:
            for line in buffer:
                OsuManiaToBMSParser._out_file.write(line)
                OsuManiaToBMSParser._out_file.write("\n")
        OsuManiaToBMSParser._out_file.write("\n")

    def expansion_wrapper(self, n, ms_per_measure) -> Fraction:
        """
        Approximates n, where 0 < n < 1, to p/q where q=2^i or 3 * 2^i up to q=192.
        """
        def expander(n, ms_per_measure, meter, end):
            """
            Generalized expander for non upper number of 3 or 4 measures.
            """
            def within_offset(num, sum__, offset):
                """
                return true if within
                """
                return int(ms_per_measure * num) - 1 < ms_per_measure * (sum__ + offset) < int(ms_per_measure * num) + 1
            done = False
            denominator = meter
            sum_ = Fraction(1, meter)
            while sum_ + Fraction(1, denominator) < n:
                sum_ += Fraction(1, denominator)
            iterations = 0
            while iterations < 6:
                if within_offset(n, sum_, 0) or round(n, 5) == round(float(sum_), 5):
                    done = True
                    break
                if float(sum_) > n:
                    sum_ -= Fraction(1, denominator)
                    denominator *= 2
                elif float(sum_) < n:
                    sum_ += Fraction(1, denominator)
                    denominator *= 2
                iterations += 1
            # pad with maxs
            while not done:
                if within_offset(n, sum_, 0):
                    break
                prev_error = abs(n - sum_)
                if sum_ > n:
                    if within_offset(n, sum_, -Fraction(1, end)):
                        sum_ -= Fraction(1, end)
                        break
                    elif abs(n - (prev_error - Fraction(1, end))) > sum_ - Fraction(1, end):
                        break
                    sum_ -= Fraction(1, end)
                elif sum_ < n:
                    if within_offset(n, sum_, Fraction(1, end)):
                        sum_ += Fraction(1, end)
                        break
                    elif abs(n - (prev_error + Fraction(1, end))) < sum_ - Fraction(1, end):
                        break
                    sum_ += Fraction(1, end)
            return (abs(n - sum_), sum_)

        error2 = expander(n, ms_per_measure, 4, 128)
        error3 = expander(n, ms_per_measure, 3, 192)
        error = error2 if error2[0] < error3[0] else error3
        time_value = error[1]
        if time_value == 1:
            return Fraction(0, 1)
        if time_value != 0:
            self.add_to_mtnv(time_value * ms_per_measure, time_value)
        return error[1]

    def music_start_time(self, beatmap: OsuMania):
        """
        Returns the measure offset and ms of first measure. Calls BMSMeasure and BMSMainDataLine on the BGM start line.
        """
        first_object = beatmap.objects[0]
        first_timing = beatmap.timing_points[0]
        ms_per_measure = first_timing.meter * first_timing.ms_per_beat
        use_obj = False
        if first_object.time < first_timing.time:
            start_time = first_object.time
            use_obj = True
        else:
            start_time = first_timing.time
        # find first obj on down
        if use_obj:
            i = 0
            while beatmap.objects[i].time < first_timing.time:
                i += 1
            start_time = beatmap.objects[i].time
        while start_time - ms_per_measure > 0:
            start_time -= ms_per_measure

        if start_time > 0:
            start_time_offset = ms_per_measure - start_time
            if use_obj:
                start_time_offset = ms_per_measure - start_time
        else:
            start_time_offset = abs(start_time)

        mus_start_at_001 = True if first_object.time + ms_per_measure < ms_per_measure else False

        sto_fraction = start_time_offset / ms_per_measure
        time_value_ratio = self.expansion_wrapper(sto_fraction, ms_per_measure)
        if time_value_ratio == 0 and mus_start_at_001:
            bms_measure = BMSMeasure("001")
            measure_start = 1
            bms_measure.create_data_line("01", time_value_ratio.denominator, [(time_value_ratio.numerator, "01")])
        else:
            if mus_start_at_001:
                bms_measure = BMSMeasure("001")
                measure_start = 1
            else:
                bms_measure = BMSMeasure("000")
                if time_value_ratio == 0:
                    measure_start = 0
                else:
                    measure_start = 1
            bms_measure.create_data_line("01", time_value_ratio.denominator, [(time_value_ratio.numerator, "01")])

        measure_offset = measure_start
        if beatmap.objects[0].time > start_time:
            while not start_time >= beatmap.objects[0].time:
                start_time += ms_per_measure
                measure_offset += 1
        else:
            measure_offset = 0 if measure_start == 0 else 1

        if first_timing.meter != 4:
            if bms_measure.measure_number == "000":
                bms_measure.create_measure_length_change(first_timing.meter / 4)
            elif bms_measure.measure_number == "001":
                bms_measure0 = BMSMeasure("000")
                bms_measure0.create_measure_length_change(first_timing.meter / 4)
                self.write_buffer(bms_measure0)
                bms_measure.create_measure_length_change(first_timing.meter / 4)
        self.write_buffer(bms_measure)
        if first_timing.meter != 4:
            for i in range(1, measure_offset):
                bms_measure = BMSMeasure(str(i).zfill(3))
                bms_measure.create_measure_length_change(first_timing.meter / 4)
                self.write_buffer(bms_measure)

        first_measure_time = int(start_time)
        if first_object.time < first_measure_time - 1:
            measure_offset -= 1
            first_measure_time -= ms_per_measure
        if time_value_ratio == 0 and not mus_start_at_001:
            while not self.within_2_ms(start_time, measure_offset * ms_per_measure):
                measure_offset += 1

        self.initialize_mtnv()
        return (measure_offset, first_measure_time)

    def get_next_measure(self, starting_measure: int, starting_ms: int, beatmap: OsuMania):
        """
        Retrieves information for each measure.
        """
        def add_to_measure(current_measure_, hitobjj_):
            """
            Adds hitobj to measure
            """
            if isinstance(hitobjj_, OsuManiaNote):
                column = hitobjj_.mania_column
                bmscolumn = OsuManiaToBMSParser._mania_note_to_channel[column]
                if bmscolumn not in current_measure_:
                    current_measure_[OsuManiaToBMSParser._mania_note_to_channel[column]] = [hitobjj_]
                else:
                    current_measure_[OsuManiaToBMSParser._mania_note_to_channel[column]].append(hitobjj_)
            elif isinstance(hitobjj_, OsuManiaLongNote):
                column = hitobjj_.mania_column
                bmscolumn = OsuManiaToBMSParser._mania_ln_to_channel[column]
                if bmscolumn not in current_measure_:
                    current_measure_[OsuManiaToBMSParser._mania_ln_to_channel[column]] = [hitobjj_]
                else:
                    current_measure_[OsuManiaToBMSParser._mania_ln_to_channel[column]].append(hitobjj_)
            elif isinstance(hitobjj_, OsuBGSoundEvent):
                column = 1
                if column not in current_measure_:
                    current_measure_[column] = [hitobjj_]
                else:
                    current_measure_[column].append(hitobjj_)
            elif isinstance(hitobjj_, OsuTimingPoint):
                if 0 not in current_measure_:
                    current_measure_[0] = [hitobjj_]
                else:
                    current_measure_[0] = [hitobjj_]

        current_measure = {}

        current_time_in_ms = starting_ms
        truncate_measure = False
        first_timing = beatmap.noninherited_tp[0]
        ms_per_measure = first_timing.ms_per_beat * first_timing.meter
        measure_number = starting_measure
        most_recent_tp = first_timing
        i = 0
        while i < len(beatmap.objects):
            hitobj = beatmap.objects[i]

            if hitobj.time < int(current_time_in_ms + ms_per_measure) - 1 and not truncate_measure:
                if not isinstance(hitobj, OsuTimingPoint):
                    add_to_measure(current_measure, hitobj)
                elif isinstance(hitobj, OsuTimingPoint) and self.within_2_ms(current_time_in_ms, hitobj.time):
                    most_recent_tp = hitobj
                    ms_per_measure = hitobj.ms_per_beat * hitobj.meter
                    current_time_in_ms = hitobj.time
                    add_to_measure(current_measure, hitobj)
                else:
                    truncate_measure = True
            else:  # hitobj.starttime >= current_time_in_ms + ms_per_measure:
                if truncate_measure:
                    if hitobj.time - current_time_in_ms < 0:
                        truncation_frac = (hitobj.time - (current_time_in_ms - ms_per_measure)) / ms_per_measure
                    else:
                        truncation_frac = (hitobj.time - current_time_in_ms) / ms_per_measure
                    truncation_float = float(self.expansion_wrapper(truncation_frac, ms_per_measure))
                    bmsmeasure = self.create_measure(current_measure, most_recent_tp, current_time_in_ms,
                                                     str(measure_number).zfill(3),
                                                     truncation_float)
                    truncate_measure = False
                    self.write_buffer(bmsmeasure)
                    self.initialize_mtnv()
                    measure_number += 1
                    most_recent_tp = hitobj
                    ms_per_measure = hitobj.ms_per_beat * hitobj.meter
                    current_time_in_ms = hitobj.time
                    current_measure = {}
                    add_to_measure(current_measure, hitobj)

                    i += 1
                    continue
                else:
                    bmsmeasure = self.create_measure(current_measure, most_recent_tp, current_time_in_ms,
                                                     str(measure_number).zfill(3), 0)

                self.write_buffer(bmsmeasure)

                # move to next measure with hitnotes
                while not self.within_2_ms(current_time_in_ms, hitobj.time):
                    measure_number += 1
                    current_time_in_ms += ms_per_measure

                    if hitobj.time < int(current_time_in_ms + ms_per_measure) - 1:
                        if isinstance(hitobj, OsuTimingPoint) and not self.within_2_ms(current_time_in_ms, hitobj.time):
                            truncate_measure = True
                        elif isinstance(hitobj, OsuTimingPoint) and self.within_2_ms(current_time_in_ms, hitobj.time):
                            most_recent_tp = hitobj
                            self.initialize_mtnv()
                            ms_per_measure = hitobj.ms_per_beat * hitobj.meter
                            current_time_in_ms = hitobj.time
                        current_measure = {}
                        add_to_measure(current_measure, hitobj)
                        break

                if measure_number > 999:
                    raise BMSMaxMeasuresException("Exceeded 999 measures")

            if not truncate_measure:
                i += 1

        # for the last measure (outside loop)
        bmsmeasure = self.create_measure(current_measure, most_recent_tp, current_time_in_ms,
                                         str(measure_number).zfill(3), 0)
        self.write_buffer(bmsmeasure)

    def initialize_mtnv(self) -> None:
        """
        Reset _ms_to_inverse_note_values (bpm changes)
        """
        OsuManiaToBMSParser._ms_to_inverse_note_values = {}

    def add_to_mtnv(self, key: int, value: Fraction):
        """
        Wrapper to add into mtnv
        """
        OsuManiaToBMSParser._ms_to_inverse_note_values[key] = value
        OsuManiaToBMSParser._ms_to_inverse_note_values[key - 1] = value
        OsuManiaToBMSParser._ms_to_inverse_note_values[key + 1] = value

    def within_2_ms(self, base, n) -> bool:
        """
        True if n is close enough to base
        """
        return base - 2 <= n <= base + 2

    def create_measure(self, current_measure, timing_point: OsuTimingPoint, measure_start: float,
                       measure_number: str, measure_truncation: float):
        """
        Creates a BMSMeasure containing linedata
        """
        def get_numerator_with_gcd(fraction, gcd_) -> int:
            """
            Returns numerator of fraction with denom of gcd
            """
            if fraction[1] == gcd_:
                return fraction[0]
            elif fraction[1] < gcd_:
                fraction[0] *= 2
                fraction[1] *= 2
                return get_numerator_with_gcd(fraction, gcd_)
            else:  # fraction[1] > gcd: (switch from
                if fraction[1] % 3 == 0:
                    fraction[0] //= 3
                    fraction[1] //= 3
                else:
                    fraction[0] //= 4
                    fraction[0] *= 3
                    fraction[1] //= 4
                    fraction[1] *= 3
                return get_numerator_with_gcd(fraction, gcd_)

        #  if the measure is empty skip
        if len(current_measure) == 0:
            return

        bms_measure = BMSMeasure(measure_number)
        if timing_point.meter != 4:
            bms_measure.create_measure_length_change(timing_point.meter / 4)
            self.initialize_mtnv()
        elif measure_truncation != 0:
            bms_measure.create_measure_length_change(measure_truncation)
        ms_per_measure = timing_point.meter * timing_point.ms_per_beat

        if len(current_measure) != 0:
            for key in sorted(current_measure.keys()):
                # get notes from column/key and put them into a line
                denoms = []
                locations = []  # temp
                locations_ = []  # to be passed into bmsmaindataline
                for note in current_measure[key]:
                    # if first_note:
                    time_value_ms = round(abs(measure_start - note.time), 5)
                    if self.within_2_ms(time_value_ms, 0):
                        time_value_ratio = Fraction(0, 1)
                    elif int(time_value_ms) in OsuManiaToBMSParser._ms_to_inverse_note_values:
                        time_value_ratio = OsuManiaToBMSParser._ms_to_inverse_note_values[int(time_value_ms)]
                    else:
                        time_value_ratio = self.expansion_wrapper(time_value_ms / ms_per_measure, ms_per_measure)
                    denoms.append(time_value_ratio.denominator)
                    locations.append(([time_value_ratio.numerator, time_value_ratio.denominator], note))

                if key == 0 and not current_measure[key][0].inherited:
                    new_bpm = calculate_bpm(current_measure[key][0])
                    if new_bpm <= 255 and isinstance(new_bpm, int):
                        bms_measure.create_bpm_change_line(new_bpm)
                    else:
                        bms_measure.create_bpm_extended_change_line(new_bpm, self.beatmap.float_bpm)
                elif key == 1:
                    locations_ = sorted(locations, key=lambda x: x[0])
                    for i in range(len(locations)):
                        bms_measure.create_data_line(str(key).zfill(2), locations_[i][0][1],
                                                     [(locations_[i][0][0], locations_[i][1])])
                else:
                    # make all denomaintors = to gcd
                    gcd_ = reduce(lambda a, b: a * b // gcd(a, b), denoms)
                    for list_ in locations:
                        locations_.append((get_numerator_with_gcd(list_[0], gcd_), list_[1]))
                    bms_measure.create_data_line(str(key).zfill(2), gcd_, sorted(locations_, key=lambda x: x[0]))

            return bms_measure

    def create_header(self) -> List[str]:
        """
        Makes everything before maindata field
        """
        # HEADER FIELD
        buffer = list([""])
        buffer.append("*---------------------- HEADER FIELD")
        buffer.append("")
        buffer.append("#PLAYER 1")
        buffer.append("#GENRE " + self.beatmap.creator)
        buffer.append("#TITLE " + self.beatmap.title_unicode)
        buffer.append("#SUBTITLE " + self.beatmap.version)
        buffer.append("#ARTIST " + self.beatmap.artist_unicode)
        # buffer.append("#SUBARTIST " + beatmap.artist)
        buffer.append("#BPM " + str(int(calculate_bpm(self.beatmap.timing_points[0]))))
        buffer.append("#DIFFICULTY " + "5")
        buffer.append("#RANK " + "3")
        buffer.append("")
        for hs in self.beatmap.hitsound_names:
            buffer.append("#WAV" + hs[0] + " " + str(hs[1]))
        buffer.append("")
        if self.beatmap.stagebg is not None and OsuManiaToBMSParser._convertion_options["BG"]:
            buffer.append("#BMP01 " + self.beatmap.stagebg)
            buffer.append("")
        if len(self.beatmap.float_bpm) > 0:
            for e in self.beatmap.float_bpm:
                buffer.append("#BPM" + str(e[0]) + " " + str(e[1]))
            buffer.append("")
        # BGM FIELD
        buffer.append("*---------------------- EXPANSION FIELD")
        buffer.append("")

        buffer.append("*---------------------- MAIN DATA FIELD")
        buffer.append("")
        buffer.append("")
        if self.beatmap.stagebg is not None and OsuManiaToBMSParser._convertion_options["BG"]:
            buffer.append("#00004:01")

        return buffer
