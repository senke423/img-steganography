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
lossless_formats = ['png', 'bmp', 'tiff', 'tif']
HEADER_SIZE = 8 # in pixels

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
    pattern = re.compile(r"^.*\.(png|bmp|tiff|tif)$")

    if not pattern.match(args.img1_path):
            raise Exception('Invalid format of input image. Input image must be in a lossless format! E.g.: ' + str(lossless_formats))
        
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
            aux = int(img1[row][col][j] & mask) # convert to variable length int, so that the left-most bits won't be truncated while shifting left
            aux <<= i*6 + j*2
            hid_w |= aux

    logger.log('Decoding hidden image height...')
    for i in range(3, 6, 1):
        row = i // img1_w
        col = i % img1_w
        for j in range(3):
            aux = int(img1[row][col][j] & mask) # convert to variable length int, so that the left-most bits won't be truncated while shifting left
            aux <<= (i - 3)*6 + j*2
            hid_h |= aux

    no_of_pixels = 0b0000
    bits = 0b0000

    z = 6
    row = z // img1_w
    col = z % img1_w
    logger.log('Decoding number of most significant bits that were used from the hidden image...')
    for i in range(2):
        aux = img1[row][col][i] & mask
        aux <<= i*2
        bits |= aux

    logger.log('Decoding number of pixels that the most significant bits were spread out on...')
    
    z = 7
    row = z // img1_w
    col = z % img1_w
    for i in range(2):
        aux = img1[row][col][i] & mask
        aux <<= i*2
        no_of_pixels |= aux

    if hid_w * hid_h > img1_w * img1_h - HEADER_SIZE or no_of_pixels > 8 or bits > 8 or bits == 0:
        raise Exception('There\'s no secret message encoded in here. Change the decoding parameters or make sure you selected the correct image.')

    logger.log(f'\n\nFound the width and height! The resolution is: {hid_w} x {hid_h} px')
    logger.log(f'Found the no of pixels and no of bits! NO_OF_PIXELS = {no_of_pixels}, BITS = {bits}')

    hid_h = int(hid_h)
    hid_w = int(hid_w)
    no_of_pixels = int(no_of_pixels)
    bits = int(bits)


    img_out = np.zeros((hid_h, hid_w, 3), dtype=np.uint8)
    img_out[:] = (0, 0, 0)


    bits_per_px = bits // no_of_pixels
    px_cnt = 0
    z = 0 # pixel in hidden image we got to
    mask = (0b11111111 << bits_per_px) & 0xFF
    inv_mask = ~mask & 0xFF
    hid_row = 0
    hid_col = 0

    increment = 10000
    if hid_h * hid_w > 5000000:
        increment *= 10

    with alive_bar(hid_h * hid_w * no_of_pixels, title='Extracting hidden image...', bar='classic2') as bar:
        for i in range(HEADER_SIZE, hid_h * hid_w * no_of_pixels + HEADER_SIZE, 1):
            row = i // img1_w
            col = i % img1_w
            img_pix = img1[row][col]

            if i % increment == 0 and i + increment >= hid_h * hid_w * no_of_pixels:
                bar(hid_h * hid_w * no_of_pixels - bar.current)
            elif i % increment == 0:
                bar(increment)
            
            if px_cnt == no_of_pixels:
                px_cnt = 0
                z += 1
                if z == hid_w * hid_h: # iterated through every pixel
                    break
                hid_row = z // hid_w
                hid_col = z % hid_w


            for q in range(3):
                img_out[hid_row][hid_col][q] |= img_pix[q] & inv_mask

            if px_cnt + 1 != no_of_pixels:
                img_out[hid_row][hid_col] = tuple(element << bits_per_px for element in img_out[hid_row][hid_col])
            else:
                # if the NO_OF_BITS parameter is less than 8, all of the bits need to be shifted by
                # 8 - NO_OF_BITS, otherwise the image will look darker (the most significant bits will be 0
                # instead of the least significant bits)
                img_out[hid_row][hid_col] = tuple(element << (8 - bits) for element in img_out[hid_row][hid_col])

            px_cnt += 1


    logger.log('Processing finished, saving image to current directory...\n')
    out_filename = 'DECRYPTED.png'
    if args.output:
        out_filename = args.output
    cv2.imwrite(out_filename, img_out)
    logger.log(f'Saved image as: {out_filename}')
    logger.success('Aaaaaand.... Abracadabra! :)')


