// Tasks page JavaScript functionality

// Global state
let usersList = [];
let taskToDelete = null;

// Initialize tasks page
document.addEventListener('DOMContentLoaded', () => {
    loadTasks();
    loadUsers();
    setupEventListeners();
    syncRecurringOption();
    startAutoRefresh();
});

// Load tasks with current filters
async function loadTasks() {
    const category = document.getElementById('categoryFilter')?.value || '';
    const status = document.getElementById('statusFilter')?.value || '';
    const search = document.getElementById('searchInput')?.value || '';

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

    if (tasks.length === 0) {
        tbody.innerHTML = '<tr><td colspan="8" class="no-tasks">No tasks found</td></tr>';
        return;
    }

    tbody.innerHTML = tasks.map(task => `
        <tr>
            <td>
                <div class="task-cell-title">${task.title ? escapeHtml(task.title) : 'No title'}</div>
                ${task.description ? `<div class="task-cell-desc">${escapeHtml(task.description.substring(0, 50))}${task.description.length > 50 ? '...' : ''}</div>` : ''}
            </td>
            <td><span class="badge badge-${task.category}">${task.category || 'N/A'}</span></td>
            <td><span class="badge badge-${task.priority}">${task.priority || 'N/A'}</span></td>
            <td><span class="status status-${task.status}">${(task.status || 'pending').replace('_', ' ')}</span></td>
            <td>${task.assignee ? task.assignee.username : 'Unassigned'}</td>
            <td>${formatDateTime(task.due_date)}</td>
            <td>${formatDateTime(task.completed_at, false)}</td>
            <td class="actions">
                ${task.status !== 'completed' ? `
                    <button class="btn btn-small btn-complete" onclick="completeTask(${task.id})" title="Complete">✓</button>
                ` : '<button class="btn btn-small" disabled title="Completed">✓</button>'}
                ${window.currentUser && (window.currentUser.role === 'editor' || window.currentUser.role === 'admin') ? `
                    <button class="btn btn-small btn-edit" onclick="editTask(${task.id})" title="Edit">✎</button>
                    <button class="btn btn-small btn-delete" onclick="confirmDeleteTask(${task.id}, '${(task.title || '').replace(/'/g, "\\'").replace(/"/g, '\\"')}')" title="Delete">🗑</button>
                ` : ''}
            </td>
        </tr>
    `).join('');
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
    document.getElementById('categoryFilter').addEventListener('change', loadTasks);
    document.getElementById('statusFilter').addEventListener('change', loadTasks);
    document.getElementById('searchInput').addEventListener('input', debounce(loadTasks, 300));
    document.getElementById('taskCategory')?.addEventListener('change', syncRecurringOption);

    // Add task button
    const addBtn = document.getElementById('addTaskBtn');
    if (addBtn) {
        addBtn.addEventListener('click', () => openTaskModal());
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

    // Close modals on outside click
    window.addEventListener('click', (e) => {
        const taskModal = document.getElementById('taskModal');
        const deleteModal = document.getElementById('deleteModal');
        if (e.target === taskModal) closeTaskModal();
        if (e.target === deleteModal) closeDeleteModal();
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

    await loadUsers();

    if (task) {
        populateAssigneeDropdown();
        title.textContent = 'Edit Task';
        document.getElementById('editTaskId').value = task.id;
        document.getElementById('taskTitle').value = task.title;
        document.getElementById('taskDescription').value = task.description || '';
        document.getElementById('taskCategory').value = task.category;
        document.getElementById('taskPriority').value = task.priority;
        document.getElementById('taskStatus').value = task.status;
        document.getElementById('taskAssignee').value = task.assigned_to || '';
        document.getElementById('taskRecurring').checked = Boolean(task.is_recurring);
        syncRecurringOption();
        // Format datetime-local requires YYYY-MM-DDTHH:MM
        if (task.due_date) {
            const d = new Date(task.due_date);
            // Convert to local timezone
            const offset = d.getTimezoneOffset() * 60000;
            const localDate = new Date(d.getTime() - offset);
            document.getElementById('taskDue').value = localDate.toISOString().slice(0, 16);
        } else {
            document.getElementById('taskDue').value = '';
        }
    } else {
        title.textContent = 'Add New Task';
        form.reset();
        populateAssigneeDropdown();
        document.getElementById('editTaskId').value = '';
        document.getElementById('taskRecurring').checked = false;
        syncRecurringOption();
        // Set default due date to tomorrow 9 AM
        const tomorrow = new Date();
        tomorrow.setDate(tomorrow.getDate() + 1);
        tomorrow.setHours(9, 0, 0, 0);
        const offset = tomorrow.getTimezoneOffset() * 60000;
        const localDate = new Date(tomorrow.getTime() - offset);
        document.getElementById('taskDue').value = localDate.toISOString().slice(0, 16);
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

    const editId = document.getElementById('editTaskId').value;
    const dueDate = document.getElementById('taskDue').value;
    const formData = {
        title: document.getElementById('taskTitle').value,
        description: document.getElementById('taskDescription').value,
        category: document.getElementById('taskCategory').value,
        priority: document.getElementById('taskPriority').value,
        status: document.getElementById('taskStatus').value,
        assigned_to: document.getElementById('taskAssignee').value || null,
        is_recurring: document.getElementById('taskRecurring').checked,
        due_date: dueDate ? new Date(dueDate).toISOString() : null
    };

    try {
        const url = editId ? `/api/tasks/${editId}` : '/api/tasks';
        const method = editId ? 'PUT' : 'POST';

        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formData)
        });

        const result = await response.json();

        if (result.success) {
            showNotification(editId ? 'Task updated!' : 'Task created!', 'success');
            closeTaskModal();
            loadTasks();
        } else {
            showNotification(result.error || 'Operation failed', 'error');
        }
    } catch (error) {
        showNotification('Operation failed', 'error');
    }
}

// Edit task
window.editTask = async function(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}`);
        const data = await response.json();

        if (data) {
            await openTaskModal(data);
        }
    } catch (error) {
        showNotification('Failed to load task', 'error');
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
window.completeTask = async function(taskId) {
    try {
        const response = await fetch(`/api/tasks/${taskId}/complete`, {
            method: 'POST'
        });

        const result = await response.json();

        if (result.success) {
            showNotification('Task completed!', 'success');
            loadTasks();
        } else {
            showNotification(result.error || 'Failed to complete task', 'error');
        }
    } catch (error) {
        showNotification('Failed to complete task', 'error');
    }
};

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
function formatDateTime(dateString, relative = true) {
    if (!dateString) return '-';
    const date = new Date(dateString);
    const now = new Date();
    const diff = date - now;
    const days = calendarDayDifference(date, now);

    const timeStr = formatTime(date);
    const dateStr = formatDate(date);

    if (!relative) return `${dateStr} ${timeStr}`;

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
