package model

// PassiveEffectType represents the type of passive effect a card has.
type PassiveEffectType string

const (
	// TP Bonuses
	PassiveTPPerBackendDB      PassiveEffectType = "tp_per_backend_db"        // TP bonus per backend DB only (Database, CacheDB)
	PassiveTPPerBackendData    PassiveEffectType = "tp_per_backend_data"      // TP bonus per backend data (DB + ObjectStorage) (e.g., #27 Tenki Opener)
	PassiveTPIfCardTypeOnField PassiveEffectType = "tp_if_card_type_on_field" // TP bonus if specific card type exists (e.g., #6 ラム, #76 APEX)

	// Yield Bonuses
	PassiveYieldPerOtherDB    PassiveEffectType = "dv_per_other_db"     // Yield bonus per other DB (e.g., #8 SD DestributedDB - オオロバ)
	PassiveYieldIfCardOnField PassiveEffectType = "dv_if_card_on_field" // Yield bonus if specific card exists (e.g., #10 SD DB - ダイナ)

	// AV Bonuses (future)
	PassiveAVBonus PassiveEffectType = "av_bonus"

	// Scale Cost Reduction
	PassiveScaleCostFree PassiveEffectType = "scale_cost_free" // Scale cost is free (e.g., #74 Always Free)
)

// PlatformEffectType represents effects that Platform cards provide to other cards.
type PlatformEffectType string

const (
	PlatformTPBonus             PlatformEffectType = "tp_bonus"
	PlatformYieldBonus          PlatformEffectType = "yield_bonus"
	PlatformAVBonus             PlatformEffectType = "av_bonus"
)

// AttachmentEffectType represents effects that Attachment cards provide to their host.
type AttachmentEffectType string

const (
	AttachmentStatBonus AttachmentEffectType = "stat_bonus" // Generic stat bonus (TP, Yield, AV)
)

// PassiveEffect defines a card's passive (continuous) effect.
type PassiveEffect struct {
	Type   PassiveEffectType      `json:"type"`
	Params map[string]interface{} `json:"params"`
}

// PlatformEffect defines effects a Platform card provides to ally cards.
type PlatformEffect struct {
	Type   PlatformEffectType     `json:"type"`
	Params map[string]interface{} `json:"params"`
}

// AttachmentEffect defines effects an Attachment provides to its host.
type AttachmentEffect struct {
	Type   AttachmentEffectType   `json:"type"`
	Params map[string]interface{} `json:"params"`
}

// PassiveEffectConfig stores the configuration for a passive effect.
type PassiveEffectConfig struct {
	// Common params
	Faction      string   `json:"faction,omitempty"`        // Filter by faction (e.g., "Tenki")
	CardTypes    []string `json:"card_types,omitempty"`     // Filter by card types (e.g., ["Database"])
	BonusPerCard int64    `json:"bonus_per_card,omitempty"` // Bonus amount per card
	FlatBonus    int64    `json:"flat_bonus,omitempty"`     // Flat bonus amount

	// Special handling
	MultiModelCards []int64 `json:"multi_model_cards,omitempty"` // Cards that count as 2 (e.g., [32])
	SpecificCardNos []int64 `json:"specific_card_nos,omitempty"` // Specific card numbers to check
	Zone            string  `json:"zone,omitempty"`              // "backend", "frontend", "" (any)
	ExcludeSelf     bool    `json:"exclude_self,omitempty"`      // Exclude the card itself from counting
}

// GetPassiveConfig parses the Params map into a typed config.
func (pe *PassiveEffect) GetConfig() *PassiveEffectConfig {
	cfg := &PassiveEffectConfig{}

	if faction, ok := pe.Params["faction"].(string); ok {
		cfg.Faction = faction
	}
	if cardTypes, ok := pe.Params["card_types"].([]interface{}); ok {
		for _, ct := range cardTypes {
			if s, ok := ct.(string); ok {
				cfg.CardTypes = append(cfg.CardTypes, s)
			}
		}
	}
	if bonus, ok := pe.Params["bonus_per_card"].(float64); ok {
		cfg.BonusPerCard = int64(bonus)
	}
	if bonus, ok := pe.Params["flat_bonus"].(float64); ok {
		cfg.FlatBonus = int64(bonus)
	}
	if multiModel, ok := pe.Params["multi_model_cards"].([]interface{}); ok {
		for _, id := range multiModel {
			if idNum, ok := id.(float64); ok {
				cfg.MultiModelCards = append(cfg.MultiModelCards, int64(idNum))
			}
		}
	}
	if specific, ok := pe.Params["specific_card_nos"].([]interface{}); ok {
		for _, id := range specific {
			if idNum, ok := id.(float64); ok {
				cfg.SpecificCardNos = append(cfg.SpecificCardNos, int64(idNum))
			}
		}
	}
	if zone, ok := pe.Params["zone"].(string); ok {
		cfg.Zone = zone
	}
	if exclude, ok := pe.Params["exclude_self"].(bool); ok {
		cfg.ExcludeSelf = exclude
	}

	return cfg
}

// PlatformEffectConfig stores the configuration for a platform effect.
type PlatformEffectConfig struct {
	TargetFaction   string   `json:"target_faction,omitempty"`    // "SD", "Tenki", etc.
	TargetCardTypes []string `json:"target_card_types,omitempty"` // ["Compute", "AI/ML"]
	Bonus           int64    `json:"bonus,omitempty"`             // Bonus amount
	Reduction       int64    `json:"reduction,omitempty"`         // Cost reduction amount
	ApplyToSelf     bool     `json:"apply_to_self,omitempty"`     // Include self
}

// GetPlatformConfig parses the Params map into a typed config.
func (pe *PlatformEffect) GetConfig() *PlatformEffectConfig {
	cfg := &PlatformEffectConfig{}

	if faction, ok := pe.Params["target_faction"].(string); ok {
		cfg.TargetFaction = faction
	}
	if cardTypes, ok := pe.Params["target_card_types"].([]interface{}); ok {
		for _, ct := range cardTypes {
			if s, ok := ct.(string); ok {
				cfg.TargetCardTypes = append(cfg.TargetCardTypes, s)
			}
		}
	}
	if bonus, ok := pe.Params["bonus"].(float64); ok {
		cfg.Bonus = int64(bonus)
	}
	if reduction, ok := pe.Params["reduction"].(float64); ok {
		cfg.Reduction = int64(reduction)
	}
	if applyToSelf, ok := pe.Params["apply_to_self"].(bool); ok {
		cfg.ApplyToSelf = applyToSelf
	}

	return cfg
}

// AttachmentEffectConfig stores the configuration for an attachment effect.
type AttachmentEffectConfig struct {
	StatType string `json:"stat_type"` // "tp", "yield", "av"
	Bonus    int64  `json:"bonus"`     // Can be negative
}

// GetAttachmentConfig parses the Params map into a typed config.
func (ae *AttachmentEffect) GetConfig() *AttachmentEffectConfig {
	cfg := &AttachmentEffectConfig{}

	if statType, ok := ae.Params["stat_type"].(string); ok {
		cfg.StatType = statType
	}
	if bonus, ok := ae.Params["bonus"].(float64); ok {
		cfg.Bonus = int64(bonus)
	}

	return cfg
}
