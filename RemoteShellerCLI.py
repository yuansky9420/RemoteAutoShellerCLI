# -*- coding: utf-8 -*-
# @Time    : 2025/10/14 18:29:50
# @Author:  yuansky9420
# @Intsall : pip install paramiko requests pyyaml
# @Name    : RemoteSheller.py
# @Description: 批量远程执行SSH命令，并添加探活功能
# @Version: 1.0.0 alpha
# @Documentation: Readme.md

import paramiko
import time
import requests
import socket
import urllib3
import yaml
import os
from typing import List, Dict, Any

# 禁用SSL证书验证警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ========================
#         配置区
# ========================

def load_config(config_file: str = "example.yaml") -> Dict[str, Any]:
    """
    加载配置文件
    """
    if not os.path.exists(config_file):
        raise FileNotFoundError(f"配置文件 {config_file} 不存在")
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    return config

# 加载配置
config = load_config()
SSH_HOST = config["ssh"]["host"]
SSH_PORT = config["ssh"]["port"]
SSH_USER = config["ssh"]["user"]
SSH_PASSWORD = config["ssh"]["password"]
TASKS = config["tasks"]

# ========================
#         方法区
# ========================
# 获取所有任务总执行时间
def estimate_total_time(tasks: List[Dict[str, Any]]) -> int:
    """
    估算所有任务的总执行时间（秒）
    """
    total_time = 0
    for task in tasks:
        # 如果有等待时间，直接加上
        if "wait_seconds" in task:
            total_time += task["wait_seconds"]
        # 如果有探活，计算最坏情况时间
        elif "probes" in task and task["probes"]:
            retries = task.get("probe_retries", 10)
            timeout = task.get("probe_timeout", 15)
            interval = task.get("probe_interval", 30)
            # 最坏情况：每次探活都超时，每次重试都间隔
            worst_case = retries * timeout + (retries - 1) * interval
            total_time += worst_case
        # 默认给10秒执行时间
        else:
            total_time += 10
    return total_time


# 选择执行模式
def select_execution_mode(tasks: List[Dict[str, Any]]) -> List[int]:
    """
    选择执行模式，返回需要执行的任务索引列表
    """
    total_tasks = len(tasks)
    
    print("\n请选择执行模式:")
    print("1. 全部执行")
    print("2. 指定步骤执行")
    print("3. 从指定步骤开始执行")
    
    while True:
        try:
            choice = input("请输入选项 (1, 2 或 3): ").strip()
            if choice == "1":
                # 全部执行，返回所有索引
                return list(range(total_tasks))
            elif choice == "2":
                # 显示所有任务
                print("\n所有任务列表:")
                for i, task in enumerate(tasks, 1):
                    task_name = task.get("name", f"任务 {i}")
                    print(f"{i}. {task_name}")
                
                # 获取用户选择
                selected = input("\n请输入要执行的步骤序号，多个序号用逗号分隔 (例如: 1,3,5): ").strip()
                indices = []
                for s in selected.split(","):
                    idx = int(s.strip())
                    if 1 <= idx <= total_tasks:
                        indices.append(idx - 1)  # 转换为0基索引
                    else:
                        print(f"【错误】 无效的序号: {idx}，序号应在 1 到 {total_tasks} 之间")
                        raise ValueError("无效的序号")
                
                return sorted(indices)
            elif choice == "3":
                # 显示所有任务
                print("\n所有任务列表:")
                for i, task in enumerate(tasks, 1):
                    task_name = task.get("name", f"任务 {i}")
                    print(f"{i}. {task_name}")
                
                # 获取起始任务
                start_idx = int(input("\n请输入起始执行的步骤序号: ").strip())
                if 1 <= start_idx <= total_tasks:
                    # 从起始任务开始执行到最后一个任务
                    return list(range(start_idx - 1, total_tasks))
                else:
                    print(f"【错误】 无效的序号: {start_idx}，序号应在 1 到 {total_tasks} 之间")
                    raise ValueError("无效的序号")
            else:
                print("【错误】 无效选项，请输入 1、2 或 3")
        except ValueError as e:
            print(f"【错误】 输入格式错误: {e}")
        except Exception as e:
            print(f"【错误】 输入错误: {e}")


# ========================
#       执行命令
# ========================

