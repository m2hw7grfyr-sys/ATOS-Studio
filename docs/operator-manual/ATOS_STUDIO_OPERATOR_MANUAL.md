# ATOS Studio 操作人员说明书

Version: 0.1

Status: Draft

## 1. 系统介绍

ATOS 负责发现内容、抓取来源、分析线索和把候选内容送入 Studio。

ATOS Studio 负责把候选内容整理成可生产的内容资产，包括内容池、主题包、AI 分析和后续 GPT 编导输入。

当前版本不会生成视频，不会发布内容。配置 ComfyUI 后，可以生成 Scene 图片。

## 2. 当前工作流程

```text
内容池
↓
主题包
↓
AI分析
↓
GPT编导
↓
视频生产（未来）
```

## 3. 页面说明

### 首页

首页显示 Studio 服务状态、内容池数量、主题包数量、ATOS 连接状态和数据库状态。

### 内容池

内容池显示从 ATOS 导入或推送来的来源内容。

可执行：

- 查看内容详情
- 批准
- 拒绝
- 归档
- 批量审核
- 从所选内容创建主题包

### 主题包

主题包是一组围绕同一问题、痛点或内容方向的来源集合。

可执行：

- 创建主题包
- 添加来源
- 移除来源
- 设置主要来源
- 调整来源排序
- 查看相似主题提示
- 合并主题包
- 批准、拒绝、归档主题包
- 创建 AI 分析任务
- 生成主题智能分析
- 查看主题智能分析历史版本

### GPT编导

GPT 编导页用于把主题包和 AI 分析结果整理成可复制给 ChatGPT 的 Prompt。

当前只支持：

- 查看主题包输入
- 查看 AI 分析结果
- 生成 GPT Prompt 文本
- 复制 Prompt 到 ChatGPT
- 粘贴并保存 GPT 返回的 Editorial Brief JSON
- 查看 Editorial Brief 历史版本
- 将 Brief 标记为审核中或已批准

### 账号管理

账号管理页用于维护 Persona 和真实发布账号。

当前只保存生产规划，不会自动登录、不会自动发布。

可执行：

- 创建 Persona
- 禁用 Persona
- 添加 Social Account
- 绑定 Social Account 到 Persona

### 视频项目

视频项目页用于查看从 Editorial Brief 创建的视频生产计划。

当前只做管理，不执行视频生成。

可查看：

- 项目基础信息
- 绑定 Persona
- 绑定发布账号
- Script
- Scenes
- Generation 状态占位

## 4. 按钮说明

### 内容池按钮

| 按钮 | 功能 | 输入 | 输出 | 注意事项 |
| --- | --- | --- | --- | --- |
| 批准 | 将内容标记为 approved | 内容项 | 审核状态变更 | 不会自动创建主题包 |
| 拒绝 | 将内容标记为 rejected | 内容项 | 审核状态变更 | 危险操作，需确认 |
| 归档 | 将内容标记为 archived | 内容项 | 审核状态变更 | 不物理删除 |
| 用所选内容创建主题包 | 把多条内容组织成主题包 | 选中的内容项 | 新主题包 | 内容本身状态不自动改变 |

### 主题包按钮

| 按钮 | 功能 | 输入 | 输出 | 注意事项 |
| --- | --- | --- | --- | --- |
| AI分析 | 创建默认 AI 分析任务 | 主题包 | pending AI jobs | 不会自动生成视频脚本 |
| 生成主题智能分析 | 创建主题包级智能分析任务 | 主题包、多条来源、评论、互动指标 | pending topic_intelligence_analysis job | 不会自动调用视频生成 |
| 重新分析 | 创建新的主题智能分析任务 | 主题包当前上下文 | 新版本分析 | 不覆盖旧结果 |
| 执行 | 执行某个 AI Job | AI Job | completed 或 failed | Provider 不可用时安全失败 |
| 进入GPT编导 | 打开 GPT 编导交换区 | 主题包 | Prompt 文本 | 需要人工复制或粘贴 |
| 设为主要来源 | 标记主题包主来源 | 来源内容 | 主来源更新 | 每个主题包仅一个主来源 |
| 上移 / 下移 | 调整来源顺序 | 来源内容 | position 更新 | 保存人工排序 |
| 合并到当前 | 合并相似主题包 | 来源主题包 | 来源合并、来源包归档 | 不物理删除来源包 |

