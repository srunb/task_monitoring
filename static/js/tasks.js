// Tasks page JavaScript functionality

// Global state
let usersList = [];
let taskToDelete = null;

// Initialize tasks page
document.addEventListener('DOMContentLoaded', () => {
    console.log('Tasks page initializing...');
    setupEventListeners();
    loadTasks();
    loadUsers();
    startAutoRefresh();
    console.log('Tasks page initialized');
});

// Load tasks with current filters
async function loadTasks() {
    const categoryEl = document.getElementById('categoryFilter');
    const statusEl = document.getElementById('statusFilter');
    const searchEl = document.getElementById('searchInput');

    const category = categoryEl?.value || '';
    const status = statusEl?.value || '';
    const search = searchEl?.value || '';

    let url = '/api/tasks?';
    if (category) url += `category=${category}&`;
    if (status) url += `status=${status}&`;

    console.log('Loading tasks from:', url);

    try {
        const response = await fetch(url);
        console.log('Response status:', response.status);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        let data = await response.json();
        console.log('Response data:', data);

        if (data.tasks) {
            // Filter by search term
            if (search) {
                data.tasks = data.tasks.filter(task =>
                    (task.title && task.title.toLowerCase().includes(search.toLowerCase())) ||
                    (task.description && task.description.toLowerCase().includes(search.toLowerCase()))
                );
            }

            console.log('Rendering', data.tasks.length, 'tasks');
            renderTasksTable(data.tasks);
        } else {
            console.error('No tasks in response:', data);
            showNotification('No tasks data in response', 'error');
        }
    } catch (error) {
        console.error('Failed to load tasks:', error);
        showNotification('Failed to load tasks: ' + error.message, 'error');
    }
}

// Render tasks table
function renderTasksTable(tasks) {
    const tbody = document.getElementById('tasksTableBody');
    if (!tbody) {
        console.error('tasksTableBody not found');
        return;
    }

    if (tasks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="no-tasks">No tasks found</td></tr>';
        return;
    }

    tbody.innerHTML = tasks.map(task => {
        const safeTitle = (task.title || '').replace(/'/g, "\\'").replace(/"/g, '\\"');
        return `
        <tr>
            <td>
                <div class="task-cell-title">${task.title ? escapeHtml(task.title) : 'No title'}</div>
                ${task.description ? `<div class="task-cell-desc">${escapeHtml(task.description.substring(0, 50))}${task.description.length > 50 ? '...' : ''}</div>` : ''}
            </td>
            <td><span class="badge badge-${task.category}">${task.category || 'N/A'}</span></td>
            <td><span class="badge badge-${task.priority}">${task.priority || 'N/A'}</span></td>
            <td><span class="status status-${task.status}">${(task.status || 'pending').replace('_', ' ')}</span></td>
            <td>${task.assignee ? task.assignee.username : 'Unassigned'}</td>
            <td>${formatDateTime(task.due_date, true, task.status)}</td>
            <td>${formatCompletedDate(task.completed_at, task.due_date)}</td>
            <td class="actions">
                ${task.status !== 'completed' ? `
                    <button class="btn btn-small btn-complete" onclick="completeTask(${task.id})" title="Complete">✓</button>
                ` : '<button class="btn btn-small" disabled title="Completed">✓</button>'}
                ${window.currentUser && (window.currentUser.role === 'editor' || window.currentUser.role === 'admin') ? `
                    <button class="btn btn-small btn-edit" onclick="editTask(${task.id})" title="Edit">✎</button>
                    <button class="btn btn-small btn-delete" onclick="confirmDeleteTask(${task.id}, '${safeTitle}')" title="Delete">🗑</button>
                ` : ''}
            </td>
        </tr>
    `}).join('');
}

