using UnityEngine;
using UnityEngine.InputSystem;

/// <summary>
/// ============================================================================
/// TapMoveCamera_V2 —— 屏幕端虚拟自然干预平台 · 相机导航与点击语义判定
///                     【iPad 迁移版】
/// ============================================================================
///
/// 【V2 是什么，不是什么 —— 2026-08-07】
///
/// V2 = V1 + 设备适配。**判定逻辑一行未动。**
/// ClassifyHit / SampleWalkablePath / SampleGround / IsBlockedAt / 移动与转向，
/// 全部与 V1 逐字相同。V1 的所有注释原样保留，包括那些"不要加回去"的告诫。
///
/// 之所以要有 V2，是因为交互评估越往后走，越绕不开设备特征——手感判断在 27 寸
/// 桌面屏上做出来的结论，换到手持 iPad 上不一定还成立。而在把交互搬过去之前，
/// 有三个量是**用像素定义的**，换设备就换含义，不改就没法测。
///
/// 【本版本改了什么】
///
///   (1) 三个像素量改为物理量（毫米 / 厘米）
///       dragThreshold      12 px  → dragThresholdMM        (毫米)
///       lookSensitivity    0.12   → lookSensitivityDegPerCm (度/厘米手指位移)
///       debugFontSize      22 px  → 仍是 22，但按 DPI 自动缩放
///
///       其中 dragThreshold 这条最要紧，而且影响的是**点击不是拖动**：
///       12 px 在 264 ppi 的 iPad 上约 1.15 mm，而手指按下时接触面本来就会滚
///       动一两毫米。后果是点击被大量误判成拖动——人不走，画面反而微微转一下。
///       参数注释里早就写了这个失效模式（"太小会把手指的轻微滚动误判成拖动"），
///       只是在鼠标上永远不会发生。不先改这一条就上机，第一次测试的结论会是
///       "点击在 iPad 上不好用"，而那是个假结论。
///
///   (2) 设备参数在 Start 中显式设定（不暴露在 Inspector）
///       目标帧率、屏幕常亮、横屏锁定。理由见 ConfigureDevice()。
///
///   (3) DPI / 帧率 / 分辨率进调试框
///       DPI 是本版本新的"一错全错"的单点：它解析错了，上面两个物理量会同时
///       静默偏掉，而外在表现是"点击不好用""拖动太灵敏"——跟参数没调好长得
///       一模一样。按 V1 那条教训（"凡是一关就全盘失效的开关，其状态必须显示
///       在调试框里"），它必须可见。
///
///   (4) 调试框高度改为按实际行数算，并避开 safeArea
///       V1 已经因为写死行高吃过一次亏（截掉的恰好是路径采样开关）。本版本加了
///       三行，若沿用写死的 11 行会再犯一次同样的错。
///
/// 【本版本刻意没做的事】
///
///   - 没有改任何手感参数的**取值**。lookSensitivity 换了单位但不折算旧值，
///     因为旧值从来没测过（方案B 六：「都还是旧值，没有一个是测过的」），
///     折算一个没有依据的数只会制造"它是有来历的"这种错觉。它要在设备上从头定。
///   - 没有改 FOV。但须记明一条：Unity 的 fieldOfView 是**垂直**视角，桌面 16:9
///     换到 iPad 4:3 时，同一个数字给出的**水平**视角更窄。这不是 bug，但它会
///     让"iPad 上看起来不一样"多一个你没打算引入的原因。要不要补偿，属手感判断，
///     留到设备上定。
///   - 没有做任何在设备上调参的手段。这是个已知缺口，见文件末尾的说明。
///
/// 【类名为什么还是 TapMoveCamera】
///
///   故意不改。类名一变就是另一个组件，场景里序列化的那些已经调到"比较舒服"的
///   值（viewingDistance、walkKeepDistance 等）会全部回默认。
///   代价：**V1 与 V2 不能同时放在 Unity 的 Assets 里**（同名类会编译冲突）。
///   归档文件夹里放两份没问题，进工程时只能留一份。
///   另注：dragThreshold / lookSensitivity 这两个字段被改名了，它们序列化的旧值
///   会丢——这正是本版本要重定的两个数，丢了是对的。
///
/// ----------------------------------------------------------------------------
/// 以下为 V1 原文，除标注 "【V2】" 处外未作改动。
/// ----------------------------------------------------------------------------
///
/// 【修订记录 —— 请后来者先读这一段，这里全是踩过的坑】
///
/// V1 首测（2026-08-06）发现四件事，均已在本版本修正。之所以逐条记下来，是因为
/// 其中几条从代码上看都"很有道理"，不写清楚就会被重新加回去：
///
///   (1) 终点判定里用"命中点与脚下的绝对高差"来判能不能去 —— **删除**
///       这是首测中"点什么都变成我想看""卡在河沟里进退维谷"的主因。
///       错在：你和一个远处的点之间的高差，跟能不能走过去毫无关系。
///       一道 20 米长的缓坡可以升高 5 米，一路都好走，但高差是 5 米。
///       详见 ClassifyHit(d) 处的长注释。不要再加回来。
///
///   (2) 路径采样用 maxWalkableSlope 判每个采样点 —— **改为独立的 pathMaxSlope**
///       微地形到处是局部超阈值的小坑小坎，一个采样点踩中就整条路判死。
///       现在区分"能不能路过"(pathMaxSlope) 和"能不能停下"(maxWalkableSlope)，
///       这是两件不同的事，现实里也是。
///
///   (3) 路径采样的向下射线没查阻挡层 —— **已加**
///       射线穿过深水板打到河床，判定"一路通畅"，人就走进水里了。
///       首测现象：第一次点水停在岸边，再点一次就进去了。
///
///   (4) 转向用匀速角速度 —— **改为 SmoothDamp + 死区**
///       匀速转向一按下就全速起转，实测像"猛地一扭头"。
///       问题在曲线不在速度，把速度调慢也不对味。
///
/// 同时按实测反馈新增 walkKeepDistance：WalkTo 也留一段距离，不再走到点上。
/// 见该参数注释——它同时解决"近处点击挪那么碎的一小步"和"走到跟前目标掉出屏幕"。
///
/// 场景侧已知状态：倒木（DeadWood 层）的 prefab 没有碰撞体，因此目前既点不中
/// 也不挡路，该层暂时是空转的。要不要给它加碰撞体，留待后续测试再定。
///
/// 【本脚本在整个项目中的位置】
///
/// 本项目检验的是：屏幕端的轻量交互，能否在不增加认知负荷的前提下，把注意留在
/// 自然环境上。因此本脚本的一切设计取舍，判据只有一条：
///
///     这项改动是让被试更注意环境，还是更注意交互本身？后者一律不做。
///
/// 具体到导航层，这意味着：被试只表达"我对那边有兴趣"，系统负责把它翻译成
/// 走过去 / 转过去看。被试永远不需要先决定"我现在要走还是要看"。
///
///
/// 【输入只有两个手势，不会再增加】
///
///   点击 = 兴趣指向。系统据此判定语义并移动。
///   拖动 = 环顾。原地转头。
///
/// 这两个手势的表达力是有硬边界的（点击能说"哪一个"说不出"多少"；拖动能说
/// "多少"说不出"哪一个"；一根手指一次只能做一件事）。因此"后退""原地停下且
/// 不改变视角""指定距离/速度"这类意图**在本方案下表达不出来**，这不是待修的
/// 缺陷，是输入通道的容量上限。后来者若想加手势解决，请先确认它值得付一条
/// "被试必须学会的规则"的代价——练习环节只能讲操作说明，多一条就多一条负担。
///
///
/// 【点击的两种语义，以及为什么这样判】
///
///   走过去  → 终点就是被点中的那个位置
///   我想看  → 终点与被点中的位置保持 viewingDistance
///
/// 关键：**判据是"那儿能不能站人"，不是距离。**
///
/// 曾考虑过按距离插值（远=走 / 近=看），已否决。理由：远处两种意图根本分不出来
/// 但也无需分（该做的事一样）；近处意图能分了，可"走过去"这个选项已经自动失效
/// （人已经站在它旁边了）。所以距离在任何一段都不需要做判定。真正决定分岔的，
/// 从头到尾只有"那儿能不能站人"——而这是**可以查世界得到的事实，不是对被试
/// 心理的猜测**。这是本判定安全性的全部来源。
///
///
/// 【一条必须守住的硬约束：这套判定没有纠错机制，只有容错余量】
///
/// "判错了可以靠再点一次修正"是错的：对不可通行的对象，站近之后可通行性不变，
/// 第二次点击的判定结果与第一次相同。所以安全性完全取决于两个落点隔多远。
///
///   → 隔一两米，判错只是站得远近有别，被试大概率察觉不到。
///   → 隔到"贴脸"对"两米外"，判错就是一个明显且**不可挽回**的错误结果
///     （脸贴树皮，而"后退"表达不出来）。
///
/// 因此：**任何情况下都不要让相机走到贴脸距离。**若后续有人想把 viewingDistance
/// 调到很小、或想让 WalkTo 直接怼到对象表面，请先想清楚这一条。
///
///
/// 【另一条：可通行性判错了不可恢复，所以要往"能走"的方向偏】
///
///   把能走判成不能走 → 被试永远过不去，且他没有别的方式表达"我就是要过去"。无解。
///   把不能走判成能走 → 最坏是站得有点近 / 位置有点怪。可接受。
///
/// 所以 maxWalkableSlope 这类阈值宁可放宽，不要收紧。
///
///
/// 【本版本已知不做的事（不是 bug，不要当 bug 修）】
///
///   - 树没有碰撞体 → 点树等于点树后面的地形，会穿过去。触碰模块回来时一起解决。
///   - 蕨类灌木没有碰撞体 → 射线穿过去打到地形。这是**故意**的：给它们加碰撞体会
///     大量拦截射线，被试将无法点中蕨丛后面的东西，而近景蕨类在本场景极密。
///     代价是以后也摸不到它们，届时需要"能被点中但不挡路"的碰撞体方案。
///   - 没有横向碰撞。相机直接改 transform.position，没有 CharacterController /
///     Rigidbody。所以物理上什么都挡不住它，**目前唯一的阻挡机制就是"点不着"**。
///   - 山谷南北两端未封堵，可以走出活动区域。
///   - 触碰完全不做，代码中也不留接口（做一半在长周期项目里是净负债）。
///
///
/// 【场景侧的依赖（改场景的人必须知道）】
///
///   Layer 8  Terrain     地形本身
///   Layer 9  Rock        石头（独立 GameObject，资产自带碰撞体）
///   Layer 10 DeadWood    倒木、枯枝（同上）
///   Layer 11 WaterBlock  深水区的不可见阻挡板（Mesh Collider，关掉 Renderer）
///   Layer 12 Foliage     蕨/灌木/草。本版本不使用，预留。
///
///   Terrain / Rock / DeadWood = 可站立表面，被试可以踩上去。
///   WaterBlock = 永远不可通行，无论坡度如何。
///
///   ※ 世界原点与地形整体缩放一经定下不得再改——将来的行为日志记的是世界坐标。
///
/// ============================================================================
/// </summary>
public class TapMoveCamera_V2 : MonoBehaviour
{
    // ========================================================================
    // 点击语义的枚举
    // ========================================================================

