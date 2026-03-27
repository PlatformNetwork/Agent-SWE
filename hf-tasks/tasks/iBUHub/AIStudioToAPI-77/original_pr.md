# iBUHub/AIStudioToAPI-77 (original PR)

iBUHub/AIStudioToAPI (#77): fix: adapt to new AI Studio login flow

**中文：**
由于近期 AIStudio 更新，本分支已调整原有账号登录逻辑，取消了在 blank app 中启动代理的方式（该方式已不支持编辑）。现改为使用开发者预先创建的 app。因此不再支持 `WS_PORT` 环境变量，端口固定为 9998。

**English:**
Due to recent AIStudio updates, this branch has modified the original account login logic. The previous approach of starting the proxy within a blank app (which is no longer editable) has been removed. It now uses a pre-created app provided by the developer. As a result, the `WS_PORT` environment variable is no longer supported, and the port is fixed at 9998.


- close #73 
- close #76 
