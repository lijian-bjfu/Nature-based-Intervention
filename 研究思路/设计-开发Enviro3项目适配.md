# 设计-开发 Enviro 3 项目适配

> 记录时间：2026-09-11
> 涉及插件：Enviro 3 - Sky and Weather (v3.3.2)，及其与 MicroSplat、River Auto Material 3 (RAM)、Gaia/GeNa、URP 管线的兼容性问题
> 项目环境：Unity 6000.4.10f1，URP，Build Target: iOS，项目路径 `/Users/lijian/Working Projects/NBI proj/nature`

本记录按接入 Enviro 3 的实际时间顺序整理，每个问题包含：**现象 → 根因 → 解决方案 → 涉及文件**，供以后同类问题排查时查阅，也作为决定"要不要继续用这个插件"的参考依据。

---

## 一、接入阶段：URP 支持激活失败

### 现象
Enviro Manager 面板点击 "Activate URP Support" 按钮无反应，"Render Pipeline" 始终显示 "Legacy"，且点击后编辑器一度卡住、鼠标转圈。

### 根因（两层）
1. **插件文件夹位置错误**：最初把 Enviro 3 放在 `Assets/ThirdParty_Plugins/Enviro 3 - Sky and Weather/` 下，但 Enviro 的部分 shader（如 `Enviro3/Particles/WeatherParticles`）使用**硬编码的绝对 include 路径**，写死指向 `Assets/Enviro 3 - Sky and Weather/...`，多套一层目录就导致 shader 编译失败，进而引发 `EnviroManager.Update()` 每帧反复触发 `LoadConfiguration()` 的死循环，造成编辑器持续卡顿、Editor.log 暴涨至 1.7GB。
2. **iOS 平台兼容性 bug**：Enviro 的 "Activate URP Support" 按钮内部通过遍历 `BuildTargetGroup` 枚举、过滤掉标记为 `[Obsolete]` 的平台，来给各平台加 `ENVIRO_URP` 宏。但在 Unity 6000.4.x 中 `BuildTargetGroup.iOS` 恰好被判定为过时，于是被这段过滤逻辑**主动跳过**，导致 iOS 平台永远拿不到这个宏，不管点多少次按钮都没用。

### 解决方案
1. 把插件文件夹从 `Assets/ThirdParty_Plugins/Enviro 3 - Sky and Weather/` 移动到 `Assets/Enviro 3 - Sky and Weather/`（与插件 shader 里写死的路径一致）。
2. 编写 `Assets/Editor/EnviroURPFix.cs`，用 `[InitializeOnLoad]` 在编辑器加载时自动检测并调用 `PlayerSettings.SetScriptingDefineSymbols(NamedBuildTarget.iOS, ...)`，直接给 iOS 平台加上 `ENVIRO_URP` 宏，绕开 Enviro 自己那段会跳过 iOS 的逻辑。

### 涉及文件
- `Assets/Editor/EnviroURPFix.cs`（保留至今，只要还在用这个 Unity 版本 + iOS Build Target 就需要）

### 后续通用经验
- 任何第三方插件涉及"往 Scripting Define Symbols 里加宏"的自动化按钮，如果目标平台在当前 Unity 版本里被标记为 Obsolete，都可能被跳过——遇到"点了按钮没反应"，可以先查插件源码里是否用了 `BuildTargetGroup` 遍历 + Obsolete 过滤这种写法。

---

## 二、URP 渲染功能未生效：Fog / 反射看不到效果

### 现象
Fog 勾选打开、参数也设置了，场景里却看不到任何雾；Reflection Probe 设置好之后水面反射也不对。

### 根因
Enviro 文档里 "Activate URP Support" 之后其实还有几步没做完：需要手动在 URP Renderer 资产（`Mobile_Renderer.asset`、`PC_Renderer.asset`）里 **Add Renderer Feature → Enviro URP Render Feature**，并确认 "Depth Texture" 选项开启。这一步在最初被 iOS 宏定义 bug 岔开后忘记回来补上。查了两个 Renderer 资产文件，确认里面完全没有 "Enviro" 相关的 Render Feature。

### 解决方案
在 `Assets/Settings/Mobile_Renderer.asset` 和 `PC_Renderer.asset` 里都手动 Add Renderer Feature → Enviro URP Render Feature，并确认 Depth Texture 打开。