    public enum TapIntent
    {
        None,       // 射线没打中任何东西（点了天空 / 超出射程）
        WalkTo,     // 那儿能站人 → 走过去，终点就是那个点
        LookAt      // 那儿站不了人 → 停在 viewingDistance 处看它
    }


    // ========================================================================
    // 参数区
    // ========================================================================

    [Header("── 视点与身体 ──────────────────")]

    [Tooltip("眼睛离地高度。1.7m 是站立成人的视高。\n" +
             "曾经是 2.5m，那会把场景压成『俯视一片景』而不是『站在里面』。不要再调高。")]
    public float eyeHeight = 1.7f;

    [Tooltip("相机高度跟随地面的平滑速度。太小会飘，太大会在碎石地上抖。")]
    public float heightSmoothSpeed = 8f;


    [Header("── 移动 ────────────────────────")]

    [Tooltip("行走速度 (m/s)。人正常步行约 1.2~1.4，慢走约 0.8。")]
    public float moveSpeed = 1.2f;

    [Tooltip("起步加速度。越小起步越绵软。")]
    public float acceleration = 2.0f;

    [Tooltip("刹车减速度。用于到站前的自然减速，不要设太大（会变成急停，像机器）。")]
    public float deceleration = 3.5f;

    [Tooltip("到达判定阈值。离终点小于这个距离就算到了。")]
    public float arriveThreshold = 0.2f;

    [Tooltip("身体转向的大致耗时 (秒)。转向用缓入缓出，不是匀速。\n" +
             "※ 【V1 实测后改】原本是匀速角速度 (120°/秒)，一按下就以全速起转，\n" +
             "  实测像『猛地一扭头』。人转头是有加速和收尾的，匀速无论调多慢都不对味——\n" +
             "  问题在曲线不在速度。现在改成 SmoothDamp。\n" +
             "※ 0.25~0.5 比较像人。太大会觉得迟钝，太小又回到猛扭。")]
    public float turnSmoothTime = 0.35f;

    [Tooltip("转向角速度上限 (度/秒)，防止大角度转向时中段甩得太快。")]
    public float maxTurnSpeed = 180f;

    [Tooltip("转向死区 (度)。点击方向与当前朝向夹角小于这个值就不转。\n" +
             "※ 【V1 实测后加入】没有死区时，哪怕点屏幕正中偏一点点，画面都要挪一下。\n" +
             "  这种持续的小抽动本身就是一种『我在操作一个装置』的提示。")]
    public float turnDeadZoneAngle = 6f;

    [Tooltip("先转身再迈步的角度阈值。目标方向与当前朝向夹角超过这个值时，\n" +
             "先原地转到大致朝向再起步——人就是这么走路的，不会横着平移出去。\n" +
             "设成 180 等于关闭该行为。")]
    public float turnBeforeMoveAngle = 60f;


    [Header("── 我想看：停在多远 ─────────────")]

    [Tooltip("判为 LookAt 时，与被点中位置保持的距离 (m)。\n" +
             "※ 这个距离是相对**命中点**算的，不是相对『对象』算的。这一点很重要：\n" +
             "  按对象尺度算，就得先知道『目标对象是谁』，而一丛灌木的碰撞体是整株，\n" +
             "  点顶部的花和点中部的枝会命中同一个对象、算出同一个距离——等于系统\n" +
             "  替被试决定了他看的是整丛还是那朵花。按命中点算，手指指哪儿就停在哪儿前面。\n" +
             "※ 这是本版本最需要上手反复调的一个数，很可能要改好几次。")]
    public float viewingDistance = 2.5f;

    [Tooltip("判为 WalkTo 时，与被点中位置保持的距离 (m)。\n" +
             "※ 【V1 实测后加入】原本 WalkTo 是走到点上（=0）。实测发现两个问题：\n" +
             "  (1) 点脚边一小步远的地方，人会挪那么一小下，很碎、很像在操作装置；\n" +
             "  (2) 走到点上之后，那个点就在脚底下——而俯角有上限，脚下 1m 内的地面\n" +
             "      根本进不了画面。被试为了看清一样东西走过去，结果它掉出了屏幕。\n" +
             "  留出一小段距离，等于把注意力留在画面里。\n" +
             "※ 几何上有个下限：能看见的最近地面 = eyeHeight / tan(maxPitchAngle)。\n" +
             "  当前参数下约 1.0m。设得比这个还小就白留了。调试框里有实时读数。\n" +
             "※ 设为 0 = 完全不考虑距离，退回旧行为。")]
    public float walkKeepDistance = 1.0f;

    [Tooltip("判为 LookAt 且已经在观看距离之内时，是否仍然转身朝向目标。\n" +
             "建议保持 true：否则这一击将『什么都不发生』，被试会以为没点中。\n" +
             "转身是一个廉价但真实的响应——『我看向那边了』。")]
    public bool lookAtAlwaysTurnsBody = true;


    [Header("── 可通行性判定 ────────────────")]

    [Tooltip("可站立的最大坡度 (度)。超过这个角度的表面判为站不住 → LookAt。\n" +
             "※ 本场景中，上山小路与两侧挡人的陡坡是同一种地形、同一种材质，\n" +
             "  **唯一能把它们分开的就是这个数**。定高了路上不去，定低了坡挡不住。\n" +
             "※ 这个阈值是逐点判断的，不是判断『整道坡』。所以同一道坡从下往上会在\n" +
             "  某处越过阈值：坡脚可点、坡身不可点。人不是被拦在坡下，是越往上越点不着。\n" +
             "  上山路走到头的死路平台也由此自然成立——四周点上去都停住，无需空气墙。\n" +
             "※ 拿不准就往大了调（见文件头：判错方向的代价不对称）。")]
    [Range(10f, 80f)]
    public float maxWalkableSlope = 35f;

    [Tooltip("一步能跨上去的最大高差 (m)。超过就判为爬不上去 → LookAt。\n" +
             "真人一步大约能跨 0.5~0.6m，这里可以稍微给宽一点。\n" +
             "※ 这个值同时也是地面探测射线的起点高度（见 SampleGround），\n" +
             "  两者本来就是同一件事：射线起点抬多高，人就能踩上多高的东西。")]
    public float maxStepUpHeight = 0.7f;

    [Tooltip("敢往下走的最大落差 (m)。超过就判为跳不下去 → LookAt。\n" +
             "本场景是山谷地形，站在坡顶点谷底是高频情况，这个数决定那种点击的结果。")]
    public float maxStepDownHeight = 1.2f;


    [Header("── 路径采样（穷人版寻路）────────")]

    [Tooltip("是否沿路线逐点检查能不能走过去。\n" +
             "关掉的话只判断终点、不判断路上——被试点对岸会直接飘过沟去。\n" +
             "※ 这不是 NavMesh。它只是沿直线每隔一小段向下打一条射线，看高差是否\n" +
             "  超过跨越/下落能力。代价是每次点击几十条射线（一次性，不是每帧），\n" +
             "  在 iPad 上完全可以承受。\n" +
             "※ 它带来一个很自然的行为：点对岸 → 走到沟边停住。这正是现实中的样子。")]
    public bool usePathSampling = true;

    [Tooltip("路径采样的步长 (m)。越小越准越慢。0.4~0.6 比较合适。")]
    public float pathSampleStep = 0.5f;

    [Tooltip("路上允许经过的最大坡度 (度)。**必须明显大于 maxWalkableSlope。**\n" +
             "※ 【V1 实测后加入】原本路径采样直接用 maxWalkableSlope 判每个采样点，\n" +
             "  结果被试在小河沟里、在上山小路上会被卡死——因为微地形到处都有\n" +
             "  局部超过 35° 的小坑小坎，一个采样点踩中就整条路判死。\n" +
             "※ 概念上这两个数管的是两件不同的事：\n" +
             "    maxWalkableSlope = 能不能**停在**这儿（终点判定）\n" +
             "    pathMaxSlope     = 能不能**路过**这儿（路径判定）\n" +
             "  现实里也是如此：一小段陡坡你走得过去，只是站不住。")]
    [Range(20f, 89f)]
    public float pathMaxSlope = 55f;

    [Tooltip("路径采样的最大点数，防止点了很远的地方时开销失控。")]
    public int maxPathSamples = 200;


    [Header("── 地面探测 ────────────────────")]

    [Tooltip("地面探测射线的向下探测距离 (m)。用于走下坡时找到地面。")]
    public float groundProbeDown = 6f;

    [Tooltip("阻挡层（深水板）探测射线的起点高度，相对参考地面往上抬多少。\n" +
             "※ 【V1 二测后加入】必须明显大于 groundProbeUp。\n" +
             "  原因：水板浮在**水面**高度上，而路径采样的参考高度跟着**河床**走。\n" +
             "  往深水走时河床下降，探测射线的起点也跟着降到水板底下去了，\n" +
             "  射线向下打根本碰不到水板，于是判定『一路通畅』，人就走进水里。\n" +
             "※ 阻挡层可以用高射线，因为水面之上不会再有水——不存在 groundProbeUp\n" +
             "  那种『会被岩檐/树冠误命中』的顾虑。所以这两个数不能共用。\n" +
             "※ 取值应大于场景中最深的水深。")]
    public float blockProbeUp = 5f;

