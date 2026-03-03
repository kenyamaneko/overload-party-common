package model

import "encoding/json"

// ComputeStats for Compute, Container, Orchestrator, Serverless, AI/ML card types.
type ComputeStats struct {
	Throughput      int64  `json:"throughput"`
	ThroughputMax   *int64 `json:"throughput_max,omitempty"`
	Availability    int64  `json:"availability"`
	MaintenanceCost int64  `json:"maintenance_cost"`
	SLAPenalty      int64  `json:"sla_penalty"`
}

// DataStats for Database, ObjectStorage, CacheDB card types.
type DataStats struct {
	Yield           int64  `json:"yield"`
	YieldMax        *int64 `json:"yield_max,omitempty"`
	Availability    int64  `json:"availability"`
	MaintenanceCost int64  `json:"maintenance_cost"`
	SLAPenalty      int64  `json:"sla_penalty"`
}

// IsComputeType returns true if the card type is a compute-type resource.
// Compute types: Compute, Container, Orchestrator, Serverless (excludes AI/ML).
func IsComputeType(cardType string) bool {
	switch cardType {
	case "Compute", "Container", "Orchestrator", "Serverless":
		return true
	}
	return false
}

// IsAIMLType returns true if the card type is an AI/ML resource.
func IsAIMLType(cardType string) bool {
	return cardType == "AI/ML"
}

// IsDBType returns true if the card type is a DB-type resource (Yield generation).
// DB types: Database, CacheDB
func IsDBType(cardType string) bool {
	switch cardType {
	case "Database", "CacheDB":
		return true
	}
	return false
}

// IsStorageType returns true if the card type is ObjectStorage.
func IsStorageType(cardType string) bool {
	return cardType == "ObjectStorage"
}

// IsDataType returns true if the card type belongs to the data system (DB or ObjectStorage).
// This includes both DB types and ObjectStorage.
func IsDataType(cardType string) bool {
	return IsDBType(cardType) || IsStorageType(cardType)
}

// IsResourceType returns true if the card type is a deployable resource (compute, AI/ML, or data).
func IsResourceType(cardType string) bool {
	return IsComputeType(cardType) || IsAIMLType(cardType) || IsDataType(cardType)
}

// IsFrontendEligible returns true if the card can be placed in the frontend zone.
// Compute and AI/ML types attack from frontend; ObjectStorage can be placed as a wall (no yield, no attack).
func IsFrontendEligible(cardType string) bool {
	return IsComputeType(cardType) || IsAIMLType(cardType) || cardType == "ObjectStorage"
}

// IsBackendEligible returns true if the card can be placed in the backend zone.
// Data types generate Insight; Compute and AI/ML types convert Insight to Budget (monetize).
func IsBackendEligible(cardType string) bool {
	return IsDataType(cardType) || IsComputeType(cardType) || IsAIMLType(cardType)
}

// IsSupportType returns true if the card goes in the support zone.
// Attachment cards are NOT support — they attach directly to resources.
func IsSupportType(cardType string) bool {
	switch cardType {
	case "Platform", "Strategy", "Incident", "Reactive":
		return true
	}
	return false
}

// IsAttachmentType returns true if the card is an Attachment.
func IsAttachmentType(cardType string) bool {
	return cardType == "Attachment"
}

// IsImmediateType returns true if the card is used immediately and goes to trash.
func IsImmediateType(cardType string) bool {
	switch cardType {
	case "Strategy", "Incident":
		return true
	}
	return false
}

// ParseComputeStats parses Stats JSON for compute-type cards.
func ParseComputeStats(raw json.RawMessage) (*ComputeStats, error) {
	var s ComputeStats
	if err := json.Unmarshal(raw, &s); err != nil {
		return nil, err
	}
	return &s, nil
}

// ParseDataStats parses Stats JSON for data-type cards.
func ParseDataStats(raw json.RawMessage) (*DataStats, error) {
	var s DataStats
	if err := json.Unmarshal(raw, &s); err != nil {
		return nil, err
	}
	return &s, nil
}

// MaintenanceCostFor returns the maintenance cost for a resource card (0 for non-resource cards).
func MaintenanceCostFor(card *CardDefinition) int64 {
	if IsComputeType(card.CardType) || IsAIMLType(card.CardType) {
		stats, err := ParseComputeStats(card.Stats)
		if err != nil {
			return 0
		}
		return stats.MaintenanceCost
	}
	if IsDataType(card.CardType) {
		stats, err := ParseDataStats(card.Stats)
		if err != nil {
			return 0
		}
		return stats.MaintenanceCost
	}
	return 0
}

