import zipfile
import os
import shutil

from argparse import ArgumentParser
from om2bms.exceptions import BMSMaxMeasuresException

import om2bms.om_to_bms

if __name__ == "__main__":

    parser = ArgumentParser(description='Convert all .osu osu!mania files in a .osz to BMS files',
                            add_help=True,
                            allow_abbrev=True)

    parser.add_argument('-i', '--in_file',
                        action='store',
                        default='None',
                        help='Path to .osz to be converted.',
                        type=str)

    parser.add_argument('-sdo', '--set_default_out',
                        action='store',
                        default='None',
                        help='Sets the default output directory',
                        type=str)

    parser.add_argument('-hs', '--hitsound',
                        action='store_false',
                        default=True,
                        help='Disables hitsounds.')

    parser.add_argument('-b', '--bg',
                        action='store_false',
                        default=True,
                        help='Disables background image conversion.')

    parser.add_argument('-f', '--foldername',
                        action='store',
                        default='None',
                        help='Directory name to store output files in output path. '
                             'Default value is the .osz filename')

    args = parser.parse_args()
    cwd = os.getcwd()

    cfg_file = os.path.join(cwd, 'default_outdir.ini')
    if not os.path.exists(cfg_file):
        with open(cfg_file, "w") as file:
            file.write("")
    if args.set_default_out != "None":
        with open(cfg_file, 'r+') as cfg_fp:
            cfg_fp.write(args.set_default_out)
            print('Default output directory has been set to "%s"' % args.set_default_out)
            cfg_fp.close()
        outdir = args.set_default_out.strip()

    if args.in_file is "None":
        exit(0)

    if os.path.exists(cfg_file):
        with open(cfg_file, "r") as cfg_fp:
            outdir = cfg_fp.readline().strip()
            cfg_fp.close()
    else:
        outdir = cwd

    if args.foldername is "None":
        foldername = os.path.basename(args.in_file)[:-4]
        out_foldername = foldername
    else:
        out_foldername = args.foldername

    om2bms.om_to_bms.OsuManiaToBMSParser._convertion_options = {"HITSOUND": args.hitsound,
                                                                "BG": args.bg}
    unzip_dir = os.path.join(cwd, "unzip_dir")
    if not os.path.isdir(unzip_dir):
        os.makedirs(unzip_dir)
    try:
        if not os.path.isdir(unzip_dir):
            os.makedirs(unzip_dir)

        filename = os.path.basename(args.in_file)
        shutil.copy2(args.in_file, unzip_dir)

        osz_dir = os.path.join(unzip_dir, filename)

        base = os.path.splitext(osz_dir)[0]
        os.rename(osz_dir, base + ".zip")
        osz_file_dir = base + ".zip"

        print("Unzipping...")
        with zipfile.ZipFile(osz_file_dir, 'r') as zipf:
            zipf.extractall(unzip_dir)

        output_file_dir = os.path.join(outdir, out_foldername)
        print("Output directory is " + output_file_dir)

        if not os.path.isdir(output_file_dir):
            os.makedirs(output_file_dir)

        for file in os.listdir(unzip_dir):
            if file.endswith(".osu"):
                filedir = os.path.join(unzip_dir, file)
                try:
                    om2bms.om_to_bms.OsuManiaToBMSParser(filedir, output_file_dir, file)
                except BMSMaxMeasuresException as e:
                    print(e)
                    continue

        for f in os.listdir(unzip_dir):
            if not os.path.isdir(os.path.join(unzip_dir, f)):
                if not f.split(".")[-1] == "zip" and not f.split(".")[-1] == "osu":
                    full_path = os.path.join(unzip_dir, f)
                    try:
                        shutil.copy2(full_path, output_file_dir)
                    except PermissionError as e:
                        print(e)
                        continue

        print("Done")
        exit(0)
    except Exception as e:
        print(e)
        exit(1)
    finally:
        shutil.rmtree(unzip_dir)
