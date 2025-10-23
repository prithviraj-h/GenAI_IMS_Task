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
    
    container.innerHTML = incidents.map((incident, index) => {
        const isNew = isIncidentNew(incident);
        const newBadge = isNew ? '<span class="new-incident-badge">NEW</span>' : '';
        
        return `
        <div class="incident-card ${isNew ? 'new-incident' : ''}" data-incident-id="${incident.incident_id}">
            <div class="incident-header">
                <div>
                    <h3 class="incident-id" onclick="viewIncident('${incident.incident_id}')">
                        <i class='bx bx-shield-x'></i> ${incident.incident_id} ${newBadge}
                    </h3>
                    <p class="incident-use-case">${incident.use_case || incident.user_demand || 'No description available'}</p>
                </div>
                <div class="incident-badges">
                    <span class="status-badge status-${incident.status}">
                        <i class='bx ${getStatusIcon(incident.status)}'></i> ${incident.status.replace('_', ' ').toUpperCase()}
                    </span>
                    ${incident.needs_kb_approval ? 
                        '<span class="kb-approval-badge"><i class="bx bx-check-shield"></i> NEEDS APPROVAL</span>' 
                        : ''}
                    ${incident.is_new_kb_entry ? 
                        '<span class="new-kb-badge"><i class="bx bx-star"></i> NEW PATTERN</span>' 
                        : ''}
                </div>
            </div>
            
            <div class="incident-info">
                <div class="info-row">
                    <span class="label"><i class='bx bx-calendar-plus'></i> Created:</span>
                    <span>${formatDate(incident.created_on)}</span>
                </div>
                <div class="info-row">
                    <span class="label"><i class='bx bx-calendar-edit'></i> Updated:</span>
                    <span>${formatDate(incident.updated_on)}</span>
                </div>
                <div class="info-row">
                    <span class="label"><i class='bx bx-id-card'></i> Session:</span>
                    <span class="session-id">${incident.session_id || 'N/A'}</span>
                </div>
            </div>
            
            <div class="incident-actions">
                <button class="btn-view" onclick="viewIncident('${incident.incident_id}')">
                    <i class='bx bx-search-alt'></i> Investigate
                </button>
                ${incident.needs_kb_approval ? 
                    `<button class="btn-approve" onclick="showKBApprovalModal('${incident.incident_id}')">
                        <i class='bx bx-check-shield'></i> Approve Solution
                    </button>` 
                    : ''}
                ${incident.status !== 'resolved' ? 
                    `<button class="btn-resolve" onclick="resolveIncident('${incident.incident_id}')">
                        <i class='bx bx-check-double'></i> Mark Resolved
                    </button>` 
                    : ''}
                <button class="btn-delete" onclick="deleteIncident('${incident.incident_id}')">
                    <i class='bx bx-trash-alt'></i> Archive
                </button>
            </div>
        </div>
        `;
    }).join('');
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
                ${incident.status !== 'resolved' ? 
                    `<button class="btn-resolve" onclick="resolveIncident('${incident.incident_id}')">
                        <i class='bx bx-check-double'></i> Mark as Resolved
                    </button>` 
                    : ''}
                <button class="btn-delete" onclick="deleteIncident('${incident.incident_id}')">
                    <i class='bx bx-trash-alt'></i> Archive Incident
                </button>
                <button class="btn-secondary" onclick="closeModal()">
                    <i class='bx bx-x'></i> Close
                </button>
            </div>
        </div>
    `;
    
    modal.style.display = 'block';
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
    if (!confirm(`Are you sure you want to archive incident ${incidentId}?\n\nThis action will move it to the archives.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/incidents/${incidentId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            alert('Security incident archived successfully!');
            closeModal();
            loadIncidents();
            loadStats();
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail || 'Failed to archive incident'}`);
        }
    } catch (error) {
        console.error('Error deleting incident:', error);
        alert('Error archiving security incident. Please try again.');
    }
}

function closeModal() {
    document.getElementById('incidentModal').style.display = 'none';
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('incidentModal');
    if (event.target === modal) {
        closeModal();
    }
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
// Update your admin-script.js deleteChromaEntry function

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

// Add this function to update KB file status
async function updateKBFileStatus() {
    try {
        const response = await fetch('/api/admin/kb/current-file');
        const data = await response.json();
        
        // Update UI with current file status
        console.log('KB File Status:', data);
        
        // You can display this information in your admin panel
        if (data.file_exists) {
            console.log(`KB File: ${data.file_size} bytes, ${data.last_modified}`);
        } else {
            console.log('KB File: Not found');
        }
        
    } catch (error) {
        console.error('Error updating KB file status:', error);
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