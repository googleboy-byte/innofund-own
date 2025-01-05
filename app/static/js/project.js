function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.innerHTML = `
        <div class="toast-content">
            <i class="fas ${type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}"></i>
            <span>${message}</span>
        </div>
        <button onclick="this.parentElement.remove()" class="toast-close">&times;</button>
    `;
    document.body.appendChild(toast);
    
    // Animate in
    setTimeout(() => toast.classList.add('show'), 10);
    
    // Auto dismiss after 5 seconds
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 5000);
}

function deactivateProject(projectId) {
    const modal = document.getElementById('deactivateModal');
    modal.style.display = 'block';
}

function closeDeactivateModal() {
    const modal = document.getElementById('deactivateModal');
    modal.style.display = 'none';
}

async function confirmDeactivate(projectId) {
    try {
        const response = await fetch(`/deactivate-project/${projectId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            }
        });
        
        if (!response.ok) {
            throw new Error('Network response was not ok');
        }
        
        const result = await response.json();
        if (result.success) {
            showToast('Project deactivated successfully', 'success');
            setTimeout(() => location.reload(), 2000);
        } else {
            throw new Error(result.error || 'Failed to deactivate project');
        }
    } catch (error) {
        console.error('Deactivation error:', error);
        showToast(error.message, 'error');
    } finally {
        closeDeactivateModal();
    }
}

// Share project functions
function shareProject(platform) {
    const url = window.location.href;
    const title = document.querySelector('.project-main-info h1').textContent;
    
    switch(platform) {
        case 'twitter':
            window.open(`https://twitter.com/intent/tweet?text=${encodeURIComponent(title)}&url=${encodeURIComponent(url)}`, '_blank');
            break;
        case 'linkedin':
            window.open(`https://www.linkedin.com/sharing/share-offsite/?url=${encodeURIComponent(url)}`, '_blank');
            break;
    }
}

function copyProjectLink() {
    const url = window.location.href;
    navigator.clipboard.writeText(url).then(() => {
        // Show toast notification
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = 'Link copied to clipboard!';
        document.body.appendChild(toast);
        
        // Trigger animation
        setTimeout(() => toast.classList.add('show'), 10);
        
        // Remove toast after 3 seconds
        setTimeout(() => {
            toast.classList.remove('show');
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }).catch(err => {
        console.error('Failed to copy:', err);
        alert('Failed to copy link to clipboard');
    });
}

// Close modals when clicking outside or pressing escape
window.addEventListener('click', function(event) {
    const deactivateModal = document.getElementById('deactivateModal');
    if (event.target === deactivateModal) {
        closeDeactivateModal();
    }
});

document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        closeDeactivateModal();
    }
});

async function voteProject(projectId, voteType) {
    try {
        const response = await fetch(`/api/vote/${projectId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ vote_type: voteType })
        });
        
        if (response.status === 401) {
            showToast('Please log in to vote', 'error');
            return;
        }
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.error || 'Network response was not ok');
        }
        
        const result = await response.json();
        if (result.success) {
            // Update vote counts
            document.getElementById(`upvote-count-${projectId}`).textContent = result.upvotes;
            document.getElementById(`downvote-count-${projectId}`).textContent = result.downvotes;
            
            // Update button states
            const upvoteBtn = document.querySelector(`.upvote[onclick*="${projectId}"]`);
            const downvoteBtn = document.querySelector(`.downvote[onclick*="${projectId}"]`);
            
            upvoteBtn.classList.toggle('voted', result.user_vote === 'up');
            downvoteBtn.classList.toggle('voted', result.user_vote === 'down');
            
            // Show success message only when vote changes
            if (result.user_vote !== null) {
                showToast('Vote recorded successfully', 'success');
            }
        } else {
            throw new Error(result.error || 'Failed to record vote');
        }
    } catch (error) {
        console.error('Voting error:', error);
        showToast(error.message, 'error');
    }
}

let currentProjectId = null;

function showReportModal(projectId) {
    currentProjectId = projectId;
    const modal = document.getElementById('reportModal');
    modal.style.display = 'block';
    document.body.style.overflow = 'hidden';  // Prevent background scrolling
}

function closeReportModal() {
    const modal = document.getElementById('reportModal');
    modal.style.display = 'none';
    document.body.style.overflow = '';  // Restore scrolling
    document.getElementById('reportForm').reset();
}

// Add event listener for the report form
document.getElementById('reportForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const reason = document.getElementById('reportReason').value;
    const details = document.getElementById('reportDetails').value;
    
    try {
        const response = await fetch('/report_project', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                project_id: currentProjectId,
                reason: reason,
                details: details
            })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showToast('Thank you for your report. Our team will review it shortly.', 'success');
            closeReportModal();
        } else {
            showToast(data.error || 'Failed to submit report. Please try again.', 'error');
        }
    } catch (error) {
        console.error('Error submitting report:', error);
        showToast('An error occurred while submitting the report. Please try again.', 'error');
    }
});

// Add event listener for report button
document.addEventListener('DOMContentLoaded', function() {
    const reportBtn = document.querySelector('.report-btn');
    if (reportBtn) {
        reportBtn.addEventListener('click', function() {
            const isAuthenticated = this.dataset.authenticated === 'true';
            if (isAuthenticated) {
                showReportModal(this.dataset.projectId);
            } else {
                showToast('Please log in to report projects', 'error');
            }
        });
    }
});

// Modal functions
function showDonateModal(projectId, projectTitle) {
    console.log('Opening donate modal for project:', projectId, projectTitle); // Debug log
    const modal = document.getElementById('donate-modal');
    if (!modal) {
        console.error('Donate modal not found!');
        return;
    }
    
    modal.dataset.projectId = projectId;
    modal.style.display = 'block';
    document.getElementById('donationAmount').value = '';  // Reset the input
}

function closeModal() {
    const modal = document.getElementById('donate-modal');
    if (modal) {
        modal.style.display = 'none';
    }
}

// Initialize modal event listeners
document.addEventListener('DOMContentLoaded', function() {
    console.log('Initializing modal event listeners'); // Debug log
    
    // Close button
    const closeBtn = document.querySelector('#donate-modal .close');
    if (closeBtn) {
        closeBtn.onclick = closeModal;
    }

    // Click outside modal
    const modal = document.getElementById('donate-modal');
    if (modal) {
        window.onclick = function(event) {
            if (event.target === modal) {
                closeModal();
            }
        };
    }

    // Escape key
    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeModal();
        }
    });

    // Initialize toast container
    if (!document.getElementById('toast-container')) {
        const toastContainer = document.createElement('div');
        toastContainer.id = 'toast-container';
        document.body.appendChild(toastContainer);
    }
});

// Donation submission handler
async function submitDonation(event) {
    event.preventDefault();
    const modal = document.getElementById('donate-modal');
    const projectId = modal.dataset.projectId;
    const amount = parseFloat(document.getElementById('donationAmount').value);
    
    if (amount <= 0 || isNaN(amount)) {
        showToast('Please enter a valid amount', 'error');
        return;
    }

    try {
        const response = await fetch(`/update-project-funds/${projectId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({ amount })
        });
        
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        
        const result = await response.json();
        if (result.success) {
            closeModal();
            showToast('Donation successful! Thank you for your support.', 'success');
            setTimeout(() => location.reload(), 2000);
        } else {
            throw new Error(result.error || 'Donation failed');
        }
    } catch (error) {
        console.error('Donation error:', error);
        showToast(error.message, 'error');
    }
} 