using UnityEngine;

/// <summary>
/// ============================================================================
/// 指示手 —— 第二系统的可见输出
/// ============================================================================
///
/// 【它是什么】
/// 方案A 3.3 / 方案D 1.4：手的首要职能是**因果归属**，不是消歧义。
/// 屏幕点击天然是遥控式的——我点了，它就动了，中间没有东西。手是那个中间物：
/// 让"是手碰到了它，所以它动了"这句话在画面上成立。
///
/// ⚠ 这个方案本身尚未被检验。研究者明确指出：手也可能反而破坏临场感——
///   一只半透明的手臂突然出现在自然场景里，本身就是一个人造物的侵入。
///   本轮测试要回答的正是"这个方案成不成立"，而不是"参数调得对不对"。
///   因此**参数范围开得比看起来合理的更宽**，宽到能让研究者试出
///   "再怎么调都不行"这个结论。若把范围按合理值框死，就只能在合理区间里
///   打转，永远得不出否定结论。
///
/// 【本版（V5.0）做什么、不做什么】
/// 做：
///   · 收到一个世界坐标，把手臂摆过去，食指指尖落在那个点上
///   · 出现 → 停留 → 退出，三段依次发生，三段时长各自可调
///   · 手臂的倾角由轴心几何决定：目标高则手臂立起，目标低则手臂压下
/// 不做（下一轮）：
///   · 播放动画（本版固定在接触姿势的一帧，手臂整体平移，不做任何弯曲）
///   · 手腕朝向的自动调整（目标偏左右时手掌会跟着侧过去，这一版认下）
///   · 植物形变（那是另一件事，另一个脚本）
///   · timing 的正确取值（没有形变，停顿多长无从判断——停顿存在的意义
///     就是让那个反应被看见）
///
/// 【与相机脚本的关系】
/// 相机脚本判断"这是一次触碰、位置在 X"，调 Begin(X) 就撒手不管了。
/// 本脚本自己走完四个状态、自己清理。相机不知道手内部在干什么。
///
/// 【不锁输入】
/// 方案D 1.2：触碰进行中不锁视角、不锁移动，但撤回动作必然完成。
/// 本脚本对相机的任何操作都不设限——研究者一边走一边手在半空中戳，
/// 这个画面**会**出现，而且它是问题 3 要测的东西，不是 bug。
///
/// 实现上这一条是通过"手势一经触发即冻结"做到的：Begin 那一刻算定
/// 目标点、朝向、起止位置，之后相机怎么动都不重算。好处有二：
///   (1) 撤回必然完成，字面意义上的——整段手势在触发时就已经算完了
///   (2) 相机转动不会让手臂绕着指尖甩，测试时读数干净
///
/// 【挂在哪】
/// 挂在 Hand 物体上（Camera 的子物体）。但注意本脚本直接写世界坐标，
/// 父子关系不参与定位——挂在 Camera 下只是为了场景树整齐。
/// </summary>
[DisallowMultipleComponent]
public class IndicatorHand : MonoBehaviour
{
    public const string ScriptVersion = "V5.1";

    // ========================================================================
    // 状态
    // ========================================================================

    public enum Phase
    {
        Idle,       // 闲着，不可见
        Extending,  // 伸出中
        Holding,    // 停留中（接触）
        Retracting  // 收回中
    }

    /// <summary>
    /// 当前状态。四个状态是一条单行道：Idle → Extending → Holding →
    /// Retracting → Idle，没有任何跳转或中断。
    ///
    /// 方案D 1.2"互斥是自然发生的，不是强制的"在代码里就是这个形状：
    /// 新指令进不来，不是因为有谁在挡，是因为它正忙着（见 IsBusy）。
    /// </summary>
    public Phase CurrentPhase { get; private set; } = Phase.Idle;

    public bool IsBusy => CurrentPhase != Phase.Idle;