    [Tooltip("【重要】地面探测射线的起点，相对当前地面高度往上抬多少。\n" +
             "※ 旧版是从头顶 50m 往下打、取第一个命中物当地面。后果是走到岩檐/悬垂\n" +
             "  地形/树冠下面时，第一个命中的是上方那个东西，人会被瞬间弹到它上面去。\n" +
             "  在这种山谷混交林场景里那不是边缘情况，是常态。\n" +
             "※ 但这个问题不能靠『只查地形层』来修——因为『能踩上石头倒木』和『被顶到\n" +
             "  岩檐上』是同一个机制。只查地形层的话，石头倒木也踩不上去了。\n" +
             "  正确的修法是把射线起点降到眼前这一小段范围内：脚下的石头够得着，\n" +
             "  头顶的岩檐够不着。\n" +
             "※ 默认取 maxStepUpHeight 是有道理的，见该参数说明。改之前请想清楚。")]
    public float groundProbeUp = 0.7f;


    [Header("── 射线与层遮罩 ────────────────")]

    [Tooltip("点击射线的最大距离 (m)。场景是一公顷，200m 足够覆盖。")]
    public float tapRayDistance = 200f;

    [Tooltip("点击射线会命中哪些层。留空则自动填入 Terrain|Rock|DeadWood|WaterBlock。")]
    public LayerMask tapRayMask;

    [Tooltip("哪些层算『可以站上去的表面』。留空则自动填入 Terrain|Rock|DeadWood。\n" +
             "※ WaterBlock 不在此列——它就是用来表示『这儿过不去』的。")]
    public LayerMask walkableMask;

    [Tooltip("哪些层是『绝对不可通行』，无论坡度如何。留空则自动填入 WaterBlock。")]
    public LayerMask blockingMask;


    [Header("── 环顾（拖动）─────────────────")]

    [Tooltip("拖动灵敏度：手指在屏幕上划过 1 厘米，视角转多少度。\n" +
             "※ 【V2 改】原本是『每像素转多少度』(0.12)。像素定义的灵敏度跨设备无意义：\n" +
             "  同样的 0.12，在 100 ppi 的桌面屏上是 4.7 度/厘米，在 264 ppi 的 iPad 上\n" +
             "  是 12.4 度/厘米，在 326 ppi 的 8K 屏上是 15.4 度/厘米——三种完全不同的手感。\n" +
             "※ 换成度/厘米之后它才是个能说清楚、也能写进论文方法部分的数。报告\n" +
             "  『0.12 度每像素』等于没报告，别人无法在别的设备上复现。\n" +
             "※ 【这个默认值没有依据，必须在 iPad 上从头定】旧值从未测过，所以这里\n" +
             "  不去折算它——折算一个没测过的数，只会让它看起来像是有来历的。\n" +
             "※ 定这个数时的一个参考算式：以当前 maxYawAngle=70°，12 度/厘米意味着\n" +
             "  手指划过约 5.8 厘米就到脖子的极限。11 寸 iPad 横屏宽约 22 厘米，\n" +
             "  即约四分之一屏宽。觉得要划太远就调大，觉得一碰就甩过头就调小。")]
    public float lookSensitivityDegPerCm = 12f;

    [Tooltip("头部左右转动极限 (度)。模拟脖子的生理限制。")]
    public float maxYawAngle = 70f;

    [Tooltip("头部俯仰极限 (度)。\n" +
             "※ 旧值 35° 太小：眼高 1.7m 时，俯角 35° 意味着眼前约 2.4m 以内的地面\n" +
             "  根本进不了画面。而『走过去』的落点判断全靠点地面——被试为了看清一样\n" +
             "  东西走近它，走近的结果却是它掉出屏幕下沿。60° 大致相当于低头看脚前 1m。")]
    public float maxPitchAngle = 60f;

    [Tooltip("接近转动极限时的阻力曲线指数。越大，越靠近极限越黏。")]
    public float lookResistancePower = 2f;

    [Tooltip("判定为『拖动』而非『点击』的位移阈值（毫米，手指实际划过的物理距离）。\n" +
             "太小会把手指的轻微滚动误判成拖动（点击失效）；\n" +
             "太大会把想微调视角的小滑动误判成点击（人莫名走出去）。\n" +
             "※ 【V2 改】原本是 12 像素。在鼠标上这个数很宽裕——指针不会自己抖；\n" +
             "  但在 264 ppi 的 iPad 上 12 像素只有 1.15 毫米，而手指按下时接触面\n" +
             "  本来就会滚动一两毫米。**指尖点击的位移几乎必然超过它。**\n" +
             "  后果是点击被大量误判成拖动：人不走，画面反而微微转一下。\n" +
             "  这条不先改就上机，第一次测试会得出『点击在 iPad 上不好用』——假结论。\n" +
             "※ 默认 3 毫米的来历：iOS 系统自身的触摸容差约 10 point（约 1.9 毫米），\n" +
             "  Android 的 touch slop 约 1.3 毫米，两者都偏小是因为它们要服务于\n" +
             "  滚动列表这类连续手势。本项目的点击是**离散寻址**，误判代价不对称——\n" +
             "  点击被吞掉（人不走）比拖动迟钝半毫米难受得多，所以取得比系统值大一些。\n" +
             "  3 毫米在 100 ppi 的桌面屏上约合 11.8 像素，与 V1 的 12 像素几乎相同，\n" +
             "  因此桌面上的行为基本不变，可以直接对照。\n" +
             "※ 这是本版本预计要在 iPad 上反复试的两个数之一（另一个是灵敏度）。\n" +
             "  调试框里有实时的像素折算值，可以对照着看。")]
    public float dragThresholdMM = 3.0f;

    [Tooltip("移动时是否把头部拉回正前方。\n" +
             "※ 现实中人可以边走边看着某处，所以 false 更像人。但注意：这里的 false 只是\n" +
             "  『保持头相对身体的偏角』，身体转向新目标时头会跟着一起转，刚才那丛灌木\n" +
             "  照样会滑出视野。真正的『绕行时视线一直挂在对象上』需要保持头的**世界**\n" +
             "  朝向（身体转多少头反向抵消多少），那是另一种实现，本版本没有做。\n" +
             "※ 本轮先保持 true（与旧版一致），以免一次改动太多个变量、测出问题分不清\n" +
             "  是谁造成的。想试就翻成 false。")]
    public bool returnHeadOnMove = true;

    [Tooltip("移动时头部回正的速度。")]
    public float headReturnSpeed = 4f;


    [Header("── 调试 ────────────────────────")]

    [Tooltip("在屏幕上显示判定过程。\n" +
             "※ 没有它，测试时分不清『射线没打中』『参数写错』『判定逻辑错』——\n" +
             "  这几种情况的外在表现都是『人没走过去』。\n" +
             "※ 正式实验前必须关闭。")]
    public bool showDebugOverlay = true;

    [Tooltip("在 Scene 视图里画出射线、命中点、终点。仅编辑器有效。")]
    public bool drawDebugGizmos = true;

    [Tooltip("调试文字大小（以约 100 ppi 的桌面屏为基准）。\n" +
             "※ 【V2 改】现在会按实际 DPI 自动缩放，不必为 iPad 单独改这个数——\n" +
             "  在 264 ppi 的 iPad 上会自动放大到约 2.6 倍，物理字号与桌面上一致。\n" +
             "  V1 的注释说『iPad 上需要放大』，V2 把这件事自动化了。\n" +
             "※ 缩放后的实际字号显示在调试框里。")]
    public int debugFontSize = 22;


    // ========================================================================
    // 运行时状态
    // ========================================================================

    private Camera cam;

    // 移动
    private Vector3 targetPosition;          // 最终落点（世界坐标，y 无意义）
    private Vector3 lastMoveDirection = Vector3.zero;
    private bool isMoving = false;
    private float currentMoveSpeed = 0f;

    // 朝向
    private float bodyYaw;                   // 身体朝向（世界）
    private float headYaw;                   // 头相对身体的左右偏角
    private float headPitch;                 // 头的俯仰
    private float desiredBodyYaw;            // 目标身体朝向
    private bool hasTurnTarget = false;      // 是否有待完成的转向
    private float turnVelocity = 0f;         // SmoothDampAngle 的内部速度，勿手改

    // 地面
    private float currentGroundY;            // 当前脚下地面高度
    private bool hasGround = false;

    // 输入
    private bool isPointerDown = false;
    private bool isDraggingLook = false;
    private Vector2 pointerDownPosition;
    private Vector2 lastPointerPosition;
    private Ray pressRay;                    // 按下那一刻的射线（见 HandleTapInput 注释）
    private bool pressRayValid = false;

    // 调试信息
    private TapIntent lastIntent = TapIntent.None;
    private string lastHitName = "-";
    private string lastHitLayer = "-";
    private float lastHitDistance = 0f;
    private float lastHitSlope = 0f;
    private float lastHeightDelta = 0f;
    private bool lastPathBlocked = false;
    private float lastRequestedDistance = 0f;
    private float lastGrantedDistance = 0f;
    private float lastKeepDistance = 0f;
    private string lastBlockReason = "-";        // 路径为什么走不下去了
    private bool blockedUnderfoot = false;       // 当前位置是否处在阻挡层范围内
    private int blockSampleCount = 0;            // 本次点击采样了几个点
    private Vector3 lastHitPoint;
    private bool hasLastHit = false;
    private GUIStyle debugStyle;


    // ── 【V2 新增】设备相关的派生量 ────────────────────────────────────────
    //
    // 这几个都不是可调参数，是从 Screen.dpi 算出来的。它们**不进 Inspector**：
    // 设备特征不是设计变量，暴露出来只会让人误以为可以调它。
    // 但它们必须**可见**，见 dpiIsFallback 的注释。

