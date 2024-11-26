import torch
import torch.nn as nn

# RecurrentCycle: 周期建模核心模块
class RecurrentCycle(torch.nn.Module):
    def __init__(self, cycle_len, channel_size):
        super(RecurrentCycle, self).__init__()
        self.cycle_len = cycle_len
        self.channel_size = channel_size
        self.data = torch.nn.Parameter(torch.zeros(cycle_len, channel_size), requires_grad=True)

    def forward(self, index, length):
        # 动态计算索引并提取周期模式
        gather_index = (index.view(-1, 1) + torch.arange(length, device=index.device).view(1, -1)) % self.cycle_len
        return self.data[gather_index]


# DoubleCycleNet 模型
class Model(nn.Module):
    def __init__(self, configs):
        super(Model, self).__init__()

        # 配置参数
        self.seq_len = configs.seq_len
        self.pred_len = configs.pred_len
        self.enc_in = configs.enc_in
        self.cycle_len = configs.cycle
        self.model_type = configs.model_type
        self.d_model = configs.d_model
        self.use_revin = configs.use_revin

        # 第一层周期建模
        self.cycleQueue1 = RecurrentCycle(cycle_len=self.cycle_len, channel_size=self.enc_in)

        # 第二层周期建模
        self.cycleQueue2 = RecurrentCycle(cycle_len=self.cycle_len, channel_size=self.enc_in)

        # 第二层预测模型
        assert self.model_type in ['linear', 'mlp']
        if self.model_type == 'linear':
            self.model2 = nn.Linear(self.seq_len, self.pred_len)  # 第二层直接处理第一层残差
        elif self.model_type == 'mlp':
            self.model2 = nn.Sequential(
                nn.Linear(self.seq_len, self.d_model),
                nn.ReLU(),
                nn.Linear(self.d_model, self.pred_len)
            )

    def forward(self, x, cycle_index):
        # x: (batch_size, seq_len, enc_in), cycle_index: (batch_size,)

        # 实例归一化 (RevIN)
        if self.use_revin:
            seq_mean = torch.mean(x, dim=1, keepdim=True)  # 按时间步求均值
            seq_var = torch.var(x, dim=1, keepdim=True) + 1e-5  # 按时间步求方差
            x = (x - seq_mean) / torch.sqrt(seq_var)  # 标准化输入

        # ========================= 第一层 =========================
        # 提取数据的主要周期性成分
        data_cycle = self.cycleQueue1(cycle_index, self.seq_len)  # 第一层提取周期性成分
        # 去周期性，得到第一层残差
        res1 = x - data_cycle  # 第一层的输出是去掉主要周期性后的残差

        # ========================= 第二层 =========================
        # 提取第一层残差中的次级周期性成分
        res1_cycle = self.cycleQueue2(cycle_index, self.seq_len)  # 第二层提取次级周期性成分
        # 去次级周期性，得到最终残差
        res2 = res1 - res1_cycle  # 第二层的输出是去掉次级周期性后的残差

        # 使用第二层预测模型对最终残差进行建模
        final_residual = self.model2(res2.permute(0, 2, 1)).permute(0, 2, 1)

        # ========================= 最终输出 =========================
        # 最终输出 = 第一层周期性成分 + 第二层周期性成分 + 最终残差
        y = data_cycle + res1_cycle + final_residual

        # 实例反归一化 (RevIN)
        if self.use_revin:
            y = y * torch.sqrt(seq_var) + seq_mean  # 反归一化恢复原始数据分布

        return y