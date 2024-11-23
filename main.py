import argparse
import inquirer
import re
import cv2
import os.path
import numpy as np
import traceback
from alive_progress import alive_bar

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
    pattern = re.compile(r"^.*\.(jpeg|jpg|png|webp|bmp|dib|tiff|tif)$")

    if not pattern.match(args.img1_path):
            raise Exception('Invalid format of input image. Valid formats include: ' + str(valid_img_formats))
        
    if not os.path.isfile(args.img1_path):
        raise Exception('The image path isn\'t valid')

    logger.log('Analyzing image...')

    img1 = cv2.imread(args.img1_path)
    img1_h = img1.shape[0]
    img1_w = img1.shape[1]

    hid_w = hid_h = 0b000000000000000000
    mask = 0b00000011

    logger.log('Decoding hidden image width...')
    for i in range(3):
        row = i // img1_w
        col = i % img1_w
        for j in range(3):
            print(f'Pixel {i}, channel {j}: {bin(img1[row][col][j])}')
            aux = int(img1[row][col][j] & mask) # convert to variable length int, so that the left-most bits won't be truncated while shifting left
            print(f'Aux: {bin(aux)}')
            aux <<= i*6 + j*2
            print(f'Aux after shifting: {bin(aux)}')
            hid_w |= aux
            print(f'Hidden width: {bin(hid_w)}\n')

    print(f'Hidden width: {hid_w}')


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
    if img1_w * img1_h < HEADER_SIZE + img2_w * img2_h * args.advanced:
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

    # Note on the implementation  # # # # # # # # # # # # # # # # # # # # # # # # # # #
    # Colours in tuples are in this order: B, G, R                                    #
    # pixels 0-2:   hidden image width    -> B channel has least significant bits     #
    # pixels 3-5:   hidden image height   -> B channel has least significant bits     #
    # pixel 6:      NO_OF_BITS      -> B channel has least significant bits           #
    # pixel 7:      NO_OF_PIXELS    -> B channel has least significant bits           #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    
    mask = 0b11111100
    inv_mask = ~mask & 0xFF

    hid_width = img2_w
    logger.log(f'Encoding hidden image width...\t\t{bin(hid_width)}')
    for i in range(3):
        row = i // img1_w
        col = i % img1_w
        for j in range(3):
            img_out[row][col][j] = img1[row][col][j] & mask
            aux = inv_mask & hid_width
            img_out[row][col][j] += aux
            hid_width >>= 2
    
    for i in range(3):
        for j in range(3):
            print(f'{i}: {img_out[0][i][j]}')

    hid_height = img2_h
    logger.log(f'Encoding hidden image height...\t\t{bin(hid_height)}')
    for i in range(3, 6, 1):
        row = i // img1_w
        col = i % img1_w
        for j in range(3):
            img_out[row][col][j] = img1[row][col][j] & mask
            aux = inv_mask & hid_height
            img_out[row][col][j] += aux
            hid_height >>= 2

    bits = bits_aux = args.bits
    z = 6 # pixel 6
    row = z // img1_w
    col = z % img1_w

    logger.log(f'Encoding number of significant bits to be used from the hidden image...\t\t{bin(bits)}')
    for i in range(2):
        img_out[row][col][i] = img1[row][col][i] & mask
        aux = inv_mask & bits_aux
        img_out[row][col][i] += aux
        bits_aux >>= 2

    no_of_pixels = nop_aux = args.advanced
    z = 7 # pixel 7
    row = z // img1_w
    col = z % img1_w

    logger.log(f'Encoding number of pixels...\t\t{bin(no_of_pixels)}')
    for i in range(2):
        img_out[row][col][i] = img1[row][col][i] & mask
        aux = inv_mask & nop_aux
        img_out[row][col][i] += aux
        nop_aux >>= 2

    bits_per_px = bits // no_of_pixels
    px_cnt = 0
    z = 0 # pixel in hidden image we got to
    mask = (0b11111111 << (bits // no_of_pixels)) & 0xFF
    inv_mask = ~mask & 0xFF
    hid_pix = img2[0][0]
    end_of_img2 = False
    
    increment = 10000
    if img1_w * img1_h > 5000000:
        increment *= 10

    with alive_bar(img1_w * img1_h - HEADER_SIZE, title='Encoding the hidden image...', bar='classic2') as bar:
        for i in range(HEADER_SIZE, img1_w * img1_h, 1):
            # Encode 
            row = i // img1_w
            col = i % img1_w
            
            if i % increment == 0 and i + increment >= img1_w * img1_h - HEADER_SIZE:
                bar(img1_w * img1_h - HEADER_SIZE - bar.current)
            elif i % increment == 0:
                bar(increment)
            
            if not end_of_img2 and px_cnt == no_of_pixels:
                px_cnt = 0
                z += 1
                if z == img2_w * img2_h:
                    end_of_img2 = True
                else:
                    hid_row = z // img2_w
                    hid_col = z % img2_w
                    hid_pix = img2[hid_row][hid_col]

            if end_of_img2:
                img_out[row][col] = img1[row][col]
                continue

            img_out[row][col] = tuple(element & mask for element in img1[row][col])
            aux = tuple(element & inv_mask for element in hid_pix)
            for q in range(3):
                img_out[row][col][q] += aux[q]
            hid_pix = tuple(element >> bits_per_px for element in hid_pix)

            px_cnt += 1

            
    logger.log('Processing finished, saving image to current directory...\n')
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
        parser.add_argument('-a', '--advanced', type=int, default=3, action='store', metavar='NO_OF_PIXELS', help='Advanced encryption; instead of hiding NUM_OF_BITS most significant bits in 1 pixel, spread it out over NO_OF_PIXELS pixels so that the change to the original image is less noticeable. If img1 resolution is big enough, it could losslessly hide img2. Max supported hidden image resolution: 262,143 x 262,143 px. Note: 7 pixels are used as a header for the encryption algorithm.')
        parser.add_argument('-o', '--output', type=str, action='store', metavar='FILENAME', help='Name of the output file')
        parser.add_argument('-e', '--extract', action='store_true', help='Extract a hidden image')

        args = parser.parse_args()

        logger = logging_object(args.verbose)

        
        if args.bits <= 0 or args.bits > 8:
            raise Exception('Invalid number of bits.')

        if args.advanced <= 0 or args.advanced > 8 or args.advanced > args.bits or args.bits % args.advanced != 0:
            raise Exception('Invalid -a arg value. It must be:\n\t1. Between 1 and 8 (both inclusive)\n\t2. Smaller than NO_OF_BITS\n\t3. A factor of NO_OF_BITS')

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
