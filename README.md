  

# Input-Stream-Logger

  

> **基于 Rime 输入法与 CapsWriter 的本地输入收集方案**

> 无感记录你的每一次按键与语音，为个人 AI 知识库构建提供原始数据集。

注：本项目构建日期为3.23日，后续开源项目可能会做修改导致不适配

---

  

## 1. 前置准备


 ### Rime (小狼毫) 安装

- **下载地址**：[Rime Weasel Release](https://github.com/rime/weasel/releases)

- **安装建议**：建议安装到非系统盘（如 `D:\Rime_Config`），方便后续管理配置。

- **输入方案**：初步配置选“朙月拼音·简化字”即可，本项目后续配置文件也是基于这个选项

  

<details>

<summary> <b>展开：如何将 Rime 设置为 Windows 默认输入法 (Win11)</b></summary>

  

1. 按下 `Win + I` 打开 **设置**。

2. 点击左侧的 **“时间和语言”** > 右侧的 **“输入”**。

3. 点击 **“高级键盘设置”**。

4. 在 **“替代默认输入法”** 下拉菜单中，选择：**`中文(简体) - 小狼毫`**。

  

</details>



## 2. Rime 输入法配置

> **原理**：利用 Rime 的 patch 机制挂载 Lua 脚本，监听每一次文本上屏动作。

我们已经为你准备好了两个关键文件，位于项目的 `Rime_Config` 目录下：

1.  [`luna_pinyin_simp.custom.yaml`](./Rime_Config/luna_pinyin_simp.custom.yaml)  (拦截器配置开关)
2.  [`rime.lua`](./Rime_Config/rime.lua)  (核心逻辑脚本)


将上述两个文件，直接**复制并覆盖**到你的 Rime 用户文件夹根目录（如果按照上面说的自定义的话是 `D:\Rime_Config` ，如果按照软件默认设置应该是类似 `%APPDATA%\Rime`的形式）。

####  **重要：修改日志存储路径！**

`rime.lua` 文件中默认将日志存放在 D 盘。**如果你的电脑没有 D 盘，或者想自定义位置，请务必修改！**

👉 **操作方法**：
用记事本打开 `rime.lua`，找到 **第 7 行**：
```lua
-- 【注意】这里必须是你电脑上真实存在的文件夹路径
local path = "D:\\my_log\\" .. date .. ".txt"
```

我们将路径修改为你想要的文件夹（例如 `C:\\Users\\User\\Documents\\`）。
**注意：Windwos路径中的反斜杠 `\` 需要写成双斜杠 `\\` 转义！**