### 通用经验
- **凡是"面板参数看起来对，但视觉上完全没反应"，先怀疑 URP Renderer Feature 有没有装**，这是 Enviro（以及很多需要屏幕空间特效的 URP 插件）的常见坑，装一次即可，多个 Renderer（Quality 里配置的多套）要分别装。

---

## 三、编辑器卡顿排查（教训：不要过早归因于 Enviro）

### 现象
接入 Enviro 之后编辑器时不时卡顿，鼠标转圈。

### 排查过程与教训
先后怀疑过三个原因，**只有一个是真正验证过的**：
1. **最初的猜测**：Reflection Probe 设置成 Realtime + "All Faces At Once" + 高频刷新（0.025s），理论上确实会造成周期性卡顿——但**这只是根据配置做的合理推测，没有做过系统级验证**。
2. **用 `sample` 命令做过一次真实验证**：抓取 Unity 进程 5 秒 CPU 采样，发现热点函数全是 URP 渲染管线本身的工作（可见性剔除、绘制指令提交等），"Enviro"、"GeNa"、"Gaia" 关键词在采样里几乎不存在。**结论：卡顿很可能和 Enviro 本身无关，而是 Scene 视图的 "Animated Materials" 开关（水面/风力摇摆植被的动画预览）导致编辑模式下持续全屏重绘。**
3. 即使后来把 Enviro 3 整个 GameObject 禁用，卡顿依然存在，进一步印证了第 2 点的判断——**说明"感觉卡顿是从接入插件开始的"这种时间线巧合，不能直接当作因果关系**，很可能这个卡顿一直都存在，只是之前没注意到。

### 结论
**没有实锤证据证明 Enviro 本身是编辑器卡顿的元凶。** 如果以后再遇到类似卡顿，建议：
1. 优先检查 Scene 视图着色模式菜单里的 "Animated Materials" 开关。
2. 用 macOS 自带的 `sample <pid> <秒数> -f 输出文件.txt` 对 Unity 进程做真实 CPU 采样，看 "Sort by top of stack" 部分的热点函数，不要凭配置推测。
3. 同时排查项目文件夹有没有被云同步软件（见下一节）监视。

---

## 四、百度网盘同步干扰

### 现象
（独立于 Enviro 的卡顿疑似成因之一，Codex 排查出的角度）Unity 编辑器周期性卡顿，Console 报 `SearchTask 'Update' thread did not stop within 5 seconds`，`Library/Search` 索引一度膨胀到 2.5GB+。

### 根因
项目整个文件夹被纳入了百度网盘（BaiduNetdisk）的同步范围。`Library`、`Temp` 这类 Unity 内部缓存文件夹内容变化极其频繁，百度网盘在后台持续扫描/尝试上传，跟 Unity 自己的索引读写产生文件锁冲突。验证方式：`ps aux | grep -i baidu` 确认同步进程常驻；`find .../Library -iname "*.baiduyun*"` 能找到多个 `.baiduyun.uploading.cfg` 标记文件散落在 Library 内部。

### 解决方案
把项目目录（至少 `Library`、`Temp`、`Logs`、`Obj` 这几个 Unity 缓存目录）加入百度网盘客户端的**排除同步列表**。

### 通用经验
- 任何 Unity 项目文件夹，只要接入了云同步工具（百度网盘/iCloud/OneDrive 等），都应该默认排除 `Library`、`Temp`、`Obj`、`Logs` 这几个目录，这是通用最佳实践，不限于 Enviro。

---

## 五、光照/材质相关问题（部分与 Enviro 的天空天气系统相关，部分是接入过程暴露出的既有问题）

### 5.1 阴影发白发粉（过曝）
- **现象**：接入 Enviro 天空盒后，树荫、阴影区域出现不自然的粉白色，看起来"发糊"。
- **根因**：Enviro 输出的光照是 HDR、无上限的，必须配合 **Tonemapping（色调映射）** 使用；项目最初没有配置 Tonemapping。
- **解决**：在 Global Volume 的 Profile 里 Add Override 加 **Tonemapping**，模式设为 **ACES**（Enviro 官方文档推荐）。

### 5.2 反射探针 Realtime → Baked
- **现象**：反射效果开销大、且因为场景光照是固定不变的（下面 5.4 会讲为什么锁定为固定光照），没必要用实时反射。
- **解决**：Global Reflection Probe 的 Type 从 Realtime 改为 **Baked**，跟 Lightmap 一起烘焙，运行时开销从"每次实时渲染 6 面 cubemap"降为"读一张静态贴图"，对 iPad 非常友好。

