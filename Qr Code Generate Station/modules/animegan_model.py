# modules/animegan_model.py
import torch, torch.nn as nn

class ResidualBlock(nn.Module):
    def __init__(self, channels):
        super().__init__()
        self.block = nn.Sequential(
            nn.Conv2d(channels, channels, 3, 1, 1),
            nn.InstanceNorm2d(channels),
            nn.ReLU(inplace=True),
            nn.Conv2d(channels, channels, 3, 1, 1),
            nn.InstanceNorm2d(channels)
        )

    def forward(self, x): return x + self.block(x)

class Generator(nn.Module):
    def __init__(self):
        super().__init__()
        self.conv1 = nn.Sequential(nn.Conv2d(3, 32, 9, 1, 4), nn.ReLU(inplace=True))
        self.conv2 = nn.Sequential(
            nn.Conv2d(32, 64, 3, 2, 1), nn.ReLU(inplace=True),
            nn.Conv2d(64, 128, 3, 2, 1), nn.ReLU(inplace=True),
        )
        self.resblocks = nn.Sequential(*[ResidualBlock(128) for _ in range(5)])
        self.deconv = nn.Sequential(
            nn.ConvTranspose2d(128, 64, 3, 2, 1, output_padding=1), nn.ReLU(inplace=True),
            nn.ConvTranspose2d(64, 32, 3, 2, 1, output_padding=1), nn.ReLU(inplace=True),
            nn.Conv2d(32, 3, 9, 1, 4), nn.Tanh()
        )

    def forward(self, x):
        x = self.conv1(x); x = self.conv2(x); x = self.resblocks(x); x = self.deconv(x)
        return x