### GPT编导按钮

| 按钮 | 功能 | 输入 | 输出 | 注意事项 |
| --- | --- | --- | --- | --- |
| 加载 | 加载所选主题包 | 主题包 | 输入区刷新 | 不调用 AI |
| 生成GPT Prompt | 根据主题包和主题智能分析生成 Prompt | 主题包 | 可复制 Prompt | 不调用 GPT API |
| 复制Prompt | 复制 Prompt 到剪贴板 | Prompt 文本 | 剪贴板内容 | 需要浏览器支持剪贴板 |
| 解析并保存 | 校验并保存 GPT 返回 JSON | GPT Output JSON | 新 Editorial Brief 版本 | JSON 必须符合字段要求 |
| 进入审核 | 将 Brief 状态改为 reviewing | Brief | 状态更新 | 不影响旧版本 |
| 批准 | 将 Brief 状态改为 approved | Brief | 状态更新 | 为后续视频生产准备 |

## 5. AI说明

运营人员无需选择模型。

系统策略：

1. 本地模型优先。
2. OpenAI GPT 作为可选备用。
3. 所有 AI 调用必须经过 Studio AI Service。
4. Provider 未配置或不可用时，Studio 不会崩溃。
5. API Key 不会显示在页面或日志中。

当前版本只保存 AI 分析结果，不生成正式视频脚本。

## 6. AI主题分析使用说明

### 什么是主题分析

主题分析是对一个主题包进行综合判断。

它的输入不是单个帖子，而是：

- 主题包基本信息
- 多条来源内容
- 帖子正文
- 平台信息
- 作者信息
- 评论数据
- 互动指标

输出包括：

- 核心问题
- 用户画像
- 高频痛点
- 情绪触发点
- 争议点
- 高价值用户原话
- 内容机会
- 视频方向建议
- 机会评分

### 为什么不是分析单个帖子

单个帖子容易有偶然性。

主题包把多个相似讨论合并后，AI 更容易判断：

- 哪些痛点是真高频
- 哪些表达只是个别用户情绪
- 哪些用户原话更适合做内容 Hook
- 哪些角度更值得进入 GPT 编导

### 如何选择主题包

优先选择：

- 来源数大于 2 的主题包
- 评论数较高的主题包
- 多个平台重复出现的痛点
- 风险等级不是 high 的主题包
- 内容角度已经比较明确的主题包

避免选择：

- 来源太少的主题包
- 信息严重缺失的主题包
- 明显违规或高风险主题
- 只是新闻搬运、没有用户痛点的主题

### 如何运行 AI 分析

1. 打开 `主题包`。
2. 进入某个主题包详情。
3. 点击 `生成主题智能分析`。
4. 在 AI 任务列表中找到 `topic_intelligence_analysis`。
5. 点击 `执行`。
6. 等待状态变为 `completed`。
7. 查看 `主题智能分析` 区域。

### 如何重新分析

点击 `重新分析` 会创建新的 AI Job。

旧结果不会被覆盖，页面会显示：

- Analysis Version 1
- Analysis Version 2
- 后续版本

用于比较不同模型、Prompt 或上下文变化后的分析质量。

### 如何判断结果质量

重点检查：

- 核心总结是否覆盖整个主题包，而不是只复述某一个帖子。
- 痛点是否具体。
- 情绪触发点是否能用于标题、Hook 或脚本冲突。
- 用户原话是否有来源。
- 内容机会是否能直接进入 GPT 编导。
- 视频方向是否符合目标平台。

如果结果过泛，建议：

- 补充更多来源内容。
- 增加评论数据。
- 修改 Prompt 模板。
- 重新分析。

### 如何进入 GPT 编导

主题智能分析完成后，点击 `进入GPT编导`。

GPT 编导会读取：

- 主题包
- 来源内容
- AI 分析结果

然后生成可复制给 ChatGPT 的编导 Prompt。

## 7. GPT编导交换区操作说明

### 什么时候使用GPT编导

当主题包已经完成主题智能分析，并且你准备把它整理成短视频编导方案时，使用 GPT 编导。

不要在以下情况使用：

- 主题包没有来源内容。
- 主题包还没有主题智能分析。
- 主题仍处于高风险或不确定状态。
- 你还没有确认该主题适合进入内容生产。