### 5.3 Environment Reflections Source 遗留问题
- **现象**：Lighting → Environment 面板里 `Environment Reflections → Source` 停留在旧的 "Custom"，Cubemap 显示 Missing，导致烘焙出的环境反射是空/错误的（曾一度被误判为蕨类死黑的原因，后证明关系不大，见 5.4）。
- **解决**：改回 **Skybox**，与 Enviro 生成的 Skybox Material 配套。

### 5.4 场景确定为"固定光照"而非动态昼夜循环
- 项目定位是固定氛围效果（非动态昼夜玩法），因此：Enviro Time 模块的 **Simulate 关闭**，太阳角度手动调定；Sun Source（Lighting → Environment）从遗留的 `sunlight` 改指向 Enviro 生成的 `Sun/Moon Directional Light`；该灯的 **Light Mode 从 Realtime 改为 Mixed**（配合 Baked Indirect 的 Lighting Mode，间接光走 lightmap，直射光保持实时）。
- **注意**：固定光照后 Reflection Probe、Lightmap 都要重新烘焙才能对上新的太阳角度。

### 5.5 蕨类（Fern）阴影区域死黑 —— 最终定位：APV 探针设置切换后需要"新的一次" Generate Lighting
这是排查过程最长、也最容易误判的一个问题，记录详细一点：

- **现象**：场景里植被大量共用同一个 Shader（`FoliageInteractive.shader`），但唯独蕨类（Fern_Medium1/2）在阴影里呈现完全的死黑，边界很硬，其他植被表现正常。
- **排查中依次被推翻的假设**（重要：全部记录下来，避免以后重复踩同样的坑）：
  1. ~~Lightmap UV2 自动展开在复杂重叠几何体上产生坏 UV~~——被推翻，因为该 Shader 压根不读取 Lightmap（`FoliageInteractive.shader` 里有注释明确说明"刻意不支持光照贴图与 APV 探针体积"）。
  2. ~~Mesh Renderer 的 Contribute GI / Receive GI 模式不一致~~——**这个是真实存在的配置问题**（蕨类当时是 Lightmap Static，与其他已经是 Blend Probes 的植被不一致），但改完这一项后，问题在当时的那次烘焙里**依然没有消失**，说明还差一步。
  3. ~~Shader 里顶点阶段采样环境光（`SampleSHVertex`）没有做背面法线翻转，导致背面叶片采样到错误方向~~——技术上这个不一致真实存在，但后来换了完全不同的材质/纹理（Eagle Fern）问题依旧，**证明不是 Shader 或纹理的问题**。
  4. ~~模型法线导入方式（`normalImportMode: Import` 应改为 `Calculate`）~~——改了 Contribute GI 设置后没有立刻生效，一度怀疑是模型法线数据本身错误，**但最终什么都没改模型，只是重新点了一次 Generate Lighting 后问题就消失了**，证明这个假设也不是根因。
- **最终结论**：Generate Lighting 是把 **Lightmap 和 Adaptive Probe Volume 数据绑在一起、一次性重新计算**的。问题的真正根因是：改了 Contribute GI / Receive GI（Blend Probes）设置**之后**，没有立刻做一次新的 Generate Lighting——在设置改变之前烤出的 APV 数据，根本没有把这块区域当作"需要探针覆盖"的区域来计算。**只要设置改对了 + 紧接着做一次干净的 Generate Lighting，两者缺一不可，此外不需要动模型、纹理或 Shader。**
- **通用经验**：遇到"改了 GI/探针相关设置但没看到效果"，第一反应应该是"是不是还没有在新设置下重新烤过"，而不是急着往 Shader/模型层面深挖。

---

## 六、渲染队列 vs Enviro 屏幕空间雾 —— 反复出现的一类问题

这是接入 Enviro 之后遇到次数最多、模式最统一的一类问题，值得单独总结成"排查套路"。

### 根本机制
Enviro 的雾效果是通过 URP Renderer Feature 实现的**屏幕空间后处理特效**，注入时机是：

```csharp
renderPassEvent = RenderPassEvent.BeforeRenderingTransparents - 1;
```

即：在所有 **Opaque / AlphaTest 队列（Queue ≤ 2500）**物体画完之后、**Transparent 队列（Queue ≥ 2501）**物体开始画之前，整体画一次雾。**任何排在 Transparent 队列的物体，都画在这层雾特效之后，天然吃不到雾**，表现为：暗部/边缘像"浮在雾气上面"的一块，跟周围环境格格不入。

