package model

import (
	"encoding/json"
	"fmt"
	"time"
)

// Game maps to the Games table.
type Game struct {
	GameID              string          `json:"game_id" db:"game_id"`
	Player1ID           string          `json:"player1_id" db:"player1_id"`
	Player2ID           string          `json:"player2_id" db:"player2_id"`
	Player1DeckSnapshot json.RawMessage `json:"player1_deck_snapshot" db:"player1_deck_snapshot"`
	Player2DeckSnapshot json.RawMessage `json:"player2_deck_snapshot" db:"player2_deck_snapshot"`
	Status              string          `json:"status" db:"status"`
	WinnerID            *string         `json:"winner_id,omitempty" db:"winner_id"`
	CreatedAt           time.Time       `json:"created_at" db:"created_at"`
	UpdatedAt           time.Time       `json:"updated_at" db:"updated_at"`
	FinishedAt          *time.Time      `json:"finished_at,omitempty" db:"finished_at"`
}

// Game status constants are generated in constants_gen.go.

// GameState maps to the GameStates table (interleaved in Games).
type GameState struct {
	GameID             string          `json:"game_id" db:"game_id"`
	Version            int64           `json:"version" db:"version"`
	CurrentTurn        int64           `json:"current_turn" db:"current_turn"`
	CurrentPhase       string          `json:"current_phase" db:"current_phase"`
	ActivePlayer       int64           `json:"active_player" db:"active_player"`
	Player1Budget      int64           `json:"player1_budget" db:"player1_budget"`
	Player1InsightPool int64           `json:"player1_insight_pool" db:"player1_insight_pool"`
	Player1Field       json.RawMessage `json:"player1_field" db:"player1_field"`
	Player1Hand        json.RawMessage `json:"player1_hand" db:"player1_hand"`
	Player1Repository  json.RawMessage `json:"player1_repository" db:"player1_repository"`
	Player1Trash       json.RawMessage `json:"player1_trash" db:"player1_trash"`
	Player1TimeBank    int64           `json:"player1_time_bank" db:"player1_time_bank"`
	Player2Budget      int64           `json:"player2_budget" db:"player2_budget"`
	Player2InsightPool int64           `json:"player2_insight_pool" db:"player2_insight_pool"`
	Player2Field       json.RawMessage `json:"player2_field" db:"player2_field"`
	Player2Hand        json.RawMessage `json:"player2_hand" db:"player2_hand"`
	Player2Repository  json.RawMessage `json:"player2_repository" db:"player2_repository"`
	Player2Trash       json.RawMessage `json:"player2_trash" db:"player2_trash"`
	Player2TimeBank    int64           `json:"player2_time_bank" db:"player2_time_bank"`
	ChainStack         json.RawMessage `json:"chain_stack,omitempty" db:"chain_stack"`
	CurrentActionTimer *int64          `json:"current_action_timer,omitempty" db:"current_action_timer"`
	NextInstanceSeq    int64           `json:"next_instance_seq" db:"next_instance_seq"`
	UpdatedAt          time.Time       `json:"updated_at" db:"updated_at"`
}

// NextInstanceID increments the sequence counter and returns a zero-padded instance ID.
func (gs *GameState) NextInstanceID() string {
	gs.NextInstanceSeq++
	return fmt.Sprintf("i%04d", gs.NextInstanceSeq)
}

// GameEvent maps to the GameEvents table (interleaved in Games).
type GameEvent struct {
	GameID         string          `json:"game_id" db:"game_id"`
	SequenceNumber int64           `json:"sequence_number" db:"sequence_number"`
	EventType      string          `json:"event_type" db:"event_type"`
	PlayerID       *string         `json:"player_id,omitempty" db:"player_id"`
	EventData      json.RawMessage `json:"event_data" db:"event_data"`
	CreatedAt      time.Time       `json:"created_at" db:"created_at"`
}
