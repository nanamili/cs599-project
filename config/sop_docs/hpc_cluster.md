# ============================================
# 仪器SOP文档 - 高性能计算集群 (HPC)
# ============================================

---

## 一、系统基本信息

- **系统名称**：StarCluster-HPC 高性能计算集群
- **所在位置**：信息楼 3F 数据中心
- **管理员**：王工
- **部署年份**：2024年
- **计算节点**：64节点 × 2×Intel Xeon 8480+ (56核/节点)
- **GPU节点**：8节点 × 8×NVIDIA A100 (80GB)
- **总核数**：3584 CPU核心 + 64 GPU
- **存储**：2PB Lustre并行文件系统
- **网络**：InfiniBand HDR 200Gbps

## 二、账号申请与资源配额

### 2.1 账号申请
1. 填写《计算资源申请表》（导师签字）
2. 提交至信息楼301室管理员处
3. 审批通过后1个工作日内开通账号
4. 初始配额：500 CPU核时 + 100 GPU卡时/月

### 2.2 配额提升
1. 填写《资源配额调整申请表》
2. 导师签字 + 课题负责人审批
3. 注明提升原因和预期用量
4. 超额使用的按排队优先级降级处理

## 三、作业提交指南

### 3.1 Slurm 作业系统
```bash
# 交互式作业（调试用，最多2小时）
srun --partition=debug --ntasks=4 --time=02:00:00 --pty /bin/bash

# 批处理作业脚本示例
#!/bin/bash
#SBATCH --job-name=my_job
#SBATCH --partition=normal
#SBATCH --nodes=2
#SBATCH --ntasks-per-node=56
#SBATCH --time=24:00:00
#SBATCH --output=job_%j.out
#SBATCH --error=job_%j.err

module load intel/2023
module load mpi
mpirun ./my_program
```

### 3.2 分区说明
| 分区 | 最大节点数 | 最长运行时间 | 优先级 |
|------|-----------|-------------|--------|
| debug | 2 | 2小时 | 高 |
| normal | 16 | 72小时 | 中 |
| large | 64 | 48小时 | 低 |
| gpu | 8 | 24小时 | 中 |

### 3.3 数据管理
- Home目录：100GB（代码和配置）
- Scratch目录：10TB（作业临时数据，15天后自动清理）
- Project目录：按课题组分配（永久存储）
- 重要结果及时备份至学校NAS

## 四、软件环境

### 4.1 预装软件
- 编译工具：GCC 12.2, Intel oneAPI 2023, CUDA 12.1
- MPI：OpenMPI 4.1, Intel MPI 2021
- 科学计算：VASP 6.4, LAMMPS, Gaussian 16, GROMACS 2023
- AI框架：PyTorch 2.1, TensorFlow 2.13
- 数据处理：Python 3.11 (Anaconda), R 4.3, Matlab R2023b

### 4.2 自定义环境
```bash
# 使用conda创建环境
module load anaconda3
conda create -n my_env python=3.11
conda activate my_env
pip install torch numpy scipy
```

## 五、使用规范

### 5.1 禁止事项
1. 禁止在外网暴露任何服务端口
2. 禁止在登录节点运行计算密集型任务
3. 禁止挖矿或非科研用途
4. 禁止共享账号
5. 数据不备份丢失自行负责

### 5.2 建议
1. 大规模作业前先用小规模测试
2. 定期清理scratch目录
3. 使用checkpoint避免长时间作业中断损失
4. GPU节点资源紧张，非必要不使用

## 六、预约规则

- CPU节点：无需预约，直接提交作业
- GPU节点：需提前预约（最少4卡时起约）
- 独占节点：需提前48小时通过预约系统申请
- 维护窗口：每月第一个周六8:00-20:00

## 七、常见问题

### Q1: 作业一直排队
- 检查QOS设置是否正确
- 减少请求资源（节点数/时间）
- 避开高峰时段（周一到周五 9:00-22:00）

### Q2: Out of Memory错误
- 增大作业请求内存
- 优化代码内存使用
- 使用更大内存的节点

### Q3: GPU无法调用
- 确认module load cuda
- 检查程序CUDA版本兼容性
- 确认作业提交至gpu分区

---

> **文档版本**：v3.0  
> **最后更新**：2026-02-20  
> **审核人**：王工