### 遇到过的具体案例
| 场景 | 材质/Shader | 队列 | 处理方式 |
|---|---|---|---|
| 远处 LOD2 的植被卡片（半透明 billboard） | 各类 `Yapp_*` 系列植被 LOD2 | Transparent | 改成 AlphaTest（镂空裁剪），因为边缘本来就适合硬裁剪，代价小 |
| MicroSplat 物体融入地形的叠加层 | `MicroSplat 2_TerrainObjectBlend.shader` | Transparent+100 | 改 Queue 为 `AlphaTest+50`（因为这层是 ZWrite Off 的颜色叠加，不依赖深度排序，可以放心提前），**但注意 MicroSplat 重新 Generate 时会覆盖这个改动**，见下方"自动化补丁"一节 |
| 瀑布/河流/湖面（River Auto Material 3, RAM） | `Water River Offset.shader` / `Water River Mobile.shader` / `Water Sea Offset.shader` | Transparent (3000~3002，材质级硬编码 `m_CustomRenderQueue`) | **不能简单改队列**——RAM 是真半透明+ZWrite On 的水体，强行改队列曾导致瀑布整个渲染消失。最终改用"让 Shader 自己算雾"的方案，见下一节 |

### 判断标准（以后遇到"某个物体不吃雾"时的排查顺序）
1. 先查这个物体材质的 Shader 里 `Tags { "Queue" = ... }`，以及材质本身有没有 `m_CustomRenderQueue` 覆盖（材质里写死的数值优先级高于 Shader 默认值）。
2. 如果队列 ≥ 2501（Transparent），基本可以确定是这个原因。
3. **先判断这个透明物体是"贴在不透明表面上的叠加层"（ZWrite Off，比如 MicroSplat blend）还是"真正的半透明几何体"（ZWrite On/Off 都可能，比如水面、玻璃）**：
   - 前者：改队列到 2500 以下（比如 `AlphaTest+50`）通常安全。
   - 后者：**不要轻易改队列**，有真实渲染出错（整体消失、深度排序错乱）的风险，改用"让 Shader 自己接入 Enviro 雾函数"的方案（见下节）。

---

## 七、让第三方 Shader 自己接入 Enviro 雾（RAM 水体系列的最终方案）

这是本次接入过程中工作量最大、也最有参考价值的一次修改，详细记录方法论，方便以后同类第三方 Shader 遇到同样问题时复用。

### 思路
不去改变渲染顺序，而是**让 Shader 自己在计算最终颜色时，主动读取 Enviro 的雾参数、调用 Enviro 自己的雾计算函数**，这样不管这个物体排在哪个队列，都能计算出正确的雾，且保证跟场景里其他物体使用的是同一套参数/算法，视觉上完全一致。

### 关键技术点
1. **Enviro 暴露的可复用函数**：`Assets/Enviro 3 - Sky and Weather/Resources/Shader/Includes/FogIncludeHLSL.hlsl` 里有现成的：
   ```hlsl
   float3 ApplyFogAndVolumetricLights(float3 sceneColor, float2 uv, float3 wPos, float linearDepth)
   ```
   直接调用即可，不需要自己重新实现雾的数学公式。

2. **不能直接修改 Unity 官方共享文件**：RAM 的 Shader（Shader Graph 生成）最终颜色输出、调用 `MixFog()` 的代码，在 Unity 官方包的共享文件 `Packages/com.unity.render-pipelines.universal/Editor/ShaderGraph/Includes/PBRForwardPass.hlsl` 里，这个文件被大量 Shader Graph 生成的 Shader 共用，**不能直接修改**。

3. **用宏在 `#include` 之前"偷梁换柱"**：利用 C 预处理器的文本替换特性，在 `#include PBRForwardPass.hlsl` **之前**用 `#define` 把 `MixFog` 这个函数名替换成一个参数适配好的宏，指向 Enviro 的 `ApplyFogAndVolumetricLights`；`#include` 展开后，共享文件内部对 `MixFog(...)` 的调用就会被替换成我们要的逻辑；**在 `#include` 之后必须立刻 `#undef MixFog`**，否则会污染同一个 Shader 文件里后续的其他 Pass（ShadowCaster、DepthOnly 等）。

