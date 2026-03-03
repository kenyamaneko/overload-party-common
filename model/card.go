package model

import (
	"encoding/json"
	"time"
)

type CardDefinition struct {
	CardNo            int64              `json:"card_no"`
	CardName          string             `json:"card_name"`
	ResourceLabel     string             `json:"resource_label"`
	Faction           string             `json:"faction"`
	CardType          string             `json:"card_type"`
	DeployTurns       int64              `json:"deploy_turns"`
	Resizable         bool               `json:"resizable"`
	Elastic           bool               `json:"elastic"`
	ElasticIncrement  int64              `json:"elastic_increment,omitempty"`
	FreeTier          int64              `json:"free_tier,omitempty"`
	CostPerRequest    int64              `json:"cost_per_request,omitempty"`
	Stats             json.RawMessage    `json:"stats"`
	EffectText        *string            `json:"effect_text,omitempty"`
	Effects           json.RawMessage    `json:"effects,omitempty"`            // structured effect definitions (array)
	PassiveEffects    []PassiveEffect    `json:"passive_effects,omitempty"`    // continuous/passive effects
	PlatformEffects   []PlatformEffect   `json:"platform_effects,omitempty"`   // effects to allies (Platform cards)
	AttachmentEffects []AttachmentEffect `json:"attachment_effects,omitempty"` // effects to host (Attachment cards)
	Restriction       string             `json:"restriction"`
	IsActive          bool               `json:"is_active"`
	CreatedAt         time.Time          `json:"created_at"`
	UpdatedAt         time.Time          `json:"updated_at"`
}
