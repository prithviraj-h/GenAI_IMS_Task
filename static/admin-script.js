// static/admin-script.js
let allIncidents = [];
let currentFilter = { status: '', needsKBApproval: false };

// Load incidents on page load
document.addEventListener('DOMContentLoaded', () => {
    loadIncidents();
    loadStats();
});

async function loadIncidents() {
    try {
        const params = new URLSearchParams();
        if (currentFilter.status) {
            params.append('status', currentFilter.status);
        }
        if (currentFilter.needsKBApproval) {
            params.append('needs_kb_approval', 'true');
        }

        const response = await fetch(`/api/admin/incidents?${params.toString()}`);
        const data = await response.json();
        
        allIncidents = data.incidents || [];
        displayIncidents(allIncidents);
    } catch (error) {
        console.error('Error loading incidents:', error);
        document.getElementById('incidentsList').innerHTML = 
            '<p class="error"><i class="bx bx-error-circle"></i> Error loading incidents. Please try again.</p>';
    }
}

async function loadStats() {
    try {
        const response = await fetch('/api/admin/stats');
        const stats = await response.json();
        
        document.getElementById('totalIncidents').textContent = stats.total || 0;
        document.getElementById('pendingIncidents').textContent = stats.pending_info || 0;
        document.getElementById('openIncidents').textContent = stats.open || 0;
        document.getElementById('approvalIncidents').textContent = stats.needs_kb_approval || 0;
        document.getElementById('resolvedIncidents').textContent = stats.resolved || 0;
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

function displayIncidents(incidents) {
    const container = document.getElementById('incidentsList');
    
    if (!incidents || incidents.length === 0) {
        container.innerHTML = '<p class="no-data"><i class="bx bx-inbox"></i> No security incidents found.</p>';
        return;
    }
    
    let tableHTML = `
        <table class="incidents-table">
            <thead>
                <tr>
                    <th>Incident ID</th>
                    <th>Use Case</th>
                    <th>Status</th>
                    <th>Created</th>
                    <th>Admin Message</th>
                    <th>Actions</th>
                </tr>
            </thead>
            <tbody>
    `;
    
    incidents.forEach((incident, index) => {
        const isNew = isIncidentNew(incident);
        const newBadge = isNew ? ' <span class="new-incident-badge">NEW</span>' : '';
        
        // Determine placeholder text based on status
        let placeholder = "Add admin message...";
        if (incident.status === 'pending_info') {
            placeholder = "Still need some information. (Default)";
        } else if (incident.status === 'open') {
            placeholder = "All information collected. Our team will contact you soon. (Default)";
        } else if (incident.status === 'resolved') {
            placeholder = "Incident has been resolved successfully. (Default)";
        }
        
        tableHTML += `
            <tr class="${isNew ? 'new-incident' : ''}">
                <td>
                    <span class="incident-id-link" onclick="viewIncident('${incident.incident_id}')">
                        ${incident.incident_id}${newBadge}
                    </span>
                </td>
                <td>${incident.use_case || incident.user_demand || 'No description'}</td>
                <td>
                    <span class="status-badge status-${incident.status}">
                        ${incident.status.replace('_', ' ').toUpperCase()}
                    </span>
                    ${incident.needs_kb_approval ? '<br><span class="kb-approval-badge">NEEDS APPROVAL</span>' : ''}
                </td>
                <td>${formatDate(incident.created_on)}</td>
                <td class="admin-message-cell">
                    <textarea 
                        class="admin-message-input" 
                        id="admin-message-${incident.incident_id}"
                        placeholder="${placeholder}"
                        title="Edit admin message. Default messages are set based on status."
                    >${incident.admin_message || ''}</textarea>
                    <button class="btn-save-message" onclick="saveAdminMessage('${incident.incident_id}')">
                        <i class='bx bx-save'></i> Save
                    </button>
                </td>
                <td>
                    <div class="table-actions">
                        <button class="btn-view" onclick="viewIncident('${incident.incident_id}')">
                            <i class='bx bx-search-alt'></i> View
                        </button>
                        ${incident.needs_kb_approval ? 
                            `<button class="btn-approve" onclick="showKBApprovalModal('${incident.incident_id}')">
                                <i class='bx bx-check-shield'></i> Approve
                            </button>` 
                            : ''}
                        ${incident.status === 'resolved' ? 
                            `<button class="btn-resolve" onclick="reopenIncident('${incident.incident_id}')">
                                <i class='bx bx-undo'></i> Reopen
                            </button>` 
                            : ''}
                    </div>
                </td>
            </tr>
        `;
    });
    
    tableHTML += `
            </tbody>
        </table>
    `;
    
    container.innerHTML = tableHTML;
}

async function saveAdminMessage(incidentId) {
    const messageInput = document.getElementById(`admin-message-${incidentId}`);
    const message = messageInput.value.trim();
    
    try {
        const response = await fetch(`/api/admin/incidents/${incidentId}/admin-message`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                admin_message: message
            })
        });
        
        if (response.ok) {
            const result = await response.json();
            
            // Show success feedback
            const btn = messageInput.nextElementSibling;
            const originalText = btn.innerHTML;
            btn.innerHTML = '<i class="bx bx-check"></i> Saved';
            btn.style.background = 'linear-gradient(135deg, #66bb6a, #43a047)';
            
            // Update the placeholder if message is empty (will use default)
            if (!message) {
                const incident = allIncidents.find(inc => inc.incident_id === incidentId);
                if (incident) {
                    let placeholder = "Add admin message...";
                    if (incident.status === 'pending_info') {
                        placeholder = "Still need some information. (Default)";
                    } else if (incident.status === 'open') {
                        placeholder = "All information collected. Our team will contact you soon. (Default)";
                    } else if (incident.status === 'resolved') {
                        placeholder = "Incident has been resolved successfully. (Default)";
                    }
                    messageInput.placeholder = placeholder;
                }
            }
            
            setTimeout(() => {
                btn.innerHTML = originalText;
                btn.style.background = 'linear-gradient(135deg, #66bb6a, #43a047)';
            }, 2000);
            
            // Reload incidents to get updated data
            loadIncidents();
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail || 'Failed to save admin message'}`);
        }
    } catch (error) {
        console.error('Error saving admin message:', error);
        alert('Error saving admin message. Please try again.');
    }
}
async function reopenIncident(incidentId) {
    if (!confirm(`Are you sure you want to reopen incident ${incidentId}?`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/incidents/${incidentId}/status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                status: 'open'
            })
        });
        
        if (response.ok) {
            alert('Incident reopened successfully!');
            loadIncidents();
            loadStats();
        } else {
            alert('Error reopening incident');
        }
    } catch (error) {
        console.error('Error reopening incident:', error);
        alert('Error reopening incident. Please try again.');
    }
}

function getStatusIcon(status) {
    switch(status) {
        case 'pending_info': return 'bx-time-five';
        case 'open': return 'bx-error-circle';
        case 'resolved': return 'bx-check-double';
        default: return 'bx-circle';
    }
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    
    try {
        const date = new Date(dateString);
        
        // Convert to IST (UTC+5:30)
        const istOffset = 5.5 * 60 * 60 * 1000; // 5 hours 30 minutes in milliseconds
        const istTime = new Date(date.getTime() + istOffset);
        
        const now = new Date();
        const diffTime = now - date;
        const diffMinutes = Math.floor(diffTime / (1000 * 60));
        const diffHours = Math.floor(diffTime / (1000 * 60 * 60));
        const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
        
        // IST time formatting options
        const timeOptions = { 
            hour: '2-digit', 
            minute: '2-digit',
            hour12: true,
            timeZone: 'Asia/Kolkata'
        };
        
        const dateTimeOptions = {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: true,
            timeZone: 'Asia/Kolkata'
        };
        
        if (diffMinutes < 1) {
            return 'Just now';
        } else if (diffMinutes < 60) {
            return `${diffMinutes} minutes ago`;
        } else if (diffHours < 24) {
            if (diffHours === 1) {
                return '1 hour ago';
            } else {
                return `${diffHours} hours ago`;
            }
        } else if (diffDays === 1) {
            return 'Yesterday, ' + istTime.toLocaleTimeString('en-IN', timeOptions);
        } else if (diffDays <= 7) {
            return `${diffDays} days ago`;
        } else {
            return istTime.toLocaleDateString('en-IN', dateTimeOptions);
        }
    } catch (e) {
        console.error('Error formatting date:', e);
        // Fallback to simple formatting
        const date = new Date(dateString);
        return date.toLocaleString('en-IN', {
            timeZone: 'Asia/Kolkata',
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    }
}

function isIncidentNew(incident) {
    if (!incident.created_on) return false;
    const created = new Date(incident.created_on);
    const now = new Date();
    const diffTime = now - created;
    const diffHours = diffTime / (1000 * 60 * 60);
    return diffHours < 2; // Consider new if created within last 24 hours
}

function filterIncidents() {
    const statusFilter = document.getElementById('statusFilter').value;
    const approvalFilter = document.getElementById('approvalFilter').checked;
    
    currentFilter = {
        status: statusFilter,
        needsKBApproval: approvalFilter
    };
    
    loadIncidents();
}

async function viewIncident(incidentId) {
    try {
        const response = await fetch(`/api/admin/incidents/${incidentId}`);
        const incident = await response.json();
        
        showIncidentModal(incident);
    } catch (error) {
        console.error('Error loading incident details:', error);
        alert('Error loading incident details');
    }
}

function showIncidentModal(incident) {
    const modal = document.getElementById('incidentModal');
    const modalBody = document.getElementById('modalBody');
    
    // Format collected info
    const collectedInfoHtml = Object.entries(incident.collected_info || {})
        .map(([key, value]) => `<li><i class='bx bx-check'></i> <strong>${key}:</strong> ${value}</li>`)
        .join('');
    
    // Format missing info
    const missingInfoHtml = (incident.missing_info || [])
        .map(info => `<li><i class='bx bx-x-circle'></i> ${info}</li>`)
        .join('');
    
    // Format conversation history
    const conversationHtml = (incident.conversation_history || [])
        .map(msg => `
            <div class="chat-message ${msg.role}">
                <div class="message-role">
                    <i class='bx ${msg.role === 'user' ? 'bx-user' : 'bx-bot'}'></i>
                    ${msg.role === 'user' ? 'User' : 'Security Analyst'}:
                </div>
                <div class="message-content">${msg.content}</div>
                <div class="message-time">${formatDate(msg.timestamp)}</div>
            </div>
        `).join('');
    
    // Get admin message or use default
    const adminMessage = incident.admin_message || 
        (incident.status === 'pending_info' ? 'Still need some information.' :
         incident.status === 'open' ? 'All information collected. Our team will contact you soon.' :
         incident.status === 'resolved' ? 'Incident has been resolved successfully.' :
         'Incident has been closed.');
    
    modalBody.innerHTML = `
        <div class="incident-details">
            <h2><i class='bx bx-shield-x'></i> ${incident.incident_id}</h2>
            
            <div class="detail-section">
                <h3><i class='bx bx-info-circle'></i> Security Overview</h3>
                <table class="detail-table">
                    <tr>
                        <td><strong>Threat Type:</strong></td>
                        <td>${incident.use_case || incident.user_demand || 'N/A'}</td>
                    </tr>
                    <tr>
                        <td><strong>Status:</strong></td>
                        <td><span class="status-badge status-${incident.status}">${incident.status.replace('_', ' ').toUpperCase()}</span></td>
                    </tr>
                    <tr>
                        <td><strong>Session ID:</strong></td>
                        <td>${incident.session_id || 'N/A'}</td>
                    </tr>
                    <tr>
                        <td><strong>KB ID:</strong></td>
                        <td>${incident.kb_id || 'N/A'}</td>
                    </tr>
                    <tr>
                        <td><strong>Needs KB Approval:</strong></td>
                        <td>${incident.needs_kb_approval ? 'Yes' : 'No'}</td>
                    </tr>
                    <tr>
                        <td><strong>Created:</strong></td>
                        <td>${formatDate(incident.created_on)}</td>
                    </tr>
                    <tr>
                        <td><strong>Updated:</strong></td>
                        <td>${formatDate(incident.updated_on)}</td>
                    </tr>
                </table>
            </div>
            
            <div class="detail-section">
                <h3><i class='bx bx-message-alt'></i> Admin Message</h3>
                <div class="admin-message-display" style="background: rgba(102, 126, 234, 0.1); padding: 20px; border-radius: 12px; border-left: 5px solid #667eea; margin: 15px 0;">
                    <p style="margin: 0; font-size: 16px; line-height: 1.6; color: rgba(255, 255, 255, 0.9);">
                        <strong>📢 Message to User:</strong><br>
                        ${adminMessage}
                    </p>
                </div>
                <div style="margin-top: 15px;">
                    <textarea 
                        class="admin-message-input" 
                        id="modal-admin-message-${incident.incident_id}"
                        placeholder="Edit admin message..."
                        style="width: 100%; margin-bottom: 10px;"
                    >${incident.admin_message || ''}</textarea>
                    <button class="btn-save-message" onclick="saveModalAdminMessage('${incident.incident_id}')">
                        <i class='bx bx-save'></i> Update Message
                    </button>
                </div>
            </div>
            
            <div class="detail-section">
                <h3><i class='bx bx-check-circle'></i> Collected Evidence</h3>
                ${collectedInfoHtml ? `<ul class="info-list">${collectedInfoHtml}</ul>` : '<p>No evidence collected yet.</p>'}
            </div>
            
            <div class="detail-section">
                <h3><i class='bx bx-x-circle'></i> Missing Information</h3>
                ${missingInfoHtml ? `<ul class="info-list">${missingInfoHtml}</ul>` : '<p>All required information collected.</p>'}
            </div>
            
            ${incident.solution_steps ? `
                <div class="detail-section">
                    <h3><i class='bx bx-cog'></i> Resolution Steps</h3>
                    <div class="solution-box">
                        ${incident.solution_steps.split('\n').map(step => `<p>${step}</p>`).join('')}
                    </div>
                </div>
            ` : ''}
            
            <div class="detail-section">
                <h3><i class='bx bx-conversation'></i> Investigation Log</h3>
                <div class="conversation-box">
                    ${conversationHtml || '<p>No investigation log available.</p>'}
                </div>
            </div>
            
            <div class="modal-actions">
                ${incident.needs_kb_approval ? 
                    `<button class="btn-approve" onclick="showKBApprovalModal('${incident.incident_id}')">
                        <i class='bx bx-check-shield'></i> Approve & Add to KB
                    </button>` 
                    : ''}
                ${incident.status !== 'resolved' && incident.status !== 'closed' ? 
                    `<button class="btn-resolve" onclick="resolveIncident('${incident.incident_id}')">
                        <i class='bx bx-check-double'></i> Mark as Resolved
                    </button>` 
                    : ''}
                ${incident.status === 'resolved' ? 
                    `<button class="btn-resolve" onclick="reopenIncident('${incident.incident_id}')">
                        <i class='bx bx-undo'></i> Reopen Incident
                    </button>` 
                    : ''}
                <button class="btn-delete" onclick="deleteIncident('${incident.incident_id}')">
                    <i class='bx bx-trash-alt'></i> Delete Incident
                </button>
                <button class="btn-secondary" onclick="closeModal()">
                    <i class='bx bx-x'></i> Close
                </button>
            </div>
        </div>
    `;
    
    modal.style.display = 'block';
}

// Add function to save admin message from modal
async function saveModalAdminMessage(incidentId) {
    const messageInput = document.getElementById(`modal-admin-message-${incidentId}`);
    const message = messageInput.value.trim();
    
    try {
        const response = await fetch(`/api/admin/incidents/${incidentId}/admin-message`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                admin_message: message
            })
        });
        
        if (response.ok) {
            // Show success feedback
            const btn = messageInput.nextElementSibling;
            const originalText = btn.innerHTML;
            btn.innerHTML = '<i class="bx bx-check"></i> Updated';
            btn.style.background = 'linear-gradient(135deg, #66bb6a, #43a047)';
            
            setTimeout(() => {
                btn.innerHTML = originalText;
                btn.style.background = 'linear-gradient(135deg, #66bb6a, #43a047)';
            }, 2000);
            
            // Reload the modal to show updated message
            viewIncident(incidentId);
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail || 'Failed to update admin message'}`);
        }
    } catch (error) {
        console.error('Error updating admin message:', error);
        alert('Error updating admin message. Please try again.');
    }
}
function showKBApprovalModal(incidentId) {
    const modal = document.getElementById('incidentModal');
    const modalBody = document.getElementById('modalBody');
    
    modalBody.innerHTML = `
        <div class="kb-approval-form">
            <h2><i class='bx bx-check-shield'></i> Approve Security Solution</h2>
            <p>Incident ID: <strong>${incidentId}</strong></p>
            
            <div class="form-group">
                <label for="solutionSteps"><i class='bx bx-edit-alt'></i> Resolution Protocol:</label>
                <textarea 
                    id="solutionSteps" 
                    rows="10" 
                    placeholder="Enter the security resolution steps for this incident. Each step should be on a new line.&#10;&#10;Example:&#10;- Isolate affected system from network&#10;- Run malware scan with updated definitions&#10;- Check for suspicious processes&#10;- Review firewall logs for anomalies"
                    required
                ></textarea>
            </div>
            
            <div class="form-actions">
                <button class="btn-approve" onclick="approveKBEntry('${incidentId}')">
                    <i class='bx bx-check-shield'></i> Approve & Add to KB
                </button>
                <button class="btn-secondary" onclick="closeModal()">
                    <i class='bx bx-x'></i> Cancel
                </button>
            </div>
        </div>
    `;
    
    modal.style.display = 'block';
}

