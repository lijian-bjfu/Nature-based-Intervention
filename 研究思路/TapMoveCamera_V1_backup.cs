using UnityEngine;
using UnityEngine.InputSystem;

/// <summary>
/// ============================================================================
/// TapMoveCamera_V1 —— 屏幕端虚拟自然干预平台 · 相机导航与点击语义判定
/// ============================================================================
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
public class TapMoveCamera : MonoBehaviour
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

    [Tooltip("身体转向速度 (度/秒)。\n" +
             "※ 旧版这里是一个 Lerp 系数 (1.2)，含义是每秒衰减比例，实际转 180° 要两三秒，\n" +
             "  会造成『人已经在横着滑，画面才慢慢转过来』——那是最像『操作一个视图』的时刻。\n" +
             "  现在改成明确的角速度，好理解也好调。")]
    public float bodyTurnSpeed = 120f;

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

    [Tooltip("路径采样的最大点数，防止点了很远的地方时开销失控。")]
    public int maxPathSamples = 200;


    [Header("── 地面探测 ────────────────────")]

    [Tooltip("地面探测射线的向下探测距离 (m)。用于走下坡时找到地面。")]
    public float groundProbeDown = 6f;

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

    [Tooltip("拖动灵敏度：每像素转多少度。")]
    public float lookSensitivity = 0.12f;

    [Tooltip("头部左右转动极限 (度)。模拟脖子的生理限制。")]
    public float maxYawAngle = 70f;

    [Tooltip("头部俯仰极限 (度)。\n" +
             "※ 旧值 35° 太小：眼高 1.7m 时，俯角 35° 意味着眼前约 2.4m 以内的地面\n" +
             "  根本进不了画面。而『走过去』的落点判断全靠点地面——被试为了看清一样\n" +
             "  东西走近它，走近的结果却是它掉出屏幕下沿。60° 大致相当于低头看脚前 1m。")]
    public float maxPitchAngle = 60f;

    [Tooltip("接近转动极限时的阻力曲线指数。越大，越靠近极限越黏。")]
    public float lookResistancePower = 2f;

    [Tooltip("判定为『拖动』而非『点击』的位移阈值（屏幕像素）。\n" +
             "太小会把手指的轻微滚动误判成拖动（点击失效）；\n" +
             "太大会把想微调视角的小滑动误判成点击（人莫名走出去）。")]
    public float dragThreshold = 12f;

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

    [Tooltip("调试文字大小。iPad 上屏幕分辨率高，需要放大。")]
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
    private Vector3 lastHitPoint;
    private bool hasLastHit = false;
    private GUIStyle debugStyle;


    // ========================================================================
    // 生命周期
    // ========================================================================

    void Start()
    {
        cam = Camera.main;
        if (cam == null) cam = GetComponent<Camera>();

        AutoFillLayerMasks();

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
        HandleTapInput();
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

            if (!isDraggingLook && deltaFromStart.magnitude > dragThreshold)
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
        Vector3 desiredFlat;

        if (intent == TapIntent.WalkTo)
        {
            // 走过去：终点就是那个点。
            desiredFlat = hitFlat;
        }
        else
        {
            // 我想看：停在离**命中点** viewingDistance 处。
            Vector3 toHit = hitFlat - selfFlat;
            float dist = toHit.magnitude;

            if (dist <= viewingDistance + arriveThreshold)
            {
                // 已经在观看距离之内了。不后退——"后退"这个意图在本方案里表达不出来，
                // 系统自作主张地后退会让被试莫名其妙地被推开。
                // 但也不能什么都不发生（那就是一次"无意义的点击"），所以转身朝向它。
                if (lookAtAlwaysTurnsBody)
                {
                    RequestTurnTowards(hitFlat - selfFlat);
                }
                isMoving = false;
                targetPosition = transform.position;
                lastRequestedDistance = 0f;
                lastGrantedDistance = 0f;
                return;
            }

            desiredFlat = hitFlat - toHit.normalized * viewingDistance;
        }

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

        // (d) 高差。爬不上去 / 不敢跳下去。
        //     本场景是山谷地形，"站在坡顶点谷底"是高频情况，这一条专门管它。
        if (hasGround)
        {
            float delta = hit.point.y - currentGroundY;
            lastHeightDelta = delta;

            if (delta > maxStepUpHeight) return TapIntent.LookAt;      // 太高，上不去
            if (delta < -maxStepDownHeight) return TapIntent.LookAt;   // 太低，不敢下

            // ※ 这里有一个已知的不精确：一个很远、但可以沿缓坡走过去的低处，
            //   它与当前位置的高差可能很大，会被误判成 LookAt。严格说这需要沿路
            //   累计高差来判断，而那正是路径采样在做的事。
            //   之所以在终点判定这里也保留一个粗的高差检查，是因为它便宜、且能挡掉
            //   最刺眼的情况（站在崖顶点谷底）。若测试中发现"明明走得过去却判成看"
            //   频繁发生，把 maxStepDownHeight 调大，或者干脆去掉这两行、
            //   全部交给路径采样。
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

        Vector3 lastGoodFlat = fromFlat;
        float lastGoodY = startGroundY;

        for (int i = 1; i <= stepCount; i++)
        {
            float d = Mathf.Min(totalDistance, i * pathSampleStep);
            Vector3 sampleFlat = fromFlat + dir * d;

            if (!SampleGround(sampleFlat, lastGoodY, out float groundY, out float slope))
            {
                // 这儿没地面（悬空、地形边缘外）。停在上一个好点。
                blocked = true;
                return lastGoodFlat;
            }

            float rise = groundY - lastGoodY;

            if (rise > maxStepUpHeight) { blocked = true; return lastGoodFlat; }   // 迈不上去
            if (rise < -maxStepDownHeight) { blocked = true; return lastGoodFlat; } // 不敢往下跳
            if (slope > maxWalkableSlope) { blocked = true; return lastGoodFlat; }  // 太陡站不住

            lastGoodFlat = sampleFlat;
            lastGoodY = groundY;
        }

        return lastGoodFlat;
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

        desiredBodyYaw = Quaternion.LookRotation(flatDirection.normalized, Vector3.up).eulerAngles.y;
        hasTurnTarget = true;
    }

    private void UpdateTurning()
    {
        if (!hasTurnTarget) return;

        bodyYaw = Mathf.MoveTowardsAngle(bodyYaw, desiredBodyYaw, bodyTurnSpeed * Time.deltaTime);

        if (returnHeadOnMove && isMoving)
        {
            headYaw = Mathf.Lerp(headYaw, 0f, headReturnSpeed * Time.deltaTime);
            headPitch = Mathf.Lerp(headPitch, 0f, headReturnSpeed * Time.deltaTime);
        }

        ApplyCameraRotation();

        if (Mathf.Abs(Mathf.DeltaAngle(bodyYaw, desiredBodyYaw)) < 0.5f)
        {
            hasTurnTarget = false;
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
        if (isMoving && turnBeforeMoveAngle < 179f)
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
        float yawInput = delta.x * lookSensitivity;
        float pitchInput = -delta.y * lookSensitivity;

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
        hasLastHit = false;
    }

    void OnGUI()
    {
        if (!showDebugOverlay) return;

        if (debugStyle == null)
        {
            debugStyle = new GUIStyle(GUI.skin.label);
            debugStyle.normal.textColor = Color.white;
        }
        debugStyle.fontSize = debugFontSize;

        string intentText;
        Color intentColor;
        switch (lastIntent)
        {
            case TapIntent.WalkTo: intentText = "走过去 WalkTo"; intentColor = new Color(0.5f, 1f, 0.5f); break;
            case TapIntent.LookAt: intentText = "我想看 LookAt"; intentColor = new Color(1f, 0.85f, 0.4f); break;
            default: intentText = "无 (未命中)"; intentColor = new Color(1f, 0.5f, 0.5f); break;
        }

        float w = 520f;
        float h = 330f;
        GUI.Box(new Rect(10, 10, w, h), "");

        GUILayout.BeginArea(new Rect(24, 24, w - 28, h - 28));

        Color old = debugStyle.normal.textColor;
        debugStyle.normal.textColor = intentColor;
        GUILayout.Label("判定：" + intentText, debugStyle);
        debugStyle.normal.textColor = old;

        GUILayout.Label("命中对象：" + lastHitName, debugStyle);
        GUILayout.Label("所属层　：" + lastHitLayer, debugStyle);
        GUILayout.Label($"命中距离：{lastHitDistance:F2} m", debugStyle);

        // 坡度是本轮最要紧的一个数：它同时决定"哪儿挡得住"和"哪儿上得去"。
        // 站在不同的坡上点一点，把这个读数记下来，就是在给 maxWalkableSlope 找依据。
        debugStyle.normal.textColor = (lastHitSlope > maxWalkableSlope) ? new Color(1f, 0.6f, 0.4f) : Color.white;
        GUILayout.Label($"命中处坡度：{lastHitSlope:F1}°　(阈值 {maxWalkableSlope:F0}°)", debugStyle);
        debugStyle.normal.textColor = old;

        GUILayout.Label($"与脚下高差：{lastHeightDelta:F2} m　(上限 +{maxStepUpHeight:F2} / -{maxStepDownHeight:F2})", debugStyle);

        debugStyle.normal.textColor = lastPathBlocked ? new Color(1f, 0.6f, 0.4f) : Color.white;
        GUILayout.Label($"路径：{(lastPathBlocked ? "中途受阻" : "通畅")}　想走 {lastRequestedDistance:F1} m / 实走 {lastGrantedDistance:F1} m", debugStyle);
        debugStyle.normal.textColor = old;

        GUILayout.Label($"当前速度：{currentMoveSpeed:F2} m/s　地面高度：{(hasGround ? currentGroundY.ToString("F2") : "无")}", debugStyle);
        GUILayout.Label($"朝向 body {bodyYaw:F0}°　head {headYaw:F0}° / {headPitch:F0}°", debugStyle);

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