### 如何生成Prompt

1. 打开 `主题包`。
2. 进入一个已完成主题智能分析的主题包。
3. 点击 `进入GPT编导`。
4. 在 GPT 编导页点击 `生成GPT Prompt`。
5. 页面会生成完整 Prompt。

Prompt 会包含：

- 主题包信息
- 来源数量
- 平台分布
- 核心总结
- 用户画像
- 痛点
- 用户原话
- 内容机会
- 输出 JSON 格式要求

### 如何复制Prompt到ChatGPT

1. 点击 `复制Prompt`。
2. 打开 ChatGPT。
3. 粘贴 Prompt。
4. 等待 ChatGPT 输出 JSON。

当前系统不会自动调用 OpenAI API，也不会替你完成 ChatGPT 对话。

### 如何处理GPT返回结果

ChatGPT 返回内容必须是 JSON。

必须包含：

- title
- hook
- script
- scenes
- caption

每个 scene 必须包含：

- scene_number
- duration
- visual_prompt
- voiceover
- subtitle

可选字段：

- camera_direction
- target_audience
- hashtags

### 如何粘贴JSON

1. 回到 GPT 编导页。
2. 找到 `GPT Output JSON`。
3. 粘贴 ChatGPT 返回的完整 JSON。
4. 点击 `解析并保存`。

如果 JSON 不合法，系统会提示具体错误，例如：

- GPT Output JSON 不是合法 JSON
- 缺少 scenes 字段
- scenes 字段不能为空
- 第 1 个 scene 缺少 voiceover 字段

### 如何审核脚本

保存后，系统会生成一个新的 Editorial Brief 版本。

你需要检查：

- 标题是否准确
- Hook 是否抓住核心痛点
- 脚本是否符合平台风格
- 分镜是否能被后续视频系统理解
- voiceover 和 subtitle 是否清晰
- visual_prompt 是否可用于图像或视频生成

### 如何批准进入下一阶段

检查无误后点击 `批准`。

批准后状态变为：

`approved`

未来视频生产模块会读取已批准的 Editorial Brief。

### 操作人员不需要理解的内容

操作人员只需要按页面流程操作，不需要理解：

- LLM
- API
- 数据库
- Prompt Template 内部结构
- 视频模型
- ComfyUI 图片生成已支持；视频生成未支持

## 8. Persona与账号管理

### 什么是Persona

Persona 是账号人格设定。

它描述一个账号应该像谁、对谁说话、用什么语气、避免什么表达。

系统默认内置一个 Persona：

`Brainy（小脑瓜）`

定位：

深夜想法的陪伴者 / 你的精神内耗代言人。

默认账号：

TikTok `@TiredBrainClub`

例如：

```json
{
  "identity": "college student",
  "age_range": "18-25",
  "tone": "casual",
  "language": "american english",
  "style": "personal storytelling",
  "avoid": ["medical claims"]
}
```

### 为什么不同账号需要不同人格

不同账号面对的人群、内容风格和风险边界不同。

例如：

- 学生人设适合个人经历表达。
- 教育人设适合解释型内容。
- 效率教练适合方法论内容。

把 Persona 固定下来，可以让后续 Prompt、脚本和视觉风格更一致。

### 如何创建Persona

1. 打开 `账号管理`。
2. 在 `创建 Persona` 区域填写名称、描述、目标用户和风格。
3. 填写 Persona Profile JSON。
4. 点击 `创建`。

### 如何绑定账号

1. 在 `添加 Social Account` 区域填写平台和用户名。
2. 选择一个 Persona。
3. 选择状态：testing、active 或 inactive。
4. 点击 `添加账号`。

一个 Persona 可以绑定多个账号。

### 如何禁用Persona

在 Personas 列表点击 `禁用`。

禁用后，该 Persona 不应再用于新的视频项目。

## 9. 视频项目管理

### Persona模式与通用模式

创建视频项目时有两种模式：

- 通用模式：不选择 Persona，也不绑定发布账号。适合先做普通脚本规划，后面再决定账号。
- Persona模式：选择一个 Persona，并可选择该 Persona 绑定的发布账号。适合固定账号人格、语气和视觉风格的内容。

系统自带 `Default Creator`，用于通用创作参考。但通用模式不会强制绑定任何 Persona。

建议：

