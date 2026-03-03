package model

import "fmt"

// FindResourceByID searches frontend + backend zones for a resource instance.
// Returns (instance, zone, index) or (nil, "", -1) if not found.
func FindResourceByID(field *Field, instanceID string) (*ResourceInstance, string, int) {
	for i, res := range field.Frontend {
		if res != nil && res.InstanceID == instanceID {
			return res, ZoneFrontend, i
		}
	}
	for i, res := range field.Backend {
		if res != nil && res.InstanceID == instanceID {
			return res, ZoneBackend, i
		}
	}
	return nil, "", -1
}

// HasFrontendResources returns true if any frontend slot has a face-up resource.
func HasFrontendResources(field *Field) bool {
	for _, res := range field.Frontend {
		if res != nil && res.FaceUp {
			return true
		}
	}
	return false
}

// CalculateEffectiveAV computes the current effective availability.
func CalculateEffectiveAV(instance *ResourceInstance) int64 {
	return instance.MaxAV - instance.Damage
}

// CreateResourceInstance creates a ResourceInstance from a CardDefinition at rank small.
// FaceUp is determined by the card's DeployTurns: 0 = immediate (face-up), >0 = deploying (face-down).
func CreateResourceInstance(card *CardDefinition, instanceID string) (*ResourceInstance, error) {
	faceUp := card.DeployTurns == 0
	res := &ResourceInstance{
		InstanceID:         instanceID,
		CardID:             card.CardNo,
		Rank:               RankSmall,
		FaceUp:             faceUp,
		DeployingTurnsLeft: card.DeployTurns,
		Attachments:        []AttachmentRef{},
		TemporaryEffects:   []TemporaryEffect{},
	}

	if IsComputeType(card.CardType) {
		stats, err := ParseComputeStats(card.Stats)
		if err != nil {
			return nil, fmt.Errorf("parse compute stats for card %d: %w", card.CardNo, err)
		}
		res.CurrentAV = stats.Availability
		res.MaxAV = stats.Availability
		tp := stats.Throughput
		res.CurrentTP = &tp
		if !card.Elastic {
			maxTP := stats.Throughput
			if stats.ThroughputMax != nil {
				maxTP = *stats.ThroughputMax
			}
			res.MaxTP = &maxTP
		}
	} else if IsDataType(card.CardType) {
		stats, err := ParseDataStats(card.Stats)
		if err != nil {
			return nil, fmt.Errorf("parse data stats for card %d: %w", card.CardNo, err)
		}
		res.CurrentAV = stats.Availability
		res.MaxAV = stats.Availability
		yieldVal := stats.Yield
		res.CurrentYield = &yieldVal
		if !card.Elastic {
			maxYield := stats.Yield
			if stats.YieldMax != nil {
				maxYield = *stats.YieldMax
			}
			res.MaxYield = &maxYield
		}
	}

	return res, nil
}

// RankMultiplier returns 1, 2, or 3 for small, medium, large.
func RankMultiplier(rank string) int64 {
	switch rank {
	case RankSmall:
		return 1
	case RankMedium:
		return 2
	case RankLarge:
		return 3
	default:
		return 1
	}
}
