// Donation handling functions
async function handleDonation(projectId, amount) {
    try {
        // First check if MetaMask is installed
        if (typeof window.ethereum === 'undefined') {
            throw new Error('Please install MetaMask to make donations');
        }

        // Request account access
        const accounts = await window.ethereum.request({ method: 'eth_requestAccounts' });
        if (!accounts || accounts.length === 0) {
            throw new Error('Please connect your wallet first');
        }

        // Get transaction data from backend
        const response = await fetch(`/api/donate/${projectId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ amount: parseFloat(amount) })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to prepare transaction');
        }

        const data = await response.json();
        console.log('Transaction data:', data);

        // Send transaction via MetaMask
        const provider = new ethers.BrowserProvider(window.ethereum);
        const signer = await provider.getSigner();
        
        // Prepare and send transaction
        const tx = await signer.sendTransaction({
            to: data.transaction.to,
            data: data.transaction.data,
            value: ethers.parseEther(data.total_amount.toString()),
            gasLimit: data.transaction.gas
        });

        console.log('Transaction sent:', tx);
        
        // Wait for transaction confirmation
        const receipt = await tx.wait();
        console.log('Transaction confirmed:', receipt);

        // Record successful transaction
        const confirmResponse = await fetch(`/api/donate/${projectId}/confirm`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                transaction_hash: receipt.hash,
                amount: data.amount,
                platform_fees: data.platform_fees,
                total_amount: data.total_amount
            })
        });

        if (!confirmResponse.ok) {
            console.error('Failed to confirm transaction with backend');
            return {
                success: true,
                warning: 'Transaction successful but failed to update backend'
            };
        }

        return {
            success: true,
            amount: data.amount
        };

    } catch (error) {
        console.error('Error processing donation:', error);
        let errorMessage = error.message;
        
        // Handle common MetaMask errors
        if (error.code === 4001) {
            errorMessage = 'Transaction was rejected';
        } else if (error.code === -32603) {
            errorMessage = 'Transaction failed. Please check your wallet balance and try again';
        }
        
        throw new Error(errorMessage);
    }
}

function updateProjectUI(projectId, newAmount) {
    // Find all project cards with this ID
    const projectCards = document.querySelectorAll(`[data-project-id="${projectId}"]`);
    
    projectCards.forEach(card => {
        // Get current values
        const fundsRaised = parseFloat(card.dataset.fundsRaised || 0);
        const goalAmount = parseFloat(card.dataset.goalAmount || 1);
        
        // Calculate new values
        const newFundsRaised = fundsRaised + newAmount;
        const newProgress = Math.round((newFundsRaised / goalAmount) * 100);
        
        // Update data attributes
        card.dataset.fundsRaised = newFundsRaised;
        
        // Update display elements
        const progressBar = card.querySelector('.progress-fill');
        const progressText = card.querySelector('.progress-percentage');
        const raisedText = card.querySelector('.raised');
        
        if (progressBar) {
            progressBar.style.width = `${newProgress}%`;
        }
        
        if (progressText) {
            progressText.textContent = `${newProgress}% funded`;
        }
        
        if (raisedText) {
            raisedText.textContent = `${newFundsRaised} AVAX`;
        }
    });
}

async function submitDonation(event) {
    event.preventDefault();
    const modal = document.getElementById('donate-modal');
    const projectId = modal.dataset.projectId;
    const amount = document.getElementById('donationAmount').value;
    
    if (!amount || amount <= 0) {
        showToast('Please enter a valid donation amount', 'error');
        return;
    }

    // Show loading state
    const donateBtn = modal.querySelector('.donate-btn');
    const originalText = donateBtn.innerHTML;
    donateBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>Processing...';
    donateBtn.disabled = true;

    try {
        // Process donation
        const result = await handleDonation(projectId, amount);

        // Close modal and show success message
        modal.style.display = 'none';
        
        if (result.warning) {
            showToast(result.warning, 'warning');
        } else {
            showToast('Donation successful! Thank you for your support.', 'success');
            // Update UI with new donation amount
            updateProjectUI(projectId, parseFloat(amount));
        }

    } catch (error) {
        console.error('Error in submitDonation:', error);
        showToast(error.message, 'error');
    } finally {
        // Reset button state
        donateBtn.innerHTML = originalText;
        donateBtn.disabled = false;
        // Reset the form
        document.getElementById('donationAmount').value = '';
    }
}
