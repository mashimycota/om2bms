# o!m2bms

A 7k/8k osu!mania to BMS file converter.

Supports fully keysounded maps and bpm changes.

### Installation

Written on Python 3.6+ and requires Pillow (for image resizing).

```
pip install Pillow
```

Set the default output directory by running,

```
python om2bms_osz.py -sdo [OUTPUT DIRECTORY]
```

or go to `default_outdir.ini` and paste a subdirectory to the a songfolder directory.

### Running
Run

```
python om2bms_osz.py -i sample_osz_file.osz
```

to convert all 7k/8k files in `sample_osz_file.osz` and output them to `[OUTPUT DIRECTORY]/sample_osz_file`

To convert individual .osu files run

```
python om2bms.py -i sample_osu_file.osu
```



To view help, run

```
python om2bms_osz.py -h
```

```
python om2bms.py -h
```



### To-do List

- Drag-and-drop GUI
- 5k maps
- Key options for non-7k/8k maps

### Notes

- Tested with LR2
- Does not support SV changes
- Uses first timing point to estimate the first measure
- Assumes timing points are always the start of a new measure
- There may be some offset issues (no online offset)
- If there are >1 hitsounds played in one note, only plays the hitsound with the highest bit

[.osu file documentation](https://osu.ppy.sh/help/wiki/osu!_File_Formats/Osu_(file_format)).

[BMS file documentation](https://hitkey.nekokan.dyndns.info/cmds.htm).

## License

This project is licensed under the GPLv3 license, refer to LICENSE for details.

