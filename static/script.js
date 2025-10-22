// backend/static/script.js
let sessionId = null;
let currentIncidentId = null;
let isProcessing = false;

// DOM elements
const chatMessages = document.getElementById('chatMessages');
const userInput = document.getElementById('userInput');
const sendButton = document.getElementById('sendButton');
const sessionIdDisplay = document.getElementById('sessionId');
const currentIncidentDisplay = document.getElementById('currentIncident');
const incidentStatusDisplay = document.getElementById('incidentStatus');

// Event listeners
sendButton.addEventListener('click', sendMessage);
userInput.addEventListener('keypress', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    userInput.focus();
});

async function sendMessage() {
    const message = userInput.value.trim();
    
    if (!message || isProcessing) {
        return;
    }
    
    // Disable input
    isProcessing = true;
    sendButton.disabled = true;
    userInput.disabled = true;
    
    // Add user message to chat
    addMessage(message, 'user');
    
    // Clear input
    userInput.value = '';
    
    // Show typing indicator
    const typingId = addTypingIndicator();
    
    try {
        // Send to API
        const response = await fetch('/api/chat/query', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                user_input: message,
                session_id: sessionId
            })
        });
        
        if (!response.ok) {
            throw new Error('Failed to send message');
        }
        
        const data = await response.json();
        
        // Update session ID
        if (data.session_id) {
            sessionId = data.session_id;
            sessionIdDisplay.textContent = sessionId.substring(0, 8) + '...';
        }
        
        // Update incident info
        if (data.incident_id) {
            currentIncidentId = data.incident_id;
            currentIncidentDisplay.textContent = data.incident_id;
        }
        
        if (data.status) {
            incidentStatusDisplay.textContent = formatStatus(data.status);
        }
        
        // Handle special actions
        if (data.action === 'clear_session') {
            // Session was cleared, reset UI without page refresh
            sessionId = data.session_id;
            currentIncidentId = null;
            currentIncidentDisplay.textContent = 'None';
            incidentStatusDisplay.textContent = '-';
        }
        
        // Remove typing indicator
        removeTypingIndicator(typingId);
        
        // Add bot response with or without buttons
        if (data.show_action_buttons && data.action_buttons) {
            addMessageWithButtons(data.message, 'bot', data.action_buttons);
        } else {
            addMessage(data.message, 'bot');
        }
        
    } catch (error) {
        console.error('Error:', error);
        removeTypingIndicator(typingId);
        addMessage('Sorry, I encountered an error. Please try again.', 'bot');
    } finally {
        // Re-enable input
        isProcessing = false;
        sendButton.disabled = false;
        userInput.disabled = false;
        userInput.focus();
    }
}