- 账号风格已经明确时，用 Persona模式。
- 只是测试选题、脚本或分镜时，用通用模式。

### 什么是Generation Pipeline

Pipeline 是一次完整视频生产计划。

一个视频项目可以创建一个或多个 Pipeline。

Pipeline 会拆成多个 Task，例如：

- 图片生成
- 视频生成
- 配音
- 字幕
- 合成

当前版本只创建计划，不自动生成文件。

### 什么是Generation Task

Task 是 Pipeline 里的具体步骤。

常见状态：

- pending：已创建但未排队
- queued：已进入队列
- running：执行中
- paused：暂停
- completed：完成
- failed：失败
- cancelled：取消

当前可执行的是 ComfyUI 图片生成；Wan、FLUX、TTS、FFmpeg 等外部视频服务仍未接入。

### 从Editorial Brief创建项目

1. 打开 `GPT编导`。
2. 选择主题包和 Persona。
3. 保存一个合法的 Editorial Brief JSON。
4. 在历史版本列表中选择 `通用模式` 或 `Persona模式`。
5. Persona模式下选择发布账号。
6. 点击 `创建视频项目`。

系统会创建 Video Project，并从 Brief 的 `scenes` 初始化分镜。

### 创建生成计划

1. 打开 `视频项目`。
2. 进入某个项目详情。
3. 点击 `创建生成计划`。
4. 打开 `生成队列` 查看任务。

生成计划会自动拆分：

- 每个分镜一条图片生成任务。
- 每个分镜一条视频生成任务。
- 整体配音任务。
- 整体字幕任务。
- 最终合成任务。

### 查看生成队列

打开左侧菜单 `生成队列`。

可以查看：

- Task ID
- 项目
- 类型
- Provider
- 状态
- 创建时间
- 更新时间

也可以按状态、类型和 Provider 筛选。

### 为什么当前没有自动生成

Sprint 09 的目标是建立生产队列和 Provider Adapter 架构。

它只负责：

- 拆分任务
- 保存任务上下文
- 展示队列状态
- 为后续模型接入预留接口

它不会：

- 调用视频模型
- 调用 TTS
- 调用 FFmpeg
- 自动生成视频
- 自动发布

## 10. 图片生成流程

### 什么是Generation Task

Generation Task 是一次生成动作。

例如：

- 某个 Scene 的图片生成
- 某个 Scene 的视频生成
- 整条视频的配音
- 字幕
- 合成

当前可执行的是：

`image_generation`

也就是 Scene 图片生成。

### 什么是Provider

Provider 是实际执行生成的工具。

当前已接入：

`ComfyUI`

未接入：

- Wan
- FLUX
- CogVideoX
- TTS
- FFmpeg
- Kling
- Runway
- Veo

如果 ComfyUI 没有开启，系统仍然可以打开，只是图片生成任务会失败并显示错误。

### 如何生成Scene图片

1. 打开 `视频项目`。
2. 进入某个视频项目详情。
3. 找到 `Scenes`。
4. 在某个 Scene 右侧点击 `生成图片`。
5. 系统会创建一条 `image_generation` 任务。
6. 如果 ComfyUI 可用，任务会提交到 ComfyUI。
7. 生成完成后，图片会作为 Asset 保存并显示在 Scene 预览中。

### 如何查看结果

可以在两个地方查看：

- `视频项目详情`：查看 Scene 图片预览。
- `生成队列`：查看 Task 状态、Provider Task ID 和 Asset 数量。

### 失败如何处理

常见失败原因：

- ComfyUI 没有启动。
- `COMFYUI_URL` 不正确。
- Workflow JSON 不是可执行的 ComfyUI API workflow。
- ComfyUI 生成中断或超时。

处理方式：

1. 检查 ComfyUI 是否能打开。
2. 检查 Studio 的 ComfyUI 配置。
3. 检查 `生成队列` 中的错误状态。
4. 修正后重新点击 `生成图片`。

当前版本不会自动重试，也不会自动执行视频生成。

## 11. Workflow管理说明

### 什么是Workflow

Workflow 是 ComfyUI 的生成流程配置。

它决定：

- 使用哪些节点
- 使用哪些模型
- 输入 Prompt 放在哪里
- 输出图片从哪里获取

Studio 不会把 Workflow 写死在代码里。

操作人员需要在 `Workflow管理` 页面导入 Workflow。