    private float screenDpi = 0f;            // 解析出来的屏幕 DPI
    private bool dpiIsFallback = false;      // 是否用了兜底值（见 ResolveDpi）
    private float pixelsPerMM = 1f;          // 每毫米多少像素
    private float dragThresholdPx = 12f;     // dragThresholdMM 折算出的像素阈值
    private float lookSensDegPerPx = 0.12f;  // lookSensitivityDegPerCm 折算出的度/像素
    private int scaledFontSize = 22;         // 按 DPI 缩放后的调试字号
    private int lastScreenWidth = 0;         // 用于检测分辨率/朝向变化
    private int lastScreenHeight = 0;

    // 帧率读数（调试用）。用平滑值，否则数字跳得看不清。
    private float smoothedFps = 0f;

    /// <summary>
    /// DPI 兜底值。仅在 Screen.dpi 返回 0 或异常时使用（某些桌面平台会返回 0）。
    /// 96 是 Windows/通用桌面的传统假定值。
    /// ※ 故意写成常量而不是 Inspector 参数：它不是给人调的，是给系统兜底的。
    ///   真要是走到了兜底分支，调试框会红字提示，那时该查的是设备而不是这个数。
    /// </summary>
    private const float FallbackDpi = 96f;

    /// <summary>
    /// 调试字号缩放的参考 DPI。debugFontSize 以这个 DPI 为基准。
    /// </summary>
    private const float DebugFontReferenceDpi = 100f;


    // ========================================================================
    // 生命周期
    // ========================================================================

    void Start()
    {
        cam = Camera.main;
        if (cam == null) cam = GetComponent<Camera>();

        AutoFillLayerMasks();

        // 【V2 新增】设备配置与单位换算，必须在读取任何输入之前完成。
        ConfigureDevice();
        ResolveDpi();
        RecomputeDeviceDerivedValues();

        targetPosition = transform.position;
        bodyYaw = transform.eulerAngles.y;
        desiredBodyYaw = bodyYaw;
        headYaw = 0f;
        headPitch = 0f;

        SnapToGroundImmediate();
        ApplyCameraRotation();
    }

    void Update()
    {
        // 【V2 新增】分辨率或朝向变了就重算换算系数。
        // 每帧比两个整数，开销可忽略；不做的话，横竖屏切换或分辨率缩放变更之后
        // 所有物理量都会静默偏掉——而那正是最难查的一类问题。
        if (Screen.width != lastScreenWidth || Screen.height != lastScreenHeight)
        {
            ResolveDpi();
            RecomputeDeviceDerivedValues();
        }

        // 帧率平滑，仅供调试框显示。
        if (Time.unscaledDeltaTime > 0.0001f)
        {
            float instant = 1f / Time.unscaledDeltaTime;
            smoothedFps = (smoothedFps <= 0f) ? instant : Mathf.Lerp(smoothedFps, instant, 0.1f);
        }

        HandleTapInput();

        // 诊断用：当前位置是否处在阻挡层（深水板）范围内。
        // 若显示"是"却仍能走进来，说明是路径采样没拦住；
        // 若显示"否"而人明明泡在水里，说明水板的水平覆盖没铺到这儿、或几块之间有缝。
        if (showDebugOverlay && hasGround)
        {
            blockedUnderfoot = IsBlockedAt(Flat(transform.position), currentGroundY);
        }

        UpdateTurning();
        UpdateMovement();
        UpdateGroundHeight();
    }

    /// <summary>
    /// 层遮罩留空时按名字自动填。这样脚本挂上去就能跑，不依赖 Inspector 手工勾选，
    /// 也避免了『忘了勾一个层导致某类对象永远打不中』这种极难排查的问题。
    /// </summary>
    private void AutoFillLayerMasks()
    {
        if (tapRayMask.value == 0)
            tapRayMask = LayerMask.GetMask("Terrain", "Rock", "DeadWood", "WaterBlock");

        if (walkableMask.value == 0)
            walkableMask = LayerMask.GetMask("Terrain", "Rock", "DeadWood");

        if (blockingMask.value == 0)
            blockingMask = LayerMask.GetMask("WaterBlock");

        if (tapRayMask.value == 0 || walkableMask.value == 0)
        {
            Debug.LogError("[TapMoveCamera] 层遮罩为空。请确认 Project Settings → Tags and Layers " +
                           "里已经建好 Terrain / Rock / DeadWood / WaterBlock 这几个 Layer，名字要完全一致。");
        }
    }


    // ========================================================================
    // 【V2 新增】设备配置与单位换算
    //
    // 这一整节都不暴露在 Inspector。理由：设备特征不是设计变量。把帧率、DPI 这类
    // 东西做成可调参数，会让后来的人（包括几个月后的自己）误以为它们是待定的、
    // 可以拿来调手感的——而它们不是，它们是前提条件。
    //
    // 但"不可调"不等于"不可见"。见 OnGUI 中的设备行。
    // ========================================================================

    /// <summary>
    /// 【V2 新增】设备侧的三条设定。都是"不显式写就会拿到一个你没打算要的默认值"。
    /// </summary>
    private void ConfigureDevice()
    {
        // ── (1) 帧率 ──────────────────────────────────────────────────
        // Unity 在 iOS 上 targetFrameRate 的默认值是 30，桌面上是不限。
        // 不显式设定，iPad 上就是 30 fps 而桌面上是 60+，两台设备的体验差里
        // 会混进一个跟设备形态无关的因素——而**帧率正是方案B 第八节列出的
        // 晕动技术变量之一**，且 30 fps 的方向恰好是加重。
        //
        // 设 60 不设 120：高刷 iPad 能跑 120，但那会让 iPad 与桌面又不可比，
        // 且移动端高刷的耗电与发热在 20 分钟的干预时长里不是小事。
        // 若将来要试 120，改这一个数即可，但两组被试必须用同一个值。
        QualitySettings.vSyncCount = 0;      // 不设这个，targetFrameRate 不生效
        Application.targetFrameRate = 60;

        // ── (2) 屏幕常亮 ──────────────────────────────────────────────
        // 这一条不是便利性设置，是**实验完整性设置**。
        // 本干预明确允许被试什么都不做（方案A 第十节：指导语须写明"你可以完全
        // 不动，那也很好"），而"总体观察"这一情境本来就几乎不点击。
        // iPad 默认两分钟无操作就暗屏——那会在干预中途把场景关掉，而且恰好发生
        // 在被试进入最安静的那种状态时。
        Screen.sleepTimeout = SleepTimeout.NeverSleep;

        // ── (3) 横屏锁定（允许左右两个方向）──────────────────────────
        // 锁的不是"某一个朝向"，是**宽高比**。前后两次测试若一次横屏一次竖屏，
        // 视野范围完全不同，读数不可比。
        // 允许 LandscapeLeft / LandscapeRight 两个方向，是为了让被试怎么拿都行——
        // 手持姿势属于生态效度的一部分，不该由我们规定。
        Screen.autorotateToPortrait = false;
        Screen.autorotateToPortraitUpsideDown = false;
        Screen.autorotateToLandscapeLeft = true;
        Screen.autorotateToLandscapeRight = true;
        Screen.orientation = ScreenOrientation.AutoRotation;
    }


    /// <summary>
    /// 【V2 新增】解析屏幕 DPI。
    ///
    /// ※ 这是 V2 引入的一个新的"一错全错"的单点：DPI 错了，dragThresholdMM 和
    ///   lookSensitivityDegPerCm 会**同时**静默地偏掉，而外在表现是"点击不好用"
    ///   "拖动太灵敏"——跟参数没调好长得一模一样，查起来会很久。
    ///   所以它必须显示在调试框里，用了兜底值时还要红字提示。
    ///   这条规则来自 V1 的教训：凡是一关就全盘失效的东西，状态必须可见。
    ///
    /// ※ iOS 上 Screen.dpi 由 Unity 按机型返回，可靠。某些桌面平台会返回 0。
    /// </summary>
    private void ResolveDpi()
    {
        float dpi = Screen.dpi;

        // 上界 1000 是个 sanity check：至今没有哪块屏超过它，超了说明读数有问题。
        if (dpi < 1f || dpi > 1000f || float.IsNaN(dpi))
        {
            screenDpi = FallbackDpi;
            dpiIsFallback = true;
            Debug.LogWarning($"[TapMoveCamera] Screen.dpi 返回了 {dpi}，不可用，已改用兜底值 " +
                             $"{FallbackDpi}。所有以毫米/厘米定义的参数（拖动阈值、拖动灵敏度）" +
                             $"的实际手感会因此偏离。请在调试框里确认这一行。");
        }
        else
        {
            screenDpi = dpi;
            dpiIsFallback = false;
        }

        lastScreenWidth = Screen.width;
        lastScreenHeight = Screen.height;
    }


    /// <summary>
    /// 【V2 新增】把以物理长度定义的参数折算成像素。
    ///
    /// 每帧都能调用（很便宜），但实际只在 Start 和分辨率变化时调。
    /// 分成一个独立函数，是为了让"哪些量依赖 DPI"一目了然——将来若再增加物理量
    /// 定义的参数，加在这里，不要散落到各处去算。
    /// </summary>
    private void RecomputeDeviceDerivedValues()
    {
        // 1 英寸 = 25.4 毫米
        pixelsPerMM = screenDpi / 25.4f;

        dragThresholdPx = Mathf.Max(1f, dragThresholdMM * pixelsPerMM);

        // 度/像素 = (度/厘米) ÷ (像素/厘米) = (度/厘米) × 2.54 ÷ dpi
        lookSensDegPerPx = lookSensitivityDegPerCm * 2.54f / Mathf.Max(1f, screenDpi);

        // 调试字号按 DPI 缩放，使物理字高在不同设备上一致。
        // 不缩放的话，22 px 在 264 ppi 的 iPad 上只有桌面的三分之一大小，
        // 举在手上根本读不清——而调试框读不清等于第五步没法做。
        scaledFontSize = Mathf.Max(8, Mathf.RoundToInt(debugFontSize * screenDpi / DebugFontReferenceDpi));
    }