    /// <summary>
    /// 【V5.1】上一次 Begin 被拒绝的原因。
    ///
    /// V5.0 在相机脚本那边猜了一句"它正忙"，而实际的失败原因是指尖骨没找到。
    /// 猜出来的理由比没有理由更糟——它把排查引向了错误的方向，浪费了一整轮测试。
    /// 现在由手自己说。
    /// </summary>
    public string LastRefuseReason { get; private set; } = "-";

    /// <summary>指尖骨骼是否找到。没找到时手臂无法定位。</summary>
    public bool HasFingertip => fingertip != null;

    /// <summary>是否已经执行过至少一次手势（用于显示上一次的落点偏差）。</summary>
    public bool HasGesture { get; private set; } = false;

    /// <summary>
    /// 【验收条件三的读数】接触那一刻，指尖离点击点差多少米。
    ///
    /// 理论上应当是 0（ComposeGesture 就是按"指尖落在目标上"反解的）。
    /// 不为 0 说明有别的东西在动这个 transform，或者指尖骨在手势中被动画改了位置。
    /// </summary>
    public float TipErrorMeters { get; private set; } = 0f;

    public string StateName
    {
        get
        {
            switch (CurrentPhase)
            {
                case Phase.Extending:  return "伸出中";
                case Phase.Holding:    return "停留中";
                case Phase.Retracting: return "收回中";
                default:               return "闲";
            }
        }
    }


    // ========================================================================
    // 时长（本轮先不判断取值，只保证三段依次发生）
    // ========================================================================

    [Header("时长 —— 本轮不调，下一轮（形变就位后）才判断取值")]

    [Tooltip("伸出用多久（秒）。\n\n" +
             "  ⚠ 本轮的默认值是占位数，没有任何依据。\n" +
             "  Blender 里那段动画全长 27 帧 @30fps = 0.9 秒，其中第 12–15 帧\n" +
             "  是接触停顿。那组数是在 Blender 预览窗口里做的，不是在森林场景里\n" +
             "  按感受定的，所以不作数。\n\n" +
             "  范围开到 0.05–3.0：够慢到荒谬，也够快到看不清。这是有意的——\n" +
             "  要能试出『再怎么调都不行』，范围就不能按合理值框死。")]
    [Range(0.05f, 3f)] public float extendDuration = 0.35f;

    [Tooltip("接触后停留多久（秒）。\n\n" +
             "  ⚠ 这个数在植物形变做出来之前**判断不了**。\n" +
             "  停顿存在的意义就是让世界的反应被看见；没有反应，停多久都是空的，\n" +
             "  只能凭空猜一个数。本轮只看它有没有发生，不看它多长合适。")]
    [Range(0f, 3f)] public float holdDuration = 0.25f;

    [Tooltip("收回用多久（秒）。\n\n" +
             "  一般略慢于伸出——现实里伸手是有目的的（快），收手是松弛的（慢）。\n" +
             "  但这只是常识推测，不是依据，等实测。")]
    [Range(0.05f, 3f)] public float retractDuration = 0.45f;

    [Tooltip("用缓入缓出曲线，还是匀速。\n\n" +
             "  方案D 里已经三次遇到同一件事：V1 身体转向、V3 头部转动、V4 回正漂移，\n" +
             "  三次抱怨措辞都不同，三次病因都是**曲线不对，不是速度不对**。\n" +
             "  这条已升为通则：听到『这个动作不像人做的』，先查曲线，别先动速度。\n\n" +
             "  留一个匀速选项只为 A/B 对照——不对照就不知道曲线到底有没有起作用。")]
    public bool useEasing = true;


    // ========================================================================
    // 轴心几何
    // ========================================================================

    [Header("轴心 —— 决定手臂的倾角")]

