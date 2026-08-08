// Dashboard JavaScript functionality with Kanban board

// Global state
let currentFilter = 'all';
let usersList = [];
let allTasks = [];

// Initialize dashboard
document.addEventListener('DOMContentLoaded', () => {
    loadDashboardData();
    loadUsers();
    setupEventListeners();
    syncRecurringOption();
    startAutoRefresh();
});

// Load all dashboard data
async function loadDashboardData() {
    await Promise.all([
        loadSummary(),
        loadTasks()
    ]);
    updateTime();
}

// Load summary statistics
async function loadSummary() {
    try {
        const response = await fetch('/api/dashboard/summary');
        const data = await response.json();

        if (data.summary) {
            document.getElementById('totalTasks').textContent = data.summary.total;
            document.getElementById('completedTasks').textContent = data.summary.completed;
            document.getElementById('pendingTasks').textContent = data.summary.pending;
            document.getElementById('overdueTasks').textContent = data.summary.overdue;
        }
    } catch (error) {
        console.error('Failed to load summary:', error);
    }
}

// Load tasks
async function loadTasks() {
    const endpoint = currentFilter === 'my' ? '/api/dashboard/my-tasks' :
                     currentFilter === 'overdue' ? '/api/dashboard/overdue' :
                     '/api/tasks';

    try {
        const response = await fetch(endpoint);
        const data = await response.json();

        if (data.tasks) {
            allTasks = data.tasks;
            renderKanbanBoard();
        }
    } catch (error) {
        console.error('Failed to load tasks:', error);
    }
}

// Render Kanban board
function renderKanbanBoard() {
    console.log('Rendering Kanban board with', allTasks.length, 'tasks');

    const columns = [
        { id: 'adhoc', categories: ['adhoc'] },
        { id: 'daily', categories: ['daily'] },
        { id: 'weekly', categories: ['weekly'] },
        { id: 'monthly', categories: ['monthly'] },
        { id: 'long-term', categories: ['quarterly', 'yearly'] }
    ];

    columns.forEach(({ id, categories }) => {
        const column = document.getElementById(`column-${id}`);
        const count = document.getElementById(`count-${id}`);

        if (!column) {
            console.error('Column not found:', id);
            return;
        }

        // Filter out completed tasks
        const categoryTasks = allTasks.filter(task => categories.includes(task.category) && task.status !== 'completed');
        console.log('Column', id, ':', categoryTasks.length, 'tasks (excluding completed)');

        // Update count
        count.textContent = categoryTasks.length;

        // Render cards
        if (categoryTasks.length === 0) {
            column.innerHTML = '<p class="no-tasks">No tasks</p>';
        } else {
            column.innerHTML = categoryTasks.map(task => createKanbanCard(task)).join('');
        }
    });
}

// Create Kanban card HTML
function createKanbanCard(task) {
    const priorityEmoji = {
        low: '🟢',
        medium: '🟡',
        high: '🟠',
        critical: '🔴'
    };

    const statusClass = task.status === 'completed' ? 'completed' : '';
    const overdueClass = task.is_overdue ? 'overdue' : '';

    return `
        <div class="kanban-card ${statusClass} ${overdueClass}" data-id="${task.id}" onclick="openTaskDetail(${task.id})">
            <div class="kanban-card-header">
                <div class="kanban-card-title">${escapeHtml(task.title)}</div>
                <span title="${task.priority}">${priorityEmoji[task.priority] || '⚪'}</span>
            </div>
            <div class="kanban-card-meta">
                <span class="badge badge-${task.status}">${task.status.replace('_', ' ')}</span>
                ${task.is_overdue ? '<span class="badge badge-overdue">Overdue</span>' : ''}
            </div>
            ${task.description ? `<p class="kanban-card-description">${escapeHtml(task.description.substring(0, 80))}${task.description.length > 80 ? '...' : ''}</p>` : ''}
            <div class="kanban-card-footer">
                <span>Due: ${formatDate(task.due_date)}</span>
                <span>${task.assignee ? task.assignee.username : 'Unassigned'}</span>
            </div>
        </div>
    `;
}

// Load users for assignment dropdown
async function loadUsers() {
    if (!window.currentUser || (window.currentUser.role !== 'editor' && window.currentUser.role !== 'admin')) {
        return [];
    }

    try {
        let response = await fetch('/api/users/assignable');

        // Fallback for older backends where the new endpoint is not available yet.
        if (!response.ok && window.currentUser.role === 'admin') {
            response = await fetch('/api/users');
        }

        if (!response.ok) {
            throw new Error(`Failed to load assignees (${response.status})`);
        }

        const data = await response.json();

        if (data.users) {
            usersList = data.users;
            if (window.currentUser && (window.currentUser.role === 'editor' || window.currentUser.role === 'admin')) {
                populateAssigneeDropdown();
                console.log('Users loaded for dashboard:', usersList.length);
            }
        }

        return usersList;
    } catch (error) {
        console.error('Failed to load users:', error);
        showNotification('Failed to load assignees', 'error');
        return [];
    }
}

