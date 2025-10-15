# 远程脚本自动执行器 RemoteAutoSheller

## 项目概述

这是一个用于远程SSH连接到服务器，停止和重新启动一系列服务，并监控它们是否成功启动的Python脚本。该脚本适用于复杂的微服务架构环境，可以按顺序管理多个相关联的容器服务。具有顺序执行，指定任务执行，指定起始任务的顺序执行的功能，运维人的脱手神器！

当前版本: v1.0.0 alpha

[工作原理](#工作原理) | [使用方法](#使用方法) | [注意事项](#注意事项) | [配置说明](#配置说明) | [版本说明](#版本说明)


## 工作原理

1. 脚本通过SSH连接到远程服务器
2. 按照预定义的顺序执行一系列任务
3. 每个任务可以是执行命令、等待一段时间或执行带有健康检查的命令
4. 脚本会等待所有任务完成，期间可能包含健康检查探活操作

## 使用方法

1. 安装依赖

   ```shell
   pip install paramiko requests pyyaml
   ```

2. 修改config.yaml配置文件中的SSH连接信息和任务列表

2. 运行脚本：
   ```shell
   python RemoteShellerCLI.py
   ```

3. 根据提示选择执行模式：
   - 全部执行：按顺序执行所有任务
   - 指定步骤执行：选择特定的多个任务执行
   - 从指定步骤开始执行：从指定任务开始执行到结束

## 注意事项

1. 确保远程服务器上已安装ssh
2. 确保运行脚本的机器可以访问远程服务器的SSH端口
3. 脚本会严格按照TASKS列表中的顺序执行任务
4. 如果任何任务失败，脚本会停止执行并显示错误信息
5. 探活检查会在达到最大重试次数后仍然失败时终止脚本
6. 探活失败后会等待指定时间（默认30秒）再进行下一次尝试
7. HTTP探活会忽略SSL证书验证，适用于自签名证书环境
8. 建议先在测试环境中验证配置后再在生产环境中使用
9. 目前探活仅支持HTTP和TCP探活，内置服务探活在后续版本中添加

## 配置说明

### 1. SSH连接配置

SSH连接配置现在保存在`example.yaml`文件中：

```yaml
ssh:
  host: "your_remote_host"      # 远程服务器IP地址或域名
  port: 22                      # SSH端口号，默认为22
  user: "your_username"         # 登录用户名
  password: "your_password"     # 登录密码
```

### 2. 任务配置

所有任务也都在`example.yaml`文件中的`tasks`列表中定义，每个任务是一个字典对象，包含以下字段：

#### 基本命令执行
```yaml
- name: "任务名称"              # 任务名称，用于显示执行进度
  cmd: "要执行的命令"
```

#### 带等待时间的命令
```yaml
- name: "任务名称"
  cmd: "要执行的命令"
  wait_seconds: 100             # 执行命令后等待的秒数
```

#### 带探活检查的命令
```yaml
- name: "任务名称"
  cmd: "要执行的命令"
  probe_timeout: 15             # 探活超时时间（秒）
  probe_interval: 30            # 探活失败后的等待时间（秒）
  probe_retries: 25             # 探活重试次数
  probes:                       # 探活配置列表
    - type: "http"              # 探活类型，支持http和tcp
      url: "https://example.com/health"  # HTTP探活的URL
```

### 3. 探活配置

探活机制用于确认服务是否已成功启动并可正常访问。

#### HTTP探活
检查HTTP(S)端点是否返回200状态码：
```yaml
- type: "http"
  url: "https://example.com/health"
```

#### TCP探活
检查指定主机和端口是否可连接：
```yaml
- type: "tcp"
  host: "example.com"
  port: 8080
```

#### 多探活配置
对于依赖多个服务的复杂应用，可以配置多个探活项：
```yaml
- name: "任务名称"
  cmd: "docker-compose -f app.yml up -d"
  probe_timeout: 15
  probe_interval: 30
  probe_retries: 25
  probes:
    - type: "http"
      url: "https://example.com/service1/health"
    - type: "http"
      url: "https://example.com/service2/health"
```

注意：每个探活项应该是独立的配置对象，不应在单个探活项中使用URL数组。

## 版本说明

**当前版本：v1.0.0 alpha**

主要的更新：

- 实现了基础的远程命令执行功能，并且可以按顺序执行多个任务
- 实现了3种任务类型：命令执行、等待、带探活的命令执行
- 添加了多探活功能，可以同时检查多个服务是否已启动并正常访问
- 解决了探活时提示证书验证的错误，以及忽略证书验证警告（本地测试环境适配）
- 支持将配置文件保存为YAML格式，运行时读取YAML文件，并执行任务列表中的任务