    [Tooltip("轴心相对相机的偏移（米，相机局部坐标：X 右、Y 上、Z 前）。\n\n" +
             "  研究者给的方案：轴心大致在肩与肘之间（上臂中点），手臂绕它转。\n" +
             "  这比『手臂直直指向目标』真实得多——后者看起来像一根棍子。\n\n" +
             "  默认值按真人推算（眼高 1.7 m ≈ 身高 1.82 m）：\n" +
             "    肩：眼下 0.215、右侧 0.235\n" +
             "    上臂长 ≈ 0.34，自然下垂时中点在肩下约 0.17\n" +
             "    → 眼下约 0.385、右侧 0.235、前方 0（略微靠前给 0.05）\n\n" +
             "  ※ 轴心只决定**朝向**，不决定位置。见 ComposeGesture 里的说明。\n" +
             "  ※ 这三个数的判据是好不好看，不是算得对不对。默认值只是起点。")]
    public Vector3 pivotOffset = new Vector3(0.235f, -0.385f, 0.05f);

    [Tooltip("手臂进画面的行程（米）。\n\n" +
             "  起点 = 接触位置沿手臂自身轴线往回退这么远。\n" +
             "  沿自身轴线退，意味着手臂是『从肩那边伸出来』的，不是从旁边平移进来。\n\n" +
             "  0.6 m 大致等于手臂完全缩回到身侧。太小则手像是凭空出现在半空中；\n" +
             "  太大则起点跑到相机后面去，前几帧看不见（未必是坏事，等实测）。")]
    [Range(0.1f, 1.5f)] public float entryDistance = 0.6f;


    // ========================================================================
    // 姿势
    // ========================================================================

    [Header("姿势 —— 本版不播动画，固定在接触那一帧")]

    [Tooltip("接触姿势所在的动画片段。可留空。\n\n" +
             "  留空则用模型导入时的姿势（多半是第 1 帧，手指是弯的）。\n" +
             "  手指弯着不影响本轮的四条验收，只是『指尖落点对不对』看起来\n" +
             "  没那么直观。想看清楚就把 FBX 里的那个 Clip 拖进来。\n\n" +
             "  ⚠ 本版**不播放**这个片段，只在它上面取一帧当静态姿势。\n" +
             "  把整段动画当成一串姿势而非一段影片，是下一轮的事——\n" +
             "  那时伸出/停留/收回的节奏由上面三个参数指定，而不是由\n" +
             "  Blender 里烘死的 27 帧决定。")]
    public AnimationClip poseClip;

    [Tooltip("取哪一帧当接触姿势（0=片段开头，1=结尾）。\n\n" +
             "  Blender 里第 12–15 帧是接触停顿，取中间的第 13 帧：\n" +
             "    (13 - 1) / (27 - 1) ≈ 0.46")]
    [Range(0f, 1f)] public float poseNormalizedTime = 0.46f;


    // ========================================================================
    // 指尖
    // ========================================================================

    [Header("指尖")]

    [Tooltip("食指接触点。留空则按名字自动找 MCH_Index_Contact。\n\n" +
             "  这根骨在 Blender 那套 rig 里的用途就是『标记食指接触位置』，\n" +
             "  正好是本脚本需要的锚点。\n\n" +
             "  ※ 将来植物形变要读的手部坐标也是这一根——一根骨同时解决\n" +
             "    寻址锚点和形变场源两件事。")]
    public Transform fingertip;

    [Tooltip("自动查找时用的骨骼名。")]
    public string fingertipBoneName = "MCH_Index_Contact";

    [Tooltip("【V5.1】找不到指尖骨时的备用偏移（根物体局部坐标，米）。\n\n" +
             "  V5.0 在找不到骨的时候直接拒绝执行，结果是手完全不出现，\n" +
             "  而本轮四条验收里有三条只要手出现就能测。宁可落点不准也要让它出来——\n" +
             "  『诚实的不准』比『什么都没有』信息量大得多。\n\n" +
             "  默认 (0, 0, 0.515)：模型探出方向是 +Z，小臂断口到食指指尖实测 51.5 cm。")]
    public Vector3 fallbackTipLocalOffset = new Vector3(0f, 0f, 0.515f);