// Load users
async function loadUsers() {
    if (!window.currentUser || (window.currentUser.role !== 'editor' && window.currentUser.role !== 'admin')) {
        console.log('Skipping user load - not editor/admin');
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
            populateAssigneeDropdown();
            console.log('Users loaded:', usersList.length);
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

// Setup event listeners
function setupEventListeners() {
    // Filters
    const categoryFilter = document.getElementById('categoryFilter');
    const statusFilter = document.getElementById('statusFilter');
    const searchInput = document.getElementById('searchInput');

    if (categoryFilter) categoryFilter.addEventListener('change', loadTasks);
    if (statusFilter) statusFilter.addEventListener('change', loadTasks);
    if (searchInput) searchInput.addEventListener('input', debounce(loadTasks, 300));

    // Add task button
    const addBtn = document.getElementById('addTaskBtn');
    if (addBtn) {
        addBtn.addEventListener('click', () => {
            console.log('Add task button clicked');
            openTaskModal();
        });
    } else {
        console.error('Add task button not found');
    }

    // Task form
    const taskForm = document.getElementById('taskForm');
    if (taskForm) {
        taskForm.addEventListener('submit', handleTaskSubmit);
        const closeModal = document.getElementById('closeModal');
        if (closeModal) closeModal.addEventListener('click', closeTaskModal);
        const cancelBtn = document.getElementById('cancelBtn');
        if (cancelBtn) cancelBtn.addEventListener('click', closeTaskModal);
    }

    // Delete modal
    const deleteModal = document.getElementById('deleteModal');
    if (deleteModal) {
        const closeDeleteButton = document.getElementById('closeDeleteModal');
        if (closeDeleteButton) closeDeleteButton.addEventListener('click', closeDeleteModal);
        const cancelDelete = document.getElementById('cancelDelete');
        if (cancelDelete) cancelDelete.addEventListener('click', closeDeleteModal);
        const confirmDelete = document.getElementById('confirmDelete');
        if (confirmDelete) confirmDelete.addEventListener('click', executeDeleteTask);
    }

    // Complete modal
    const completeModal = document.getElementById('completeModal');
    if (completeModal) {
        const closeCompleteButton = document.getElementById('closeCompleteModal');
        if (closeCompleteButton) closeCompleteButton.addEventListener('click', closeCompleteModal);
        const cancelComplete = document.getElementById('cancelComplete');
        if (cancelComplete) cancelComplete.addEventListener('click', () => finishCompleteTask(false));
        const confirmComplete = document.getElementById('confirmComplete');
        if (confirmComplete) confirmComplete.addEventListener('click', () => finishCompleteTask(true));
    }

    // Close modals on outside click
    window.addEventListener('click', (e) => {
        const taskModal = document.getElementById('taskModal');
        const deleteModal = document.getElementById('deleteModal');
        const completeModal = document.getElementById('completeModal');
        if (e.target === taskModal) closeTaskModal();
        if (e.target === deleteModal) closeDeleteModal();
        if (e.target === completeModal) closeCompleteModal();
    });

    // Logout
    const logoutBtn = document.getElementById('logoutBtn');
    if (logoutBtn) {
        logoutBtn.addEventListener('click', handleLogout);
    }
}

// Open task modal (add or edit)
async function openTaskModal(task = null) {
    const modal = document.getElementById('taskModal');
    const title = document.getElementById('modalTitle');
    const form = document.getElementById('taskForm');

    if (!modal || !title || !form) {
        console.error('Modal elements not found');
        showNotification('Failed to open task modal', 'error');
        return;
    }

    await loadUsers();

    if (task) {
        populateAssigneeDropdown();
        title.textContent = 'Edit Task';
        const editIdEl = document.getElementById('editTaskId');
        const taskTitleEl = document.getElementById('taskTitle');
        const taskDescEl = document.getElementById('taskDescription');
        const taskCatEl = document.getElementById('taskCategory');
        const taskPriEl = document.getElementById('taskPriority');
        const taskStatEl = document.getElementById('taskStatus');
        const taskAssigneeEl = document.getElementById('taskAssignee');

        if (editIdEl) editIdEl.value = task.id;
        if (taskTitleEl) taskTitleEl.value = task.title || '';
        if (taskDescEl) taskDescEl.value = task.description || '';
        if (taskCatEl) taskCatEl.value = task.category || 'adhoc';
        if (taskPriEl) taskPriEl.value = task.priority || 'medium';
        if (taskStatEl) taskStatEl.value = task.status || 'pending';
        if (taskAssigneeEl) taskAssigneeEl.value = task.assigned_to || '';
        // Format datetime-local requires YYYY-MM-DDTHH:MM
        const taskDueEl = document.getElementById('taskDue');
        if (taskDueEl) {
            if (task.due_date) {
                const d = new Date(task.due_date);
                // Convert to local timezone
                const offset = d.getTimezoneOffset() * 60000;
                const localDate = new Date(d.getTime() - offset);
                taskDueEl.value = localDate.toISOString().slice(0, 16);
            } else {
                taskDueEl.value = '';
            }
        }
    } else {
        title.textContent = 'Add New Task';
        form.reset();
        populateAssigneeDropdown();
        const editIdEl = document.getElementById('editTaskId');
        if (editIdEl) editIdEl.value = '';
        // Set default due date to tomorrow 9 AM
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        tomorrow.setHours(9, 0, 0, 0);
        const offset = tomorrow.getTimezoneOffset() * 60000;
        const localDate = new Date(tomorrow.getTime() - offset);
        const taskDueEl = document.getElementById('taskDue');
        if (taskDueEl) taskDueEl.value = localDate.toISOString().slice(0, 16);
        // Set default category
        const taskCatEl = document.getElementById('taskCategory');
        if (taskCatEl) taskCatEl.value = 'adhoc';
    }

    modal.classList.add('show');
}

// Close task modal
function closeTaskModal() {
    document.getElementById('taskModal').classList.remove('show');
}

// Handle task form submit
async function handleTaskSubmit(e) {
    e.preventDefault();

    const editIdEl = document.getElementById('editTaskId');
    const dueDateEl = document.getElementById('taskDue');
    const titleEl = document.getElementById('taskTitle');
    const descEl = document.getElementById('taskDescription');
    const catEl = document.getElementById('taskCategory');
    const priEl = document.getElementById('taskPriority');
    const statEl = document.getElementById('taskStatus');
    const assigneeEl = document.getElementById('taskAssignee');

    const editId = editIdEl?.value || '';
    const dueDate = dueDateEl?.value || '';
    const title = titleEl?.value?.trim() || '';

    if (!title) {
        showNotification('Title is required', 'error');
        return;
    }

    if (!catEl || !catEl.value) {
        showNotification('Category is required', 'error');
        return;
    }

    const formData = {
        title: title,
        description: descEl?.value || '',
        category: catEl.value,
        priority: priEl?.value || 'medium',
        status: statEl?.value || 'pending',
        assigned_to: assigneeEl?.value || null,
        due_date: dueDate ? new Date(dueDate).toISOString() : null
    };

    try {
        const url = editId ? `/api/tasks/${editId}` : '/api/tasks';
        const method = editId ? 'PUT' : 'POST';

        console.log('Submitting task:', { url, method, formData });

        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        console.log('Response status:', response.status);

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            console.error('Error response:', errorData);
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }

        const result = await response.json();
        console.log('Result:', result);

        if (result.success) {
            showNotification(editId ? 'Task updated!' : 'Task created!', 'success');
            closeTaskModal();
            loadTasks();
        } else {
            showNotification(result.error || 'Operation failed', 'error');
        }
    } catch (error) {
        console.error('Task submit error:', error);
        showNotification('Operation failed: ' + error.message, 'error');
    }
}

// Edit task
window.editTask = async function(taskId) {
    try {
        console.log('Loading task', taskId, 'for edit');
        const response = await fetch(`/api/tasks/${taskId}`);
        if (!response.ok) {
            if (response.status === 403) {
                throw new Error('Access denied - you do not have permission to edit this task');
            }
            throw new Error(`HTTP ${response.status}`);
        }
        const data = await response.json();

        if (data && data.id) {
            await openTaskModal(data);
        } else {
            showNotification('Task not found', 'error');
        }
    } catch (error) {
        console.error('Failed to load task:', error);
        showNotification('Failed to load task: ' + error.message, 'error');
    }
};

// Delete task (open confirmation)
window.confirmDeleteTask = function(taskId, taskTitle) {
    taskToDelete = taskId;
    document.getElementById('deleteTaskTitle').textContent = taskTitle;
    document.getElementById('deleteModal').classList.add('show');
};

// Close delete modal
function closeDeleteModal() {
    document.getElementById('deleteModal').classList.remove('show');
    taskToDelete = null;
}

// Execute delete task
async function executeDeleteTask() {
    if (!taskToDelete) return;

    try {
        const response = await fetch(`/api/tasks/${taskToDelete}`, {
            method: 'DELETE'
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Task deleted!', 'success');
            loadTasks();
        } else {
            showNotification(result.error || 'Delete failed', 'error');
        }
    } catch (error) {
        showNotification('Delete failed', 'error');
    }

    closeDeleteModal();
}

// Complete task
let pendingCompleteTaskId = null;

window.completeTask = async function(taskId) {
    pendingCompleteTaskId = taskId;

    try {
        const response = await fetch(`/api/tasks/${taskId}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const task = await response.json();

        const recurringCategories = ['daily', 'weekly', 'monthly'];
        const isRecurringTask = recurringCategories.includes(task.category);

        if (isRecurringTask) {
            const modal = document.getElementById('completeModal');

            if (!modal) {
                console.error('Complete modal elements not found');
                executeCompleteTask(taskId, false);
                return;
            }

            modal.classList.add('show');
        } else {
            executeCompleteTask(taskId, false);
        }
    } catch (error) {
        pendingCompleteTaskId = null;
        console.error('Failed to load task for completion:', error);
        showNotification('Failed to load task: ' + error.message, 'error');
    }
};

// Complete modal
function openCompleteModal() {
    const modal = document.getElementById('completeModal');
    if (modal) modal.classList.add('show');
}

function closeCompleteModal() {
    const modal = document.getElementById('completeModal');
    if (modal) modal.classList.remove('show');
    pendingCompleteTaskId = null;
}

function finishCompleteTask(createNext) {
    const taskId = pendingCompleteTaskId;
    if (!taskId) return;

    const modal = document.getElementById('completeModal');
    if (modal) modal.classList.remove('show');
    pendingCompleteTaskId = null;
    executeCompleteTask(taskId, createNext);
}

async function executeCompleteTask(taskId, createNext) {
    if (!taskId) return;

    try {
        const response = await fetch(`/api/tasks/${taskId}/complete`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ create_next: createNext })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.error || `HTTP ${response.status}`);
        }

        const result = await response.json();

        if (result.success) {
            showNotification('Task completed!', 'success');
            loadTasks();
        } else {
            showNotification(result.error || 'Failed to complete task', 'error');
        }
    } catch (error) {
        console.error('Execute complete task error:', error);
        showNotification('Failed to complete task: ' + error.message, 'error');
    } finally {
        pendingCompleteTaskId = null;
    }
}

// Logout
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
    setInterval(loadTasks, 30000);
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

// Format date with time
function formatDateTime(dateString, relative = true, status = null) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    const now = new Date();
    const diff = date - now;
    const days = calendarDayDifference(date, now);

    const timeStr = formatTime(date);
    const dateStr = formatDate(date);

    if (!relative || status === 'completed') return `${dateStr} ${timeStr}`;

    if (days < 0) {
        const hoursOverdue = Math.abs(Math.floor(diff / (1000 * 60 * 60)));
        if (hoursOverdue < 24) return `<span class="text-danger">${hoursOverdue}h overdue (${dateStr} ${timeStr})</span>`;
        return `<span class="text-danger">${Math.abs(days)}d overdue (${dateStr} ${timeStr})</span>`;
    }
    if (days === 0) return `<span class="text-danger">Today ${timeStr}</span>`;
    if (days === 1) return `<span class="text-warning">Tomorrow ${timeStr}</span>`;
    if (days < 7) return `In ${days}d (${dateStr} ${timeStr})`;
    return `${dateStr} ${timeStr}`;
}

function formatDate(date) {
    return date.toLocaleDateString('en-GB', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        timeZone: 'Asia/Bangkok'
    });
}

function formatTime(date) {
    return date.toLocaleTimeString('en-GB', {
        hour: '2-digit',
        minute: '2-digit',
        hour12: false,
        timeZone: 'Asia/Bangkok'
    });
}

function formatCompletedDate(completedAt, dueDate) {
    if (!completedAt) return '-';
    const completed = new Date(completedAt);
    const dateStr = formatDate(completed);
    const timeStr = formatTime(completed);

    if (dueDate) {
        const due = new Date(dueDate);
        if (completed > due) {
            const diffMs = completed - due;
            const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
            const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
            const lateStr = diffDays > 0 ? `${diffDays}d late` : `${diffHrs}h late`;
            return `<span class="text-danger">${dateStr} ${timeStr}</span> <span class="badge badge-overdue">⏰ ${lateStr}</span>`;
        }
    }

    return `${dateStr} ${timeStr}`;
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

// Utility functions
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
