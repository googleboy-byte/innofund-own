const hre = require("hardhat");

async function main() {
    // Deploy RewardToken
    const RewardToken = await hre.ethers.getContractFactory("RewardToken");
    const rewardToken = await RewardToken.deploy("InnoFund Token");
    await rewardToken.deployed();
    console.log("RewardToken deployed to:", rewardToken.address);

    // Deploy ProjectDAO with RewardToken
    const ProjectDAO = await hre.ethers.getContractFactory("ProjectDAO");
    const projectDAO = await ProjectDAO.deploy(
        rewardToken.address,    // token address for voting
        rewardToken.address     // for constructor
    );
    await projectDAO.deployed();
    console.log("ProjectDAO deployed to:", projectDAO.address);

    // Deploy FundingContract with both RewardToken and ProjectDAO
    const FundingContract = await hre.ethers.getContractFactory("FundingContract");
    const fundingContract = await FundingContract.deploy(rewardToken.address, projectDAO.address);
    await fundingContract.deployed();
    console.log("FundingContract deployed to:", fundingContract.address);

    // Transfer ownership of RewardToken to FundingContract
    await rewardToken.transferOwnership(fundingContract.address);
    console.log("RewardToken ownership transferred to FundingContract");

    // Verify contracts on Snowtrace (Avalanche's block explorer)
    if (network.name === "fuji" || network.name === "avalanche") {
        console.log("Waiting for block confirmations...");
        await rewardToken.deployTransaction.wait(6); // Wait for 6 block confirmations
        await projectDAO.deployTransaction.wait(6);
        await fundingContract.deployTransaction.wait(6);

        console.log("Verifying contracts on Snowtrace...");
        
        await hre.run("verify:verify", {
            address: rewardToken.address,
            constructorArguments: ["InnoFund Token"],
        });

        await hre.run("verify:verify", {
            address: projectDAO.address,
            constructorArguments: [rewardToken.address, rewardToken.address],
        });

        await hre.run("verify:verify", {
            address: fundingContract.address,
            constructorArguments: [rewardToken.address, projectDAO.address],
        });
    }
}

main()
    .then(() => process.exit(0))
    .catch((error) => {
        console.error(error);
        process.exit(1);
    }); 