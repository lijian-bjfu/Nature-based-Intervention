# 设计-开发技术迭代B：Houdini 地形 → Unity Terrain 迁移方案
---

Create: 2026-07-08
Edit: 2026-07-10

---

## 一、 Unity 资源导入与项目管理

> 记录范围:Unity 项目结构规范、外部资源包(Asset Store / 第三方)导入后的组织与复用、依赖管理与安全清理、Built-in → URP 材质批量转换。
> 环境:Unity 6.4、URP、目标平台 iPad(M 系列);主项目 `nature`,已导入 BadDog/ForwardSSRWater、WaterCausticsModules,待导入 5 个植被/岩石资源包(NatureManufacture Meadow Environment 等,学生已完成 URP 转换)。

**三条核心心智模型**(本节一切操作规则均为其推论):
1. **引用靠 GUID,不靠路径**。每个资产旁的 `.meta` 文件存有 GUID;材质→贴图、Prefab→材质、场景→Prefab 的全部引用记录的是 GUID。
2. **项目本体只有三个文件夹**:`Assets/`、`Packages/`、`ProjectSettings/`。其余(Library/Temp/Logs/obj/UserSettings/*.csproj/*.slnx)全是可再生派生物。
3. **打包只含被引用资产**。Build 时 Unity 只打包被场景实际引用的资产(+ Resources 等特殊目录)。工程里的"垃圾"不进包、不影响产品体积,只影响工程整洁和导入时间——清理可以从容做。

---

### 1. 项目本体、派生物与残留清理

#### 1.1 本体 / 派生物划分
- 备份、git、拷给学生,只需 `Assets` + `Packages` + `ProjectSettings` 三件套。验证项目完整独立的终极测试:三件套拷到新位置能原样打开。
- `Library`(本项目曾达 3.5GB)是导入缓存,可整删,重开项目全量重导(耗时但无损)。`Temp`、`Logs`、`obj`、崩溃日志(`mono_crash.*.json`)随时删。`UserSettings` 是个人编辑器布局,不属项目。

#### 1.2 csproj / slnx 残留(踩坑修正)
- `*.csproj`、`*.slnx` 是 Unity 为代码编辑器自动生成的工程描述文件,位于项目根目录,不进包,**随时可删,自动重生成**。
- **残留成因**:删除资产后 Unity 未触发重新生成。案例:Crest 从 Assets 删净后,根目录残留 `Crest.csproj` 等三个文件 → 直接删除即可。
- **"删不掉"的 csproj**:`WaterCausticsModules.Effect.csproj` 删后重生,因为它对应的 `.asmdef`(程序集定义)还在 Assets 里——**每个 asmdef 生成一个 csproj**。正确清理方向不是删 csproj,而是删 Assets 里不用的部分(如 DEMO 文件夹),csproj 自动跟随缩小/消失。
- Build 输出目录(如 `natureprobe-ios-build`)以后放项目文件夹**外**,避免混入。

#### 1.3 版本控制
- git 从第一天开始,用 GitHub 官方 Unity `.gitignore` 模板(自动忽略全部派生物);**meta 文件必须提交**。大贴图多可加 Git LFS。
- git 是一切删除操作的兜底:有了它,"误删"概念不存在。

---

### 2. meta / GUID 机制与移动铁律

- `.meta` = 资产身份证(GUID)+ 导入设置(贴图压缩、模型缩放等)。meta 必须与资产同进退。
- **铁律:移动/重命名资产只在 Unity 的 Project 面板内做,绝不在 Finder 里做。** Unity 内操作 meta 同步搬走、GUID 不变、引用完好;Finder 移动 meta 掉队 → Unity 生成新 GUID → 全部引用断裂(材质变粉是典型症状)。
- **唯一安全的 Finder 操作**:跨项目搬运时**整文件夹复制**(meta 天然随行),如把学生转换好的包整体拷入主项目 `ThirdParty_Art/`。
- **GUID 机制的盲区(移动前检查)**:脚本内硬编码路径(`Resources.Load("...")`、字符串拼路径)、shader 的**相对路径** include(`#include "../xxx.hlsl"`)不受 GUID 保护。指向 `Packages/...` 的绝对 include 不受影响,搬到哪都有效。
- 推论:纯内容型资产(模型/贴图/材质/Prefab)随便移、随便改名;**含代码/shader 的功能性插件保持出厂目录结构不动**(且插件更新按原路径重导,移过位置会出现新旧两份)。

---

### 3. 目录结构规范

#### 3.1 结构图(本项目已实施)
```
Assets/
├── _Project/                  ← 自有内容,唯一"可信区"(下划线置顶)
│   ├── Scenes/                  Main 正式场景 + Sandbox 实验场景分开
│   ├── Prefabs/                 ← 场景唯一的拖拽来源
│   │   ├── Tree / Shrub / Ground_Plant / Ground_Mass / Rocks / Logs
│   │   │                        (分类对齐 Houdini Biome 分层,便于 CSV 散布映射)
│   ├── Texture/                  自制模型、地形用到的贴图
│   ├── Scripts
│   ├── Settings
│   ├── Terrain / Scatter Data / Terrain Layers 
├── ThirdParty_Art/            ← 美术资源包(只读区,保持出厂结构)
│   ├── 01MeadowEnvironment/ …(p01–p05 逐个入驻)
└── ThirdParty_Plugins/        ← 功能性插件(含代码,整包保留)
    ├── WaterCausticsModules/  BadDog/
```

#### 3.2 配套纪律(比目录本身更重要)
1. **单向依赖**:`_Project` 可引用 ThirdParty;ThirdParty 永不引用 `_Project`,各包互不引用。任何第三方包整删,`_Project` 结构不塌——这就是"独立性"的操作性定义。
2. **场景只见 Variant**:Hierarchy 里的植被/岩石一律来自 `_Project/Prefabs/`;ThirdParty_Art 当"仓库",只看不拖。核对方法:选中场景实例 → Inspector 顶部 Prefab 栏 Select,看定位到哪个文件。
3. **命名规范只施加于 `_Project`**:自有 Variant 按规范命名(建议带 `_var` 等识别标记);ThirdParty 保持出厂原名,便于对照厂商更新。
4. **Sandbox 场景**:新资产测试、参数实验都在 Sandbox 做,Main 保持干净(pilot 与正式实验分离的同构)。
5. 未来做实验对照版本:在 `Scenes/` 复制场景做变体,资产层完全共享,避免多版本不同步。

---

### 4. FBX / Prefab / Prefab Variant 三层模型

#### 4.1 概念
- **FBX = 原料**:导入后是只读 Model Prefab,只含网格 + 默认材质映射,无 LOD、无碰撞体、无脚本。
- **Prefab = 成品模板**:把 GameObject 层级 + 组件配置 + 材质引用存成磁盘文件;场景实例与模板保持链接,改模板全实例同步,实例可局部覆盖。厂商 Prefab 已配好材质、**LOD Group**(LOD0/1/2 + billboard,iPad 性能关键)、碰撞体、GPU instancing。
- **Prefab Variant = 收编壳**:继承原 Prefab 一切,零成本创建;自己的修改(换材质、调 LOD 距离、加交互脚本)做在 Variant 上,原包保持出厂状态。
- **关键认知:.prefab 文件只是"引用清单"**,不含网格/贴图数据。单独复制 .prefab 到自己文件夹,模型并没有跟过来(且复制产生新 GUID,徒增混乱)。Prefab 不需要"拷",需要"套一层 Variant"。

#### 4.2 使用规则
- **场景里只拖 Prefab / Variant,永不拖 FBX**(拖 FBX = 丢掉厂商全部配置,手动重做)。
- **何时 Prefab 化**,两条判断标准满足其一即做:① 会被复用(多实例 / 多场景);② 配置有价值(挂了脚本、调好参数,值得存档)。一次性简单物体(唯一方向光、相机)可不做;"一切皆 Prefab"是团队偏好非规则。
- **Variant 创建**:Project 面板右键厂商 Prefab → Create → Prefab Variant → 移入 `_Project/Prefabs/` 对应分类、按规范改名。可多选批量创建;只给实际要用的建。注意:"把厂商 prefab 拖进自己文件夹"是移动原件,不是创建 Variant。
- **收益兑现时点**:批量种树后统一调 LOD 切换距离、阴影开关、材质替换——改 Variant 一处,全场景实例同步;不建 Variant 届时只能改厂商原件(污染底座、更新即被覆盖)或挨个改实例。
- 场景物体转 Prefab:Hierarchy 拖到 Project 面板即生成(如水面组合体 → `_Project/Prefabs/Environment/`)。

---

### 5. 大体积资源包(10G+)导入流程:素材提取项目

**原则:不把 5 个 10GB+ 的包直接导入主项目**——Library 缓存会膨胀至上百 GB,打开项目、切 iOS 平台(全量重压缩贴图)都是灾难级等待。加一个中间层:

1. **建一次性"素材提取项目"(Staging)**:空 Unity 项目,管线与主项目一致(URP)。整包导入这里挑选。此项目脏乱大均无所谓——它是菜市场,不是厨房。可放外置硬盘,用完即删或留作仓库。
2. **URP 转换在提取项目内完成**(见 §8),确认无粉红后再出口,保证进主项目的资产"URP 就绪"。
3. **按依赖出口精选子集**:选中要的 Prefab → 右键 **Select Dependencies**(自动高亮牵连的全部 FBX/材质/贴图/shader,无论厂商藏多深)→ 保持选中 → **Assets → Export Package**(勾 Include dependencies)→ 得到几百 MB 的精选 .unitypackage → 导入主项目。
4. **主项目内收编**:精选包按原路径落地(体积已可控,无妨)→ 对要用的 Prefab 建 Variant 入 `_Project/Prefabs/` → 场景拖 Variant。

**分支判断**:
- 包内大部分内容都要用(如 Meadow Environment)→ 跳过提取项目,Finder **整文件夹连 meta** 拷入主项目 `ThirdParty_Art/`(§2 的唯一安全 Finder 操作)。
- 包是功能性插件(含脚本/shader,如 WaterCausticsModules)→ 不拆散收编,整包保留原结构于 `ThirdParty_Plugins/`。

---

### 6. 从 Demo 收编资产(WaterSurface 案例)

**模式**:插件 DEMO 文件夹本意是示范,但常藏可直接投产的资产(示例材质、配好的 Prefab)。标准流程四步:

1. **识别**:选中目标资产 → Select Dependencies,看它真正牵连什么。
2. **收编**:在 Unity 内把目标及其依赖**移动**(非复制)到 `_Project` 对应目录、改名。移动 = GUID 随行、场景引用无缝;复制 = 新 GUID、场景仍指旧文件,白干。
3. **清场**:对剩余 Demo 部分反查引用(§7 工具),确认无外部引用后整删。
4. **验证**:场景材质变粉 = 依赖断了,git / Ctrl+Z 恢复重来。

**案例实测**(WaterCausticsModules):
- 场景水面做法 = 自有 `water.fbx` + 拖上 DEMO_2 的 WaterSurface 材质。
- 经文件级核查:`WaterSurface` 实为**文件夹**,内含 `DEMO_WaterSurface.mat` + `DEMO_WaterSurface.shader`(手写 HLSL,非 Shader Graph);mat 的 shader GUID 即指向旁边这个 shader;**mat 无任何贴图引用;shader 的 include 全部指向 `Packages/...`(URP 官方包,绝对路径)** → 该文件对完全自包含,整体移入 `_Project` 即可,原路径层级无须保留。
- 清场注意:`DEMO (Effect)` 下的 `Data/Scripts/` 删前需反查;插件本体 `Effect/` 与 `ShaderFunctions/` 必须保留。

---

### 7. 依赖管理与安全清理

#### 7.1 工具矩阵
- **正向查询(它依赖谁)**:选中资产/场景 → 右键 **Select Dependencies**。"场景到底用了什么"一次看清,未被高亮者即候选删除对象。
- **依赖打包**:Select Dependencies 后 **Export Package**(Include dependencies)——官方的自动依赖收集器,§5 流程的核心。
- **反向查询(谁在用它)**:Unity 内建极弱(仅 Find References In Scene,限当前场景)。用开源插件 **Asset Usage Detector**(yasirkula):
  - 安装:Package Manager → + → Install package from git URL → `https://github.com/yasirkula/UnityAssetUsageDetector.git`(以 Package 形式存在,不污染 Assets)。
  - 单查:Project 面板右键资产 → **Search for References** → GO。
  - 批查:**Window → Asset Usage Detector**,把资产或**整个文件夹**(如 DEMO 文件夹)拖入 SEARCHED OBJECTS。
  - 设置:Search in scenes = **All scenes in the project**(只选 Open scenes 会漏未打开场景的引用);Search in Project Settings 保持勾选。
  - 判读:引用者全部来自其自身文件夹内部(Demo 场景引用 Demo 材质)→ 安全删;"No references found" → 放心删。
  - **局限**:查不到代码硬编码路径引用(`Resources.Load` / 字符串拼路径)。纯美术资产无此问题;删插件脚本文件夹前留心。
- **兜底**:git(§1.3);以及心智模型 3——没删干净也不进包。
- **终极手段(项目烂到没法原地清)**:整体迁移法——新建空工程,Export Package(含依赖)只带走需要的场景,垃圾整体留在旧工程。

---

### 8. Built-in → URP 材质批量转换(粉红材质)

粉红仅表示 shader 不兼容 URP,**材质内的贴图引用都在**,不需逐个手动重连。三级处理,工作量递减:

1. **找官方 URP 补丁(最优)**:包内找 `URP` / `SRP` / `Pipeline Support` 文件夹,常有作者配好的 .unitypackage,导入即完事。商店页写 "URP supported" 的多为此模式。每个包先查这个。
2. **官方批量转换器**:选中包的材质 → **Edit → Rendering → Materials → Convert Selected Built-in Materials to URP**(精准);或 **Window → Rendering → Render Pipeline Converter** → Built-in to URP → Material Upgrade(全局)。自动识别 Standard 系 shader、换 URP/Lit、**自动重映射贴图槽**(Albedo→Base Map、Normal、Metallic),alpha cutout 设置带过去。通常消灭 80–95% 粉红。
3. **顽固粉红才手动**:作者自写 shader(树叶风摆、双面渲染常见)转换器不认 → Inspector 手动切 Shader 为 `Universal Render Pipeline/Lit`(iPad 优先试更省的 **Simple Lit**;树叶勾 Alpha Clipping),Base Map 需重新指认(旧属性名对不上)。一个树种通常仅 1–2 个材质,实际量小。SpeedTree 树 URP 原生支持,基本不粉。

**时点**:转换在素材提取项目内完成(§5 步骤 2),主项目永不见粉红、转换劳动不重复。

---

### 9. NatureManufacture Meadow Environment 包特记

- 结构:130 个 Prefab,按 Background Mountains / Trees / Bushes / Grass / Ground / Rocks / Details / Fence / Roads 分类,规整。
- **公共依赖不可删**:`Foliage Shaders`、`Object Shaders`、`NatureManufacture Wind` 三个文件夹是全部植被的依赖。
- **场景必须放 `Prefab_Wind`**:该厂植被摆动由风控制器驱动,缺失则草木僵直。
- `Demo Scenes` 参考完毕后,Asset Usage Detector 验证 → 删。
- 学生转换后的项目位于 `TP_HRP_Resources/MeadowEnv/`,整包(含 meta)拷入主项目 `ThirdParty_Art/` 即可。

---

### 附:本轮"项目管理"踩坑与原则速查

| 现象 / 疑问 | 根因 / 原理 | 做法 |
|---|---|---|
| 删了 Crest,根目录仍有 Crest.csproj | csproj 是 IDE 派生物,删资产未触发重生成 | 直接删,自动按现状重生成 |
| WaterCausticsModules 的 csproj 删了又长回来 | Assets 里 asmdef 还在,每个 asmdef 对应一个 csproj | 删 Assets 里不用的部分(DEMO),csproj 自动跟随 |
| Finder 里移动资产后材质变粉、引用全断 | meta 掉队 → 新 GUID → 引用断裂 | 移动/改名只在 Unity Project 面板做;Finder 仅限整文件夹连 meta 复制 |
| Demo 里的材质想用,要保留原路径层级吗 | 引用靠 GUID 不靠路径 | 不用;Unity 内移入 _Project 即可(先确认 shader 无相对 include) |
| 把 .prefab 复制到自己文件夹"拿走模型" | prefab 只是引用清单,不含网格/贴图;复制生成新 GUID | 厂商包留原地作底座,建 Prefab Variant 入 _Project |
| 拖 FBX 进场景,树没有 LOD/材质不对 | FBX 是原料,配置在厂商 Prefab 上 | 场景只拖 Prefab / Variant |
| 直接拽厂商 Prefab 进场景,要重设材质 LOD 吗 | Prefab 自带全部配置 | 不用;但拖 Variant,为将来统一调参留接口 |
| 怕误删依赖,不敢清理 | Build 只含被引用资产,垃圾不进包 | 从容清:Select Dependencies 正查 + Asset Usage Detector 反查 + git 兜底 |
| 10G+ 大包直接导入主项目 | Library 暴涨、切 iOS 平台全量重压缩 | 素材提取项目挑选 → Export Package(含依赖)→ 主项目 |
| 导入的非 URP 包全场粉红 | shader 不兼容,贴图引用未丢 | 三级转换:官方补丁 → 批量 Converter → 手动 URP (Simple) Lit |
| NatureManufacture 草木不摆动 | 缺风控制器 | 场景放入 Prefab_Wind |
---

## 二、地形技术流程：Unity Terrain

> 记录范围：仅地形本体（高度）、尺度换算、地表材质（splatmap + Terrain Layer）的技术路径与实现。
> 树木/散布点导入、水面、光照等另行记录。
> 环境：Houdini 21（Copernicus/新版 COPs）、Unity 6.4、URP、目标平台 iPad（M 系列）。

**结论**：Houdini heightfield 不转 poly、不 polyreduce、不导 FBX，而是导出**高度图（heightmap）**，由 Unity Terrain 系统重建。

**理由**：
- Unity Terrain 不是固定面数 mesh，而是按摄像机距离**动态细分**的高度场（LOD 系统内建，由 Pixel Error 控制）。第一人称视角下实际绘制三角形远少于采样点数，1 公顷地块 iPad 毫无压力。
- 高度图只是一张 16-bit 灰度图，数据量比"大模型 + 大贴图"小两个数量级，细节反而更高。
- polyreduce 会最先牺牲高频细节（岩石变尖角），均匀网格等效采样密度远低于高度图。

**配套原则**：岩石/露头/倒木等高频、悬垂结构**不放进地形**（高度场表达不了悬垂），而作为**独立 mesh 资产散布**在地表。地形只承载平滑的宏观起伏。

---

### 1. 尺度问题（关键，反直觉）

#### 1.1 背景矛盾
- Houdini 场景以"1 单位 = 10 米"的自定比例制作（因为在 1 平方公里上做细小溪流需要极高分辨率，正常比例下细溪会显得过宽）。
- 目标是把这个"1 平方公里"的地形，在 Unity 中呈现为 **1 公顷（100×100 米）**。
- 顾虑：heightfield 的 noise 信息与模型空间尺度分离，直接缩小模型会导致 noise 不跟着缩、模型失真。

#### 1.2 解决方案：缩放不发生在 Houdini，只发生在 Unity 导入参数
**关键认识**：高度图本身没有尺度。导出的 16-bit 灰度图只是 0–1 归一化的高度值阵列，它不知道自己代表 1 公里还是 100 米。尺度完全由 Unity Terrain 的 Width/Length/Height 三个数字决定。

- Houdini 网络**一个节点都不动**，照常 cook。noise、erosion、compute range 的结果已经写死进 heightfield 像素，导出只是"抄数"，不触发上游重算。
- 因此不存在"noise 和空间尺度分离导致失真"——因为从头到尾没有任何节点被要求重新求值。

#### 1.3 等比缩放的不变量
- **坡度不变**：水平 ÷10、高度 ÷10 的等比缩放下，30° 河岸缩完还是 30°。基于 slope 的 mask 及 Unity 侧基于坡度的逻辑自动正确。
- 唯一改变的是绝对数值的单位解读（17 单位宽的溪 → 1.7 米宽的溪），这正是想要的结果。

#### 1.4 Height Remap 的正确理解（踩坑修正）
> **重要修正**：Terrain Toolbox 里的 Height Remap Min/Max **不是**图像归一化的 0–1 值域，而是**直接以"米"为单位的真实输出高度范围**。它与 Terrain Height 协同定义真实高度。

因此：Houdini 高程（Houdini 单位）整体 ×0.1 缩到真实米制，填入 Height Remap。
- 实际案例：Houdini 高程 min = -11.52，max = 243.38 → ×0.1 → Height Remap **Min = -1.15，Max = 24.3**。
- 这才是让地形得到正确真实高度的填法（曾误填 0/1 导致地形被拉成深井，或误填原始高程导致放大 10 倍）。

---

### 2. 高度图导出（Houdini 侧）

#### 2.1 节点链
`terrain_add_mask`（地形最终 null）→ **HeightField Resample** → **HeightField Output**

#### 2.2 HeightField Resample
- **Division Mode = By Axis**（不是 By Size；By Size 的 Grid Spacing 是"每格多少米"，填 2049 会只剩一两个格子）。
- Resolution 填 **2049**（对齐 Unity 高度图要求的 2ⁿ+1；1 公顷用 2049 ≈ 5cm/采样点，够用；1025 ≈ 10cm 亦可，更省）。
- 从 1500 上采样到 2049 是插值放大，不丢现有细节。
- Filter：上采样时把 Filter Scale 降到 1，或换 Catmull-Rom（锐利保细节）；默认 Gaussian + 1.5 是给下采样防锯齿用的，会糊掉高频（溪岸侵蚀纹理）。

> 注意：Resample 设 2049，实际导出图可能是 2050（格子/采样边界差 1 像素）。无害——Terrain Toolbox 导入时会自动 resize 到 2049。若想精确对齐可回 Houdini 微调，但不值得。

#### 2.3 HeightField Output（关键参数）
- **Format = Single Channel**（灰度，不要 RGBA 四通道全塞 height，白白大四倍）。
- **Type = 16 Bit Integer / 16b Fixed**（8-bit 只有 256 级高度，斜坡出阶梯；不要 32b Floating Point，PNG 不支持会被静默降级）。
- **Filename** 后缀 `.png`，导出 height 层。
- **Output Range = Manual Remap**：
  - **From Range**：输入端，填地形高程的"米"区间（用实际 min/max，或略宽的整数便于以后微调重导）。
  - **To Range**：输出端，填 **0, 1**（16-bit 图的归一化值域）。
  - > 踩坑：曾误填 To Range = -15/255（当成 8-bit 像素值），导致负数被裁成黑、超 1 被裁成白，图变成"白底 + 一条黑线"的二值化。正确必须是 0, 1。
- **Flip Output**：先全部不勾，进 Unity 对照地标判断方向后再决定（只能翻一边）。
- 记下 From Range 的 min 和跨度：跨度 ÷10 = Unity Terrain Height；min ÷10 = Terrain Y 位置偏移。

---

### 3. 高度图导入（Unity 侧）

#### 3.1 工具准备
- 装 **Terrain Tools** 包：Package Manager → 加号 → **Install package by technical name** → `com.unity.terrain-tools`（不在默认列表里）。
- 入口：**Window → Terrain → Terrain Toolbox**。

#### 3.2 建 Terrain + 导高度图（Create New Terrain 页）
> 高度图导入功能只在 **Create** 页，Utilities 页没有。修改高度图后需删旧 Terrain 重建（Create 流程），或用 RAW 走 Utilities 的 Import Raw 快速刷新（需 Houdini 另导 .raw）。

Create 页参数：
- **Total Terrain Width(m) = 100**，**Length(m) = 100**
- **Terrain Height(m) = 跨度 ÷10**（案例 = 26，给了余量；只要 ≥ 实际最大高度即可）
- **Heightmap Resolution = 2049**（下拉里的 33/65/…/2049/4097 即 2ⁿ+1 序列）
- **勾 Import Heightmap**，Heightmap Mode = **Global**，**Use Raw File 不勾**（导入的是 PNG）
- **Select Texture** → 选导出的高度图 PNG（需先拖进 Assets）
- **Height Remap**：Min/Max 填**真实米制高度**（案例 Min = -1.15，Max = 24.3，即 Houdini 高程 ×0.1）—— 见 §1.4
- **Start Position Y = 0**（不要填成负的高程值，会把整块地形下沉）
- **Flip Axis = None**（先默认，方向不对再回 Houdini Flip 重导）
- 底部 **Create**

#### 3.3 高度图 PNG 的导入设置（Inspector）
- **sRGB (Color Texture) = 取消勾选**（高度图是数据不是颜色，做 sRGB 会非线性扭曲灰度，河谷层次被压没）。
  > 踩坑：sRGB 被误勾会导致地形比正常还平。
- **Compression = None**（压缩成 ASTC 会在陡坡产生块状/垂直条纹破碎伪影）。
- **Max Size** 提到 8192（≥ 图分辨率）。
- **Non-Power of 2 = None**。
- **Format = R 16 bit**（单通道 16-bit）。

#### 3.4 验收
- 建好后按 **F** 聚焦 Terrain（否则可能从侧面看像飘空的薄片，是视角问题非地形问题）。
- 俯瞰核对**方向**：对照 Houdini 的山脊/河道走向，判断有无南北/东西镜像；镜像则回 HeightField Output 勾 Flip Vertically 重导（只翻一次）。方向必须在种树、刷贴图前定死。
- 尺度终验：放 2 米高 Capsule 到河道边，看人 vs 溪宽比例（最初"小溪别变大江"的最终检验）。

---

### 4. 地表材质：splatmap + Terrain Layer（URP）

#### 4.1 概念
- **splatmap = mask**，区分地表材质分布，与 Houdini 的 feature mask 同类。
- 物理载体是一张 **RGBA 图**，但内容是**权重数据不是颜色**（不能做 sRGB）。R/G/B/A 四个通道各装一种材质的权重灰度图。四通道每像素权重和应 ≈ 1（归一化）。
- **一张 RGBA 装 4 种材质**；超过 4 种用多张 splatmap（Unity 内部叫 SplatAlpha 0、1、2…，第 5-8 种放第二张）。iPad 上 4 层一个 pass，最优；建议不超过 4。
- splatmap 只回答"哪里是什么材质"；**normal / AO / roughness 由平铺纹理集自带**，不需自己做、不从 Houdini 来。
- 必要地面材质 = **平铺 PBR 纹理集（提供细节，含 normal）× splatmap（提供分配）**；
- 其他材质。metallic, ambient occlusion, detail mask, smootheness，这些材质平成一张mask图,分别占用 RGBA通道，为地形提供材质质感(注意，这一点尚不确定)。

#### 4.2 splatmap 制作（Houdini Copernicus 侧）
> Houdini 21 COPs 已被 Copernicus 重写（20.5 起），旧 COP2 的 Channel Copy 属废弃的 "COP Network - Old"。MaterialX 的 mtlxseparate/combine 是着色器网络节点，非 COPs，不用于此。

- 用 **Channel Join** 把多个单通道 mask（Mono layer）合并成 RGBA：草皮 mask → R，岩石 mask → G，泥土 → B…（也可用 Channel Split/Swap/Extract 辅助）。
- 通道分配顺序**必须**与 Unity 侧建 Terrain Layer 的顺序一致。
- **权重互补/归一化**（防留空、防超界）：
  - 少量材质（2-3 种，覆盖层不重叠）：基础层扣除法，如 `草皮 = max(0, 1 - 岩石 - 泥土)`（必须 clamp 到 0，否则负权重出错）。
  - 材质多、mask 会重叠：统一归一化，`每种 = 各自权重 / 总和`，强制和为 1，画 mask 时不用操心留空/超界。
- **输出**：线性色彩空间（非 sRGB），PNG，512 或 1024 分辨率即可（低频，不做 2K）。
- **分辨率必须匹配** Terrain 的 Control Texture Resolution（见 §4.4 踩坑）。
- **方向**必须与高度图一致（若高度图做过 Flip，splatmap 同样处理），否则材质贴错位。
- 注意：COP 画布设 1024，但从 heightfield 取的 mask 可能继承源头 1500 分辨率；末端加 **Resample 节点**强制成 1024 再进 rop_image 输出。

#### 4.3 建 Terrain Layer 并挂到地形（Unity 侧）
- 选中 Terrain → Terrain 组件工具栏**画笔图标** → **Paint Texture** → **Edit Terrain Layers → Create Layer**。
- 逐个 Create：选每种材质的 **albedo** 图生成 Layer。**建 Layer 的顺序 = splatmap 的通道顺序**（Layer 0 = R，Layer 1 = G，Layer 2 = B…）。
- 每个 Layer 补：**Normal Map**（名带 _N/_Normal 的图；拖入若提示 "not marked as normal map, fix now" 点 Fix）、**Mask Map**（含 Metallic/AO/rough(or Detail Mask)/smoothness）。
- Base Color纹理如果带alpha通道，Smooth Source选项可使用该通道读取，选择“Diffuse Alpha Channel”
- **Tiling Size**：控制纹理每几米重复一次（先填 5×5 或 8×10 试；太小碎、太大糊）。

#### 4.4 用 splatmap 覆盖默认权重（Terrain Toolbox → Utilities → Terrain Splatmaps）
- **Import from Selected Terrain** 占好槽位（SplatAlpha 0…）。
- 把 Houdini 导出的 splatmap 指定进槽（通道对应 R→layer0，G→layer1，B→layer2）。
- 勾 **Preview Splatmap** 看分布（预览态显示 R=红/G=绿/B=蓝 的权重可视化，不是最终效果）。
- 核对方向（红=岩石应沿河道、绿=草应在坡面）；反了用 **Flip / Rotate Adjustment** 调，或回 Houdini 同 Flip 重导。
- **Apply to Terrain**（荧光色消失，真实纹理按权重铺上）。

#### 4.5 splatmap 导入的硬性格式要求（踩坑集合）
splatmap 图能被 Terrain Toolbox 接受并 Apply，需同时满足：
1. **分辨率 = Terrain 的 Control Texture Resolution**（案例：图 1024 → Terrain 设置页 Texture Resolutions → Control Texture Resolution 也设 1024；不等则 Select 时静默弹空、选不进去）。
2. **Read/Write 开启**（Advanced → Read/Write，勾）。
3. **Format = RGBA32 / ARGB32 / RGB24**（非压缩、可读；否则 Preview/Apply 报 "Texture format isn't compatable"）。
4. **sRGB 取消勾选**（权重数据，防 gamma 扭曲）。
5. **平台 override 检查**：改的是 Default 标签下的 Format，但当前平台（iOS）若有单独 override 会覆盖 Default → 需在对应平台标签下也设 RGBA32，或关掉该 override 使其回落 Default。
   > 原因：Terrain Toolbox 的 Preview/Apply 在 CPU 侧逐像素读 splatmap 权重，要求未压缩、可读格式（与 GPU 直接用的高度图不同）。

#### 4.6 两种 splatmap 来源（补充认知）
- **程序化生成（本项目方式）**：Houdini feature mask → 导出 PNG → Toolbox 导入。适合"材质严格对应地形数据（坡度/高度/河道）"的精确分布。出现在 Toolbox 导入列表。
- **Unity 内手刷**：Paint Texture 画笔在地形上刷，权重直接存入 TerrainData 内部（SplatAlpha 作为 TerrainData 子资产）。不走 Toolbox，故 Import 列表看不到。
- 二者产物相同（TerrainData 里的权重），可混用：程序打底 + 手工局部精修。

---

### 5. 减轻纹理重复感（tiling）——评估与取舍

**问题**：单张纹理平铺必然重复（有限图块无限平铺）。

**方案清单（按对本项目的适用性）**：
1. **植被覆盖**（首选，必做）：林地地面大面积被草/灌木/落叶/石头盖住，重复露不出多少。是最自然的解药，也是场景主体。
2. **调大 Tiling Size + 挂好 Normal**（低成本，已做）：拉长重复周期 + Normal 打散光影规律。缺点是 Size 太大近看糊。
3. **Terrain Detail 层**（内置）：Paint Details 撒草簇/碎石打断重复——但需额外贴片素材，且与 Houdini biome 散布重复，**本项目不用**。
4. **MicroSplat**（插件）：实时 shader 逐像素扰动 UV（旋转/缩放）+ Texture Clusters 破重复，效果最彻底。原理是生成 URP shader 由 GPU 运行、不产出可平铺图。但为 PC/高端优化居多，移动端需裁剪、有学习/版本兼容成本，**本项目暂不引入**（且版本卡 6.3，本项目 6.4）。
5. 自定义 terrain shader（Shader Graph/HLSL）：门槛高，不推荐。

> Shader Graph **不能**直接零代码替换 Terrain 的 shader（Terrain 有特殊多层/splatmap 接口）；能上但需手搭那套接口，非新手项目。

**结论**：本项目用 **1 + 2** 组合足够。验收标准是"第一人称漫游时可信"，非"俯视图完美"。符合反螺旋纪律：到"够用"即停。

---

### 6. 性能（iPad / 移动端）要点

- **地形本身不是瓶颈**：Unity Terrain 动态细分，100×100m + 2049 高度图对 M 系列 iPad 很轻。可把 Terrain 的 **Pixel Error** 调大（5 → 10-20）让远处更激进简化，第一人称几乎无差别。
- **splatmap 地表可参与烘焙光照**：splatmap（材质分布）与 lightmap（光影）是独立两层，最终相乘，不冲突。Terrain 勾 **Contribute Global Illumination** 即参与烘焙。属场景定型后的收尾步骤，现不做。
- **Depth / Opaque Texture 开销可忽略**：每帧一张全屏纹理，与场景复杂度/分辨率挂钩、与具体物体大小无关；空旷自然场景很轻，放心开。
- 真正的性能预算重点在**植被密度（instancing + LOD）**，其次实时阴影（靠烘焙）——均属后续环节。

---

### 附：本轮关键"地形"踩坑速查

| 现象 | 根因 | 修法 |
|---|---|---|
| 高度图导出全白 + 一条黑线 | HeightField Output 的 To Range 填成 -15/255（当 8-bit 像素） | To Range 改 **0, 1** |
| Unity 地形拉成深井 | Height Remap 填了原始 Houdini 高程（放大 10 倍） | Height Remap 填 **×0.1 的真实米制**（如 -1.15 ~ 24.3） |
| 地形比正常还平、河谷层次没了 | 高度图 PNG 被误勾 **sRGB** | 取消 sRGB，重建 Terrain |
| 陡坡/河岸垂直条纹破碎 | 高度图被 **压缩**（ASTC） | Compression = None，Max Size 8192 |
| Resample 设 2049 导出却 2050 | 格子/采样边界差 1 像素 | 无害，Toolbox 自动 resize |
| splatmap 选不进 SplatAlpha 槽（点了弹空） | 图分辨率 ≠ Terrain Control Texture Resolution | 两者设一致（如都 1024） |
| Preview/Apply 报 "format isn't compatable" | 格式非 RGBA32 / 未开 Read/Write | Format RGBA32 + 勾 Read/Write；检查 iOS 平台 override |
| 地形从侧面看像飘空薄片 | 相机视角贴地 | 选中 Terrain 按 **F** 聚焦 |
| 岩石变尖角（曾出现于 poly 路线） | polyreduce 牺牲高频 + 高度场表达不了悬垂 | 弃 poly 路线；岩石作独立散布 mesh |
---

## 三、植物导入流程：从 Houdini Biome 到 Unity

### 大树

> 记录范围：Houdini Biome Scatter 生成的植物散布点（位置/朝向/大小/种类）导入 Unity 的完整技术路径——路线选择、CSV 数据管线、Houdini 侧属性计算与导出、Unity 侧 Terrain Tree 种植工具。草地/地衣的 Detail 层分流、水面、光照另行记录。
> 环境：Houdini 21（Biome / SideFX Labs）、Unity 6.4、URP、目标平台 iPad（M 系列）。

**结论**：不走 Houdini Engine 实时插件，而是 **Houdini 端导出 CSV 散布表 → Unity 端脚本读取 → 写入 Unity Terrain 的 Tree Instances**（内置地形树系统）。大树、灌木走此路；草地、地衣走 Terrain Detail 层（另记）。

**理由**：
- **移动端性能**：Terrain 树实例由地形树系统统一渲染，自带 billboard/LOD/视锥剔除/批处理，几千棵树对 iPad 友好。而"直接实例化成独立 GameObject"则是几千个 MeshRenderer、几千 draw call，移动端需自己补 instancing/LOD，得不偿失。
- **不占 Engine 许可、管线解耦**：文件驱动（CSV）不依赖 Houdini Engine 插件与许可证，Houdini 与 Unity 两端各自独立，学生可在无 Houdini 的机器上重跑导入。
- **朝向无损**：Biome 的 orient 是纯 yaw（见 §4.3），恰好与 Terrain 树"只支持绕 Y 旋转"的限制吻合，走 Terrain 树不损失任何旋转信息。

**核心取舍认知**：三条路径的差别不是"哪个更简单"，而是**复杂度落在导入期还是运行期**。Terrain 树 = 导入期麻烦一次（一次性、可脚本化），运行期性能被 Unity 解决；直接实例化 = 导入期舒服，运行期性能得自己扛（而运行期正是 iPad 目标最吃紧处）。故选前者。

---

#### 1. 路线选择：三条候选路径

| 路径 | 机制 | 产物 | 代价 |
|---|---|---|---|
| A. Houdini Engine 点云实例化 | HDA 在 Unity 内 cook，点带 `unity_instance` 字符串属性 → 实例化 prefab | 独立 GameObject | 需 Engine 许可 + 插件；仅编辑器可用、须 Bake；移动端 GameObject 过多 |
| B. Terrain 树实例（本项目选用） | 散布点数据 → 写入 TerrainData 的 TreeInstance | 地形树实例（存于 TerrainData） | 导入期需适配 Terrain 规矩；只支持 yaw；草类不适用 |
| C. 文件驱动直接实例化 | CSV → Unity 脚本 `Instantiate` prefab | 独立 GameObject | 导入简单但运行期性能自理（instancing/LOD 全手动） |

- B 又分两个子变体：**B1** 走 Houdini Engine 的 `unity_hf_treeinstance_*` 特殊属性（实时、无中间文件、需许可）；**B2** 文件驱动（导出 CSV + 自写 Unity 脚本调 `TerrainData.SetTreeInstances`）。**本项目用 B2**。
- 关键澄清：`unity_hf_treeinstance_prototypeindex` 等属性**不是 Houdini 现成节点**，而是自己创建的、名字特殊的点属性，仅 Houdini Engine 插件 cook 时识别。既然 B2 不用插件，就完全不涉及这些属性。

---

#### 2. 数据管线架构：CSV 而非 JSON

- **只导每点的放置数据**：归一化 XZ 位置、yaw、pscale、树种 key。这是扁平表格 → **CSV 最简，Unity 解析零依赖**。
- **plant_definition 不导**：Biome 每点还带一个 plant_definition 字典（年龄段、竞争权重、降水/温度耐受、树干/树冠半径、meshvariant 路径等），信息虽多，但那是**每树种一份的 Biome 内部元数据，种树时用不到**。想留档留在 Houdini 侧即可——这也是不必上 JSON 的原因。
- 管线全貌：`Houdini（Wrangle 算属性 → Python SOP 导 CSV）→ CSV → Unity（脚本读 CSV → 注册 prefab 为 TreePrototype → 生成 TreeInstance 种到 Terrain）`。

---

#### 3. Houdini 侧：属性计算与导出

##### 3.1 节点链
`biome_plant_scatter`（Plant Points Output）→ **Attribute Wrangle**（input 1 接地形几何，用于取包围盒）→ **Python SOP**（写 CSV）。

##### 3.2 Attribute Wrangle（关键属性，run over Points）
```vex
// input 0 = biome 点，input 1 = 地形几何
// 归一化 XZ 到 0..1（基于地形包围盒）—— 见 §4.1 为何这一步自动吸收 10 倍尺度差
vector bmin, bmax;
getbbox(1, bmin, bmax);
f@nx = (@P.x - bmin.x) / (bmax.x - bmin.x);
f@nz = (@P.z - bmin.z) / (bmax.z - bmin.z);

// yaw（弧度），从 yaw-only 四元数取角 —— 见 §4.3
vector4 q = p@orient;               // (x,y,z,w) = orient[0..3]
f@yaw = 2.0 * atan2(q.y, q.w);

// 树种 + 株型 -> 唯一 key，如 "Poplar_med3" —— 见 §4.2
s@treekey = s@plant_name + "_" + s@name;
// pscale 已存在，不动
```

##### 3.3 Python SOP 导出（每套植被改文件名）
```python
node = hou.pwd(); geo = node.geometry()
out = hou.text.expandString("$HIP/export/trees.csv")   # shrubs.csv ...
with open(out, "w") as f:
    f.write("nx,nz,yaw,pscale,key\n")
    for pt in geo.points():
        f.write("{:.6f},{:.6f},{:.6f},{:.4f},{}\n".format(
            pt.attribValue("nx"), pt.attribValue("nz"),
            pt.attribValue("yaw"), pt.attribValue("pscale"),
            pt.attribValue("treekey")))
```

##### 3.4 CSV 格式
```
nx,nz,yaw,pscale,key
0.5123,0.8842,2.113,1.04,spure_med3
0.5210,0.8790,-1.552,0.87,Poplar_small2
```
一行一棵树，纯文本。放进 Unity 工程 `Assets/` 下即被识别为 TextAsset。

---

#### 4. 关键技术点

##### 4.1 坐标归一化自动吸收 10 倍尺度差（关键洞察）
- Terrain 树的 `TreeInstance.position` 是**归一化到 0–1** 的比例值（相对地形包围盒），与绝对尺寸无关。
- 因此 Houdini（1 单位=10 米）与 Unity（1 公顷）之间的 **10 倍空间尺度差、树间距，全被归一化自动处理**，`nx/nz` 不需 ×10。只要 Unity 地形本身尺寸正确，树的分布与间距就自动对。
- 与 §2（地形）"高度图无尺度、尺度由 Terrain 三数字决定"是同一思想的延续：**位置以比例表达，把绝对尺度外置给地形**。

##### 4.2 树种 key = plant_name + "_" + name（碰撞问题）
- Biome 每点带 `plant_name`（树种：Poplar/Beech/spure）与 `name`（株型：small1/med3/lage2…）。
- **必须两者合并**做 key：`name` 在不同树种间会重复（spure 的 med3 与 Poplar 的 med3 是完全不同的网格），单用 `name` 会张冠李戴。合并后唯一映射到一个 Unity prefab。

##### 4.3 orient 是 yaw-only（无倾斜损失）
- 实测 spreadsheet：`orient[0]=orient[2]=0`，配合 plant_definition 的 `randomizeyaw:180` → Biome 只给绕 Y 的随机偏航，无俯仰/倾斜。
- 纯 Y 四元数 `(0, sin(θ/2), 0, cos(θ/2))` → `yaw = 2·atan2(orient.y, orient.w)`。
- 结论：Terrain 树"只能绕 Y 旋转"的限制，对本项目**不损失任何信息**。

##### 4.4 坐标手性（镜像）
- Houdini（右手系）↔ Unity（左手系）会镜像。工具提供 `Flip X / Flip Z / Invert Yaw` 三开关（内部对归一化坐标做 `1-nx` / `1-nz`、对 yaw 取反）。
- 默认 `Flip Z + Invert Yaw`。**必须先导几个点、俯视对照 Houdini 分布轮廓验证方向**，试开关组合直到对上；对上后固定。与 §2.4 地形方向核对同理——方向必须在批量种植前定死。

##### 4.5 缩放分解（把两件事分清）
最终大小 = **Unity prefab 原始大小 × pscale × perSpecies 系数 × global 系数**。
- **10 倍空间尺度差不进这个式子**——它只影响位置（已被 §4.1 归一化吸收）。用户初始把"整体 10 倍"与"单株缩放"混为一谈，实为两件独立的事。
- **prefab 已是 Unity 尺度**（导入时已 ×10 调正），故单株大小从 prefab 来，起点系数为 1。
- **pscale 用作相对变化**：Biome 的 pscale 带每棵树的大小变化（也带真实尺度，如 spure≈10–15、Poplar≈2）。`Use Pscale` 开关决定是否乘入；关掉则同种树等大。
- **主体尺寸差异由不同 prefab 承载**（small1/med3/lage2 各是不同 prefab），pscale 是其上的细分。
- 调法：先导入看效果 → 整体偏了调 `Global Scale`，单种偏了调该行 `Scale Multiplier`，要等大就关 `Use Pscale`。heightScale/widthScale 以**树根 pivot** 为中心缩放（须确保 prefab 轴心在树根），即"局部缩放"非全局。

---

#### 5. Unity Terrain Tree 机制（导进来是什么）
- `TreeInstance` 字段：`position`（归一化 0–1，Y 由 snapToHeightmap 吸附地表）、`prototypeIndex`（指向 TreePrototype 列表）、`heightScale/widthScale`（对 prefab 的倍率）、`rotation`（弧度，仅 Y）。
- `terrainData.treePrototypes` = 有序 prefab 列表；`SetTreeInstances(instances, snapToHeightmap:true)` 一次写入。
- **产物形态**：树存进 **TerrainData 资产**，由地形树系统渲染；**不是 Hierarchy 里一个个 GameObject**。可在 Terrain 的 Paint Trees 工具里看到 prefab 列为树原型。这正是移动端友好（billboard/LOD/批处理）的原因。
- **固化性（踩坑）**：树一旦写入，尺寸/位置烘死在每个实例里。面板参数只是"下次生成用"，**改完必须重新 Import 才生效**，非实时。
- prefab 要求：带 **LODGroup + billboard** 才能享受远处 billboard（本项目 prefab 已具）；材质须 URP（否则粉红）。

---

#### 6. Unity 侧导入工具：TreeScatterConfig
Claude 编写的编辑器工具，一个 `.cs` 文件放进工程即用（`Assets/` 任意处）。

##### 6.1 设计
- **ScriptableObject 配置资产**（存 CSV 引用、key→prefab 映射、缩放/翻转参数）+ **CustomEditor** 面板。映射一次维护、长期复用。
- **字典映射 + Scan 自动提取**：拖入 CSV → 点 "Scan keys" → 自动列出所有唯一 key，用户只需把对应 Unity prefab 拖到每行旁（key 是文本、prefab 是拖槽，不碰路径/代码）。内部整数 prototypeIndex 脚本自算。
- **多套植被**：`Biome Sets` 列表，一套 Biome 一个元素（大树、灌木各一套 CSV + 各自映射），`Import All` 一次全种、prefab 跨套自动去重。

##### 6.2 关键踩坑：资产不能引用场景物体
- **现象**：Terrain 拖不进配置资产的槽（从 Hierarchy 拖也不行）。
- **根因**：`TreeScatterConfig` 是 Project 里的 **ScriptableObject 资产**，而 Unity 硬规则——**资产不能序列化对场景物体的引用**（场景物体无持久 GUID）。Terrain 是场景物体，故被拒。
- **修法**：把 Terrain 引用从"资产字段"挪到 **Editor 面板自身**（编辑器实例可临时持有场景引用），用 `EditorGUILayout.ObjectField(..., allowSceneObjects:true)` 绘制。映射等资产型数据不受影响。
- **副作用**：该 Terrain 槽仅在选中该资产期间有效，重新编译/切走再回来会变回 None，重拖即可（映射不丢）。

##### 6.3 操作流程
1. 脚本 + 各套 CSV 拖进工程，等编译完。
2. Project 右键 → Create → Houdini → Tree Scatter Config，命名。
3. 面板顶部 **Terrain** 槽：从 **Hierarchy** 拖地形物体（不是 Project 里的 TerrainData 资产）进来。
4. 每套 Biome：+ 一个 Set → 命名、拖 CSV → 点 "Scan keys" → 给每行 key 拖对应 prefab（Scale Multiplier 先留 1）。
5. **先验证坐标**：默认翻转开关，点 ▶ Import All → Console 看数量、Scene 俯视对轮廓；镜像/朝向不对就试 Flip 开关组合，重 Import 直到对上（覆盖式，无需先清）。
6. **再调大小**：整体调 Global Scale、单种调 Scale Multiplier、要等大关 Use Pscale，各自重 Import。

##### 6.4 参数速览
- `Flip X / Flip Z / Invert Yaw`：坐标手性修正（默认 Flip Z + Invert Yaw）。
- `Use Pscale`：是否乘 Biome pscale（默认开，带大小变化；关则等大）。
- `Global Scale`：全局尺寸倍率。
- 每行 `Scale Multiplier`：单树种/株型微调。

---

#### 7. 草地/地衣的分流（重要边界）
- Unity Terrain 有两套系统：**树系统**（TreeInstance，适合有体积、要 LOD/billboard 的大树、灌木）与 **Detail/草系统**（`DetailPrototype`，专渲染海量地被，成本低得多）。
- **草地、地衣点数极大，不能塞进树系统**，应走 Detail 层（导出格式类似，Unity 端换 `SetDetailLayer` 那套 API，另行实现）。
- 本工具负责大树 + 灌木；草地、地衣待做时另配 Detail 版导入器。

---

#### 附：本轮"植物导入"踩坑速查

| 现象 / 疑问 | 根因 / 原理 | 做法 |
|---|---|---|
| 该走哪条路把 Biome 树导入 Unity | Terrain 树=运行期省（移动友好），直接实例化=导入期省但运行期贵 | 选文件驱动 Terrain 树（B2） |
| 找不到 `unity_hf_treeinstance_*` 属性 | 那是 Houdini Engine 插件识别的自建特殊属性，非现成节点 | 文件驱动路线根本不用它 |
| 该导 CSV 还是 JSON | 每点放置数据是扁平表；plant_definition 是种级元数据、种树用不到 | CSV |
| 树的位置要不要按 10 倍换算 | Terrain 树位置归一化 0–1，与绝对尺度无关 | 不换算，归一化自动吸收 |
| 单用 `name` 做 key，松树变别的树 | `name`（med3 等）跨树种重复 | key = plant_name + "_" + name |
| Terrain 树只能 yaw，会丢倾斜吗 | Biome orient 本就是纯 yaw（randomizeyaw） | 无损，直接用 |
| 树分布左右/前后镜像 | Houdini 右手系 ↔ Unity 左手系 | Flip X/Z + Invert Yaw，导几点先验证方向 |
| Global Scale 设 0.1 树几乎没变小 | Use Pscale 开着，pscale≈10–15 把它乘回来 | 关 Use Pscale 或把 pscale 当相对变化 |
| Terrain 拖不进配置资产的槽 | 资产不能引用场景物体（无持久 GUID） | Terrain 改由 Editor 面板持有（allowSceneObjects） |
| 改了 scale 树没变 | 尺寸已固化进 TreeInstance，参数只影响下次生成 | 改完重新 Import（非实时） |
| 草/地衣也想用这个种 | 树系统不适合海量地被 | 走 Terrain Detail 层（另做） |

### 草

> 记录范围：Houdini Biome Scatter 生成的草地、地被、莓类、地衣等低矮植物分布信息，如何从点云转为每物种一张 density map，并在 Unity Terrain Detail 系统中按 density map 铺设草类 prefab。
> 环境：Houdini 21（Biome / SideFX Labs / HeightField）、Unity 6.4、URP、目标平台 iPad（M 系列）。

**结论**：草地、地被、莓类等海量低矮植物不走 TreeInstance，也不导出逐点 CSV，而是走 **Houdini 点云 → 每物种 density map → Unity Terrain Detail Layer**。Houdini 端负责把 Biome 点云按植物类型拆分，并用 `HeightField Mask by Object` 烘成分布图；Unity 端脚本扫描这些 PNG，给每张图绑定一个 detail prefab，再用 `TerrainData.SetDetailLayer()` 写入 Terrain 的 detail density layer。

**理由**：
- 草、莓类、地被的数量远高于树木和灌木，若按 TreeInstance 或普通 GameObject 实例化，会产生过多实例与渲染开销，不适合 iPad。
- Terrain Detail 系统本来就是为海量草、地被、碎石等小型重复对象设计，能够利用 Terrain 的 detail distance、density scale、patch culling、instancing 等机制。
- 低矮植物不需要逐株精确保留 yaw、pscale、年龄等点级属性；对自然场景而言，空间分布密度比单株身份更重要。因此把点云烘成 density map 更符合该类资产的表现目标。

**核心取舍认知**：大树/灌木要保留树种、朝向、尺寸等个体信息，所以导 CSV 写 TreeInstance；草/地被追求群落密度和覆盖范围，所以导 density map 写 Detail Layer。二者不是同一套导入逻辑，只是都以 Houdini Biome 的植物分布结果为源头。

---

#### 1. 路线选择：点云不直接进 Unity，而是烘成 density map

| 路径 | 机制 | 产物 | 评价 |
|---|---|---|---|
| A. 点云 CSV → GameObject 实例化 | 每个点实例化一个 prefab | Hierarchy 中大量独立物体 | 导入直观，但运行期开销高，不适合海量草 |
| B. 点云 CSV → Terrain TreeInstance | 把草当树写入 Terrain 树系统 | TerrainData 中大量 TreeInstance | 树系统适合大树/灌木，不适合草地与地被 |
| C. 点云 → density map → Terrain Detail（本项目选用） | 每物种一张灰度分布图，Unity 写入 detail layer | TerrainData 中的 detail density layer | 运行期最适合草类；与 Terrain Detail 系统匹配 |

本项目选择 C。Houdini 只负责生成每类植物的分布权重图；Unity 只负责把这些图转成 Terrain Detail 的整数密度图。这样做把复杂度放在导入期，运行期交给 Terrain Detail 系统处理，符合移动端自然场景的性能需求。

---

#### 2. Houdini 侧：从 Biome 点云导出每物种 density map

##### 2.1 前提：Biome Plant Define 中必须给每类植物唯一命名

在 `Labs Biome Plant Define` 中，每一个放入生态系统的植物条目都要设置唯一的 `Name`，例如：

```text
strawberry
blackberry
small_grass1
small_grass2
sedge
```

该名称会随 Biome Scatter 输出的点云进入点属性。后续所有自动拆分、编号、逐帧输出文件名，都依赖这个唯一名称。如果不同植物共享同一个 `name`，后续就无法把它们拆成不同 density map。

##### 2.2 节点链

本项目中用于提取地被植物 density map 的核心节点链如下：

```text
biome_plant_scatter
→ biome_groundCover_points（Null，取 Ground Cover 点云）
→ attribwrangle8（生成 variant_key）
→ enumerate1（按 variant_key 给植物类型编号）
→ attribpromote1（统计类型总数 variantN）
→ delete1（按当前帧只保留一种植物）
→ plants_type1（Null，当前帧对应的单一植物点集）
→ copytopoints3（把小球复制到这些点上）
→ heightfield_maskbyobject6（用小球在地形上生成 mask）
→ heightfield_maskblur3（轻微模糊分布图）
→ heightfield_output3（逐帧导出 PNG）
```

其中左侧地形输入为：

```text
get_terrain_with_ground_cover_mask
→ heightfield_resample
→ heightfield_maskbyobject
```

`heightfield_resample` 的作用是保证输出 density map 的分辨率与 Unity 侧 Terrain Detail Resolution 对齐。本轮测试中使用的是 `1500 × 1500`。

##### 2.3 Attribute Wrangle：把植物名称保存为 variant_key

在 `attribwrangle` 中，把 Biome 点云中的植物名称转存为用于分类的字符串属性：

```vex
s@variant_key = s@name;
```

这里的 `name` 来自 `Labs Biome Plant Define` 中对每个植物条目的命名。`variant_key` 的作用是作为后续 `Enumerate` 的 piece attribute，也作为导出文件名的来源。

##### 2.4 Enumerate：按植物名称给点集编号

`enumerate` 的设置为：

```text
Group Type       = Points
Piece Attribute  = variant_key
Mode             = Enumerate Pieces
Attribute        = variant_id
Type             = Integer
```

它的作用是把同一个 `variant_key` 的点归为同一类，并给每一类分配一个整数编号：

```text
variant_key = small_grass2  → variant_id = 0
variant_key = blackberry    → variant_id = 1
variant_key = sedge         → variant_id = 2
...
```

具体编号顺序不需要手工控制，只要同一次导出中稳定即可。真正用于文件命名的是 `variant_key`，不是 `variant_id`。

##### 2.5 Attribute Promote：记录植物类别总数

在 `attribpromote1` 中，把点属性 `variant_id` 提升为 detail 级统计属性，用于获得一共有多少类植物。设置逻辑为：

```text
Original Class   = Point
New Class        = Detail
Original Name    = variant_id
Promotion Method = Maximum
New Name         = variantN
```

由于 `variant_id` 从 0 开始编号，所以 `variantN` 记录的是最大编号。导出帧范围需要写成：

```text
1 - detail("../plants_type1/", "variantN", 0)
```

实际使用时需要注意：如果有 N 类植物，而编号为 `0 ... N-1`，最大编号是 `N-1`。因此帧号与类型编号通过 `variant_id == $F - 1` 对应。根据实际节点输出，如果发现最后一类没有导出，应把结束帧改为 `detail("../plants_type1/", "variantN", 0) + 1`。

##### 2.6 Delete：逐帧只保留一种植物点

`delete` 使用 `Delete by Expression`，表达式为：

```text
@variant_id==$F-1
```

该节点的目标是让每一帧只对应一种植物。第 1 帧保留 `variant_id = 0` 的点，第 2 帧保留 `variant_id = 1` 的点，以此类推。这样同一套节点网络可以在不同帧自动切换当前植物类型，并逐帧导出对应 density map。

如果节点的删除语义导致结果相反，即当前类型被删除而其他类型被保留，则应改用互补表达式：

```text
@variant_id!=$F-1
```

判断标准很简单：查看 `plants_type(null)`，当前帧应该只剩一种植物的点。如果还剩多种植物，说明 Delete 表达式方向需要反过来。

##### 2.7 用小球把点云转成 HeightField mask

点本身不能直接作为 heightfield mask 的面积来源，所以使用一个小球作为体积代理：

```text
sphere → copytopoints
plants_type → copytopoints
```

`copytopoints` 会在当前植物点集上复制出一批小球。随后把这些小球送入 `heightfield_maskbyobject`，在原始地形上生成该植物的覆盖 mask。

该方法的含义是：每个植物点不是直接变成一个 Unity 草实例，而是先在 Houdini 中变成一个小的覆盖区域；这些覆盖区域叠加后形成该植物在地形上的 density map。小球半径越大，分布图越连续；小球半径越小，分布图越接近原始点云。

##### 2.8 Mask Blur：让分布图更自然

`heightfield_maskblur` 对 `heightfield_maskbyobject` 生成的 mask 做轻微模糊。该步骤的目的不是制造大面积糊化，而是消除点状小球边缘过硬的问题，让 Unity 侧的草簇分布有柔和过渡。

模糊程度不宜过大。过大的 blur 会让不同植物的生态边界变得不清楚，也会导致本来应该稀疏的地被扩散到不合适的位置。

##### 2.9 HeightField Output：逐帧导出每类植物的 PNG

`heightfield_output` 负责逐帧保存 density map。核心设置如下：

```text
Output Type = Packed Raster
Format      = RGB
Type        = 16b Fixed
```

Output Layers 中把同一个 `mask` 写入 R/G/B 三个通道：

```text
Red   = mask
Green = mask
Blue  = mask
```

因此 Unity 侧读取任意一个颜色通道都可以得到同样的密度信息。之前曾怀疑读取红色通道可能导致全 0，但本项目的 Houdini 输出已经明确把 mask 同时写入 RGB，所以该问题可以排除。

帧范围设置为：

```text
Start = 1
End   = detail("../plants_type1/", "variantN", 0)
```

或在需要包含最大编号对应类型时使用：

```text
End = detail("../plants_type1/", "variantN", 0) + 1
```

文件名表达式为：

```text
$HIP/Plant_distribution/`points("../plants_type1",0,"variant_key")`.png
```

该表达式会读取当前帧 `plants_type1` 中第 0 个点的 `variant_key`，并用它作为输出文件名。因此导出的结果类似：

```text
blackberry.png
CONIbramble.png
CONIcreeper_large.png
CONIcreeper_small.png
large_grass1.png
large_grass2.png
sedge.png
small_grass1.png
small_grass2.png
strawberry.png
```

##### 2.10 Houdini 侧验收

导出后在 Finder 或图像查看器中检查：

1. 每类植物应有一张同名 PNG。
2. 图中应为黑底灰白分布，白色区域代表较高密度，黑色区域代表无分布。
3. 图像分辨率应与 Unity 侧 Detail Resolution 保持一致，例如 `1500 × 1500`。
4. 若某张图完全黑，优先检查当前帧的 `plants_type1` 是否真的保留了对应植物点。
5. 若文件名错误或重复，优先检查 `Biome Plant Define` 中的 `Name` 是否唯一，以及 `variant_key` 是否正确生成。

---

#### 3. Unity 侧：从 density map 写入 Terrain Detail Layer

##### 3.1 总体流程

Unity 侧使用 `GrassDetailConfig.cs` 编辑器工具完成导入。流程是：

```text
扫描 density map 文件夹
→ 每张 PNG 生成一个 Species entry
→ 手工给每个 entry 指定一个 detail prefab
→ Apply To Terrain
→ 脚本创建 DetailPrototype 列表
→ 脚本读取 PNG 灰度并转换为整数密度图
→ TerrainData.SetDetailLayer() 写入 Terrain
```

该工具不在 Hierarchy 中实例化草物体。最终草数据写入 TerrainData 的 detail layers，由 Unity Terrain Detail 系统统一渲染。

##### 3.2 操作流程

1. 将 Houdini 导出的 PNG 文件夹放入 Unity 工程，例如：

```text
Assets/_Project/Textures/Plant_Map/
```

2. Project 面板右键创建配置资产：

```text
Create → Houdini → Grass Detail Config
```

3. 在配置面板中拖入场景里的 Terrain。注意这里拖的是 Hierarchy 中的 Terrain 物体，不是 Project 中的 TerrainData 资产。

4. 在 `Density Map Folder` 中指定保存 PNG 的文件夹。

5. 点击：

```text
Scan Folder For Density Maps
```

脚本会自动按 PNG 文件生成物种列表。每个 PNG 对应一个 detail layer。

6. 对每个物种手工指定对应的草、地被或莓类 prefab。

7. 点击：

```text
Apply To Terrain
```

脚本会把这些 prefab 注册为 `DetailPrototype`，并把对应 density map 写入 Terrain 的 detail layer。

##### 3.3 Detail prefab 的关键要求

本轮踩坑的核心问题是：**不能直接把带 LODGroup 的根 prefab 作为 Terrain Detail Prototype。**

最初使用的是类似下面这种结构的 prefab：

```text
Coni_Grass2 Variant
├─ Grass2_LOD0(Clone)
├─ Grass2_LOD1(Clone)
└─ Grass2_LOD2(Clone)
```

这个根 prefab 带 `LOD Group`，真正的 `MeshFilter` 和 `MeshRenderer` 在子物体上。它可以作为普通场景物体使用，也可以由普通 LODGroup 管理，但不适合作为 Terrain Detail 的直接 prototype。使用这种 prefab 时，Terrain 的 Paint Details Control 中能看到 prototype 已加载，但地形上可能完全不显示。

正确做法是把 LOD0 子对象单独做成一个独立 prefab，例如：

```text
Grass2_LOD0.prefab
└─ 根节点：MeshFilter + MeshRenderer + Material
```

操作方式：

1. 把原始植物 prefab 临时拖入场景。
2. 在 Hierarchy 中展开它，选中 `LOD0` 子物体。
3. 把该子物体拖回 Project 面板，生成新的独立 prefab。
4. 在 `GrassDetailConfig` 中使用这个独立 LOD0 prefab，而不是原始 LODGroup 根 prefab。

本轮测试确认：独立 LOD0 prefab 可以手绘，也可以由脚本按 density map 正确生成。

##### 3.4 手绘测试：先验证 prefab，再验证脚本

排查时应先进入 Terrain 的 `Paint Details`，选中指定 detail prototype，用画笔手动画一小块。

- 如果手绘都看不到，问题在 prefab、材质、shader、Terrain detail 显示设置或全局密度设置，不应继续查 density map。
- 如果手绘能看到，而脚本 Apply 后看不到，问题才集中到脚本写入 density layer 的过程。

本轮测试中，`Grass2_LOD0(Clone)` 手绘可以显示，说明 prefab 与材质本身可用于 Terrain Detail。

##### 3.5 诊断结果：density map 读取与 SetDetailLayer 已确认成功

脚本中加入读写统计后，`small_grass2` 的测试结果为：

```text
[GrassDetailConfig] small_grass2 BEFORE SetDetailLayer: nonZero=427425/2250000, max=82, sum=7877889, mult=100, png=1500x1500
[GrassDetailConfig] small_grass2 AFTER GetDetailLayer: nonZero=427425/2250000, max=82, sum=7877889
[GrassDetailConfig] Applied 1 detail layer(s) at 1500x1500. detailWidth=1500, detailHeight=1500, detailObjectDensity=1, detailObjectDistance=120
```

该结果说明：

1. PNG 被正确读取。
2. 生成的 density map 不是空图。
3. `SetDetailLayer()` 写入成功。
4. `GetDetailLayer()` 读回值与写入值完全一致。

因此可以排除以下问题：

```text
density map 没读到
density 被写成全 0
SetDetailLayer 没有生效
TerrainData 没有保存 detail layer
```

##### 3.6 渲染模式与 instancing

诊断阶段曾把 `useInstancing` 临时改为 `false`，结果草可以显示但材质变成白色。这说明非 instancing 路径没有正确表现原植物 shader 的贴图。

恢复：

```csharp
useInstancing = true;
```

之后草的贴图恢复，说明当前使用的 `MK4/URP/Plants Waving` 材质可以在 Terrain Detail instancing 路径下工作。本项目正式使用时应保持 `useInstancing = true`。

##### 3.7 密度参数

测试时 `Density Multiplier` 曾设为 `100`，因此日志中出现：

```text
max=82
sum=7877889
```

这证明脚本写入成功。每次调整后观察视觉覆盖率，并在 iPad 真机上检查帧率。原则是先达到自然覆盖，再考虑局部加密，而不是用高密度掩盖地表纹理重复问题。

##### 3.8 方向与对齐

工具提供：

```text
Flip X
Flip Z
Transpose
```

这三个开关用于匹配 Houdini 输出图与 Unity Terrain 坐标方向。由于 heightmap、splatmap、density map 都来自 Houdini，三者方向必须保持一致。建议先只用一种草图测试方向：若分布区域与 Houdini 中对应植物点云轮廓一致，则锁定这些开关；不要每种植物分别调方向。

##### 3.9 清空与重导

`Clear All Details On Terrain` 会清空 Terrain 上的 detail prototypes 和 detail layers。排查时建议先清空，再 Apply，避免手绘草与脚本生成草混在一起。

注意：脚本参数修改后需要重新点击 `Apply To Terrain`。Terrain Detail 数据写入 TerrainData 后并非实时链接 PNG；改了密度图、prefab 或 multiplier，都要重新 Apply。

##### 3.10 混合 Unity Paint Detail 方法

该方法用于把 Houdini 程序化生成的草类 density map 与 Unity Terrain 的手工 Paint Details 编辑结合起来。目标不是放弃 Houdini 的 Biome 大结构，而是在 Unity 中完成局部视觉修正，并把修正结果重新写回当前 density map PNG，使后续重新 Apply 时仍然保留手工修改。

**核心结论**：Unity Paint Details 修改的不是 Houdini 导出的 PNG 文件，而是 Unity `TerrainData` 内部的 detail density layer。`GrassDetailConfig` 的 `Apply To Terrain` 会把外部 PNG 重新转换为 Unity 内部 detail layer；因此，如果只在 Unity 中手工刷草或擦草，而不把结果写回 PNG，下一次 Apply 会用原 PNG 覆盖掉这些手工修改。

两层 map 的关系如下：

```text
Houdini / Unity Project 中的外部 density map PNG
    例如：small_grass2.png
    作用：作为 GrassDetailConfig 的输入源图

Unity TerrainData 内部 detail density layer
    作用：Terrain 当前真正用于显示草的内部密度栅格
```

因此实际数据流为：

```text
small_grass2.png
→ GrassDetailConfig Apply To Terrain
→ TerrainData.DetailLayer[small_grass2]
→ Unity Paint Details 手工擦除 / 补充
→ Bake Manual Edit to Map
→ 覆盖 small_grass2.png
```

##### 3.10.1 Unity Paint Details 的作用边界

Unity 的 Paint Details 工具可以直接修改当前 Terrain 上某一种草的 detail layer：

- 用较高 `Target Density` 刷，会增加该草层的局部密度。
- 把 `Target Density` 改为 `0` 再刷，可以删除该草层的局部密度。
- 该操作只影响当前选中的 detail prototype，不会自动影响其他草种。
- 该操作会改变 Unity 当前 TerrainData 中的内部 detail layer，但不会自动修改 `small_grass2.png`、`blackberry.png` 等外部源图。

所以 Paint Details 适合做：

```text
小溪边缘草穿帮 → 局部擦除
近景地面过空 → 局部补草
某些莓类或地被进入不合适区域 → 局部降低密度
镜头前景需要更自然 → 少量手工加密
```

但 Paint Details 不适合作为唯一长期数据源。如果之后还要反复执行 `Apply To Terrain`，就必须把手工修改通过 Bake 写回 PNG。

##### 3.10.2 Bake Manual Edit to Map 的功能

新增按钮：

```text
Bake Manual Edit to Map
```

该按钮的作用是把 Unity 当前 TerrainData 中的 detail layer 反向写回对应的 density map PNG。它不是另存为 `_baked` 文件，而是直接覆盖当前 entry 使用的 PNG。这样做符合当前工作流：Houdini 随时可以重新导出原始大结构，Unity 只负责把当前人工精修结果落盘回同一个 map 文件，避免产生大量临时文件。

功能逻辑为：

```text
读取当前 TerrainData.DetailLayer
→ 按 entry 与 detail layer 的映射找到对应 PNG
→ 将整数密度反算为灰度值
→ 按当前 flip / transpose 关系写回原始 PNG 坐标
→ 覆盖当前 densityMap 文件
→ AssetDatabase 刷新
```

Bake 后，再执行：

```text
Clear All Details On Terrain
→ Apply To Terrain
```

如果之前手工擦除或补充的区域仍然保留，就说明 Bake 成功。

##### 3.10.3 为什么必须先 Apply 再 Bake

Bake 需要知道每个 `GrassEntry` 对应 Terrain 中的哪一个 detail layer。这个对应关系不是 Unity Terrain 原生存储的语义字段，而是由 `GrassDetailConfig` 在 `Apply To Terrain` 时建立并记录。

因此脚本在 `GrassEntry` 中记录以下隐藏字段：

```text
stableId              基于 density map GUID 的稳定 entry 标识
lastAppliedLayer      上一次 Apply 时写入的 Terrain detail layer 编号
lastAppliedMapGuid    上一次 Apply 使用的 density map GUID
lastAppliedPrefabGuid 上一次 Apply 使用的 prefab GUID
```

这些字段用于保证 Bake 时不会把某一层草错误写回另一张 PNG。按钮逻辑为：

- 未执行过成功 Apply 时，`Bake Manual Edit to Map` 不可用。
- 如果改过 entry、删除 entry、替换 prefab、替换 density map，必须先重新 `Apply To Terrain`，再 Bake。
- Bake 时会检查当前 Terrain 的 detail prototype 是否仍然与 entry 的 prefab 匹配。
- Bake 时会检查当前 entry 的 map / prefab 是否与上次 Apply 记录一致。
- 如果检查不通过，该 entry 会被跳过，并在 Console 中输出 warning。

这个机制避免了单纯依赖列表顺序造成的错写风险。虽然 entries 在面板中可以被删除或重新组织，但只要遵循“改结构后先 Apply，再 Bake”的规则，映射关系就是安全的。

##### 3.10.4 坐标与 flip / transpose 的处理原则

Bake 的目标是“只修改原始 PNG 中对应像素的灰度，不额外改变方向参数”。因此，Bake 不会把当前 `flipX / flipZ / transpose` 的结果永久叠加到图像方向里，而是按 Apply 时使用的同一套坐标映射，把 Unity 内部 detail layer 写回原始 PNG 的对应坐标。

换句话说：

```text
Apply：PNG 像素 → 按 flip / transpose 采样 → Unity detail layer
Bake：Unity detail layer → 按同一坐标关系反写 → PNG 像素
```

这样做的目的，是保证以后再次导入时，面板中的 `flipX / flipZ / transpose` 参数仍然具有同样含义，不会出现“图像方向已经被 Bake 改过一次，导入参数又再翻一次”的叠加混乱。

##### 3.10.5 推荐操作流程

正式推荐流程如下：

```text
1. Houdini 导出每种草 / 地被的 density map PNG。
2. Unity 中 Scan Folder For Density Maps。
3. 给每个 entry 指定独立 LOD0 detail prefab。
4. 点击 Apply To Terrain。
5. 使用 Unity Paint Details 局部擦除或补充草层。
6. 点击 Bake Manual Edit to Map，把当前 Terrain detail 状态覆盖回 PNG。
7. 后续若需要重建 Terrain detail，点击 Clear All Details On Terrain 后再 Apply To Terrain。
```

如果第 7 步重新 Apply 后，手工修过的区域仍然保留，说明 Unity 手工修改已经成功进入 density map 源数据。

##### 3.10.6 风险与使用规则

1. **Bake 会覆盖当前 PNG**。如果需要回到 Houdini 原始分布，直接从 Houdini 重新导出即可。
2. **Bake 保存的是当前完整 detail layer，不是差异补丁**。它不会区分哪些像素来自 Houdini，哪些来自 Unity 手刷。
3. **不要在改 entry 之后直接 Bake**。替换 prefab、替换 map、删除 entry、重新扫描文件夹后，都应先 Apply。
4. **Bake 会遍历所有有效 entries**。它不追踪“用户刚刚画的是哪一层”，而是把当前 Terrain 中所有已映射草层同步回各自 PNG。
5. **Density Multiplier 会参与反算**。Bake 时会用当前 entry 的 `Density Multiplier` 把 Unity 内部整数密度反算为 PNG 灰度值。因此，手工精修前后不宜随意大幅修改 multiplier；如果修改了 multiplier，应先 Apply，再进行 Paint 和 Bake。

##### 3.10.7 当前完整工作流

最终形成的草类管线为：

```text
Houdini Biome 生成大结构植物分布
→ 每类植物导出一张 density map PNG
→ GrassDetailConfig 扫描 PNG 并绑定 detail prefab
→ Apply To Terrain 写入 Unity Terrain Detail Layer
→ Unity Paint Details 做局部精修
→ Bake Manual Edit to Map 覆盖回当前 PNG
→ 后续重新 Apply 时保留 Unity 精修结果
```

该流程把 Houdini 的程序化分布与 Unity 的直观手工编辑合并为一条可重复管线。Houdini 负责生态结构和大范围规则，Unity 负责近景和局部体验修正，最终结果仍然落回同一批 density map 文件，便于继续迭代。

---

#### 4. 当前已解决问题与正式规则

##### 4.1 已解决问题

| 现象 | 根因 | 修法 |
|---|---|---|
| Paint Details Control 中能看到草 prefab，但地形上什么都没有 | 使用了带 LODGroup 的根 prefab，Terrain Detail 无法直接渲染该复合结构 | 从原 prefab 中提取 LOD0 子物体，做成根节点直接带 MeshFilter + MeshRenderer 的独立 prefab |
| 脚本运行后不确定是否真的写入 density | 原脚本只打印 Applied，不能证明 density map 有值 | 加入 BEFORE / AFTER 统计，用 `GetDetailLayer()` 读回验证 |
| 诊断时草显示为白色 | 临时关闭 `useInstancing` 后，植物 shader 在非 instancing 路径下贴图表现异常 | 恢复 `useInstancing = true` |
| Console 出现重复类定义错误 | 项目中存在重复的 `GrassDetailConfig.cs` 或同名类定义 | 删除重复脚本，只保留一份 `GrassEntry / GrassDetailConfig / GrassDetailConfigEditor` |

##### 4.2 正式使用规则

1. **Houdini 侧每个植物名称必须唯一**。该名称同时决定分类、输出文件名和 Unity 侧物种 entry。
2. **每种草/地被导出一张 PNG density map**。RGB 三通道都写入同一个 `mask`，Unity 读取红通道即可。
3. **Unity 侧每张 PNG 对应一个 DetailPrototype**。不要把多种植物混在同一张 density map 中。
4. **Detail prefab 使用独立 LOD0 mesh prefab**。不要直接使用带 LODGroup 的根 prefab。
5. **正式运行保持 `useInstancing = true`**。该设置既有利于性能，也能正确表现当前植物材质。
6. **Density Multiplier 从低值开始调**。测试值 100 不作为正式参数。
7. **方向开关只校准一次**。heightmap、splatmap、density map 应统一方向，不应各自独立翻转。
8. **所有修改后重新 Apply**。Terrain Detail 数据写入后是 TerrainData 内部状态，不会自动跟随 PNG 或参数实时更新。

#### 附：本轮“草 / Terrain Detail”踩坑速查

| 现象 / 疑问 | 根因 / 原理 | 做法 |
|---|---|---|
| 草类能不能像树一样导 CSV | 可以但不合适；草数量太大，逐点实例化或 TreeInstance 都不适合 | 走 density map + Terrain Detail |
| Biome 点云怎么拆成不同植物 | 每点有 `name`，先存成 `variant_key`，再用 Enumerate 编号 | `s@variant_key = s@name;`，Enumerate Pieces |
| 每帧怎么只导出一种植物 | 用 `variant_id` 和帧号对应 | `@variant_id==$F-1` 或按 Delete 语义改成 `!=` |
| 点云怎么变成分布图 | 点没有面积，不能直接作为 heightfield mask | 用小球 Copy to Points，再 Mask by Object |
| 导出的 PNG 为什么读红通道即可 | Houdini 输出时把同一个 mask 写入 RGB 三通道 | Unity 读 `.r` 没问题 |
| Paint Details 里有 prototype，但地形上无草 | prototype 创建成功不等于可渲染；LODGroup 根 prefab 不适合 Detail | 提取 LOD0 子对象为独立 prefab |
| LOD0 子对象为什么一开始拖不进槽 | prefab 内部子对象不是 Project 中的独立 prefab asset | 先从 Hierarchy 拖到 Project 生成独立 prefab |
| 手绘能显示但脚本不显示 | prefab 没问题，应查 density layer 写入 | 用 `GetDetailLayer()` 读回 nonZero / max / sum |
| 关闭 instancing 后草变白 | shader 非 instancing 路径贴图表现异常 | 正式使用 `useInstancing = true` |
| 密度调到 100 可以吗 | 诊断可以，正式不建议；一簇草 prefab 会造成过高实例密度 | 从 4/8/16 起调，并用 iPad 真机验证 |