async function approveKBEntry(incidentId) {
    const solutionSteps = document.getElementById('solutionSteps').value.trim();
    
    if (!solutionSteps) {
        alert('Please enter resolution steps');
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/incidents/${incidentId}/approve-kb`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                solution_steps: solutionSteps
            })
        });
        
        if (response.ok) {
            alert('Security solution approved and added to knowledge base!');
            closeModal();
            loadIncidents();
            loadStats();
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail || 'Failed to approve security solution'}`);
        }
    } catch (error) {
        console.error('Error approving KB entry:', error);
        alert('Error approving security solution. Please try again.');
    }
}

async function resolveIncident(incidentId) {
    if (!confirm('Are you sure you want to mark this security incident as resolved?')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/incidents/${incidentId}/status`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                status: 'resolved'
            })
        });
        
        if (response.ok) {
            alert('Security incident marked as resolved!');
            closeModal();
            loadIncidents();
            loadStats();
        } else {
            alert('Error updating incident status');
        }
    } catch (error) {
        console.error('Error resolving incident:', error);
        alert('Error resolving security incident. Please try again.');
    }
}

async function deleteIncident(incidentId) {
    if (!confirm(`Are you sure you want to Delete incident ${incidentId}?\n\nThis action will move it to the archives.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/incidents/${incidentId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            alert('Security incident deleted successfully!');
            closeModal();
            loadIncidents();
            loadStats();
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail || 'Failed to delete incident'}`);
        }
    } catch (error) {
        console.error('Error deleting incident:', error);
        alert('Error archiving security incident. Please try again.');
    }
}

function closeModal() {
    document.getElementById('incidentModal').style.display = 'none';
}

// ChromaDB Management Functions
async function viewChromaEntries() {
    try {
        const response = await fetch('/api/admin/chroma/entries');
        const data = await response.json();
        
        const modal = document.getElementById('incidentModal');
        const modalBody = document.getElementById('modalBody');
        
        let content = `<h2><i class='bx bx-book-alt'></i> Security Knowledge Base</h2>`;
        content += `<p class="info-note"><i class='bx bx-info-circle'></i> Total: ${data.total} security patterns - Used for threat detection and analysis</p>`;
        content += `<div class="chroma-entries-list">`;
        
        if (data.entries && data.entries.length > 0) {
            data.entries.forEach(entry => {
                content += `
                    <div class="chroma-entry-card">
                        <div class="chroma-entry-header">
                            <h4>${entry.id}</h4>
                            <button class="btn-delete" onclick="deleteChromaEntry('${entry.id}')">
                                <i class='bx bx-trash-alt'></i> Remove
                            </button>
                        </div>
                        <div class="chroma-entry-content">
                            <p><strong>Threat Pattern:</strong> ${entry.metadata.use_case}</p>
                            <p><strong>Required Evidence:</strong> ${entry.metadata.required_info}</p>
                            <p><strong>Resolution Protocol:</strong> ${entry.metadata.solution_steps ? entry.metadata.solution_steps.substring(0, 100) + '...' : 'N/A'}</p>
                            <p><strong>Investigation Questions:</strong> ${entry.metadata.questions}</p>
                        </div>
                    </div>
                `;
            });
        } else {
            content += `<p class="no-data"><i class='bx bx-inbox'></i> No security patterns found in knowledge base.</p>`;
        }
        
        content += `</div>`;
        modalBody.innerHTML = content;
        modal.style.display = 'block';
        
    } catch (error) {
        console.error('Error loading Chroma entries:', error);
        alert('Error loading security knowledge base');
    }
}

async function deleteChromaEntry(kbId) {
    if (!confirm(`Are you sure you want to remove security pattern: ${kbId}?\n\nThis will remove it from both the database and knowledge base file.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/chroma/entries/${kbId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            const result = await response.json();
            alert('✅ Security pattern removed successfully! Database and file synchronized.');
            
            // Refresh the KB file status
            await updateKBFileStatus();
            closeModal();
        } else {
            const error = await response.json();
            alert(`❌ Error: ${error.detail || 'Failed to remove security pattern'}`);
        }
    } catch (error) {
        console.error('Error deleting Chroma entry:', error);
        alert('❌ Error removing security pattern. Please try again.');
    }
}

// Add force sync function
async function forceSyncKB() {
    try {
        const response = await fetch('/api/admin/kb/force-sync');
        const result = await response.json();
        
        alert(`✅ ${result.message}`);
        await updateKBFileStatus();
        
    } catch (error) {
        console.error('Error forcing KB sync:', error);
        alert('❌ Error synchronizing knowledge base');
    }
}

async function updateKBFileStatus() {
    try {
        const response = await fetch('/api/admin/kb/current-file');
        const data = await response.json();
        
        console.log('KB File Status:', data);
        
    } catch (error) {
        console.error('Error updating KB file status:', error);
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', function(event) {
    // Escape key to close modal
    if (event.key === 'Escape') {
        closeModal();
    }
    
    // Ctrl+R to refresh incidents
    if (event.ctrlKey && event.key === 'r') {
        event.preventDefault();
        loadIncidents();
    }
});

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('incidentModal');
    if (event.target === modal) {
        closeModal();
    }
}