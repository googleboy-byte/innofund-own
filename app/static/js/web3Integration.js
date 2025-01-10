import { web3Service } from './web3Service.js';

// Connect wallet button handler
async function connectWallet() {
    const connectButton = document.querySelector('.wallet:not(.connected)');
    if (connectButton) {
        connectButton.disabled = true;
        connectButton.textContent = 'Connecting...';
    }
    
    try {
        const address = await web3Service.connectWallet();
        
        // Update the backend with the wallet address
        const response = await fetch('/update_wallet', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ wallet_address: address })
        });
        
        if (response.ok) {
            showToast('Wallet connected successfully!', 'success');
            location.reload();
        } else {
            throw new Error('Failed to update wallet address on server');
        }
    } catch (error) {
        console.error('Error connecting wallet:', error);
        let errorMessage = 'Failed to connect wallet. ';
        
        if (error.message.includes('Please install MetaMask')) {
            errorMessage = 'Please install MetaMask to use this application.';
        } else if (error.message.includes('Fuji Testnet')) {
            errorMessage = error.message;
        } else {
            errorMessage += 'Please try again.';
        }
        
        showToast(errorMessage, 'error');
    } finally {
        if (connectButton) {
            connectButton.disabled = false;
            connectButton.textContent = 'Connect Wallet';
        }
    }
}

// Project creation handler
async function createProject(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    
    try {
        // Create project on blockchain
        const event = await web3Service.createProject(
            formData.get('name'),
            formData.get('description'),
            formData.get('funding_goal'),
            formData.get('deadline')
        );
        
        // Add blockchain project ID to form data
        formData.append('blockchain_project_id', event.args.projectId.toString());
        
        // Submit to backend
        const response = await fetch(form.action, {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            window.location.href = '/dashboard';
        }
    } catch (error) {
        console.error('Error creating project:', error);
        alert('Failed to create project. Please try again.');
    }
}

// Project funding handler
async function fundProject(projectId, amount) {
    try {
        await web3Service.fundProject(projectId, amount);
        
        // Update backend
        const response = await fetch(`/fund_project/${projectId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ amount: amount })
        });
        
        if (response.ok) {
            location.reload();
        }
    } catch (error) {
        console.error('Error funding project:', error);
        alert('Failed to fund project. Please try again.');
    }
}

// Proposal creation handler
async function createProposal(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    
    try {
        // Create proposal on blockchain
        const receipt = await web3Service.createProposal(
            formData.get('project_id'),
            formData.get('description')
        );
        
        // Add blockchain proposal ID to form data
        const proposalId = receipt.logs[0].args.proposalId.toString();
        formData.append('blockchain_proposal_id', proposalId);
        
        // Submit to backend
        const response = await fetch(form.action, {
            method: 'POST',
            body: formData
        });
        
        if (response.ok) {
            window.location.href = `/project/${formData.get('project_id')}`;
        }
    } catch (error) {
        console.error('Error creating proposal:', error);
        alert('Failed to create proposal. Please try again.');
    }
}

async function handleDonation(projectId, amount) {
    try {
        // Show loading state
        const donateButton = document.querySelector('#donate-button');
        const originalText = donateButton.textContent;
        donateButton.disabled = true;
        donateButton.textContent = 'Processing...';

        // First, get transaction data from backend
        const response = await fetch(`/api/donate/${projectId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ amount: amount })
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to prepare transaction');
        }

        const data = await response.json();
        
        // Execute the blockchain transaction
        const provider = new ethers.BrowserProvider(window.ethereum);
        const signer = await provider.getSigner();
        
        // Send the transaction
        const tx = await signer.sendTransaction({
            to: data.transaction.to,
            data: data.transaction.data,
            value: ethers.parseEther(data.total_amount.toString()),
            gasLimit: data.transaction.gas,
            chainId: data.transaction.chainId
        });

        // Show pending state
        donateButton.textContent = 'Transaction Pending...';
        showToast('Transaction submitted! Waiting for confirmation...', 'info');

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
            showToast('Transaction successful but failed to update backend', 'warning');
        } else {
            // Show success message
            showToast('Donation successful! Funds have been transferred.', 'success');
        }
        
        // Reload page after a short delay
        setTimeout(() => {
            window.location.reload();
        }, 2000);

    } catch (error) {
        console.error('Donation error:', error);
        showToast(error.message || 'Failed to process donation', 'error');
    } finally {
        // Reset button state
        if (donateButton) {
            donateButton.disabled = false;
            donateButton.textContent = originalText;
        }
    }
}

// Proposal voting handler
async function castVote(proposalId, support) {
    try {
        await web3Service.castVote(proposalId, support);
        
        // Update backend
        const response = await fetch(`/vote/${proposalId}`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ support: support })
        });
        
        if (response.ok) {
            location.reload();
        }
    } catch (error) {
        console.error('Error casting vote:', error);
        alert('Failed to cast vote. Please try again.');
    }
}

// Initialize Web3 event listeners
document.addEventListener('DOMContentLoaded', async () => {
    try {
        await web3Service.initialize();
        
        // Listen for project creation events
        web3Service.addProjectCreatedListener((projectId, name, creator, fundingGoal, deadline) => {
            console.log('New project created:', { projectId, name, creator, fundingGoal, deadline });
        });
        
        // Listen for proposal creation events
        web3Service.addProposalCreatedListener((projectId, proposalId, description, deadline) => {
            console.log('New proposal created:', { projectId, proposalId, description, deadline });
        });
        
        // Add event listeners to buttons and forms
        const connectWalletBtn = document.querySelector('.wallet:not(.connected)');
        if (connectWalletBtn) {
            connectWalletBtn.addEventListener('click', connectWallet);
        }
        
        const createProjectForm = document.getElementById('create-project-form');
        if (createProjectForm) {
            createProjectForm.addEventListener('submit', createProject);
        }
        
        const createProposalForm = document.getElementById('create-proposal-form');
        if (createProposalForm) {
            createProposalForm.addEventListener('submit', createProposal);
        }
    } catch (error) {
        console.error('Error initializing Web3:', error);
    }
});