// Populate assignee dropdown
function populateAssigneeDropdown() {
    const select = document.getElementById('taskAssignee');
    if (!select) return;

    select.innerHTML = '<option value="">Unassigned</option>' +
        usersList.map(user =>
            `<option value="${user.id}">${escapeHtml(user.username)}</option>`
        ).join('');
}

// Populate assignee dropdown (call this after modal opens)
function populateAssigneeDropdownInModal() {
    const select = document.getElementById('taskAssignee');
    if (!select) return;

    const currentValue = select.value;
    select.innerHTML = '<option value="">Unassigned</option>' +
        usersList.map(user =>
            `<option value="${user.id}">${escapeHtml(user.username)}</option>`
        ).join('');
    select.value = currentValue;
}

// Setup event listeners
function setupEventListeners() {
    // Filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentFilter = e.target.dataset.filter;
            loadTasks();
        });
    });

    // Add task button
    const addBtn = document.getElementById('addTaskBtn');
    if (addBtn) {
        addBtn.addEventListener('click', openAddTaskModal);
    }

    document.getElementById('taskCategory')?.addEventListener('change', syncRecurringOption);

    // Modal close buttons
    const modal = document.getElementById('addTaskModal');
    if (modal) {
        document.getElementById('closeModal').addEventListener('click', closeAddTaskModal);
        document.getElementById('cancelBtn').addEventListener('click', closeAddTaskModal);
        document.getElementById('addTaskForm').addEventListener('submit', handleAddTask);

        // Close on outside click
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeAddTaskModal();
        });
    }

    // Task detail modal
    const detailModal = document.getElementById('taskDetailModal');
    if (detailModal) {
        document.getElementById('closeDetailModal').addEventListener('click', closeTaskDetail);
        document.getElementById('closeDetailBtn').addEventListener('click', closeTaskDetail);
        document.getElementById('detailCompleteBtn').addEventListener('click', completeFromDetail);

        detailModal.addEventListener('click', (e) => {
            if (e.target === detailModal) closeTaskDetail();
        });
    }

    // Logout button
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }
}

// Open add task modal
async function openAddTaskModal() {
    const modal = document.getElementById('addTaskModal');
    modal.classList.add('show');

    await loadUsers();

    // Populate users dropdown
    populateAssigneeDropdown();
    syncRecurringOption();

    // Set default due date to tomorrow 9 AM
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(9, 0, 0, 0);
    const offset = tomorrow.getTimezoneOffset() * 60000;
    const localDate = new Date(tomorrow.getTime() - offset);
    document.getElementById('taskDue').value = localDate.toISOString().slice(0, 16);
}

// Close add task modal
function closeAddTaskModal() {
    const modal = document.getElementById('addTaskModal');
    modal.classList.remove('show');
    document.getElementById('addTaskForm').reset();
}

// Handle add task form submission
async function handleAddTask(e) {
    e.preventDefault();

    const dueDate = document.getElementById('taskDue').value;
    const formData = {
        title: document.getElementById('taskTitle').value,
        description: document.getElementById('taskDescription').value,
        category: document.getElementById('taskCategory').value,
        priority: document.getElementById('taskPriority').value,
        assigned_to: document.getElementById('taskAssignee').value || null,
        is_recurring: document.getElementById('taskRecurring').checked,
        due_date: dueDate ? new Date(dueDate).toISOString() : null
    };

    try {
        const response = await fetch('/api/tasks', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Task created successfully!', 'success');
            closeAddTaskModal();
            loadDashboardData();
        } else {
            showNotification(result.error || 'Failed to create task', 'error');
        }
    } catch (error) {
        showNotification('Failed to create task', 'error');
    }
}