function addMessage(text, type) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Format message with line breaks and lists
    const formattedText = formatMessageText(text);
    contentDiv.innerHTML = formattedText;
    
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function addMessageWithButtons(text, type, buttons) {
    console.log('Adding message with buttons:', buttons); // Debug log
    
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${type}-message`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Format message text
    const formattedText = formatMessageText(text);
    contentDiv.innerHTML = formattedText;
    
    // Create button container
    const buttonContainer = document.createElement('div');
    buttonContainer.className = 'action-buttons-container';
    buttonContainer.style.marginTop = '15px';
    buttonContainer.style.paddingTop = '15px';
    buttonContainer.style.borderTop = '1px solid #e0e0e0';
    buttonContainer.style.display = 'flex';
    buttonContainer.style.gap = '12px';
    buttonContainer.style.flexWrap = 'wrap';
    
    // Add buttons
    buttons.forEach((button, index) => {
        console.log(`Creating button ${index}:`, button); // Debug log
        
        const btn = document.createElement('button');
        btn.textContent = button.label;
        btn.className = 'action-button';
        btn.setAttribute('data-value', button.value);
        
        // Inline styles as fallback
        btn.style.padding = '12px 24px';
        btn.style.border = 'none';
        btn.style.borderRadius = '10px';
        btn.style.fontSize = '15px';
        btn.style.fontWeight = '600';
        btn.style.cursor = 'pointer';
        btn.style.transition = 'all 0.3s ease';
        btn.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.15)';
        btn.style.textTransform = 'uppercase';
        btn.style.letterSpacing = '0.5px';
        btn.style.color = 'white';
        
        // Set gradient based on value
        if (button.value.toLowerCase().includes('keep')) {
            btn.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
        } else if (button.value.toLowerCase().includes('ignore')) {
            btn.style.background = 'linear-gradient(135deg, #f093fb 0%, #f5576c 100%)';
        } else if (button.value.toLowerCase().includes('track')) {
            btn.style.background = 'linear-gradient(135deg, #4facfe 0%, #00f2fe 100%)';
        } else if (button.value.toLowerCase().includes('create')) {
            btn.style.background = 'linear-gradient(135deg, #43e97b 0%, #38f9d7 100%)';
        } else {
            btn.style.background = 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)';
        }
        
        btn.onclick = function() {
            console.log('Button clicked:', button.value); // Debug log
            
            // Disable all buttons after click
            const allButtons = buttonContainer.querySelectorAll('.action-button');
            allButtons.forEach(b => b.disabled = true);
            
            // Send the button value as message
            userInput.value = button.value;
            sendMessage();
        };
        
        btn.onmouseover = function() {
            btn.style.transform = 'translateY(-2px)';
            btn.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.25)';
        };
        
        btn.onmouseout = function() {
            if (!btn.disabled) {
                btn.style.transform = 'translateY(0)';
                btn.style.boxShadow = '0 2px 8px rgba(0, 0, 0, 0.15)';
            }
        };
        
        buttonContainer.appendChild(btn);
    });
    
    contentDiv.appendChild(buttonContainer);
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    // Scroll to bottom
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function formatMessageText(text) {
    // Convert newlines to <br>
    let formatted = text.replace(/\n/g, '<br>');
    
    // Convert bullet points
    formatted = formatted.replace(/• (.*?)(<br>|$)/g, '<li>$1</li>');
    formatted = formatted.replace(/- (.*?)(<br>|$)/g, '<li>$1</li>');
    
    // Wrap lists in <ul>
    if (formatted.includes('<li>')) {
        formatted = formatted.replace(/(<li>.*?<\/li>)+/g, '<ul>$&</ul>');
    }
    
    // Convert numbered lists
    formatted = formatted.replace(/\d+\. (.*?)(<br>|$)/g, '<li>$1</li>');
    if (formatted.match(/<li>.*?<\/li>/) && !formatted.includes('<ul>')) {
        formatted = formatted.replace(/(<li>.*?<\/li>)+/g, '<ol>$&</ol>');
    }
    
    // Make **text** bold
    formatted = formatted.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    
    return formatted;
}

function addTypingIndicator() {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot-message';
    messageDiv.id = 'typing-indicator';
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    const typingDiv = document.createElement('div');
    typingDiv.className = 'typing-indicator';
    typingDiv.innerHTML = '<span></span><span></span><span></span>';
    
    contentDiv.appendChild(typingDiv);
    messageDiv.appendChild(contentDiv);
    chatMessages.appendChild(messageDiv);
    
    chatMessages.scrollTop = chatMessages.scrollHeight;
    
    return 'typing-indicator';
}

function removeTypingIndicator(id) {
    const indicator = document.getElementById(id);
    if (indicator) {
        indicator.remove();
    }
}

function formatStatus(status) {
    const statusMap = {
        'pending_info': 'Pending Info',
        'open': 'Open',
        'resolved': 'Resolved',
        'closed': 'Closed',
        'error': 'Error',
        'session_cleared': 'Session Cleared',
        'awaiting_decision': 'Awaiting Decision',
        'awaiting_incident_id': 'Awaiting Incident ID',
        'not_found': 'Not Found',
        'awaiting_issue_description': 'Awaiting Issue Description'
    };
    
    return statusMap[status] || status;
}

async function clearSession() {
    if (!sessionId) {
        alert('No active session to clear');
        return;
    }
    
    if (!confirm('Are you sure you want to clear the session? This will close all active incidents and start fresh.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/chat/session/${sessionId}/clear`, {
            method: 'POST'
        });
        
        if (!response.ok) {
            throw new Error('Failed to clear session');
        }
        
        const data = await response.json();
        
        // Clear chat messages
        chatMessages.innerHTML = '';
        
        // Add welcome message
        addMessage("Session cleared! Hello! I'm your IT helpdesk assistant. How may I help you? Do you want to track an already created incident or create a new one?", 'bot');
        
        // Reset UI
        currentIncidentId = null;
        currentIncidentDisplay.textContent = 'None';
        incidentStatusDisplay.textContent = '-';
        
        alert('Session cleared successfully!');
        
    } catch (error) {
        console.error('Error clearing session:', error);
        alert('Failed to clear session. Please try again.');
    }
}

async function viewHistory() {
    if (!sessionId) {
        alert('No active session');
        return;
    }
    
    const modal = document.getElementById('historyModal');
    const modalBody = document.getElementById('historyModalBody');
    
    modal.style.display = 'block';
    modalBody.innerHTML = '<p class="loading">Loading history...</p>';
    
    try {
        const response = await fetch(`/api/chat/session/${sessionId}/history`);
        
        if (!response.ok) {
            throw new Error('Failed to load history');
        }
        
        const data = await response.json();
        
        if (data.history && data.history.length > 0) {
            let historyHTML = '<div class="history-list">';
            
            data.history.forEach((msg, index) => {
                const role = msg.role === 'user' ? 'You' : 'Assistant';
                const messageClass = msg.role === 'user' ? 'history-user' : 'history-assistant';
                
                historyHTML += `
                    <div class="history-message ${messageClass}">
                        <strong>${role}:</strong>
                        <p>${formatMessageText(msg.content)}</p>
                    </div>
                `;
            });
            
            historyHTML += '</div>';
            historyHTML += `<p class="history-count">Total messages: ${data.count}</p>`;
            
            modalBody.innerHTML = historyHTML;
        } else {
            modalBody.innerHTML = '<p class="no-history">No conversation history yet.</p>';
        }
        
    } catch (error) {
        console.error('Error loading history:', error);
        modalBody.innerHTML = '<p class="error">Failed to load history. Please try again.</p>';
    }
}

function closeHistoryModal() {
    document.getElementById('historyModal').style.display = 'none';
}

// Close modal when clicking outside
window.onclick = function(event) {
    const modal = document.getElementById('historyModal');
    if (event.target === modal) {
        closeHistoryModal();
    }
}