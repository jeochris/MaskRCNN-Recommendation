import os
from PIL import Image
import pickle

import torch
import torchvision
import torch.nn as nn
from torchvision import transforms
import torchvision.models.resnet as resnet

# 미리 정의
conv1x1=resnet.conv1x1
Bottleneck = resnet.Bottleneck
BasicBlock= resnet.BasicBlock

class ResNet_without_fc(nn.Module):

    def __init__(self, block, layers, num_classes=1000, zero_init_residual=True):
        super(ResNet_without_fc, self).__init__()
        self.inplanes = 64

        # inputs = 3x224x224 -> 3x128x128로 바뀜
        self.conv1 = nn.Conv2d(3, self.inplanes, kernel_size=7, stride=2, padding=3, bias=False) # 마찬가지로 전부 사이즈 조정
        self.bn1 = nn.BatchNorm2d(self.inplanes)
        self.relu = nn.ReLU(inplace=True)
        self.maxpool = nn.MaxPool2d(kernel_size=3, stride=2, padding=1)
        
        self.layer1 = self._make_layer(block, 64, layers[0]) # 3 반복
        self.layer2 = self._make_layer(block, 128, layers[1], stride=2) # 4 반복
        self.layer3 = self._make_layer(block, 256, layers[2], stride=2) # 6 반복
        self.layer4 = self._make_layer(block, 512, layers[3], stride=2) # 3 반복
        
        self.avgpool = nn.AdaptiveAvgPool2d((1, 1))

        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.kaiming_normal_(m.weight, mode='fan_out', nonlinearity='relu')
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

        # Zero-initialize the last BN in each residual branch,
        # so that the residual branch starts with zeros, and each residual block behaves like an identity.
        # This improves the model by 0.2~0.3% according to https://arxiv.org/abs/1706.02677
        if zero_init_residual:
            for m in self.modules():
                if isinstance(m, Bottleneck):
                    nn.init.constant_(m.bn3.weight, 0)
                elif isinstance(m, BasicBlock):
                    nn.init.constant_(m.bn2.weight, 0)

    def _make_layer(self, block, planes, blocks, stride=1): # planes -> 입력되는 채널 수
        downsample = None
        if stride != 1 or self.inplanes != planes * block.expansion: 
            downsample = nn.Sequential(
                conv1x1(self.inplanes, planes * block.expansion, stride),
                nn.BatchNorm2d(planes * block.expansion),
            )

        layers = []
        layers.append(block(self.inplanes, planes, stride, downsample))
        self.inplanes = planes * block.expansion
        for _ in range(1, blocks):
            layers.append(block(self.inplanes, planes))

        return nn.Sequential(*layers)

    def forward(self, x):
        # input [32, 128, 128] -> [C ,H, W]
        x = self.conv1(x)
        x = self.bn1(x)
        x = self.relu(x)
        x = self.maxpool(x)
        #x.shape =[32, 64, 64]

        x = self.layer1(x)
        #x.shape =[128, 64, 64]
        x = self.layer2(x)
        #x.shape =[256, 32, 32]
        x = self.layer3(x)
        #x.shape =[512, 16, 16]
        x = self.layer4(x)
        #x.shape =[1024, 8, 8]
        
        x = self.avgpool(x)
        x = x.view(x.size(0), -1)

        return x

device = torch.device('cpu')
feature_model = ResNet_without_fc(resnet.BasicBlock, [2, 2, 2, 2], 2, True)
feature_model.load_state_dict(torch.load('no_fc_model_state_dict.pt', map_location=device))

# torchvision.transforms
tf_resize = transforms.Resize((224,224))
tf_toTensor = transforms.ToTensor()

# 파일 모으기
image_path_all = []
imageset_total = torch.Tensor()
for fashion_images in os.listdir('uploader'):
    images_path = os.path.join('uploader', fashion_images)
    image_path_all.append(images_path)
    img_RGB  = Image.open(images_path).convert('RGB')
    # PIL to Tensor
    img_RGB_tensor_from_PIL = tf_toTensor(tf_resize(img_RGB))
    img_unsqueeze = torch.unsqueeze(img_RGB_tensor_from_PIL, 0)
    imageset_total = torch.cat([imageset_total,img_unsqueeze], dim=0)

feature_model.eval()
with torch.no_grad():
    output_feature=feature_model(imageset_total)
# print(output_feature.shape)
# torch.Size([2,512])

pickle.dump(output_feature, open("image_features_embedding.pkl", "wb"))
pickle.dump(image_path_all, open("img_files.pkl", "wb"))
