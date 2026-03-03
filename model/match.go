package model

import "time"

// Match maps to the Matches table.
type Match struct {
	MatchID   int64     `json:"match_id"`
	GameID    string    `json:"game_id"`
	CreatedAt time.Time `json:"created_at"`
}