    // ========================================================================
    // 输入处理
    // ========================================================================

    private void HandleTapInput()
    {
        Vector2? currentPosition = GetPointerPosition();
        bool pressed = IsPointerPressedThisFrame();
        bool released = IsPointerReleasedThisFrame();

        if (pressed && currentPosition.HasValue)
        {
            isPointerDown = true;
            isDraggingLook = false;
            pointerDownPosition = currentPosition.Value;
            lastPointerPosition = currentPosition.Value;

            // 在**按下**那一刻就把射线算好存起来。
            // 理由：射线是从相机位姿出发的，而抬起手指要过几十毫秒。若在抬起时才算，
            // 移动中（或减速滑行中）相机已经挪过位置、还在转向，射线会从新位姿穿过
            // 旧屏幕点，打到别处去。而『移动中点击』恰恰是『我看到点什么，改主意去
            // 那边』的典型时刻。
            if (cam != null)
            {
                pressRay = cam.ScreenPointToRay(pointerDownPosition);
                pressRayValid = true;
            }
        }

        if (isPointerDown && currentPosition.HasValue)
        {
            Vector2 deltaFromStart = currentPosition.Value - pointerDownPosition;

            // 【V2 改】阈值改为按 dragThresholdMM 实时折算的像素值（见 dragThresholdPx）。
            // 比较仍然在像素空间做——输入事件本来就是像素的，把它换算成毫米再比
            // 只是多一次除法，且会在每帧的路径上引入不必要的浮点误差。
            if (!isDraggingLook && deltaFromStart.magnitude > dragThresholdPx)
            {
                isDraggingLook = true;

                // 一开始拖动就立即取消移动意图，但不清零速度——让它按 deceleration
                // 自然滑停。被试无需额外点击『取消移动』。
                //
                // ※ 已知的一个语义模糊：被试可能只是想『边走边瞥一眼』，而不是想停。
                //   目前两者共用同一个动作，系统一律理解为『想停』。这是待解决项，
                //   不要在这里随手加一个『拖动幅度小就不停』之类的启发式——那会造成
                //   『同样的动作有时停有时不停』，比一律停下更让人困惑。
                if (isMoving)
                {
                    isMoving = false;
                    hasTurnTarget = false;
                    targetPosition = transform.position;
                }
            }

            if (isDraggingLook)
            {
                Vector2 delta = currentPosition.Value - lastPointerPosition;
                ApplyLookDrag(delta);
            }

            lastPointerPosition = currentPosition.Value;
        }

        if (released && isPointerDown)
        {
            if (isDraggingLook)
            {
                // 一次环顾结束，把当前实际朝向吸收进 bodyYaw，下一次拖动从这里重新起算。
                // 否则连续几次拖动会一直受同一个 headYaw 极限的约束，转不过去。
                bodyYaw = transform.eulerAngles.y;
                headYaw = 0f;
                desiredBodyYaw = bodyYaw;
                ApplyCameraRotation();
            }
            else if (pressRayValid)
            {
                ResolveTap(pressRay);
            }

            isPointerDown = false;
            isDraggingLook = false;
            pressRayValid = false;
        }
    }


    // ========================================================================
    // 【核心】点击语义判定
    // ========================================================================

    /// <summary>
    /// 一次点击的完整处理：射线 → 判定语义 → 算出想去的位置 → 沿路检查能走多远 → 设为目标。
    ///
    /// 流程刻意分成四个独立步骤，每一步都可以单独看懂、单独改：
    ///   1. 打中了什么
    ///   2. 那儿能不能站人（→ 语义）
    ///   3. 语义决定『理想终点』
    ///   4. 路径采样把理想终点削减为『实际能到的终点』
    ///
    /// 后来者若要改判定规则，绝大多数情况只需要动第 2 步。
    /// </summary>
    private void ResolveTap(Ray ray)
    {
        ResetTapDebug();

        // ---- 步骤 1：打中了什么 --------------------------------------------
        if (!Physics.Raycast(ray, out RaycastHit hit, tapRayDistance, tapRayMask))
        {
            // 打空了。常见于点天空、点林间透光的缝隙、或超出射程。
            // 此时**什么都不做**是对的——被试点了个不存在的地方。
            // 不要在这里加『朝那个方向走一段』之类的兜底：那会让点天空变成一种
            // 有效操作，被试很快会发现并利用它，那就成了一个需要被学会的规则。
            lastIntent = TapIntent.None;
            lastHitName = "(未命中)";
            return;
        }

        hasLastHit = true;
        lastHitPoint = hit.point;
        lastHitName = hit.collider != null ? hit.collider.name : "?";
        lastHitLayer = LayerMask.LayerToName(hit.collider.gameObject.layer);
        lastHitDistance = hit.distance;

        Vector3 selfFlat = Flat(transform.position);
        Vector3 hitFlat = Flat(hit.point);

        // ---- 步骤 2：那儿能不能站人 → 语义 ---------------------------------
        TapIntent intent = ClassifyHit(hit);
        lastIntent = intent;

        // ---- 步骤 3：语义决定理想终点 --------------------------------------
        //
        // 【V1 实测后的结构调整】
        // 原本 WalkTo 走到点上、只有 LookAt 才留距离。实测下来两种语义都需要留距离，
        // 只是留多少不同。所以这里统一成一个"保持距离"，由语义决定取哪个值。
        //
        // 这没有改变判定逻辑（判据仍然只有可通行性），改的是落点的算法。
        // 保持距离同时承担两件事：
        //   (1) 近处点击 → 只转身不移动（避免那种很碎的一小步）
        //   (2) 远处点击 → 停在目标前面一点，让目标还留在画面里
        // 两件事用同一个数表达，是因为它们本来就是同一件事：别贴到目标上去。

        float keepDistance = (intent == TapIntent.WalkTo) ? walkKeepDistance : viewingDistance;
        lastKeepDistance = keepDistance;

        Vector3 toHit = hitFlat - selfFlat;
        float distToHit = toHit.magnitude;

        Vector3 desiredFlat;

        if (distToHit <= keepDistance + arriveThreshold)
        {
            // 已经在保持距离之内。不后退——"后退"这个意图在本方案里表达不出来，
            // 系统自作主张地后退会让被试莫名其妙地被推开。
            // 但也不能什么都不发生（那就是一次"无意义的点击"），所以转身朝向它。
            if (lookAtAlwaysTurnsBody)
            {
                RequestTurnTowards(toHit);
            }
            isMoving = false;
            targetPosition = transform.position;
            lastRequestedDistance = 0f;
            lastGrantedDistance = 0f;
            return;
        }

        desiredFlat = (keepDistance <= 0.001f)
            ? hitFlat
            : hitFlat - toHit.normalized * keepDistance;

        // ---- 步骤 4：路径采样，削减为实际能到的终点 ------------------------
        Vector3 finalFlat = desiredFlat;
        bool blocked = false;

        if (usePathSampling && hasGround)
        {
            finalFlat = SampleWalkablePath(selfFlat, desiredFlat, currentGroundY, out blocked);
        }

        lastPathBlocked = blocked;
        lastRequestedDistance = (desiredFlat - selfFlat).magnitude;
        lastGrantedDistance = (finalFlat - selfFlat).magnitude;

        // 如果一步都走不了（脚下就被挡住），至少把身体转过去，让这一击有个响应。
        if (lastGrantedDistance < arriveThreshold)
        {
            if (lookAtAlwaysTurnsBody)
            {
                RequestTurnTowards(hitFlat - selfFlat);
            }
            isMoving = false;
            targetPosition = transform.position;
            return;
        }

        targetPosition = new Vector3(finalFlat.x, transform.position.y, finalFlat.z);
        RequestTurnTowards(finalFlat - selfFlat);
        isMoving = true;
    }


    /// <summary>
    /// 判断被点中的那个点能不能站人。这是整个交互的分岔口。
    ///
    /// ※ 注意：这里只判断**终点本身**，不判断路上通不通。路上的事交给路径采样。
    ///   两者分开是有意的——终点判定决定"语义"，路径采样决定"走多远"。
    /// </summary>
    private TapIntent ClassifyHit(RaycastHit hit)
    {
        int layer = hit.collider.gameObject.layer;

        // (a) 绝对不可通行层（深水阻挡板）。无论坡度如何。
        if (((1 << layer) & blockingMask.value) != 0)
        {
            lastHitSlope = Vector3.Angle(hit.normal, Vector3.up);
            return TapIntent.LookAt;
        }

        // (b) 不在可站立层里的东西 → 一律当成"看"。
        //     目前实际上不会走到这里（tapRayMask 只包含四个层），但保留这条兜底：
        //     将来若有人把新的层加进 tapRayMask 而忘了归类，行为是安全的那一侧
        //     （停下来看，而不是走进去）。
        if (((1 << layer) & walkableMask.value) == 0)
        {
            lastHitSlope = Vector3.Angle(hit.normal, Vector3.up);
            return TapIntent.LookAt;
        }

        // (c) 坡度。
        //     这一条同时处理了好几种看起来不同、其实同源的情况：
        //       - 陡坡、崖壁     → 法线明显偏斜
        //       - 树干侧面       → 法线接近水平（若将来树有了碰撞体）
        //       - 大石的侧面     → 同上
        //       - 石头/倒木的顶面 → 法线接近竖直，可以站
        //     所以"点石头顶上 = 站上去"和"点石头侧面 = 看它"是自动区分的，
        //     不需要给石头额外标注任何东西。
        float slope = Vector3.Angle(hit.normal, Vector3.up);
        lastHitSlope = slope;

        if (slope > maxWalkableSlope)
        {
            return TapIntent.LookAt;
        }

        // (d) 高差 —— 【V1 实测后删除，不要再加回来】
        //
        //     这里原本有一段：拿"命中点与当前脚下的绝对高差"跟 maxStepUpHeight /
        //     maxStepDownHeight 比，超了就判 LookAt。
        //
        //     这段是错的，而且是 V1 首测中"点什么都变成我想看""进退维谷动弹不得"
        //     的主要原因。错在哪里：
        //
        //       **你和一个远处的点之间的高差，跟能不能走过去毫无关系。**
        //       一道 20 米长的缓坡可以升高 5 米，一路都好走，但高差是 5 米。
        //
        //     实测现象与它一一对应：
        //       - 卡在河沟里 → 沟深 1m，沟外一切都比脚下高 1m 以上 → 四面全是 LookAt
        //       - 爬小路时点什么都是 LookAt → 站在坡上，前面的路面比脚下高
        //       - 点远处不走、点旁边能走 → 旁边那点的高差碰巧在阈值内
        //
        //     正确的分工是：
        //       终点判定（这里）  只管坡度 —— 那儿能不能**站住**
        //       路径采样          只管相邻采样点的高差 —— 能不能**迈过去**
        //     高差只有在"一步"的尺度上才有意义，在"你到终点"的尺度上没有意义。
        //
        //     下面这行只是记录给调试框看，不参与任何判定。
        if (hasGround)
        {
            lastHeightDelta = hit.point.y - currentGroundY;
        }

        return TapIntent.WalkTo;
    }


