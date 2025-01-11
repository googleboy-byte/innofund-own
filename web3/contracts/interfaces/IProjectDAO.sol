// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

interface IProjectDAO {
    enum ProposalCategory {
        FUNDING_REQUEST,
        MILESTONE_REVIEW,
        GENERAL
    }

    function createProjectProposal(
        uint256 projectId,
        string calldata description,
        ProposalCategory category
    ) external returns (uint256);

    function getProjectProposal(uint256 projectId) external view returns (uint256);
}
