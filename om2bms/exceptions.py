"""
For exceptions
"""


class OsuParseException(Exception):
    """Excpetion class for osu parsing excpetions"""
    pass


class OsuGameTypeException(Exception):
    """For non-osumania maps """
    pass


class BMSHitSoundException(Exception):
    """When there are too many sound files (~1293)"""
    pass


class BMSMaxMeasuresException(Exception):
    """BMS files only support up to 999 measures."""
    pass