def hide_image(args, logger):
    extensions = re.compile(r"^.*\.(jpeg|jpg|png|webp|bmp|dib|tiff|tif)$")

    if not extensions.match(args.img1_path) or not extensions.match(args.img2_path):
            raise Exception('Invalid format(s) of input images. Valid formats include: ' + str(valid_img_formats))
        
    if not os.path.isfile(args.img1_path) or not os.path.isfile(args.img2_path):
        raise Exception('One or both of the file paths isn\'t valid')

    logger.log(f'Entered parameters:\n\tNumber of sig. bits:\t{args.bits}\n\tNumber of pixels:\t{args.advanced}')

    if args.bits == 8:
        logger.log('\tEncoding type:\t\tlossless')
    else:
        logger.log('\tEncoding type:\t\tlossy')
    
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

    pattern = re.compile(r"^.*\/(.*)$") # extract the filename

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
    # pixels 0-2:   hidden image width      -> MSB first                              #
    # pixels 3-5:   hidden image height     -> MSB first                              #
    # pixel 6:      NO_OF_BITS                                                        #
    # pixel 7:      NO_OF_PIXELS                                                      #
    # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # # #
    
    mask = 0b11111100
    inv_mask = ~mask & 0xFF # 0xFF, because ints are represented using two's complement

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

    logger.log(f'Encoding number of most significant bits to be used from the hidden image...\t\t{bin(bits)}')
    for i in range(2):
        img_out[row][col][i] = img1[row][col][i] & mask
        aux = inv_mask & bits_aux
        img_out[row][col][i] += aux
        bits_aux >>= 2

    no_of_pixels = args.advanced
    nop_aux = args.advanced
    z = 7 # pixel 7
    row = z // img1_w
    col = z % img1_w

    logger.log(f'Encoding number of pixels to spread the most significant bits out on...\t\t{bin(no_of_pixels)}')
    for i in range(2):
        img_out[row][col][i] = img1[row][col][i] & mask
        aux = inv_mask & nop_aux
        img_out[row][col][i] += aux
        nop_aux >>= 2


    bits_per_px = bits // no_of_pixels
    px_cnt = 0
    z = 0 # pixel in hidden image we got to
    mask = (0b11111111 << bits_per_px) & 0xFF
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
            aux = tuple((element >> (8 - bits_per_px)) & inv_mask for element in hid_pix)
            for q in range(3):
                img_out[row][col][q] |= aux[q]
            hid_pix = tuple(element << bits_per_px for element in hid_pix)
            
            px_cnt += 1

            
    logger.log('Processing finished, saving image to current directory...\n')
    out_filename = 'OUTPUT' + str(bits) + 'B' + str(no_of_pixels) + 'A.png'
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
        parser.add_argument('-a', '--advanced', type=int, default=3, action='store', metavar='NO_OF_PIXELS', help='Advanced encryption; instead of hiding NUM_OF_BITS most significant bits in 1 pixel, spread it out over NO_OF_PIXELS pixels so that the change to the original image is less noticeable. If img1 resolution is big enough, it could losslessly hide img2. Max supported hidden image resolution: 262,143 x 262,143 px. Note: 8 pixels are used as a header for the encryption algorithm, so you can\'t have two images with the same resolutions! Not enough space!')
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
        if match and match.group(1) not in lossless_formats:
            raise Exception('Invalid output format. Output format must be lossless! E.g.: ' + str(lossless_formats))
        

        if args.extract:
            extract_image(args, logger)
        else: 
            hide_image(args, logger)


    except Exception as e:
        print(red + 'ERROR: ' + str(e) + reset)
        print(traceback.format_exc())