4. **变量来源要用真实值，不要凭空造**：
   - UV 用 `inputData.normalizedScreenSpaceUV`（Unity 官方已经用 `GetNormalizedScreenSpaceUV()` 算好，比自己手动除 `_ScaledScreenParams` 更稳，能正确处理 Render Scale/动态分辨率）。
   - 深度用 `Linear01Depth(unpacked.positionCS.z, _ZBufferParams)`，注意用的是 `unpacked.positionCS`（来自 `Varyings`），**不要用** `inputData.positionCS`——后者只有在 `DEBUG_DISPLAY` 宏定义时才会被赋值，正常构建下是空的。
   - `ApplyFogAndVolumetricLights` 的 `linearDepth` 参数内部用 `saturate()` 处理，说明它要的是 **Linear01Depth（0-1 归一化）**，不是 LinearEyeDepth（实际米数），传错会导致雾效果整体错乱。

5. **【最容易漏掉、也是这次真正踩坑的一步】`#include` 必须换成 `#include_with_pragmas`**：
   `FogIncludeHLSL.hlsl` 内部包含：
   ```hlsl
   #pragma multi_compile __ ENVIRO_SIMPLEFOG
   #pragma multi_compile __ ENVIRO_VOLUMELIGHT
   ```
   这两个 pragma 决定了要编译出 Simple/Normal 两层雾、要不要带体积光这几种 shader variant。**Unity 的 ShaderLab 在解析 `#pragma` 时，只会扫描顶层 HLSLPROGRAM 块以及通过 `#include_with_pragmas` 引入的文件，普通 `#include` 引入的文件里的 `#pragma` 不会被识别、不会参与 variant 编译。** 第一次用普通 `#include` 时，函数确实能正常调用、编译也不报错，**但 Enviro 面板里 Fog Quality Mode 切换 Simple/Normal、或者切换体积光，这个 Shader 都不会跟着联动**，导致水体和周围环境即使读的是同一份 Density 数值，算出来的雾也对不上——这正是"改完雾变淡了一点但融不进背景"这个现象的真正原因。
   把普通 `#include` 换成 `#include_with_pragmas` 之后，问题彻底解决。

### 最终代码模板（三个 RAM Shader 文件通用，已应用）
```hlsl
// === Enviro Fog Integration (manually added, toggle via material) ===
#if defined(_ENVIRO_FOG_ON)
    #include_with_pragmas "Assets/Enviro 3 - Sky and Weather/Resources/Shader/Includes/FogIncludeHLSL.hlsl"
    #define MixFog(color, unityFogFactor) \
        ApplyFogAndVolumetricLights(color, inputData.normalizedScreenSpaceUV, inputData.positionWS, Linear01Depth(unpacked.positionCS.z, _ZBufferParams))
#endif
// === End Enviro Fog Integration ===

#include "Packages/com.unity.render-pipelines.universal/Editor/ShaderGraph/Includes/PBRForwardPass.hlsl"
#if defined(_ENVIRO_FOG_ON)
    #undef MixFog
#endif
```

同时在 Properties 块最前面加了一个材质开关：
```hlsl
[Toggle(_ENVIRO_FOG_ON)] _UseEnviroFog("Use Enviro Fog (off = default Unity Fog)", Float) = 1
```
并在 Forward Pass 的 Pragmas 区加：
```hlsl
#pragma shader_feature_local_fragment _ENVIRO_FOG_ON
```
这样每个用到这几个 Shader 的材质球，都能在 Inspector 里通过一个勾选框，在"Enviro 自定义雾"和"退回 Unity 最原始的内置雾"之间切换，不需要再改代码、不需要重新经历这次排查。**开关默认是"开"（用 Enviro Fog）。**

### 已应用的文件清单
- `Assets/ThirdParty_Plugins/NatureManufacture Assets/Water Shaders/Water River Offset.shader`（对应材质如 `M_R3_River_Big_Offset.mat`，瀑布用）
- `Assets/ThirdParty_Plugins/NatureManufacture Assets/Water Shaders/Water River Mobile.shader`（对应材质如 `M_R3_River_Big_Mobile.mat`）
- `Assets/ThirdParty_Plugins/NatureManufacture Assets/Water Shaders/Water Sea Offset.shader`（对应材质如 `M_R3_Sea_Lake_Mirror_Offset.mat`）

每个文件同目录下都留了修改前的备份（`.bak_before_enviro_fog` / `.bak_before_toggle` 等后缀），如需完全回退可以直接用备份覆盖。

