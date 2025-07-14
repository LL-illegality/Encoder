# keybindings.py
# 存储游戏中所有按键配置

import pygame

# 默认按键配置
DEFAULT_KEYBINDINGS = {
    # 基础数制切换
    'decimal_mode': pygame.K_z,      # 切换到十进制
    'binary_mode': pygame.K_x,       # 切换到二进制
    'hex_mode': pygame.K_c,          # 切换到十六进制

    # 技能按键 (二进制模式下)
    'skill_1': pygame.K_h,           # 第一个技能
    'skill_2': pygame.K_j,           # 第二个技能
    'skill_3': pygame.K_k,           # 第三个技能
    'skill_4': pygame.K_l,           # 第四个技能

    # 取消技能按键
    'cancel_skill': pygame.K_e, # 取消当前技能
}

# 加载自定义按键配置
def load_keybindings():
    """
    从配置文件加载自定义按键配置
    如果配置文件不存在，返回默认配置
    """
    # 未来可以从JSON或其他配置文件加载
    # 目前直接返回默认配置
    return DEFAULT_KEYBINDINGS

# 获取pygame键值的可读名称
def get_key_name(key_code):
    """
    将pygame键值转换为可读名称
    """
    return pygame.key.name(key_code)
