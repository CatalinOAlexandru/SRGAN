print('Starting imports...')
import argparse
import os
from math import log10

import numpy as np
import pandas as pd
import torch
import torchvision.utils as utils
from torch.autograd import Variable
from torch.utils.data import DataLoader
from tqdm import tqdm

import pytorch_ssim
from data_utils import TestDatasetFromFolder, display_transform
from model import Generator

parser = argparse.ArgumentParser(description='Test Benchmark Datasets')
parser.add_argument('--upscale_factor', default=4, type=int, help='super resolution upscale factor')
parser.add_argument('--model_name', default='netG_epoch_4_100.pth', type=str, help='generator model epoch name')
parser.add_argument('--path_test', default='data/test', type=str, help='path to test dataset')
parser.add_argument('--workers', default=4, type=int, help='number of workers/cores')
parser.add_argument('--name', default='Histo', type=str, help='name for folder')
opt = parser.parse_args()

UPSCALE_FACTOR = opt.upscale_factor
MODEL_NAME = opt.model_name
TEST_DATA = opt.path_test
WORKERS = opt.workers
FOLDER_NAME = opt.name

results = {'Histology': {'psnr': [], 'ssim': []}}

print('Loading model')
model = Generator(UPSCALE_FACTOR).eval()
if torch.cuda.is_available():
    model = model.cuda()
    print('CUDA is available')
print('Loading model state dict...')
model.load_state_dict(torch.load('epochs/'+ str(FOLDER_NAME) +'/' + MODEL_NAME))
print('Model loaded.')

print('Preparing dataset')
test_set = TestDatasetFromFolder(TEST_DATA, upscale_factor=UPSCALE_FACTOR)
test_loader = DataLoader(dataset=test_set, num_workers=WORKERS, batch_size=1, shuffle=False)
test_bar = tqdm(test_loader, desc='[testing benchmark datasets]')

out_path = 'benchmark_results/'+str(FOLDER_NAME)+'_' + str(UPSCALE_FACTOR) + '/'
if not os.path.exists(out_path):
    os.makedirs(out_path)

print('Starting benchmark')

allPSNR = []
allSSIM = []

for image_name, lr_image, hr_restore_img, hr_image in test_bar:
    image_name = image_name[0]

    with torch.no_grad():
        lr_image = Variable(lr_image)
        hr_image = Variable(hr_image)
        if torch.cuda.is_available():
            lr_image = lr_image.cuda()
            hr_image = hr_image.cuda()

        sr_image = model(lr_image)
        mse = ((hr_image - sr_image) ** 2).data.mean()
        psnr = 10 * log10(1 / mse)
        ssim = pytorch_ssim.ssim(sr_image, hr_image)
        print('SSIM data:',ssim)
        ssim = ssim.item()

        test_images = torch.stack(
            [display_transform()(hr_restore_img.squeeze(0)), display_transform()(hr_image.data.cpu().squeeze(0)),
             display_transform()(sr_image.data.cpu().squeeze(0))])
        image = utils.make_grid(test_images, nrow=3, padding=5)
        utils.save_image(image, out_path + image_name.split('.')[0] + '_psnr_%.4f_ssim_%.4f.' % (psnr, ssim) +
                         image_name.split('.')[-1], padding=5)

        # save psnr\ssim
        # results[image_name.split('_')[0]]['psnr'].append(psnr)
        allPSNR.append(psnr)
        # results[image_name.split('_')[0]]['ssim'].append(ssim)
        allSSIM.append(ssim)

out_path = 'statistics/'
saved_results = {'psnr': [], 'ssim': []}
# for item in results.values():
psnr = np.array(allPSNR)
ssim = np.array(allSSIM)
if (len(psnr) == 0) or (len(ssim) == 0):
    psnr = 'No data'
    ssim = 'No data'
else:
    psnr = psnr.mean()
    ssim = ssim.mean()
saved_results['psnr'].append(psnr)
saved_results['ssim'].append(ssim)

data_frame = pd.DataFrame(saved_results, results.keys())
data_frame.to_csv(out_path + str(FOLDER_NAME) +'_' + str(UPSCALE_FACTOR) + '_test_results.csv', index_label='DataSet')

print('Finished benchmark')
