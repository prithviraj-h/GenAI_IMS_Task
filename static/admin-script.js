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
            '<p class="error">Error loading incidents. Please try again.</p>';
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
        container.innerHTML = '<p class="no-data">No incidents found.</p>';
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
                        ${incident.incident_id} ${newBadge}
                    </h3>
                    <p class="incident-use-case">${incident.use_case || incident.user_demand}</p>
                </div>
                <div class="incident-badges">
                    <span class="status-badge status-${incident.status}">${incident.status}</span>
                    ${incident.needs_kb_approval ? '<span class="kb-approval-badge">Needs KB Approval</span>' : ''}
                    ${incident.is_new_kb_entry ? '<span class="new-kb-badge">New Issue Type</span>' : ''}
                </div>
            </div>
            
            <div class="incident-info">
                <div class="info-row">
                    <span class="label">Created:</span>
                    <span>${formatDate(incident.created_on)}</span>
                </div>
                <div class="info-row">
                    <span class="label">Updated:</span>
                    <span>${formatDate(incident.updated_on)}</span>
                </div>
                <div class="info-row">
                    <span class="label">Session:</span>
                    <span>${incident.session_id}</span>
                </div>
            </div>
            
            <div class="incident-actions">
                <button class="btn-view" onclick="viewIncident('${incident.incident_id}')">View Details</button>
                ${incident.needs_kb_approval ? 
                    `<button class="btn-approve" onclick="showKBApprovalModal('${incident.incident_id}')">Approve KB Entry</button>` 
                    : ''}
                ${incident.status !== 'resolved' ? 
                    `<button class="btn-resolve" onclick="resolveIncident('${incident.incident_id}')">Mark as Resolved</button>` 
                    : ''}
            </div>
        </div>
        `;
    }).join('');
}

function formatDate(dateString) {
    if (!dateString) return 'N/A';
    const date = new Date(dateString);
    const now = new Date();
    const diffTime = Math.abs(now - date);
    const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
    
    if (diffDays === 1) {
        return 'Today, ' + date.toLocaleTimeString();
    } else if (diffDays === 2) {
        return 'Yesterday, ' + date.toLocaleTimeString();
    } else if (diffDays <= 7) {
        return `${diffDays - 1} days ago`;
    } else {
        return date.toLocaleString();
    }
}

function isIncidentNew(incident) {
    if (!incident.created_on) return false;
    const created = new Date(incident.created_on);
    const now = new Date();
    const diffTime = now - created;
    const diffHours = diffTime / (1000 * 60 * 60);
    return diffHours < 24; // Consider new if created within last 24 hours
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
// Add this function


// Add this to display Chroma entries with delete buttons
// Add these functions to admin-script.js

async function viewChromaEntries() {
    try {
        const response = await fetch('/api/admin/chroma/entries');
        const data = await response.json();
        
        const modal = document.getElementById('incidentModal');
        const modalBody = document.getElementById('modalBody');
        
        let content = `<h2>📚 ChromaDB Knowledge Base Entries</h2>`;
        content += `<p class="info-note">Total: ${data.total} entries - These are used for semantic search</p>`;
        content += `<div class="chroma-entries-list">`;
        
        if (data.entries && data.entries.length > 0) {
            data.entries.forEach(entry => {
                content += `
                    <div class="chroma-entry-card">
                        <div class="chroma-entry-header">
                            <h4>${entry.id}</h4>
                            <button class="btn-delete" onclick="deleteChromaEntry('${entry.id}')">🗑️ Delete</button>
                        </div>
                        <div class="chroma-entry-content">
                            <p><strong>Use Case:</strong> ${entry.metadata.use_case}</p>
                            <p><strong>Required Info:</strong> ${entry.metadata.required_info}</p>
                            <p><strong>Solution Steps Preview:</strong> ${entry.metadata.solution_steps.substring(0, 100)}...</p>
                            <p><strong>Questions:</strong> ${entry.metadata.questions}</p>
                        </div>
                    </div>
                `;
            });
        } else {
            content += `<p class="no-data">No KB entries found in ChromaDB.</p>`;
        }
        
        content += `</div>`;
        modalBody.innerHTML = content;
        modal.style.display = 'block';
        
    } catch (error) {
        console.error('Error loading Chroma entries:', error);
        alert('Error loading KB entries');
    }
}

async function deleteChromaEntry(kbId) {
    if (!confirm(`Are you sure you want to delete KB entry: ${kbId}?\n\nThis will remove it from the semantic search database and cannot be undone.`)) {
        return;
    }
    
    try {
        const response = await fetch(`/api/admin/chroma/entries/${kbId}`, {
            method: 'DELETE'
        });
        
        if (response.ok) {
            alert('✅ KB entry deleted successfully!');
            // Close modal and reload
            closeModal();
            // Optionally reload the Chroma entries view
            // viewChromaEntries();
        } else {
            const error = await response.json();
            alert(`❌ Error: ${error.detail || 'Failed to delete KB entry'}`);
        }
    } catch (error) {
        console.error('Error deleting Chroma entry:', error);
        alert('❌ Error deleting KB entry. Please try again.');
    }
}

// Add a button to admin UI to view Chroma entries
// Add this to your admin.html in the header-actions div:
// <button class="btn-refresh" onclick="viewChromaEntries()" style="margin-left: 10px;">
//     📚 View KB Entries
// </button>
function showIncidentModal(incident) {
    const modal = document.getElementById('incidentModal');
    const modalBody = document.getElementById('modalBody');
    
    // Format collected info
    const collectedInfoHtml = Object.entries(incident.collected_info || {})
        .map(([key, value]) => `<li><strong>${key}:</strong> ${value}</li>`)
        .join('');
    
    // Format missing info
    const missingInfoHtml = (incident.missing_info || [])
        .map(info => `<li>${info}</li>`)
        .join('');
    
    // Format conversation history
    const conversationHtml = (incident.conversation_history || [])
        .map(msg => `
            <div class="chat-message ${msg.role}">
                <div class="message-role">${msg.role === 'user' ? 'User' : 'Assistant'}:</div>
                <div class="message-content">${msg.content}</div>
                <div class="message-time">${formatDate(msg.timestamp)}</div>
            </div>
        `).join('');
    
    modalBody.innerHTML = `
        <div class="incident-details">
            <h2>${incident.incident_id}</h2>
            
            <div class="detail-section">
                <h3>Overview</h3>
                <table class="detail-table">
                    <tr>
                        <td><strong>Use Case:</strong></td>
                        <td>${incident.use_case || incident.user_demand}</td>
                    </tr>
                    <tr>
                        <td><strong>Status:</strong></td>
                        <td><span class="status-badge status-${incident.status}">${incident.status}</span></td>
                    </tr>
                    <tr>
                        <td><strong>Session ID:</strong></td>
                        <td>${incident.session_id}</td>
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
                <h3>Collected Information</h3>
                ${collectedInfoHtml ? `<ul class="info-list">${collectedInfoHtml}</ul>` : '<p>No information collected yet.</p>'}
            </div>
            
            <div class="detail-section">
                <h3>Missing Information</h3>
                ${missingInfoHtml ? `<ul class="info-list">${missingInfoHtml}</ul>` : '<p>All information collected.</p>'}
            </div>
            
            ${incident.solution_steps ? `
                <div class="detail-section">
                    <h3>Solution Steps (Admin Only)</h3>
                    <div class="solution-box">
                        ${incident.solution_steps.split('\n').map(step => `<p>${step}</p>`).join('')}
                    </div>
                </div>
            ` : ''}
            
            <div class="detail-section">
                <h3>Conversation History</h3>
                <div class="conversation-box">
                    ${conversationHtml}
                </div>
            </div>
            
            <div class="modal-actions">
                ${incident.needs_kb_approval ? 
                    `<button class="btn-approve" onclick="showKBApprovalModal('${incident.incident_id}')">Approve & Add to KB</button>` 
                    : ''}
                ${incident.status !== 'resolved' ? 
                    `<button class="btn-resolve" onclick="resolveIncident('${incident.incident_id}')">Mark as Resolved</button>` 
                    : ''}
                <button class="btn-secondary" onclick="closeModal()">Close</button>
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
            <h2>Approve KB Entry</h2>
            <p>Incident ID: <strong>${incidentId}</strong></p>
            
            <div class="form-group">
                <label for="solutionSteps">Solution Steps:</label>
                <textarea 
                    id="solutionSteps" 
                    rows="10" 
                    placeholder="Enter the solution steps for this issue. Each step should be on a new line.&#10;&#10;Example:&#10;- Check the network cable connection&#10;- Restart the router&#10;- Run network diagnostics"
                    required
                ></textarea>
            </div>
            
            <div class="form-actions">
                <button class="btn-approve" onclick="approveKBEntry('${incidentId}')">Approve & Add to KB</button>
                <button class="btn-secondary" onclick="closeModal()">Cancel</button>
            </div>
        </div>
    `;
    
    modal.style.display = 'block';
}

async function approveKBEntry(incidentId) {
    const solutionSteps = document.getElementById('solutionSteps').value.trim();
    
    if (!solutionSteps) {
        alert('Please enter solution steps');
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
            alert('KB entry approved and added successfully!');
            closeModal();
            loadIncidents();
            loadStats();
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail || 'Failed to approve KB entry'}`);
        }
    } catch (error) {
        console.error('Error approving KB entry:', error);
        alert('Error approving KB entry. Please try again.');
    }
}

async function resolveIncident(incidentId) {
    if (!confirm('Are you sure you want to mark this incident as resolved?')) {
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
            alert('Incident marked as resolved!');
            closeModal();
            loadIncidents();
            loadStats();
        } else {
            alert('Error updating incident status');
        }
    } catch (error) {
        console.error('Error resolving incident:', error);
        alert('Error resolving incident. Please try again.');
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

// View ChromaDB entries (for debugging)
async function viewChromaEntries() {
    try {
        const response = await fetch('/api/admin/chroma/entries');
        const data = await response.json();
        
        console.log('ChromaDB Entries:', data);
        alert(`ChromaDB has ${data.total} entries. Check console for details.`);
    } catch (error) {
        console.error('Error loading ChromaDB entries:', error);
        alert('Error loading ChromaDB entries');
    }
}

// Add button to view ChromaDB entries (optional)
// You can call viewChromaEntries() from browser console