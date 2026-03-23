-- rime.lua

-- 1. 定义一个专门写文件的工具函数
local function save_to_file(text)
   local date = os.date("%Y-%m-%d")
   -- 【注意】这里必须是你电脑上真实存在的文件夹路径
   local path = "D:\\my_log\\" .. date .. ".txt"
   
   -- 以追加模式打开
   local file = io.open(path, "a")
   if file then
      -- 加上时间戳并写入
      file:write(os.date("[%H:%M:%S] ") .. text .. "\n")
      file:close()
   end
end

-- 2. 定义 logger 模块（这是一个表）
logger = {}

-- 3. 初始化：监听“提交”信号
-- 只有当文字真正上屏（Commit）时，才会触发这里，无论是打字还是语音
function logger.init(env)
   env.notifier = env.engine.context.commit_notifier:connect(function(ctx)
      -- 获取刚刚上屏的文字
      local text = ctx:get_commit_text()
      if (text ~= "") then
         save_to_file(text)
      end
   end)
end

-- 4. 处理器主函数
-- 这里我们什么都不拦截，直接返回 2 (kNoop)，保证不影响你正常打字
function logger.func(input, env)
   return 2 
end

-- 5. 收尾：断开监听
function logger.fini(env)
   if env.notifier then
      env.notifier:disconnect()
   end
end