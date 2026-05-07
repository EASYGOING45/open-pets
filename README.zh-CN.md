# open-pets

> 给 [Codex CLI](https://github.com/openai/codex) 与 [Claude Code](https://www.anthropic.com/claude-code) 用的自定义桌面宠物，附带一个可复用的 AI Skill —— 把生成器产出的 chibi 精灵图转成符合 Codex 协议的 `1536x1872` 宠物原子图。

[English](./README.md) · 简体中文

---

## ✨ 仓库里有什么

| | |
| --- | --- |
| 🐾 **三只可直接安装的宠物** | Phrolova（鸣潮）、粉星仔（洛克王国）、迪莫（洛克王国） |
| 🛠️ **可复用 Skill** —— `open-pet-creator` | repack / inspect / validate / install 四件套，Codex 或 Claude Code 中的 agent 都能驱动 |
| 📝 **可复刻的设计文档** | 每只宠物的设计文档与图像生成提示词模板，照抄即可做下一只 |
| ✅ **回归测试** | 锁住 Codex 原子图契约（8×9 格、192×208 单元、未用格透明）的契约测试 |

Skill 是**纯确定性打包工具** —— 只做裁剪、alpha 清理、重排、校验、安装，**不生成新美术**。源图来自你自己的图像生成工具（gpt-image / Midjourney / SDXL 等）。

## 🐾 已收录宠物

每只宠物都是 9 行 × 8 列原子图，覆盖 Codex 全部状态（`idle` / `running-right` / `running-left` / `waving` / `jumping` / `failed` / `waiting` / `running` / `review`）。

| 宠物 | 来源 | 预览 |
| --- | --- | --- |
| **Phrolova** | *鸣潮 / Wuthering Waves* 同人 | [`pets/phrolova/spritesheet-repacked-preview.png`](pets/phrolova/spritesheet-repacked-preview.png) |
| **粉星仔 / Pink Star** | *洛克王国 / Roco World* 同人 | [`pets/pink-star/spritesheet-repacked-preview.png`](pets/pink-star/spritesheet-repacked-preview.png) |
| **迪莫 / Dimo** | *洛克王国 / Roco World* 同人 | [`pets/rocom-dimo/spritesheet-repacked-preview.png`](pets/rocom-dimo/spritesheet-repacked-preview.png) |

## 🚀 快速开始 —— 安装一只宠物

挑一只宠物，把它的目录复制到运行时的 pets 目录里：

```bash
# Codex CLI
mkdir -p ~/.codex/pets/phrolova
cp pets/phrolova/spritesheet.webp ~/.codex/pets/phrolova/
cp pets/phrolova/pet.json         ~/.codex/pets/phrolova/

# 然后在 Codex 里重新选一次宠物（或重启），让缩略图缓存刷掉
```

`pets/pink-star/` 和 `pets/rocom-dimo/` 同理。

## 🧰 安装 Skill

`open-pet-creator` Skill 在 Codex 与 Claude Code 中都能用。复制一次到对应 skill 目录：

```bash
# Codex CLI
cp -R open-pet-creator ~/.codex/skills/open-pet-creator

# Claude Code
cp -R open-pet-creator ~/.claude/skills/open-pet-creator
```

之后用 `$open-pet-creator`（Codex）或 `/open-pet-creator`（Claude Code）调用，把重排、校验、检视、安装的工作交给 agent。

## 🛠️ 做你自己的宠物

只要源美术齐了，整个流程通常 30 分钟内能完成：

1. **设计** —— 复制 [`docs/rocom-dimo-pet-design.md`](docs/rocom-dimo-pet-design.md) 当模板，描述配色、辨识特征、每行姿势。
2. **写提示词** —— 复制 [`docs/rocom-dimo-generation-prompt.md`](docs/rocom-dimo-generation-prompt.md)，按你的角色改写；末尾的 **Final Prompt** 直接粘贴到图像生成器。
3. **生成** —— 输出一张 `1536 × 1664` PNG，8 列 × 8 行布局，纯黑底。存为 `pets/<your-pet>/spritesheet-source.png`。
4. **重排** —— 让 Skill 打包成 `1536 × 1872` Codex 原子图：

   ```bash
   python3 open-pet-creator/scripts/repack_pet_atlas.py \
     --source pets/<your-pet>/spritesheet-source.png \
     --output pets/<your-pet>/spritesheet.webp \
     --preview pets/<your-pet>/spritesheet-repacked-preview.png \
     --scale 0.98 --offset-y 14 \
     --detect-sprites
   ```

   只要源图来自图像模型，就一律带上 `--detect-sprites` —— 生成器很少会严格按等分网格出图。
5. **检视 & 校验**：

   ```bash
   python3 open-pet-creator/scripts/inspect_pet_atlas.py  pets/<your-pet>/spritesheet.webp
   python3 open-pet-creator/scripts/validate_pet_atlas.py pets/<your-pet>/spritesheet.webp
   ```

   调 `--scale` 和 `--offset-y`，让 idle bbox 落入推荐的 `105 – 125 × 140 – 155`，且 `top_min ≥ 35`。**不要照抄上一只宠物的数值** —— 轮廓几何因角色不同（Phrolova 的紧凑型能撑 1.07，粉星仔的高耳只能 0.98）。
6. **安装** —— 把 `pet.json` 和 `spritesheet.webp` 拷到 `~/.codex/pets/<your-pet>/`。

Skill 的 [`SKILL.md`](open-pet-creator/SKILL.md) 与 [`references/codex-pet-atlas.md`](open-pet-creator/references/codex-pet-atlas.md) 详细记录了原子图契约与 scale/offset 取舍。

## 📁 仓库结构

```text
open-pets/
├── pets/                              可直接安装的宠物包
│   ├── phrolova/   pink-star/   rocom-dimo/
│   │     ├── pet.json
│   │     ├── spritesheet.webp           ← 安装用原子图
│   │     ├── spritesheet-source.png     ← 生成的源图（8×8 单元）
│   │     └── spritesheet-repacked-preview.png
├── open-pet-creator/                  可复用 Skill
│   ├── SKILL.md
│   ├── agents/openai.yaml
│   ├── references/codex-pet-atlas.md
│   └── scripts/
│         ├── repack_pet_atlas.py        （支持 --detect-sprites）
│         ├── inspect_pet_atlas.py
│         ├── validate_pet_atlas.py
│         └── install_pet.py
├── tools/                             单宠物专用 repacker（路径硬编码）
│   ├── repack_phrolova_spritesheet.py
│   └── repack_pink_star_spritesheet.py
├── tests/                             回归测试
│   └── test_phrolova_spritesheet.py
└── docs/                              各宠物设计文档 + 生成提示词
    ├── phrolova-pet-design.md
    ├── pink-star-pet-design.md
    ├── pink-star-generation-prompt.md
    ├── rocom-dimo-pet-design.md
    └── rocom-dimo-generation-prompt.md
```

## 🤝 贡献

非常欢迎新宠物。流程：

1. 提个 issue，描述角色（贴官方美术、列辨识特征）。
2. 用 `docs/<pet>-generation-prompt.md` 当模板生成源图。
3. 提 PR，加入 `pets/<pet-id>/`、`docs/<pet-id>-pet-design.md` 与生成提示词。inspect 输出需所有行 `top_min ≥ 35`。
4. 视觉风格保持 chibi，避免漂移到写实/painterly 路线，让所有宠物在 picker 里风格统一。

打包逻辑的 bug 修复或 Skill 扩展（新校验器、其他 sheet 契约）的 PR 也欢迎。

## 🧠 项目经验

两条已经踩过的坑：

- **每只宠物的 `--scale` 不能照抄。** 高轮廓（兔耳、帽子、天线）天花板大约 0.95–1.0；矮胖紧凑型可以拉到 1.05+。新宠物一律从 `0.98` 起步。
- **生成器产的源图必须用 `--detect-sprites`。** gpt-image / Midjourney / SDXL 出图很少严格按等分网格，默认 even-grid 切割会把宽精灵切成残片。

两条都已写进 `open-pet-creator/SKILL.md`。

## 🙏 致谢与免责声明

这是一个**同人项目**，目的是个人桌面定制。所有角色形象致敬原作者：

- **Phrolova** —— *鸣潮 / Wuthering Waves*（KURO GAMES）。© Kuro Games。
- **粉星仔 / Pink Star** 与 **迪莫 / Dimo** —— *洛克王国 / Roco World*（淘米）。© TaoMee。

`open-pet-creator/`、`tools/`、`tests/`、`docs/` 中的可复用代码与模板均为项目原创。若您是版权方且希望下架某只具体宠物包，请提 issue 联系我。

## 📄 协议

`open-pet-creator/`、`tools/`、`tests/` 与 `docs/` 中的设计文档/提示词模板以 **MIT 协议**发布——见 [`LICENSE`](LICENSE)。`pets/` 下的宠物包属于同人创作，对应角色形象版权归原厂所有，仅用于个人桌面定制使用。详见上方免责声明。