### 如何导入Workflow

1. 打开左侧菜单 `Workflow管理`。
2. 在 `导入Workflow` 区域填写名称、描述、Provider 和类型。
3. 将 ComfyUI 导出的 API workflow JSON 粘贴到 `Workflow JSON`。
4. 填写标签，例如 `realistic`、`portrait`、`ugc`。
5. 如果该 Workflow 需要指定模型，在 `需要模型 JSON` 中填写。
6. 点击 `导入Workflow`。

导入后状态为：

`draft`

### 如何测试Workflow

1. 在 Workflow 列表中找到目标 Workflow。
2. 点击 `测试Workflow`。
3. 系统会检查 Workflow JSON、Provider 状态和模型能力。
4. 测试成功后状态变为 `available`。
5. 测试失败会保留错误信息。

### 如何启用Workflow

当前版本通过测试后自动标记为：

`available`

只有 `available` 的 Workflow 会出现在视频项目 Scene 的生成选择框中。

### 如何处理Workflow失败

常见原因：

- JSON 不是合法格式。
- Workflow 缺少节点。
- Provider 不是 `comfyui`。
- ComfyUI 没有启动。
- 需要的模型没有登记为 `available`。

处理方式：

1. 检查 Workflow JSON。
2. 确认 ComfyUI 正常运行。
3. 到模型能力区域添加或修正模型。
4. 再次点击 `测试Workflow`。

## 12. 模型能力说明

### 什么是模型能力

模型能力表示当前服务器可用哪些模型。

例如：

- `FLUX.1 Schnell`
- Provider：`comfyui`
- Type：`image`
- Status：`available`

### 模型状态

- `available`：可以使用。
- `missing`：应存在但当前不可用。
- `disabled`：暂时禁用。

### Provider状态

Provider 是执行生成的服务。

当前 Provider：

`ComfyUI`

如果 Provider 离线，生成任务会失败，并在生成队列显示：

`provider_offline`

### 为什么生成前需要检查

生成前检查可以避免：

- Workflow 不可用还继续提交。
- 模型不存在导致 ComfyUI 报错。
- Provider 离线时任务卡住。

如果检查失败，任务会直接变为 `failed`，并显示原因：

- `workflow_not_available`
- `provider_offline`
- `missing_model`

### 选择Persona

Persona 会影响 GPT Prompt。

生成 Prompt 前选择 Persona，Prompt 会包含：

- Identity
- Tone
- Audience
- Language
- Style
- Voice
- Avoid rules

### 选择发布账号

发布账号会按照 Persona 过滤。

例如选择 Sarah Persona 后，只显示绑定 Sarah 的 TikTok、YouTube 等账号。

### 查看生产状态

打开 `视频项目` 页面。

详情页显示：

- 基础信息
- Script
- Scenes
- Generation 状态

当前 Generation 状态会显示 Pipeline 和 Task：

- 图片生成
- 视频生成
- 配音
- 合成

Sprint 11 支持 Workflow 管理、模型能力登记和 ComfyUI 图片生成前检查。视频生成、配音、字幕、合成仍未实现。

## 12.1 Creator Workspace 场景生产工作台

Creator Workspace 是视频项目详情页的升级版本。

它不是一个新的项目系统。

它把以下操作集中在同一个页面：

- 查看项目上下文
- 查看主题智能分析摘要
- 编辑 Editorial Brief
- 新增、编辑、复制、删除 Scene
- 调整 Scene 顺序
- 复制 Voiceover、Image Prompt、Video Prompt、Negative Prompt、On-screen Text
- 复制完整 Scene
- 复制完整项目
- 触发 Scene 图片生成
- 查看 Scene 最新图片资产

### 进入方式

打开：

`视频项目`

点击某个项目的：

`查看`

进入后页面标题显示：

`Creator Workspace`

### Project Context

Project Context 显示：

- Title
- Status
- Creation Mode
- Persona
- Social Account
- Topic Package
- Editorial Brief
- Updated At

如果项目没有绑定 Persona，系统会显示：

`Default Creator`

这表示当前项目使用通用创作模式。

### Topic Intelligence Summary

Topic Intelligence Summary 默认折叠。

展开后可以查看：

- Topic Summary
- Audience
- User Pain Points
- Core Emotion
- Content Opportunity
- Recommended Angle
- Useful User Language

