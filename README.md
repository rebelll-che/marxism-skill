# Marxism Skill

让 Agent 自己读原著，依据马克思、恩格斯的材料理解和讨论马克思主义。

本仓库提供完整原著材料、阅读指引和使用约束。Agent使用自己的文件搜索与阅读能力，不需要启动Mind Spark，也不需要专用检索服务。导读用于找到原著，不用预写的二手答案替代原著。

## 当前范围

当前收录110份选定文本：马克思76份、恩格斯26份、合著8份，涵盖哲学、政治经济学和科学社会主义的主要论述，以及有关的历史分析、理论书信、手稿和序导言。以中文译本为主，部分材料含外文。

这不是全集，也不宣称完整收齐经典马克思主义。尚无列宁等后续作者；以私生活、出版联络为主且缺少理论内容的材料不在当前范围内。一部作品只保存一份主用文本，独立草稿、实质修订和不同序言按文献性质区分，不把同一理论材料复制到多个主题目录。

## 安装和使用

```sh
git clone https://github.com/rebelll-che/marxism-skill.git
```

将仓库中的**完整`marxism-sources/`文件夹**放入目标Agent支持的Skill目录，或通过它支持的仓库安装方式选择这个子目录。不要只复制`SKILL.md`，也不需要把`tools/`、`tests/`或收集缓存装进Agent。具体安装位置以所用Agent的说明为准。

可以这样提问：

> 使用marxism-sources，依据实际读过的原著解释异化劳动与私有财产的关系，给出作品和章节出处。

也可以要求核对一个引文、比较不同作品中的论述，或先推荐阅读顺序。Skill要求区分原文、归纳和进一步分析，不编造历史作者的观点；找不到材料时应说明限制。它提供阅读约定，不能保证所有模型每次理解正确。

## 文件怎样组织

```text
marxism-sources/
├─ SKILL.md                      Agent使用入口
└─ references/
   ├─ reading-guide.md            按思想主题组织的阅读入口
   ├─ catalog.md                  作品、作者、版本与文件路径
   ├─ chapters.md                 原有章节层级和原文件行号
   ├─ works/
   │  ├─ marx/                    马克思作品
   │  ├─ engels/                  恩格斯作品
   │  └─ marx-engels/             合著
   ├─ assets/                     原文附件
   ├─ sources/                    原文附件
   └─ checks/                     原文引用的图片等附件
```

作品按作者存储；哲学、政治经济学、科学社会主义等主题在导读中组织，同一作品可以被多个主题引用。`catalog.md`和`chapters.md`由工具生成，不是理论依据；实际回答应回到`works/`中的原文。材料有原始章节、版本和来源说明，应注意区分作者正文、引用、修订者和编者说明。

`checks/`名称承自材料整理过程，包内这些文件是原文实际引用的阅读附件，不是可以随意删除的测试缓存。Markdown头部的`source_file`、`source_sha256`保留此前转换原件的位置与哈希；历史下载原件不随Skill公开，核对出处时使用同一头部的公共`source`地址及文献说明。这些历史路径不表示包内有可直接打开的PDF。

全部文本使用UTF-8。Windows工具如显示乱码，请以UTF-8模式重读，例如`python -X utf8`；文件行号按原始LF计算并包含YAML头，不是书本页码。Agent按问题读取必要材料即可，不需要加载完整目录或整库正文。

## 维护和验证

原著、附件、Skill指令和导读在本仓库维护。修改规则见[AGENTS.md](AGENTS.md)，重要变化见[CHANGELOG.md](CHANGELOG.md)。普通使用者无需安装下面的维护依赖。

维护工具只需Python、PyYAML；自动检查另外需要pytest：

```sh
python -m pip install PyYAML pytest
python -X utf8 tools/build_skill.py
python -X utf8 tools/build_skill.py --check
python -X utf8 -m pytest -q
```

第一条工具命令仅刷新作品和章节目录；`--check`只检查，不修改原文或指引。工具直接读取本仓库的原著，不依赖Mind Spark的清单、SQLite、API Key或运行数据。具体Python版本见`pyproject.toml`。

已有原生Codex CLI在本机完成入口、书目和原著读取及带出处回答，另有概念、版本区分和跨作品查读试用；这证明当前Skill初步可用，不等同于所有客户端、模型或问题都已验证。此次独立仓库拆分复用这些内容试用，另做文件、导航和独立运行检查，不为迁移重复调用在线模型。

## 与Mind Spark的关系

本仓库是选定原著和外置Skill的唯一维护源。[Mind Spark](https://github.com/rebelll-che/mind-spark)是基于这些材料的桌面对话应用；它在构建时导入一个明确的Git提交并生成自己的本地索引，随应用一起打包，运行时不自动追踪本仓库的新材料。两个项目分别管理版本。

## 来源与许可说明

各作品保留既有来源、版本及文献性质说明。仓库尚未为所有内容选定统一许可证，不把维护脚本的许可或材料公开可读理解为覆盖所有原著译本的统一许可。