    // ========================================================================
    // 路径采样：穷人版寻路
    // ========================================================================

    /// <summary>
    /// 从 fromFlat 沿直线走向 toFlat，每隔 pathSampleStep 向下打一条射线找地面，
    /// 检查相邻两点的高差是否在跨越/下落能力之内、坡度是否可站。
    /// 一旦走不动了，返回最后一个还站得住的位置。
    ///
    /// 【这是什么，不是什么】
    ///   它不是 NavMesh，不会绕路，只沿直线检查。
    ///   它换来的行为是：点对岸 → 走到沟边停下；点坡上 → 走到坡度变陡处停下。
    ///   这恰好就是现实中的样子，而且**不需要烘焙、不依赖场景完成度、场景改了
    ///   也不用重做任何事**——对一个学生还在并行铺场景的项目，这条很重要。
    ///
    /// 【代价】
    ///   每次点击几十条射线。只在点击时跑一次，不是每帧，iPad 完全承受得住。
    ///
    /// 【什么时候该换成 NavMesh】
    ///   当"直线走不通但绕一下能到"变成常见抱怨的时候。目前的谷地结构里，
    ///   被试想去的地方基本都在直线可达范围内，所以先不上。
    /// </summary>
    private Vector3 SampleWalkablePath(Vector3 fromFlat, Vector3 toFlat, float startGroundY, out bool blocked)
    {
        blocked = false;

        Vector3 delta = toFlat - fromFlat;
        float totalDistance = delta.magnitude;

        if (totalDistance < 0.01f) return fromFlat;

        Vector3 dir = delta / totalDistance;

        int stepCount = Mathf.CeilToInt(totalDistance / Mathf.Max(0.05f, pathSampleStep));
        stepCount = Mathf.Min(stepCount, maxPathSamples);

        Vector3 lastStandableFlat = fromFlat;  // 走到过的、坡度还站得住的最远处
        float lastGoodY = startGroundY;

        // 【V1 实测后加入】把"路过"和"停留"分开。
        // pathMaxSlope 允许人从一小段陡坡上走过去，但人不该**停在**陡坡上——
        // 那看起来像挂在山壁上。所以落脚点只取坡度 ≤ maxWalkableSlope 的采样点。
        // 这也让两个坡度阈值的关系自洽：
        //   pathMaxSlope     = 能不能路过
        //   maxWalkableSlope = 能不能停下
        for (int i = 1; i <= stepCount; i++)
        {
            float d = Mathf.Min(totalDistance, i * pathSampleStep);
            Vector3 sampleFlat = fromFlat + dir * d;

            // 阻挡层（深水板）挡在路上。放在最前面判，因为水板浮在水面高度上，
            // 可能完全在地面探测的射线范围之外——等地面探测有了结果再判就晚了。
            //
            // 【V1 两次实测的坑，都记在这里】
            //   一测：路径采样根本没查阻挡层 → 射线穿过水板打到河床，判"通畅"，走进水。
            //   二测：合并进 SampleGround 一起查 → 仍然走进水。因为起点高度跟着河床走，
            //         深水处河床低，射线起点降到了水板底下。起点高度必须分开设。
            blockSampleCount = i;

            if (IsBlockedAt(sampleFlat, lastGoodY))
            {
                blocked = true;
                lastBlockReason = $"阻挡层 @{d:F1}m";
                return lastStandableFlat;
            }

            if (!SampleGround(sampleFlat, lastGoodY, out float groundY, out float slope))
            {
                // 这儿没地面（悬空、地形边缘外）。停在上一个站得住的点。
                blocked = true;
                lastBlockReason = $"无地面 @{d:F1}m";
                return lastStandableFlat;
            }

            float rise = groundY - lastGoodY;

            if (rise > maxStepUpHeight)
            { blocked = true; lastBlockReason = $"迈不上去 {rise:F2}m @{d:F1}m"; return lastStandableFlat; }

            if (rise < -maxStepDownHeight)
            { blocked = true; lastBlockReason = $"落差太大 {rise:F2}m @{d:F1}m"; return lastStandableFlat; }

            // 【V1 实测后改】这里原本用 maxWalkableSlope，结果被试在河沟里、
            // 在上山小路上被卡死——微地形到处都有局部超阈值的小坑小坎。
            // 改用更宽松的 pathMaxSlope：路过 ≠ 停留。见该参数注释。
            if (slope > pathMaxSlope)
            { blocked = true; lastBlockReason = $"太陡 {slope:F0}° @{d:F1}m"; return lastStandableFlat; }

            lastGoodY = groundY;

            // 只有坡度可站的采样点才能当落脚点。
            //
            // 【这一条正是"坡度挡不住人"的机制来源，实测已证实，不要误以为是 bug】
            // 路径可以从一段陡坡上通过（pathMaxSlope 55°），但人只会停在能站住的地方
            // （maxWalkableSlope 35°）。于是：
            //   被试点向一面 42° 的坡 → 路径通畅 → 人走到坡脚附近某个 35° 以下的
            //   小平面停住 → 再点一次 → 又往上蹭一小截。
            // 微地形上总能找到这样的小平面，所以 40~55° 的坡最终是能被"蹭"上去的。
            //
            // 结论（第一阶段实测确立）：**坡度只能限制单次点击的落点，不能限定活动
            // 范围。**凡是要真正封闭的边界，都必须配合遮挡物，这不是参数问题。
            if (slope <= maxWalkableSlope)
            {
                lastStandableFlat = sampleFlat;
            }
        }

        return lastStandableFlat;
    }


    /// <summary>
    /// 在某个水平位置向下探测地面。
    /// 射线起点 = 参考高度 + groundProbeUp，而不是固定的头顶高空。
    /// 为什么这么做，见 groundProbeUp 参数的注释（岩檐 / 石头 是同一个机制）。
    /// </summary>
    private bool SampleGround(Vector3 flatPos, float referenceY, out float groundY, out float slope)
    {
        Vector3 origin = new Vector3(flatPos.x, referenceY + groundProbeUp, flatPos.z);
        float maxDist = groundProbeUp + groundProbeDown;

        // 只查可站立层。阻挡层（水板）由 IsBlockedAt 单独负责，不要合并进来——
        // 两者需要的射线起点高度差一个量级，见 blockProbeUp 的注释。
        if (Physics.Raycast(origin, Vector3.down, out RaycastHit hit, maxDist, walkableMask))
        {
            groundY = hit.point.y;
            slope = Vector3.Angle(hit.normal, Vector3.up);
            return true;
        }

        groundY = referenceY;
        slope = 0f;
        return false;
    }


    /// <summary>
    /// 【V1 二测后新增】在某个水平位置检查有没有阻挡层（深水板）。
    ///
    /// 单独一条射线，起点抬得比地面探测高得多。为什么不能跟 SampleGround 合并：
    ///   - 地面探测的起点必须**低**（0.7m），否则头顶的岩檐、树冠会被误当成地面。
    ///   - 阻挡探测的起点必须**高**（数米），因为水板浮在水面上，而参考高度跟着
    ///     河床走；河床越深两者差得越远，低起点的射线从水板下面穿过去了。
    /// 这两个要求方向相反，只能各用各的射线。
    /// </summary>
    private bool IsBlockedAt(Vector3 flatPos, float referenceY)
    {
        if (blockingMask.value == 0) return false;

        Vector3 origin = new Vector3(flatPos.x, referenceY + blockProbeUp, flatPos.z);
        float maxDist = blockProbeUp + groundProbeDown;

        return Physics.Raycast(origin, Vector3.down, maxDist, blockingMask);
    }


    // ========================================================================
    // 转向与移动
    // ========================================================================

    private void RequestTurnTowards(Vector3 flatDirection)
    {
        if (flatDirection.sqrMagnitude < 0.0001f) return;

        // 把当前实际朝向吸收进 bodyYaw 再重新起算，避免上一次环顾留下的 headYaw
        // 参与到这次转向里（否则会出现"转过头"或反向摆动）。
        bodyYaw = transform.eulerAngles.y;
        headYaw = 0f;

        float wanted = Quaternion.LookRotation(flatDirection.normalized, Vector3.up).eulerAngles.y;

        // 【V1 实测后加入】死区。夹角很小就干脆不转。
        // 没有死区时，点屏幕正中偏一点点画面都要挪一下，那种持续的小抽动本身
        // 就是"我在操作一个装置"的提示。
        if (Mathf.Abs(Mathf.DeltaAngle(bodyYaw, wanted)) < turnDeadZoneAngle)
        {
            desiredBodyYaw = bodyYaw;
            hasTurnTarget = false;
            return;
        }

        desiredBodyYaw = wanted;
        turnVelocity = 0f;   // 新的一次转向，速度从零起
        hasTurnTarget = true;
    }

