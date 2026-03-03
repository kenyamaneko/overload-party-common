package model

import "encoding/json"

// Phase, Rank, Family, InitialValues, GameStatus, WinReason, Faction constants
// are generated in constants_gen.go from data/constants.json.

// Field represents one player's complete field layout.
// Each zone has 3 slots. nil means the slot is empty.
type Field struct {
	Frontend               [3]*ResourceInstance `json:"frontend"`
	Backend                [3]*ResourceInstance `json:"backend"`
	Support                [3]*SupportInstance  `json:"support"`
	IncidentPlayedThisTurn bool                 `json:"incidentPlayedThisTurn,omitempty"`
	HasHadActiveResource   bool                 `json:"hasHadActiveResource,omitempty"`
}

// ResourceInstance is a card deployed on the frontend or backend zone.
type ResourceInstance struct {
	InstanceID          string            `json:"instanceId"`
	CardID              int64             `json:"cardId"`
	Rank                string            `json:"rank"`
	InstanceFamily      *string           `json:"instanceFamily"`
	FaceUp              bool              `json:"faceUp"`
	DeployingTurnsLeft  int64             `json:"deployingTurnsLeft,omitempty"`
	CurrentAV           int64             `json:"currentAV"`
	MaxAV               int64             `json:"maxAV"`
	CurrentTP           *int64            `json:"currentTP,omitempty"`
	MaxTP               *int64            `json:"maxTP,omitempty"`
	CurrentYield        *int64            `json:"currentYield,omitempty"`
	MaxYield            *int64            `json:"maxYield,omitempty"`
	Damage              int64             `json:"damage"`
	Attachments         []AttachmentRef   `json:"attachments"`
	TemporaryEffects    []TemporaryEffect `json:"temporaryEffects"`
	MonetizedAmount     int64             `json:"monetizedAmount"`
	HasAttacked         bool              `json:"hasAttacked"`
	EffectUsedThisTurn  bool              `json:"effectUsedThisTurn,omitempty"`
	DeployedOnTurn      int64             `json:"deployedOnTurn,omitempty"`
	DeployOrder         int64             `json:"deployOrder,omitempty"`
	MigratingFrom       *string           `json:"migratingFrom,omitempty"`   // new resource: old resource's InstanceID
	MigrationTarget     *string           `json:"migrationTarget,omitempty"` // old resource: new resource's InstanceID
	MigratingOnTurn     int64             `json:"migratingOnTurn,omitempty"` // turn when migration started
	ElasticBonus        int64             `json:"elasticBonus,omitempty"`    // accumulated Elastic auto-scaling bonus
}

// AttachmentRef references an attachment card on a resource.
type AttachmentRef struct {
	InstanceID string `json:"instanceId"`
	CardID     int64  `json:"cardId"`
}

// TemporaryEffect is a time-limited modifier on a resource.
type TemporaryEffect struct {
	EffectType string `json:"effectType"`
	Value      int64  `json:"value"`
	Duration   string `json:"duration"` // "this_turn", "until_next_turn_end"
	SourceID   string `json:"sourceId"`
}

// SupportInstance is a Platform or Reactive card in the support zone.
type SupportInstance struct {
	InstanceID          string `json:"instanceId"`
	CardID              int64  `json:"cardId"`
	FaceDown            bool   `json:"faceDown"`
	DeployingTurnsLeft  int64  `json:"deployingTurnsLeft,omitempty"`
	DeployOrder         int64  `json:"deployOrder,omitempty"`
	EffectUsedThisTurn  bool   `json:"effectUsedThisTurn,omitempty"`
}

// HandCard represents a card in a player's hand.
type HandCard struct {
	InstanceID string `json:"instanceId"`
	CardID     int64  `json:"cardId"`
}

// ChainEntry is one entry in the chain stack.
type ChainEntry struct {
	ChainLevel       int64           `json:"chainLevel"`
	ActionType       string          `json:"actionType"` // "attack", "component_effect", "reactive"
	SourcePlayerID   string          `json:"sourcePlayerId"`
	SourceInstanceID string          `json:"sourceInstanceId"`
	TargetInstanceID string          `json:"targetInstanceId"`
	TargetChainLevel int64           `json:"targetChainLevel"`
	EffectData       json.RawMessage `json:"effectData,omitempty"`
	Resolved         bool            `json:"resolved"`
}

// DeckSnapshot is stored in Games.playerN_deck_snapshot.
type DeckSnapshot struct {
	DeckID string  `json:"deckId"`
	Cards  []int64 `json:"cards"` // card_no list (shuffled order)
}
