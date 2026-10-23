using UnityEngine;
using UnityEngine.InputSystem;

public class TapMoveCamera : MonoBehaviour
{
    [Header("Height")]
    public float eyeHeight = 2.5f;
    public float heightSmoothSpeed = 6f;

    [Header("Movement")]
    public float moveSpeed = 1.2f;
    public float acceleration = 2.0f;
    public float deceleration = 3.5f;
    public float stopDistance = 0.2f;

    // 用户点击新位置时，摄像机需要旋转时的速度控制
    // 点击目标后，身体/摄像机朝目标转向的速度
    public float bodyTurnSpeed = 1.2f;
    // 移动时，头部观察角度回正的速度
    public float headReturnSpeed = 4f;

    [Header("Raycast")]
    public LayerMask groundLayer = ~0;
    public float rayStartHeight = 50f;
    public float rayDistance = 200f;

    [Header("Look Around")]
    public float lookSensitivity = 0.12f;
    public float maxYawAngle = 70f;
    public float maxPitchAngle = 35f;
    public float lookResistancePower = 2f;
    public float dragThreshold = 8f;

    [Header("Debug")]
    public float currentMoveSpeed = 0f;

    private Vector3 targetPosition;
    private Vector3 lastMoveDirection = Vector3.zero;
    private bool isMoving = false;

    private float bodyYaw;
    private float headYaw;
    private float headPitch;

    private bool isPointerDown = false;
    private bool isDraggingLook = false;
    private Vector2 pointerDownPosition;
    private Vector2 lastPointerPosition;

    void Start()
    {
        targetPosition = transform.position;

        bodyYaw = transform.eulerAngles.y;
        headYaw = 0f;
        headPitch = transform.eulerAngles.x;

        UpdateHeightImmediate();
    }

    void Update()
    {
        HandleTapInput();
        MoveToTarget();
        SmoothFollowGroundHeight();
    }