    private void UpdateTurning()
    {
        if (hasTurnTarget)
        {
            // 【V1 实测后改】缓入缓出，不是匀速。
            // 原来用 MoveTowardsAngle（匀速），一按下就全速起转，实测像"猛地一扭头"。
            // 人转头是有加速和收尾的；匀速无论调多慢都不对味，问题在曲线不在速度。
            //
            // SmoothDampAngle 会自动处理角度绕回（359°→1°），不必自己判象限。
            bodyYaw = Mathf.SmoothDampAngle(
                bodyYaw, desiredBodyYaw, ref turnVelocity, turnSmoothTime,
                maxTurnSpeed, Time.deltaTime);

            if (Mathf.Abs(Mathf.DeltaAngle(bodyYaw, desiredBodyYaw)) < 0.3f)
            {
                bodyYaw = desiredBodyYaw;
                turnVelocity = 0f;
                hasTurnTarget = false;
            }
        }

        if (returnHeadOnMove && isMoving)
        {
            headYaw = Mathf.Lerp(headYaw, 0f, headReturnSpeed * Time.deltaTime);
            headPitch = Mathf.Lerp(headPitch, 0f, headReturnSpeed * Time.deltaTime);
        }

        if (hasTurnTarget || (returnHeadOnMove && isMoving))
        {
            ApplyCameraRotation();
        }
    }

    private void UpdateMovement()
    {
        Vector3 selfFlat = Flat(transform.position);
        Vector3 targetFlat = Flat(targetPosition);

        Vector3 toTarget = targetFlat - selfFlat;
        float remaining = toTarget.magnitude;

        if (isMoving && remaining <= arriveThreshold)
        {
            isMoving = false;
        }

        // 先转身再迈步。
        // 人不会一边横着平移一边慢慢把脸转过来——那是摄像机运镜，不是走路，
        // 而且纯旋转产生光流但无视差，知觉上读作"画面在动"而不是"我在动"。
        bool waitingToTurn = false;
        if (isMoving && hasTurnTarget && turnBeforeMoveAngle < 179f)
        {
            float angleToTarget = Mathf.Abs(Mathf.DeltaAngle(bodyYaw, desiredBodyYaw));
            if (angleToTarget > turnBeforeMoveAngle)
            {
                waitingToTurn = true;
            }
        }

        // 到站前自然减速：算出以当前速度刹停需要多长距离，快到了就松油门。
        float brakingDistance = (currentMoveSpeed * currentMoveSpeed) / (2f * Mathf.Max(0.01f, deceleration));
        bool shouldBrake = isMoving && remaining <= brakingDistance + arriveThreshold;

        float desiredSpeed = (isMoving && !waitingToTurn && !shouldBrake) ? moveSpeed : 0f;
        float rate = desiredSpeed > currentMoveSpeed ? acceleration : deceleration;

        currentMoveSpeed = Mathf.MoveTowards(currentMoveSpeed, desiredSpeed, rate * Time.deltaTime);

        if (currentMoveSpeed <= 0.001f)
        {
            currentMoveSpeed = 0f;
            return;
        }

        Vector3 moveDirection;
        if (isMoving && remaining > 0.001f)
        {
            moveDirection = toTarget / remaining;
            lastMoveDirection = moveDirection;
        }
        else
        {
            // 已经取消移动但还在滑行——沿最后的方向继续减速滑出去。
            // 这就是"停下的余速"，属于身体存在感的一部分，不要去掉。
            moveDirection = lastMoveDirection;
        }

        if (moveDirection == Vector3.zero) return;

        float step = currentMoveSpeed * Time.deltaTime;

        if (isMoving && step > remaining)
        {
            step = remaining;
            isMoving = false;
        }

        transform.position += moveDirection * step;
    }


    // ========================================================================
    // 地面跟随
    // ========================================================================

    private void UpdateGroundHeight()
    {
        Vector3 pos = transform.position;
        Vector3 flat = Flat(pos);

        // 参考高度用"当前脚下高度"，而不是相机高度。
        float reference = hasGround ? currentGroundY : pos.y - eyeHeight;

        // 【V1 二测后改】这里曾经有一段"探测到水板就保留上一帧地面高度"的补丁，
        // 结果是人浮在水面上——治标，而且治错了地方。
        // 相机高度永远只跟真实地面走；不让人进水是路径采样的职责，不是高度跟随的职责。
        if (SampleGround(flat, reference, out float groundY, out float slope))
        {
            currentGroundY = groundY;
            hasGround = true;

            float targetY = groundY + eyeHeight;
            pos.y = Mathf.Lerp(pos.y, targetY, heightSmoothSpeed * Time.deltaTime);
            transform.position = pos;
        }
        else
        {
            // 探不到地面。多半是走出了地形边界，或站在了一个探测范围够不着的地方。
            // 不做任何"掉下去"的处理——本项目没有重力，也不该有。保持原高度。
            hasGround = false;
        }
    }

    private void SnapToGroundImmediate()
    {
        Vector3 pos = transform.position;

        // 初始化时还不知道地面在哪，用一条足够长的射线从高处找一次。
        // 这是唯一一处允许从高空打射线的地方（只在 Start 跑一次，不存在岩檐问题，
        // 因为出生点是人工放置的，不会放在岩檐下面）。
        Vector3 origin = new Vector3(pos.x, pos.y + 50f, pos.z);
        if (Physics.Raycast(origin, Vector3.down, out RaycastHit hit, 200f, walkableMask))
        {
            currentGroundY = hit.point.y;
            hasGround = true;
            pos.y = currentGroundY + eyeHeight;
            transform.position = pos;
        }
        else
        {
            Debug.LogWarning("[TapMoveCamera] 出生点下方没有探测到可站立地面。" +
                             "请检查出生点位置，以及地形是否已归入 Terrain 层。");
        }
    }


    // ========================================================================
    // 环顾
    // ========================================================================

    private void ApplyLookDrag(Vector2 delta)
    {
        // 【V2 改】用 lookSensDegPerPx（由 lookSensitivityDegPerCm 按 DPI 折算而来），
        // 不再直接用一个以像素定义的灵敏度。见该参数注释。
        float yawInput = delta.x * lookSensDegPerPx;
        float pitchInput = -delta.y * lookSensDegPerPx;

        headYaw = ApplyLimitedRotation(headYaw, yawInput, maxYawAngle);
        headPitch = ApplyLimitedRotation(headPitch, pitchInput, maxPitchAngle);

        ApplyCameraRotation();
    }

    /// <summary>
    /// 接近转动极限时逐渐变黏，模拟脖子的生理限制。
    ///
    /// ※ 修正了旧版的一处：旧版按 |当前角度|/极限 算阻力，不看输入方向。结果是视角
    ///   已经偏到 65° 时，**往回拉和继续往外推一样费劲**。跟随蝴蝶这类"甩出去再
    ///   收回来"的动作，收回来那一半是黏的。现在只在"继续往外推"时施加阻力。
    /// </summary>
    private float ApplyLimitedRotation(float currentAngle, float inputDelta, float limit)
    {
        bool pushingOutward = Mathf.Sign(inputDelta) == Mathf.Sign(currentAngle) || Mathf.Approximately(currentAngle, 0f);

        float effectiveInput = inputDelta;

        if (pushingOutward)
        {
            float normalized = Mathf.Clamp01(Mathf.Abs(currentAngle) / Mathf.Max(0.01f, limit));
            float resistance = Mathf.Pow(normalized, lookResistancePower);
            effectiveInput = inputDelta * (1f - resistance);
        }

        return Mathf.Clamp(currentAngle + effectiveInput, -limit, limit);
    }

    private void ApplyCameraRotation()
    {
        transform.rotation = Quaternion.Euler(headPitch, bodyYaw + headYaw, 0f);
    }


    // ========================================================================
    // 输入设备读取（New Input System）
    // ========================================================================

    private Vector2? GetPointerPosition()
    {
        if (Touchscreen.current != null && Touchscreen.current.primaryTouch.press.isPressed)
            return Touchscreen.current.primaryTouch.position.ReadValue();

        if (Mouse.current != null)
            return Mouse.current.position.ReadValue();

        if (Touchscreen.current != null)
            return Touchscreen.current.primaryTouch.position.ReadValue();

        return null;
    }

    private bool IsPointerPressedThisFrame()
    {
        if (Touchscreen.current != null && Touchscreen.current.primaryTouch.press.wasPressedThisFrame) return true;
        if (Mouse.current != null && Mouse.current.leftButton.wasPressedThisFrame) return true;
        return false;
    }

    private bool IsPointerReleasedThisFrame()
    {
        if (Touchscreen.current != null && Touchscreen.current.primaryTouch.press.wasReleasedThisFrame) return true;
        if (Mouse.current != null && Mouse.current.leftButton.wasReleasedThisFrame) return true;
        return false;
    }


    // ========================================================================
    // 工具
    // ========================================================================

    private static Vector3 Flat(Vector3 v) => new Vector3(v.x, 0f, v.z);

    /// <summary>把 LayerMask 转成可读的层名列表，用于调试显示。</summary>
    private static string LayerMaskToNames(LayerMask mask)
    {
        if (mask.value == 0) return "【空！水拦不住】";

        string result = "";
        for (int i = 0; i < 32; i++)
        {
            if ((mask.value & (1 << i)) == 0) continue;
            string n = LayerMask.LayerToName(i);
            if (string.IsNullOrEmpty(n)) n = "Layer" + i;
            result += (result.Length > 0 ? "," : "") + n;
        }
        return result;
    }


    // ========================================================================
    // 调试显示
    //
    // ※ 这不是可有可无的装饰。没有它，测试时"人没走过去"这一个现象背后可能是：
    //   射线没打中 / 层没归对 / 坡度阈值不合适 / 路径采样挡住了 / 高差判定拦下了，
    //   五种完全不同的原因，从外面看一模一样。
    // ※ 正式实验前把 showDebugOverlay 关掉。
    // ========================================================================

    private void ResetTapDebug()
    {
        lastIntent = TapIntent.None;
        lastHitName = "-";
        lastHitLayer = "-";
        lastHitDistance = 0f;
        lastHitSlope = 0f;
        lastHeightDelta = 0f;
        lastPathBlocked = false;
        lastRequestedDistance = 0f;
        lastGrantedDistance = 0f;
        lastKeepDistance = 0f;
        lastBlockReason = "-";
        blockSampleCount = 0;
        hasLastHit = false;
    }

