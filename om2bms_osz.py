import zipfile
import os
import shutil

from argparse import ArgumentParser
from om2bms.exceptions import BMSMaxMeasuresException
from om2bms.image_resizer import black_background_thumbnail

import om2bms.om_to_bms
import multiprocessing


def start_convertion(filedir_, output_file_dir_, file_, args, bg_list_):
    """
    Returns bg filename
    """
    try:
        om2bms.om_to_bms.OsuManiaToBMSParser._convertion_options = {
            "HITSOUND": args.hitsound,
            "BG": args.bg,
            "OFFSET": args.offset,
            "JUDGE": args.judge
        }
        
        converted_file = om2bms.om_to_bms.OsuManiaToBMSParser(filedir_, output_file_dir_, file_)
        if not converted_file.failed and args.bg:
            bg_list_.append(converted_file.get_bg())
    except BMSMaxMeasuresException as e:
        print(e)


def convert_bg_list(bg_list_) -> None:
    """
    Converts all images in img_list
    """
    seen = []
    for bg in bg_list_:
        if bg is not None and bg not in seen:
            black_background_thumbnail(bg)
            seen.append(bg)


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

    parser.add_argument('-o', '--offset',
                        default=0,
                        type=int,
                        help="Adjusts music start time by [offset] ms.")

    parser.add_argument('-j', '--judge',
                        default=3,
                        type=int,
                        help="Judge difficulty. Defaults to EASY. "
                        "(3: EASY), (2: NORMAL), (1: HARD), (0: VERY HARD)")

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

        # convert beatmap
        # bg_list = []
        # for file in os.listdir(unzip_dir):
        #     if file.endswith(".osu"):
        #         filedir = os.path.join(unzip_dir, file)
        #         try:
        #             convert = om2bms.om_to_bms.OsuManiaToBMSParser(filedir, output_file_dir, file)
        #             bg_list.append(convert.get_bg())
        #         except BMSMaxMeasuresException as e:
        #             print(e)
        #             continue
        processes = []
        manager = multiprocessing.Manager()
        bg_list = manager.list()
        for file in os.listdir(unzip_dir):
            if file.endswith(".osu"):
                filedir = os.path.join(unzip_dir, file)
                p = multiprocessing.Process(target=start_convertion,
                                            args=(filedir, output_file_dir, file, args, bg_list))
                processes.append(p)

        for p in processes:
            p.start()

        for p in processes:
            p.join()

        # convert bg
        # if args.hitsound:
        #     seen = []
        #     for bg in bg_list:
        #         if bg is not None and bg not in seen:
        #             black_background_thumbnail(bg)
        #             seen.append(bg)
        if args.bg:
            print("Converting BG...")
            convert_bg_list(bg_list)

        # move files to output directory
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