# SSH执行命令
def ssh_execute(client: paramiko.SSHClient, command: str) -> str:
    print(f"执行命令: {command}")
    stdin, stdout, stderr = client.exec_command(command)
    exit_status = stdout.channel.recv_exit_status()
    output = stdout.read().decode()
    error = stderr.read().decode()
    if exit_status != 0:
        raise RuntimeError(
            f"命令执行失败，退出码 {exit_status}: {error}")
    if output.strip():
        print(f"输出:\n{output}")
    return output

# 探活执行函数
def probe_exec(item: Dict[str, Any], default_timeout: int = 5) -> bool:
    probe_type = item.get("type", "").lower()
    timeout = default_timeout  # 使用传入的默认超时时间，忽略探活项中的设置

    if probe_type == "http":
        url = item.get("url")
        if not url:
            raise ValueError("HTTP探活缺少'url'参数")
        try:
            # 忽略SSL证书验证
            resp = requests.get(url, timeout=timeout, verify=False)
            return resp.status_code == 200
        except Exception as e:
            print(f"【错误】 HTTP探活失败 {url}: {e}")
            return False

    elif probe_type == "tcp":
        host = item.get("host")
        port = item.get("port")
        if not host or port is None:
            raise ValueError("TCP探活缺少'host'或'port'参数")
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except Exception as e:
            print(f"【错误】 TCP探活失败 {host}:{port}: {e}")
            return False

    else:
        raise ValueError(f"【警告】 未知的探活类型: {probe_type}")

# 执行模式函数
def handle_post_execution(task: dict) -> None:
    # 1. 多探活模式
    if "probes" in task and task["probes"]:
        probes = task["probes"]
        retries = task.get("probe_retries", 10)
        default_timeout = task.get("probe_timeout", 5)
        # 获取探活间隔时间，默认为5秒
        probe_interval = task.get("probe_interval", 5)

        for attempt in range(1, retries + 1):
            print(f"【信息】 尝试 {attempt}/{retries}: 探活 {len(probes)} 个端点...")
            all_ok = True
            for p in probes:
                if not probe_exec(p, default_timeout):
                    all_ok = False
                    break  # 可选：也可以不 break，检查全部
            if all_ok:
                print("【成功】 所有探活成功!")
                return
            # 在重试前等待一段时间
            if attempt < retries:
                print(f"【等待】 等待 {probe_interval} 秒后进行下一次探活...")
                time.sleep(probe_interval)
        raise TimeoutError("达到最大重试次数后，一个或多个探活失败")

    # 2. 等待模式
    elif "wait_seconds" in task:
        wait_sec = task["wait_seconds"]
        print(f"【等待】 等待 {wait_sec} 秒...")
        time.sleep(wait_sec)

    # 3. 立即继续
    else:
        print("→ 立即继续执行下一个任务.")


# ========================
#         主流程
# ========================

def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        print(f"正在连接 {SSH_HOST}...")
        client.connect(
            hostname=SSH_HOST,
            port=SSH_PORT,
            username=SSH_USER,
            password=SSH_PASSWORD,
            timeout=10
        )
        print("【成功】 SSH连接成功.")

        # 选择执行模式
        selected_indices = select_execution_mode(TASKS)
        
        if not selected_indices:
            print("【错误】 未选择任何任务，程序退出")
            return

        # 获取选中的任务列表
        selected_tasks = [TASKS[i] for i in selected_indices]
        total_selected = len(selected_indices)
        
        print(f"\n 任务总数: {total_selected}")

        for idx_in_list, task_idx in enumerate(selected_indices):
            task = TASKS[task_idx]
            task_name = task.get("name", f"任务 {task_idx + 1}")
            
            # 计算剩余任务的预计时间
            remaining_tasks = selected_tasks[idx_in_list:]
            estimated_total_time = estimate_total_time(remaining_tasks)
            estimated_minutes = estimated_total_time // 60
            
            print(f"\n--- 正在执行 {task_name} ({idx_in_list + 1}/{total_selected})，预计时间: {estimated_minutes}分钟 ---")
            ssh_execute(client, task["cmd"])
            handle_post_execution(task)

        print("\n【成功】 所有任务成功完成!")

    except Exception as e:
        print(f"【错误】 错误: {e}")
        raise
    finally:
        client.close()
        print("SSH连接已关闭.")


if __name__ == "__main__":
    main()