    // ========================================================================
    // 显隐
    // ========================================================================

    [Header("显隐")]

    [Tooltip("闲置时是否自动隐藏。\n\n" +
             "  方案A 3.3：手是短暂的，不常驻。关掉这个开关可以让手一直显示，\n" +
             "  方便在编辑器里对位，但那不是运行时该有的样子。")]
    public bool hideWhenIdle = true;


    // ========================================================================
    // 内部
    // ========================================================================

    private Renderer[] renderers;

    // 手势一经触发即冻结的量（见类注释"不锁输入"那一段）
    private Vector3    contactPosition;   // 接触时刻的世界位置（根物体的）
    private Vector3    startPosition;     // 起点世界位置
    private Quaternion gestureRotation;   // 整段手势共用的朝向
    private Vector3    targetPoint;       // 被点中的那个世界点（调试用）

    private float phaseTimer = 0f;


    // ========================================================================
    // 生命周期
    // ========================================================================

    private bool initialized = false;

    private void Awake()
    {
        EnsureInit();
    }

    /// <summary>
    /// 【V5.1 修复】初始化改成懒执行，不再依赖 Awake。
    ///
    /// V5.0 的 bug 就出在这里，而且是我给的操作说明和我写的代码互相矛盾：
    ///   · 我让研究者"把 Hand 物体先关掉（Inspector 最上面那个勾去掉）"
    ///   · 但代码的隐藏只切 Renderer.enabled，从来不去开关 GameObject
    /// 物体一旦被关掉，Awake 永远不执行 → fingertip 永远是 null →
    /// Begin() 在第二行就 return false → 相机那边把它显示成"手正忙"。
    ///
    /// 于是研究者看到的是：手明明是"闲"，却报"正忙"，而且满场找不到那只
    /// 正在忙的手。整整一轮测试耗在这上面。
    ///
    /// 现在：初始化随时可执行，Begin 时若物体是关的就自己打开。
    /// 两种摆法（物体常开只切 Renderer / 物体默认关闭）都能跑。
    /// </summary>
    private void EnsureInit()
    {
        if (initialized) return;
        initialized = true;

        renderers = GetComponentsInChildren<Renderer>(true);

        if (fingertip == null)
        {
            fingertip = FindDeep(transform, fingertipBoneName);
        }

        if (fingertip == null)
        {
            Debug.LogWarning(
                $"[IndicatorHand] 找不到指尖骨骼「{fingertipBoneName}」，改用备用偏移 {fallbackTipLocalOffset}。\n" +
                "手仍会出现，但落点会不准。请检查：\n" +
                "  (1) FBX 导出时这根骨有没有被过滤掉——它可能没有蒙皮权重，\n" +
                "      有些导出设置会把这类纯技术骨剔除；\n" +
                "  (2) 名字有没有对上，或者直接把它拖到 Inspector 的 fingertip 槽里。",
                this);
        }

        ApplyPose();
        SetVisible(!hideWhenIdle);
    }


    /// <summary>
    /// 把手臂固定在接触姿势。本版只在启动时做一次——手臂在整段手势里
    /// 是刚性的，只平移和旋转，不做任何弯曲。
    /// </summary>
    private void ApplyPose()
    {
        if (poseClip == null) return;

        // SampleAnimation 不需要 Animator，编辑器和运行时都能用。
        poseClip.SampleAnimation(gameObject, poseNormalizedTime * poseClip.length);
    }


    // ========================================================================
    // 对外：接受一次触碰指令
    // ========================================================================