    private void HandleTapInput()
    {
        Vector2? currentPosition = GetPointerPosition();
        bool pressedThisFrame = IsPointerPressedThisFrame();
        bool releasedThisFrame = IsPointerReleasedThisFrame();

        if (pressedThisFrame && currentPosition.HasValue)
        {
            isPointerDown = true;
            isDraggingLook = false;
            pointerDownPosition = currentPosition.Value;
            lastPointerPosition = currentPosition.Value;
        }

        if (isPointerDown && currentPosition.HasValue)
        {
            Vector2 deltaFromStart = currentPosition.Value - pointerDownPosition;

            if (!isDraggingLook && deltaFromStart.magnitude > dragThreshold)
            {
                isDraggingLook = true;

                // 用户开始拖动观察时，取消目标移动，但不立刻清零速度。
                // 摄像机会按 deceleration 参数自然减速停止。
                if (isMoving)
                {
                    isMoving = false;
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

        if (releasedThisFrame && isPointerDown)
        {
            if (isDraggingLook)
            {
                // 一次拖动观察结束后，把当前实际朝向吸收到 bodyYaw。
                // 这样下一次拖动会从当前视角重新开始，而不是继续受上一次 headYaw 极限限制。
                bodyYaw = transform.eulerAngles.y;
                headYaw = 0f;
                ApplyCameraRotation();
            }
            else
            {
                TrySetTarget(pointerDownPosition);
            }
                isPointerDown = false;
                isDraggingLook = false;
        }
    }

    private void TrySetTarget(Vector2 screenPosition)
    {
        Ray ray = Camera.main.ScreenPointToRay(screenPosition);

        if (Physics.Raycast(ray, out RaycastHit hit, rayDistance, groundLayer))
        {
            targetPosition = hit.point;
            targetPosition.y = transform.position.y;

            // 用户点击新目标时，把当前实际视角视为新的身体朝向起点。
            // 避免上一次拖动观察留下的 headYaw 参与到下一次转向。
            bodyYaw = transform.eulerAngles.y;
            headYaw = 0f;

            isMoving = true;
        }
    }

    private void MoveToTarget()
    {
        Vector3 current = transform.position;

        Vector3 flatCurrent = new Vector3(current.x, 0f, current.z);
        Vector3 flatTarget = new Vector3(targetPosition.x, 0f, targetPosition.z);

        Vector3 direction = flatTarget - flatCurrent;
        float distance = direction.magnitude;

        if (isMoving && distance <= stopDistance)
        {
            isMoving = false;
        }

        float desiredSpeed = isMoving ? moveSpeed : 0f;
        float speedChangeRate = desiredSpeed > currentMoveSpeed ? acceleration : deceleration;

        currentMoveSpeed = Mathf.MoveTowards(
            currentMoveSpeed,
            desiredSpeed,
            speedChangeRate * Time.deltaTime
        );

        if (currentMoveSpeed <= 0.001f)
        {
            currentMoveSpeed = 0f;
            return;
        }

        Vector3 moveDirection;

        if (isMoving && distance > 0.001f)
        {
            moveDirection = direction.normalized;
            lastMoveDirection = moveDirection;
        }
        else
        {
            moveDirection = lastMoveDirection;
        }

        if (moveDirection == Vector3.zero)
        {
            return;
        }

        float moveStep = currentMoveSpeed * Time.deltaTime;

        if (isMoving && moveStep > distance - stopDistance)
        {
            moveStep = Mathf.Max(0f, distance - stopDistance);
            isMoving = false;
        }

        transform.position = current + moveDirection * moveStep;

        if (isMoving)
        {
            Quaternion targetRotation = Quaternion.LookRotation(moveDirection, Vector3.up);
            float targetBodyYaw = targetRotation.eulerAngles.y;

            bodyYaw = Mathf.LerpAngle(bodyYaw, targetBodyYaw, bodyTurnSpeed * Time.deltaTime);

            headYaw = Mathf.Lerp(headYaw, 0f, headReturnSpeed * Time.deltaTime);
            headPitch = Mathf.Lerp(headPitch, 0f, headReturnSpeed * Time.deltaTime);

            ApplyCameraRotation();
        }
    }

    private void SmoothFollowGroundHeight()
    {
        Vector3 currentPosition = transform.position;

        Vector3 rayOrigin = new Vector3(
            currentPosition.x,
            currentPosition.y + rayStartHeight,
            currentPosition.z
        );

        if (Physics.Raycast(rayOrigin, Vector3.down, out RaycastHit hit, rayDistance, groundLayer))
        {
            float targetY = hit.point.y + eyeHeight;

            currentPosition.y = Mathf.Lerp(
                currentPosition.y,
                targetY,
                heightSmoothSpeed * Time.deltaTime
            );

            transform.position = currentPosition;
        }
    }

    private void UpdateHeightImmediate()
    {
        Vector3 currentPosition = transform.position;

        Vector3 rayOrigin = new Vector3(
            currentPosition.x,
            currentPosition.y + rayStartHeight,
            currentPosition.z
        );

        if (Physics.Raycast(rayOrigin, Vector3.down, out RaycastHit hit, rayDistance, groundLayer))
        {
            currentPosition.y = hit.point.y + eyeHeight;
            transform.position = currentPosition;
        }
    }

    private Vector2? GetPointerPosition()
    {
        if (Mouse.current != null)
        {
            return Mouse.current.position.ReadValue();
        }

        if (Touchscreen.current != null)
        {
            return Touchscreen.current.primaryTouch.position.ReadValue();
        }

        return null;
    }

    private bool IsPointerPressedThisFrame()
    {
        if (Mouse.current != null && Mouse.current.leftButton.wasPressedThisFrame)
        {
            return true;
        }

        if (Touchscreen.current != null &&
            Touchscreen.current.primaryTouch.press.wasPressedThisFrame)
        {
            return true;
        }

        return false;
    }

    private bool IsPointerReleasedThisFrame()
    {
        if (Mouse.current != null && Mouse.current.leftButton.wasReleasedThisFrame)
        {
            return true;
        }

        if (Touchscreen.current != null &&
            Touchscreen.current.primaryTouch.press.wasReleasedThisFrame)
        {
            return true;
        }

        return false;
    }

    private void ApplyLookDrag(Vector2 delta)
    {
        float yawInput = delta.x * lookSensitivity;
        float pitchInput = -delta.y * lookSensitivity;

        headYaw = ApplyLimitedRotation(headYaw, yawInput, maxYawAngle);
        headPitch = ApplyLimitedRotation(headPitch, pitchInput, maxPitchAngle);

        ApplyCameraRotation();
    }

    private float ApplyLimitedRotation(float currentAngle, float inputDelta, float limit)
    {
        float normalizedDistanceToLimit = Mathf.Abs(currentAngle) / limit;
        float resistance = Mathf.Pow(normalizedDistanceToLimit, lookResistancePower);
        float effectiveInput = inputDelta * (1f - resistance);

        float nextAngle = currentAngle + effectiveInput;
        return Mathf.Clamp(nextAngle, -limit, limit);
    }

    private void ApplyCameraRotation()
    {
        transform.rotation = Quaternion.Euler(headPitch, bodyYaw + headYaw, 0f);
    }
}