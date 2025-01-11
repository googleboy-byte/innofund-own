const { ethers } = require("hardhat");

async function main() {
    console.log("Starting integration tests on Fuji testnet...");

    // Contract addresses on Fuji
    const REWARD_TOKEN_ADDRESS = "0xA68b3808DCf0Fd8630640018fCB96a28f497F504";
    const PROJECT_DAO_ADDRESS = "0x310BE1F533FFE873743A00aCBB69c22C980c2ECc";
    const FUNDING_CONTRACT_ADDRESS = "0xdC13a4eD2717a7b1E0dE2E55beF927c291A4fA0e";

    // Get contract instances
    const RewardToken = await ethers.getContractFactory("RewardToken");
    const ProjectDAO = await ethers.getContractFactory("ProjectDAO");
    const FundingContract = await ethers.getContractFactory("FundingContract");

    const rewardToken = RewardToken.attach(REWARD_TOKEN_ADDRESS);
    const projectDAO = ProjectDAO.attach(PROJECT_DAO_ADDRESS);
    const fundingContract = FundingContract.attach(FUNDING_CONTRACT_ADDRESS);

    // Get signers
    const [deployer] = await ethers.getSigners();
    console.log("Testing with address:", deployer.address);

    try {
        // Test 1: Create a new project
        console.log("\nTest 1: Creating a new project...");
        const projectName = "Test Project";
        const projectDescription = "A test project for integration testing";
        const fundingGoal = ethers.utils.parseEther("0.1"); // 0.1 AVAX
        const duration = 7200; // 2 hours in seconds

        console.log("Creating project with parameters:");
        console.log("Name:", projectName);
        console.log("Description:", projectDescription);
        console.log("Funding Goal:", ethers.utils.formatEther(fundingGoal), "AVAX");
        console.log("Duration:", duration, "seconds");

        const createTx = await fundingContract.createProject(
            projectName,
            projectDescription,
            fundingGoal,
            duration
        );
        console.log("Transaction hash:", createTx.hash);
        console.log("Waiting for transaction confirmation...");
        
        const createReceipt = await createTx.wait();
        const projectId = createReceipt.events[0].args.projectId;
        console.log("Project created with ID:", projectId.toString());

        // Test 2: Make a contribution
        console.log("\nTest 2: Making a contribution...");
        const contributionAmount = ethers.utils.parseEther("0.05"); // 0.05 AVAX
        console.log("Contributing:", ethers.utils.formatEther(contributionAmount), "AVAX");
        
        const contributeTx = await fundingContract.contribute(projectId, {
            value: contributionAmount
        });
        console.log("Transaction hash:", contributeTx.hash);
        console.log("Waiting for transaction confirmation...");
        
        await contributeTx.wait();
        console.log("Contribution successful");

        // Test 3: Check reward token balance
        console.log("\nTest 3: Checking reward token balance...");
        const tokenBalance = await rewardToken.balanceOf(deployer.address);
        console.log("Reward token balance:", ethers.utils.formatEther(tokenBalance));

        // Test 4: Create a proposal
        console.log("\nTest 4: Creating a proposal...");
        const proposalDescription = "Test proposal for the project";
        const proposalCategory = 0; // GENERAL category
        
        // Create a dummy proposal action
        const targets = [fundingContract.address];
        const values = [0];
        const calldatas = [
            fundingContract.interface.encodeFunctionData("withdrawFunds", [projectId])
        ];
        
        console.log("Creating proposal with parameters:");
        console.log("Description:", proposalDescription);
        console.log("Category:", proposalCategory);
        console.log("Target:", targets[0]);
        
        const createProposalTx = await projectDAO.propose(
            targets,
            values,
            calldatas,
            proposalDescription
        );
        console.log("Transaction hash:", createProposalTx.hash);
        console.log("Waiting for transaction confirmation...");
        
        const proposalReceipt = await createProposalTx.wait();
        const proposalId = proposalReceipt.events[0].args.proposalId;
        console.log("Proposal created with ID:", proposalId.toString());

        // Test 5: Check proposal state and vote
        console.log("\nTest 5: Checking proposal state...");
        const proposalState = await projectDAO.state(proposalId);
        console.log("Proposal state:", proposalState);
        // States: 0=Pending, 1=Active, 2=Canceled, 3=Defeated, 4=Succeeded, 5=Queued, 6=Expired, 7=Executed

        if (proposalState === 0) {
            console.log("Proposal is pending. Waiting for voting delay...");
            // We need to mine some blocks to pass the voting delay
            for(let i = 0; i < 2; i++) {
                await ethers.provider.send("evm_mine", []);
            }
            console.log("Blocks mined. Checking state again...");
            const newState = await projectDAO.state(proposalId);
            console.log("New proposal state:", newState);
        }

        console.log("\nTest 6: Casting vote...");
        const voteTx = await projectDAO.castVote(proposalId, 1); // Vote in favor
        console.log("Transaction hash:", voteTx.hash);
        console.log("Waiting for transaction confirmation...");
        await voteTx.wait();
        console.log("Vote cast successfully");

        // Test 7: Check proposal votes
        console.log("\nTest 7: Checking proposal votes...");
        const votes = await projectDAO.proposalVotes(proposalId);
        console.log("Vote counts:");
        console.log("For:", ethers.utils.formatEther(votes.forVotes));
        console.log("Against:", ethers.utils.formatEther(votes.againstVotes));
        console.log("Abstain:", ethers.utils.formatEther(votes.abstainVotes));

        console.log("\nAll tests completed successfully!");
    } catch (error) {
        console.error("\nError during testing:");
        console.error("Message:", error.message);
        if (error.data) {
            console.error("Contract error data:", error.data);
        }
        if (error.transaction) {
            console.error("Failed transaction:", error.transaction);
        }
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    });