    /// <summary>
    /// 去碰 worldPoint。返回是否受理。
    ///
    /// ※ 手正忙时返回 false 而不是打断当前动作。方案D 1.2：手一定会把
    ///   收回动作做完。中途改道会让"撤回必然完成"这条失效。
    /// </summary>
    public bool Begin(Vector3 worldPoint, Transform cameraTransform)
    {
        EnsureInit();

        if (IsBusy)
        {
            LastRefuseReason = $"手正忙（{StateName}），收回动作还没做完";
            return false;
        }

        if (cameraTransform == null) cameraTransform = transform.parent;
        if (cameraTransform == null)
        {
            LastRefuseReason = "拿不到相机（Hand 不是 Camera 的子物体，调用也没传相机）";
            return false;
        }

        // 【V5.1】物体被关掉时自己打开。见 EnsureInit 里那段说明。
        if (!gameObject.activeSelf) gameObject.SetActive(true);

        ComposeGesture(worldPoint, cameraTransform);

        targetPoint  = worldPoint;
        CurrentPhase = Phase.Extending;
        phaseTimer   = 0f;
        HasGesture   = true;

        LastRefuseReason = "-";

        SetVisible(true);
        ApplyAt(0f);
        return true;
    }


    /// <summary>
    /// 算定整段手势：朝向、接触位置、起点。一次算完，之后不重算。
    ///
    /// ────────────────────────────────────────────────────────────────
    /// 【这里有一个必须说清的取舍】
    ///
    /// 理想情况是：手臂绕轴心转动，指尖正好落在目标上。但这要求
    ///   轴心到指尖的距离 == 轴心到目标的距离
    /// 而前者是模型定死的（从轴心到指尖约 0.5 m 出头），后者每次都不一样
    /// （目标高一点低一点、近一点远一点）。两者不可能永远相等。
    ///
    /// 二者只能取一个：
    ///   (a) 轴心严格不动 → 指尖落不准
    ///   (b) 指尖严格落准 → 手臂沿自身轴线滑动，轴心不严格在 pivotOffset 上
    ///
    /// 本版取 (b)。理由：本轮的验收条件之一就是"食指落点与点击点基本吻合"，
    /// 而轴心那一段在画面外（手臂断口在相机前约 0.3 m、眼下 0.26 m，
    /// 画面下缘在 0.30 m 处对应眼下 0.14 m，所以断口在画面外），
    /// 它滑一点没人看得见。
    ///
    /// 于是轴心退化成一个**纯朝向参考**：它只回答"手臂该以什么倾角伸过去"，
    /// 不回答"手臂根部在哪"。研究者要的效果照样成立——目标高则轴心到目标的
    /// 连线向上，手臂立起来；目标低则连线向下，手臂压下去。
    /// ────────────────────────────────────────────────────────────────
    /// </summary>
    private void ComposeGesture(Vector3 worldPoint, Transform cam)
    {
        // 1. 轴心（世界）
        Vector3 pivot = cam.TransformPoint(pivotOffset);

        // 2. 朝向：轴心 → 目标。倾角就是从这条线来的。
        Vector3 dir = worldPoint - pivot;
        if (dir.sqrMagnitude < 1e-6f) dir = cam.forward;
        dir.Normalize();

        // 模型的探出方向是 Unity +Z（Blender -Y 转过来的），上方是 +Y。
        // 所以把 +Z 对齐 dir 即可。
        //
        // 上方参考用世界 Vector3.up 而不是相机的 up：相机会俯仰，
        // 用它会让手臂跟着镜头滚，那是本版不想引入的变量。
        // 目标接近正上/正下方时 LookRotation 会退化，用相机 up 兜底。
        Vector3 upRef = (Mathf.Abs(Vector3.Dot(dir, Vector3.up)) > 0.99f)
            ? cam.up
            : Vector3.up;

        gestureRotation = Quaternion.LookRotation(dir, upRef);

        // 3. 接触位置：让指尖正好落在目标上。
        //
        //    指尖在根物体局部坐标里的位置：
        //    【V5.1】找不到指尖骨时退回备用偏移，让手照样出得来（落点不准，
        //    但调试面板会把"指尖骨丢失"标红，不会让人误以为落点是对的）。
        Vector3 localTip = (fingertip != null)
            ? transform.InverseTransformPoint(fingertip.position)
            : fallbackTipLocalOffset;
        //    旋转后指尖相对根物体的世界偏移：
        Vector3 tipOffset = gestureRotation * localTip;
        //    于是根物体该在：
        contactPosition = worldPoint - tipOffset;

        // 4. 起点：沿手臂自身轴线往回退。
        //    退的是 dir 的反方向，所以手臂看起来是"从肩那边伸出来"的，
        //    不是从画面旁边平移进来。
        startPosition = contactPosition - dir * entryDistance;
    }


