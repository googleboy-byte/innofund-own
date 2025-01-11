const hre = require("hardhat");

async function main() {
  const [deployer] = await hre.ethers.getSigners();
  console.log("Deploying contracts with the account:", deployer.address);

  // Deploy RewardToken
  console.log("Deploying RewardToken...");
  const RewardToken = await hre.ethers.getContractFactory("RewardToken");
  const rewardToken = await RewardToken.deploy("InnoFund Token");
  await rewardToken.deployed();
  console.log("RewardToken deployed to:", rewardToken.address);

  // Deploy ProjectDAO with RewardToken
  console.log("Deploying ProjectDAO...");
  const ProjectDAO = await hre.ethers.getContractFactory("ProjectDAO");
  const projectDAO = await ProjectDAO.deploy(rewardToken.address);
  await projectDAO.deployed();
  console.log("ProjectDAO deployed to:", projectDAO.address);

  // Deploy FundingContract
  console.log("Deploying FundingContract...");
  const FundingContract = await hre.ethers.getContractFactory("FundingContract");
  const fundingContract = await FundingContract.deploy(
    rewardToken.address,
    projectDAO.address
  );
  await fundingContract.deployed();
  console.log("FundingContract deployed to:", fundingContract.address);

  // Set FundingContract in ProjectDAO
  console.log("Setting FundingContract in ProjectDAO...");
  await projectDAO.setFundingContract(fundingContract.address);
  console.log("FundingContract set in ProjectDAO");

  // Set up permissions
  console.log("Setting up permissions...");
  await rewardToken.transferOwnership(fundingContract.address);
  console.log("Transferred RewardToken ownership to FundingContract");

  // Save contract addresses
  const fs = require("fs");
  const contractAddresses = {
    rewardToken: rewardToken.address,
    projectDAO: projectDAO.address,
    fundingContract: fundingContract.address,
  };

  // Save to both web3 and client directories
  fs.writeFileSync(
    "contract-addresses.json",
    JSON.stringify(contractAddresses, null, 2)
  );
  
  // Also save to client directory for frontend
  const clientPath = "../client/src/contracts/addresses.json";
  fs.writeFileSync(
    clientPath,
    JSON.stringify(contractAddresses, null, 2)
  );
  
  console.log("Contract addresses saved to contract-addresses.json and client/src/contracts/addresses.json");
}

main()
  .then(() => process.exit(0))
  .catch((error) => {
    console.error(error);
    process.exit(1);
  });