// Open task detail
window.openTaskDetail = async function(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}`);
        const task = await response.json();

        document.getElementById('taskDetailTitle').textContent = task.title;

        const priorityEmoji = {
            low: '🟢 Low',
            medium: '🟡 Medium',
            high: '🟠 High',
            critical: '🔴 Critical'
        };

        document.getElementById('taskDetailContent').innerHTML = `
            <div class="task-detail-row">
                <strong>Status:</strong>
                <span class="status status-${task.status}">${task.status.replace('_', ' ')}</span>
            </div>
            <div class="task-detail-row">
                <strong>Priority:</strong> ${priorityEmoji[task.priority]}
            </div>
            <div class="task-detail-row">
                <strong>Category:</strong> ${task.category}
            </div>
            <div class="task-detail-row">
                <strong>Due Date:</strong> ${formatDate(task.due_date)}
            </div>
            <div class="task-detail-row">
                <strong>Assigned To:</strong> ${task.assignee ? task.assignee.username : 'Unassigned'}
            </div>
            <div class="task-detail-row">
                <strong>Created By:</strong> ${task.creator ? task.creator.username : 'Unknown'}
            </div>
            ${task.description ? `<div class="task-detail-row"><strong>Description:</strong><p>${escapeHtml(task.description)}</p></div>` : ''}
        `;

        // Update complete button
        const completeBtn = document.getElementById('detailCompleteBtn');
        if (task.status === 'completed') {
            completeBtn.style.display = 'none';
        } else {
            completeBtn.style.display = 'inline-block';
            completeBtn.dataset.taskId = taskId;
        }

        document.getElementById('taskDetailModal').classList.add('show');
    } catch (error) {
        showNotification('Failed to load task details', 'error');
    }
};

function closeTaskDetail() {
    document.getElementById('taskDetailModal').classList.remove('show');
}

// Complete task from detail modal
async function completeFromDetail() {
    const btn = document.getElementById('detailCompleteBtn');
    const taskId = btn.dataset.taskId;

    if (!taskId) return;

    try {
        const response = await fetch(`/api/tasks/${taskId}/complete`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Task completed!', 'success');
            closeTaskDetail();
            loadDashboardData();
        } else {
            showNotification(result.error || 'Failed to complete task', 'error');
        }
    } catch (error) {
        showNotification('Failed to complete task', 'error');
    }
}

// Complete task (for backward compatibility)
window.completeTask = async function(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/complete`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Task completed!', 'success');
            loadDashboardData();
        } else {
            showNotification(result.error || 'Failed to complete task', 'error');
        }
    } catch (error) {
        showNotification('Failed to complete task', 'error');
    }
};

// Logout handler
async function handleLogout() {
    try {
        await fetch('/api/auth/logout', { method: 'POST' });
        window.location.href = '/login';
    } catch (error) {
        window.location.href = '/login';
    }
}

// Auto refresh every 30 seconds
function startAutoRefresh() {
    setInterval(loadDashboardData, 30000);
    updateTime();
    setInterval(updateTime, 1000);
}

// Update current time display
function updateTime() {
    const timeEl = document.getElementById('currentTime');
    if (timeEl) {
        const now = new Date();
        timeEl.textContent = `${formatDatePart(now)} ${formatTimePart(now)}`;
    }
}

// Show notification
function showNotification(message, type = 'info') {
    const container = document.getElementById('notification-container');
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    container.appendChild(notification);

    setTimeout(() => notification.remove(), 5000);
}

// Utility functions
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function formatDate(dateString) {
    if (!dateString) return 'No due date';
    const date = new Date(dateString);
    const now = new Date();
    const diff = date - now;
    const days = calendarDayDifference(date, now);

    const timeStr = formatTimePart(date);
    const dateStr = formatDatePart(date);

    if (days < 0) {
        const hoursOverdue = Math.abs(Math.floor(diff / (1000 * 60 * 60)));
        if (hoursOverdue < 24) return `${hoursOverdue}h overdue (${dateStr} ${timeStr})`;
        return `${Math.abs(days)}d overdue (${dateStr} ${timeStr})`;
    }
    if (days === 0) return `<span class="text-danger">Today ${timeStr}</span>`;
    if (days === 1) return `<span class="text-warning">Tomorrow ${timeStr}</span>`;
    if (days < 7) return `In ${days}d (${dateStr} ${timeStr})`;
    return `${dateStr} ${timeStr}`;
}

function formatDatePart(date) {
    return date.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        timeZone: 'Asia/Bangkok'
    });
}

function formatTimePart(date) {
    return date.toLocaleTimeString('en-GB', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        timeZone: 'Asia/Bangkok'
    });
}

function calendarDayDifference(date, reference) {
    const parts = value => {
        const result = new Intl.DateTimeFormat('en-GB', {
            timeZone: 'Asia/Bangkok',
            year: 'numeric',
            month: '2-digit',
            day: '2-digit'
        }).formatToParts(value);
        return Date.UTC(
            Number(result.find(part => part.type === 'year').value),
            Number(result.find(part => part.type === 'month').value) - 1,
            Number(result.find(part => part.type === 'day').value)
        );
    };

    return Math.round((parts(date) - parts(reference)) / (1000 * 60 * 60 * 24));
}

function syncRecurringOption() {
    const category = document.getElementById('taskCategory');
    const recurring = document.getElementById('taskRecurring');
    if (!category || !recurring) return;

    const supported = ['daily', 'weekly', 'monthly'].includes(category.value);
    recurring.disabled = !supported;
    if (!supported) {
        recurring.checked = false;
    }
}