这里的数据来自主题包的 AI 分析结果。

如果还没有运行主题智能分析，页面会显示暂无内容。

### Editorial & Script

这里可以编辑：

- Content Goal
- Main Angle
- Hook
- Core Message
- Call to Action
- Tone
- Platform
- Target Duration

修改后点击：

`保存 Editorial Brief`

系统会保存到当前 Editorial Brief，不会创建新版本。

如果需要多个版本，请回到 GPT 编导流程重新生成 Editorial Brief。

### Scenes

每个 Scene 支持：

- 保存
- 删除
- 复制
- 上移
- 下移
- 复制完整 Scene
- 生成图片

Scene 字段包括：

- Scene Title
- Purpose
- Duration Seconds
- Visual Description
- Voiceover Script
- On-screen Text
- Image Prompt
- Video Prompt
- Negative Prompt
- Camera Direction

### 复制功能

每个文本区旁边都有复制按钮。

常用复制项：

- Voiceover Script
- On-screen Text
- Image Prompt
- Video Prompt
- Negative Prompt

页面顶部支持：

`复制完整项目`

适合把项目、主题分析、Editorial Brief 和所有 Scenes 一次性复制给外部工具。

### 图片生成

Scene 下方保留：

`生成图片`

点击后会沿用已有流程：

Scene

↓

Generation Task

↓

ComfyUI Adapter

↓

Asset

↓

Scene 图片预览

如果 ComfyUI 没有配置，页面会提示：

`ComfyUI 未配置。`

此时仍然可以编辑和复制文本，不影响编导工作。

## 12.2 任务控制中心与人工审核

任务控制中心用于在生成前做最后人工审核。

入口：

`任务中心`

任务中心显示：

- 任务标题
- 内容来源
- 创建时间
- 更新时间
- 当前状态
- 当前步骤
- 审核状态
- 生成进度
- 重试次数
- 最终输出状态

### 状态筛选

支持筛选：

- 全部
- 待编辑
- 待审核
- 审核通过
- 生成中
- 已完成
- 失败

也可以按创建时间或更新时间排序。

### 任务详情

点击任务标题进入详情页。

详情页包含：

- 基础信息
- ATOS 来源内容
- GPT 编辑内容
- Scene 预览
- 生成状态
- 生成结果

### GPT JSON 编辑

在任务详情页可以编辑 GPT Output JSON。

操作流程：

1. 修改 JSON。
2. 点击 `保存 JSON`。
3. 点击 `重新解析`。
4. 查看 Scene 预览。

如果 JSON 不合法，系统会提示错误。

无效 JSON 不会覆盖上一次有效 Scene。

### 人工审核流程

任务默认是：

`draft`

提交审核：

`draft → pending_review`

审核通过：

`pending_review → approved`

退回修改：

`pending_review → rejected`

退回时可以填写审核备注，例如：

- 第 2 个场景画面描述需要修改
- 旁白过长
- 视频节奏不合适

退回后，修改 JSON 并保存，会回到 `draft`，可以重新提交审核。

### 生成限制

只有审核状态为：

`approved`

的任务才允许开始生成。

以下状态不能开始生成：

- draft
- pending_review
- rejected
- running
- completed

这是后端校验，不只是页面按钮限制。

### 失败与重试

如果生成任务失败，任务详情和生成队列会显示：

- 当前步骤
- 失败步骤
- 错误信息
- 重试次数

失败任务可以点击：

`从失败步骤重试`

系统会跳过已完成步骤，从失败步骤继续。

## 13. 常见问题

### AI任务失败

可能原因：

- 本地 Ollama/vLLM 未启动
- 模型名称配置错误
- OpenAI Provider 关闭
- Prompt 模板被禁用

处理：

1. 检查 `/api/ai/health`。
2. 检查 Prompt 模板是否 enabled。
3. 确认本地 LLM 服务是否可用。

### GPT编导保存失败

通常是 JSON 格式不合法。

请先确认输入内容是合法 JSON，例如：

```json
{
  "hook": "Why your medication feels like it stops too early",
  "structure": []
}
```

## 14. 当前未实现能力

- 视频生成
- Wan / FLUX / CogVideoX
- TTS
- 字幕
- FFmpeg
- 自动发布
- 自动调用 GPT 生成完整视频脚本
