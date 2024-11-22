import argparse
import inquirer
import re
import cv2
import os.path
import numpy as np
import traceback

cyan = '\033[96m'
yellow = '\033[93m'
green = '\033[32m'
red = '\033[31m'
reset = '\033[0m'

valid_img_formats = ['jpg', 'jpeg', 'png', 'bmp', 'webp', 'dib', 'tiff', 'tif']
HEADER_SIZE = 7 # in pixels

class logging_object:
    __enabled = False

    def __init__(self, enabled):
        self.__enabled = enabled

    def log(self, msg):
        if self.__enabled:
            print(yellow + msg + reset)
    
    def success(self, msg):
        if self.__enabled:
            print(green + msg + reset)


def extract_image(args, logger):
    logger.log('Extracting the hidden image...')


def hide_image(args, logger):
    pattern = re.compile(r"^.*\.(jpeg|jpg|png|webp|bmp|dib|tiff|tif)$")

    if not pattern.match(args.img1_path) or not pattern.match(args.img2_path):
            raise Exception('Invalid format(s) of input images. Valid formats include: ' + str(valid_img_formats))
        
    if not os.path.isfile(args.img1_path) or not os.path.isfile(args.img2_path):
        raise Exception('One or both of the file paths isn\'t valid')

    
    logger.log('Loading images...')

    img1 = cv2.imread(args.img1_path)
    img2 = cv2.imread(args.img2_path)

    img1_h = img1.shape[0]
    img1_w = img1.shape[1]
    img2_h = img2.shape[0]
    img2_w = img2.shape[1]

    logger.log('Analyzing dimensions...')
    if img1_h * img1_w < HEADER_SIZE + (img2_h * img2_w) * args.advanced:
        raise Exception('For the specified parameters, img1 (the visible image) doesn\'t have a high enough resolution to hide img2.')

    pattern = re.compile(r"^.*\/(.*)$")

    img1_filename, img2_filename = args.img1_path, args.img2_path
    if '\\' in args.img1_path:
        img1_filename = re.match(pattern, args.img1_path).group(1)
    if '\\' in args.img2_path:
        img2_filename = re.match(pattern, args.img2_path).group(1)

    logger.log("\n{:<55} {}x{} px".format('img1 (' + str(img1_filename) + ') (visible) dimensions:', img1_w, img1_h))
    logger.log("{:<55} {}x{} px".format('img2 (' + str(img2_filename) + ') (hidden) dimensions:', img2_w, img2_h))

    logger.log('\nHiding {} inside {}...'.format(img2_filename, img1_filename))

    img_out = np.zeros(img1.shape, dtype=np.uint8)

    bits = args.bits
    # Pixel tuple colours:
    # B, G, R
    # pixels 0-2:   hidden width    -> BLUE channel - starting with LSBs
    # pixels 3-5:   hidden height   -> BLUE channel - starting with LSBs
    # pixel  6:     NO_OF_BITS      -> BLUE channel
    #               NO_OF_PIXELS    -> GREEN channel
    # WIDTH
        
            
            
    logger.log('Processing finished, saving image to current directory...')
    out_filename = 'OUTPUT.jpg'
    if args.output:
        out_filename = args.output
    cv2.imwrite(out_filename, img_out)
    logger.log(f'Saved image as: {out_filename}')
    logger.success('Sshhhh.... Image successfully hid! ;)')


if __name__ == '__main__':
    try:
        parser = argparse.ArgumentParser(prog='img_steg', description ='Hide an image inside another image.')

        parser.add_argument('img1_path', type=str, help='Path to an image to extract a hidden image from / the visible image in which to hide another image')
        parser.add_argument('-i', '--img2-path', action='store', metavar='PATH', type=str, help='Path to image you\'d like to hide')
        parser.add_argument('-v', '--verbose', action='store_true', help='Prints additional log messages')
        parser.add_argument('-b', '--bits', type=int, default=6, action='store', metavar='NUM_OF_BITS', help='Number of most significant bits to use from the hidden image')
        parser.add_argument('-a', '--advanced', type=int, default=2, action='store', metavar='NO_OF_PIXELS', help='Advanced encryption; instead of hiding NUM_OF_BITS most significant bits in 1 pixel, spread it out over NO_OF_PIXELS pixels so that the change to the original image is less noticeable. If img1 resolution is big enough, it could losslessly hide img2. Max supported hidden image resolution: 262,143 x 262,143 px. Note: 7 pixels are used as a header for the encryption algorithm.')
        parser.add_argument('-o', '--output', type=str, action='store', metavar='FILENAME', help='Name of the output file')
        parser.add_argument('-e', '--extract', action='store_true', help='Extract a hidden image')

        args = parser.parse_args()

        logger = logging_object(args.verbose)

        
        if args.bits <= 0 or args.bits > 8:
            raise Exception('Invalid number of bits.')

        if args.advanced <= 0 or args.advanced > 8 or args.advanced > args.bits or args.bits % args.advanced != 0:
            raise Exception('Invalid -a arg value. It must be:\n\t1. Smaller than NUM_OF_BITS, and\n\t2. A multiple of NUM_OF_BITS')

        extension = re.compile(r"\.(.*)")
        match = None
        if args.output:
            match = re.search(extension, args.output)
        if match and match.group(1) not in valid_img_formats:
            raise Exception('Invalid output format. Supported formats: ' + str(valid_img_formats))
        

        if args.extract:
            extract_image(args, logger)
        else:
            hide_image(args, logger)


    except Exception as e:
        print(red + 'ERROR: ' + str(e) + reset)
        print(traceback.format_exc())