    // ========================================================================
    // 每帧推进
    // ========================================================================

    private void Update()
    {
        if (CurrentPhase == Phase.Idle) return;

        phaseTimer += Time.deltaTime;

        switch (CurrentPhase)
        {
            case Phase.Extending:
            {
                float d = Mathf.Max(0.0001f, extendDuration);
                float t = Mathf.Clamp01(phaseTimer / d);
                ApplyAt(t);
                if (t >= 1f) EnterPhase(Phase.Holding);
                break;
            }

            case Phase.Holding:
            {
                ApplyAt(1f);

                // 【V5.1】验收条件三的读数：接触时指尖离点击点差多少。
                if (fingertip != null)
                    TipErrorMeters = Vector3.Distance(fingertip.position, targetPoint);

                if (phaseTimer >= holdDuration) EnterPhase(Phase.Retracting);
                break;
            }

            case Phase.Retracting:
            {
                float d = Mathf.Max(0.0001f, retractDuration);
                float t = Mathf.Clamp01(phaseTimer / d);
                ApplyAt(1f - t);
                if (t >= 1f) EnterPhase(Phase.Idle);
                break;
            }
        }
    }


    private void EnterPhase(Phase next)
    {
        CurrentPhase = next;
        phaseTimer = 0f;

        if (next == Phase.Idle)
        {
            SetVisible(!hideWhenIdle);
        }
    }


    /// <summary>t: 0 = 起点（缩回），1 = 接触。</summary>
    private void ApplyAt(float t)
    {
        float k = useEasing ? Mathf.SmoothStep(0f, 1f, t) : t;

        transform.SetPositionAndRotation(
            Vector3.Lerp(startPosition, contactPosition, k),
            gestureRotation);
    }


    private void SetVisible(bool on)
    {
        if (renderers == null) return;
        for (int i = 0; i < renderers.Length; i++)
        {
            if (renderers[i] != null) renderers[i].enabled = on;
        }
    }


    // ========================================================================
    // 工具
    // ========================================================================

    private static Transform FindDeep(Transform root, string name)
    {
        if (root.name == name) return root;
        for (int i = 0; i < root.childCount; i++)
        {
            Transform found = FindDeep(root.GetChild(i), name);
            if (found != null) return found;
        }
        return null;
    }


    // ========================================================================
    // 场景视图辅助线
    //
    // 只在编辑器里画，不影响真机。用途是对位时能看见轴心到底在哪——
    // 那三个偏移量光看数字调不出来。
    // ========================================================================

    private void OnDrawGizmosSelected()
    {
        Transform cam = transform.parent;
        if (cam == null) return;

        Vector3 pivot = cam.TransformPoint(pivotOffset);

        Gizmos.color = new Color(1f, 0.6f, 0.1f);
        Gizmos.DrawWireSphere(pivot, 0.04f);

        if (IsBusy)
        {
            Gizmos.color = Color.green;
            Gizmos.DrawLine(pivot, targetPoint);
            Gizmos.DrawWireSphere(targetPoint, 0.03f);

            Gizmos.color = new Color(0.4f, 0.7f, 1f);
            Gizmos.DrawLine(startPosition, contactPosition);
        }

        if (fingertip != null)
        {
            Gizmos.color = Color.red;
            Gizmos.DrawWireSphere(fingertip.position, 0.015f);
        }
    }
}