### 如果以后 RAM 或类似第三方水体/植被 Shader 又出现同样问题
1. 先确认是不是队列 ≥ 2501 导致的（见第六节判断标准）。
2. 如果是真半透明几何体（不能简单改队列），按本节模板接入 `ApplyFogAndVolumetricLights`。
3. **务必用 `#include_with_pragmas`，不要用普通 `#include`**，否则 Enviro 的雾质量模式切换不会联动。
4. 记得给材质加一个可以随时切回原生 Unity Fog 的开关，避免"改坏了回不去"的顾虑。

---

## 八、Weather 模块相关：什么时候需要、什么时候不需要

### 8.1 面板参数变灰、"由 weather/quality 模块控制"提示
- **原理**：Enviro 编辑器代码里有两个独立的判断（`EnviroBaseInspector.RenderDisableInputBox`）：只要 `Weather` 模块**存在**（不需要有激活的天气预设），Fog/Sky 等模块面板的对应字段就会被锁定为只读；`Quality` 模块同理，是完全独立的第二把锁。**两把锁都要解除（把对应模块整个 X 掉，不是仅仅取消勾选/不激活预设），字段才会变回可编辑。**
- 仅仅"没有点 Set Active 任何天气预设"不代表内部 `targetWeatherType` 一定是空的，不能只看 UI 有没有高亮就判断。

### 8.2 什么时候不需要 Weather 模块
如果只是想要一个**固定的**雾 + 固定的 2D 云（不需要天气随时间/剧情变化），**完全不需要添加 Weather 模块**，直接单独添加 **Fog** 模块和 **Flat Clouds** 模块即可，参数直接在各自面板里改、立即生效，逻辑更简单，也省掉 Weather 模块本身的运行时开销（每帧的天气混合/切换判断）。

### 8.3 Cloudy 系列预设默认可能启用了 Volumetric Clouds（体积云，开销大）
如果确实需要用 Weather 模块做天气切换，注意预设（如 `Cloudy 1.asset`）里 `coverage`/`density` 字段对应的是 Volumetric Clouds（raymarching，iPad 上较贵），建议把这两个值调到 0，只保留 `flatCloudsCoverage`（2D 云，便宜），一样能有云的观感。

---

## 九、给 MicroSplat 做的配套自动化脚本

因为 MicroSplat 的 Terrain Object Blend Shader（`MicroSplat_TerrainObjectBlend.shader` / `MicroSplat 2_TerrainObjectBlend.shader`）每次被 MicroSplat 工具重新 Generate 时，队列会被重置回 `Transparent+100`（见第六节），写了一个自动巡查脚本：

`Assets/_Project/Editor/MicroSplatFogQueueFix.cs`

- 通过 `AssetPostprocessor.OnPostprocessAllAssets` 监听资源导入，只要检测到文件名包含 `TerrainObjectBlend` 的 `.shader` 文件被（重新）导入，自动把队列改回 `AlphaTest+50`。
- 同时提供菜单 `Window → MicroSplat → Fix Terrain Blend Fog Queue (Scan All)`，用于手动全项目扫一遍（比如这个脚本是后来才加入项目、需要补扫历史生成的文件时用）。

---

## 十、遗留 / 后续需要留意的点

1. `Assets/Editor/EnviroURPFix.cs`、`Assets/_Project/Editor/MicroSplatFogQueueFix.cs` 这两个自动化脚本**要跟着项目一起提交到版本控制**，换电脑/新拉项目代码时一起带过去，否则相关 bug 会复现。
2. 三个 RAM 水体 Shader 文件的改动，**如果以后升级 RAM 插件版本、Shader 文件被官方新版本覆盖，这次的手动改动会丢失，需要重新执行第七节的接入步骤**（备份文件里保留了改动前的原始版本，可以用 diff 工具对比新版官方文件改了哪些地方，加快重新接入的速度）。
3. Enviro 官方面板本身有一个 "MicroSplat Integration" 组件（Third Party Support → MicroSplat），当时已经勾选启用，但**没有细查过它具体处理了哪些兼容性问题**，不排除跟本记录第六节里手动改 MicroSplat 队列的做法有重复，以后有空可以验证一下是否可以互相替代。
4. 蕨类等植被的自定义 Shader（`FoliageInteractive.shader`）**刻意不支持 Lightmap 也不支持 APV 体积采样**，只用最基础的单点 SH 环境光插值——这是项目自己写的 Shader 的既有设计限制，不是这次 Enviro 接入引入的问题，但会影响大体积、跨越较大空间的单个物体的光照均匀度，需要时可以考虑升级为真正的 APV 体积采样。
