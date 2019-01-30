import copy
import codecs

from om2bms.data_structures import OsuMania
from om2bms.data_structures import OsuTimingPoint
from om2bms.data_structures import OsuBGSoundEvent
from om2bms.data_structures import HitSound
from om2bms.data_structures import OsuManiaNote
from om2bms.data_structures import OsuManiaLongNote
from om2bms.data_structures import calculate_bpm
from om2bms.exceptions import OsuGameTypeException
from om2bms.exceptions import OsuParseException


class OsuBeatmapReader:
    """Parses information from .osu file to OsuMania class. """
    _latest_tp_index = 0
    _latest_noninherited_tp_index = 0
    _sample_index = 1

    def __init__(self, input_file):
        self.osumania_beatmap = OsuMania()
        self.parse(input_file, self.osumania_beatmap)

    def get_parsed_beatmap(self):
        """
        Returns the parsed beatmap.
        """
        return self.osumania_beatmap

    def parse(self, input_file, osumania_beatmap):
        """
        Parses beatmap
        """
        def header_hitobjects(line, beatmap):
            """
            Parses header HitObjects
            """
            def decode_bits(num: int) -> int:
                """
                For when sample_set plays > 1 hitsound at the same time. Take only the largest
                """
                if num > 8:
                    return 8
                elif num > 4:
                    return 4
                elif num > 2:
                    return 2
                else:
                    return 1
            ln_buffer = None
            type_ln = False
            line_separated = parse_symbol_separated(line, ',')
            if len(line_separated) < 4:
                OsuParseException("HitObject Error: Invalid Syntax")
            hit_object_type = line_separated[3]
            hit_object_arg = parse_symbol_separated(line_separated[-1], ':')

            hit_object = None
            if hit_object_type == "1" or hit_object_type == "5":  # single note
                hit_object = OsuManiaNote()
                if hit_object_type == "5":
                    hit_object.new_combo = True
            elif hit_object_type == "2" or hit_object_type == "6":  # o!std slider
                return
            elif hit_object_type == "8" or hit_object_type == "12":  # o!std spinner
                return
            elif hit_object_type == "132" or hit_object_type == "128":  # o!m longnote
                type_ln = True
                hit_object = OsuManiaLongNote(int(hit_object_arg[0]))
                ln_buffer = OsuManiaLongNote(int(hit_object_arg[0]))
                if hit_object_type == "128":
                    hit_object.new_combo = True
            else:
                raise OsuParseException("HitObject Error: type " + hit_object_type + " not found in " + line)

            if beatmap.key_count == 7:
                hit_object.mania_column = (int(line_separated[0]) // (512 // beatmap.key_count)) + 1 \
                    if line_separated[0] != "0" else 0
            elif beatmap.key_count == 8:
                hit_object.mania_column = (int(line_separated[0]) // (512 // beatmap.key_count))
            hit_object.hit_sound = int(line_separated[4])
            hit_object.time = int(line_separated[2])

            if OsuBeatmapReader._latest_tp_index < len(beatmap.timing_points) - 1 and \
                    beatmap.timing_points[OsuBeatmapReader._latest_tp_index + 1].time <= hit_object.time:
                OsuBeatmapReader._latest_tp_index += 1

            hitsound_int = int(line_separated[4]) if int(line_separated[4]) in [0, 1, 2, 4, 8] else \
                decode_bits(int(line_separated[4]))
            timing_point = beatmap.timing_points[OsuBeatmapReader._latest_tp_index]
            if type_ln:
                filename = "" if len(hit_object_arg) < 5 else hit_object_arg[5].strip()
                sample_set = int(hit_object_arg[1])
            else:
                filename = "" if len(hit_object_arg) < 4 else hit_object_arg[4].strip()
                sample_set = int(hit_object_arg[0])

            if filename == "" and hitsound_int == 0:
                hitsound = None
            else:
                if sample_set == 0:
                    sample_set = timing_point.sample_set
                custom_index = int(hit_object_arg[3]) if type_ln else int(hit_object_arg[2])
                hs_id = (hitsound_int, sample_set, custom_index, filename)
                if hs_id not in beatmap.hitsounds:
                    hitsound = HitSound(hitsound_int, timing_point, sample_set, custom_index, filename, OsuBeatmapReader._sample_index)
                    OsuBeatmapReader._sample_index += 1
                    beatmap.hitsounds[hs_id] = hitsound
                    beatmap.hitsound_names.append(hitsound.get_info())
                else:
                    hitsound = beatmap.hitsounds[hs_id]

            hit_object.hit_sound = hitsound
            hit_object.timing_point = timing_point
            beatmap.hit_objects.append(hit_object)
            if ln_buffer is not None:
                ln_buffer.time = hit_object.end_time
                ln_buffer.end_time = hit_object.end_time
                ln_buffer.mania_column = hit_object.mania_column
                beatmap.hit_objects.append(ln_buffer)

        def header_timingpoints(line, beatmap):
            """
            Parses header TimingPoints:
            """
            def get_ms_per_beat(ms, _beatmap):
                """
                Takes care of negative values found in Timing Points
                """
                if ms >= 0:
                    return ms
                else:
                    for _tp in reversed(_beatmap.timing_points):
                        if not _tp.inherited:
                            return (abs(ms) / 100) * _tp.ms_per_beat
                    raise OsuParseException("Non inherited BPM not found. Timing points are broken")

            line_separated = parse_symbol_separated(line, ',')
            if len(line_separated) != 8:
                raise OsuParseException("TimingPoint Error: Invalid Syntax")
            tp = OsuTimingPoint()
            tp.time = int(float(line_separated[0]))
            tp.inherited = True if int(line_separated[6]) == 0 else False
            tp.meter = int(line_separated[2])
            tp.sample_set = int(line_separated[3])
            tp.sample_index = int(line_separated[4])
            tp.volume = int(line_separated[5])
            tp.kiai_mode = False if line_separated[7] == 0 else True
            # delete previous tp if new tp causes old tp to last only a few ms
            if len(beatmap.timing_points) > 0 and tp.time <= beatmap.timing_points[-1].time + 2 and not tp.inherited:
                del beatmap.timing_points[-1]
            if tp.inherited:
                tp.ms_per_beat = get_ms_per_beat(float(line_separated[1]), beatmap)
                prev_tp = beatmap.timing_points[-1]
                if len(beatmap.timing_points) > 0 and tp.time <= prev_tp.time + 1 and \
                        tp.sample_set != prev_tp.sample_set and tp.sample_index != prev_tp.sample_index:
                    del beatmap.timing_points[-1]
            else:
                tp.ms_per_beat = float(line_separated[1])
                bpm = calculate_bpm(tp)
                if isinstance(bpm, float) or bpm > 255:
                    beatmap.parse_float_bpm(bpm)
                if len(beatmap.timing_points) > 0 and tp.time <= beatmap.noninherited_tp[-1].time + 1:
                    del beatmap.noninherited_tp[-1]
                beatmap.noninherited_tp.append(tp)
            beatmap.timing_points.append(tp)

        def header_events(line, beatmap):
            """
            Parses header Events
            """
            line_separated = parse_symbol_separated(line, ',')
            if len(line_separated) < 1:
                OsuParseException("Events Error: Invalid Syntax")
            event = {}
            if line_separated[0] == "Sample":
                if len(line_separated) != 5:
                    raise OsuParseException("Events Error: Invalid Syntax")
                time = int(line_separated[1])
                filename = str(line_separated[3][1:-1])
                if filename not in beatmap.filename_to_sample.keys():
                    beatmap.sample_filenames.append(filename)
                    sample = OsuBGSoundEvent(time, filename, OsuBeatmapReader._sample_index)
                    OsuBeatmapReader._sample_index += 1
                    beatmap.filename_to_sample[filename] = sample
                    beatmap.sample_objects.append(sample)
                    beatmap.hitsound_names.append(sample.get_info())
                else:
                    sample = beatmap.filename_to_sample[filename]
                    new_sample = copy.deepcopy(sample)
                    new_sample.time = time
                    beatmap.sample_objects.append(new_sample)

            # elif line_separated[0] == "Video":
            #     if len(line_separated) != 3:
            #         OsuParseException("Events Error: Invalid Syntax")
            #         pass
            #     event["Time"] = int(line_separated[1])
            #     event["FilePath"] = line_separated[2][1:-1]
            elif len(line_separated) <= 5 and line_separated[0] == "0":
                temp = line_separated[2]
                temp = temp.replace('"', '').strip()
                sep = temp.split('.')
                if len(sep) == 2:
                    beatmap.stagebg = sep[0] + "." + sep[1]

        def header_difficulty(line, beatmap):
            """
            Parses the header Difficulty
            """
            line_property = get_line_property(line)
            if line_property[0] == "CircleSize":
                keycount = int(line_property[1])
                if keycount == 7 or keycount == 8:
                    beatmap.key_count = keycount
                else:
                    raise OsuParseException("Only 7k/8k files are supported!")
            elif line_property[0] == "HPDrainRate":
                pass
            elif line_property[0] == "OverallDifficulty":
                beatmap.od = float(line_property[1])
            elif line_property[0] == "ApproachRate":
                pass
            else:
                OsuParseException("Attribute Error: " + line_property[0] + " not found")

        def header_general(line, beatmap):
            """
            Parses the header General
            """
            line_property = get_line_property(line)
            if line_property[0] == "AudioFilename":
                audio_filename = line_property[1].strip()
                beatmap.audio_filename = audio_filename
                audio = HitSound(0, None, 0, 1, audio_filename, OsuBeatmapReader._sample_index)
                OsuBeatmapReader._sample_index += 1
                beatmap.hitsound_names.append(audio.get_info())
            elif line_property[0] == "AudioLeadIn":
                beatmap.audio_lead_in = int(line_property[1])
            elif line_property[0] == "PreviewTime":
                beatmap.preview_time = int(line_property[1])
            elif line_property[0] == "Countdown":
                pass
            elif line_property[0] == "SampleSet":
                beatmap.sample_set = str(line_property[1])
                pass
            elif line_property[0] == "StackLeniency":
                pass
            elif line_property[0] == "Mode":
                if not int(line_property[1]) == 3:
                    raise OsuGameTypeException("Beatmap is not an o!m beatmap!")
            elif line_property[0] == "LetterboxInBreaks":
                pass
            elif line_property[0] == "SpecialStyle":
                if line_property[1] == 1:
                    beatmap.special_style = True
            elif line_property[0] == "WidescreenStoryboard":
                pass

        def header_metadata(line, beatmap):
            """
            Parses the header Metadata
            """
            line_property = get_line_property(line)
            if line_property[0] == "Title":
                beatmap.title = line_property[1].strip().replace("/", "").replace("\\", "")
            elif line_property[0] == "TitleUnicode":
                try:
                    beatmap.title_unicode = line_property[1].strip().encode("shiftjis")
                    beatmap.title_unicode = line_property[1].strip()
                except UnicodeEncodeError:
                    beatmap.title_unicode = beatmap.title
            elif line_property[0] == "Artist":
                beatmap.artist = line_property[1].strip()
            elif line_property[0] == "ArtistUnicode":
                try:
                    beatmap.artist_unicode = line_property[1].strip().encode("shiftjis")
                    beatmap.artist_unicode = line_property[1].strip()
                except UnicodeEncodeError:
                    beatmap.artist_unicode = beatmap.artist
            elif line_property[0] == "Creator":
                beatmap.creator = line_property[1].strip()
            elif line_property[0] == "Version":
                beatmap.version = line_property[1].strip()
            elif line_property[0] == "Source":
                beatmap.source = line_property[1].strip()
            elif line_property[0] == "Tags":
                pass
            elif line_property[0] == "BeatmapID":
                beatmap.beatmap_id = line_property[1].strip()
            elif line_property[0] == "BeatmapSetID":
                pass

        def is_empty(line):
            """
            Returns True iff line is empty
            """
            return len(line.strip()) == 0

        def is_comment(line):
            """
            Returns True iff line is a comment line
            """
            return len(line) >= 2 and line[0:1] == "//"

        def is_section_header(line):
            """
            Return True iff line is section header.
            """
            return len(line) >= 2 and line[0] == '[' and line[-1] == ']'

        def get_section(line):
            """
            Return section header
            """
            return line[1:-1]

        def get_line_property(line):
            """
            Returns tuple of (Attribute, Value)
            """
            split = line.split(":")
            return (split[0], split[1])

        def parse_symbol_separated(line, symbol):
            """
            Returns list of elements in line separated by symbol.
            """
            return line.split(symbol)

        file = codecs.open(input_file, 'r', "utf-8")
        section = "FileFormat"
        for line in file.readlines():
            if is_empty(line) or is_comment(line):
                continue
            elif is_section_header(line):
                section = get_section(line)
                continue
            if line[0] == '[':
                section = line[1:-3]
                continue
            if section == "FileFormat":
                continue
            elif section == "General":
                header_general(line, osumania_beatmap)
            elif section == "Editor":
                continue
            elif section == "Metadata":
                header_metadata(line, osumania_beatmap)
            elif section == "Difficulty":
                header_difficulty(line, osumania_beatmap)
            elif section == "Events":
                header_events(line, osumania_beatmap)
            elif section == "TimingPoints":
                header_timingpoints(line, osumania_beatmap)
            elif section == "Colours":
                continue
            elif section == "HitObjects":
                header_hitobjects(line, osumania_beatmap)
            else:
                OsuParseException("Header Error: " + section + " not found")

        osumania_beatmap.objects = sorted(osumania_beatmap.hit_objects +
                                          osumania_beatmap.sample_objects +
                                          osumania_beatmap.noninherited_tp,
                                          key=lambda x: (x.time, x.sort_type))

        # for i in range(len(osumania_beatmap.objects)):
        #     if isinstance(osumania_beatmap.objects[i], OsuTimingPoint):
        #         j = i
        #         while osumania_beatmap.objects[j].time == osumania_beatmap.objects[i].time:
        #             j -= 1
        #         j += 1
        #         osumania_beatmap.objects[j], osumania_beatmap.objects[i], = \
        #             osumania_beatmap.objects[i], osumania_beatmap.objects[j]

        file.close()
