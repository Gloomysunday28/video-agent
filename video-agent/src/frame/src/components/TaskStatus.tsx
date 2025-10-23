// 内联声明，避免对 hooks/useSSE 的类型依赖
type TaskStatus = {
  task_id: string
  status: 'pending' | 'processing' | 'completed' | 'failed'
  message: string
  progress?: number
  timestamp?: string
  type?: string
}

interface TaskStatusProps {
  status: TaskStatus
  onDismiss?: () => void
}

export function TaskStatusComponent({ status, onDismiss }: TaskStatusProps) {
  const getStatusIcon = () => {
    switch (status.status) {
      case 'pending':
        return '⏳'
      case 'processing':
        return '⚙️'
      case 'completed':
        return '✅'
      case 'failed':
        return '❌'
      default:
        return '📋'
    }
  }

  const getStatusColor = () => {
    switch (status.status) {
      case 'pending':
        return '#f59e0b' // 黄色
      case 'processing':
        return '#3b82f6' // 蓝色
      case 'completed':
        return '#10b981' // 绿色
      case 'failed':
        return '#ef4444' // 红色
      default:
        return '#6b7280' // 灰色
    }
  }

  const getProgressBar = () => {
    if (status.type === 'task_progress' && typeof status.progress === 'number') {
      return (
        <div className="progress-bar">
          <div 
            className="progress-fill" 
            style={{ width: `${Math.min(100, Math.max(0, status.progress))}%` }}
          />
        </div>
      )
    }
    return null
  }

  return (
    <div className="task-status" style={{ borderLeftColor: getStatusColor() }}>
      <div className="task-status-header">
        <div className="task-status-icon">
          {getStatusIcon()}
        </div>
        <div className="task-status-content">
          <div className="task-status-message">
            {status.message}
          </div>
        </div>
        <div className="task-status-actions">
          {status.type === 'task_progress' && status.progress !== undefined && (
            <span className="task-progress">
              {Math.round(status.progress)}%
            </span>
          )}
          {onDismiss && (
            <button 
              className="task-status-dismiss"
              onClick={onDismiss}
              title="关闭"
            >
              ✕
            </button>
          )}
        </div>
      </div>
      
      {getProgressBar()}
    </div>
  )
}

// 任务状态列表组件
interface TaskStatusListProps {
  statuses: TaskStatus[]
  onDismissStatus?: (taskId: string) => void
}

export function TaskStatusList({ statuses, onDismissStatus }: TaskStatusListProps) {
  if (statuses.length === 0) {
    return null
  }

  return (
    <div className="task-status-list">
      {statuses.map((status, index) => (
        <TaskStatusComponent
          key={`${status.task_id}-${index}`}
          status={status}
          onDismiss={status.task_id ? () => onDismissStatus?.(status.task_id!) : undefined}
        />
      ))}
    </div>
  )
}

// 实时状态显示组件
interface RealtimeStatusProps {
  currentStatus?: TaskStatus
  isConnected: boolean
  connectionId?: string
}

export function RealtimeStatus({ currentStatus, isConnected }: RealtimeStatusProps) {
  // 如果连接正常且没有活跃任务，不显示状态栏
  if (isConnected && !currentStatus) {
    return null
  }

  // 只对失败的连接显示状态栏
  if (!isConnected) {
    return (
      <div className="websocket-status-bar disconnected">
        <div className="status-content">
          <span className="status-icon">🔌</span>
          <span className="status-text">连接已断开</span>
        </div>
      </div>
    )
  }

  // 如果没有当前任务，不显示状态栏
  if (!currentStatus) {
    return null
  }

  // 如果有任务状态，显示任务状态
  if (currentStatus) {
    const isCompleted = currentStatus.status === 'completed'
    const isFailed = currentStatus.status === 'failed'
    const isActive = currentStatus.status === 'pending' || currentStatus.status === 'processing'
    
    return (
      <div className={`realtime-status ${isActive ? 'active' : isCompleted ? 'completed' : isFailed ? 'failed' : ''}`}>
        <div className="current-task">
          <span className="task-icon">
            {currentStatus.status === 'pending' ? '⏳' :
             currentStatus.status === 'processing' ? '⚙️' :
             currentStatus.status === 'completed' ? '✅' :
             currentStatus.status === 'failed' ? '❌' : '📋'}
          </span>
          <span className="task-message">{currentStatus.message}</span>
          {currentStatus.type === 'task_progress' && currentStatus.progress !== undefined && (
            <span className="task-progress">
              {Math.round(currentStatus.progress)}%
            </span>
          )}
        </div>
      </div>
    )
  }

  // 只有在连接断开时才显示错误状态
  if (!isConnected) {
    return (
      <div className="realtime-status disconnected">
        <span className="status-icon">⚠️</span>
        <span className="status-text">连接中断，正在重连...</span>
      </div>
    )
  }

  return null
}
