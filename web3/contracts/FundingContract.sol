// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/access/Ownable.sol";
import "@openzeppelin/contracts/utils/math/SafeMath.sol";
import "./RewardToken.sol";
import "./interfaces/IProjectDAO.sol";

contract FundingContract is Ownable {
    using SafeMath for uint256;
    
    struct Project {
        string name;
        string description;
        address payable creator;
        uint96 fundingGoal;    // Reduce from uint256 (max ~79K ETH is enough)
        uint96 currentFunding; // Reduce from uint256
        uint32 deadline;       // Reduce from uint256 (timestamp until 2106 is enough)
        bool funded;
        bool exists;
    }

    struct Contribution {
        uint96 amount;   // Reduce from uint256
        uint32 timestamp; // Reduce from uint256
    }

    RewardToken public immutable rewardToken;
    address public immutable projectDAO;
    address public platformFeeAddress;
    uint256 public platformFeePercentage = 275; // 2.75% (275/10000)
    
    mapping(uint256 => Project) public projects;
    mapping(uint256 => mapping(address => Contribution[])) public contributions;
    mapping(uint256 => address[]) public projectContributors;
    
    uint256 private nextProjectId;
    
    // Constants - reduced for testing
    uint96 public constant MIN_FUNDING_GOAL = 0.01 ether;
    uint32 public constant MAX_FUNDING_PERIOD = 1 days;
    uint96 public constant TOKEN_REWARD_RATE = 100; // tokens per ETH contributed
    
    event ProjectCreated(
        uint256 indexed projectId,
        string name,
        address indexed creator,
        uint96 fundingGoal,
        uint32 deadline
    );
    
    event ContributionMade(
        uint256 indexed projectId,
        address indexed contributor,
        uint96 amount,
        uint32 timestamp
    );
    
    event ProjectFunded(uint256 indexed projectId, uint96 totalAmount);
    event FundsWithdrawn(uint256 indexed projectId, address indexed creator, uint96 amount);
    event PlatformFeeCollected(uint256 indexed projectId, uint96 amount);
    
    constructor(address _rewardToken, address _projectDAO) {
        rewardToken = RewardToken(_rewardToken);
        projectDAO = _projectDAO;
        platformFeeAddress = 0xe87758C6CCcf3806C9f1f0C8F99f6Dcae36E5449;
    }
    
    function createProject(
        string calldata _name,
        string calldata _description,
        uint96 _fundingGoal,
        uint32 _duration
    ) external returns (uint256) {
        require(_fundingGoal >= MIN_FUNDING_GOAL, "Goal < min");
        require(_duration <= MAX_FUNDING_PERIOD, "Duration > max");
        
        uint256 projectId = nextProjectId++;
        uint32 deadline = uint32(block.timestamp + _duration);
        
        projects[projectId] = Project({
            name: _name,
            description: _description,
            creator: payable(msg.sender),
            fundingGoal: _fundingGoal,
            currentFunding: 0,
            deadline: deadline,
            funded: false,
            exists: true
        });
        
        emit ProjectCreated(projectId, _name, msg.sender, _fundingGoal, deadline);
        return projectId;
    }
    
    function contribute(uint256 _projectId) external payable {
        Project storage project = projects[_projectId];
        require(project.exists, "Not found");
        require(block.timestamp < project.deadline, "Ended");
        require(msg.value > 0, "Zero value");
        
        uint96 amount = uint96(msg.value);
        
        // Calculate platform fee
        uint96 platformFee = uint96((uint256(amount) * platformFeePercentage) / 10000);
        uint96 projectAmount = amount - platformFee;
        
        // Send platform fee
        (bool feeSuccess, ) = payable(platformFeeAddress).call{value: platformFee}("");
        require(feeSuccess, "Fee transfer failed");
        emit PlatformFeeCollected(_projectId, platformFee);
        
        // Send remaining amount to project
        project.currentFunding += projectAmount;
        (bool success, ) = project.creator.call{value: projectAmount}("");
        require(success, "Transfer failed");
        
        // Record contribution
        contributions[_projectId][msg.sender].push(Contribution({
            amount: amount,
            timestamp: uint32(block.timestamp)
        }));
        
        // Add contributor to list if first contribution
        if (contributions[_projectId][msg.sender].length == 1) {
            projectContributors[_projectId].push(msg.sender);
        }
        
        // Mint reward tokens
        uint256 tokenAmount = uint256(amount) * TOKEN_REWARD_RATE;
        rewardToken.mint(msg.sender, tokenAmount);
        
        emit ContributionMade(_projectId, msg.sender, amount, uint32(block.timestamp));
        
        // Check if funding goal is reached
        if (project.currentFunding >= project.fundingGoal && !project.funded) {
            project.funded = true;
            emit ProjectFunded(_projectId, project.currentFunding);
        }
    }
    
    function createProposal(uint256 _projectId, string memory _description) external {
        Project storage project = projects[_projectId];
        require(project.exists, "Project does not exist");
        require(project.funded, "Project not funded");
        
        uint256 proposalId = IProjectDAO(projectDAO).createProjectProposal(
            _projectId,
            _description,
            IProjectDAO.ProposalCategory.GENERAL
        );
        
        require(proposalId > 0, "Failed to create proposal");
    }
    
    function getProjectVotes(uint256 _projectId) external view returns (
        uint256 againstVotes,
        uint256 forVotes,
        uint256 abstainVotes
    ) {
        Project storage project = projects[_projectId];
        require(project.exists, "Project does not exist");
        
        uint256 proposalId = IProjectDAO(projectDAO).getProjectProposal(_projectId);
        require(proposalId > 0, "No proposal exists for project");
        
        return (0, 0, 0); // Placeholder - implement actual vote counting
    }
    
    function withdrawFunds(uint256 _projectId) external {
        Project storage project = projects[_projectId];
        require(project.exists, "Not found");
        require(project.funded, "Not funded");
        require(msg.sender == project.creator, "Not creator");
        
        uint96 amount = project.currentFunding;
        project.currentFunding = 0;
        (bool success, ) = payable(project.creator).call{value: amount}("");
        require(success, "Transfer failed");
        
        emit FundsWithdrawn(_projectId, project.creator, amount);
    }
    
    function getProject(uint256 _projectId) external view returns (
        string memory name,
        string memory description,
        address creator,
        uint96 fundingGoal,
        uint96 currentFunding,
        uint32 deadline,
        bool funded,
        bool exists
    ) {
        Project storage project = projects[_projectId];
        return (
            project.name,
            project.description,
            project.creator,
            project.fundingGoal,
            project.currentFunding,
            project.deadline,
            project.funded,
            project.exists
        );
    }
    
    function getContributions(uint256 _projectId, address _contributor) external view returns (Contribution[] memory) {
        return contributions[_projectId][_contributor];
    }
    
    function getContributors(uint256 _projectId) external view returns (address[] memory) {
        return projectContributors[_projectId];
    }
}