    /// <summary>
    /// 【V2 新增】调试框的一行。
    /// 改成先收集、后绘制，是为了让框高**由实际行数算出来**，而不是靠一个手写的常量。
    /// V1 已经为写死行高吃过一次亏（截掉的恰好是路径采样开关，查了两轮代码），
    /// 而 V2 又要再加三行设备信息——沿用写死的做法必然会再犯同一个错。
    /// 现在加行、减行、加条件行都不需要动任何计数。
    /// </summary>
    private struct DebugLine
    {
        public string text;
        public Color color;
        public DebugLine(string t, Color c) { text = t; color = c; }
    }

    private readonly System.Collections.Generic.List<DebugLine> debugLines
        = new System.Collections.Generic.List<DebugLine>();

    void OnGUI()
    {
        if (!showDebugOverlay) return;

        if (debugStyle == null)
        {
            debugStyle = new GUIStyle(GUI.skin.label);
            debugStyle.normal.textColor = Color.white;
        }
        // 【V2 改】用按 DPI 缩放后的字号，不再直接用 debugFontSize。
        debugStyle.fontSize = scaledFontSize;

        Color white = Color.white;
        Color warn = new Color(1f, 0.6f, 0.4f);
        Color alarm = new Color(1f, 0.45f, 0.45f);

        debugLines.Clear();

        string intentText;
        Color intentColor;
        switch (lastIntent)
        {
            case TapIntent.WalkTo: intentText = "走过去 WalkTo"; intentColor = new Color(0.5f, 1f, 0.5f); break;
            case TapIntent.LookAt: intentText = "我想看 LookAt"; intentColor = new Color(1f, 0.85f, 0.4f); break;
            default: intentText = "无 (未命中)"; intentColor = new Color(1f, 0.5f, 0.5f); break;
        }

        debugLines.Add(new DebugLine("判定：" + intentText, intentColor));

        // 路径采样总开关。关掉时一切"走不过去"的判定都不生效——包括水。
        // 放在很显眼的位置，因为它是最容易被忘记勾回来、后果又最大的一个开关。
        if (!usePathSampling)
            debugLines.Add(new DebugLine("⚠ 路径采样已关闭：水与陡坡都拦不住", alarm));
        else
            debugLines.Add(new DebugLine("路径采样：开", white));

        debugLines.Add(new DebugLine("命中对象：" + lastHitName, white));
        debugLines.Add(new DebugLine("所属层　：" + lastHitLayer, white));
        debugLines.Add(new DebugLine($"命中距离：{lastHitDistance:F2} m", white));

        // 坡度是本轮最要紧的一个数：它同时决定"哪儿挡得住"和"哪儿上得去"。
        // 站在不同的坡上点一点，把这个读数记下来，就是在给 maxWalkableSlope 找依据。
        debugLines.Add(new DebugLine(
            $"命中处坡度：{lastHitSlope:F1}°　(停留阈值 {maxWalkableSlope:F0}° / 路过阈值 {pathMaxSlope:F0}°)",
            (lastHitSlope > maxWalkableSlope) ? warn : white));

        // 高差只是信息，不参与判定（V1 实测后已从判定中移除，见 ClassifyHit）
        debugLines.Add(new DebugLine($"与脚下高差：{lastHeightDelta:F2} m　(仅供参考，不参与判定)", white));

        // 保持距离，以及"能看见的最近地面"。
        // 后者 = eyeHeight / tan(maxPitchAngle)：低头到极限时，画面下沿落在多远的地面上。
        // 保持距离若小于这个数，走到终点时目标就掉出屏幕了——这正是 V1 首测的抱怨之一。
        float minVisible = eyeHeight / Mathf.Max(0.01f, Mathf.Tan(maxPitchAngle * Mathf.Deg2Rad));
        bool keepTooSmall = lastKeepDistance > 0.001f && lastKeepDistance < minVisible;
        debugLines.Add(new DebugLine(
            $"保持距离：{lastKeepDistance:F2} m　可见最近地面：{minVisible:F2} m",
            keepTooSmall ? warn : white));

        // 【V1 三测后改】区分两种"没走到位"，它们是不同的事：
        //
        //   受阻      路上真的过不去（太陡 / 高差 / 阻挡层 / 无地面）→ 人被拦在半路
        //   落不了脚  路是通的，但后半段坡度超过 maxWalkableSlope，站不住 → 退回最后
        //             一个能站的点
        //
        // 原来两者都显示"通畅"，因为 blocked 只在前一种情况下置位。结果是实测中
        // 看到"路径：通畅　想走 4.3 / 实走 3.0"——明明被截短了却说通畅，会误以为
        // 人已经走到位。这不是逻辑错，是显示误导，但排查时一样害人。
        bool shortOfTarget = !lastPathBlocked
                             && lastRequestedDistance - lastGrantedDistance > 0.3f;

        string pathText;
        if (lastPathBlocked)        pathText = lastBlockReason;
        else if (shortOfTarget)     pathText = $"坡上无处落脚 @{lastGrantedDistance:F1}m";
        else                        pathText = "通畅";

        debugLines.Add(new DebugLine(
            $"路径：{pathText}　想走 {lastRequestedDistance:F1} / 实走 {lastGrantedDistance:F1} m　(采样 {blockSampleCount} 点)",
            (lastPathBlocked || shortOfTarget) ? warn : white));

        // ── 阻挡层诊断 ─────────────────────────────────────────────
        // blockingMask 若为空，IsBlockedAt 直接返回 false，水就拦不住。
        // "脚下阻挡层"是每帧实时检测：走到水边看它翻不翻成"是"，
        // 就能立刻分清是"层没配对"还是"水板没铺到这儿"。
        bool maskEmpty = blockingMask.value == 0;
        debugLines.Add(new DebugLine($"阻挡层遮罩：{LayerMaskToNames(blockingMask)}",
                                     maskEmpty ? new Color(1f, 0.4f, 0.4f) : white));
        debugLines.Add(new DebugLine($"脚下阻挡层：{(blockedUnderfoot ? "是（此处本不该进得来）" : "否")}",
                                     blockedUnderfoot ? new Color(0.5f, 0.9f, 1f) : white));

        debugLines.Add(new DebugLine(
            $"当前速度：{currentMoveSpeed:F2} m/s　地面高度：{(hasGround ? currentGroundY.ToString("F2") : "无")}", white));
        debugLines.Add(new DebugLine($"朝向 body {bodyYaw:F0}°　head {headYaw:F0}° / {headPitch:F0}°", white));

        // ── 【V2 新增】设备诊断 ────────────────────────────────────
        //
        // 这三行是 V2 的核心新增。DPI 是本版本引入的新的"一错全错"单点：
        // 它解析错了，拖动阈值与拖动灵敏度会**同时**静默偏掉，而外在表现是
        // "点击不好用""拖动太灵敏"——跟参数没调好长得一模一样。
        // 按 V1 那条教训（凡是一关就全盘失效的东西，状态必须可见），它必须在这儿。
        //
        // 折算后的像素值也一并显示，是为了在 iPad 上调 dragThresholdMM 时能直接
        // 对照着看："我设的 3 毫米在这块屏上到底是多少像素"。
        debugLines.Add(new DebugLine(
            dpiIsFallback
                ? $"⚠ DPI：{screenDpi:F0}（兜底值！物理尺寸参数全部不准）　{Screen.width}×{Screen.height}"
                : $"DPI：{screenDpi:F0}　{Screen.width}×{Screen.height}　{pixelsPerMM:F1} px/mm",
            dpiIsFallback ? alarm : white));

        debugLines.Add(new DebugLine(
            $"拖动阈值：{dragThresholdMM:F1} mm = {dragThresholdPx:F0} px　　灵敏度：{lookSensitivityDegPerCm:F1} °/cm",
            white));

        // 帧率。低于目标值明显偏多时变色——iOS 上不显式设 targetFrameRate 会拿到 30，
        // 而帧率是方案B 第八节列出的晕动技术变量之一。
        debugLines.Add(new DebugLine(
            $"帧率：{smoothedFps:F0} fps　(目标 {Application.targetFrameRate})",
            (Application.targetFrameRate > 0 && smoothedFps < Application.targetFrameRate * 0.8f) ? warn : white));

        // ── 绘制 ───────────────────────────────────────────────────
        //
        // 【V2 改】框高由 debugLines.Count 算出，不再是写死的常量。
        // 【V2 改】起点避开 safeArea。iPad 的圆角与状态栏区域会盖住左上角，
        //   而被盖住的恰好是第一行"判定"——又是一次"信息被截断比没有更坏"。
        float lineH = scaledFontSize * 1.65f;
        float w = scaledFontSize * 32f;
        float h = lineH * debugLines.Count + 28f;

        Rect safe = Screen.safeArea;
        float x0 = safe.x + 10f;
        // GUI 坐标系原点在左上，而 safeArea 的原点在左下，需要换算。
        float y0 = (Screen.height - safe.yMax) + 10f;

        GUI.Box(new Rect(x0, y0, w, h), "");
        GUILayout.BeginArea(new Rect(x0 + 14f, y0 + 12f, w - 28f, h - 24f));

        for (int i = 0; i < debugLines.Count; i++)
        {
            debugStyle.normal.textColor = debugLines[i].color;
            GUILayout.Label(debugLines[i].text, debugStyle);
        }
        debugStyle.normal.textColor = Color.white;

        GUILayout.EndArea();
    }

    void OnDrawGizmos()
    {
        if (!drawDebugGizmos || !Application.isPlaying) return;

        if (hasLastHit)
        {
            Gizmos.color = (lastIntent == TapIntent.WalkTo) ? Color.green : Color.yellow;
            Gizmos.DrawWireSphere(lastHitPoint, 0.3f);
            Gizmos.DrawLine(transform.position, lastHitPoint);
        }

        if (isMoving)
        {
            Gizmos.color = Color.cyan;
            Vector3 t = new Vector3(targetPosition.x, currentGroundY, targetPosition.z);
            Gizmos.DrawWireCube(t, new Vector3(0.4f, 0.05f, 0.4f));
        }
    }
}