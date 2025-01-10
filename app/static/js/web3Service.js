import { ethers } from 'ethers';

const FundingContractABI = require('../../../web3/artifacts/contracts/FundingContract.sol/FundingContract.json').abi;
const ProjectDAOABI = require('../../../web3/artifacts/contracts/ProjectDAO.sol/ProjectDAO.json').abi;
const RewardTokenABI = require('../../../web3/artifacts/contracts/RewardToken.sol/RewardToken.json').abi;

// Load contract addresses from deployment
const contractAddresses = require('../../../web3/contract-addresses.json');

// Avalanche Fuji Testnet Configuration
const AVALANCHE_TESTNET_CONFIG = {
    chainId: '0xA869', // 43113 in hex
    chainName: 'Avalanche Fuji Testnet',
    nativeCurrency: {
        name: 'AVAX',
        symbol: 'AVAX',
        decimals: 18
    },
    rpcUrls: ['https://api.avax-test.network/ext/bc/C/rpc'],
    blockExplorerUrls: ['https://testnet.snowtrace.io/']
};

class Web3Service {
    constructor() {
        this.provider = null;
        this.signer = null;
        this.fundingContract = null;
        this.projectDAO = null;
        this.rewardToken = null;
    }

    async switchToAvalancheTestnet() {
        try {
            // Try to switch to Avalanche testnet
            await window.ethereum.request({
                method: 'wallet_switchEthereumChain',
                params: [{ chainId: AVALANCHE_TESTNET_CONFIG.chainId }],
            });
        } catch (switchError) {
            // This error code indicates that the chain has not been added to MetaMask
            if (switchError.code === 4902) {
                try {
                    await window.ethereum.request({
                        method: 'wallet_addEthereumChain',
                        params: [AVALANCHE_TESTNET_CONFIG],
                    });
                } catch (addError) {
                    console.error('Error adding Avalanche network:', addError);
                    throw new Error('Failed to add Avalanche Fuji Testnet to your wallet. Please try again.');
                }
            } else {
                console.error('Error switching to Avalanche network:', switchError);
                throw new Error('Failed to switch to Avalanche Fuji Testnet. Please try again.');
            }
        }
    }

    async initialize() {
        if (typeof window.ethereum === 'undefined') {
            throw new Error('Please install MetaMask to use this application');
        }

        try {
            // First ensure we're on Avalanche testnet
            await this.switchToAvalancheTestnet();

            // Then initialize provider and contracts
            this.provider = new ethers.BrowserProvider(window.ethereum);
            this.signer = await this.provider.getSigner();
            
            this.fundingContract = new ethers.Contract(
                contractAddresses.FundingContract,
                FundingContractABI,
                this.signer
            );

            this.projectDAO = new ethers.Contract(
                contractAddresses.ProjectDAO,
                ProjectDAOABI,
                this.signer
            );

            this.rewardToken = new ethers.Contract(
                contractAddresses.RewardToken,
                RewardTokenABI,
                this.signer
            );
        } catch (error) {
            console.error('Initialization error:', error);
            throw error;
        }
    }

    async connectWallet() {
        try {
            if (!this.provider) {
                await this.initialize();
            }

            // Request account access
            const accounts = await window.ethereum.request({ 
                method: 'eth_requestAccounts' 
            });

            // Ensure we're on the correct network
            await this.switchToAvalancheTestnet();

            return accounts[0];
        } catch (error) {
            console.error('Wallet connection error:', error);
            throw error;
        }
    }

    // Project Creation
    async createProject(name, description, fundingGoal, deadline) {
        if (!this.fundingContract) await this.initialize();
        
        const tx = await this.fundingContract.createProject(
            name,
            description,
            ethers.parseEther(fundingGoal.toString()),
            Math.floor(new Date(deadline).getTime() / 1000)
        );
        
        const receipt = await tx.wait();
        const event = receipt.logs.find(log => 
            log.topics[0] === ethers.id("ProjectCreated(uint256,string,address,uint96,uint32)")
        );
        
        return event;
    }

    // Project Funding
    async fundProject(projectId, amount) {
        if (!this.fundingContract) {
            throw new Error('Funding contract not initialized');
        }

        try {
            // Convert amount to Wei
            const amountInWei = ethers.parseEther(amount.toString());

            // Call the smart contract's fund function
            const tx = await this.fundingContract.fundProject(projectId, {
                value: amountInWei,
                gasLimit: 300000 // Adjust as needed for Avalanche
            });

            // Wait for transaction confirmation
            const receipt = await tx.wait();

            // Return transaction hash for verification
            return receipt.hash;
        } catch (error) {
            console.error('Funding error:', error);
            throw error;
        }
    }

    async getProjectFunding(projectId) {
        if (!this.fundingContract) {
            throw new Error('Funding contract not initialized');
        }

        try {
            const funding = await this.fundingContract.getProjectFunding(projectId);
            return ethers.formatEther(funding);
        } catch (error) {
            console.error('Error getting project funding:', error);
            throw error;
        }
    }


    async castVote(proposalId, support) {
        if (!this.projectDAO) await this.initialize();
        
        const tx = await this.projectDAO.castVote(proposalId, support);
        return await tx.wait();
    }

    // Token Balance and Transfers
    async getTokenBalance(address) {
        if (!this.rewardToken) await this.initialize();
        
        const balance = await this.rewardToken.balanceOf(address);
        return ethers.formatEther(balance);
    }

    // Project Data
    async getProject(projectId) {
        if (!this.fundingContract) await this.initialize();
        
        const project = await this.fundingContract.projects(projectId);
        return {
            name: project.name,
            description: project.description,
            creator: project.creator,
            fundingGoal: ethers.formatEther(project.fundingGoal),
            currentFunding: ethers.formatEther(project.currentFunding),
            deadline: new Date(project.deadline * 1000),
            funded: project.funded,
            exists: project.exists
        };
    }

    // Event Listeners
    addProjectCreatedListener(callback) {
        this.fundingContract.on("ProjectCreated", callback);
    }

    addProposalCreatedListener(callback) {
        this.projectDAO.on("ProposalCreated", callback);
    }
}

export const web3Service = new Web3Service();
