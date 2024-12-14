import time
import torch
import torch.nn as nn
import matplotlib.pyplot as plt

class RecurrentCycle(torch.nn.Module):
    # Thanks for the contribution of wayhoww.
    # The new implementation uses index arithmetic with modulo to directly gather cyclic data in a single operation,
    # while the original implementation manually rolls and repeats the data through looping.
    # It achieves a significant speed improvement (2x ~ 3x acceleration).
    # See https://github.com/ACAT-SCUT/CycleNet/pull/4 for more details.
    def __init__(self, cycle_len, channel_size):
        super(RecurrentCycle, self).__init__()
        self.cycle_len = cycle_len
        self.channel_size = channel_size
        self.data = torch.nn.Parameter(torch.zeros(cycle_len, channel_size), requires_grad=True)

    def forward(self, index, length):
        gather_index = (index.view(-1, 1) + torch.arange(length, device=index.device).view(1, -1)) % self.cycle_len    
        return self.data[gather_index]

class Model(nn.Module):
    def __init__(self, configs):
        super(Model, self).__init__()

        # Existing initializations...
        self.seq_len = configs.seq_len
        self.pred_len = configs.pred_len
        self.enc_in = configs.enc_in
        self.cycle_len = configs.cycle
        self.model_type = configs.model_type
        self.d_model = configs.d_model
        self.use_revin = configs.use_revin

        self.cycleQueue = RecurrentCycle(cycle_len=self.cycle_len, channel_size=self.enc_in)
        assert self.model_type in ['linear', 'mlp']
        if self.model_type == 'linear':
            self.model = nn.Linear(self.seq_len, self.pred_len)
        elif self.model_type == 'mlp':
            self.model = nn.Sequential(
                nn.Linear(self.seq_len, self.d_model),
                nn.ReLU(),
                nn.Linear(self.d_model, self.pred_len)
            )
        
        # Add seasonal scaler
        self.seasonal_scaler = nn.Linear(self.enc_in, self.enc_in)

    def forward(self, x, cycle_index):
        # Existing forward steps...
        if self.use_revin:
            seq_mean = torch.mean(x, dim=1, keepdim=True)
            seq_var = torch.var(x, dim=1, keepdim=True) + 1e-5
            x = (x - seq_mean) / torch.sqrt(seq_var)

        # Remove the cycle of the input data
        Q = self.cycleQueue(cycle_index, self.seq_len)
        Q = self.seasonal_scaler(Q)
        x = x - Q

        # Forecasting with channel independence
        y = self.model(x.permute(0, 2, 1)).permute(0, 2, 1)

        # Add back the cycle of the output data
        Q = self.cycleQueue((cycle_index + self.seq_len) % self.cycle_len, self.pred_len)
        Q = self.seasonal_scaler(Q)
        y = y + Q

        # Instance denorm
        if self.use_revin:
            y = y * torch.sqrt(seq_var) + seq_mean

        return y, x
