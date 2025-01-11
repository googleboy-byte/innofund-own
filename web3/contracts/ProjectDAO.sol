// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

import "@openzeppelin/contracts/governance/Governor.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorSettings.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorCountingSimple.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorVotes.sol";
import "@openzeppelin/contracts/governance/extensions/GovernorVotesQuorumFraction.sol";
import "./FundingContract.sol";
import "./RewardToken.sol";

contract ProjectDAO is
    Governor,
    GovernorSettings,
    GovernorCountingSimple,
    GovernorVotes,
    GovernorVotesQuorumFraction
{
    using SafeCast for uint256;
    
    FundingContract public fundingContract;
    RewardToken public rewardToken;
    bool public initialized;
    
    enum ProposalCategory {
        GENERAL,
        FUND_ALLOCATION,
        RESEARCH_DIRECTION,
        EMERGENCY
    }

    struct ProposalDetails {
        ProposalCategory category;
        uint32 requiredQuorum;
        uint32 proposalDelay;
        uint32 proposalPeriod;
    }
    
    mapping(uint256 => ProposalDetails) public proposalDetails;
    mapping(uint256 => uint256) public projectProposals; // projectId => proposalId

    event ProposalCreated(
        uint256 indexed projectId,
        uint256 indexed proposalId,
        string description,
        uint32 deadline
    );

    constructor(address _token)
        Governor("InnoFund DAO")
        GovernorSettings(1, /* 1 block voting delay */ 20, /* ~3 min voting period */ 0)
        GovernorVotes(IVotes(_token))
        GovernorVotesQuorumFraction(4) // 4% quorum
    {
        rewardToken = RewardToken(_token);
    }

    function setFundingContract(address _fundingContract) external {
        require(!initialized, "Already initialized");
        fundingContract = FundingContract(_fundingContract);
        initialized = true;
    }

    function createProjectProposal(
        uint256 projectId,
        string calldata description,
        ProposalCategory category
    ) external returns (uint256) {
        require(initialized, "Not initialized");
        require(rewardToken.balanceOf(msg.sender) >= proposalThreshold(), "Insufficient tokens");
        
        address[] memory targets = new address[](0);
        uint256[] memory values = new uint256[](0);
        bytes[] memory calldatas = new bytes[](0);
        
        uint256 proposalId = super.propose(targets, values, calldatas, description);
        
        // Set proposal details based on category
        uint32 requiredQuorum;
        uint32 proposalDelay;
        uint32 proposalPeriod;
        
        if (category == ProposalCategory.EMERGENCY) {
            requiredQuorum = 10; // 10% quorum
            proposalDelay = 1;   // 1 block
            proposalPeriod = 10; // ~1.5 min
        } else if (category == ProposalCategory.FUND_ALLOCATION) {
            requiredQuorum = 30; // 30% quorum
            proposalDelay = 5;   // ~45 sec
            proposalPeriod = 20; // ~3 min
        } else {
            requiredQuorum = 20; // 20% quorum
            proposalDelay = 3;   // ~30 sec
            proposalPeriod = 15; // ~2.5 min
        }
        
        proposalDetails[proposalId] = ProposalDetails({
            category: category,
            requiredQuorum: requiredQuorum,
            proposalDelay: proposalDelay,
            proposalPeriod: proposalPeriod
        });
        
        projectProposals[projectId] = proposalId;
        
        emit ProposalCreated(
            projectId,
            proposalId,
            description,
            uint32(block.timestamp + proposalPeriod)
        );
        
        return proposalId;
    }

    function getProjectProposal(uint256 projectId) external view returns (uint256) {
        return projectProposals[projectId];
    }

    function propose(
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        string memory description
    ) public override(Governor) returns (uint256) {
        return super.propose(targets, values, calldatas, description);
    }

    function votingDelay()
        public
        view
        override(IGovernor, GovernorSettings)
        returns (uint256)
    {
        return super.votingDelay();
    }

    function votingPeriod()
        public
        view
        override(IGovernor, GovernorSettings)
        returns (uint256)
    {
        return super.votingPeriod();
    }

    function quorum(uint256 blockNumber)
        public
        view
        override(IGovernor, GovernorVotesQuorumFraction)
        returns (uint256)
    {
        return super.quorum(blockNumber);
    }

    function proposalThreshold()
        public
        view
        override(Governor, GovernorSettings)
        returns (uint256)
    {
        return super.proposalThreshold();
    }

    function _getVotes(
        address account,
        uint256 timepoint,
        bytes memory params
    ) internal view override(Governor, GovernorVotes) returns (uint256) {
        uint256 votes = super._getVotes(account, timepoint, params);
        // Implement quadratic voting
        return _sqrt(votes);
    }
    
    function _sqrt(uint256 x) internal pure returns (uint256 y) {
        uint256 z = (x + 1) / 2;
        y = x;
        while (z < y) {
            y = z;
            z = (x / z + z) / 2;
        }
    }

    // Required overrides
    function state(
        uint256 proposalId
    ) public view override(Governor) returns (ProposalState) {
        return super.state(proposalId);
    }

    function _execute(
        uint256 proposalId,
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        bytes32 descriptionHash
    ) internal override(Governor) {
        super._execute(proposalId, targets, values, calldatas, descriptionHash);
    }

    function _cancel(
        address[] memory targets,
        uint256[] memory values,
        bytes[] memory calldatas,
        bytes32 descriptionHash
    ) internal override(Governor) returns (uint256) {
        return super._cancel(targets, values, calldatas, descriptionHash);
    }

    function supportsInterface(bytes4 interfaceId)
        public
        view
        override(Governor)
        returns (bool)
    {
        return super.supportsInterface(interfaceId);
    }
}