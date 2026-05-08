<div align="center">

# 🐾 Open Pets

### 给 [Codex CLI](https://github.com/openai/codex) 与 [Claude Code](https://www.anthropic.com/claude-code) 准备的桌面宠物工坊

**🌟 内置 AI Skill —— 让 agent 全自动完成"生图 → 切帧 → 校验 → 安装"**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)
[![Skill](https://img.shields.io/badge/Skill-open--pet--creator-blueviolet.svg?style=flat-square)](open-pet-creator/SKILL.md)
[![Codex CLI](https://img.shields.io/badge/Codex_CLI-supported-success.svg?style=flat-square)](https://github.com/openai/codex)
[![Claude Code](https://img.shields.io/badge/Claude_Code-supported-success.svg?style=flat-square)](https://www.anthropic.com/claude-code)
[![GitHub Stars](https://img.shields.io/github/stars/EASYGOING45/open-pets?style=flat-square&color=yellow)](https://github.com/EASYGOING45/open-pets/stargazers)
[![Petdex](https://img.shields.io/badge/Petdex-published-ff69b4.svg?style=flat-square)](https://petdex.crafter.run/)

[English](./README.en.md) · **简体中文**

<table>
<tr>
<td align="center" width="33%">
  <img src="pets/phrolova/spritesheet-repacked-preview.png" width="220"><br>
  <b>Phrolova</b> · <i>鸣潮</i><br>
  <code>npx petdex install phrolova</code><br>
  <a href="https://petdex.crafter.run/zh/pets/phrolova">Petdex 主页 →</a>
</td>
<td align="center" width="33%">
  <img src="pets/pink-star/spritesheet-repacked-preview.png" width="220"><br>
  <b>粉星仔</b> · <i>洛克王国</i><br>
  <code>npx petdex install pink-star</code><br>
  <a href="https://petdex.crafter.run/zh/pets/pink-star">Petdex 主页 →</a>
</td>
<td align="center" width="33%">
  <img src="pets/rocom-dimo/spritesheet-repacked-preview.png" width="220"><br>
  <b>迪莫</b> · <i>洛克王国</i><br>
  <sub>仅本仓库（待上架 Petdex）</sub>
</td>
</tr>
</table>

</div>

---

## 💡 这个仓库为什么特别？

> **它不止是一个宠物素材库——它本身就是一份可复用的 Skill。**

很多人会做几张宠物素材发到网上，但要让 AI agent 真正"理解"如何把它打包成符合 Codex 协议的桌面宠物，靠零散的脚本远远不够。`open-pet-creator` 把这个领域知识完整封装成了 **Codex CLI / Claude Code 通用的 Skill**：

- 你说一句"帮我把这张精灵图打包成桌面宠物"，agent 就会自动加载这份 Skill
- Skill 里写好了**契约**（1536×1872 / 8×9 网格 / 192×208 单元）、**调参规则**（`--scale` 与 `--offset-y` 的 trade-off）、**踩坑预案**（生成器源图列宽不齐时切换 `--detect-sprites`）
- 还附带 4 个确定性脚本：`repack` / `inspect` / `validate` / `install`，可被 agent 串起来组成完整流水线

> **🤖 → 这就是 Skill 的核心价值**：把人类专家的领域知识 + 工具，喂给 AI agent，让它在合适场景自动调用。Open Pets 同时是宠物商城 + Skill 范例 + 工具集合。

---

## 📦 仓库内含

<table>
<thead>
<tr><th>组件</th><th>说明</th><th>位置</th></tr>
</thead>
<tbody>
<tr>
<td>🤖 <b>open-pet-creator Skill</b></td>
<td>可被 Codex CLI 与 Claude Code 直接加载的 Skill 包，含 SKILL.md、4 个 Python 脚本、参考文档</td>
<td><a href="open-pet-creator/"><code>open-pet-creator/</code></a></td>
</tr>
<tr>
<td>🖥️ <b>OpenPets 桌面应用</b></td>
<td>Tauri 2 写的轻量级桌面渲染器（~5MB），直接读 <code>~/.codex/pets/</code>，让宠物脱离 Codex 也能在桌面动起来。<b>跨全屏 Space 可见</b>、可拖动、点击触发动画；托盘菜单 + 磨砂玻璃 picker 支持多宠物切换。<b>🤖 与 Claude Code 联动</b>：通过 hook 让宠物随 AI 对话状态自然切换（提问 → running，AI 回完 → waving）。macOS 优先，Linux/Windows 在路上</td>
<td><a href="app/"><code>app/</code></a></td>
</tr>
<tr>
<td>🐾 <b>三只可直接安装的宠物</b></td>
<td>Phrolova、粉星仔、迪莫，每只都包含 9 行 × 8 列完整原子图与 <code>pet.json</code></td>
<td><a href="pets/"><code>pets/</code></a></td>
</tr>
<tr>
<td>📝 <b>设计文档与生成提示词</b></td>
<td>每只宠物的设计描述与可粘贴到图像生成器的 Final Prompt，照抄即可做下一只</td>
<td><a href="docs/"><code>docs/</code></a></td>
</tr>
<tr>
<td>✅ <b>回归测试套件</b></td>
<td>锁定 Codex 原子图契约（网格、单元尺寸、未用格透明）的契约测试</td>
<td><a href="tests/"><code>tests/</code></a></td>
</tr>
</tbody>
</table>

---

## 🎯 核心工作流：用 Skill 造一只你想要的宠物

> **整个流程的主语都是 Skill。** 你只描述想做什么，剩下的"写提示词 → 等你生图 → 切帧打包 → 安装"全部由 Skill 驱动 agent 自动完成。

```mermaid
sequenceDiagram
    autonumber
    actor U as 你
    participant A as Codex / Claude Code agent
    participant S as open-pet-creator<br/>Skill
    participant G as gpt-image / Midjourney<br/>/ SDXL

    U->>A: "我想做一只 X 的桌面宠物"
    A->>S: 自动加载 Skill
    S-->>U: 输出针对 X 的设计文档<br/>+ 可粘贴的 Final Prompt
    U->>G: 把提示词喂给图像生成器
    G-->>U: 8×8 网格源图 PNG
    U->>A: "源图好了，在 ~/Downloads/x.png"
    A->>S: 调 repack → inspect → validate → install
    S-->>U: ✅ 1536×1872 原子图已生成<br/>✅ 已装到 ~/.codex/pets/x/
```

### 第 1 步 · 把 Skill 装进 agent 工具

一次安装、Codex 与 Claude Code 通用：

```bash
# Codex CLI
cp -R open-pet-creator ~/.codex/skills/open-pet-creator

# Claude Code
cp -R open-pet-creator ~/.claude/skills/open-pet-creator
```

> 安装好后无需手动调用——agent 看到"我想做 Codex 宠物"这类需求时会**自动加载** Skill。

### 第 2 步 · 告诉 agent 想要哪只，Skill 给你写提示词

> 👤 **你**："我想做一只皮卡丘的 Codex 桌面宠物。"
>
> 🤖 **Claude Code**（自动加载 `open-pet-creator` Skill）：
> 好的，我按 Skill 里的设计模板帮你写一份针对皮卡丘的设计文档与生成提示词，包含每行姿势规格、配色约束、签名特征……
>
> ✏️ 已生成：
> - `docs/pikachu-pet-design.md`（设计文档）
> - `docs/pikachu-generation-prompt.md`（含可直接粘贴的 **Final Prompt** 块）
>
> 拿这段 Final Prompt 去图像生成器跑一次，得到 1536×1664 的 8×8 网格源图（纯黑底），然后告诉我源图位置即可。

> 💡 **Skill 携带的领域知识让提示词不踩坑**：每行需要几帧、姿势如何描述、为什么要黑底（自动 alpha 抽取）、为什么要 8×8 网格（匹配 Codex 协议），全在 SKILL.md 里写好了。

### 第 3 步 · 用任意图像生成器跑出源图

把上一步拿到的 **Final Prompt** 粘贴到任意一种生成器：

| 工具 | 入口 | 特点 |
| --- | --- | --- |
| **OpenAI gpt-image-1 / GPT-4o Image** | API 或 ChatGPT 内 Image | 指令遵循度最好，**首选** |
| **Midjourney v6+** | Discord / Web | 角色一致性最强；网格可能要分行跑 |
| **SDXL + chibi LoRA** | Automatic1111 / ComfyUI | 适合本地化定制 |

> 💡 **一致性差**就分行单独跑再合并——Skill 的提示词模板里已经写了这个回退方案。

### 第 4 步 · 把源图交回 agent，Skill 帮你完成剩下所有事

源图存为 `pets/<pet>/spritesheet-source.png` 后告诉 agent：

> 👤 **你**："源图好了，在 `pets/pikachu/spritesheet-source.png`。"
>
> 🤖 **Claude Code**（继续用 `open-pet-creator` Skill）：
> 收到。源图来自图像生成器，按 Skill 规则自动启用 `--detect-sprites`（生成器源图列宽不齐的兜底）……
>
> ✅ **Repack**：1536×1872 RGBA WebP，全部 9 行通过 Codex 协议
> ✅ **Validate**：format / mode / 网格契约全部命中
> ✅ **Inspect**：所有行 `top_min ≥ 38`，idle bbox `121×155` 在推荐区间
>
> 是否同步到 `~/.codex/pets/pikachu/`？

> 💡 **调参规则也已沉淀进 Skill**：从保守的 `--scale 0.98` 起步、生成器源图必走 `--detect-sprites`、`top_min < 35` 时自动加 `--offset-y` —— 这些都不需要你记。

### 第 5 步 · Codex 召唤

```text
Codex Settings → Appearance → Pets → Custom pets → 选中你的宠物 → 输入 /pet
```

整个流程通常 **15–30 分钟**（瓶颈是图像生成器迭代速度）。Skill 抽走了所有重复劳动——写约束文档、记得切 `--detect-sprites`、调 `--scale/--offset-y`、跑契约校验、避免踩同样的坑。

---

## 🐾 想直接装现成的几只？

不想自己造也完全可以——三只示范宠物已经做好：

### 路线 A · 用 [Petdex](https://petdex.crafter.run/) 一行命令装好（最快）

[Phrolova](https://petdex.crafter.run/zh/pets/phrolova) 与 [Pink Star](https://petdex.crafter.run/zh/pets/pink-star) 已上架 Petdex：

```bash
npx petdex install phrolova
npx petdex install pink-star
```

装完后：**Codex Settings → Appearance → Pets → Custom pets → 选中宠物**，输入 `/pet` 召唤。

### 路线 B · 手动安装（适合迪莫，或离线/开发场景）

```bash
git clone https://github.com/EASYGOING45/open-pets.git
cd open-pets
mkdir -p ~/.codex/pets/rocom-dimo
cp pets/rocom-dimo/spritesheet.webp ~/.codex/pets/rocom-dimo/
cp pets/rocom-dimo/pet.json         ~/.codex/pets/rocom-dimo/
```

> 💡 迪莫尚未上架 Petdex，目前只能手动安装；后续上架后这里会同步更新。

---

## 🖥️ 桌面应用 — 让宠物跟着你的 AI 工作流

`app/` 下是一个 ~5MB 的 Tauri 2 桌面应用，**直接读 `~/.codex/pets/` 同样的格式**，把 Codex 宠物原子图渲染成永远在最上层的桌面伴侣——脱离 Codex CLI 也能跑。

```bash
cd app
npm install && npm run dev
```

第一次构建 30-60s。启动后宠物会出现在屏幕右下角，**跨全屏 Space 可见**，可拖动，点击触发挥手；右上角托盘菜单点 *Choose Pet…* 调出磨砂玻璃 picker 切换宠物。

### 🤖 与 Claude Code 实时联动

桌面应用监听 `~/.openpets/state.json`——任何能跑 shell 命令的工具都能驱动宠物动画。Claude Code 通过 5 个 hook 接管宠物状态：

| Claude Code 事件 | 触发时机 | 宠物状态 |
| --- | --- | --- |
| `SessionStart` | 新会话启动 | `idle`（站立） |
| `UserPromptSubmit` | 你按下回车提问 | `running`（跑动） |
| `Notification` | Claude 申请权限 / 等你决策 | `review`（侧脸思考） |
| `Stop` | Claude 一个 turn 回完 | `waving`（挥手 → 自动回 idle） |
| `SessionEnd` | 会话结束 | `idle` |

随便提一句话 → 宠物开始跑动 → 我回完 → 它挥手致意 → 安静下来。

完整安装步骤、Codex / Cursor 接入说明、`openpets-event` helper 的用法见 [`app/README.md`](app/README.md)。

> 💡 **未来**：用户不应手动编 `~/.claude/settings.json`。Phase 2.B 计划提供 `openpets connect <tool>` CLI 一键完成 hook 注入。

---

## 🤖 关于 open-pet-creator Skill

<details>
<summary><b>Skill 是什么？为什么我们要把它做成 Skill 而不是普通脚本？</b>（点开展开）</summary>

<br>

**Skill** 是 Codex CLI 与 Claude Code 都支持的一种"领域工具包"格式：把某个垂直领域的知识、约束、脚本、文档打包到一个目录里，agent 在合适场景会**自动加载**。

相比普通脚本：

| | 普通脚本 | Skill |
| --- | --- | --- |
| **使用方式** | 用户得自己读 README、记参数 | agent 看到相关需求自动加载 |
| **携带的知识** | 只有代码逻辑 | 代码 + 契约文档 + 调参规则 + 踩坑预案 |
| **跨工具复用** | 各家工具各搞一套 | Codex / Claude Code 通用同一份 Skill |
| **演化** | 每次升级都要通知用户 | agent 每次调用都读最新的 SKILL.md |

把"打包桌面宠物"做成 Skill，意味着任何写代码的 AI agent 在用户提"我想做个 Codex 宠物"时，都能站在我们已经踩过坑的肩膀上做事。

</details>

### Skill 提供的能力

| 命令 | 干啥 |
| --- | --- |
| ✂️ `repack_pet_atlas.py` | 把任意尺寸的源精灵图重排成 Codex 标准 1536×1872 / 8×9 / 192×208 原子图。**支持 `--detect-sprites`** 处理生成器产的列宽不齐源图 |
| 🔍 `inspect_pet_atlas.py` | 列出每行 sprite 的尺寸、居中位置、顶部留白，做调参依据 |
| ✅ `validate_pet_atlas.py` | 检查格式、透明度、网格契约 |
| 📦 `install_pet.py` | 一键安装到 `~/.codex/pets/<id>/` |

详细使用说明见 [`open-pet-creator/SKILL.md`](open-pet-creator/SKILL.md)，原子图契约见 [`references/codex-pet-atlas.md`](open-pet-creator/references/codex-pet-atlas.md)。

> ⚠️ **设计文档里有一条硬规矩**：不要照抄上一只宠物的 `--scale`——轮廓不同决定上限不同（高耳兔 ≤ 1.0；矮胖型可到 1.05+）。新宠物一律从 `0.98` 起步。

---

## 📁 仓库结构

```text
open-pets/
├── 🤖 open-pet-creator/             ← 可复用 Skill（核心资产）
│   ├── SKILL.md                          Skill 元信息 + 调参规则
│   ├── agents/openai.yaml                agent 接入元信息
│   ├── references/codex-pet-atlas.md     Codex 原子图契约文档
│   └── scripts/                          repack / inspect / validate / install
│
├── 🖥️ app/                          ← 桌面应用（Tauri 2，macOS 优先）
│   ├── index.html / main.js / style.css   主宠物窗口（vanilla 前端）
│   ├── picker.html / picker.js / picker.css  多宠物切换面板
│   ├── scripts/openpets-event             Claude Code / Codex 等 hook 用的写入器
│   ├── package.json                      只有 @tauri-apps/cli 一个 devDep
│   └── src-tauri/                        Rust 核：窗口 / 托盘 / NSPanel / 文件 watcher
│
├── 🐾 pets/                         ← 已收录宠物
│   ├── phrolova/  (鸣潮)
│   ├── pink-star/ (洛克王国)
│   └── rocom-dimo/(洛克王国)
│       └── 每只含 pet.json / spritesheet.webp / spritesheet-source.png / preview
│
├── 📝 docs/                         ← 设计文档 + 生成提示词模板
├── 🛠️ tools/                        ← 单宠物专用 repacker（路径硬编码）
├── ✅ tests/                        ← Codex 原子图契约的回归测试
├── README.md / README.en.md         ← 双语自述
└── LICENSE                          ← MIT
```

---

## 🤝 想加新宠物或扩展 Skill？

非常欢迎贡献！

<details>
<summary><b>加新宠物</b>（点开展开）</summary>

1. 提个 issue 描述角色，贴官方美术、列辨识特征
2. 用 `docs/<pet>-generation-prompt.md` 当模板生成源图
3. 提 PR，加入 `pets/<pet-id>/`、`docs/<pet-id>-pet-design.md` 与生成提示词
4. inspect 输出需所有行 `top_min ≥ 35`
5. 视觉风格保持 chibi，避免漂移到写实/painterly

</details>

<details>
<summary><b>扩展 Skill</b>（点开展开）</summary>

打包逻辑的 bug 修复、新校验器、其他 sheet 契约支持的 PR 都欢迎。改动 `open-pet-creator/scripts/` 下脚本时，记得：
- 同步更新 `SKILL.md` 中的相关章节（agent 读这份文档决定怎么用）
- 跑一遍 `python3 -m unittest tests/test_phrolova_spritesheet.py` 确认契约不被破坏
- 在 `references/codex-pet-atlas.md` 中补充对应的契约/调参说明

</details>

---

## 🧠 项目经验（已沉淀进 Skill）

两条踩过的坑，已写进 `open-pet-creator/SKILL.md`，agent 加载 Skill 时会自动获得这些知识：

| 坑 | 教训 |
| --- | --- |
| **照抄上只宠物的 `--scale`** | 不行。高耳轮廓 ≤ 1.0，矮胖型可到 1.05+。新宠物一律从 `0.98` 起步 |
| **生成器源图按等分网格切割** | 残片！必须用 `--detect-sprites`。gpt-image / Midjourney / SDXL 极少严格按等分网格出图 |

---

## 🙏 致谢与免责声明

这是一个**同人项目**，目的是个人桌面定制。所有角色形象致敬原作者：

- **Phrolova** —— *鸣潮 / Wuthering Waves* © Kuro Games
- **粉星仔 / Pink Star** 与 **迪莫 / Dimo** —— *洛克王国 / Roco World* © 腾讯 / Tencent

`open-pet-creator/`、`tools/`、`tests/`、`docs/` 中的代码与模板均为项目原创。**若您是版权方且希望下架某只具体宠物包，请提 issue 联系，会尽快配合移除。**

---

## 📄 协议

`open-pet-creator/`、`tools/`、`tests/` 与 `docs/` 中的代码与模板以 **MIT 协议**发布——见 [`LICENSE`](LICENSE)。`pets/` 下的宠物包属于同人创作，对应角色形象版权归原厂所有，仅用于个人桌面定制使用。

<div align="center">

---

⭐ **觉得有用就给个 Star 吧** ⭐

[报告 bug](https://github.com/EASYGOING45/open-pets/issues) · [建议宠物](https://github.com/EASYGOING45/open-pets/issues/new?labels=new-pet) · [English](./README.en.md)

</div>
