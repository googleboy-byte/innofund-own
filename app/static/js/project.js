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